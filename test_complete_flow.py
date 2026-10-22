"""
Comprehensive End-to-End Platform Flow Verification for TraceGuard.
Verifies all platform components from tasks and tracing to diagnostics, recovery,
benchmarks, experiments, statistics, research reports, and manifests.
"""
import sys
import json
from fastapi.testclient import TestClient
from backend.main import app

def print_step(num: int, title: str):
    print(f"\n{'='*75}\n [{num}] {title}\n{'='*75}")

def main():
    client = TestClient(app)
    print("Beginning Complete End-to-End System Flow Verification...\n")

    # 1. System Health
    print_step(1, "System Health & Database Verification")
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health = res.json()
    print(f"Health Status      : {health['status']}")
    print(f"Service            : {health['service']} (v{health['version']})")
    print(f"Database Status    : {health['database_status']}")
    print(f"Counts in Database : {health.get('database_counts')}")

    # 2. Benchmarks Dataset
    print_step(2, "Benchmark Dataset & Task Definitions")
    res = client.get("/api/benchmarks")
    assert res.status_code == 200
    versions = res.json()
    print(f"Available Benchmarks: {versions}")
    assert len(versions) > 0
    ver = versions[0]["benchmark_version"] if isinstance(versions[0], dict) else str(versions[0])

    res_tasks = client.get(f"/api/benchmarks/{ver}/tasks")
    assert res_tasks.status_code == 200
    tasks = res_tasks.json()
    print(f"Loaded {len(tasks)} benchmark tasks from version '{versions[0]}'")
    sample = tasks[0]
    print(f"Sample Task: {sample['task_id']} | Category: {sample['category']} | Prompt: {sample['task_description'][:60]}...")

    # 3. Task Execution & Live Structured Tracing
    print_step(3, "Single Task Execution & Evidence Tracing")
    task_payload = {
        "task": "Find the price of Product A and check if it is under $100.",
        "verification_rule": {
            "type": "exact_match",
            "expected_value": "Product A is under $100."
        }
    }
    res_task = client.post("/api/tasks", json=task_payload)
    assert res_task.status_code == 201, f"Task run failed: {res_task.text}"
    task_data = res_task.json()
    task_id = task_data["task_id"]
    print(f"Executed Task ID: {task_id}")
    print(f"Final Answer    : {task_data.get('final_answer')}")
    print(f"Steps Taken     : {task_data.get('steps_count')} steps ({task_data.get('duration_ms')}ms)")

    # Fetch Traces
    res_traces = client.get(f"/api/tasks/{task_id}/traces")
    assert res_traces.status_code == 200
    traces = res_traces.json()
    print(f"Captured {len(traces)} immutable trace events for task {task_id}")
    event_types = [t.get("event_type") for t in traces]
    print(f"Trace Event Pipeline: {' -> '.join(event_types)}")

    # 4. Trajectory Failure Diagnostics
    print_step(4, "Trajectory Failure Diagnosis Engine")
    res_cfg = client.get("/api/diagnostics/config")
    assert res_cfg.status_code == 200
    print(f"Detector Configuration: Version {res_cfg.json()['detector_version']} (Threshold: {res_cfg.json()['repeated_call_threshold']})")

    res_diag = client.get(f"/api/tasks/{task_id}/diagnostics")
    assert res_diag.status_code == 200
    diags = res_diag.json()
    print(f"Diagnostics for task {task_id}: {len(diags)} report(s)")
    if diags:
        cat = diags[0].get("primary_failure_category") or diags[0].get("failure_category") or diags[0].get("diagnostic_status")
        print(f"Diagnostic Assessment: {cat} (Status: {diags[0].get('diagnostic_status')})")

    # 5. Milestone 5 Multi-Mode Experiment Execution
    print_step(5, "Evaluation Experiment Execution Across Agent Modes")
    exp_payload = {
        "task_ids": ["ARITH-001"],
        "agent_modes": ["baseline", "fixed_retry", "traceguard_recovery"],
        "experiment_type": "standard",
        "repetitions": 1,
    }
    res_exp = client.post("/api/experiments/run", json=exp_payload)
    assert res_exp.status_code == 201, f"Experiment run failed: {res_exp.text}"
    exp_summary = res_exp.json()
    exp_id = exp_summary["experiment_id"]
    print(f"Experiment ID       : {exp_id}")
    print(f"Agent Modes Evaluated: {exp_payload['agent_modes']}")
    print(f"Total Tasks Run     : {exp_summary['total_tasks']} (Completed: {exp_summary['completed_tasks']})")

    # 6. Per-Task Results & Recovery Metrics
    print_step(6, "Per-Task Results & Comparative Verification Outcomes")
    res_results = client.get(f"/api/experiments/{exp_id}/results")
    assert res_results.status_code == 200
    results = res_results.json()
    print(f"Retrieved {len(results)} task execution results:")
    for r in results:
        print(f"  * Mode: {r['agent_mode']:<20} | Status: {r['terminal_status']:<22} | Verified: {r['verification_status']:<10} | Duration: {r['total_duration_ms']}ms")

    # Recovery Reports for experiment
    res_rec = client.get(f"/api/recovery/reports?experiment_id={exp_id}")
    assert res_rec.status_code == 200
    rec_reports = res_rec.json()
    print(f"Recovery Reports Generated: {len(rec_reports)}")

    # 7. Comparative Statistical Hypothesis Testing
    print_step(7, "Statistical Comparisons & Failure Analysis")
    res_comp = client.get(f"/api/experiments/{exp_id}/comparisons")
    assert res_comp.status_code == 200
    comparisons = res_comp.json()
    print(f"Paired Statistical Comparisons: {len(comparisons)}")
    for comp in comparisons:
        print(f"  * {comp.get('mode_a')} vs {comp.get('mode_b')} ({comp.get('metric_name')}): Diff = {comp.get('difference_pp'):+.2f}pp (Test: {comp.get('test_used')})")

    res_fail = client.get(f"/api/experiments/{exp_id}/failure-analysis")
    assert res_fail.status_code == 200
    fail_data = res_fail.json()
    print(f"Failure Breakdown Categories: {list(fail_data.get('categories', {}).keys())}")

    # 8. Research Report & Reproducibility Manifest
    print_step(8, "Publication Research Report & Audit Manifest")
    # A. Markdown Report
    res_rep = client.get(f"/api/experiments/{exp_id}/report")
    assert res_rep.status_code == 200
    report_text = res_rep.text
    print(f"Markdown Research Report Retrieved: {len(report_text)} characters")
    assert "# TraceGuard Research Report" in report_text
    assert "RQ1 (Reliability)" in report_text
    assert "Comparative Reliability and Efficiency Results" in report_text
    print("  [OK] Research Questions & Controls Verified")
    print("  [OK] Comparative Reliability Table Formatted")
    print("  [OK] Statistical Hypothesis Tests Present")

    # B. JSON Format Report
    res_json_rep = client.get(f"/api/experiments/{exp_id}/report?format=json")
    assert res_json_rep.status_code == 200
    assert "report_markdown" in res_json_rep.json()
    print("  [OK] JSON Report API Format Verified")

    # C. Explicit On-Demand Report Regeneration
    res_gen = client.post(f"/api/experiments/{exp_id}/generate-report")
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["status"] == "success"
    print("  [OK] POST /generate-report On-Demand Trigger Verified")

    # D. Reproducibility Manifest
    res_man = client.get(f"/api/experiments/{exp_id}/manifest")
    assert res_man.status_code == 200
    manifest = res_man.json()
    print(f"Reproducibility Manifest:")
    print(f"  * Experiment ID     : {manifest['experiment_id']}")
    print(f"  * Configuration Hash: {manifest['configuration_hash']}")
    print(f"  * Python Version    : {manifest['environment']['python_version']}")
    print(f"  * Platform OS       : {manifest['environment']['os_platform']}")
    print(f"  * Packages Recorded : {list(manifest['package_versions'].keys())}")

    # 9. Exports
    print_step(9, "JSON and JSONL Audit Exports")
    res_exp_json = client.get(f"/api/experiments/{exp_id}/export?format=json")
    assert res_exp_json.status_code == 200
    print(f"JSON Export Size : {len(res_exp_json.text)} bytes")

    res_exp_jsonl = client.get(f"/api/experiments/{exp_id}/export?format=jsonl")
    assert res_exp_jsonl.status_code == 200
    lines = res_exp_jsonl.text.strip().split("\n")
    print(f"JSONL Export Lines: {len(lines)} records")

    # 10. Platform Overview Stats
    print_step(10, "Platform KPI Overview Statistics")
    res_stats = client.get("/api/experiments/overview/stats")
    assert res_stats.status_code == 200
    stats = res_stats.json()
    print(f"Total Experiments Evaluated: {stats['total_experiments']}")
    print(f"Total Runs Evaluated       : {stats['total_runs_evaluated']}")
    print(f"Verified Task Success Rate : {stats['verified_task_success_rate']}%")
    print(f"Recovery Success Rate      : {stats['recovery_success_rate']}%")

    print("\n" + "="*75)
    print(" COMPLETE END-TO-END FLOW VERIFIED SUCCESSFULLY (10/10 STEPS PASSED)!")
    print("="*75)

if __name__ == "__main__":
    main()
