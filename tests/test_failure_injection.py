"""Unit tests for all 8 controlled failure injection scenarios."""
import pytest
from backend.agents.controller import AgentController
from backend.agents.mock_model import MockModelAdapter
from backend.agents.tool_registry import ToolRegistry
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.failure_injection import InjectedModelAdapter, InjectedToolExecutor
from backend.models.schemas import TaskCreateRequest
from backend.tracing.storage import TraceStorage

@pytest.fixture
def storage(tmp_path):
    return TraceStorage(db_path=str(tmp_path / "failure_test.db"))

@pytest.fixture
def tasks_by_id():
    loader = BenchmarkDatasetLoader()
    tasks = loader.load_tasks(version="v1.0")
    return {t.task_id: t for t in tasks}

def _run_with_injection(task, storage, inject=True):
    registry = ToolRegistry()
    base_model = MockModelAdapter()
    failure_config = task.failure_scenario if inject else None

    if failure_config:
        tool_executor = InjectedToolExecutor(registry, failure_config=failure_config)
        model_adapter = InjectedModelAdapter(base_model, failure_config=failure_config)
        controller = AgentController(
            tool_registry=registry,
            model_adapter=model_adapter,
            storage=storage
        )
        controller.tool_executor = tool_executor
    else:
        controller = AgentController(
            tool_registry=registry,
            model_adapter=base_model,
            storage=storage
        )

    req = TaskCreateRequest(
        task=task.task_description,
        max_steps=task.failure_scenario.injection_parameters.get("max_steps", 6) if task.failure_scenario else 6,
        timeout_seconds=task.failure_scenario.injection_parameters.get("simulated_timeout_seconds", 30.0) if task.failure_scenario else 30.0,
        allowed_tools=task.allowed_tools,
        verification_rule=task.verification_rule
    )
    return controller.run_task(req)

# 1. Transient tool failure
def test_scenario_transient_tool_failure(storage, tasks_by_id):
    task = tasks_by_id["FAIL-001"]
    resp = _run_with_injection(task, storage, inject=True)
    events = storage.get_events(resp.task_id)
    failed_tools = [e for e in events if e.event_type == "tool_execution_failed"]
    assert len(failed_tools) >= 1
    assert "Service Temporarily Unavailable" in failed_tools[0].output_summary

# 2. Invalid tool arguments
def test_scenario_invalid_tool_arguments(storage, tasks_by_id):
    task = tasks_by_id["FAIL-002"]
    resp = _run_with_injection(task, storage, inject=True)
    events = storage.get_events(resp.task_id)
    failed_tools = [e for e in events if e.event_type == "tool_execution_failed"]
    assert len(failed_tools) >= 1
    assert "Invalid arguments" in failed_tools[0].output_summary

# 3. Repeated tool calls
def test_scenario_repeated_tool_calls(storage, tasks_by_id):
    task = tasks_by_id["FAIL-003"]
    resp = _run_with_injection(task, storage, inject=True)
    assert resp.status == "step_limit_reached"
    events = storage.get_events(resp.task_id)
    tool_calls = [e for e in events if e.event_type == "tool_call_requested"]
    assert len(tool_calls) >= 3

# 4. Missing evidence
def test_scenario_missing_evidence(storage, tasks_by_id):
    task = tasks_by_id["FAIL-004"]
    resp = _run_with_injection(task, storage, inject=True)
    assert resp.status == "completed"
    assert "no relevant" in resp.final_answer.lower() or "not found" in resp.final_answer.lower()

# 5. Incorrect final answer
def test_scenario_incorrect_final_answer(storage, tasks_by_id):
    task = tasks_by_id["FAIL-005"]
    resp = _run_with_injection(task, storage, inject=True)
    assert resp.status == "completed"
    assert "99999" in resp.final_answer
    assert resp.verification is not None
    assert resp.verification.verified is False

# 6. Step limit exhaustion
def test_scenario_step_limit_exhaustion(storage, tasks_by_id):
    task = tasks_by_id["FAIL-006"]
    resp = _run_with_injection(task, storage, inject=True)
    assert resp.status == "step_limit_reached"
    assert "maximum step limit" in resp.error_info

# 7. Tool timeout
def test_scenario_tool_timeout(storage, tasks_by_id):
    task = tasks_by_id["FAIL-007"]
    resp = _run_with_injection(task, storage, inject=True)
    assert resp.status == "failed"
    assert "Simulated timeout limit" in (resp.error_info or "")

# 8. No matching record
def test_scenario_no_matching_record(storage, tasks_by_id):
    task = tasks_by_id["FAIL-008"]
    resp = _run_with_injection(task, storage, inject=True)
    assert resp.status == "completed"
    assert "No matching records found" in resp.final_answer

# Disabled by default
def test_failure_injection_disabled_by_default(storage, tasks_by_id):
    task = tasks_by_id["FAIL-001"]
    resp = _run_with_injection(task, storage, inject=False)
    # When injection is disabled, normal execution proceeds
    events = storage.get_events(resp.task_id)
    transient_errors = [e for e in events if "Service Temporarily Unavailable" in (e.output_summary or "")]
    assert len(transient_errors) == 0
