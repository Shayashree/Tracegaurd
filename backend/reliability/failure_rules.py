"""Explainable rule definitions for trajectory-based failure detection."""
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from backend.reliability.detector_config import DetectorConfig
from backend.reliability.diagnostic_report import (
    ConfirmationStatus,
    DiagnosticFinding,
    FailureCategory,
    SeverityLevel,
    TrajectoryFeatures,
)

class BaseFailureRule(ABC):
    """Abstract base class for explainable failure detection rules."""
    rule_id: str
    failure_category: FailureCategory
    default_severity: SeverityLevel
    explanation_template: str

    @abstractmethod
    def evaluate(
        self,
        features: TrajectoryFeatures,
        events: List[Dict[str, Any]],
        config: DetectorConfig,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DiagnosticFinding]:
        """Evaluate rule against trajectory features and raw events."""
        pass

class RepeatedActionRule(BaseFailureRule):
    """R1: Trigger when an equivalent tool action is repeated at least threshold times."""
    rule_id = "R1_REPEATED_ACTION"
    failure_category = FailureCategory.REPEATED_TOOL_CALLS
    default_severity = SeverityLevel.HIGH
    explanation_template = "Detected {count} consecutive identical tool calls to '{tool_name}' without observable task progress."

    def evaluate(
        self,
        features: TrajectoryFeatures,
        events: List[Dict[str, Any]],
        config: DetectorConfig,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DiagnosticFinding]:
        threshold = config.repeated_call_threshold
        if features.max_consecutive_identical_tool_calls >= threshold:
            # Find evidence events
            evidence_ids = []
            tool_name = "unknown"
            for ev in events:
                if ev.get("event_type") == "tool_call_requested":
                    evidence_ids.append(f"step_{ev.get('step_index', 0)}")
                    tool_name = ev.get("tool_name", tool_name)

            return DiagnosticFinding(
                finding_id=f"fnd_{uuid.uuid4().hex[:8]}",
                rule_id=self.rule_id,
                failure_category=self.failure_category,
                severity=self.default_severity,
                confirmation_status=ConfirmationStatus.CONFIRMED,
                confidence=1.0,
                evidence_event_ids=evidence_ids[-threshold:],
                explanation=self.explanation_template.format(
                    count=features.max_consecutive_identical_tool_calls,
                    tool_name=tool_name
                ),
                recommended_next_action="Examine repetitive tool call loops, inject repetition constraints, or prompt agent to revise strategy."
            )
        return None

class PersistentToolFailureRule(BaseFailureRule):
    """R2: Trigger when a tool repeatedly fails or an unhandled tool exception occurs."""
    rule_id = "R2_PERSISTENT_TOOL_FAILURE"
    failure_category = FailureCategory.TOOL_EXECUTION_FAILURE
    default_severity = SeverityLevel.HIGH
    explanation_template = "Encountered {count} tool execution failure(s) during trajectory."

    def evaluate(
        self,
        features: TrajectoryFeatures,
        events: List[Dict[str, Any]],
        config: DetectorConfig,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DiagnosticFinding]:
        ctx = task_context or {}
        term_stat = ctx.get("terminal_status") or features.terminal_status
        has_failure = (
            features.persistent_tool_failures >= 1
            or features.tool_execution_failures >= 1
            or term_stat in ("tool_error", "timeout")
        )

        if has_failure:
            is_persistent = (
                features.persistent_tool_failures >= 1
                or features.tool_execution_failures >= config.persistent_tool_failure_threshold
            )
            sev = SeverityLevel.HIGH if (is_persistent or term_stat in ("tool_error", "timeout")) else SeverityLevel.MEDIUM
            msg = (
                "Persistent tool failure pattern detected ({count} failure(s))."
                if is_persistent
                else "Tool execution failure encountered during trajectory ({count} failure(s))."
            )

            evidence_ids = []
            for ev in events:
                if ev.get("event_type") == "tool_execution_failed":
                    evidence_ids.append(f"step_{ev.get('step_index', 0)}")

            return DiagnosticFinding(
                finding_id=f"fnd_{uuid.uuid4().hex[:8]}",
                rule_id=self.rule_id,
                failure_category=self.failure_category,
                severity=sev,
                confirmation_status=ConfirmationStatus.CONFIRMED,
                confidence=1.0,
                evidence_event_ids=evidence_ids or ["tool_failure_event"],
                explanation=msg.format(count=features.tool_execution_failures or 1),
                recommended_next_action="Check tool service health, examine parameter constraints, or substitute a fallback tool."
            )
        return None

