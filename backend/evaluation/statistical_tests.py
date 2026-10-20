"""Statistical testing and paired comparative evaluation methods for TraceGuard Milestone 5."""
import math
import random
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field
from backend.evaluation.statistics import calculate_wilson_confidence_interval as compute_wilson_ci

class PairedComparisonMetric(BaseModel):
    """Statistical summary of a paired comparison between two agent modes."""
    mode_a: str
    mode_b: str
    metric_name: str
    sample_size: int
    point_estimate_a: float
    point_estimate_b: float
    difference_pp: float
    bootstrap_ci_95: Optional[Tuple[float, float]] = None
    test_used: str
    p_value: Optional[float] = None
    statistically_significant: bool = False
    alpha: float = 0.05
    bonferroni_adjusted_alpha: Optional[float] = None
    discordant_pairs: Optional[Dict[str, int]] = None
    assumptions_met: bool = True
    interpretation_and_limitations: str

def exact_binomial_p_value(k: int, n: int, p: float = 0.5) -> float:
    """Computes exact two-sided binomial p-value for k successes in n Bernoulli trials."""
    if n == 0:
        return 1.0
    if k > n // 2:
        k = n - k  # symmetry around 0.5

    # Sum PMF from 0 to k
    cum_prob = 0.0
    for i in range(k + 1):
        coeff = math.comb(n, i)
        cum_prob += coeff * (p ** n)

    # Two-sided p-value
    p_val = min(1.0, 2.0 * cum_prob)
    return round(p_val, 5)

def chi2_sf_df1(chi2_val: float) -> float:
    """Survival function (p-value) for Chi-Square distribution with 1 degree of freedom."""
    if chi2_val <= 0.0:
        return 1.0
    # For df=1, chi2 = Z^2, so P(Chi2 >= x) = 2 * (1 - Phi(sqrt(x))) = erfc(sqrt(x)/sqrt(2))
    z = math.sqrt(chi2_val)
    p = math.erfc(z / math.sqrt(2))
    return round(max(0.0, min(1.0, p)), 5)

def compute_paired_bootstrap_ci(
    values_a: List[float],
    values_b: List[float],
    n_resamples: int = 1000,
    confidence_level: float = 0.95,
    random_seed: int = 42
) -> Tuple[float, float]:
    """Computes a paired bootstrap confidence interval for the mean difference (b - a)."""
    n = len(values_a)
    if n == 0 or len(values_b) != n:
        return (0.0, 0.0)
    if n < 3:
        diff = sum(values_b) / n - sum(values_a) / n
        return (round(diff, 2), round(diff, 2))

    rng = random.Random(random_seed)
    diffs = [b - a for a, b in zip(values_a, values_b)]
    bootstrap_means = []

    for _ in range(n_resamples):
        sample = [diffs[rng.randint(0, n - 1)] for _ in range(n)]
        bootstrap_means.append(sum(sample) / n)

    bootstrap_means.sort()
    alpha = (1.0 - confidence_level) / 2.0
    low_idx = int(math.floor(alpha * n_resamples))
    high_idx = int(math.ceil((1.0 - alpha) * n_resamples)) - 1
    low_idx = max(0, min(low_idx, n_resamples - 1))
    high_idx = max(0, min(high_idx, n_resamples - 1))

    return (round(bootstrap_means[low_idx], 2), round(bootstrap_means[high_idx], 2))

