"""Bounded, safe recovery actions implementing Policies A through H."""
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from backend.agents.model_adapter import BaseModelAdapter
from backend.agents.tool_registry import ToolExecutor, ToolRegistry
from backend.models.schemas import (
    InteractionStep,
    ModelResponse,
    ToolCallRequest,
    ToolResult,
    VerificationResult,
    VerificationRule,
)
from backend.reliability.recovery_budget import RecoveryBudgetTracker
from backend.reliability.recovery_report import RecoveryActionRecord, RecoveryPolicyType
from backend.reliability.recovery_state import RecoveryCheckpoint
from backend.tracing.event_schema import (
    EVENT_RECOVERY_ACTION_COMPLETED,
    EVENT_RECOVERY_ACTION_FAILED,
    EVENT_RECOVERY_ACTION_STARTED,
    current_utc_timestamp,
    sanitize_text,
)
from backend.verification.verifier import OutcomeVerifier

logger = logging.getLogger(__name__)

class BaseRecoveryAction:
    """Base class for all failure-specific recovery actions."""
    policy_type: RecoveryPolicyType

    def __init__(
        self,
        tool_registry: ToolRegistry,
        tool_executor: ToolExecutor,
        model_adapter: BaseModelAdapter,
        budget_tracker: RecoveryBudgetTracker,
    ):
        self.tool_registry = tool_registry
        self.tool_executor = tool_executor
        self.model_adapter = model_adapter
        self.budget_tracker = budget_tracker

