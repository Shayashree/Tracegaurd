"""Unit tests for feature extraction and argument normalization."""
import json
import pytest
from backend.reliability.feature_extractor import TrajectoryFeatureExtractor, normalize_tool_arguments

def test_stable_argument_normalization_dict_keys():
    # Different key insertion orders should yield identical normalized representations
    args1 = {"b": 2, "a": 1, "c": 3}
    args2 = {"c": 3, "a": 1, "b": 2}
    norm1 = normalize_tool_arguments(args1)
    norm2 = normalize_tool_arguments(args2)
    assert norm1 == norm2
    assert norm1 == '{"a": 1, "b": 2, "c": 3}'

def test_stable_argument_normalization_numbers_and_whitespace():
    # Floats with .0, whitespace strings, casing
    args1 = {"query": "  Product A  ", "val": 20.0}
    args2 = {"query": "product a", "val": 20}
    norm1 = normalize_tool_arguments(args1)
    norm2 = normalize_tool_arguments(args2)
    assert norm1 == norm2

def test_stable_argument_normalization_strings_and_none():
    assert normalize_tool_arguments(None) == "{}"
    assert normalize_tool_arguments("") == "{}"
    assert normalize_tool_arguments("   ") == "{}"
    raw_str = normalize_tool_arguments("some plain text query")
    assert "some plain text query" in raw_str

def test_deterministic_feature_extraction():
    events = [
        {"step_index": 0, "event_type": "task_started", "timestamp": "2026-10-20T10:00:00.000Z"},
        {"step_index": 0, "event_type": "tool_call_requested", "tool_name": "calculator", "input_summary": '{"operation": "add", "a": 5, "b": 5}', "timestamp": "2026-10-20T10:00:00.010Z"},
        {"step_index": 0, "event_type": "tool_execution_started", "tool_name": "calculator", "timestamp": "2026-10-20T10:00:00.012Z"},
        {"step_index": 0, "event_type": "tool_execution_completed", "tool_name": "calculator", "output_summary": '{"result": 10}', "duration_ms": 2.5, "timestamp": "2026-10-20T10:00:00.015Z"},
        {"step_index": 1, "event_type": "final_answer_proposed", "output_summary": "Result is 10.", "timestamp": "2026-10-20T10:00:00.020Z"},
        {"step_index": 1, "event_type": "verification_completed", "status": "verified", "output_summary": "Verified matches 10", "timestamp": "2026-10-20T10:00:00.022Z"},
        {"step_index": 1, "event_type": "task_completed", "status": "completed", "timestamp": "2026-10-20T10:00:00.025Z"},
    ]

    f1 = TrajectoryFeatureExtractor.extract_features(events)
    f2 = TrajectoryFeatureExtractor.extract_features(events)

    # Identical features across multiple extractions
    assert f1.model_dump() == f2.model_dump()
    assert f1.total_steps == 2
    assert f1.total_tool_calls == 1
    assert f1.unique_tools_used == 1
    assert f1.successful_tool_results == 1
    assert f1.final_answer_produced is True
    assert f1.verification_status == "verified"
    assert f1.terminal_status == "completed"
    assert f1.max_consecutive_identical_tool_calls == 1

def test_feature_extraction_empty_events():
    features = TrajectoryFeatureExtractor.extract_features([])
    assert features.total_steps == 0
    assert features.total_tool_calls == 0
    assert features.terminal_status == "no_events"
