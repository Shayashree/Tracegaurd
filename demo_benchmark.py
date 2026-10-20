"""
TraceGuard Milestone 2 & 3 - Benchmark Execution and Trajectory Failure Diagnostics Demo Script.
Demonstrates running an evaluation experiment, extracting trajectory features,
diagnosing failure patterns, computing detector metrics, and printing the results.
"""
import json
import sys
from pathlib import Path
from backend.evaluation.benchmark_runner import BenchmarkRunner
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.detector_metrics import DetectorMetricsCalculator
from backend.evaluation.schemas import ExperimentRunRequest
from backend.reliability.failure_detector import TrajectoryFailureDetector
from backend.tracing.storage import TraceStorage

def run_demo():
    print("=" * 70)
    print(" TraceGuard Milestone 3: Trajectory Failure Detection Engine")
    print("=" * 70)

    # 1. Initialize dependencies
    db_path = "data/traceguard.db"
    storage = TraceStorage(db_path=db_path)
    dataset_loader = BenchmarkDatasetLoader()
    runner = BenchmarkRunner(
        dataset_loader=dataset_loader,
        storage=storage
    )
    detector = TrajectoryFailureDetector()

    # 2. Inspect available benchmarks
    benchmarks = dataset_loader.list_available_benchmarks()
    print("\n[1] Available Benchmark Datasets:")
    for b in benchmarks:
        print(f"  * Version: {b['benchmark_version']}, Tasks: {b['total_tasks']}, Categories: {b['categories']}")

    category = None if "--all" in sys.argv else ("failure_scenario" if "--category" not in sys.argv else sys.argv[sys.argv.index("--category") + 1])
    cat_label = category if category else "ALL CATEGORIES"
    print(f"\n[2] Executing Benchmark Run (Category: {cat_label})...")
    req = ExperimentRunRequest(
        benchmark_version="v1.0",
        category=category,
        agent_mode="baseline",
        repetitions=1,
        enable_failure_injection=True if category in (None, "failure_scenario") else False
    )

    summary = runner.run_experiment(req)
    exp_id = summary.experiment_id
    print(f"\n[3] Experiment Completed! Experiment ID: {exp_id} (Status: {summary.status})")

    # 4. Fetch metrics
    metrics = storage.get_experiment_metrics(exp_id)
    if metrics:
        m = metrics
        print("\n[4] Agent Experiment Metrics Summary:")
        print(f"  * Total Tasks Attempted:    {m.total_attempted}")
        print(f"  * Successful Tasks:         {m.successful_tasks}")
        ci_str = f"[{m.success_rate_ci.lower_bound:.1f}%, {m.success_rate_ci.upper_bound:.1f}%]" if m.success_rate_ci else "N/A"
        print(f"  * Success Rate:             {m.success_rate:.1f}% (Wilson 95% CI: {ci_str})")
        print(f"  * Verification Accuracy:    {m.verification_accuracy:.1f}%")
        print(f"  * Tool Calls:               {m.total_tool_calls} (Error Rate: {m.tool_error_rate:.1f}%)")
        print(f"  * Mean Duration:            {m.efficiency.mean_duration_ms:.2f} ms")

    # 5. Fetch diagnostic reports
    diag_reports = storage.get_diagnostics_for_experiment(exp_id)
    print(f"\n[5] Trajectory Failure Diagnostics ({len(diag_reports)} reports generated):")
    for d in diag_reports[:8]:
        cat_str = d.primary_failure_category.value if d.primary_failure_category else "none"
        findings_str = f"{len(d.findings)} finding(s)" if d.findings else "healthy"
        print(f"  * Task: {d.task_id:<12} | Status: {d.diagnostic_status.value:<16} | Category: {cat_str:<24} | Severity: {d.severity.value:<8} | Findings: {findings_str}")
        for f in d.findings[:2]:
            print(f"      -> [{f.rule_id}] {f.explanation}")

    # 6. Compute Detector Performance Metrics against ground-truth
    tasks = dataset_loader.load_tasks(version="v1.0")
    task_map = {t.task_id: t for t in tasks}
    evaluations = []
    results = storage.get_experiment_results(exp_id)
    for r in results:
        bench_task = task_map.get(r.task_id)
        gt_category = None
        if bench_task and bench_task.failure_scenario:
            gt_category = bench_task.failure_scenario.failure_type
        elif r.verification_status == "failed":
            gt_category = "incorrect_final_answer"
        elif r.terminal_status == "tool_error":
            gt_category = "tool_execution_failure"
        elif r.terminal_status == "step_limit_reached":
            gt_category = "step_limit_exhaustion"

        diag = storage.get_diagnostics_for_run(r.run_id)
        detected_cats = [f.failure_category.value for f in diag.findings] if diag else []
        evaluations.append({
            "expected_failure_category": gt_category,
            "detected_categories": detected_cats,
            "diagnostic_status": diag.diagnostic_status.value if diag else "healthy",
            "latency_ms": diag.analysis_duration_ms if diag else 0.0,
            "is_held_out": (BenchmarkDatasetLoader.get_task_split(r.task_id) == "test"),
        })

    det_metrics = DetectorMetricsCalculator.calculate_metrics(evaluations, detector_version=detector.config.detector_version)
    print("\n[6] Detector Evaluation Metrics:")
    print(f"  * Total Runs Evaluated:     {det_metrics.total_runs_evaluated}")
    print(f"  * Ground Truth Failures:    {det_metrics.total_failures_ground_truth}")
    print(f"  * Failures Detected:        {det_metrics.detected_failures_count}")
    print(f"  * Detection Coverage:       {det_metrics.detection_coverage:.1f}%")
    print(f"  * False Alarms:             {det_metrics.false_alarm_count}")
    print(f"  * Micro Precision:          {f'{det_metrics.micro_precision:.4f}' if det_metrics.micro_precision is not None else 'N/A'}")
    print(f"  * Micro Recall:             {f'{det_metrics.micro_recall:.4f}' if det_metrics.micro_recall is not None else 'N/A'}")
    print(f"  * Micro F1:                 {f'{det_metrics.micro_f1:.4f}' if det_metrics.micro_f1 is not None else 'N/A'}")
    print(f"  * Mean Detection Latency:   {det_metrics.mean_detection_latency_ms:.3f} ms")

    print("\n" + "=" * 70)
    print(" Trajectory Failure Diagnostics Demo Finished Successfully!")
    print("=" * 70)

if __name__ == "__main__":
    run_demo()