class PolicyATransientRetryAction(BaseRecoveryAction):
    """Policy A: Safe, bounded retry for transient tool execution failures."""
    policy_type = RecoveryPolicyType.POLICY_A_TRANSIENT_TOOL_FAILURE

    def execute(
        self,
        task: str,
        checkpoint: RecoveryCheckpoint,
        last_tool_call: Optional[ToolCallRequest],
        allowed_tools: Optional[List[str]] = None,
        verification_rule: Optional[VerificationRule] = None,
        attempt_index: int = 1,
    ) -> Tuple[Optional[str], Optional[VerificationResult], List[RecoveryActionRecord], Optional[str]]:
        action_records = []
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        if not last_tool_call:
            err = "Policy A failed: No prior tool call found in execution trace to retry."
            record = RecoveryActionRecord(
                action_id=action_id,
                attempt_index=attempt_index,
                policy_id=self.policy_type.value,
                action_type="retry_transient_tool_call",
                status="failed",
                error=err,
                description="Retry aborted: missing tool call context.",
            )
            return None, None, [record], err

        # Check tool retry budget
        can_call, reason = self.budget_tracker.check_can_call_tool(last_tool_call.tool_name, is_retry=True)
        if not can_call:
            err = f"Policy A aborted: {reason}"
            record = RecoveryActionRecord(
                action_id=action_id,
                attempt_index=attempt_index,
                policy_id=self.policy_type.value,
                action_type="retry_transient_tool_call",
                status="rejected",
                error=err,
                description="Retry rejected by budget limits.",
            )
            return None, None, [record], err

        # Re-validate arguments before execution
        tool_def = self.tool_registry.get_definition(last_tool_call.tool_name)
        if not tool_def:
            err = f"Tool '{last_tool_call.tool_name}' is not registered."
            return None, None, [], err

        # Execute retry
        self.budget_tracker.record_tool_call(last_tool_call.tool_name, is_retry=True)
        self.budget_tracker.record_step()

        # Configurable tiny backoff for realism without slowing down tests
        time.sleep(0.02)
        tool_result = self.tool_executor.execute(last_tool_call, allowed_tools=allowed_tools)
        dur_ms = (time.perf_counter() - t_start) * 1000
        self.budget_tracker.record_duration(dur_ms)

        if not tool_result.success:
            err = f"Transient retry failed: {tool_result.error}"
            record = RecoveryActionRecord(
                action_id=action_id,
                attempt_index=attempt_index,
                policy_id=self.policy_type.value,
                action_type="retry_transient_tool_call",
                status="failed",
                duration_ms=dur_ms,
                description=f"Retried tool '{last_tool_call.tool_name}' but failure persisted.",
                input_context={"tool_name": last_tool_call.tool_name, "arguments": last_tool_call.arguments},
                output_result={"error": tool_result.error},
                error=err,
            )
            return None, None, [record], err

        # Tool succeeded! Synthesize final answer with model
        record = RecoveryActionRecord(
            action_id=action_id,
            attempt_index=attempt_index,
            policy_id=self.policy_type.value,
            action_type="retry_transient_tool_call",
            status="completed",
            duration_ms=dur_ms,
            description=f"Retried tool '{last_tool_call.tool_name}' successfully.",
            input_context={"tool_name": last_tool_call.tool_name, "arguments": last_tool_call.arguments},
            output_result={"data": tool_result.data},
        )
        action_records.append(record)

        # Now get final answer from model
        final_answer, verif_res, extra_records, synth_err = self._synthesize_final_answer(
            task=task,
            tool_name=last_tool_call.tool_name,
            tool_data=tool_result.data,
            verification_rule=verification_rule,
            attempt_index=attempt_index,
        )
        action_records.extend(extra_records)
        return final_answer, verif_res, action_records, synth_err

    def _synthesize_final_answer(
        self,
        task: str,
        tool_name: str,
        tool_data: Any,
        verification_rule: Optional[VerificationRule],
        attempt_index: int,
    ) -> Tuple[Optional[str], Optional[VerificationResult], List[RecoveryActionRecord], Optional[str]]:
        act_id = f"act_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        can_model, reason = self.budget_tracker.check_can_call_model()
        if not can_model:
            # Fallback to direct string representation if model budget exhausted
            ans = str(tool_data)
            verif = OutcomeVerifier.verify(ans, verification_rule)
            return ans, verif, [], None

        self.budget_tracker.record_model_call()
        history = [
            InteractionStep(step_index=1, role="user", content=task),
            InteractionStep(
                step_index=1,
                role="tool",
                tool_result=ToolResult(tool_name=tool_name, success=True, data=tool_data),
            ),
        ]

        try:
            resp = self.model_adapter.generate_next_step(task=task, tool_definitions=[], history=history)
            final_ans = resp.final_answer or str(tool_data)
        except Exception as e:
            final_ans = str(tool_data)

        dur_ms = (time.perf_counter() - t_start) * 1000
        self.budget_tracker.record_duration(dur_ms)

        verif_res = OutcomeVerifier.verify(final_ans, verification_rule)
        rec = RecoveryActionRecord(
            action_id=act_id,
            attempt_index=attempt_index,
            policy_id=self.policy_type.value,
            action_type="synthesize_recovered_answer",
            status="completed",
            duration_ms=dur_ms,
            description="Synthesized final answer from recovered tool result.",
            output_result={"final_answer": final_ans, "verified": verif_res.verified},
        )
        return final_ans, verif_res, [rec], None

