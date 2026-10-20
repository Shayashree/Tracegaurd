"""Experiment execution, result retrieval, and export API endpoints for TraceGuard."""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from backend.api.tasks import get_storage
from backend.evaluation.benchmark_runner import BenchmarkRunner
from backend.evaluation.experiment_config import ExperimentConfig
from backend.evaluation.experiment_runner import FullExperimentRunner
from backend.evaluation.recovery_metrics import (
    RecoveryMetricsSummary,
    compute_recovery_metrics,
)
from backend.evaluation.schemas import (
    EvaluationMetrics,
    ExperimentRunRequest,
    ExperimentSummary,
    TaskExecutionResult,
)
from backend.tracing.storage import TraceStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/experiments", tags=["Experiments"])

_default_runner: Optional[BenchmarkRunner] = None
_default_full_runner: Optional[FullExperimentRunner] = None

def get_runner(storage: TraceStorage = Depends(get_storage)) -> BenchmarkRunner:
    global _default_runner
    if _default_runner is None or _default_runner.storage != storage:
        _default_runner = BenchmarkRunner(storage=storage)
    return _default_runner

def get_full_runner(storage: TraceStorage = Depends(get_storage)) -> FullExperimentRunner:
    global _default_full_runner
    if _default_full_runner is None or _default_full_runner.storage != storage:
        _default_full_runner = FullExperimentRunner(storage=storage)
    return _default_full_runner

@router.post("/run", response_model=ExperimentSummary, status_code=status.HTTP_201_CREATED)
def run_experiment(
    request: Dict[str, Any],
    runner: BenchmarkRunner = Depends(get_runner),
    full_runner: FullExperimentRunner = Depends(get_full_runner)
) -> ExperimentSummary:
    """
    Start an evaluation experiment across selected benchmark tasks.
    Supports either ExperimentConfig (Milestone 5) or ExperimentRunRequest (Milestones 2-4).
    """
    try:
        if "agent_modes" in request or "experiment_type" in request:
            config = ExperimentConfig.model_validate(request)
            exec_summary = full_runner.run_experiment(config)
            return ExperimentSummary(
                experiment_id=exec_summary.experiment_id,
                benchmark_version=exec_summary.benchmark_version,
                agent_mode=exec_summary.agent_modes[0] if exec_summary.agent_modes else "baseline",
                status="completed",
                total_tasks=exec_summary.total_tasks,
                completed_tasks=exec_summary.completed_tasks,
                created_at=exec_summary.started_at,
                completed_at=exec_summary.completed_at,
                config=config.model_dump(),
            )
        else:
            req = ExperimentRunRequest.model_validate(request)
            summary = runner.run_experiment(req)
            return summary
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        logger.error(f"Experiment execution error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Experiment runner failed: {str(e)}"
        )

@router.get("", response_model=List[ExperimentSummary])
@router.get("/", response_model=List[ExperimentSummary], include_in_schema=False)
def list_experiments(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    storage: TraceStorage = Depends(get_storage)
) -> List[ExperimentSummary]:
    """List all executed experiments ordered by creation time descending."""
    experiments = storage.list_experiments()
    return experiments[offset : offset + limit]

