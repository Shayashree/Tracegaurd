"""Passive trace collector recording observable execution events."""
import logging
from typing import Any, Dict, List, Optional
from backend.models.schemas import TraceEvent
from backend.tracing.event_schema import (
    EVENT_FINAL_ANSWER_PROPOSED,
    EVENT_MODEL_REQUEST,
    EVENT_STEP_LIMIT_REACHED,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_FAILED,
    EVENT_TASK_STARTED,
    EVENT_TOOL_CALL_REQUESTED,
    EVENT_TOOL_EXEC_COMPLETED,
    EVENT_TOOL_EXEC_FAILED,
    EVENT_TOOL_EXEC_STARTED,
    EVENT_VERIFICATION_COMPLETED,
    current_utc_timestamp,
    sanitize_text,
)
from backend.tracing.storage import TraceStorage

logger = logging.getLogger(__name__)

class TraceCollector:
    """Passively records structured execution events during an agent run."""

    def __init__(self, task_id: str, run_id: str, storage: Optional[TraceStorage] = None):
        self.task_id = task_id
        self.run_id = run_id
        self.storage = storage
        self.events: List[TraceEvent] = []

    def record_event(
        self,
        step_index: int,
        event_type: str,
        status: str,
        tool_name: Optional[str] = None,
        duration_ms: Optional[float] = None,
        input_summary: Optional[str] = None,
        output_summary: Optional[str] = None,
        error_type: Optional[str] = None,
        model_tokens: Optional[Dict[str, int]] = None,
    ) -> TraceEvent:
        """Create, sanitize, and record an event."""
        event = TraceEvent(
            task_id=self.task_id,
            run_id=self.run_id,
            step_index=step_index,
            event_type=event_type,
            tool_name=tool_name,
            status=status,
            timestamp=current_utc_timestamp(),
            duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
            input_summary=sanitize_text(input_summary),
            output_summary=sanitize_text(output_summary),
            error_type=error_type,
            model_tokens=model_tokens,
        )
        self.events.append(event)
        logger.debug(f"Trace recorded: [{event.step_index}] {event.event_type} - {event.status}")
        return event

    def record_task_started(self, task_text: str) -> TraceEvent:
        return self.record_event(
            step_index=0,
            event_type=EVENT_TASK_STARTED,
            status="started",
            input_summary=task_text,
        )

    def record_model_request(
        self,
        step_index: int,
        prompt_summary: str,
        duration_ms: Optional[float] = None,
        model_tokens: Optional[Dict[str, int]] = None
    ) -> TraceEvent:
        return self.record_event(
            step_index=step_index,
            event_type=EVENT_MODEL_REQUEST,
            status="completed",
            duration_ms=duration_ms,
            input_summary=prompt_summary,
            model_tokens=model_tokens,
        )

    def record_tool_call_requested(
        self,
        step_index: int,
        tool_name: str,
        arguments_summary: str
    ) -> TraceEvent:
        return self.record_event(
            step_index=step_index,
            event_type=EVENT_TOOL_CALL_REQUESTED,
            tool_name=tool_name,
            status="requested",
            input_summary=arguments_summary,
        )

    def record_tool_exec_started(
        self,
        step_index: int,
        tool_name: str,
        arguments_summary: str
    ) -> TraceEvent:
        return self.record_event(
            step_index=step_index,
            event_type=EVENT_TOOL_EXEC_STARTED,
            tool_name=tool_name,
            status="started",
            input_summary=arguments_summary,
        )

    def record_tool_exec_completed(
        self,
        step_index: int,
        tool_name: str,
        output_summary: str,
        duration_ms: float
    ) -> TraceEvent:
        return self.record_event(
            step_index=step_index,
            event_type=EVENT_TOOL_EXEC_COMPLETED,
            tool_name=tool_name,
            status="completed",
            duration_ms=duration_ms,
            output_summary=output_summary,
        )

    def record_tool_exec_failed(
        self,
        step_index: int,
        tool_name: str,
        error_message: str,
        duration_ms: float,
        error_type: Optional[str] = "ToolExecutionError"
    ) -> TraceEvent:
        return self.record_event(
            step_index=step_index,
            event_type=EVENT_TOOL_EXEC_FAILED,
            tool_name=tool_name,
            status="failed",
            duration_ms=duration_ms,
            output_summary=error_message,
            error_type=error_type,
        )

    def record_final_answer_proposed(
        self,
        step_index: int,
        final_answer: str
    ) -> TraceEvent:
        return self.record_event(
            step_index=step_index,
            event_type=EVENT_FINAL_ANSWER_PROPOSED,
            status="proposed",
            output_summary=final_answer,
        )

    def record_verification_completed(
        self,
        step_index: int,
        verification_status: str,
        summary: str
    ) -> TraceEvent:
        return self.record_event(
            step_index=step_index,
            event_type=EVENT_VERIFICATION_COMPLETED,
            status=verification_status,
            output_summary=summary,
        )

    def record_task_completed(
        self,
        step_index: int,
        final_answer: str,
        duration_ms: float
    ) -> TraceEvent:
        return self.record_event(
            step_index=step_index,
            event_type=EVENT_TASK_COMPLETED,
            status="completed",
            duration_ms=duration_ms,
            output_summary=final_answer,
        )

    def record_task_failed(
        self,
        step_index: int,
        error_message: str,
        duration_ms: float,
        error_type: str = "TaskExecutionFailed"
    ) -> TraceEvent:
        return self.record_event(
            step_index=step_index,
            event_type=EVENT_TASK_FAILED,
            status="failed",
            duration_ms=duration_ms,
            output_summary=error_message,
            error_type=error_type,
        )

    def record_step_limit_reached(
        self,
        step_index: int,
        max_steps: int
    ) -> TraceEvent:
        return self.record_event(
            step_index=step_index,
            event_type=EVENT_STEP_LIMIT_REACHED,
            status="stopped",
            output_summary=f"Execution reached maximum limit of {max_steps} steps.",
            error_type="StepLimitExceeded",
        )

    def flush(self) -> None:
        """Persist accumulated events to storage."""
        if self.storage and self.events:
            self.storage.save_events(self.events)
