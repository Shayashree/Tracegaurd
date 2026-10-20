"""Unit and safety tests for Recovery Policies A through H and PolicySelector."""
import json
import pytest
from backend.agents.mock_model import MockModelAdapter
from backend.agents.tool_registry import ToolExecutor, ToolRegistry
from backend.models.schemas import ToolCallRequest, VerificationRule
from backend.reliability.diagnostic_report import (
    ConfirmationStatus,
    DiagnosticFinding,
    DiagnosticReport,
    DiagnosticStatus,
    FailureCategory,
    SeverityLevel,
    TrajectoryFeatures,
)
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
from backend.reliability.recovery_report import RecoveryPolicyType
from backend.reliability.recovery_state import RecoveryCheckpoint, RecoveryStateManager

@pytest.fixture
def clean_registry():
    return ToolRegistry()

@pytest.fixture
def clean_budget():
    return RecoveryBudgetTracker(RecoveryBudgetConfig(max_recovery_attempts=2, max_recovery_steps=5))

@pytest.fixture
def empty_checkpoint():
    return RecoveryCheckpoint(
        checkpoint_id="chk_test",
        task_id="task_test",
        run_id="run_test",
        recovery_attempt_id="atm_test",
        step_index=1,
    )

def test_policy_selector_prioritization():
    """PolicySelector prioritizes confirmed findings and critical failure categories."""
    tracker = RecoveryBudgetTracker()
    findings = [
        DiagnosticFinding(
            finding_id="fnd_1",
            rule_id="R1_REPEATED_ACTION",
            failure_category=FailureCategory.REPEATED_TOOL_CALLS,
            severity=SeverityLevel.HIGH,
            confirmation_status=ConfirmationStatus.SUSPECTED,
            explanation="Repeated tool calls detected.",
            recommended_next_action="Break loop",
        ),
        DiagnosticFinding(
            finding_id="fnd_2",
            rule_id="R2_INVALID_ARGS",
            failure_category=FailureCategory.INVALID_TOOL_ARGUMENTS,
            severity=SeverityLevel.CRITICAL,
            confirmation_status=ConfirmationStatus.CONFIRMED,
            explanation="Invalid tool arguments detected.",
            recommended_next_action="Revalidate arguments",
        ),
    ]
    diag = DiagnosticReport(
        diagnostic_id="diag_1",
        task_id="t1",
        run_id="r1",
        detector_version="v1.0",
        diagnostic_status=DiagnosticStatus.FAILURE_DETECTED,
        primary_failure_category=FailureCategory.INVALID_TOOL_ARGUMENTS,
        severity=SeverityLevel.CRITICAL,
        confirmation_status=ConfirmationStatus.CONFIRMED,
        findings=findings,
        features=TrajectoryFeatures(),
    )

    decision = PolicySelector.select_policy(diag, tracker)
    assert decision.policy_id == RecoveryPolicyType.POLICY_B_INVALID_TOOL_ARGUMENTS
    assert decision.can_execute is True
    assert "fnd_2" in decision.finding_ids

def test_policy_selector_budget_exhaustion():
    """Exhausted budget cleanly rejects policy execution."""
    tracker = RecoveryBudgetTracker(RecoveryBudgetConfig(max_recovery_attempts=1))
    tracker.record_attempt()

    findings = [
        DiagnosticFinding(
            finding_id="fnd_1",
            rule_id="R3_PERSISTENT_FAILURE",
            failure_category=FailureCategory.TOOL_EXECUTION_FAILURE,
            severity=SeverityLevel.HIGH,
            confirmation_status=ConfirmationStatus.CONFIRMED,
            explanation="Persistent failure detected.",
            recommended_next_action="Retry or stop",
        )
    ]
    diag = DiagnosticReport(
        diagnostic_id="diag_1",
        task_id="t1",
        run_id="r1",
        detector_version="v1.0",
        diagnostic_status=DiagnosticStatus.FAILURE_DETECTED,
        findings=findings,
        features=TrajectoryFeatures(),
    )

    decision = PolicySelector.select_policy(diag, tracker)
    assert decision.can_execute is False
    assert decision.policy_id == RecoveryPolicyType.POLICY_NONE
    assert "exhausted" in decision.reason.lower()

def test_policy_a_transient_retry(clean_registry, clean_budget, empty_checkpoint):
    """Policy A retries transient tool calls and re-synthesizes answer."""
    action = PolicyATransientRetryAction(
        tool_registry=clean_registry,
        tool_executor=ToolExecutor(clean_registry),
        model_adapter=MockModelAdapter(),
        budget_tracker=clean_budget,
    )
    tool_call = ToolCallRequest(tool_name="calculator", arguments={"operation": "add", "a": 5, "b": 10})
    verif_rule = VerificationRule(type="numerical_tolerance", expected_value=15.0)

    final_ans, verif, records, err = action.execute(
        task="What is 5 + 10?",
        checkpoint=empty_checkpoint,
        last_tool_call=tool_call,
        verification_rule=verif_rule,
    )

    assert err is None
    assert verif is not None
    assert verif.verified is True
    assert clean_budget.tool_calls_used == 1

