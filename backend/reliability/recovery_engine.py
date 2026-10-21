"""Recovery Engine orchestrating intelligent, bounded, failure-specific recovery and fixed retry."""
from __future__ import annotations
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from backend.agents.mock_model import MockModelAdapter
from backend.agents.model_adapter import BaseModelAdapter
from backend.agents.tool_registry import ToolExecutor, ToolRegistry
from backend.models.schemas import (
    InteractionStep,
    TaskResponse,
    ToolCallRequest,
    ToolResult,
    TraceEvent,
    VerificationResult,
    VerificationRule,
)
from backend.reliability.diagnostic_report import DiagnosticReport, FailureCategory
from backend.reliability.recovery_actions import (
    PolicyATransientRetryAction,
    PolicyBInvalidArgumentAction,
    PolicyCRepeatedActionsAction,
    PolicyDMissingEvidenceAction,
    PolicyEIncorrectAnswerAction,
    PolicyFStepLimitContinuationAction,
    PolicyGUnverifiedCompletionAction,
    PolicyHMalformedOutputAction,
)
from backend.reliability.recovery_budget import RecoveryBudgetConfig, RecoveryBudgetTracker
from backend.reliability.recovery_policy import PolicyDecision, PolicySelector
from backend.reliability.recovery_report import (
    RecoveryAttemptReport,
    RecoveryPolicyType,
    RecoveryReport,
    RecoveryTerminalStatus,
)
from backend.reliability.recovery_state import RecoveryCheckpoint, RecoveryStateManager
from backend.reliability.recovery_verifier import RecoveryVerifier
from backend.tracing.collector import TraceCollector
from backend.tracing.event_schema import (
    EVENT_DIAGNOSTIC_REPORT_CREATED,
    EVENT_RECOVERY_ACTION_COMPLETED,
    EVENT_RECOVERY_ACTION_FAILED,
    EVENT_RECOVERY_ACTION_STARTED,
    EVENT_RECOVERY_ATTEMPT_COMPLETED,
    EVENT_RECOVERY_BUDGET_CHECKED,
    EVENT_RECOVERY_BUDGET_EXHAUSTED,
    EVENT_RECOVERY_POLICY_REJECTED,
    EVENT_RECOVERY_POLICY_SELECTED,
    EVENT_RECOVERY_STARTED,
    EVENT_RECOVERY_VERIFICATION_COMPLETED,
    EVENT_TASK_RECOVERED,
    EVENT_TASK_UNRESOLVED,
    current_utc_timestamp,
)
from backend.tracing.storage import TraceStorage

logger = logging.getLogger(__name__)

