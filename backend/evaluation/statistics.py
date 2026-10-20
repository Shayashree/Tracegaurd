"""Statistical calculations and confidence intervals for benchmark evaluation."""
import math
from typing import List, Optional, Tuple
from backend.evaluation.schemas import ConfidenceInterval

def calculate_wilson_confidence_interval(
    successes: int,
    total: int,
    confidence_level: float = 0.95
) -> ConfidenceInterval:
    """
    Computes the Wilson score interval for binomial proportion.
    Accurate for small sample sizes and extreme probabilities (0 or 1).
    """
    if total == 0:
        return ConfidenceInterval(
            point_estimate=0.0,
            lower_bound=0.0,
            upper_bound=0.0,
            confidence_level=confidence_level,
            sample_size=0,
            warning="Sample size is zero; confidence interval cannot be computed."
        )

    p_hat = successes / total

    # Standard normal quantile for common confidence levels
    if confidence_level == 0.90:
        z = 1.64485
    elif confidence_level == 0.99:
        z = 2.57583
    else:
        # Default 0.95
        z = 1.95996

    denominator = 1.0 + (z ** 2) / total
    centre_adjusted_probability = (p_hat + (z ** 2) / (2.0 * total)) / denominator
    adjusted_std_error = (
        z * math.sqrt((p_hat * (1.0 - p_hat) + (z ** 2) / (4.0 * total)) / total)
    ) / denominator

    lower = max(0.0, round((centre_adjusted_probability - adjusted_std_error) * 100, 2))
    upper = min(100.0, round((centre_adjusted_probability + adjusted_std_error) * 100, 2))
    point_est = round(p_hat * 100, 2)

    warning = None
    if total < 20:
        warning = f"Small sample size (n={total} < 20). Confidence interval is wide; interpret as preliminary evidence."
    elif successes == 0 or successes == total:
        warning = "Extreme proportion (0% or 100%); rule of three / Wilson score boundary applied."

    return ConfidenceInterval(
        point_estimate=point_est,
        lower_bound=lower,
        upper_bound=upper,
        confidence_level=confidence_level,
        method="Wilson score interval",
        sample_size=total,
        warning=warning
    )

def calculate_percentile(data: List[float], percentile: float) -> Optional[float]:
    """Calculate the p-th percentile using linear interpolation."""
    if not data:
        return None
    sorted_data = sorted(data)
    n = len(sorted_data)
    if n == 1:
        return round(sorted_data[0], 2)
    index = (percentile / 100.0) * (n - 1)
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    weight = index - lower
    val = sorted_data[lower] * (1.0 - weight) + sorted_data[upper] * weight
    return round(val, 2)

def calculate_mean_and_std(data: List[float]) -> Tuple[float, float]:
    """Compute arithmetic mean and sample standard deviation."""
    if not data:
        return 0.0, 0.0
    n = len(data)
    mean_val = sum(data) / n
    if n < 2:
        return round(mean_val, 2), 0.0
    variance = sum((x - mean_val) ** 2 for x in data) / (n - 1)
    std_val = math.sqrt(variance)
    return round(mean_val, 2), round(std_val, 2)
