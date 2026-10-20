"""Unit tests for ReproducibilityManifest and ResearchReportGenerator."""
from backend.evaluation.experiment_config import ExperimentConfig
from backend.evaluation.manifest import create_reproducibility_manifest
from backend.evaluation.recovery_metrics import RecoveryMetricsSummary
from backend.evaluation.report_generator import ResearchReportGenerator
from backend.evaluation.statistical_tests import PairedComparisonMetric

def test_manifest_creation_and_credential_sanitization():
    """Manifest must strip credentials and record system environment."""
    config = ExperimentConfig(
        experiment_id="exp_manifest_test",
        model_configuration={"api_key": "secret_token_123", "model_adapter": "mock"},
    )
    manifest = create_reproducibility_manifest(config)
    assert manifest.experiment_id == "exp_manifest_test"
    assert manifest.model_configuration["api_key"] == "[REDACTED]"
    assert manifest.environment.python_version is not None
    assert manifest.environment.os_platform is not None
    assert manifest.configuration_hash == config.configuration_hash

def test_report_generator_structure():
    """Report generator produces comprehensive publication-ready markdown."""
    config = ExperimentConfig(experiment_id="exp_report_test")
    manifest = create_reproducibility_manifest(config)
    mode_metrics = {
        "baseline": RecoveryMetricsSummary(
            agent_mode="baseline",
            total_attempted=10,
            initial_successful_tasks=8,
            final_verified_successful_tasks=8,
            end_to_end_success_rate=80.0,
        ),
        "traceguard_recovery": RecoveryMetricsSummary(
            agent_mode="traceguard_recovery",
            total_attempted=10,
            initial_successful_tasks=8,
            final_verified_successful_tasks=9,
            end_to_end_success_rate=90.0,
        ),
    }

    comparisons = [
        PairedComparisonMetric(
            mode_a="baseline",
            mode_b="traceguard_recovery",
            metric_name="task_success_rate",
            sample_size=10,
            point_estimate_a=80.0,
            point_estimate_b=90.0,
            difference_pp=10.0,
            bootstrap_ci_95=(0.0, 20.0),
            test_used="Exact Binomial McNemar",
            p_value=0.5,
            statistically_significant=False,
            interpretation_and_limitations="Small sample test."
        )
    ]

    report_md = ResearchReportGenerator.generate_markdown_report(
        config=config,
        manifest=manifest,
        mode_metrics=mode_metrics,
        statistical_comparisons=comparisons,
    )

    assert "# TraceGuard Research Report" in report_md
    assert "RQ1 (Reliability)" in report_md
    assert "RQ2 (Failure Detection)" in report_md
    assert "Comparative Reliability and Efficiency Results" in report_md
    assert "Statistical Hypothesis Testing" in report_md
    assert "Threats to Validity & Limitations" in report_md
    assert "Reproducibility Instructions" in report_md
    assert config.configuration_hash in report_md