class RecoveryEngine:
    """Orchestrates trajectory diagnosis, policy selection, safe intervention, tracing, and verification."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        model_adapter: Optional[BaseModelAdapter] = None,
        storage: Optional[TraceStorage] = None,
        budget_config: Optional[RecoveryBudgetConfig] = None,
    ):
        self.tool_registry = tool_registry or ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.model_adapter = model_adapter or MockModelAdapter()
        self.storage = storage or TraceStorage()
        self.budget_config = budget_config or RecoveryBudgetConfig()

    def recover(
        self,
        task_response: TaskResponse,
        task_context: Dict[str, Any],
        initial_trace_events: List[TraceEvent],
        diag_report: DiagnosticReport,
        experiment_id: Optional[str] = None,
    ) -> RecoveryReport:
        """Execute intelligent recovery workflow consuming Milestone 3 diagnostic report."""
        recovery_id = f"rec_{uuid.uuid4().hex[:12]}"
        recovery_attempt_id = f"atm_{uuid.uuid4().hex[:10]}"
        start_time = time.perf_counter()

        collector = TraceCollector(task_id=task_response.task_id, run_id=task_response.run_id, storage=self.storage)
        budget_tracker = RecoveryBudgetTracker(
            config=self.budget_config,
            initial_task_duration_ms=task_response.duration_ms,
        )

        collector.record_recovery_event(
            step_index=task_response.steps_count + 1,
            event_type=EVENT_DIAGNOSTIC_REPORT_CREATED,
            status="completed",
            recovery_attempt_id=recovery_attempt_id,
            input_summary=f"Diagnostic report: status={diag_report.diagnostic_status}, severity={diag_report.severity}",
        )

        # 1. Deterministic Policy Selection
        trace_dicts = [e.model_dump() for e in initial_trace_events]
        decision: PolicyDecision = PolicySelector.select_policy(
            diagnostic_report=diag_report,
            budget_tracker=budget_tracker,
            task_context=task_context,
            trace_events=trace_dicts,
        )

        collector.record_recovery_event(
            step_index=task_response.steps_count + 1,
            event_type=EVENT_RECOVERY_BUDGET_CHECKED,
            status="checked",
            recovery_attempt_id=recovery_attempt_id,
            policy_id=decision.policy_id.value,
            remaining_budget=budget_tracker.remaining_summary(),
        )

        if not decision.can_execute:
            collector.record_recovery_event(
                step_index=task_response.steps_count + 1,
                event_type=EVENT_RECOVERY_POLICY_REJECTED,
                status="rejected",
                recovery_attempt_id=recovery_attempt_id,
                policy_id=decision.policy_id.value,
                output_summary=decision.reason,
            )
            collector.record_recovery_event(
                step_index=task_response.steps_count + 1,
                event_type=EVENT_TASK_UNRESOLVED,
                status="unresolved",
                recovery_attempt_id=recovery_attempt_id,
                output_summary=decision.expected_outcome,
            )
            collector.flush()

            terminal_status = RecoveryVerifier.determine_terminal_status(
                original_status=task_response.status,
                original_verification=task_response.verification,
                recovery_attempted=False,
                final_verification=task_response.verification,
                budget_tracker=budget_tracker,
                final_answer=task_response.final_answer,
            )

            report = RecoveryReport(
                recovery_id=recovery_id,
                task_id=task_response.task_id,
                run_id=task_response.run_id,
                recovery_attempt_id=recovery_attempt_id,
                experiment_id=experiment_id,
                recovery_attempted=False,
                policy_id=decision.policy_id.value,
                initial_failure_category=decision.initial_failure_category,
                diagnostic_finding_ids=decision.finding_ids,
                preconditions=decision.preconditions,
                selection_reason=decision.reason,
                terminal_status=terminal_status,
                original_status=task_response.status,
                original_verification_status=task_response.verification.status if task_response.verification else None,
                final_verification_status=task_response.verification.status if task_response.verification else None,
                final_answer=task_response.final_answer,
                attempts=[],
                total_recovery_duration_ms=0.0,
                total_execution_duration_ms=task_response.duration_ms,
                additional_tool_calls=0,
                additional_model_calls=0,
                budget_usage=budget_tracker.to_usage_model(),
            )
            self.storage.save_recovery_report(report)
            return report

        # Policy was selected and can execute!
        collector.record_recovery_event(
            step_index=task_response.steps_count + 1,
            event_type=EVENT_RECOVERY_POLICY_SELECTED,
            status="selected",
            recovery_attempt_id=recovery_attempt_id,
            policy_id=decision.policy_id.value,
            action_type=decision.action_type,
            finding_ids=decision.finding_ids,
            output_summary=decision.reason,
        )

        collector.record_recovery_event(
            step_index=task_response.steps_count + 1,
            event_type=EVENT_RECOVERY_STARTED,
            status="started",
            recovery_attempt_id=recovery_attempt_id,
            policy_id=decision.policy_id.value,
            action_type=decision.action_type,
        )

        budget_tracker.record_attempt()

        # Build checkpoint
        history_steps = self._reconstruct_history(initial_trace_events)
        checkpoint = RecoveryStateManager.create_checkpoint(
            task_id=task_response.task_id,
            run_id=task_response.run_id,
            recovery_attempt_id=recovery_attempt_id,
            step_index=task_response.steps_count,
            history=history_steps,
        )

        # 2. Execute Policy Action
        attempt_report = self._execute_selected_policy(
            decision=decision,
            task_response=task_response,
            task_context=task_context,
            checkpoint=checkpoint,
            initial_trace_events=initial_trace_events,
            budget_tracker=budget_tracker,
            recovery_attempt_id=recovery_attempt_id,
            collector=collector,
        )

        total_rec_dur_ms = (time.perf_counter() - start_time) * 1000
        budget_tracker.record_duration(total_rec_dur_ms)

        final_verif = attempt_report.verification_result
        final_ans = attempt_report.intermediate_answer

        collector.record_recovery_event(
            step_index=task_response.steps_count + len(attempt_report.actions) + 1,
            event_type=EVENT_RECOVERY_VERIFICATION_COMPLETED,
            status="completed",
            recovery_attempt_id=recovery_attempt_id,
            output_summary=f"Final Verification: {final_verif.status if final_verif else 'none'} (verified={final_verif.verified if final_verif else False})",
        )

        terminal_status = RecoveryVerifier.determine_terminal_status(
            original_status=task_response.status,
            original_verification=task_response.verification,
            recovery_attempted=True,
            final_verification=final_verif,
            budget_tracker=budget_tracker,
            error_info=attempt_report.error_message,
            final_answer=final_ans,
        )

        if terminal_status == RecoveryTerminalStatus.RECOVERED_SUCCESSFULLY:
            collector.record_recovery_event(
                step_index=task_response.steps_count + len(attempt_report.actions) + 2,
                event_type=EVENT_TASK_RECOVERED,
                status="success",
                recovery_attempt_id=recovery_attempt_id,
                output_summary=f"Task recovered with final answer: {final_ans}",
            )
        else:
            collector.record_recovery_event(
                step_index=task_response.steps_count + len(attempt_report.actions) + 2,
                event_type=EVENT_TASK_UNRESOLVED,
                status="unresolved",
                recovery_attempt_id=recovery_attempt_id,
                output_summary=f"Task ended with terminal status: {terminal_status.value}",
            )

        if budget_tracker.is_exhausted:
            collector.record_recovery_event(
                step_index=task_response.steps_count + len(attempt_report.actions) + 3,
                event_type=EVENT_RECOVERY_BUDGET_EXHAUSTED,
                status="exhausted",
                recovery_attempt_id=recovery_attempt_id,
                output_summary=budget_tracker.exhausted_limit,
            )

        collector.flush()

        report = RecoveryReport(
            recovery_id=recovery_id,
            task_id=task_response.task_id,
            run_id=task_response.run_id,
            recovery_attempt_id=recovery_attempt_id,
            experiment_id=experiment_id,
            recovery_attempted=True,
            policy_id=decision.policy_id.value,
            initial_failure_category=decision.initial_failure_category,
            diagnostic_finding_ids=decision.finding_ids,
            preconditions=decision.preconditions,
            selection_reason=decision.reason,
            terminal_status=terminal_status,
            original_status=task_response.status,
            original_verification_status=task_response.verification.status if task_response.verification else None,
            final_verification_status=final_verif.status if final_verif else None,
            final_answer=final_ans,
            attempts=[attempt_report],
            total_recovery_duration_ms=round(total_rec_dur_ms, 2),
            total_execution_duration_ms=round(task_response.duration_ms + total_rec_dur_ms, 2),
            additional_tool_calls=budget_tracker.tool_calls_used,
            additional_model_calls=budget_tracker.model_calls_used,
            budget_usage=budget_tracker.to_usage_model(),
        )
        self.storage.save_recovery_report(report)
        return report

    def _execute_selected_policy(
        self,
        decision: PolicyDecision,
        task_response: TaskResponse,
        task_context: Dict[str, Any],
        checkpoint: RecoveryCheckpoint,
        initial_trace_events: List[TraceEvent],
        budget_tracker: RecoveryBudgetTracker,
        recovery_attempt_id: str,
        collector: TraceCollector,
    ) -> RecoveryAttemptReport:
        """Dispatch concrete policy action."""
        step_idx = task_response.steps_count + 1
        collector.record_recovery_event(
            step_index=step_idx,
            event_type=EVENT_RECOVERY_ACTION_STARTED,
            status="started",
            recovery_attempt_id=recovery_attempt_id,
            policy_id=decision.policy_id.value,
            action_type=decision.action_type,
        )

        task_text = task_response.task
        allowed_tools = task_context.get("allowed_tools")
        verif_rule_dict = task_context.get("verification_rule")
        verif_rule = VerificationRule.model_validate(verif_rule_dict) if verif_rule_dict else None

        last_tool_call, last_err, repeated_tool = self._extract_trace_context(initial_trace_events)

        final_ans = None
        verif_res = None
        action_records = []
        action_err = None

        policy = decision.policy_id

        if policy == RecoveryPolicyType.POLICY_A_TRANSIENT_TOOL_FAILURE:
            action_a = PolicyATransientRetryAction(self.tool_registry, self.tool_executor, self.model_adapter, budget_tracker)
            final_ans, verif_res, action_records, action_err = action_a.execute(
                task=task_text,
                checkpoint=checkpoint,
                last_tool_call=last_tool_call,
                allowed_tools=allowed_tools,
                verification_rule=verif_rule,
            )

        elif policy == RecoveryPolicyType.POLICY_B_INVALID_TOOL_ARGUMENTS:
            action_b = PolicyBInvalidArgumentAction(self.tool_registry, self.tool_executor, self.model_adapter, budget_tracker)
            final_ans, verif_res, action_records, action_err = action_b.execute(
                task=task_text,
                checkpoint=checkpoint,
                invalid_tool_call=last_tool_call,
                validation_error=last_err or "Invalid tool arguments schema",
                allowed_tools=allowed_tools,
                verification_rule=verif_rule,
            )

        elif policy == RecoveryPolicyType.POLICY_C_REPEATED_ACTIONS:
            action_c = PolicyCRepeatedActionsAction(self.tool_registry, self.tool_executor, self.model_adapter, budget_tracker)
            final_ans, verif_res, action_records, action_err = action_c.execute(
                task=task_text,
                checkpoint=checkpoint,
                repeated_tool_name=repeated_tool,
                allowed_tools=allowed_tools,
                verification_rule=verif_rule,
            )

        elif policy == RecoveryPolicyType.POLICY_D_MISSING_EVIDENCE:
            action_d = PolicyDMissingEvidenceAction(self.tool_registry, self.tool_executor, self.model_adapter, budget_tracker)
            final_ans, verif_res, action_records, action_err = action_d.execute(
                task=task_text,
                checkpoint=checkpoint,
                allowed_tools=allowed_tools,
                verification_rule=verif_rule,
            )

        elif policy == RecoveryPolicyType.POLICY_E_INCORRECT_ANSWER:
            action_e = PolicyEIncorrectAnswerAction(self.tool_registry, self.tool_executor, self.model_adapter, budget_tracker)
            msg = task_response.verification.verification_message if task_response.verification else "Verification failed"
            final_ans, verif_res, action_records, action_err = action_e.execute(
                task=task_text,
                checkpoint=checkpoint,
                original_final_answer=task_response.final_answer,
                verification_message=msg,
                verification_rule=verif_rule,
            )

        elif policy == RecoveryPolicyType.POLICY_F_STEP_LIMIT_EXHAUSTION:
            action_f = PolicyFStepLimitContinuationAction(self.tool_registry, self.tool_executor, self.model_adapter, budget_tracker)
            final_ans, verif_res, action_records, action_err = action_f.execute(
                task=task_text,
                checkpoint=checkpoint,
                verification_rule=verif_rule,
            )

        elif policy == RecoveryPolicyType.POLICY_G_UNVERIFIED_COMPLETION:
            action_g = PolicyGUnverifiedCompletionAction(self.tool_registry, self.tool_executor, self.model_adapter, budget_tracker)
            final_ans, verif_res, action_records, action_err = action_g.execute(
                task=task_text,
                final_answer=task_response.final_answer,
                verification_rule=verif_rule,
            )

        elif policy == RecoveryPolicyType.POLICY_H_MALFORMED_OUTPUT:
            action_h = PolicyHMalformedOutputAction(self.tool_registry, self.tool_executor, self.model_adapter, budget_tracker)
            final_ans, verif_res, action_records, action_err = action_h.execute(
                task=task_text,
                checkpoint=checkpoint,
                verification_rule=verif_rule,
            )

        status = "completed" if verif_res and verif_res.verified else ("failed" if action_err else "unresolved")

        collector.record_recovery_event(
            step_index=step_idx + 1,
            event_type=EVENT_RECOVERY_ACTION_COMPLETED if not action_err else EVENT_RECOVERY_ACTION_FAILED,
            status=status,
            recovery_attempt_id=recovery_attempt_id,
            policy_id=decision.policy_id.value,
            action_type=decision.action_type,
            output_summary=f"Final Answer: {final_ans}, Verified: {verif_res.verified if verif_res else False}",
            error_type=action_err,
        )

        collector.record_recovery_event(
            step_index=step_idx + 2,
            event_type=EVENT_RECOVERY_ATTEMPT_COMPLETED,
            status=status,
            recovery_attempt_id=recovery_attempt_id,
            policy_id=decision.policy_id.value,
        )

        return RecoveryAttemptReport(
            attempt_id=recovery_attempt_id,
            attempt_index=1,
            policy_id=decision.policy_id.value,
            action_type=decision.action_type,
            status=status,
            actions=action_records,
            intermediate_answer=final_ans,
            verification_result=verif_res,
            error_message=action_err,
        )

    def _extract_trace_context(
        self,
        trace_events: List[TraceEvent]
    ) -> Tuple[Optional[ToolCallRequest], Optional[str], Optional[str]]:
        last_tool_call = None
        last_err = None
        repeated_tool = None
        tool_counts: Dict[str, int] = {}

        for ev in trace_events:
            if ev.event_type == "tool_call_requested" and ev.tool_name:
                tool_counts[ev.tool_name] = tool_counts.get(ev.tool_name, 0) + 1
                args = {}
                if ev.input_summary:
                    try:
                        args = json.loads(ev.input_summary)
                    except Exception:
                        pass
                last_tool_call = ToolCallRequest(tool_name=ev.tool_name, arguments=args)
            elif ev.event_type == "tool_execution_failed":
                last_err = ev.output_summary or ev.error_type

        for tool, count in tool_counts.items():
            if count >= 2:
                repeated_tool = tool
                break

        return last_tool_call, last_err, repeated_tool

    def _reconstruct_history(self, trace_events: List[TraceEvent]) -> List[InteractionStep]:
        history = []
        for ev in trace_events:
            if ev.event_type == "tool_call_requested" and ev.tool_name:
                args = {}
                try:
                    args = json.loads(ev.input_summary or "{}")
                except Exception:
                    pass
                history.append(InteractionStep(
                    step_index=ev.step_index,
                    role="assistant",
                    tool_call=ToolCallRequest(tool_name=ev.tool_name, arguments=args),
                ))
            elif ev.event_type in ("tool_execution_completed", "tool_execution_failed") and ev.tool_name:
                data = None
                try:
                    data = json.loads(ev.output_summary or "null")
                except Exception:
                    data = ev.output_summary
                history.append(InteractionStep(
                    step_index=ev.step_index,
                    role="tool",
                    tool_result=ToolResult(
                        tool_name=ev.tool_name,
                        success=(ev.event_type == "tool_execution_completed"),
                        data=data if ev.event_type == "tool_execution_completed" else None,
                        error=ev.output_summary if ev.event_type == "tool_execution_failed" else None,
                    ),
                ))
        return history

class FixedRetryEngine:
    """Fixed-retry baseline strategy: retries transient tool failures without trajectory diagnosis or replanning."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        storage: Optional[TraceStorage] = None,
        budget_config: Optional[RecoveryBudgetConfig] = None,
    ):
        self.tool_registry = tool_registry or ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.storage = storage or TraceStorage()
        self.budget_config = budget_config or RecoveryBudgetConfig(max_recovery_attempts=1, max_retries_per_tool=2)

    def execute_fixed_retry(
        self,
        task_response: TaskResponse,
        task_context: Dict[str, Any],
        initial_trace_events: List[TraceEvent],
        experiment_id: Optional[str] = None,
    ) -> RecoveryReport:
        """Apply blind bounded retry to eligible transient tool failure only."""
        recovery_id = f"fix_{uuid.uuid4().hex[:12]}"
        recovery_attempt_id = f"fatm_{uuid.uuid4().hex[:10]}"
        t_start = time.perf_counter()

        collector = TraceCollector(task_id=task_response.task_id, run_id=task_response.run_id, storage=self.storage)
        budget_tracker = RecoveryBudgetTracker(
            config=self.budget_config,
            initial_task_duration_ms=task_response.duration_ms,
        )

        # Check if the failure was a transient tool failure
        has_transient_failure = False
        last_tool_call = None
        for ev in initial_trace_events:
            if ev.event_type == "tool_call_requested" and ev.tool_name:
                args = {}
                try:
                    args = json.loads(ev.input_summary or "{}")
                except Exception:
                    pass
                last_tool_call = ToolCallRequest(tool_name=ev.tool_name, arguments=args)
            if ev.event_type == "tool_execution_failed":
                has_transient_failure = True

        if not has_transient_failure or not last_tool_call:
            # Fixed retry only retries transient tool failures
            terminal_status = RecoveryVerifier.determine_terminal_status(
                original_status=task_response.status,
                original_verification=task_response.verification,
                recovery_attempted=False,
                final_verification=task_response.verification,
                budget_tracker=budget_tracker,
                final_answer=task_response.final_answer,
            )
            report = RecoveryReport(
                recovery_id=recovery_id,
                task_id=task_response.task_id,
                run_id=task_response.run_id,
                recovery_attempt_id=recovery_attempt_id,
                experiment_id=experiment_id,
                recovery_attempted=False,
                policy_id="fixed_retry",
                selection_reason="Fixed retry strategy only retries eligible transient tool failures; skipped.",
                terminal_status=terminal_status,
                original_status=task_response.status,
                original_verification_status=task_response.verification.status if task_response.verification else None,
                final_verification_status=task_response.verification.status if task_response.verification else None,
                final_answer=task_response.final_answer,
                attempts=[],
                total_recovery_duration_ms=0.0,
                total_execution_duration_ms=task_response.duration_ms,
                budget_usage=budget_tracker.to_usage_model(),
            )
            self.storage.save_recovery_report(report)
            return report

        # Execute fixed retry
        collector.record_recovery_event(
            step_index=task_response.steps_count + 1,
            event_type=EVENT_RECOVERY_STARTED,
            status="started",
            recovery_attempt_id=recovery_attempt_id,
            policy_id="fixed_retry",
            action_type="fixed_retry_tool_execution",
        )
        budget_tracker.record_attempt()
        budget_tracker.record_tool_call(last_tool_call.tool_name, is_retry=True)

        tool_res = self.tool_executor.execute(last_tool_call, allowed_tools=task_context.get("allowed_tools"))
        dur_ms = (time.perf_counter() - t_start) * 1000
        budget_tracker.record_duration(dur_ms)

        final_ans = str(tool_res.data) if tool_res.success else None
        verif_rule_dict = task_context.get("verification_rule")
        verif_rule = VerificationRule.model_validate(verif_rule_dict) if verif_rule_dict else None
        verif_res = RecoveryVerifier.verify_recovery_result(final_ans, verif_rule) if final_ans else None

        terminal_status = RecoveryVerifier.determine_terminal_status(
            original_status=task_response.status,
            original_verification=task_response.verification,
            recovery_attempted=True,
            final_verification=verif_res,
            budget_tracker=budget_tracker,
            error_info=tool_res.error,
            final_answer=final_ans,
        )

        collector.record_recovery_event(
            step_index=task_response.steps_count + 2,
            event_type=EVENT_RECOVERY_ATTEMPT_COMPLETED,
            status="completed" if tool_res.success else "failed",
            recovery_attempt_id=recovery_attempt_id,
            policy_id="fixed_retry",
            action_type="fixed_retry_tool_execution",
            output_summary=f"Result: {tool_res.success}",
        )
        collector.flush()

        report = RecoveryReport(
            recovery_id=recovery_id,
            task_id=task_response.task_id,
            run_id=task_response.run_id,
            recovery_attempt_id=recovery_attempt_id,
            experiment_id=experiment_id,
            recovery_attempted=True,
            policy_id="fixed_retry",
            selection_reason="Fixed blind retry of last failed tool call.",
            terminal_status=terminal_status,
            original_status=task_response.status,
            original_verification_status=task_response.verification.status if task_response.verification else None,
            final_verification_status=verif_res.status if verif_res else None,
            final_answer=final_ans,
            attempts=[
                RecoveryAttemptReport(
                    attempt_id=recovery_attempt_id,
                    attempt_index=1,
                    policy_id="fixed_retry",
                    action_type="fixed_retry_tool_execution",
                    status="completed" if tool_res.success else "failed",
                    duration_ms=dur_ms,
                    intermediate_answer=final_ans,
                    verification_result=verif_res,
                    error_message=tool_res.error,
                )
            ],
            total_recovery_duration_ms=round(dur_ms, 2),
            total_execution_duration_ms=round(task_response.duration_ms + dur_ms, 2),
            additional_tool_calls=budget_tracker.tool_calls_used,
            additional_model_calls=0,
            budget_usage=budget_tracker.to_usage_model(),
        )
        self.storage.save_recovery_report(report)
        return report
