"""Unit tests for EvaluationMetrics and statistical calculations."""
import pytest
from backend.evaluation.metrics import compute_experiment_metrics
from backend.evaluation.schemas import TaskExecutionResult
from backend.evaluation.statistics import (
    calculate_mean_and_std,
    calculate_percentile,
    calculate_wilson_confidence_interval,
)

def test_wilson_confidence_interval_math():
    # 80 successes out of 100
    ci = calculate_wilson_confidence_interval(80, 100, confidence_level=0.95)
    assert ci.point_estimate == 80.0
    # Wilson interval for 80/100 is approx [71.15, 86.66]
    assert 70.0 <= ci.lower_bound <= 73.0
    assert 85.0 <= ci.upper_bound <= 88.0
    assert ci.sample_size == 100
    assert ci.warning is None

def test_wilson_confidence_interval_small_sample():
    ci = calculate_wilson_confidence_interval(4, 5)
    assert ci.point_estimate == 80.0
    assert ci.warning is not None
    assert "Small sample size" in ci.warning

def test_wilson_confidence_interval_zero_denominator():
    ci = calculate_wilson_confidence_interval(0, 0)
    assert ci.point_estimate == 0.0
    assert ci.lower_bound == 0.0
    assert ci.upper_bound == 0.0
    assert "Sample size is zero" in ci.warning

def test_percentile_calculation():
    data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    p50 = calculate_percentile(data, 50.0)
    p95 = calculate_percentile(data, 95.0)
    assert p50 == 55.0
    assert p95 == 95.5

def test_mean_and_std():
    mean, std = calculate_mean_and_std([10.0, 20.0, 30.0])
    assert mean == 20.0
    assert std == 10.0

    mean_empty, std_empty = calculate_mean_and_std([])
    assert mean_empty == 0.0
    assert std_empty == 0.0

def test_metrics_calculation_known_values():
    results = [
        TaskExecutionResult(
            experiment_id="exp_test",
            task_id="T1",
            run_id="R1",
            benchmark_version="v1.0",
            agent_mode="baseline",
            started_at="2026-10-20T10:00:00Z",
            completed_at="2026-10-20T10:00:01Z",
            terminal_status="successful_completion",
            expected_answer=10,
            observed_answer="10",
            verification_status="verified",
            verification_message="OK",
            step_count=2,
            tool_call_count=2,
            tool_error_count=0,
            total_duration_ms=100.0,
            model_tokens={"total_tokens": 50},
        ),
        TaskExecutionResult(
            experiment_id="exp_test",
            task_id="T2",
            run_id="R2",
            benchmark_version="v1.0",
            agent_mode="baseline",
            started_at="2026-10-20T10:00:00Z",
            completed_at="2026-10-20T10:00:01Z",
            terminal_status="incorrect_answer",
            expected_answer=20,
            observed_answer="99",
            verification_status="failed",
            verification_message="Wrong",
            step_count=2,
            tool_call_count=1,
            tool_error_count=0,
            total_duration_ms=200.0,
            model_tokens={"total_tokens": 50},
        ),
        TaskExecutionResult(
            experiment_id="exp_test",
            task_id="T3",
            run_id="R3",
            benchmark_version="v1.0",
            agent_mode="baseline",
            started_at="2026-10-20T10:00:00Z",
            completed_at="2026-10-20T10:00:01Z",
            terminal_status="tool_error",
            expected_answer=None,
            observed_answer=None,
            verification_status="not_applicable",
            verification_message="None",
            step_count=1,
            tool_call_count=1,
            tool_error_count=1,
            total_duration_ms=300.0,
            model_tokens={"total_tokens": 50},
        ),
        TaskExecutionResult(
            experiment_id="exp_test",
            task_id="T4",
            run_id="R4",
            benchmark_version="v1.0",
            agent_mode="baseline",
            started_at="2026-10-20T10:00:00Z",
            completed_at="2026-10-20T10:00:01Z",
            terminal_status="step_limit_exhaustion",
            expected_answer=None,
            observed_answer=None,
            verification_status="not_applicable",
            verification_message="None",
            step_count=8,
            tool_call_count=4,
            tool_error_count=0,
            total_duration_ms=400.0,
            model_tokens={"total_tokens": 50},
        ),
    ]

    metrics = compute_experiment_metrics(
        results=results,
        experiment_id="exp_test",
        benchmark_version="v1.0",
        agent_mode="baseline",
        repetitions=1
    )

    # 1 of 4 is successful -> 25%
    assert metrics.total_attempted == 4
    assert metrics.successful_tasks == 1
    assert metrics.success_rate == 25.0

    # Verification accuracy: T1 verified, T2 failed -> 1 of 2 -> 50%
    assert metrics.verification_denominator == 2
    assert metrics.verification_accuracy == 50.0

    # Tool error rate: 1 failed out of (2 + 1 + 1 + 4 = 8) -> 12.5%
    assert metrics.total_tool_calls == 8
    assert metrics.failed_tool_calls == 1
    assert metrics.tool_error_rate == 12.5

    # Failure distribution
    assert metrics.failure_distribution.incorrect_answers == 1
    assert metrics.failure_distribution.tool_errors == 1
    assert metrics.failure_distribution.step_limit_exhaustion == 1

    # Efficiency
    assert metrics.efficiency.mean_duration_ms == 250.0
    assert metrics.efficiency.median_duration_ms == 250.0
    assert metrics.efficiency.mean_steps_per_task == 3.25
    assert metrics.efficiency.mean_tool_calls_per_task == 2.0
    assert metrics.efficiency.total_tokens == 200

def test_metrics_zero_denominators():
    metrics = compute_experiment_metrics(
        results=[],
        experiment_id="exp_empty",
        benchmark_version="v1.0",
        agent_mode="baseline"
    )
    assert metrics.total_attempted == 0
    assert metrics.success_rate == 0.0
    assert metrics.verification_accuracy == 0.0
    assert metrics.tool_error_rate == 0.0
    assert metrics.efficiency.mean_duration_ms == 0.0
