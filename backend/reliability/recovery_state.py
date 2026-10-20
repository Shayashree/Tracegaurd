"""Safe checkpointing and state tracking for recovery attempts."""
import json
import logging
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.models.schemas import InteractionStep
from backend.tracing.event_schema import current_utc_timestamp, sanitize_text

logger = logging.getLogger(__name__)

class RecoveryCheckpoint(BaseModel):
    """Sanitized checkpoint capturing safe resumable state."""
    checkpoint_id: str
    task_id: str
    run_id: str
    recovery_attempt_id: str
    parent_attempt_id: Optional[str] = None
    step_index: int
    completed_tool_results: List[Dict[str, Any]] = Field(default_factory=list)
    sanitized_history_summary: List[str] = Field(default_factory=list)
    last_known_evidence: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=current_utc_timestamp)

def sanitize_data_object(obj: Any) -> Any:
    """Recursively sanitize strings inside dicts, lists, or primitive values."""
    if isinstance(obj, str):
        return sanitize_text(obj)
    elif isinstance(obj, dict):
        return {k: sanitize_data_object(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_data_object(item) for item in obj]
    return obj

class RecoveryStateManager:
    """Manages creation, validation, and retrieval of safe recovery checkpoints."""

    @staticmethod
    def create_checkpoint(
        task_id: str,
        run_id: str,
        recovery_attempt_id: str,
        step_index: int,
        history: List[InteractionStep],
        parent_attempt_id: Optional[str] = None,
    ) -> RecoveryCheckpoint:
        """Create a safe checkpoint stripped of secrets, credentials, or private model reasoning."""
        checkpoint_id = f"chk_{uuid.uuid4().hex[:10]}"
        completed_tool_results: List[Dict[str, Any]] = []
        sanitized_history_summary: List[str] = []
        last_known_evidence: List[str] = []

        for step in history:
            if step.tool_result and step.tool_result.success:
                raw_data = step.tool_result.data
                safe_data = sanitize_data_object(raw_data)

                completed_tool_results.append({
                    "step_index": step.step_index,
                    "tool_name": step.tool_result.tool_name,
                    "success": True,
                    "data": safe_data,
                    "duration_ms": step.tool_result.duration_ms,
                })

                if step.tool_result.tool_name == "document_search" and isinstance(raw_data, list):
                    for item in raw_data:
                        if isinstance(item, dict) and "content" in item:
                            last_known_evidence.append(sanitize_text(str(item["content"][:300])))

            if step.role == "tool" and step.tool_result:
                sanitized_history_summary.append(
                    f"Step {step.step_index} [tool={step.tool_result.tool_name}]: success={step.tool_result.success}"
                )
            elif step.role == "assistant" and step.tool_call:
                sanitized_history_summary.append(
                    f"Step {step.step_index} [assistant]: called {step.tool_call.tool_name}"
                )

        return RecoveryCheckpoint(
            checkpoint_id=checkpoint_id,
            task_id=task_id,
            run_id=run_id,
            recovery_attempt_id=recovery_attempt_id,
            parent_attempt_id=parent_attempt_id,
            step_index=step_index,
            completed_tool_results=completed_tool_results,
            sanitized_history_summary=sanitized_history_summary,
            last_known_evidence=last_known_evidence,
            created_at=current_utc_timestamp(),
        )