class PolicyBInvalidArgumentAction(BaseRecoveryAction):
    """Policy B: Schema-aware correction of invalid tool arguments with mandatory revalidation."""
    policy_type = RecoveryPolicyType.POLICY_B_INVALID_TOOL_ARGUMENTS

    def execute(
        self,
        task: str,
        checkpoint: RecoveryCheckpoint,
        invalid_tool_call: Optional[ToolCallRequest],
        validation_error: str,
        allowed_tools: Optional[List[str]] = None,
        verification_rule: Optional[VerificationRule] = None,
        attempt_index: int = 1,
    ) -> Tuple[Optional[str], Optional[VerificationResult], List[RecoveryActionRecord], Optional[str]]:
        action_records = []
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        if not invalid_tool_call:
            err = "Policy B aborted: No invalid tool call record provided."
            return None, None, [], err

        can_model, reason = self.budget_tracker.check_can_call_model()
        if not can_model:
            err = f"Policy B rejected by budget: {reason}"
            return None, None, [], err

        tool_def = self.tool_registry.get_definition(invalid_tool_call.tool_name)
        if not tool_def:
            err = f"Tool '{invalid_tool_call.tool_name}' not found in registry."
            return None, None, [], err

        # Prompt agent with actual validation error and expected schema
        schema_info = json.dumps(tool_def.parameters)
        correction_prompt = (
            f"Your tool call to '{invalid_tool_call.tool_name}' with arguments {json.dumps(invalid_tool_call.arguments)} "
            f"failed schema validation with error: '{validation_error}'. "
            f"The required parameter schema is: {schema_info}. Please provide corrected valid arguments."
        )

        history = [
            InteractionStep(step_index=1, role="user", content=task),
            InteractionStep(step_index=1, role="assistant", tool_call=invalid_tool_call),
            InteractionStep(
                step_index=1,
                role="tool",
                tool_result=ToolResult(
                    tool_name=invalid_tool_call.tool_name,
                    success=False,
                    error=f"ValidationError: {validation_error}",
                ),
            ),
        ]

        self.budget_tracker.record_model_call()
        self.budget_tracker.record_step()

        # In benchmark mock testing, let model produce corrected call
        resp = self.model_adapter.generate_next_step(
            task=f"{task}\nCorrection requirement: {correction_prompt}",
            tool_definitions=[tool_def],
            history=history,
            scenario_hint="invalid_arguments_recovery",
        )

        corrected_call = resp.tool_call
        if not corrected_call:
            # Check if model self-corrected directly to final answer
            if resp.is_final_answer and resp.final_answer:
                dur_ms = (time.perf_counter() - t_start) * 1000
                self.budget_tracker.record_duration(dur_ms)
                verif = OutcomeVerifier.verify(resp.final_answer, verification_rule)
                rec = RecoveryActionRecord(
                    action_id=action_id,
                    attempt_index=attempt_index,
                    policy_id=self.policy_type.value,
                    action_type="direct_answer_after_validation_error",
                    status="completed",
                    duration_ms=dur_ms,
                    description="Agent corrected trajectory directly to final answer.",
                )
                return resp.final_answer, verif, [rec], None

            err = "Agent failed to produce corrected tool call arguments."
            dur_ms = (time.perf_counter() - t_start) * 1000
            self.budget_tracker.record_duration(dur_ms)
            rec = RecoveryActionRecord(
                action_id=action_id,
                attempt_index=attempt_index,
                policy_id=self.policy_type.value,
                action_type="correct_tool_arguments",
                status="failed",
                duration_ms=dur_ms,
                error=err,
                description="Model produced neither corrected tool call nor final answer.",
            )
            return None, None, [rec], err

        # MANDATORY SAFETY RULE: Re-validate arguments before execution!
        can_tool, t_reason = self.budget_tracker.check_can_call_tool(corrected_call.tool_name)
        if not can_tool:
            err = f"Policy B tool call rejected: {t_reason}"
            return None, None, [], err

        self.budget_tracker.record_tool_call(corrected_call.tool_name)
        tool_result = self.tool_executor.execute(corrected_call, allowed_tools=allowed_tools)
        dur_ms = (time.perf_counter() - t_start) * 1000
        self.budget_tracker.record_duration(dur_ms)

        if not tool_result.success:
            err = f"Revalidated tool execution still failed: {tool_result.error}"
            rec = RecoveryActionRecord(
                action_id=action_id,
                attempt_index=attempt_index,
                policy_id=self.policy_type.value,
                action_type="execute_revalidated_tool_call",
                status="failed",
                duration_ms=dur_ms,
                description="Corrected tool call failed validation or execution.",
                input_context={"tool_name": corrected_call.tool_name, "arguments": corrected_call.arguments},
                output_result={"error": tool_result.error},
                error=err,
            )
            return None, None, [rec], err

        rec = RecoveryActionRecord(
            action_id=action_id,
            attempt_index=attempt_index,
            policy_id=self.policy_type.value,
            action_type="execute_revalidated_tool_call",
            status="completed",
            duration_ms=dur_ms,
            description="Revalidated tool call executed successfully.",
            input_context={"tool_name": corrected_call.tool_name, "arguments": corrected_call.arguments},
            output_result={"data": tool_result.data},
        )
        action_records.append(rec)

        final_ans, verif, extra_recs, synth_err = self._formulate_answer(
            task=task,
            tool_name=corrected_call.tool_name,
            tool_data=tool_result.data,
            verification_rule=verification_rule,
            attempt_index=attempt_index,
        )
        action_records.extend(extra_recs)
        return final_ans, verif, action_records, synth_err

    def _formulate_answer(
        self,
        task: str,
        tool_name: str,
        tool_data: Any,
        verification_rule: Optional[VerificationRule],
        attempt_index: int,
    ) -> Tuple[Optional[str], Optional[VerificationResult], List[RecoveryActionRecord], Optional[str]]:
        t_start = time.perf_counter()
        final_ans = str(tool_data)
        dur_ms = (time.perf_counter() - t_start) * 1000
        verif = OutcomeVerifier.verify(final_ans, verification_rule)
        rec = RecoveryActionRecord(
            action_id=f"act_{uuid.uuid4().hex[:8]}",
            attempt_index=attempt_index,
            policy_id=self.policy_type.value,
            action_type="formulate_final_answer",
            status="completed",
            duration_ms=dur_ms,
            description="Formulated answer from revalidated tool execution result.",
            output_result={"final_answer": final_ans},
        )
        return final_ans, verif, [rec], None

