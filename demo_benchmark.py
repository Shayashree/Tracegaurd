"""
TraceGuard Milestone 4 - Failure-Specific Recovery Engine and Comparative Experiment Demo.
Executes and compares baseline, fixed_retry, and traceguard_recovery on benchmark tasks,
demonstrating diagnosis-driven recovery, policy execution, post-recovery verification,
and comparative metrics.
"""
import json
import sys
from pathlib import Path
from backend.evaluation.benchmark_runner import BenchmarkRunner
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.recovery_metrics import (
    compute_comparative_metrics,
    compute_recovery_metrics,
)
from backend.evaluation.schemas import ExperimentRunRequest
from backend.tracing.storage import TraceStorage

def run_demo():
    print("=" * 76)
    print(" TraceGuard Milestone 4: Failure-Specific Recovery Engine & Comparative Demo")
    print("=" * 76)

    db_path = "data/traceguard.db"
    storage = TraceStorage(db_path=db_path)
    dataset_loader = BenchmarkDatasetLoader()
    runner = BenchmarkRunner(dataset_loader=dataset_loader, storage=storage)

    # Allow custom category filter or default to failure_scenario for clear recovery demonstration
    category = "failure_scenario" if "--all" not in sys.argv else None
    cat_label = category if category else "ALL 44 BENCHMARK TASKS"
    print(f"\n[1] Evaluating Modes Across Category: {cat_label}")

    modes = ["baseline", "fixed_retry", "traceguard_recovery"]
    summaries = {}
    recovery_metric_summaries = {}

    for mode in modes:
        print(f"\n---> Executing Mode: {mode.upper()}...")
        req = ExperimentRunRequest(
            benchmark_version="v1.0",
            category=category,
            agent_mode=mode,
            repetitions=1,
            enable_failure_injection=True,
        )
        summary = runner.run_experiment(req)
        summaries[mode] = summary

        # Compute recovery metrics
        reports = storage.get_recovery_reports_for_experiment(summary.experiment_id)
        results = storage.get_experiment_results(summary.experiment_id)
        rec_m = compute_recovery_metrics(
            recovery_reports=reports,
            agent_mode=mode,
            total_attempted_override=summary.total_tasks,
            experiment_results=results,
        )
        recovery_metric_summaries[mode] = rec_m

        metrics = storage.get_experiment_metrics(summary.experiment_id)
        sr = metrics.success_rate if metrics else 0.0
        ci_str = f"[{metrics.success_rate_ci.lower_bound:.1f}%, {metrics.success_rate_ci.upper_bound:.1f}%]" if metrics and metrics.success_rate_ci else "N/A"
        print(f"     Success Rate: {sr:.1f}% (Wilson 95% CI: {ci_str}) | Mean Latency: {metrics.efficiency.mean_duration_ms:.1f}ms")

    # [2] Comparative Analysis
    base_m = recovery_metric_summaries["baseline"]
    fixed_m = recovery_metric_summaries["fixed_retry"]
    tg_m = recovery_metric_summaries["traceguard_recovery"]
    comp = compute_comparative_metrics(base_m, fixed_m, tg_m)

    print("\n" + "=" * 76)
    print(" [2] COMPARATIVE RELIABILITY & EFFICIENCY SUMMARY")
    print("=" * 76)
    print(f"  Mode                  | Success Rate | Eligible Recov SR | Recov Attempts | Mean Latency")
    print(f"  ----------------------+--------------+-------------------+----------------+-------------")
    print(f"  baseline              | {base_m.end_to_end_success_rate:>10.1f}% | {base_m.recovery_success_rate_eligible:>15.1f}% | {base_m.recovery_interventions_initiated:>14} | {base_m.efficiency.mean_total_latency_ms:>9.1f}ms")
    print(f"  fixed_retry           | {fixed_m.end_to_end_success_rate:>10.1f}% | {fixed_m.recovery_success_rate_eligible:>15.1f}% | {fixed_m.recovery_interventions_initiated:>14} | {fixed_m.efficiency.mean_total_latency_ms:>9.1f}ms")
    print(f"  traceguard_recovery   | {tg_m.end_to_end_success_rate:>10.1f}% | {tg_m.recovery_success_rate_eligible:>15.1f}% | {tg_m.recovery_interventions_initiated:>14} | {tg_m.efficiency.mean_total_latency_ms:>9.1f}ms")

    print("\n  Comparative Deltas:")
    print(f"  * Fixed Retry vs Baseline:        {comp.delta_fixed_retry_vs_baseline_pp:+.1f} pp (Relative Gain: {comp.relative_gain_fixed_retry_pct or 0.0:+.1f}%) | Latency: +{comp.latency_overhead_fixed_retry_ms:.1f}ms")
    print(f"  * TraceGuard vs Baseline:         {comp.delta_traceguard_vs_baseline_pp:+.1f} pp (Relative Gain: {comp.relative_gain_traceguard_pct or 0.0:+.1f}%) | Latency: +{comp.latency_overhead_traceguard_ms:.1f}ms")
    print(f"  * TraceGuard vs Fixed Retry:      {comp.delta_traceguard_vs_fixed_retry_pp:+.1f} pp (Relative Gain: {comp.relative_gain_traceguard_vs_fixed_pct or 0.0:+.1f}%)")

    # [3] Detailed Sample Recovery Trajectory Walkthrough
    tg_exp_id = summaries["traceguard_recovery"].experiment_id
    reports = storage.get_recovery_reports_for_experiment(tg_exp_id)
    recovered_samples = [r for r in reports if r.terminal_status.value == "recovered_successfully"]
    sample = recovered_samples[0] if recovered_samples else (reports[0] if reports else None)

    if sample:
        print("\n" + "=" * 76)
        print(" [3] REPRODUCIBLE RECOVERY TRAJECTORY SAMPLE")
        print("=" * 76)
        print(f"  * Task ID:             {sample.task_id}")
        print(f"  * Initial Status:      {sample.original_status} (Verification: {sample.original_verification_status})")
        print(f"  * Diagnosed Category:  {sample.initial_failure_category}")
        print(f"  * Selected Policy:     {sample.policy_id}")
        print(f"  * Selection Reason:    {sample.selection_reason}")
        print(f"  * Terminal Status:     {sample.terminal_status.value}")
        print(f"  * Final Answer:        {sample.final_answer}")
        print(f"  * Post-Recovery Verif: {sample.final_verification_status}")
        print(f"  * Recovery Overhead:   +{sample.total_recovery_duration_ms:.1f}ms | +{sample.additional_tool_calls} tool call(s) | +{sample.budget_usage.steps} step(s)")

    print("\n" + "=" * 76)
    print(" Milestone 4 Demonstration Completed Successfully!")
    print("=" * 76)

if __name__ == "__main__":
    run_demo()
