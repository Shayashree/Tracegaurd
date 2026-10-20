"""Experiment execution, result retrieval, and export API endpoints for TraceGuard."""
import json
import logging
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

    if format == "jsonl":
        lines = [r.model_dump_json() for r in results]
        content = "\n".join(lines) + ("\n" if lines else "")
        media_type = "application/x-ndjson"
        filename = f"{experiment_id}_results.jsonl"
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
        filename = f"{experiment_id}_results.json"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