@router.get("/overview/stats")
def get_platform_overview_stats(
    storage: TraceStorage = Depends(get_storage)
) -> Dict[str, Any]:
    """Calculate platform-wide KPI statistics from persisted experiment runs."""
    experiments = storage.list_experiments()
    total_experiments = len(experiments)

    total_runs = 0
    total_verified = 0
    total_tool_calls = 0
    total_cost = 0.0
    latencies = []

    mode_stats: Dict[str, Dict[str, Any]] = {}
    failure_counts: Dict[str, int] = {}

    with storage._lock, storage._connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM experiment_results")
        rows = cursor.fetchall()
        total_runs = len(rows)
        for r in rows:
            mode = r["agent_mode"]
            if mode not in mode_stats:
                mode_stats[mode] = {"total": 0, "verified": 0, "latencies": [], "tool_calls": 0}
            mode_stats[mode]["total"] += 1
            if r["verification_status"] == "verified":
                total_verified += 1
                mode_stats[mode]["verified"] += 1
            dur = r["total_duration_ms"] or 0.0
            latencies.append(dur)
            mode_stats[mode]["latencies"].append(dur)
            tc = r["tool_call_count"] or 0
            total_tool_calls += tc
            mode_stats[mode]["tool_calls"] += tc
            if r["estimated_cost"]:
                total_cost += r["estimated_cost"]
            if r["terminal_status"] != "successful_completion":
                status = r["terminal_status"]
                failure_counts[status] = failure_counts.get(status, 0) + 1

        cursor.execute("SELECT terminal_status FROM recovery_reports")
        rec_rows = cursor.fetchall()
        rec_count = len(rec_rows)
        rec_success = sum(1 for rr in rec_rows if rr["terminal_status"] == "recovered_successfully")

    success_rate = round((total_verified / total_runs) * 100.0, 1) if total_runs > 0 else 0.0
    rec_success_rate = round((rec_success / rec_count) * 100.0, 1) if rec_count > 0 else 0.0
    sorted_lats = sorted(latencies)
    med_latency = round(sorted_lats[len(sorted_lats) // 2], 1) if sorted_lats else 0.0
    mean_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
    avg_tools = round(total_tool_calls / total_runs, 2) if total_runs > 0 else 0.0

    mode_breakdown = []
    for mode, data in sorted(mode_stats.items(), key=lambda x: x[0]):
        m_tot = data["total"]
        m_ver = data["verified"]
        m_sr = round((m_ver / m_tot) * 100.0, 1) if m_tot > 0 else 0.0
        m_mean_lat = round(sum(data["latencies"]) / len(data["latencies"]), 1) if data["latencies"] else 0.0
        m_avg_tools = round(data["tool_calls"] / m_tot, 2) if m_tot > 0 else 0.0
        mode_breakdown.append({
            "mode": mode,
            "total_runs": m_tot,
            "verified_runs": m_ver,
            "success_rate": m_sr,
            "mean_latency_ms": m_mean_lat,
            "avg_tool_calls": m_avg_tools,
        })

    return {
        "total_experiments": total_experiments,
        "total_runs_evaluated": total_runs,
        "verified_task_success_rate": success_rate,
        "recovery_success_rate": rec_success_rate,
        "total_recovery_interventions": rec_count,
        "median_latency_ms": med_latency,
        "mean_latency_ms": mean_latency,
        "average_tool_calls_per_task": avg_tools,
        "total_measured_cost": round(total_cost, 4),
        "mode_breakdown": mode_breakdown,
        "failure_distribution": [{"category": k, "count": v} for k, v in sorted(failure_counts.items(), key=lambda x: -x[1])],
    }

@router.get("/{experiment_id}", response_model=ExperimentSummary)
def get_experiment(
    experiment_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> ExperimentSummary:
    """Returns experiment metadata, execution status, and aggregated metrics."""
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )
    return exp

@router.get("/{experiment_id}/results", response_model=List[TaskExecutionResult])
def get_experiment_results(
    experiment_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    mode: Optional[str] = Query(None, description="Optional agent mode filter"),
    storage: TraceStorage = Depends(get_storage)
) -> List[TaskExecutionResult]:
    """Returns paginated per-task execution results, verification outcomes, and trace references."""
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )
    results, _ = storage.get_experiment_results_paginated(experiment_id, limit=limit, offset=offset, mode=mode)
    return results

@router.get("/{experiment_id}/metrics", response_model=EvaluationMetrics)
def get_experiment_metrics(
    experiment_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> EvaluationMetrics:
    """Returns aggregated reliability, verification accuracy, efficiency, and failure metrics."""
    metrics = storage.get_experiment_metrics(experiment_id)
    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metrics for experiment '{experiment_id}' not found."
        )
    return metrics

@router.get("/{experiment_id}/recovery-metrics", response_model=RecoveryMetricsSummary)
def get_experiment_recovery_metrics(
    experiment_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> RecoveryMetricsSummary:
    """Returns recovery success rates, attempt rates, and overhead efficiency metrics."""
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )
    recovery_reports = storage.get_recovery_reports_for_experiment(experiment_id)
    return compute_recovery_metrics(
        recovery_reports=recovery_reports,
        agent_mode=exp.agent_mode,
        total_attempted_override=exp.total_tasks,
    )

@router.get("/{experiment_id}/comparisons")
def get_experiment_comparisons(
    experiment_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> List[Dict[str, Any]]:
    """Returns paired statistical hypothesis test comparisons between agent modes."""
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )
    comparisons = storage.get_experiment_comparisons(experiment_id)
    if comparisons is None:
        return []
    return comparisons

@router.get("/{experiment_id}/failure-analysis")
def get_experiment_failure_analysis(
    experiment_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> Dict[str, Any]:
    """Returns granular results grouped by failure category and controlled scenario."""
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )
    analysis = storage.get_experiment_failure_analysis(experiment_id)
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failure analysis not available for experiment '{experiment_id}'."
        )
    return analysis

@router.get("/{experiment_id}/ablation")
def get_experiment_ablation(
    experiment_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> Dict[str, Any]:
    """Returns component ablation study results when executed for this experiment."""
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )
    ablation = storage.get_experiment_ablation(experiment_id)
    if ablation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ablation analysis not available for experiment '{experiment_id}'."
        )
    return ablation

@router.get("/{experiment_id}/report")
def get_experiment_report(
    experiment_id: str,
    format: str = Query("markdown", pattern="^(markdown|text)$"),
    storage: TraceStorage = Depends(get_storage)
) -> Response:
    """Returns the generated Markdown research report for the experiment."""
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )
    report_md = storage.get_experiment_report(experiment_id)
    if not report_md:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Research report for experiment '{experiment_id}' not found."
        )
    return Response(content=report_md, media_type="text/markdown")

@router.get("/{experiment_id}/manifest")
def get_experiment_manifest(
    experiment_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> Dict[str, Any]:
    """Returns the immutable reproducibility manifest with sanitized credentials."""
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )
    manifest = storage.get_experiment_manifest(experiment_id)
    if not manifest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reproducibility manifest for experiment '{experiment_id}' not found."
        )
    return manifest

@router.get("/{experiment_id}/export")
def export_experiment(
    experiment_id: str,
    format: str = Query("json", pattern="^(json|jsonl)$"),
    storage: TraceStorage = Depends(get_storage)
) -> Response:
    """Export experiment results in JSON or JSONL format."""
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )

    results = storage.get_experiment_results(experiment_id, limit=5000, offset=0)
    safe_exp_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", experiment_id)

    if format == "jsonl":
        lines = [r.model_dump_json() for r in results]
        content = "\n".join(lines) + ("\n" if lines else "")
        media_type = "application/x-ndjson"
        filename = f"{safe_exp_id}_results.jsonl"
    else:
        metrics = storage.get_experiment_metrics(experiment_id)
        manifest = storage.get_experiment_manifest(experiment_id)
        comparisons = storage.get_experiment_comparisons(experiment_id)
        export_data = {
            "experiment": exp.model_dump(),
            "manifest": manifest,
            "metrics": metrics.model_dump() if metrics else None,
            "comparisons": comparisons,
            "results": [r.model_dump() for r in results]
        }
        content = json.dumps(export_data, indent=2)
        media_type = "application/json"
        filename = f"{safe_exp_id}_results.json"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
