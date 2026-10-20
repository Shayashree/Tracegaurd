"""Deterministic policy selection interface mapping diagnostic findings to recovery actions."""
import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.reliability.diagnostic_report import (
    ConfirmationStatus,
    DiagnosticFinding,
    DiagnosticReport,
    FailureCategory,
)
from backend.reliability.recovery_budget import RecoveryBudgetTracker
from backend.reliability.recovery_report import RecoveryPolicyType

logger = logging.getLogger(__name__)

class PolicyDecision(BaseModel):
    """Structured decision produced by the rule-based policy selector."""
    policy_id: RecoveryPolicyType
    action_type: str
    reason: str
    finding_ids: List[str] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    expected_outcome: str
    can_execute: bool
    budget_required: Dict[str, int] = Field(default_factory=dict)
    initial_failure_category: Optional[str] = None

class PolicySelector:
    """Deterministic, explainable rule-based recovery policy selector."""

    # Priority ranking of failure categories when multiple findings exist
    CATEGORY_PRIORITY: List[FailureCategory] = [
        FailureCategory.INVALID_TOOL_ARGUMENTS,   # Policy B: Immediate schema blocker
        FailureCategory.TOOL_EXECUTION_FAILURE,   # Policy A: Tool error
        FailureCategory.REPEATED_TOOL_CALLS,      # Policy C: Repetition loop
        FailureCategory.LACK_OF_PROGRESS,         # Policy C: Progress stall
        FailureCategory.MISSING_EVIDENCE,         # Policy D: Inadequate evidence
        FailureCategory.STEP_LIMIT_EXHAUSTION,    # Policy F: Step ceiling
        FailureCategory.INCORRECT_FINAL_ANSWER,   # Policy E: Verification mismatch
        FailureCategory.INVALID_MODEL_OUTPUT,     # Policy H: Malformed output
        FailureCategory.UNVERIFIED_COMPLETION,    # Policy G: Unverified completion
    ]

    @classmethod
    def select_policy(
        cls,
        diagnostic_report: DiagnosticReport,
        budget_tracker: RecoveryBudgetTracker,
        task_context: Optional[Dict[str, Any]] = None,
        trace_events: Optional[List[Dict[str, Any]]] = None,
    ) -> PolicyDecision:
        """Evaluate diagnostic findings and budget to choose the best recovery policy."""
        # 1. Budget check
        can_attempt, budget_reason = budget_tracker.check_can_attempt()
        if not can_attempt:
            return PolicyDecision(
                policy_id=RecoveryPolicyType.POLICY_NONE,
                action_type="stop_budget_exhausted",
                reason=f"Recovery rejected: budget exhausted ({budget_reason})",
                can_execute=False,
                expected_outcome="Task preserved in original state due to exhausted recovery budget.",
                budget_required={"attempts": 1, "steps": 1},
            )

        # 2. Extract findings
        findings: List[DiagnosticFinding] = diagnostic_report.findings
        if not findings:
            return PolicyDecision(
                policy_id=RecoveryPolicyType.POLICY_NONE,
                action_type="stop_healthy_or_no_findings",
                reason="No actionable diagnostic findings reported by detector.",
                can_execute=False,
                expected_outcome="No intervention warranted; preserving original execution result.",
                budget_required={},
            )

        # 3. Sort findings: confirmed first, then by priority hierarchy
        sorted_findings = sorted(
            findings,
            key=lambda f: (
                0 if f.confirmation_status == ConfirmationStatus.CONFIRMED else 1,
                cls.CATEGORY_PRIORITY.index(f.failure_category) if f.failure_category in cls.CATEGORY_PRIORITY else 999
            )
        )

        chosen_finding = sorted_findings[0]
        cat = chosen_finding.failure_category
        f_ids = [chosen_finding.finding_id]

        allowed_tools = (task_context or {}).get("allowed_tools") or []

        # 4. Map to Policy A-H
        if cat == FailureCategory.TOOL_EXECUTION_FAILURE:
            # Check if transient or benchmark transient scenario
            is_transient = True  # By default tool execution error can attempt bounded retry
            # If tool name is known, check tool retry budget
            tool_name = "unknown"
            if trace_events:
                for ev in reversed(trace_events):
                    if ev.get("tool_name"):
                        tool_name = ev.get("tool_name")
                        break
            can_tool, tool_reason = budget_tracker.check_can_call_tool(tool_name, is_retry=True)
            if not can_tool:
                return PolicyDecision(
                    policy_id=RecoveryPolicyType.POLICY_NONE,
                    action_type="stop_tool_retry_exhausted",
                    reason=f"Policy A rejected: {tool_reason}",
                    finding_ids=f_ids,
                    can_execute=False,
                    expected_outcome="Transient retry limit exhausted for tool.",
                    initial_failure_category=cat.value,
                )

            return PolicyDecision(
                policy_id=RecoveryPolicyType.POLICY_A_TRANSIENT_TOOL_FAILURE,
                action_type="retry_transient_tool_call",
                reason=f"Confirmed tool execution failure detected on '{tool_name}'. Applying bounded retry.",
                finding_ids=f_ids,
                preconditions=["Valid tool name", "Tool is idempotent or benchmark transient mock"],
                expected_outcome="Tool succeeds on retry or fails safely within budget.",
                can_execute=True,
                budget_required={"attempts": 1, "steps": 1, "tool_calls": 1},
                initial_failure_category=cat.value,
            )

        elif cat == FailureCategory.INVALID_TOOL_ARGUMENTS:
            return PolicyDecision(
                policy_id=RecoveryPolicyType.POLICY_B_INVALID_TOOL_ARGUMENTS,
                action_type="correct_tool_arguments",
                reason="Invalid tool arguments detected by schema validator. Prompting agent for corrected arguments.",
                finding_ids=f_ids,
                preconditions=["Documented tool schema available", "Argument revalidation enforced"],
                expected_outcome="Agent supplies schema-conforming arguments, which are strictly re-validated.",
                can_execute=True,
                budget_required={"attempts": 1, "steps": 1, "model_calls": 1, "tool_calls": 1},
                initial_failure_category=cat.value,
            )

        elif cat in (FailureCategory.REPEATED_TOOL_CALLS, FailureCategory.LACK_OF_PROGRESS):
            return PolicyDecision(
                policy_id=RecoveryPolicyType.POLICY_C_REPEATED_ACTIONS,
                action_type="replan_loop_or_stall",
                reason=f"Action repetition / stalled progress detected ({cat.value}). Providing action summary and enforcing alternative step.",
                finding_ids=f_ids,
                preconditions=["Observable trace summary provided", "Strict anti-repetition constraint"],
                expected_outcome="Agent executes a distinct alternative tool call or returns a verified abstention.",
                can_execute=True,
                budget_required={"attempts": 1, "steps": 2, "model_calls": 1, "tool_calls": 1},
                initial_failure_category=cat.value,
            )

        elif cat == FailureCategory.MISSING_EVIDENCE:
            if "document_search" not in allowed_tools and allowed_tools:
                return PolicyDecision(
                    policy_id=RecoveryPolicyType.POLICY_NONE,
                    action_type="stop_disallowed_tool",
                    reason="Policy D requires 'document_search' but tool is not in allowed_tools.",
                    finding_ids=f_ids,
                    can_execute=False,
                    expected_outcome="Cannot retrieve evidence without permitted document search tool.",
                    initial_failure_category=cat.value,
                )

            return PolicyDecision(
                policy_id=RecoveryPolicyType.POLICY_D_MISSING_EVIDENCE,
                action_type="retrieve_alternative_evidence",
                reason="Missing evidence required by task. Executing targeted alternative document query.",
                finding_ids=f_ids,
                preconditions=["Allowed document_search tool", "Task search keywords extracted"],
                expected_outcome="Evidence retrieved and verified, or explicit abstention returned if not found.",
                can_execute=True,
                budget_required={"attempts": 1, "steps": 2, "tool_calls": 1, "model_calls": 1},
                initial_failure_category=cat.value,
            )

        elif cat == FailureCategory.STEP_LIMIT_EXHAUSTION:
            return PolicyDecision(
                policy_id=RecoveryPolicyType.POLICY_F_STEP_LIMIT_EXHAUSTION,
                action_type="bounded_step_continuation",
                reason="Step limit reached without final answer. Allowing bounded continuation with existing progress.",
                finding_ids=f_ids,
                preconditions=["Remaining recovery step budget > 0", "Non-empty tool result history"],
                expected_outcome="Agent synthesizes gathered tool outputs into a final verified answer.",
                can_execute=True,
                budget_required={"attempts": 1, "steps": 2, "model_calls": 1},
                initial_failure_category=cat.value,
            )

        elif cat == FailureCategory.INCORRECT_FINAL_ANSWER:
            return PolicyDecision(
                policy_id=RecoveryPolicyType.POLICY_E_INCORRECT_ANSWER,
                action_type="correct_verification_mismatch",
                reason="Outcome verifier reported mismatch. Prompting agent with observable tool results and error info.",
                finding_ids=f_ids,
                preconditions=["Ground-truth answer NOT exposed to agent", "Independent verifier re-run on completion"],
                expected_outcome="Agent recalculates/corrects answer using observable tool data.",
                can_execute=True,
                budget_required={"attempts": 1, "steps": 1, "model_calls": 1},
                initial_failure_category=cat.value,
            )

        elif cat == FailureCategory.INVALID_MODEL_OUTPUT:
            return PolicyDecision(
                policy_id=RecoveryPolicyType.POLICY_H_MALFORMED_OUTPUT,
                action_type="correct_malformed_output",
                reason="Model output was malformed or unsupported. Requesting format correction.",
                finding_ids=f_ids,
                preconditions=["Valid JSON / tool call format requested"],
                expected_outcome="Agent returns valid structured output.",
                can_execute=True,
                budget_required={"attempts": 1, "steps": 1, "model_calls": 1},
                initial_failure_category=cat.value,
            )

        elif cat == FailureCategory.UNVERIFIED_COMPLETION:
            return PolicyDecision(
                policy_id=RecoveryPolicyType.POLICY_G_UNVERIFIED_COMPLETION,
                action_type="verify_completion_or_abstain",
                reason="Agent returned answer but verification rule could not establish correctness.",
                finding_ids=f_ids,
                preconditions=["Independent verification rule checked"],
                expected_outcome="Attempt secondary verification or retain unverified/abstained outcome.",
                can_execute=True,
                budget_required={"attempts": 1, "steps": 1},
                initial_failure_category=cat.value,
            )

        # Fallback
        return PolicyDecision(
            policy_id=RecoveryPolicyType.POLICY_NONE,
            action_type="stop_unsupported_category",
            reason=f"No supported recovery policy for failure category '{cat.value}'.",
            finding_ids=f_ids,
            can_execute=False,
            expected_outcome="Preserve task status without intervention.",
            initial_failure_category=cat.value,
        )
