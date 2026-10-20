"""
TraceGuard Milestone 2 - Benchmark Execution Demo Script.
Demonstrates running a baseline evaluation experiment across benchmark tasks,
computing metrics, and printing the results.
"""
import json
from pathlib import Path
from backend.evaluation.benchmark_runner import BenchmarkRunner
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.schemas import ExperimentRunRequest
from backend.tracing.storage import TraceStorage

def run_demo():
    print("=" * 70)
    print(" TraceGuard Milestone 2: Benchmark Evaluation Framework")
    print("=" * 70)

    # 1. Initialize dependencies
    db_path = "data/traceguard.db"
    storage = TraceStorage(db_path=db_path)
    dataset_loader = BenchmarkDatasetLoader()
    runner = BenchmarkRunner(
        dataset_loader=dataset_loader,
        storage=storage
    )

    # 2. Inspect available benchmarks
    benchmarks = dataset_loader.list_available_benchmarks()
    print("\n[1] Available Benchmark Datasets:")
    for b in benchmarks:
        print(f"  * Version: {b['benchmark_version']}, Tasks: {b['total_tasks']}, Categories: {b['categories']}")

    import sys
    category = None if "--all" in sys.argv else ("arithmetic" if "--category" not in sys.argv else sys.argv[sys.argv.index("--category") + 1])
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
        print("\n[4] Experiment Metrics Summary:")
        print(f"  * Total Tasks Attempted:    {m.total_attempted}")
        print(f"  * Successful Tasks:         {m.successful_tasks}")
        ci_str = f"[{m.success_rate_ci.lower_bound:.1f}%, {m.success_rate_ci.upper_bound:.1f}%]" if m.success_rate_ci else "N/A"
        print(f"  * Success Rate:             {m.success_rate:.1f}% (Wilson 95% CI: {ci_str})")
        print(f"  * Verification Accuracy:    {m.verification_accuracy:.1f}%")
        print(f"  * Tool Calls:               {m.total_tool_calls} (Error Rate: {m.tool_error_rate:.1f}%)")
        print(f"  * Mean Duration:            {m.efficiency.mean_duration_ms:.2f} ms")
        print(f"  * Median Duration:          {m.efficiency.median_duration_ms:.2f} ms")
        print(f"  * P95 Duration:             {m.efficiency.p95_duration_ms:.2f} ms")
        print(f"  * Mean Steps / Task:        {m.efficiency.mean_steps_per_task:.2f}")

    # 5. Fetch per-task results
    results = storage.get_experiment_results(exp_id)
    print(f"\n[5] Per-Task Results Sample ({len(results)} total):")
    for r in results:
        print(f"  * Task: {r.task_id:<12} | Status: {r.terminal_status:<14} | Verified: {str(r.verification_status):<8} | Duration: {r.total_duration_ms:.2f}ms | Trace: {r.trace_reference}")

    print("\n" + "=" * 70)
    print(" Benchmark Evaluation Demo Finished Successfully!")
    print("=" * 70)

if __name__ == "__main__":
    run_demo()
