"""CLI entrypoint for running TraceGuard Milestone 5 experimental evaluations.
Executes reproducible benchmarks, statistical comparisons, ablation studies, and generates research reports.
"""
import argparse
import json
from pathlib import Path
import sys

from backend.evaluation.experiment_config import ExperimentConfig
from backend.evaluation.experiment_runner import FullExperimentRunner
from backend.tracing.storage import TraceStorage

def parse_args():
    parser = argparse.ArgumentParser(description="TraceGuard Milestone 5: Research Experiment Runner")
    parser.add_argument(
        "--type",
        choices=["standard", "controlled_failure", "held_out", "repeated_stability", "ablation"],
        default="standard",
        help="Experiment protocol type"
    )
    parser.add_argument(
        "--split",
        choices=["all", "train", "val", "test", "held_out"],
        default="all",
        help="Dataset split to evaluate"
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Filter by specific benchmark category"
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["baseline", "fixed_retry", "traceguard_recovery"],
        help="Agent execution modes to run and compare"
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Repetitions per task"
    )
    parser.add_argument(
        "--out",
        type=str,
        default="data/experiments",
        help="Directory to save generated research report and manifest"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    print("=" * 78)
    print(" TraceGuard Milestone 5: Experimental Evaluation & Research Platform")
    print("=" * 78)

    db_path = "data/traceguard.db"
    storage = TraceStorage(db_path=db_path)
    runner = FullExperimentRunner(storage=storage)

    modes = args.modes
    if args.type == "ablation":
        modes = ["baseline", "detection_only", "fixed_retry", "traceguard_recovery"]

    config = ExperimentConfig(
        experiment_type=args.type,
        dataset_split=args.split,
        category=args.category,
        agent_modes=modes,
        repetitions=args.repetitions,
    )

    print(f"\n[1] Starting Experiment: {config.experiment_id}")
    print(f"    * Experiment Type:      {config.experiment_type}")
    print(f"    * Dataset Split:        {config.dataset_split}")
    print(f"    * Category Filter:      {config.category or 'ALL'}")
    print(f"    * Agent Modes:          {', '.join(config.agent_modes)}")
    print(f"    * Configuration Hash:   {config.configuration_hash}")

    summary = runner.run_experiment(config)

    print("\n" + "=" * 78)
    print(" [2] COMPARATIVE RELIABILITY & EFFICIENCY RESULTS")
    print("=" * 78)
    print(f"  Agent Mode          | Success Rate | Interventions | Mean Latency | Mean Add'l Latency")
    print(f"  --------------------+--------------+---------------+--------------+-------------------")
    for mode in config.agent_modes:
        m = summary.mode_metrics.get(mode)
        if m:
            print(
                f"  {mode:<19} | {m.end_to_end_success_rate:>10.1f}% | "
                f"{m.recovery_interventions_initiated:>13} | "
                f"{m.efficiency.mean_total_latency_ms:>10.1f}ms | "
                f"+{m.efficiency.mean_additional_recovery_latency_ms:>15.1f}ms"
            )

    if summary.comparative_metrics:
        comp = summary.comparative_metrics
        print("\n  Comparative Differences:")
        print(f"  * Fixed Retry vs Baseline:   {comp.delta_fixed_retry_vs_baseline_pp:+.2f} pp (Latency: {comp.latency_overhead_fixed_retry_ms:+.1f}ms)")
        print(f"  * TraceGuard vs Baseline:    {comp.delta_traceguard_vs_baseline_pp:+.2f} pp (Latency: {comp.latency_overhead_traceguard_ms:+.1f}ms)")
        print(f"  * TraceGuard vs Fixed Retry: {comp.delta_traceguard_vs_fixed_retry_pp:+.2f} pp")

    if summary.statistical_comparisons:
        print("\n" + "=" * 78)
        print(" [3] PAIRED STATISTICAL HYPOTHESIS TESTING (McNemar & Paired Bootstrap)")
        print("=" * 78)
        for stat in summary.statistical_comparisons:
            p_val_str = f"p = {stat.p_value:.4f}" if stat.p_value is not None else "p = N/A"
            sig_str = "SIGNIFICANT" if stat.statistically_significant else "NOT SIGNIFICANT"
            print(f"  * {stat.mode_b} vs {stat.mode_a} [{stat.metric_name}]:")
            print(f"    Delta: {stat.difference_pp:+.2f} | 95% CI: {stat.bootstrap_ci_95} | {stat.test_used}")
            print(f"    {p_val_str} | Result: {sig_str}")
            print(f"    Interpretation: {stat.interpretation_and_limitations}")

    if summary.ablation_results and summary.ablation_results.contributions:
        print("\n" + "=" * 78)
        print(" [4] COMPONENT ABLATION STUDY RESULTS")
        print("=" * 78)
        for contrib in summary.ablation_results.contributions:
            print(f"  * {contrib.component_name}:")
            print(f"    Delta Success Rate: {contrib.delta_success_rate_pp:+.2f} pp | Delta Latency: {contrib.delta_latency_ms:+.2f}ms")
            print(f"    Assessment: {contrib.assessment}")

    if summary.failure_analysis and summary.failure_analysis.categories:
        print("\n" + "=" * 78)
        print(" [5] FAILURE-SPECIFIC CATEGORY BREAKDOWN")
        print("=" * 78)
        print(f"  Category / Failure Mode        | Tasks | Failures | Recov Success Rate | Assessment")
        print(f"  -------------------------------+-------+----------+--------------------+-------------")
        for cat_name, cat_m in summary.failure_analysis.categories.items():
            print(
                f"  {cat_name:<30} | {cat_m.total_tasks:>5} | {cat_m.actual_failures:>8} | "
                f"{cat_m.recovery_success_rate:>16.1f}% | {cat_m.assessment.upper():<11}"
            )

    # Save report and manifest to disk
    out_dir = Path(args.out) / config.experiment_id
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = out_dir / "research_report.md"
    if summary.report_markdown:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(summary.report_markdown)

    manifest_path = out_dir / "reproducibility_manifest.json"
    if summary.manifest:
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write(summary.manifest.model_dump_json(indent=2))

    print("\n" + "=" * 78)
    print(" [6] ARTIFACTS PERSISTED")
    print("=" * 78)
    print(f"  * Research Report:        {report_path}")
    print(f"  * Reproducibility Manifest: {manifest_path}")
    print(f"  * SQLite Database:         {db_path}")
    print("=" * 78)
    print(" Milestone 5 Experiment Completed Successfully!")
    print("=" * 78)

if __name__ == "__main__":
    main()
