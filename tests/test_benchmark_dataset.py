"""Tests for benchmark dataset loading, schema validation, and filtering."""
import json
import pytest
from backend.evaluation.dataset import BenchmarkDatasetError, BenchmarkDatasetLoader

def test_load_official_benchmark_v1():
    loader = BenchmarkDatasetLoader()
    tasks = loader.load_tasks(version="v1.0")

    # Verify minimum requirements: at least 40 total
    assert len(tasks) >= 40

    # Verify category counts (minimum 8 in each category)
    categories = {}
    for t in tasks:
        categories[t.category] = categories.get(t.category, 0) + 1

    assert categories.get("arithmetic", 0) >= 8
    assert categories.get("data_lookup", 0) >= 8
    assert categories.get("document_qa", 0) >= 8
    assert categories.get("multi_step", 0) >= 8
    assert categories.get("failure_scenario", 0) >= 8

def test_benchmark_task_unique_ids():
    loader = BenchmarkDatasetLoader()
    tasks = loader.load_tasks(version="v1.0")
    task_ids = [t.task_id for t in tasks]
    assert len(task_ids) == len(set(task_ids)), "Task IDs in benchmark must be unique!"

def test_benchmark_filtering_by_category():
    loader = BenchmarkDatasetLoader()
    arith_tasks = loader.load_tasks(version="v1.0", category="arithmetic")
    assert len(arith_tasks) >= 8
    for t in arith_tasks:
        assert t.category == "arithmetic"

def test_benchmark_filtering_by_task_ids():
    loader = BenchmarkDatasetLoader()
    selected = ["ARITH-001", "DATA-002", "DOC-003"]
    tasks = loader.load_tasks(version="v1.0", task_ids=selected)
    assert len(tasks) == 3
    assert set(t.task_id for t in tasks) == set(selected)

def test_reject_duplicate_task_id(tmp_path):
    bad_file = tmp_path / "benchmark_dup.jsonl"
    task_line = json.dumps({
        "task_id": "DUP-001",
        "benchmark_version": "dup",
        "category": "arithmetic",
        "task_description": "Calculate 1 + 1",
        "allowed_tools": ["calculator"]
    })
    bad_file.write_text(f"{task_line}\n{task_line}\n", encoding="utf-8")

    loader = BenchmarkDatasetLoader(benchmarks_dir=tmp_path)
    with pytest.raises(BenchmarkDatasetError) as exc_info:
        loader.load_tasks(version="dup")
    assert "Duplicate task ID 'DUP-001'" in str(exc_info.value)

def test_reject_malformed_json(tmp_path):
    bad_file = tmp_path / "benchmark_bad.jsonl"
    bad_file.write_text("{this is not valid json}\n", encoding="utf-8")

    loader = BenchmarkDatasetLoader(benchmarks_dir=tmp_path)
    with pytest.raises(BenchmarkDatasetError) as exc_info:
        loader.load_tasks(version="bad")
    assert "Malformed JSON" in str(exc_info.value)

def test_reject_invalid_schema(tmp_path):
    bad_file = tmp_path / "benchmark_invalid.jsonl"
    # Missing required category and task_description
    bad_file.write_text(json.dumps({"task_id": "INV-001"}) + "\n", encoding="utf-8")

    loader = BenchmarkDatasetLoader(benchmarks_dir=tmp_path)
    with pytest.raises(BenchmarkDatasetError) as exc_info:
        loader.load_tasks(version="invalid")
    assert "Validation error" in str(exc_info.value)

def test_list_available_benchmarks():
    loader = BenchmarkDatasetLoader()
    benchmarks = loader.list_available_benchmarks()
    assert len(benchmarks) >= 1
    v1 = next((b for b in benchmarks if "1" in b["benchmark_version"]), None)
    assert v1 is not None
    assert v1["total_tasks"] >= 40
    assert "categories" in v1
