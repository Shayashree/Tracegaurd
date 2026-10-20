"""Structured schemas and enums for failure-specific recovery reporting."""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.models.schemas import VerificationResult
from backend.tracing.event_schema import current_utc_timestamp

class RecoveryPolicyType(str, Enum):
    """Supported recovery policies per Milestone 4 specification."""
    POLICY_A_TRANSIENT_TOOL_FAILURE = "policy_a_transient_tool_failure"
    POLICY_B_INVALID_TOOL_ARGUMENTS = "policy_b_invalid_tool_arguments"
    POLICY_C_REPEATED_ACTIONS = "policy_c_repeated_actions"
    POLICY_D_MISSING_EVIDENCE = "policy_d_missing_evidence"
    POLICY_E_INCORRECT_ANSWER = "policy_e_incorrect_answer"
    POLICY_F_STEP_LIMIT_EXHAUSTION = "policy_f_step_limit_exhaustion"
    POLICY_G_UNVERIFIED_COMPLETION = "policy_g_unverified_completion"
    POLICY_H_MALFORMED_OUTPUT = "policy_h_malformed_output"
    POLICY_NONE = "policy_none"

class RecoveryTerminalStatus(str, Enum):
    """Terminal outcomes distinguishing unassisted, recovered, and failed tasks."""
    SUCCESS_WITHOUT_RECOVERY = "success_without_recovery"
    RECOVERED_SUCCESSFULLY = "recovered_successfully"
    FAILED_AFTER_RECOVERY = "failed_after_recovery"
    UNRESOLVED = "unresolved"
    ABSTAINED = "abstained"
    UNVERIFIED = "unverified"
    TIMEOUT = "timeout"
    BUDGET_EXHAUSTED = "budget_exhausted"

class RecoveryBudgetUsage(BaseModel):
    """Tracks multi-dimensional budget consumption during recovery."""
    attempts: int = 0
    steps: int = 0
    tool_calls: int = 0
    model_calls: int = 0
    duration_ms: float = 0.0
    estimated_cost: Optional[float] = None
    exhausted_limit: Optional[str] = None

class RecoveryActionRecord(BaseModel):
    """Record of a single bounded recovery operation."""
    action_id: str
    attempt_index: int
    policy_id: str
    action_type: str
    status: str
    duration_ms: float = 0.0
    description: str
    input_context: Optional[Dict[str, Any]] = None
    output_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=current_utc_timestamp)

class RecoveryAttemptReport(BaseModel):
    """Record of a single bounded recovery attempt."""
    attempt_id: str
    attempt_index: int
    policy_id: str
    action_type: str
    status: str
    duration_ms: float = 0.0
    actions: List[RecoveryActionRecord] = Field(default_factory=list)
    intermediate_answer: Optional[str] = None
    verification_result: Optional[VerificationResult] = None
    error_message: Optional[str] = None

class RecoveryReport(BaseModel):
    """Comprehensive, explainable recovery report linking original diagnostics to outcome."""
    recovery_id: str
    task_id: str
    run_id: str
    recovery_attempt_id: str
    experiment_id: Optional[str] = None
    recovery_attempted: bool
    policy_id: str
    policy_version: str = "v1.0"
    initial_failure_category: Optional[str] = None
    diagnostic_finding_ids: List[str] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    selection_reason: str = ""
    terminal_status: RecoveryTerminalStatus
    original_status: str
    original_verification_status: Optional[str] = None
    final_verification_status: Optional[str] = None
    final_answer: Optional[str] = None
    attempts: List[RecoveryAttemptReport] = Field(default_factory=list)
    total_recovery_duration_ms: float = 0.0
    total_execution_duration_ms: float = 0.0
    additional_tool_calls: int = 0
    additional_model_calls: int = 0
    budget_usage: RecoveryBudgetUsage
    created_at: str = Field(default_factory=current_utc_timestamp)
