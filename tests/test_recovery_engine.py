"""Integration tests for RecoveryEngine, FixedRetryEngine, and trace persistence."""
import pytest
from backend.agents.controller import AgentController
from backend.agents.mock_model import MockModelAdapter
from backend.agents.tool_registry import ToolRegistry
from backend.models.schemas import TaskCreateRequest, VerificationRule
from backend.reliability.diagnostic_report import (
    ConfirmationStatus,
    DiagnosticFinding,
    DiagnosticReport,
    DiagnosticStatus,
    FailureCategory,
    SeverityLevel,
    TrajectoryFeatures,
)
from backend.reliability.failure_detector import TrajectoryFailureDetector
from backend.reliability.recovery_budget import RecoveryBudgetConfig
from backend.reliability.recovery_engine import FixedRetryEngine, RecoveryEngine
from backend.reliability.recovery_report import RecoveryTerminalStatus
from backend.reliability.recovery_state import RecoveryStateManager
from backend.tracing.storage import TraceStorage

@pytest.fixture
def temp_storage(tmp_path):
    db_file = tmp_path / "test_recovery_engine.db"
    return TraceStorage(db_path=str(db_file))

def test_full_recovery_workflow_transient_failure(temp_storage):
    """End-to-end test: initial failure -> diagnosis -> policy selection -> recovery -> verified success."""
    registry = ToolRegistry()
    controller = AgentController(tool_registry=registry, storage=temp_storage)

    # 1. Execute task
    req = TaskCreateRequest(
        task="Calculate 25 * 4",
        allowed_tools=["calculator"],
        verification_rule=VerificationRule(type="numerical_tolerance", expected_value=100.0),
    )
    task_res = controller.run_task(req)
    trace_events = temp_storage.get_events(task_res.task_id)

    # 2. Simulate detector identifying tool failure finding
    diag_report = DiagnosticReport(
        diagnostic_id=f"diag_{task_res.task_id}",
        task_id=task_res.task_id,
        run_id=task_res.run_id,
        detector_version="v1.0",
        diagnostic_status=DiagnosticStatus.FAILURE_DETECTED,
        primary_failure_category=FailureCategory.TOOL_EXECUTION_FAILURE,
        severity=SeverityLevel.HIGH,
        confirmation_status=ConfirmationStatus.CONFIRMED,
        findings=[
            DiagnosticFinding(
                finding_id="fnd_transient",
                rule_id="R3_PERSISTENT_FAILURE",
                failure_category=FailureCategory.TOOL_EXECUTION_FAILURE,
                severity=SeverityLevel.HIGH,
                confirmation_status=ConfirmationStatus.CONFIRMED,
                explanation="Transient failure detected on calculator.",
                recommended_next_action="Retry operation",
            )
        ],
        features=TrajectoryFeatures(),
    )
    temp_storage.save_diagnostic_report(diag_report)

    # 3. Recovery Engine
    engine = RecoveryEngine(tool_registry=registry, storage=temp_storage)
    task_ctx = {
        "task_description": task_res.task,
        "max_steps": task_res.steps_count,
        "allowed_tools": ["calculator"],
        "verification_rule": req.verification_rule.model_dump(),
    }
    rec_report = engine.recover(
        task_response=task_res,
        task_context=task_ctx,
        initial_trace_events=trace_events,
        diag_report=diag_report,
    )

    # 4. Assertions
    assert rec_report.recovery_attempted is True
    assert rec_report.policy_id == "policy_a_transient_tool_failure"
    assert rec_report.terminal_status == RecoveryTerminalStatus.RECOVERED_SUCCESSFULLY
    assert rec_report.final_answer is not None
    assert rec_report.final_verification_status == "verified"

    # Verify trace events were persisted
    all_events = temp_storage.get_events(task_res.task_id)
    recovery_events = [e for e in all_events if e.recovery_attempt_id is not None]
    assert len(recovery_events) > 0
    event_types = {e.event_type for e in recovery_events}
    assert "recovery_started" in event_types
    assert "recovery_policy_selected" in event_types
    assert "task_recovered" in event_types

