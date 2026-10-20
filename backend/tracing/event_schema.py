"""Structured event schema and sanitization for TraceGuard execution traces."""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Event types per Milestone 1 specification
EVENT_TASK_STARTED = "task_started"
EVENT_MODEL_REQUEST = "model_request"
EVENT_TOOL_CALL_REQUESTED = "tool_call_requested"
EVENT_TOOL_EXEC_STARTED = "tool_execution_started"
EVENT_TOOL_EXEC_COMPLETED = "tool_execution_completed"
EVENT_TOOL_EXEC_FAILED = "tool_execution_failed"
EVENT_FINAL_ANSWER_PROPOSED = "final_answer_proposed"
EVENT_VERIFICATION_COMPLETED = "verification_completed"
EVENT_TASK_COMPLETED = "task_completed"
EVENT_TASK_FAILED = "task_failed"
EVENT_STEP_LIMIT_REACHED = "step_limit_reached"

VALID_EVENT_TYPES = {
    EVENT_TASK_STARTED,
    EVENT_MODEL_REQUEST,
    EVENT_TOOL_CALL_REQUESTED,
    EVENT_TOOL_EXEC_STARTED,
    EVENT_TOOL_EXEC_COMPLETED,
    EVENT_TOOL_EXEC_FAILED,
    EVENT_FINAL_ANSWER_PROPOSED,
    EVENT_VERIFICATION_COMPLETED,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_FAILED,
    EVENT_STEP_LIMIT_REACHED,
}

REDACTION_PATTERNS = [
    (re.compile(r"(?i)(api[_-]?key|secret|password|bearer|auth|token)[\s:=]+['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"), r"\1=[REDACTED]"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE), "sk-[REDACTED]"),
]

def sanitize_text(text: Optional[str]) -> Optional[str]:
    """Redact sensitive credentials, authorization tokens, and API keys."""
    if not text:
        return text
    sanitized = text
    for pattern, replacement in REDACTION_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized

def current_utc_timestamp() -> str:
    """Return ISO 8601 UTC timestamp string with millisecond precision."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

class TraceEventModel(BaseModel):
    """Event model validating all required trace fields."""
    task_id: str
    run_id: str
    step_index: int
    event_type: str
    tool_name: Optional[str] = None
    status: str
    timestamp: str = Field(default_factory=current_utc_timestamp)
    duration_ms: Optional[float] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    error_type: Optional[str] = None
    model_tokens: Optional[Dict[str, int]] = None

    def model_post_init(self, __context: Any) -> None:
        if self.input_summary:
            self.input_summary = sanitize_text(self.input_summary)
        if self.output_summary:
            self.output_summary = sanitize_text(self.output_summary)
