"""Unit tests for the TrajectoryFailureDetector and individual failure rules."""
import pytest
from backend.agents.controller import AgentController
from backend.agents.mock_model import MockModelAdapter
from backend.agents.tool_registry import ToolRegistry
from backend.models.schemas import TaskCreateRequest
from backend.reliability.detector_config import DetectorConfig
from backend.reliability.diagnostic_report import (
    ConfirmationStatus,
    DiagnosticStatus,
    FailureCategory,
    SeverityLevel,
)
from backend.reliability.failure_detector import TrajectoryFailureDetector
from backend.tracing.storage import TraceStorage

@pytest.fixture
def detector():
    return TrajectoryFailureDetector()

@pytest.fixture
def storage(tmp_path):
    return TraceStorage(db_path=str(tmp_path / "detector_test.db"))

def test_f1_repeated_tool_calls(detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "tool_call_requested", "tool_name": "data_lookup", "input_summary": '{"query": "stuck"}'},
        {"step_index": 0, "event_type": "tool_execution_completed", "tool_name": "data_lookup", "output_summary": '{"count": 0, "matches": []}'},
        {"step_index": 1, "event_type": "tool_call_requested", "tool_name": "data_lookup", "input_summary": '{"query": "stuck"}'},
        {"step_index": 1, "event_type": "tool_execution_completed", "tool_name": "data_lookup", "output_summary": '{"count": 0, "matches": []}'},
        {"step_index": 2, "event_type": "tool_call_requested", "tool_name": "data_lookup", "input_summary": '{"query": "stuck"}'},
        {"step_index": 2, "event_type": "tool_execution_completed", "tool_name": "data_lookup", "output_summary": '{"count": 0, "matches": []}'},
        {"step_index": 2, "event_type": "step_limit_reached"},
    ]
    report = detector.analyze(events, task_id="t1", run_id="r1")
    assert report.diagnostic_status == DiagnosticStatus.FAILURE_DETECTED
    categories = [f.failure_category for f in report.findings]
    assert FailureCategory.REPEATED_TOOL_CALLS in categories
    f1_finding = next(f for f in report.findings if f.failure_category == FailureCategory.REPEATED_TOOL_CALLS)
    assert f1_finding.confirmation_status == ConfirmationStatus.CONFIRMED
    assert "data_lookup" in f1_finding.explanation

def test_f2_invalid_tool_arguments(detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "tool_call_requested", "tool_name": "calculator", "input_summary": '{"operation": "add", "a": "bad"}'},
        {"step_index": 0, "event_type": "tool_execution_failed", "tool_name": "calculator", "output_summary": "Invalid arguments for tool 'calculator'", "error_type": "ToolExecutionError"},
        {"step_index": 0, "event_type": "task_failed", "error_type": "ToolExecutionError"},
    ]
    report = detector.analyze(events, task_id="t2", run_id="r2")
    assert report.diagnostic_status == DiagnosticStatus.FAILURE_DETECTED
    categories = [f.failure_category for f in report.findings]
    assert FailureCategory.INVALID_TOOL_ARGUMENTS in categories

def test_f3_persistent_tool_failure(detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "tool_call_requested", "tool_name": "calculator"},
        {"step_index": 0, "event_type": "tool_execution_failed", "tool_name": "calculator", "output_summary": "Service Temporarily Unavailable"},
        {"step_index": 1, "event_type": "tool_call_requested", "tool_name": "calculator"},
        {"step_index": 1, "event_type": "tool_execution_failed", "tool_name": "calculator", "output_summary": "Service Temporarily Unavailable"},
        {"step_index": 1, "event_type": "task_failed", "error_type": "ToolExecutionError"},
    ]
    report = detector.analyze(events, task_id="t3", run_id="r3")
    assert report.diagnostic_status == DiagnosticStatus.FAILURE_DETECTED
    categories = [f.failure_category for f in report.findings]
    assert FailureCategory.TOOL_EXECUTION_FAILURE in categories

def test_f4_lack_of_progress(detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "tool_call_requested", "tool_name": "data_lookup", "input_summary": '{"query": "unknown 1"}'},
        {"step_index": 0, "event_type": "tool_execution_completed", "tool_name": "data_lookup", "output_summary": '{"count": 0, "matches": []}'},
        {"step_index": 1, "event_type": "tool_call_requested", "tool_name": "data_lookup", "input_summary": '{"query": "unknown 2"}'},
        {"step_index": 1, "event_type": "tool_execution_completed", "tool_name": "data_lookup", "output_summary": '{"count": 0, "matches": []}'},
        {"step_index": 2, "event_type": "tool_call_requested", "tool_name": "data_lookup", "input_summary": '{"query": "unknown 3"}'},
        {"step_index": 2, "event_type": "tool_execution_completed", "tool_name": "data_lookup", "output_summary": '{"count": 0, "matches": []}'},
    ]
    report = detector.analyze(events, task_id="t4", run_id="r4")
    categories = [f.failure_category for f in report.findings]
    assert FailureCategory.LACK_OF_PROGRESS in categories

