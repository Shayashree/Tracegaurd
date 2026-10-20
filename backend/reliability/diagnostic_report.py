"""Structured schemas and enums for diagnostic reports and failure findings."""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.tracing.event_schema import current_utc_timestamp

class FailureCategory(str, Enum):
    """Failure Taxonomy Categories F1 through F9."""
    REPEATED_TOOL_CALLS = "repeated_tool_calls"          # F1
    INVALID_TOOL_ARGUMENTS = "invalid_tool_arguments"    # F2
    TOOL_EXECUTION_FAILURE = "tool_execution_failure"    # F3
    LACK_OF_PROGRESS = "lack_of_progress"                # F4
    MISSING_EVIDENCE = "missing_evidence"                # F5
    INCORRECT_FINAL_ANSWER = "incorrect_final_answer"    # F6
    STEP_LIMIT_EXHAUSTION = "step_limit_exhaustion"      # F7
    INVALID_MODEL_OUTPUT = "invalid_model_output"        # F8
    UNVERIFIED_COMPLETION = "unverified_completion"      # F9

class DiagnosticStatus(str, Enum):
    """Overall status of diagnostic assessment."""
    HEALTHY = "healthy"
    WARNING = "warning"
    FAILURE_DETECTED = "failure_detected"
    INSUFFICIENT_DATA = "insufficient_data"

class ConfirmationStatus(str, Enum):
    """Certainty/evidence level of diagnostic finding."""
    CONFIRMED = "confirmed"      # Backed by deterministic runtime/verifier proof
    SUSPECTED = "suspected"      # Inferred from observable behavioral heuristics
    UNVERIFIED = "unverified"    # Outcome cannot be definitively established

class SeverityLevel(str, Enum):
    """Severity classification for diagnostic findings."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TrajectoryFeatures(BaseModel):
    """Structured feature vector extracted deterministically from trace events."""
    total_steps: int = 0
    total_tool_calls: int = 0
    unique_tools_used: int = 0
    tool_call_repetition_ratio: float = 0.0
    distinct_argument_patterns: int = 0
    max_consecutive_identical_tool_calls: int = 0
    tool_execution_failures: int = 0
    persistent_tool_failures: int = 0
    validation_failures: int = 0
    empty_tool_results: int = 0
    successful_tool_results: int = 0
    final_answer_attempts: int = 0
    step_limit_reached: bool = False
    final_answer_produced: bool = False
    terminal_status: Optional[str] = None
    verification_status: Optional[str] = None
    evidence_retrieval_occurred: bool = False
    evidence_policy_satisfied: Optional[bool] = None
    mean_step_duration_ms: float = 0.0
    total_duration_ms: float = 0.0
    observable_progress_stalled: bool = False
    tool_names_sequence: List[str] = Field(default_factory=list)

class DiagnosticFinding(BaseModel):
    """A specific failure finding triggered by an explainable rule."""
    finding_id: str
    rule_id: str
    failure_category: FailureCategory
    severity: SeverityLevel
    confirmation_status: ConfirmationStatus
    confidence: Optional[float] = None
    evidence_event_ids: List[str] = Field(default_factory=list)
    explanation: str
    recommended_next_action: str

class DiagnosticReport(BaseModel):
    """Complete machine-readable diagnostic report for an agent trajectory."""
    diagnostic_id: str
    experiment_id: Optional[str] = None
    task_id: str
    run_id: str
    detector_version: str = "v1.0.0"
    diagnostic_status: DiagnosticStatus
    features: TrajectoryFeatures
    findings: List[DiagnosticFinding] = Field(default_factory=list)
    primary_failure_category: Optional[FailureCategory] = None
    severity: SeverityLevel = SeverityLevel.INFO
    evidence_event_ids: List[str] = Field(default_factory=list)
    explanation: str = "Trajectory analyzed without issues detected."
    confirmation_status: ConfirmationStatus = ConfirmationStatus.CONFIRMED
    analysis_duration_ms: float = 0.0
    created_at: str = Field(default_factory=current_utc_timestamp)