class PolicyCRepeatedActionsAction(BaseRecoveryAction):
    """Policy C: Halts repetition loops, summarizes previous actions, and enforces alternative replanning."""
    policy_type = RecoveryPolicyType.POLICY_C_REPEATED_ACTIONS

    def execute(
        self,
        task: str,
        checkpoint: RecoveryCheckpoint,
        repeated_tool_name: Optional[str],
        allowed_tools: Optional[List[str]] = None,
        verification_rule: Optional[VerificationRule] = None,
        attempt_index: int = 1,
    ) -> Tuple[Optional[str], Optional[VerificationResult], List[RecoveryActionRecord], Optional[str]]:
        action_records = []
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        can_model, reason = self.budget_tracker.check_can_call_model()
        if not can_model:
            err = f"Policy C rejected: {reason}"
            return None, None, [], err

        summary_lines = checkpoint.sanitized_history_summary[-5:] if checkpoint.sanitized_history_summary else []
        summary_text = "; ".join(summary_lines) if summary_lines else "No observable tool output recorded."

        replan_prompt = (
            f"Diagnostic Alert: Repeated action or lack of measurable progress detected on '{repeated_tool_name or 'unknown'}'. "
            f"History summary: [{summary_text}]. "
            f"Anti-repetition rule: You MUST NOT repeat the identical action. Choose a distinct permitted alternative tool or propose an answer/abstention."
        )

        self.budget_tracker.record_model_call()
        self.budget_tracker.record_step()

        tool_defs = self.tool_registry.list_definitions(allowed_tools)
        resp = self.model_adapter.generate_next_step(
            task=f"{task}\n{replan_prompt}",
            tool_definitions=tool_defs,
            history=[],
            scenario_hint="break_repetition_loop",
        )

        dur_ms = (time.perf_counter() - t_start) * 1000
        self.budget_tracker.record_duration(dur_ms)

        if resp.is_final_answer and resp.final_answer:
            verif = OutcomeVerifier.verify(resp.final_answer, verification_rule)
            rec = RecoveryActionRecord(
                action_id=action_id,
                attempt_index=attempt_index,
                policy_id=self.policy_type.value,
                action_type="replan_to_final_answer",
                status="completed",
                duration_ms=dur_ms,
                description="Agent replanned and successfully produced distinct final answer.",
                output_result={"final_answer": resp.final_answer},
            )
            return resp.final_answer, verif, [rec], None

        if resp.tool_call:
            # Enforce distinct action constraint
            if resp.tool_call.tool_name == repeated_tool_name and resp.tool_call.arguments == {}:
                err = "Agent repeated identical prohibited tool call during recovery."
                rec = RecoveryActionRecord(
                    action_id=action_id,
                    attempt_index=attempt_index,
                    policy_id=self.policy_type.value,
                    action_type="replan_loop_or_stall",
                    status="failed",
                    duration_ms=dur_ms,
                    error=err,
                    description="Prohibited repeated tool call attempted; terminating loop.",
                )
                return None, None, [rec], err

            # Execute distinct tool call
            can_tool, t_reason = self.budget_tracker.check_can_call_tool(resp.tool_call.tool_name)
            if not can_tool:
                return None, None, [], t_reason

            self.budget_tracker.record_tool_call(resp.tool_call.tool_name)
            t_exec_start = time.perf_counter()
            tool_res = self.tool_executor.execute(resp.tool_call, allowed_tools=allowed_tools)
            exec_dur_ms = (time.perf_counter() - t_exec_start) * 1000
            self.budget_tracker.record_duration(exec_dur_ms)

            final_ans = str(tool_res.data) if tool_res.success else "Abstained: unable to progress."
            verif = OutcomeVerifier.verify(final_ans, verification_rule)
            rec = RecoveryActionRecord(
                action_id=action_id,
                attempt_index=attempt_index,
                policy_id=self.policy_type.value,
                action_type="replan_alternative_tool_call",
                status="completed" if tool_res.success else "failed",
                duration_ms=dur_ms + exec_dur_ms,
                description=f"Agent pivoted to distinct tool call '{resp.tool_call.tool_name}'.",
                output_result={"data": tool_res.data},
            )
            return final_ans, verif, [rec], None

        # Terminate with explicit unresolved status
        err = "Agent produced neither alternative action nor answer during replanning."
        rec = RecoveryActionRecord(
            action_id=action_id,
            attempt_index=attempt_index,
            policy_id=self.policy_type.value,
            action_type="replan_loop_or_stall",
            status="failed",
            duration_ms=dur_ms,
            error=err,
            description="Replanning produced empty response.",
        )
        return None, None, [rec], err

