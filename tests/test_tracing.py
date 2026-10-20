"""Unit tests for observable tracing, SQLite storage, redaction, and JSONL export."""
import json
import pytest
from backend.models.schemas import TaskResponse, TraceEvent, VerificationResult
from backend.tracing.collector import TraceCollector
from backend.tracing.event_schema import (
    EVENT_TASK_STARTED,
    EVENT_TOOL_CALL_REQUESTED,
    EVENT_TOOL_EXEC_COMPLETED,
    EVENT_FINAL_ANSWER_PROPOSED,
    EVENT_TASK_COMPLETED,
    sanitize_text,
)
from backend.tracing.storage import TraceStorage

def test_credential_redaction():
    text_with_key = "Bearer eyJhbGciOiJIUzI1NiIsIn... and api_key=sk-1234567890abcdef12345678"
    sanitized = sanitize_text(text_with_key)
    assert "Bearer=[REDACTED]" in sanitized or "sk-[REDACTED]" in sanitized
    assert "sk-1234567890abcdef12345678" not in sanitized

def test_trace_collector_event_fields(tmp_path):
    storage = TraceStorage(db_path=str(tmp_path / "test_trace.db"))
    collector = TraceCollector(task_id="task_123", run_id="run_456", storage=storage)

    event = collector.record_task_started("Test task prompt")
    assert event.task_id == "task_123"
    assert event.run_id == "run_456"
    assert event.step_index == 0
    assert event.event_type == EVENT_TASK_STARTED
    assert event.status == "started"
    assert event.timestamp is not None
    assert event.input_summary == "Test task prompt"

def test_trace_storage_and_ordering(tmp_path):
    storage = TraceStorage(db_path=str(tmp_path / "test_trace.db"))
    collector = TraceCollector(task_id="task_order", run_id="run_order", storage=storage)

    collector.record_task_started("Starting task")
    collector.record_tool_call_requested(1, "calculator", '{"a": 1, "b": 2}')
    collector.record_tool_exec_completed(1, "calculator", '{"result": 3}', duration_ms=1.5)
    collector.record_final_answer_proposed(2, "The answer is 3.")
    collector.record_task_completed(2, "The answer is 3.", duration_ms=10.0)

    collector.flush()

    events = storage.get_events("task_order")
    assert len(events) == 5
    assert events[0].event_type == EVENT_TASK_STARTED
    assert events[1].event_type == EVENT_TOOL_CALL_REQUESTED
    assert events[2].event_type == EVENT_TOOL_EXEC_COMPLETED
    assert events[3].event_type == EVENT_FINAL_ANSWER_PROPOSED
    assert events[4].event_type == EVENT_TASK_COMPLETED

    # Check step index ordering
    step_indices = [e.step_index for e in events]
    assert step_indices == [0, 1, 1, 2, 2]

def test_jsonl_export(tmp_path):
    storage = TraceStorage(db_path=str(tmp_path / "test_trace.db"))
    collector = TraceCollector(task_id="task_jsonl", run_id="run_jsonl", storage=storage)

    collector.record_task_started("Export test")
    collector.record_task_completed(1, "Completed", duration_ms=5.0)
    collector.flush()

    jsonl_output = storage.export_jsonl("task_jsonl")
    lines = [l for l in jsonl_output.splitlines() if l.strip()]
    assert len(lines) == 2

    # Verify each line is valid JSON with required schema fields
    for line in lines:
        data = json.loads(line)
        assert "task_id" in data
        assert "run_id" in data
        assert "event_type" in data
        assert "timestamp" in data
        assert "status" in data

def test_task_storage_persistence(tmp_path):
    storage = TraceStorage(db_path=str(tmp_path / "test_tasks.db"))
    task_res = TaskResponse(
        task_id="task_persist_01",
        run_id="run_persist_01",
        task="Test persistence",
        status="completed",
        final_answer="Answer 42",
        error_info=None,
        verification=VerificationResult(
            verified=True,
            status="verified",
            verification_method="numerical_tolerance",
            expected_result=42,
            observed_result=42,
            verification_message="Verified OK"
        ),
        steps_count=2,
        duration_ms=45.2,
        created_at="2026-10-20T10:00:00.000Z",
        completed_at="2026-10-20T10:00:01.000Z"
    )

    storage.save_task(task_res)
    loaded = storage.get_task("task_persist_01")
    assert loaded is not None
    assert loaded.task_id == "task_persist_01"
    assert loaded.status == "completed"
    assert loaded.final_answer == "Answer 42"
    assert loaded.verification.verified is True
    assert loaded.verification.expected_result == 42