def test_fixed_retry_engine_behavior(temp_storage):
    """FixedRetryEngine retries tool failure without replanning or diagnosis."""
    registry = ToolRegistry()
    controller = AgentController(tool_registry=registry, storage=temp_storage)

    req = TaskCreateRequest(
        task="Calculate 10 / 2",
        allowed_tools=["calculator"],
        verification_rule=VerificationRule(type="numerical_tolerance", expected_value=5.0),
    )
    task_res = controller.run_task(req)
    trace_events = temp_storage.get_events(task_res.task_id)

    # Manually inject tool execution failed event into trace to simulate transient failure
    temp_storage.save_events([
        trace_events[0].model_copy(update={"event_type": "tool_execution_failed", "output_summary": "Network timeout"})
    ])
    updated_traces = temp_storage.get_events(task_res.task_id)

    fixed_engine = FixedRetryEngine(tool_registry=registry, storage=temp_storage)
    task_ctx = {
        "task_description": task_res.task,
        "allowed_tools": ["calculator"],
        "verification_rule": req.verification_rule.model_dump(),
    }
    report = fixed_engine.execute_fixed_retry(
        task_response=task_res,
        task_context=task_ctx,
        initial_trace_events=updated_traces,
    )

    assert report.recovery_attempted is True
    assert report.policy_id == "fixed_retry"
    assert report.terminal_status == RecoveryTerminalStatus.RECOVERED_SUCCESSFULLY

def test_checkpoint_sanitization():
    """Checkpointing strips sensitive credentials, auth tokens, and private model reasoning."""
    from backend.models.schemas import InteractionStep, ToolResult
    raw_history = [
        InteractionStep(
            step_index=1,
            role="assistant",
            content="sk-1234567890abcdef1234567890 is the secret token",
        ),
        InteractionStep(
            step_index=1,
            role="tool",
            tool_result=ToolResult(
                tool_name="calculator",
                success=True,
                data={"result": 100, "auth_header": "Bearer secret_jwt_token_here_12345"},
            ),
        ),
    ]

    chk = RecoveryStateManager.create_checkpoint(
        task_id="t_sec",
        run_id="r_sec",
        recovery_attempt_id="atm_sec",
        step_index=1,
        history=raw_history,
    )

    chk_json = chk.model_dump_json()
    assert "sk-1234567890abcdef1234567890" not in chk_json
    assert "secret_jwt_token_here_12345" not in chk_json
    assert "[REDACTED]" in chk_json

def test_original_failure_preserved_when_recovery_fails(temp_storage):
    """NEGATIVE TEST: A failed recovery never overwrites or erases the original failure."""
    registry = ToolRegistry()
    controller = AgentController(tool_registry=registry, storage=temp_storage)

    req = TaskCreateRequest(
        task="Impossible computation",
        allowed_tools=["calculator"],
        verification_rule=VerificationRule(type="numerical_tolerance", expected_value=9999.0),
    )
    task_res = controller.run_task(req)
    trace_events = temp_storage.get_events(task_res.task_id)

    diag_report = DiagnosticReport(
        diagnostic_id=f"diag_{task_res.task_id}",
        task_id=task_res.task_id,
        run_id=task_res.run_id,
        detector_version="v1.0",
        diagnostic_status=DiagnosticStatus.FAILURE_DETECTED,
        findings=[
            DiagnosticFinding(
                finding_id="fnd_err",
                rule_id="R6_INCORRECT_ANSWER",
                failure_category=FailureCategory.INCORRECT_FINAL_ANSWER,
                severity=SeverityLevel.HIGH,
                confirmation_status=ConfirmationStatus.CONFIRMED,
                explanation="Observed value does not match expected answer.",
                recommended_next_action="Correct answer",
            )
        ],
        features=TrajectoryFeatures(),
    )
    temp_storage.save_diagnostic_report(diag_report)

    # Budget restricted to prevent completion
    budget_cfg = RecoveryBudgetConfig(max_recovery_model_calls=0)
    engine = RecoveryEngine(tool_registry=registry, storage=temp_storage, budget_config=budget_cfg)

    rec_report = engine.recover(
        task_response=task_res,
        task_context={"task_description": req.task, "verification_rule": req.verification_rule.model_dump()},
        initial_trace_events=trace_events,
        diag_report=diag_report,
    )

    # Original attempt status preserved in report
    assert rec_report.original_status == task_res.status
    assert rec_report.terminal_status in (RecoveryTerminalStatus.FAILED_AFTER_RECOVERY, RecoveryTerminalStatus.BUDGET_EXHAUSTED, RecoveryTerminalStatus.UNRESOLVED)
    # Original task record in database remains untouched
    saved_task = temp_storage.get_task(task_res.task_id)
    assert saved_task.task_id == task_res.task_id