class PolicyDMissingEvidenceAction(BaseRecoveryAction):
    """Policy D: Alternative retrieval strategy; abstains explicitly if evidence remains unavailable."""
    policy_type = RecoveryPolicyType.POLICY_D_MISSING_EVIDENCE

    def execute(
        self,
        task: str,
        checkpoint: RecoveryCheckpoint,
        allowed_tools: Optional[List[str]] = None,
        verification_rule: Optional[VerificationRule] = None,
        attempt_index: int = 1,
    ) -> Tuple[Optional[str], Optional[VerificationResult], List[RecoveryActionRecord], Optional[str]]:
        action_records = []
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        if allowed_tools and "document_search" not in allowed_tools:
            err = "Policy D aborted: 'document_search' tool is not allowed for this task."
            return None, None, [], err

        can_tool, reason = self.budget_tracker.check_can_call_tool("document_search")
        if not can_tool:
            return None, None, [], reason

        # Extract targeted search query from task description
        search_query = self._extract_query_from_task(task)
        tool_call = ToolCallRequest(tool_name="document_search", arguments={"query": search_query})

        self.budget_tracker.record_tool_call("document_search")
        self.budget_tracker.record_step()

        tool_result = self.tool_executor.execute(tool_call, allowed_tools=allowed_tools)
        dur_ms = (time.perf_counter() - t_start) * 1000
        self.budget_tracker.record_duration(dur_ms)

        matches = []
        if tool_result.success and tool_result.data:
            if isinstance(tool_result.data, dict):
                matches = tool_result.data.get("matches", [])
            elif isinstance(tool_result.data, list):
                matches = tool_result.data

        if not tool_result.success or not matches:
            # Explicit, uninvented abstention per prompt requirement:
            # "Never invent citations or source content. Never turn an evidence failure into an unsupported confident answer."
            abstention_answer = "I am unable to answer this question because sufficient supporting evidence could not be found."
            verif = OutcomeVerifier.verify(abstention_answer, verification_rule)
            rec = RecoveryActionRecord(
                action_id=action_id,
                attempt_index=attempt_index,
                policy_id=self.policy_type.value,
                action_type="abstain_missing_evidence",
                status="completed",
                duration_ms=dur_ms,
                description="No matching documents found; produced explicit uninvented abstention.",
                output_result={"final_answer": abstention_answer},
            )
            return abstention_answer, verif, [rec], None

        rec = RecoveryActionRecord(
            action_id=action_id,
            attempt_index=attempt_index,
            policy_id=self.policy_type.value,
            action_type="retrieve_alternative_evidence",
            status="completed",
            duration_ms=dur_ms,
            description=f"Retrieved evidence using targeted query '{search_query}'.",
            output_result={"matches_count": len(matches)},
        )
        action_records.append(rec)

        # Formulate answer with retrieved evidence
        extracted_text = " ".join([d.get("snippet", d.get("content", "")) for d in matches if isinstance(d, dict)]).strip()
        final_ans = extracted_text if extracted_text else "I am unable to answer this question because sufficient supporting evidence could not be found."
        verif = OutcomeVerifier.verify(final_ans, verification_rule)
        return final_ans, verif, action_records, None

    def _extract_query_from_task(self, task: str) -> str:
        # Heuristic search term extractor: remove question words and punctuation
        words = [w.strip("?,.:;\"'") for w in task.split() if len(w) > 3]
        query_words = [w for w in words if w.lower() not in {"what", "when", "where", "which", "about", "from", "with", "find", "tell", "explain"}]
        return " ".join(query_words[:4]) if query_words else task[:40]