class InvalidToolCallRule(BaseFailureRule):
    """R3: Trigger when tool call is rejected by schema validation or authorization."""
    rule_id = "R3_INVALID_TOOL_CALL"
    failure_category = FailureCategory.INVALID_TOOL_ARGUMENTS
    default_severity = SeverityLevel.HIGH
    explanation_template = "Tool invocation rejected due to schema validation or parameter error ({count} failure(s))."

    def evaluate(
        self,
        features: TrajectoryFeatures,
        events: List[Dict[str, Any]],
        config: DetectorConfig,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DiagnosticFinding]:
        if features.validation_failures > 0:
            evidence_ids = []
            for ev in events:
                if ev.get("event_type") == "tool_execution_failed":
                    err_msg = (ev.get("output_summary") or "").lower()
                    err_type = (ev.get("error_type") or "").lower()
                    if "validation" in err_type or "invalid arguments" in err_msg or "schema" in err_msg:
                        evidence_ids.append(f"step_{ev.get('step_index', 0)}")

            return DiagnosticFinding(
                finding_id=f"fnd_{uuid.uuid4().hex[:8]}",
                rule_id=self.rule_id,
                failure_category=self.failure_category,
                severity=self.default_severity,
                confirmation_status=ConfirmationStatus.CONFIRMED,
                confidence=1.0,
                evidence_event_ids=evidence_ids or ["validation_event"],
                explanation=self.explanation_template.format(count=features.validation_failures),
                recommended_next_action="Inspect tool argument schema and provide explicit type constraints in model system prompt."
            )
        return None

class LackOfProgressRule(BaseFailureRule):
    """R4: Trigger when trajectory continues with empty/stale observations and no measurable progress."""
    rule_id = "R4_LACK_OF_PROGRESS"
    failure_category = FailureCategory.LACK_OF_PROGRESS
    default_severity = SeverityLevel.MEDIUM
    explanation_template = "Agent executed {steps} steps without measurable task progress or new evidence."

    def evaluate(
        self,
        features: TrajectoryFeatures,
        events: List[Dict[str, Any]],
        config: DetectorConfig,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DiagnosticFinding]:
        if (
            features.observable_progress_stalled
            and not features.final_answer_produced
            and features.total_steps >= config.min_steps_for_progress_eval
        ):
            return DiagnosticFinding(
                finding_id=f"fnd_{uuid.uuid4().hex[:8]}",
                rule_id=self.rule_id,
                failure_category=self.failure_category,
                severity=self.default_severity,
                confirmation_status=ConfirmationStatus.SUSPECTED,
                confidence=0.85,
                evidence_event_ids=[f"step_{features.total_steps - 1}"],
                explanation=self.explanation_template.format(steps=features.total_steps),
                recommended_next_action="Analyze search query formulation or broaden lookup criteria to locate relevant items."
            )
        return None

class UnsupportedFinalAnswerRule(BaseFailureRule):
    """R5: Trigger when task with defined evidence requirement produces final answer without evidence."""
    rule_id = "R5_UNSUPPORTED_FINAL_ANSWER"
    failure_category = FailureCategory.MISSING_EVIDENCE
    default_severity = SeverityLevel.HIGH
    explanation_template = "Final answer proposed without satisfying task evidence retrieval requirement."

    def evaluate(
        self,
        features: TrajectoryFeatures,
        events: List[Dict[str, Any]],
        config: DetectorConfig,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DiagnosticFinding]:
        ctx = task_context or {}
        req_rule = ctx.get("verification_rule") or {}
        is_evidence_rule = (
            isinstance(req_rule, dict)
            and req_rule.get("type") in ("evidence_reference", "field_presence")
            and any(k in str(ctx.get("task_description", "")).lower() for k in ["according to", "document", "policy", "evidence", "search"])
        )

        # Trigger if evidence was required but either no evidence retrieval occurred or verification failed evidence check
        if features.final_answer_produced and is_evidence_rule:
            if features.evidence_policy_satisfied is False or (not features.evidence_retrieval_occurred and features.verification_status == "failed"):
                return DiagnosticFinding(
                    finding_id=f"fnd_{uuid.uuid4().hex[:8]}",
                    rule_id=self.rule_id,
                    failure_category=self.failure_category,
                    severity=self.default_severity,
                    confirmation_status=ConfirmationStatus.CONFIRMED if features.verification_status == "failed" else ConfirmationStatus.SUSPECTED,
                    confidence=0.95,
                    evidence_event_ids=["final_answer_event"],
                    explanation=self.explanation_template,
                    recommended_next_action="Ensure document search retrieves relevant reference passages before finalizing answer."
                )
        return None

class IncorrectVerifiedOutputRule(BaseFailureRule):
    """R6: Trigger when deterministic verifier explicitly reports mismatch."""
    rule_id = "R6_INCORRECT_VERIFIED_OUTPUT"
    failure_category = FailureCategory.INCORRECT_FINAL_ANSWER
    default_severity = SeverityLevel.CRITICAL
    explanation_template = "Outcome verification failed: observed output contradicts expected ground truth."

    def evaluate(
        self,
        features: TrajectoryFeatures,
        events: List[Dict[str, Any]],
        config: DetectorConfig,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DiagnosticFinding]:
        # Only triggers when deterministic verification status is explicitly 'failed'
        if features.verification_status == "failed":
            # Check if verifier message is available in verification_completed event
            verif_msg = None
            for ev in events:
                if ev.get("event_type") == "verification_completed":
                    verif_msg = ev.get("output_summary")

            expl = self.explanation_template
            if verif_msg:
                expl = f"Outcome verification failed: {verif_msg}"

            return DiagnosticFinding(
                finding_id=f"fnd_{uuid.uuid4().hex[:8]}",
                rule_id=self.rule_id,
                failure_category=self.failure_category,
                severity=self.default_severity,
                confirmation_status=ConfirmationStatus.CONFIRMED,
                confidence=1.0,
                evidence_event_ids=["verification_completed"],
                explanation=expl,
                recommended_next_action="Review intermediate calculation steps and verify grounding in retrieved factual data."
            )
        return None

