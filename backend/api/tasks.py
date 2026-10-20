"""Task submission and retrieval endpoints."""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from backend.agents.controller import AgentController
from backend.models.schemas import TaskCreateRequest, TaskResponse
from backend.tracing.storage import TraceStorage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["Tasks"])

# Module-level instances (can be overridden in tests or app state)
_default_storage = TraceStorage()
_default_controller = AgentController(storage=_default_storage)

def get_controller() -> AgentController:
    return _default_controller

def get_storage() -> TraceStorage:
    return _default_storage

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    request: TaskCreateRequest,
    controller: AgentController = Depends(get_controller)
) -> TaskResponse:
    """
    Submit and execute a task using the baseline agent.
    Runs the agent execution loop and returns task details and verification outcome.
    """
    try:
        response = controller.run_task(request)
        return response
    except Exception as e:
        logger.error(f"Error executing task: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal agent execution error: {str(e)}"
        )

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: str,
    storage: TraceStorage = Depends(get_storage)
) -> TaskResponse:
    """Retrieve task status, final answer, error details, and verification status."""
    task = storage.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID '{task_id}' not found."
        )
    return task
