"""Evaluation and benchmark framework package for TraceGuard."""
from backend.evaluation.ablation_analysis import (
    AblationAnalysisResult,
    AblationVariantResult,
    ComponentMarginalContribution,
    compute_ablation_analysis,
)
from backend.evaluation.benchmark_runner import BenchmarkRunner
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.experiment_config import (
    ExperimentConfig,
    compute_configuration_hash,
    sanitize_dict_for_hashing,
)
from backend.evaluation.experiment_runner import ExperimentExecutionSummary, FullExperimentRunner
from backend.evaluation.failure_analysis import (
    CategoryFailureSummary,
    FailureAnalysisReport,
    compute_failure_analysis,
)
from backend.evaluation.failure_injection import InjectedModelAdapter, InjectedToolExecutor
from backend.evaluation.manifest import (
    EnvironmentInfo,
    ReproducibilityManifest,
    create_reproducibility_manifest,
)
from backend.evaluation.metrics import compute_experiment_metrics
from backend.evaluation.recovery_metrics import (
    ComparativeMetricsSummary,
    RecoveryEfficiencyMetrics,
    RecoveryMetricsSummary,
    compute_recovery_metrics,
)
from backend.evaluation.report_generator import ResearchReportGenerator
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
from backend.evaluation.statistical_tests import (
    PairedComparisonMetric,
    compute_paired_bootstrap_ci,
    exact_binomial_p_value,
    perform_mcnemar_test,
    perform_paired_latency_comparison,
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
    # Milestone 4 & 5
    "ExperimentConfig",
    "compute_configuration_hash",
    "sanitize_dict_for_hashing",
    "FullExperimentRunner",
    "ExperimentExecutionSummary",
    "PairedComparisonMetric",
    "perform_mcnemar_test",
    "perform_paired_latency_comparison",
    "compute_paired_bootstrap_ci",
    "exact_binomial_p_value",
    "CategoryFailureSummary",
    "FailureAnalysisReport",
    "compute_failure_analysis",
    "AblationAnalysisResult",
    "AblationVariantResult",
    "ComponentMarginalContribution",
    "compute_ablation_analysis",
    "ReproducibilityManifest",
    "EnvironmentInfo",
    "create_reproducibility_manifest",
    "ResearchReportGenerator",
    "RecoveryMetricsSummary",
    "ComparativeMetricsSummary",
    "compute_recovery_metrics",
]
