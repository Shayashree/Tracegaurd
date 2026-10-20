"""FastAPI endpoints for trajectory-based failure diagnostics and evaluation metrics."""
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.detector_metrics import DetectorEvaluationMetrics, DetectorMetricsCalculator
from backend.reliability.detector_config import DetectorConfig, default_detector_config
from backend.reliability.diagnostic_report import DiagnosticReport
from backend.reliability.failure_detector import TrajectoryFailureDetector
from backend.tracing.storage import TraceStorage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])

class RunDiagnosticsRequest(BaseModel):
    """Request payload to execute diagnostics over an execution run."""
    run_id: str = Field(..., description="Run identifier whose trace should be analyzed")
    task_id: Optional[str] = Field(None, description="Task identifier associated with the run")
    experiment_id: Optional[str] = Field(None, description="Optional experiment identifier")

def get_storage() -> TraceStorage:
    return TraceStorage()

def get_detector() -> TrajectoryFailureDetector:
    return TrajectoryFailureDetector()

@router.post("/run", response_model=DiagnosticReport, status_code=status.HTTP_200_OK)
def run_diagnostics_on_run(
    request: RunDiagnosticsRequest,
    storage: TraceStorage = Depends(get_storage),
    detector: TrajectoryFailureDetector = Depends(get_detector)
) -> DiagnosticReport:
    """Analyze a completed run's trace events and produce/persist a diagnostic report."""
    run_id = request.run_id
    events = storage.get_events_by_run_id(run_id)

    task_id = request.task_id
    if not task_id and events:
        task_id = events[0].task_id

    if not events:
        # Check if task_id was provided and query by task_id
        if task_id:
            events = storage.get_events(task_id)

    if not events:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No trace events found for run_id '{run_id}'."
        )

    task_id = task_id or (events[0].task_id if events else "unknown_task")

    report = detector.analyze(
        events=events,
        task_id=task_id,
        run_id=run_id,
        experiment_id=request.experiment_id
    )

    storage.save_diagnostic_report(report)
    return report

@router.get("/config", response_model=DetectorConfig)
def get_detector_configuration(
    detector: TrajectoryFailureDetector = Depends(get_detector)
) -> DetectorConfig:
    """Return active detector version and non-sensitive configuration parameters."""
    return detector.config

@router.get("", response_model=List[DiagnosticReport])
def list_diagnostic_reports(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    experiment_id: Optional[str] = Query(None, description="Filter by experiment ID"),
    failure_category: Optional[str] = Query(None, description="Filter by failure category"),
    status: Optional[str] = Query(None, description="Filter by diagnostic status"),
    storage: TraceStorage = Depends(get_storage),
) -> List[DiagnosticReport]:
    """List diagnostic reports with optional filters and pagination."""
    return storage.get_all_diagnostic_reports(
        limit=limit,
        offset=offset,
        experiment_id=experiment_id,
        failure_category=failure_category,
        diagnostic_status=status,
    )

