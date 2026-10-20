"""Unit and integration tests for BenchmarkRunner and persistence."""
import pytest
from backend.evaluation.benchmark_runner import BenchmarkRunner
from backend.evaluation.schemas import ExperimentRunRequest
from backend.tracing.storage import TraceStorage

@pytest.fixture
def storage(tmp_path):
    return TraceStorage(db_path=str(tmp_path / "runner_test.db"))

def test_runner_category_execution(storage):
    runner = BenchmarkRunner(storage=storage)
    req = ExperimentRunRequest(
        benchmark_version="v1.0",
        category="arithmetic",
        agent_mode="baseline",
        repetitions=1
    )

    summary = runner.run_experiment(req)
    assert summary.status == "completed"
    assert summary.total_tasks >= 8
    assert summary.completed_tasks == summary.total_tasks
    assert summary.metrics is not None
    assert summary.metrics.total_attempted == summary.total_tasks
    # Arithmetic tasks with deterministic mock model should be 100% verified
    assert summary.metrics.success_rate == 100.0

    # Verify persistence
    saved_exp = storage.get_experiment(summary.experiment_id)
    assert saved_exp is not None
    assert saved_exp.experiment_id == summary.experiment_id

    results = storage.get_experiment_results(summary.experiment_id)
    assert len(results) == summary.total_tasks

    # Verify trace reference links to actual trace events
    for res in results:
        task_id = res.trace_reference["task_id"]
        events = storage.get_events(task_id)
        assert len(events) >= 2

def test_runner_selected_task_ids(storage):
    runner = BenchmarkRunner(storage=storage)
    req = ExperimentRunRequest(
        benchmark_version="v1.0",
        task_ids=["ARITH-001", "DATA-001", "DOC-001"],
        agent_mode="baseline",
        repetitions=1
    )

    summary = runner.run_experiment(req)
    assert summary.total_tasks == 3
    assert summary.metrics.successful_tasks == 3

def test_runner_repetitions(storage):
    runner = BenchmarkRunner(storage=storage)
    req = ExperimentRunRequest(
        benchmark_version="v1.0",
        task_ids=["ARITH-001"],
        agent_mode="baseline",
        repetitions=3
    )

    summary = runner.run_experiment(req)
    assert summary.total_tasks == 3
    assert summary.completed_tasks == 3
    assert summary.metrics.repeatability is not None
    assert summary.metrics.repeatability.repetitions == 3
    assert summary.metrics.repeatability.output_consistent is True

def test_deterministic_reproducibility(tmp_path):
    # Run the same benchmark tasks twice and verify outcomes match identically
    storage1 = TraceStorage(db_path=str(tmp_path / "rep1.db"))
    storage2 = TraceStorage(db_path=str(tmp_path / "rep2.db"))

    runner1 = BenchmarkRunner(storage=storage1)
    runner2 = BenchmarkRunner(storage=storage2)

    req = ExperimentRunRequest(
        benchmark_version="v1.0",
        category="arithmetic",
        agent_mode="baseline",
        repetitions=1
    )

    exp1 = runner1.run_experiment(req)
    exp2 = runner2.run_experiment(req)

    assert exp1.metrics.success_rate == exp2.metrics.success_rate
    assert exp1.metrics.successful_tasks == exp2.metrics.successful_tasks
    assert exp1.metrics.total_tool_calls == exp2.metrics.total_tool_calls

    res1 = storage1.get_experiment_results(exp1.experiment_id)
    res2 = storage2.get_experiment_results(exp2.experiment_id)

    assert len(res1) == len(res2)
    for r1, r2 in zip(res1, res2):
        assert r1.task_id == r2.task_id
        assert r1.observed_answer == r2.observed_answer
        assert r1.terminal_status == r2.terminal_status
