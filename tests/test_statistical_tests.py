"""Unit tests for paired statistical tests, McNemar evaluations, and bootstrap confidence intervals."""
import pytest
from backend.evaluation.statistical_tests import (
    compute_paired_bootstrap_ci,
    exact_binomial_p_value,
    perform_mcnemar_test,
    perform_paired_latency_comparison,
)

def test_exact_binomial_p_value():
    """Verify exact binomial two-sided p-values."""
    assert exact_binomial_p_value(k=0, n=0, p=0.5) == 1.0
    # 0 out of 10 (all in one direction): 2 * (1/1024) = 2/1024 = 0.00195
    p_extreme = exact_binomial_p_value(k=0, n=10, p=0.5)
    assert 0.001 <= p_extreme <= 0.003
    # 5 out of 10 (perfect split): p = 1.0
    p_split = exact_binomial_p_value(k=5, n=10, p=0.5)
    assert p_split >= 0.99

def test_mcnemar_zero_discordant_pairs():
    """Identical outcomes across all tasks must produce difference = 0.0, p-value = 1.0."""
    outcomes_a = [1, 1, 0, 1, 0, 0, 1]
    outcomes_b = [1, 1, 0, 1, 0, 0, 1]
    res = perform_mcnemar_test(
        outcomes_a=outcomes_a,
        outcomes_b=outcomes_b,
        mode_a_name="baseline",
        mode_b_name="traceguard_recovery",
    )
    assert res.difference_pp == 0.0
    assert res.p_value == 1.0
    assert res.statistically_significant is False
    assert res.discordant_pairs["total_discordant"] == 0

def test_mcnemar_small_sample_exact():
    """Small discordant sample size (<25) uses exact binomial test."""
    outcomes_a = [1, 0, 0, 0, 1]
    outcomes_b = [1, 1, 1, 1, 1]
    # discordant: b=0 (a=1, b=0), c=3 (a=0, b=1) -> total discordant = 3
    res = perform_mcnemar_test(
        outcomes_a=outcomes_a,
        outcomes_b=outcomes_b,
        mode_a_name="baseline",
        mode_b_name="traceguard_recovery",
    )
    assert res.difference_pp == 60.0  # 100% vs 40% = +60 pp
    assert res.test_used.startswith("Exact Binomial McNemar")
    assert res.p_value is not None
    assert res.discordant_pairs["total_discordant"] == 3

def test_mcnemar_asymptotic_large_sample():
    """Large sample with >=25 discordant pairs uses Chi-Square with continuity correction."""
    # 30 discordant: 25 vs 5
    outcomes_a = [1] * 25 + [0] * 5 + [1] * 10
    outcomes_b = [0] * 25 + [1] * 5 + [1] * 10
    res = perform_mcnemar_test(
        outcomes_a=outcomes_a,
        outcomes_b=outcomes_b,
        mode_a_name="baseline",
        mode_b_name="traceguard_recovery",
    )
    assert res.test_used.startswith("McNemar Chi-Square with continuity correction")
    assert res.p_value is not None
    assert res.statistically_significant is True  # 25 vs 5 is strongly significant

def test_paired_bootstrap_ci():
    """Bootstrap confidence interval calculation for paired differences."""
    vals_a = [10.0, 20.0, 30.0, 40.0, 50.0]
    vals_b = [15.0, 25.0, 35.0, 45.0, 55.0]  # constant +5.0 difference
    low, high = compute_paired_bootstrap_ci(vals_a, vals_b, n_resamples=500)
    assert low == 5.0
    assert high == 5.0

def test_paired_latency_comparison():
    """Latency comparison between two modes."""
    lats_a = [2.0, 3.0, 2.5, 3.5]
    lats_b = [5.0, 6.0, 5.5, 6.5]
    res = perform_paired_latency_comparison(
        latencies_a=lats_a,
        latencies_b=lats_b,
        mode_a_name="baseline",
        mode_b_name="traceguard_recovery"
    )
    assert res.point_estimate_a == 2.75
    assert res.point_estimate_b == 5.75
    assert res.difference_pp == 3.0  # +3ms overhead
    assert res.bootstrap_ci_95[0] > 0
