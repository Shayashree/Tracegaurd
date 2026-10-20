"""Experiment execution, result retrieval, and export API endpoints."""
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from backend.api.tasks import get_storage
from backend.evaluation.benchmark_runner import BenchmarkRunner
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

def get_runner(storage: TraceStorage = Depends(get_storage)) -> BenchmarkRunner:
    global _default_runner
    if _default_runner is None or _default_runner.storage != storage:
        _default_runner = BenchmarkRunner(storage=storage)
    return _default_runner

@router.post("/run", response_model=ExperimentSummary, status_code=status.HTTP_201_CREATED)
def run_experiment(
    request: ExperimentRunRequest,
    runner: BenchmarkRunner = Depends(get_runner)
) -> ExperimentSummary:
    """
    Start an evaluation experiment across selected benchmark tasks.
    Executes tasks through baseline agent, calculates metrics, and persists records.
    """
    try:
        summary = runner.run_experiment(request)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
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
    storage: TraceStorage = Depends(get_storage)
) -> List[TaskExecutionResult]:
    """Returns paginated per-task execution results, verification outcomes, and trace references."""
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )
    return storage.get_experiment_results(experiment_id, limit=limit, offset=offset)

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
        export_data = {
            "experiment": exp.model_dump(),
            "metrics": metrics.model_dump() if metrics else None,
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