@router.get("/{diagnostic_id}", response_model=DiagnosticReport)
def get_diagnostic_report_by_id(
    diagnostic_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> DiagnosticReport:
    """Retrieve a stored diagnostic report by diagnostic_id."""
    report = storage.get_diagnostic_report(diagnostic_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Diagnostic report '{diagnostic_id}' not found."
        )
    return report

# Sub-routers for task and run diagnostics to match requested paths:
# GET /tasks/{task_id}/diagnostics
# GET /runs/{run_id}/diagnostics
task_diag_router = APIRouter(tags=["Diagnostics"])

@task_diag_router.get("/tasks/{task_id}/diagnostics", response_model=List[DiagnosticReport])
def get_task_diagnostics(
    task_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    storage: TraceStorage = Depends(get_storage)
) -> List[DiagnosticReport]:
    """List diagnostic reports associated with a specific task_id."""
    reports = storage.get_diagnostics_for_task(task_id)
    return reports[offset : offset + limit]

@task_diag_router.get("/runs/{run_id}/diagnostics", response_model=DiagnosticReport)
def get_run_diagnostics(
    run_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> DiagnosticReport:
    """Retrieve latest diagnostic report for a specific run_id."""
    report = storage.get_diagnostics_for_run(run_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No diagnostic report found for run_id '{run_id}'."
        )
    return report

# Router for experiment diagnostics:
# POST /experiments/{experiment_id}/diagnostics
# GET /experiments/{experiment_id}/detector-metrics
exp_diag_router = APIRouter(tags=["Diagnostics"])

@exp_diag_router.post("/experiments/{experiment_id}/diagnostics")
def run_experiment_diagnostics(
    experiment_id: str,
    storage: TraceStorage = Depends(get_storage),
    detector: TrajectoryFailureDetector = Depends(get_detector)
) -> Dict[str, Any]:
    """
    Run failure detector over all task traces from an existing experiment run.
    Stores and associates all generated diagnostic reports.
    """
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )

    results = storage.get_experiment_results(experiment_id)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Experiment '{experiment_id}' has no task execution results."
        )

    analyzed_count = 0
    failures_detected = 0

    for r in results:
        events = storage.get_events_by_run_id(r.run_id)
        if not events and r.trace_reference and "task_id" in r.trace_reference:
            events = storage.get_events(r.trace_reference["task_id"])

        task_ctx = {
            "task_id": r.task_id,
            "verification_status": r.verification_status,
            "terminal_status": r.terminal_status,
        }

        report = detector.analyze(
            events=events,
            task_id=r.task_id,
            run_id=r.run_id,
            experiment_id=experiment_id,
            task_context=task_ctx
        )
        storage.save_diagnostic_report(report)
        analyzed_count += 1
        if report.diagnostic_status.value == "failure_detected":
            failures_detected += 1

    return {
        "experiment_id": experiment_id,
        "total_analyzed": analyzed_count,
        "failures_detected": failures_detected,
        "detector_version": detector.config.detector_version,
        "status": "completed"
    }

@exp_diag_router.get("/experiments/{experiment_id}/detector-metrics", response_model=DetectorEvaluationMetrics)
def get_experiment_detector_metrics(
    experiment_id: str,
    storage: TraceStorage = Depends(get_storage),
    detector: TrajectoryFailureDetector = Depends(get_detector)
) -> DetectorEvaluationMetrics:
    """
    Calculate and return detector performance metrics (precision, recall, F1, latency)
    by comparing diagnostic reports against benchmark ground-truth labels.
    """
    exp = storage.get_experiment(experiment_id)
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment '{experiment_id}' not found."
        )

    results = storage.get_experiment_results(experiment_id)
    if not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No execution results for experiment '{experiment_id}'."
        )

    # Load benchmark tasks to obtain independent ground-truth failure scenarios
    loader = BenchmarkDatasetLoader()
    try:
        tasks = loader.load_tasks(version=exp.benchmark_version)
        task_map = {t.task_id: t for t in tasks}
    except Exception:
        task_map = {}

    evaluations: List[Dict[str, Any]] = []

    for r in results:
        # Determine ground truth failure category
        bench_task = task_map.get(r.task_id)
        gt_category: Optional[str] = None
        is_held_out = (BenchmarkDatasetLoader.get_task_split(r.task_id) == "test")

        if bench_task and bench_task.failure_scenario:
            gt_category = bench_task.failure_scenario.failure_type
        elif r.verification_status == "failed":
            gt_category = "incorrect_final_answer"
        elif r.terminal_status == "tool_error":
            gt_category = "tool_execution_failure"
        elif r.terminal_status == "step_limit_reached":
            gt_category = "step_limit_exhaustion"
        elif r.terminal_status == "timeout":
            gt_category = "tool_execution_failure"

        # Fetch diagnostic report
        diag = storage.get_diagnostics_for_run(r.run_id)
        if not diag:
            # Generate on the fly if not yet analyzed
            events = storage.get_events_by_run_id(r.run_id)
            if not events and r.trace_reference and "task_id" in r.trace_reference:
                events = storage.get_events(r.trace_reference["task_id"])
            diag = detector.analyze(
                events=events,
                task_id=r.task_id,
                run_id=r.run_id,
                experiment_id=experiment_id
            )
            storage.save_diagnostic_report(diag)

        detected_cats = [f.failure_category.value for f in diag.findings]
        evaluations.append({
            "expected_failure_category": gt_category,
            "detected_categories": detected_cats,
            "diagnostic_status": diag.diagnostic_status.value,
            "latency_ms": diag.analysis_duration_ms,
            "is_held_out": is_held_out,
        })

    metrics = DetectorMetricsCalculator.calculate_metrics(
        evaluations=evaluations,
        detector_version=detector.config.detector_version
    )
    return metrics