def test_f5_missing_evidence(detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "final_answer_proposed", "output_summary": "Policy says return in 10 days."},
        {"step_index": 0, "event_type": "verification_completed", "status": "failed", "output_summary": "Evidence check failed"},
        {"step_index": 0, "event_type": "task_completed"},
    ]
    task_context = {
        "task_description": "What is the return policy according to documents?",
        "verification_rule": {"type": "evidence_reference", "required_document_id": "DOC-REFUND-001"}
    }
    report = detector.analyze(events, task_id="t5", run_id="r5", task_context=task_context)
    categories = [f.failure_category for f in report.findings]
    assert FailureCategory.MISSING_EVIDENCE in categories or FailureCategory.INCORRECT_FINAL_ANSWER in categories

def test_f6_incorrect_final_answer(detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "tool_call_requested", "tool_name": "calculator"},
        {"step_index": 0, "event_type": "tool_execution_completed", "tool_name": "calculator", "output_summary": '{"result": 100}'},
        {"step_index": 1, "event_type": "final_answer_proposed", "output_summary": "The answer is 99999."},
        {"step_index": 1, "event_type": "verification_completed", "status": "failed", "output_summary": "Observed 99999 does not match expected 100"},
        {"step_index": 1, "event_type": "task_completed"},
    ]
    report = detector.analyze(events, task_id="t6", run_id="r6")
    assert report.diagnostic_status == DiagnosticStatus.FAILURE_DETECTED
    assert report.primary_failure_category == FailureCategory.INCORRECT_FINAL_ANSWER
    f6_finding = next(f for f in report.findings if f.failure_category == FailureCategory.INCORRECT_FINAL_ANSWER)
    assert f6_finding.confirmation_status == ConfirmationStatus.CONFIRMED

def test_f7_step_limit_exhaustion(detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 3, "event_type": "step_limit_reached"},
        {"step_index": 3, "event_type": "task_failed", "error_type": "StepLimitExceeded"},
    ]
    report = detector.analyze(events, task_id="t7", run_id="r7")
    assert report.diagnostic_status == DiagnosticStatus.FAILURE_DETECTED
    categories = [f.failure_category for f in report.findings]
    assert FailureCategory.STEP_LIMIT_EXHAUSTION in categories

def test_f8_malformed_model_output(detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "task_failed", "error_type": "MalformedModelResponse", "output_summary": "Model responded with neither a tool call nor a final answer."},
    ]
    report = detector.analyze(events, task_id="t8", run_id="r8")
    assert report.diagnostic_status == DiagnosticStatus.FAILURE_DETECTED
    categories = [f.failure_category for f in report.findings]
    assert FailureCategory.INVALID_MODEL_OUTPUT in categories

def test_f9_unverified_completion(detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "tool_call_requested", "tool_name": "calculator"},
        {"step_index": 0, "event_type": "tool_execution_completed", "tool_name": "calculator", "output_summary": '{"result": 42}'},
        {"step_index": 1, "event_type": "final_answer_proposed", "output_summary": "Calculated 42"},
        {"step_index": 1, "event_type": "task_completed"},
    ]
    task_context = {"verification_rule": None}
    report = detector.analyze(events, task_id="t9", run_id="r9", task_context=task_context)
    categories = [f.failure_category for f in report.findings]
    assert FailureCategory.UNVERIFIED_COMPLETION in categories
    # Note: Unverified completion must not be marked as confirmed failure!
    unverif_finding = next(f for f in report.findings if f.failure_category == FailureCategory.UNVERIFIED_COMPLETION)
    assert unverif_finding.confirmation_status == ConfirmationStatus.UNVERIFIED

def test_healthy_trajectory_no_false_alarm(detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "tool_call_requested", "tool_name": "calculator", "input_summary": '{"operation": "add", "a": 2, "b": 2}'},
        {"step_index": 0, "event_type": "tool_execution_completed", "tool_name": "calculator", "output_summary": '{"result": 4}'},
        {"step_index": 1, "event_type": "final_answer_proposed", "output_summary": "The answer is 4."},
        {"step_index": 1, "event_type": "verification_completed", "status": "verified", "output_summary": "Observed 4 matches expected 4"},
        {"step_index": 1, "event_type": "task_completed"},
    ]
    report = detector.analyze(events, task_id="t_healthy", run_id="r_healthy")
    assert report.diagnostic_status == DiagnosticStatus.HEALTHY
    assert len(report.findings) == 0

