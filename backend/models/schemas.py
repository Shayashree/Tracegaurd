"""Data models and validation schemas for TraceGuard."""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

class ToolDefinition(BaseModel):
    """Schema defining a tool available to the agent."""
    name: str
    description: str
    parameters: Dict[str, Any]

class ToolCallRequest(BaseModel):
    """A tool call requested by the model."""
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)

class ToolResult(BaseModel):
    """Result of a tool execution."""
    tool_name: str
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None

class ModelTokens(BaseModel):
    """Token usage reported by model provider."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ModelResponse(BaseModel):
    """Response returned by a model adapter."""
    is_final_answer: bool
    final_answer: Optional[str] = None
    tool_call: Optional[ToolCallRequest] = None
    model_name: str
    tokens_used: Optional[ModelTokens] = None

class InteractionStep(BaseModel):
    """An observable step in the interaction history."""
    step_index: int
    role: Literal["user", "assistant", "tool"]
    content: Optional[str] = None
    tool_call: Optional[ToolCallRequest] = None
    tool_result: Optional[ToolResult] = None

class VerificationRule(BaseModel):
    """Deterministic validation rule for verifying agent outcomes."""
    type: Literal["numerical_tolerance", "field_presence", "evidence_reference", "exact_match"]
    expected_value: Optional[Union[float, int, str, Dict[str, Any], List[Any]]] = None
    tolerance: Optional[float] = 1e-4
    required_fields: Optional[List[str]] = None
    required_snippets: Optional[List[str]] = None

class VerificationResult(BaseModel):
    """Outcome verification result."""
    verified: bool
    status: Literal["verified", "failed", "not_applicable", "unverified"]
    verification_method: str
    expected_result: Optional[Any] = None
    observed_result: Optional[Any] = None
    verification_message: str

class TaskCreateRequest(BaseModel):
    """API request payload for submitting a task."""
    task: str = Field(..., min_length=1, description="Task prompt or user goal")
    max_steps: Optional[int] = Field(None, ge=1, le=50, description="Max allowed execution steps")
    timeout_seconds: Optional[float] = Field(None, ge=1.0, le=300.0, description="Timeout limit in seconds")
    allowed_tools: Optional[List[str]] = Field(None, description="Whitelist of allowed tool names")
    verification_rule: Optional[VerificationRule] = Field(None, description="Optional deterministic rule to verify the outcome")
    mock_scenario: Optional[str] = Field(None, description="Optional preset scenario key for deterministic mock model testing")

class TaskResponse(BaseModel):
    """API response summarizing task execution and verification."""
    task_id: str
    run_id: str
    task: str
    status: Literal["pending", "running", "completed", "failed", "step_limit_reached", "timed_out"]
    final_answer: Optional[str] = None
    error_info: Optional[str] = None
    verification: Optional[VerificationResult] = None
    steps_count: int
    duration_ms: float
    created_at: str
    completed_at: Optional[str] = None

class TraceEvent(BaseModel):
    """Structured execution trace event adhering to Milestone 1 specifications."""
    task_id: str
    run_id: str
    step_index: int
    event_type: str
    tool_name: Optional[str] = None
    status: str
    timestamp: str
    duration_ms: Optional[float] = None
    input_summary: Optional[str] = None
    output_summary: Optional[str] = None
    error_type: Optional[str] = None
    model_tokens: Optional[Dict[str, int]] = None
    recovery_attempt_id: Optional[str] = None
    policy_id: Optional[str] = None
    action_type: Optional[str] = None
    finding_ids: Optional[List[str]] = None
    remaining_budget: Optional[Dict[str, Any]] = None
