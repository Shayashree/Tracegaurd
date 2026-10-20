"""Unit and integration tests for AgentController execution loop."""
import pytest
from backend.agents.controller import AgentController
from backend.agents.mock_model import MockModelAdapter
from backend.agents.tool_registry import ToolRegistry
from backend.models.schemas import (
    ModelResponse,
    ModelTokens,
    TaskCreateRequest,
    ToolCallRequest,
    VerificationRule,
)
from backend.tracing.storage import TraceStorage

@pytest.fixture
def test_storage(tmp_path):
    return TraceStorage(db_path=str(tmp_path / "controller_test.db"))

@pytest.fixture
def controller(test_storage):
    return AgentController(storage=test_storage, model_adapter=MockModelAdapter())

def test_multi_step_product_price_and_calculator(controller, test_storage):
    """
    Core demonstration from prompt:
    Task: "Find the prices of Product A and Product B, then calculate their combined price."
    Expected:
    1. Agent receives task
    2. Agent requests structured data lookup
    3. Tool returns prices
    4. Agent requests calculator operation
    5. Calculator returns total
    6. Agent proposes final answer
    7. Verifier checks total
    """
    req = TaskCreateRequest(
        task="Find the prices of Product A and Product B, then calculate their combined price.",
        verification_rule=VerificationRule(type="numerical_tolerance", expected_value=130.0)
    )

    resp = controller.run_task(req)

    assert resp.status == "completed"
    assert resp.final_answer is not None
    assert "130" in resp.final_answer
    assert resp.verification is not None
    assert resp.verification.verified is True
    assert resp.steps_count >= 2

    # Verify execution traces
    events = test_storage.get_events(resp.task_id)
    event_types = [e.event_type for e in events]
    assert "task_started" in event_types
    assert "tool_call_requested" in event_types
    assert "tool_execution_completed" in event_types
    assert "final_answer_proposed" in event_types
    assert "verification_completed" in event_types
    assert "task_completed" in event_types

    # Ensure both data_lookup and calculator were executed
    executed_tools = [e.tool_name for e in events if e.tool_name]
    assert "data_lookup" in executed_tools
    assert "calculator" in executed_tools

def test_direct_calculation_task(controller):
    req = TaskCreateRequest(
        task="Calculate 25 * 4",
        verification_rule=VerificationRule(type="numerical_tolerance", expected_value=100.0)
    )
    resp = controller.run_task(req)
    assert resp.status == "completed"
    assert "100" in resp.final_answer
    assert resp.verification.verified is True

def test_document_search_task(controller):
    req = TaskCreateRequest(
        task="What is the return policy for purchases?",
        verification_rule=VerificationRule(
            type="evidence_reference",
            required_snippets=["DOC-REFUND-001", "30 days"]
        )
    )
    resp = controller.run_task(req)
    assert resp.status == "completed"
    assert "DOC-REFUND-001" in resp.final_answer
    assert resp.verification.verified is True

def test_controlled_tool_error_handling(controller, test_storage):
    req = TaskCreateRequest(
        task="Divide 100 by 0",
        mock_scenario="division_by_zero"
    )
    resp = controller.run_task(req)
    assert resp.status == "completed"
    assert "error" in resp.final_answer.lower() or "cannot divide by zero" in resp.final_answer.lower()

    # Check that a failed tool execution trace was logged
    events = test_storage.get_events(resp.task_id)
    failed_tools = [e for e in events if e.event_type == "tool_execution_failed"]
    assert len(failed_tools) >= 1
    assert "Cannot divide by zero" in failed_tools[0].output_summary

def test_step_limit_enforcement(test_storage):
    # Set max_steps = 3 with an infinite loop scenario
    ctrl = AgentController(storage=test_storage, model_adapter=MockModelAdapter())
    req = TaskCreateRequest(
        task="Please run an infinite step limit test",
        max_steps=3,
        mock_scenario="infinite_loop"
    )
    resp = ctrl.run_task(req)
    assert resp.status == "step_limit_reached"
    assert resp.steps_count == 3
    assert resp.final_answer is None
    assert "maximum step limit" in resp.error_info

    events = test_storage.get_events(resp.task_id)
    event_types = [e.event_type for e in events]
    assert "step_limit_reached" in event_types
    assert "task_failed" in event_types

def test_timeout_enforcement(test_storage, monkeypatch):
    import time
    ctrl = AgentController(storage=test_storage, model_adapter=MockModelAdapter())

    # Mock time.time to simulate timeout
    req = TaskCreateRequest(
        task="Test timeout task",
        timeout_seconds=1.0,
        mock_scenario="infinite_loop"
    )

    real_time = time.time
    call_count = 0
    def fake_time():
        nonlocal call_count
        call_count += 1
        if call_count > 2:
            return real_time() + 10.0  # Jump forward 10 seconds
        return real_time()

    monkeypatch.setattr(time, "time", fake_time)
    resp = ctrl.run_task(req)
    assert resp.status == "timed_out"
    assert "timeout limit" in resp.error_info

def test_unauthorized_tool_call(test_storage):
    # Model requests calculator, but allowed_tools whitelist only includes data_lookup
    tokens = ModelTokens(prompt_tokens=10, completion_tokens=10, total_tokens=20)
    mock = MockModelAdapter(script=[
        ModelResponse(
            is_final_answer=False,
            tool_call=ToolCallRequest(tool_name="calculator", arguments={"operation": "add", "a": 1, "b": 1}),
            model_name="mock",
            tokens_used=tokens
        ),
        ModelResponse(
            is_final_answer=True,
            final_answer="Stopped after disallowed tool.",
            model_name="mock",
            tokens_used=tokens
        )
    ])
    ctrl = AgentController(storage=test_storage, model_adapter=mock)
    req = TaskCreateRequest(
        task="Disallowed tool test",
        allowed_tools=["data_lookup"]
    )
    resp = ctrl.run_task(req)
    assert resp.status == "completed"

    events = test_storage.get_events(resp.task_id)
    tool_failures = [e for e in events if e.event_type == "tool_execution_failed"]
    assert len(tool_failures) >= 1
    assert "not in the allowed tools list" in tool_failures[0].output_summary