def perform_mcnemar_test(
    outcomes_a: List[int],
    outcomes_b: List[int],
    mode_a_name: str,
    mode_b_name: str,
    num_comparisons: int = 1,
    alpha: float = 0.05
) -> PairedComparisonMetric:
    """
    Performs a paired McNemar test on binary task success outcomes (1 = success, 0 = failure).
    Uses exact binomial test when discordant pairs (b + c) < 25, and asymptotic Chi2 test with
    continuity correction when discordant pairs >= 25.
    """
    n = len(outcomes_a)
    if n != len(outcomes_b) or n == 0:
        return PairedComparisonMetric(
            mode_a=mode_a_name,
            mode_b=mode_b_name,
            metric_name="task_success_rate",
            sample_size=n,
            point_estimate_a=0.0,
            point_estimate_b=0.0,
            difference_pp=0.0,
            test_used="None",
            p_value=None,
            statistically_significant=False,
            assumptions_met=False,
            interpretation_and_limitations="Insufficient or mismatched paired task sample size."
        )

    # Success rates
    rate_a = round((sum(outcomes_a) / n) * 100.0, 2)
    rate_b = round((sum(outcomes_b) / n) * 100.0, 2)
    diff_pp = round(rate_b - rate_a, 2)

    # 2x2 Contingency Table for Paired Binary Data
    # b: mode_a=1, mode_b=0 (mode_a succeeded, mode_b failed)
    # c: mode_a=0, mode_b=1 (mode_a failed, mode_b succeeded)
    b = sum(1 for a, b_val in zip(outcomes_a, outcomes_b) if a == 1 and b_val == 0)
    c = sum(1 for a, b_val in zip(outcomes_a, outcomes_b) if a == 0 and b_val == 1)
    discordant_total = b + c

    # Bootstrap 95% CI for difference in success percentage points
    # Converting binary 0/1 to percentages (0 or 100)
    vals_a = [float(val * 100) for val in outcomes_a]
    vals_b = [float(val * 100) for val in outcomes_b]
    boot_ci = compute_paired_bootstrap_ci(vals_a, vals_b)

    bonf_alpha = round(alpha / max(1, num_comparisons), 4)

    if discordant_total == 0:
        return PairedComparisonMetric(
            mode_a=mode_a_name,
            mode_b=mode_b_name,
            metric_name="task_success_rate",
            sample_size=n,
            point_estimate_a=rate_a,
            point_estimate_b=rate_b,
            difference_pp=diff_pp,
            bootstrap_ci_95=boot_ci,
            test_used="McNemar (Zero Discordant Pairs)",
            p_value=1.0,
            statistically_significant=False,
            alpha=alpha,
            bonferroni_adjusted_alpha=bonf_alpha,
            discordant_pairs={"a_only": b, "b_only": c, "total_discordant": 0},
            assumptions_met=True,
            interpretation_and_limitations=(
                f"Identical paired outcomes across all {n} tasks. Difference is exactly 0.0 pp. "
                "No evidence of differential performance."
            )
        )

    if discordant_total < 25:
        # Exact Binomial McNemar
        k = min(b, c)
        p_val = exact_binomial_p_value(k=k, n=discordant_total, p=0.5)
        test_name = f"Exact Binomial McNemar (discordant n={discordant_total} < 25)"
        assumptions = (n >= 10 and discordant_total >= 1)
        limitation_note = (
            "Small discordant sample size limits statistical power; non-significance does not prove equivalence."
            if discordant_total < 10 else "Exact distribution applied due to discordant count < 25."
        )
    else:
        # Asymptotic Chi-Square McNemar with Edwards continuity correction
        chi2 = ((abs(b - c) - 1.0) ** 2) / float(b + c)
        p_val = chi2_sf_df1(chi2)
        test_name = f"McNemar Chi-Square with continuity correction (discordant n={discordant_total} >= 25)"
        assumptions = True
        limitation_note = "Asymptotic Chi-Square assumptions satisfied."

    is_sig = p_val < bonf_alpha

    interp = (
        f"{mode_b_name} vs {mode_a_name}: diff = {diff_pp:+.2f} pp "
        f"(95% CI: [{boot_ci[0]:+.2f}, {boot_ci[1]:+.2f}] pp). "
        f"p-value = {p_val:.4f} (Bonferroni threshold = {bonf_alpha}). "
        f"Result is {'statistically significant' if is_sig else 'not statistically significant'}. "
        f"{limitation_note}"
    )

    return PairedComparisonMetric(
        mode_a=mode_a_name,
        mode_b=mode_b_name,
        metric_name="task_success_rate",
        sample_size=n,
        point_estimate_a=rate_a,
        point_estimate_b=rate_b,
        difference_pp=diff_pp,
        bootstrap_ci_95=boot_ci,
        test_used=test_name,
        p_value=p_val,
        statistically_significant=is_sig,
        alpha=alpha,
        bonferroni_adjusted_alpha=bonf_alpha,
        discordant_pairs={"a_only": b, "b_only": c, "total_discordant": discordant_total},
        assumptions_met=assumptions,
        interpretation_and_limitations=interp
    )

def perform_paired_latency_comparison(
    latencies_a: List[float],
    latencies_b: List[float],
    mode_a_name: str,
    mode_b_name: str
) -> PairedComparisonMetric:
    """Computes paired latency overhead differences and 95% bootstrap confidence intervals."""
    n = len(latencies_a)
    if n != len(latencies_b) or n == 0:
        return PairedComparisonMetric(
            mode_a=mode_a_name,
            mode_b=mode_b_name,
            metric_name="latency_ms",
            sample_size=n,
            point_estimate_a=0.0,
            point_estimate_b=0.0,
            difference_pp=0.0,
            test_used="None",
            interpretation_and_limitations="Insufficient paired latency samples."
        )

    mean_a = round(sum(latencies_a) / n, 2)
    mean_b = round(sum(latencies_b) / n, 2)
    diff = round(mean_b - mean_a, 2)
    boot_ci = compute_paired_bootstrap_ci(latencies_a, latencies_b)

    interp = (
        f"Mean latency: {mode_b_name} ({mean_b}ms) vs {mode_a_name} ({mean_a}ms). "
        f"Overhead: {diff:+.2f}ms (95% bootstrap CI: [{boot_ci[0]:+.2f}, {boot_ci[1]:+.2f}]ms)."
    )

    return PairedComparisonMetric(
        mode_a=mode_a_name,
        mode_b=mode_b_name,
        metric_name="mean_latency_ms",
        sample_size=n,
        point_estimate_a=mean_a,
        point_estimate_b=mean_b,
        difference_pp=diff,
        bootstrap_ci_95=boot_ci,
        test_used="Paired Bootstrap (1000 resamples)",
        p_value=None,
        statistically_significant=(boot_ci[0] > 0 or boot_ci[1] < 0),
        interpretation_and_limitations=interp
    )