def test_multiple_findings_for_one_trace(detector):
    # A trace that hits repeated tool calls AND then step limit exhaustion
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "tool_call_requested", "tool_name": "data_lookup", "input_summary": '{"query": "loop"}'},
        {"step_index": 0, "event_type": "tool_execution_completed", "tool_name": "data_lookup", "output_summary": '{"count": 0, "matches": []}'},
        {"step_index": 1, "event_type": "tool_call_requested", "tool_name": "data_lookup", "input_summary": '{"query": "loop"}'},
        {"step_index": 1, "event_type": "tool_execution_completed", "tool_name": "data_lookup", "output_summary": '{"count": 0, "matches": []}'},
        {"step_index": 2, "event_type": "tool_call_requested", "tool_name": "data_lookup", "input_summary": '{"query": "loop"}'},
        {"step_index": 2, "event_type": "tool_execution_completed", "tool_name": "data_lookup", "output_summary": '{"count": 0, "matches": []}'},
        {"step_index": 2, "event_type": "step_limit_reached"},
        {"step_index": 2, "event_type": "task_failed", "error_type": "StepLimitExceeded"},
    ]
    report = detector.analyze(events, task_id="t_multi", run_id="r_multi")
    assert len(report.findings) >= 2
    categories = {f.failure_category for f in report.findings}
    assert FailureCategory.REPEATED_TOOL_CALLS in categories
    assert FailureCategory.STEP_LIMIT_EXHAUSTION in categories

def test_insufficient_data_handling(detector):
    report = detector.analyze([], task_id="t_empty", run_id="r_empty")
    assert report.diagnostic_status == DiagnosticStatus.INSUFFICIENT_DATA
    assert report.primary_failure_category is None

def test_diagnostic_report_persistence(storage, detector):
    events = [
        {"step_index": 0, "event_type": "task_started"},
        {"step_index": 0, "event_type": "tool_call_requested", "tool_name": "calculator"},
        {"step_index": 0, "event_type": "tool_execution_failed", "tool_name": "calculator", "output_summary": "Service error"},
        {"step_index": 1, "event_type": "tool_call_requested", "tool_name": "calculator"},
        {"step_index": 1, "event_type": "tool_execution_failed", "tool_name": "calculator", "output_summary": "Service error"},
        {"step_index": 1, "event_type": "task_failed", "error_type": "ToolExecutionError"},
    ]
    report = detector.analyze(events, task_id="t_persist", run_id="r_persist", experiment_id="exp_test")
    storage.save_diagnostic_report(report)

    # Retrieve by ID
    loaded_by_id = storage.get_diagnostic_report(report.diagnostic_id)
    assert loaded_by_id is not None
    assert loaded_by_id.diagnostic_id == report.diagnostic_id
    assert loaded_by_id.primary_failure_category == FailureCategory.TOOL_EXECUTION_FAILURE

    # Retrieve by run_id
    loaded_by_run = storage.get_diagnostics_for_run("r_persist")
    assert loaded_by_run is not None
    assert loaded_by_run.run_id == "r_persist"

    # Retrieve by task_id
    loaded_by_task = storage.get_diagnostics_for_task("t_persist")
    assert len(loaded_by_task) == 1

    # Retrieve by experiment_id
    loaded_by_exp = storage.get_diagnostics_for_experiment("exp_test")
    assert len(loaded_by_exp) == 1

def test_passive_diagnostics_do_not_alter_agent_execution(storage):
    # Verify that attaching a failure detector produces identical TaskResponse
    # and does not modify agent execution decisions, tool calls, or output.
    req = TaskCreateRequest(
        task="Calculate 25 * 4",
        max_steps=5,
        allowed_tools=["calculator"],
        verification_rule={"type": "numerical_tolerance", "expected_value": 100.0, "tolerance": 0.01}
    )

    # 1. Baseline controller without detector
    ctrl1 = AgentController(
        tool_registry=ToolRegistry(),
        model_adapter=MockModelAdapter(),
        storage=storage,
        failure_detector=None
    )
    resp1 = ctrl1.run_task(req)

    # 2. Controller with detector attached
    detector = TrajectoryFailureDetector()
    ctrl2 = AgentController(
        tool_registry=ToolRegistry(),
        model_adapter=MockModelAdapter(),
        storage=storage,
        failure_detector=detector
    )
    resp2 = ctrl2.run_task(req)

    assert resp1.status == resp2.status == "completed"
    assert resp1.final_answer == resp2.final_answer
    assert resp1.steps_count == resp2.steps_count
    assert resp1.verification.verified == resp2.verification.verified is True

    # Check that diagnostic report was passively generated and persisted for run 2
    diag = storage.get_diagnostics_for_run(resp2.run_id)
    assert diag is not None
    assert diag.diagnostic_status == DiagnosticStatus.HEALTHY
