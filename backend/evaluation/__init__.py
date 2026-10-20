"""Evaluation and benchmark framework package."""
from backend.evaluation.benchmark_runner import BenchmarkRunner
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.failure_injection import InjectedModelAdapter, InjectedToolExecutor
from backend.evaluation.metrics import compute_experiment_metrics
from backend.evaluation.schemas import (
    BenchmarkTask,
    ConfidenceInterval,
    EfficiencyMetrics,
    EvaluationMetrics,
    ExperimentRunRequest,
    ExperimentSummary,
    FailureDistribution,
    FailureScenarioConfig,
    RepeatabilityMetrics,
    TaskExecutionResult,
)
from backend.evaluation.statistics import (
    calculate_mean_and_std,
    calculate_percentile,
    calculate_wilson_confidence_interval,
)

__all__ = [
    "BenchmarkRunner",
    "BenchmarkDatasetLoader",
    "InjectedModelAdapter",
    "InjectedToolExecutor",
    "compute_experiment_metrics",
    "BenchmarkTask",
    "ConfidenceInterval",
    "EfficiencyMetrics",
    "EvaluationMetrics",
    "ExperimentRunRequest",
    "ExperimentSummary",
    "FailureDistribution",
    "FailureScenarioConfig",
    "RepeatabilityMetrics",
    "TaskExecutionResult",
    "calculate_wilson_confidence_interval",
    "calculate_percentile",
    "calculate_mean_and_std",
]