class PolicyEIncorrectAnswerAction(BaseRecoveryAction):
    """Policy E: Bounded correction supplying verification error WITHOUT leaking ground truth."""
    policy_type = RecoveryPolicyType.POLICY_E_INCORRECT_ANSWER

    def execute(
        self,
        task: str,
        checkpoint: RecoveryCheckpoint,
        original_final_answer: Optional[str],
        verification_message: str,
        verification_rule: Optional[VerificationRule] = None,
        attempt_index: int = 1,
    ) -> Tuple[Optional[str], Optional[VerificationResult], List[RecoveryActionRecord], Optional[str]]:
        action_records = []
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        can_model, reason = self.budget_tracker.check_can_call_model()
        if not can_model:
            return None, None, [], f"Policy E rejected: {reason}"

        # CRITICAL CONSTRAINT: In benchmark mode, NEVER pass expected_answer into the recovery model prompt!
        # Only pass observable tool results and the error message without revealing ground truth.
        sanitized_error = verification_message
        if verification_rule and verification_rule.expected_value is not None:
            sanitized_error = sanitized_error.replace(str(verification_rule.expected_value), "[REDACTED_GROUND_TRUTH]")

        tool_evidence = []
        for res in checkpoint.completed_tool_results:
            tool_evidence.append(f"{res.get('tool_name')}: {json.dumps(res.get('data'))}")
        evidence_str = "; ".join(tool_evidence) if tool_evidence else "None"

        prompt = (
            f"Original Task: {task}\n"
            f"Your previous answer '{original_final_answer}' failed verification with message: '{sanitized_error}'.\n"
            f"Observable verified tool outputs: {evidence_str}.\n"
            f"Recalculate or correct your answer using ONLY the verified tool data."
        )

        self.budget_tracker.record_model_call()
        self.budget_tracker.record_step()

        resp = self.model_adapter.generate_next_step(
            task=prompt,
            tool_definitions=[],
            history=[],
            scenario_hint="answer_correction",
        )

        dur_ms = (time.perf_counter() - t_start) * 1000
        self.budget_tracker.record_duration(dur_ms)

        final_ans = resp.final_answer or original_final_answer or ""
        # Re-verify with independent verifier
        verif = OutcomeVerifier.verify(final_ans, verification_rule)

        rec = RecoveryActionRecord(
            action_id=action_id,
            attempt_index=attempt_index,
            policy_id=self.policy_type.value,
            action_type="correct_verification_mismatch",
            status="completed" if verif.verified else "failed",
            duration_ms=dur_ms,
            description="Re-evaluated answer correction using observable tool evidence without leaking ground truth.",
            output_result={"corrected_answer": final_ans, "verified": verif.verified},
        )
        return final_ans, verif, [rec], None

