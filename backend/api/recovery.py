"""Recovery API endpoints for initiating interventions and querying recovery records."""
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from backend.api.tasks import get_storage
from backend.reliability.diagnostic_report import DiagnosticReport
from backend.reliability.failure_detector import TrajectoryFailureDetector
from backend.reliability.recovery_budget import RecoveryBudgetConfig
from backend.reliability.recovery_engine import RecoveryEngine
from backend.reliability.recovery_report import RecoveryReport
from backend.tracing.storage import TraceStorage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Recovery"])

class RecoverTaskRequest(BaseModel):
    """Optional payload to customize recovery budget or target specific run."""
    run_id: Optional[str] = Field(default=None, description="Optional target run identifier; defaults to latest run.")
    budget_config: Optional[RecoveryBudgetConfig] = Field(default=None, description="Optional override for recovery limits.")

@router.post("/tasks/{task_id}/recover", response_model=RecoveryReport, status_code=status.HTTP_200_OK)
def recover_task(
    task_id: str,
    payload: Optional[RecoverTaskRequest] = None,
    storage: TraceStorage = Depends(get_storage),
) -> RecoveryReport:
    """
    Initiate a bounded, failure-specific recovery attempt for an eligible failed or unresolved task.
    Consumes Milestone 3 diagnostic report and applies the appropriate policy.
    """
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found."
        )

    run_id = (payload.run_id if payload and payload.run_id else task.run_id)
    trace_events = storage.get_events(task_id)
    if not trace_events:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot recover task '{task_id}': execution trace is empty."
        )

    # Fetch or generate diagnostic report
    diag_report = storage.get_diagnostics_for_run(run_id)
    if not diag_report:
        detector = TrajectoryFailureDetector()
        task_ctx = {
            "task_description": task.task,
            "max_steps": task.steps_count or 10,
            "verification_rule": task.verification.model_dump() if task.verification else None,
            "verification_status": task.verification.status if task.verification else None,
            "terminal_status": task.status,
        }
        diag_report = detector.analyze(
            events=trace_events,
            task_id=task_id,
            run_id=run_id,
            task_context=task_ctx,
        )
        storage.save_diagnostic_report(diag_report)

    budget_config = payload.budget_config if payload else None
    engine = RecoveryEngine(storage=storage, budget_config=budget_config)

    task_ctx = {
        "task_description": task.task,
        "max_steps": task.steps_count,
        "verification_rule": task.verification.model_dump() if task.verification else None,
    }

    report = engine.recover(
        task_response=task,
        task_context=task_ctx,
        initial_trace_events=trace_events,
        diag_report=diag_report,
    )
    return report

@router.get("/tasks/{task_id}/recovery", response_model=RecoveryReport)
def get_task_recovery(
    task_id: str,
    storage: TraceStorage = Depends(get_storage),
) -> RecoveryReport:
    """Return latest recovery history and final status for a task."""
    report = storage.get_recovery_for_task(task_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No recovery records found for task '{task_id}'."
        )
    return report

@router.get("/runs/{run_id}/recovery", response_model=RecoveryReport)
def get_run_recovery(
    run_id: str,
    storage: TraceStorage = Depends(get_storage),
) -> RecoveryReport:
    """Return recovery report linked to a specific run."""
    report = storage.get_recovery_for_run(run_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No recovery records found for run '{run_id}'."
        )
    return report

@router.get("/recovery/reports", response_model=List[RecoveryReport])
def list_recovery_reports(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    experiment_id: Optional[str] = Query(None, description="Filter by experiment ID"),
    policy_id: Optional[str] = Query(None, description="Filter by policy ID"),
    status: Optional[str] = Query(None, description="Filter by terminal status"),
    storage: TraceStorage = Depends(get_storage),
) -> List[RecoveryReport]:
    """List recovery reports with optional filters and pagination."""
    try:
        return storage.get_all_recovery_reports(
            limit=limit,
            offset=offset,
            experiment_id=experiment_id,
            policy_id=policy_id,
            terminal_status=status,
        )
    except Exception as e:
        logger.error(f"Error querying recovery reports: {e}", exc_info=True)
        return []

@router.get("/recovery/{recovery_id}", response_model=RecoveryReport)
def get_recovery_by_id(
    recovery_id: str,
    storage: TraceStorage = Depends(get_storage),
) -> RecoveryReport:
    """Retrieve a recovery report by its unique recovery identifier."""
    report = storage.get_recovery_report(recovery_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recovery report '{recovery_id}' not found."
        )
    return report
