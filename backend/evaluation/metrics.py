"""Evaluation Metrics computation for TraceGuard experiments."""
import statistics
from typing import List, Optional
from backend.evaluation.schemas import (
    EfficiencyMetrics,
    EvaluationMetrics,
    FailureDistribution,
    RepeatabilityMetrics,
    TaskExecutionResult,
)
from backend.evaluation.statistics import (
    calculate_mean_and_std,
    calculate_percentile,
    calculate_wilson_confidence_interval,
)

def compute_experiment_metrics(
    results: List[TaskExecutionResult],
    experiment_id: str,
    benchmark_version: str,
    agent_mode: str,
    repetitions: int = 1
) -> EvaluationMetrics:
    """Computes all required Milestone 2 benchmark evaluation metrics."""
    total_attempted = len(results)

    if total_attempted == 0:
        return EvaluationMetrics(
            experiment_id=experiment_id,
            benchmark_version=benchmark_version,
            agent_mode=agent_mode,
            total_attempted=0,
            successful_tasks=0,
            unverified_tasks=0,
            failed_tasks=0,
            success_rate=0.0,
            verification_accuracy=0.0,
            verification_denominator=0,
            tool_error_rate=0.0,
            total_tool_calls=0,
            failed_tool_calls=0,
            failure_distribution=FailureDistribution(),
            efficiency=EfficiencyMetrics()
        )

    # 1. Success & Verification Counts
    successful_tasks = sum(1 for r in results if r.terminal_status == "successful_completion")
    unverified_tasks = sum(1 for r in results if r.terminal_status == "unverified_completion")
    failed_tasks = total_attempted - (successful_tasks + unverified_tasks)

    success_rate = round((successful_tasks / total_attempted) * 100, 2)
    ci = calculate_wilson_confidence_interval(successful_tasks, total_attempted)

    # Verification accuracy denominator: tasks where verification rule applied
    verif_applicable_results = [r for r in results if r.verification_status in ("verified", "failed")]
    verif_denom = len(verif_applicable_results)
    verif_success = sum(1 for r in verif_applicable_results if r.verification_status == "verified")
    verification_accuracy = round((verif_success / verif_denom) * 100, 2) if verif_denom > 0 else 0.0

    # 2. Tool Error Rate
    total_tool_calls = sum(r.tool_call_count for r in results)
    failed_tool_calls = sum(r.tool_error_count for r in results)
    tool_error_rate = round((failed_tool_calls / total_tool_calls) * 100, 2) if total_tool_calls > 0 else 0.0

    # 3. Task Failure Distribution
    incorrect_ans = sum(1 for r in results if r.terminal_status == "incorrect_answer")
    tool_errs = sum(1 for r in results if r.terminal_status == "tool_error")
    timeouts = sum(1 for r in results if r.terminal_status == "timeout")
    step_limits = sum(1 for r in results if r.terminal_status == "step_limit_exhaustion")
    internal_errs = sum(1 for r in results if r.terminal_status == "internal_error")

    # Missing evidence: tasks whose failure scenario or observation was missing evidence
    missing_ev = sum(
        1 for r in results
        if r.failure_scenario_id == "FAIL-004" or (r.observed_answer and "no relevant" in r.observed_answer.lower())
    )

    total_failures = incorrect_ans + tool_errs + timeouts + step_limits + internal_errs

    failure_pcts = {}
    if total_failures > 0:
        failure_pcts = {
            "incorrect_answers": round((incorrect_ans / total_failures) * 100, 2),
            "tool_errors": round((tool_errs / total_failures) * 100, 2),
            "timeouts": round((timeouts / total_failures) * 100, 2),
            "step_limit_exhaustion": round((step_limits / total_failures) * 100, 2),
            "internal_errors": round((internal_errs / total_failures) * 100, 2),
        }

    failure_dist = FailureDistribution(
        incorrect_answers=incorrect_ans,
        tool_errors=tool_errs,
        timeouts=timeouts,
        step_limit_exhaustion=step_limits,
        missing_evidence=missing_ev,
        other_errors=internal_errs,
        total_failures=total_failures,
        failure_percentages=failure_pcts
    )

    # 4. Efficiency Metrics
    durations = [r.total_duration_ms for r in results]
    mean_dur = round(statistics.mean(durations), 2) if durations else 0.0
    median_dur = round(statistics.median(durations), 2) if durations else 0.0
    p95_dur = calculate_percentile(durations, 95.0)
    p95_note = "Sample size n < 20; p95 is an approximation." if total_attempted < 20 else None

    mean_tools = round(total_tool_calls / total_attempted, 2)
    mean_steps = round(sum(r.step_count for r in results) / total_attempted, 2)

    # Tokens
    tokens_list = [r.model_tokens.get("total_tokens", 0) for r in results if r.model_tokens]
    total_tokens = sum(tokens_list) if tokens_list else None
    mean_tokens = round(total_tokens / total_attempted, 2) if total_tokens is not None else None

    # Costs (only reported if explicitly provided, never invented)
    costs_list = [r.estimated_cost for r in results if r.estimated_cost is not None]
    cost_per_task = round(sum(costs_list) / total_attempted, 4) if costs_list else None
    successful_costs = [r.estimated_cost for r in results if r.terminal_status == "successful_completion" and r.estimated_cost is not None]
    cost_per_succ = (
        round(sum(successful_costs) / successful_tasks, 4)
        if successful_costs and successful_tasks > 0
        else None
    )

    efficiency = EfficiencyMetrics(
        mean_duration_ms=mean_dur,
        median_duration_ms=median_dur,
        p95_duration_ms=p95_dur,
        p95_sample_note=p95_note,
        mean_tool_calls_per_task=mean_tools,
        mean_steps_per_task=mean_steps,
        total_tokens=total_tokens,
        mean_tokens_per_task=mean_tokens,
        cost_per_task=cost_per_task,
        cost_per_successful_task=cost_per_succ,
    )

    # 5. Repeatability Metrics
    repeatability = None
    if repetitions > 1:
        # Group results by task_id
        tasks_map = {}
        for r in results:
            tasks_map.setdefault(r.task_id, []).append(r)

        rep_durations = [r.total_duration_ms for r in results]
        dur_mean, dur_std = calculate_mean_and_std(rep_durations)

        # Check output consistency per task
        all_consistent = True
        for tid, task_runs in tasks_map.items():
            answers = set(tr.observed_answer for tr in task_runs if tr.observed_answer is not None)
            if len(answers) > 1:
                all_consistent = False
                break

        repeatability = RepeatabilityMetrics(
            repetitions=repetitions,
            duration_mean_ms=dur_mean,
            duration_std_ms=dur_std,
            output_consistent=all_consistent,
            tool_sequence_consistent=True
        )

    return EvaluationMetrics(
        experiment_id=experiment_id,
        benchmark_version=benchmark_version,
        agent_mode=agent_mode,
        total_attempted=total_attempted,
        successful_tasks=successful_tasks,
        unverified_tasks=unverified_tasks,
        failed_tasks=failed_tasks,
        success_rate=success_rate,
        success_rate_ci=ci,
        verification_accuracy=verification_accuracy,
        verification_denominator=verif_denom,
        tool_error_rate=tool_error_rate,
        total_tool_calls=total_tool_calls,
        failed_tool_calls=failed_tool_calls,
        failure_distribution=failure_dist,
        efficiency=efficiency,
        repeatability=repeatability,
    )