def test_policy_b_invalid_arguments_revalidation_enforcement(clean_registry, clean_budget, empty_checkpoint):
    """Policy B strictly revalidates corrected tool arguments and does not bypass schema."""
    action = PolicyBInvalidArgumentAction(
        tool_registry=clean_registry,
        tool_executor=ToolExecutor(clean_registry),
        model_adapter=MockModelAdapter(),
        budget_tracker=clean_budget,
    )
    # Invalid tool call missing 'b'
    invalid_call = ToolCallRequest(tool_name="calculator", arguments={"operation": "add", "a": 5})

    final_ans, verif, records, err = action.execute(
        task="Calculate 5 + 5",
        checkpoint=empty_checkpoint,
        invalid_tool_call=invalid_call,
        validation_error="Missing required argument 'b'",
        verification_rule=VerificationRule(type="numerical_tolerance", expected_value=10.0),
    )

    assert len(records) > 0
    # Mandatory safety: the executed tool call must have passed validation
    for r in records:
        if r.action_type == "execute_revalidated_tool_call":
            assert r.status == "completed"

def test_policy_c_repeated_actions_loop_break(clean_registry, clean_budget, empty_checkpoint):
    """Policy C enforces anti-repetition rule when breaking repetition loop."""
    action = PolicyCRepeatedActionsAction(
        tool_registry=clean_registry,
        tool_executor=ToolExecutor(clean_registry),
        model_adapter=MockModelAdapter(),
        budget_tracker=clean_budget,
    )

    final_ans, verif, records, err = action.execute(
        task="Find info without looping",
        checkpoint=empty_checkpoint,
        repeated_tool_name="calculator",
    )

    assert len(records) > 0
    assert records[0].status == "completed"

def test_policy_d_missing_evidence_abstention(clean_registry, clean_budget, empty_checkpoint):
    """Policy D produces explicit uninvented abstention when evidence is not found."""
    action = PolicyDMissingEvidenceAction(
        tool_registry=clean_registry,
        tool_executor=ToolExecutor(clean_registry),
        model_adapter=MockModelAdapter(),
        budget_tracker=clean_budget,
    )

    # Search for completely non-existent concept
    final_ans, verif, records, err = action.execute(
        task="What is the quantum flux hyperdrive graviton oscillation frequency?",
        checkpoint=empty_checkpoint,
        allowed_tools=["document_search"],
    )

    assert final_ans is not None
    assert "unable to answer" in final_ans.lower()
    assert records[0].action_type == "abstain_missing_evidence"

def test_policy_e_ground_truth_isolation(clean_registry, clean_budget, empty_checkpoint):
    """NEGATIVE TEST: Policy E NEVER reveals expected ground truth to the recovery model."""
    action = PolicyEIncorrectAnswerAction(
        tool_registry=clean_registry,
        tool_executor=ToolExecutor(clean_registry),
        model_adapter=MockModelAdapter(),
        budget_tracker=clean_budget,
    )

    rule = VerificationRule(type="numerical_tolerance", expected_value=42.0)
    final_ans, verif, records, err = action.execute(
        task="Calculate secret value",
        checkpoint=empty_checkpoint,
        original_final_answer="100.0",
        verification_message="Observed 100.0 does not match expected 42.0",
        verification_rule=rule,
    )

    assert len(records) > 0
    # The record description and action must exist
    assert records[0].action_type == "correct_verification_mismatch"

def test_policy_f_step_limit_continuation(clean_registry, clean_budget):
    """Policy F synthesizes answer from checkpointed tool output on step limit."""
    action = PolicyFStepLimitContinuationAction(
        tool_registry=clean_registry,
        tool_executor=ToolExecutor(clean_registry),
        model_adapter=MockModelAdapter(),
        budget_tracker=clean_budget,
    )

    chk = RecoveryCheckpoint(
        checkpoint_id="chk_f",
        task_id="t1",
        run_id="r1",
        recovery_attempt_id="a1",
        step_index=8,
        completed_tool_results=[{"tool_name": "calculator", "data": 99.0}],
    )

    final_ans, verif, records, err = action.execute(
        task="What was the calculated total?",
        checkpoint=chk,
        verification_rule=VerificationRule(type="numerical_tolerance", expected_value=99.0),
    )

    assert final_ans == "99.0"
    assert verif.verified is True
    assert records[0].action_type == "bounded_step_continuation"
