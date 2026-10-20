"""Integration tests for FullExperimentRunner across multiple agent modes and protocols."""
import pytest
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.experiment_config import ExperimentConfig
from backend.evaluation.experiment_runner import FullExperimentRunner
from backend.tracing.storage import TraceStorage

@pytest.fixture
def temp_runner(tmp_path):
    db_file = tmp_path / "test_exp_runner.db"
    storage = TraceStorage(db_path=str(db_file))
    loader = BenchmarkDatasetLoader()
    return FullExperimentRunner(dataset_loader=loader, storage=storage), storage

def test_full_experiment_runner_comparative(temp_runner):
    """Run comparative experiment across baseline and traceguard_recovery on 2 tasks."""
    runner, storage = temp_runner
    config = ExperimentConfig(
        task_ids=["ARITH-001", "ARITH-002"],
        agent_modes=["baseline", "traceguard_recovery"],
        experiment_type="standard",
    )

    summary = runner.run_experiment(config)

    assert summary.status == "completed"
    assert summary.total_tasks == 4  # 2 tasks * 2 modes
    assert "baseline" in summary.mode_metrics
    assert "traceguard_recovery" in summary.mode_metrics
    assert summary.manifest is not None
    assert summary.report_markdown is not None
    assert len(summary.statistical_comparisons) > 0

    # Verify persisted in database
    persisted_manifest = storage.get_experiment_manifest(config.experiment_id)
    assert persisted_manifest is not None
    assert persisted_manifest["experiment_id"] == config.experiment_id

    persisted_report = storage.get_experiment_report(config.experiment_id)
    assert persisted_report is not None
    assert "# TraceGuard Research Report" in persisted_report

def test_full_experiment_runner_ablation(temp_runner):
    """Run ablation experiment with 4 modes on 1 task."""
    runner, storage = temp_runner
    config = ExperimentConfig(
        task_ids=["ARITH-001"],
        agent_modes=["baseline", "detection_only", "fixed_retry", "traceguard_recovery"],
        experiment_type="ablation",
    )

    summary = runner.run_experiment(config)
    assert summary.status == "completed"
    assert summary.ablation_results is not None
    assert len(summary.ablation_results.variants) == 4
    assert len(summary.ablation_results.contributions) >= 3

    persisted_ablation = storage.get_experiment_ablation(config.experiment_id)
    assert persisted_ablation is not None
    assert "variants" in persisted_ablation