class StepLimitExhaustionRule(BaseFailureRule):
    """R7: Trigger when execution terminates because maximum step count is reached."""
    rule_id = "R7_STEP_LIMIT_EXHAUSTION"
    failure_category = FailureCategory.STEP_LIMIT_EXHAUSTION
    default_severity = SeverityLevel.HIGH
    explanation_template = "Task reached maximum step ceiling ({steps}) without achieving completed status."

    def evaluate(
        self,
        features: TrajectoryFeatures,
        events: List[Dict[str, Any]],
        config: DetectorConfig,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DiagnosticFinding]:
        if features.step_limit_reached or features.terminal_status == "step_limit_reached":
            return DiagnosticFinding(
                finding_id=f"fnd_{uuid.uuid4().hex[:8]}",
                rule_id=self.rule_id,
                failure_category=self.failure_category,
                severity=self.default_severity,
                confirmation_status=ConfirmationStatus.CONFIRMED,
                confidence=1.0,
                evidence_event_ids=["step_limit_reached"],
                explanation=self.explanation_template.format(steps=features.total_steps),
                recommended_next_action="Increase maximum execution steps ceiling or compress multi-step planning into fewer tool hops."
            )
        return None

class IncompleteModelOutputRule(BaseFailureRule):
    """R8: Trigger when model adapter records response validation error or malformed response."""
    rule_id = "R8_INCOMPLETE_MODEL_OUTPUT"
    failure_category = FailureCategory.INVALID_MODEL_OUTPUT
    default_severity = SeverityLevel.HIGH
    explanation_template = "Model output was malformed, incomplete, or rejected by schema validation."

    def evaluate(
        self,
        features: TrajectoryFeatures,
        events: List[Dict[str, Any]],
        config: DetectorConfig,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DiagnosticFinding]:
        for ev in events:
            if ev.get("event_type") == "task_failed":
                err_type = (ev.get("error_type") or "").lower()
                err_msg = (ev.get("output_summary") or "").lower()
                if "model" in err_type or "malformed" in err_msg or "neither a tool call nor a final answer" in err_msg:
                    return DiagnosticFinding(
                        finding_id=f"fnd_{uuid.uuid4().hex[:8]}",
                        rule_id=self.rule_id,
                        failure_category=self.failure_category,
                        severity=self.default_severity,
                        confirmation_status=ConfirmationStatus.CONFIRMED,
                        confidence=1.0,
                        evidence_event_ids=[f"step_{ev.get('step_index', 0)}"],
                        explanation=self.explanation_template,
                        recommended_next_action="Validate model output parser and enforce structured output schema."
                    )
        return None

class UnverifiedCompletionRule(BaseFailureRule):
    """R9: Trigger when agent completes with final answer but verifier cannot establish correctness."""
    rule_id = "R9_UNVERIFIED_COMPLETION"
    failure_category = FailureCategory.UNVERIFIED_COMPLETION
    default_severity = SeverityLevel.LOW
    explanation_template = "Task completed with final answer, but no ground-truth rule was available to establish correctness."

    def evaluate(
        self,
        features: TrajectoryFeatures,
        events: List[Dict[str, Any]],
        config: DetectorConfig,
        task_context: Optional[Dict[str, Any]] = None
    ) -> Optional[DiagnosticFinding]:
        # Only triggers when task completed successfully, but verification_status is not_applicable/unverified/None
        if (
            features.final_answer_produced
            and features.terminal_status in ("completed", "successful_completion")
            and features.verification_status in ("not_applicable", "unverified", None)
            and not features.tool_execution_failures
            and not features.step_limit_reached
        ):
            # Check if there is an explicit verification rule in task_context
            ctx = task_context or {}
            rule = ctx.get("verification_rule")
            if not rule:
                return DiagnosticFinding(
                    finding_id=f"fnd_{uuid.uuid4().hex[:8]}",
                    rule_id=self.rule_id,
                    failure_category=self.failure_category,
                    severity=self.default_severity,
                    confirmation_status=ConfirmationStatus.UNVERIFIED,
                    confidence=None,
                    evidence_event_ids=["final_answer_event"],
                    explanation=self.explanation_template,
                    recommended_next_action="Define explicit deterministic verification rule (numerical tolerance or field presence) for ground truth verification."
                )
        return None

DEFAULT_FAILURE_RULES: List[BaseFailureRule] = [
    RepeatedActionRule(),
    PersistentToolFailureRule(),
    InvalidToolCallRule(),
    LackOfProgressRule(),
    UnsupportedFinalAnswerRule(),
    IncorrectVerifiedOutputRule(),
    StepLimitExhaustionRule(),
    IncompleteModelOutputRule(),
    UnverifiedCompletionRule(),
]
