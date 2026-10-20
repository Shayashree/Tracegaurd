"""Unit tests for component ablation analysis."""
from backend.evaluation.ablation_analysis import compute_ablation_analysis

def test_ablation_decomposition():
    """Verify marginal contributions of detection alone, fixed retry, and targeted recovery."""
    variants = {
        "baseline": {
            "sample_size": 20,
            "success_rate": 60.0,
            "total_failures": 8,
            "interventions_initiated": 0,
            "mean_latency_ms": 10.0,
            "mean_tool_calls": 1.0,
            "mean_model_calls": 1.0,
        },
        "detection_only": {
            "sample_size": 20,
            "success_rate": 60.0,
            "total_failures": 8,
            "interventions_initiated": 0,
            "mean_latency_ms": 10.5,
            "mean_tool_calls": 1.0,
            "mean_model_calls": 1.0,
        },
        "fixed_retry": {
            "sample_size": 20,
            "success_rate": 65.0,
            "total_failures": 7,
            "interventions_initiated": 3,
            "mean_latency_ms": 12.0,
            "mean_tool_calls": 1.3,
            "mean_model_calls": 1.0,
        },
        "traceguard_recovery": {
            "sample_size": 20,
            "success_rate": 80.0,
            "total_failures": 4,
            "interventions_initiated": 5,
            "mean_latency_ms": 15.0,
            "mean_tool_calls": 1.6,
            "mean_model_calls": 1.2,
        },
    }

    ablation = compute_ablation_analysis(
        experiment_id="exp_ablation_test",
        variant_results=variants,
    )

    assert len(ablation.variants) == 4
    assert len(ablation.contributions) >= 3

    # Check detection alone marginal delta
    det_contrib = next(c for c in ablation.contributions if "Detection" in c.component_name)
    assert det_contrib.delta_success_rate_pp == 0.0
    assert det_contrib.delta_latency_ms == 0.5

    # Check fixed retry marginal delta vs baseline
    fixed_contrib = next(c for c in ablation.contributions if "Fixed Retry" in c.component_name and "Diagnosis" not in c.component_name)
    assert fixed_contrib.delta_success_rate_pp == 5.0
    assert fixed_contrib.delta_latency_ms == 2.0

    # Check full TraceGuard vs baseline
    tg_contrib = next(c for c in ablation.contributions if "Full TraceGuard" in c.component_name)
    assert tg_contrib.delta_success_rate_pp == 20.0
    assert tg_contrib.delta_latency_ms == 5.0