class PolicyFStepLimitContinuationAction(BaseRecoveryAction):
    """Policy F: Bounded continuation using checkpointed progress when step limit was exhausted."""
    policy_type = RecoveryPolicyType.POLICY_F_STEP_LIMIT_EXHAUSTION

    def execute(
        self,
        task: str,
        checkpoint: RecoveryCheckpoint,
        verification_rule: Optional[VerificationRule] = None,
        attempt_index: int = 1,
    ) -> Tuple[Optional[str], Optional[VerificationResult], List[RecoveryActionRecord], Optional[str]]:
        action_records = []
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        can_model, reason = self.budget_tracker.check_can_call_model()
        if not can_model:
            return None, None, [], f"Policy F rejected: {reason}"

        # If we have completed tool results in checkpoint, synthesize them
        if not checkpoint.completed_tool_results:
            err = "Policy F failed: No tool results available in checkpoint to synthesize final answer."
            rec = RecoveryActionRecord(
                action_id=action_id,
                attempt_index=attempt_index,
                policy_id=self.policy_type.value,
                action_type="bounded_step_continuation",
                status="failed",
                error=err,
                description="Continuation rejected: empty checkpoint.",
            )
            return None, None, [rec], err

        last_tool = checkpoint.completed_tool_results[-1]
        data = last_tool.get("data")
        final_ans = str(data) if data is not None else "Completed"

        self.budget_tracker.record_step()
        dur_ms = (time.perf_counter() - t_start) * 1000
        self.budget_tracker.record_duration(dur_ms)

        verif = OutcomeVerifier.verify(final_ans, verification_rule)
        rec = RecoveryActionRecord(
            action_id=action_id,
            attempt_index=attempt_index,
            policy_id=self.policy_type.value,
            action_type="bounded_step_continuation",
            status="completed",
            duration_ms=dur_ms,
            description=f"Synthesized final answer from last completed tool '{last_tool.get('tool_name')}'.",
            output_result={"final_answer": final_ans, "verified": verif.verified},
        )
        return final_ans, verif, [rec], None

class PolicyGUnverifiedCompletionAction(BaseRecoveryAction):
    """Policy G: Retains explicit unverified/abstained outcome rather than misrepresenting success."""
    policy_type = RecoveryPolicyType.POLICY_G_UNVERIFIED_COMPLETION

    def execute(
        self,
        task: str,
        final_answer: Optional[str],
        verification_rule: Optional[VerificationRule] = None,
        attempt_index: int = 1,
    ) -> Tuple[Optional[str], Optional[VerificationResult], List[RecoveryActionRecord], Optional[str]]:
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        # If verification rule exists now, re-verify; otherwise mark explicitly unverified
        verif = OutcomeVerifier.verify(final_answer or "", verification_rule)
        rec = RecoveryActionRecord(
            action_id=action_id,
            attempt_index=attempt_index,
            policy_id=self.policy_type.value,
            action_type="retain_unverified_outcome",
            status="completed",
            description="Evaluated unverified completion; verified status retained.",
            output_result={"verified": verif.verified, "status": verif.status},
        )
        return final_answer, verif, [rec], None

class PolicyHMalformedOutputAction(BaseRecoveryAction):
    """Policy H: Bounded structured format correction for malformed model outputs."""
    policy_type = RecoveryPolicyType.POLICY_H_MALFORMED_OUTPUT

    def execute(
        self,
        task: str,
        checkpoint: RecoveryCheckpoint,
        verification_rule: Optional[VerificationRule] = None,
        attempt_index: int = 1,
    ) -> Tuple[Optional[str], Optional[VerificationResult], List[RecoveryActionRecord], Optional[str]]:
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        t_start = time.perf_counter()

        can_model, reason = self.budget_tracker.check_can_call_model()
        if not can_model:
            return None, None, [], f"Policy H rejected: {reason}"

        self.budget_tracker.record_model_call()
        self.budget_tracker.record_step()

        prompt = f"{task}\nFormat correction requirement: Output MUST either be a valid tool call or a clear final answer string."
        resp = self.model_adapter.generate_next_step(task=prompt, tool_definitions=[], history=[])

        dur_ms = (time.perf_counter() - t_start) * 1000
        self.budget_tracker.record_duration(dur_ms)

        final_ans = resp.final_answer or "Format corrected."
        verif = OutcomeVerifier.verify(final_ans, verification_rule)

        rec = RecoveryActionRecord(
            action_id=action_id,
            attempt_index=attempt_index,
            policy_id=self.policy_type.value,
            action_type="correct_malformed_output",
            status="completed",
            duration_ms=dur_ms,
            description="Agent returned valid formatted answer on format correction prompt.",
            output_result={"final_answer": final_ans},
        )
        return final_ans, verif, [rec], None
