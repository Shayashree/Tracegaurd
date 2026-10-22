"""Execution trace query and export endpoints."""
import logging
import re
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Response, status
from backend.api.tasks import get_storage
from backend.models.schemas import TraceEvent
from backend.tracing.storage import TraceStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Traces"])

@router.get("/{task_id}/traces", response_model=List[TraceEvent])
def get_task_traces(
    task_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> List[TraceEvent]:
    """Retrieve ordered execution events recorded for the given task, run_id, or benchmark ID."""
    events = storage.get_events(task_id)
    if not events and not storage.get_task(task_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task or run with ID '{task_id}' not found."
        )
    return events

@router.get("/{task_id}/traces/export")
def export_task_traces_jsonl(
    task_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> Response:
    """Export the execution trace as JSON Lines (JSONL)."""
    events = storage.get_events(task_id)
    if not events and not storage.get_task(task_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task or run with ID '{task_id}' not found."
        )

    jsonl_content = storage.export_jsonl(task_id)
    safe_task_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", task_id)
    filename = f"{safe_task_id}_trace.jsonl"
    return Response(
        content=jsonl_content,
        media_type="application/x-ndjson",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
