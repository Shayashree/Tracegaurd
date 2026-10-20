"""Evaluation and Benchmark Pydantic Schemas for TraceGuard Milestone 2."""
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator
from backend.models.schemas import VerificationRule

CategoryType = Literal[
    "arithmetic",
    "data_lookup",
    "document_qa",
    "multi_step",
    "failure_scenario"
]

AgentModeType = Literal[
    "baseline",
    "fixed_retry",
    "traceguard"
]

TerminalStatusType = Literal[
    "successful_completion",
    "incorrect_answer",
    "tool_error",
    "step_limit_exhaustion",
    "timeout",
    "unverified_completion",
    "internal_error"
]

class FailureScenarioConfig(BaseModel):
    """Configuration for a controlled failure injection scenario."""
    scenario_id: str
    failure_type: Literal[
        "transient_tool_failure",
        "invalid_tool_arguments",
        "repeated_tool_calls",
        "missing_evidence",
        "incorrect_final_answer",
        "step_limit_exhaustion",
        "tool_timeout",
        "no_matching_record"
    ]
    trigger_condition: Dict[str, Any] = Field(default_factory=dict)
    injection_parameters: Dict[str, Any] = Field(default_factory=dict)
    expected_observation: str
    expected_terminal_status: str

class BenchmarkTask(BaseModel):
    """Schema for a single versioned benchmark task."""
    task_id: str = Field(..., min_length=1, description="Unique, stable task identifier")
    benchmark_version: str = Field("v1.0", description="Benchmark version string")
    category: CategoryType = Field(..., description="Benchmark category")
    task_description: str = Field(..., min_length=1, description="Task prompt / instruction")
    allowed_tools: List[str] = Field(default_factory=list, description="Whitelisted tools for task")
    expected_answer: Optional[Union[float, int, str, Dict[str, Any], List[Any]]] = None
    verification_rule: Optional[VerificationRule] = None
    expected_tool_sequence: Optional[List[str]] = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    tags: List[str] = Field(default_factory=list)
    failure_scenario: Optional[FailureScenarioConfig] = None

class TaskExecutionResult(BaseModel):
    """Execution record for a single task within an evaluation experiment."""
    experiment_id: str
    task_id: str
    run_id: str
    benchmark_version: str
    agent_mode: str = "baseline"
    started_at: str
    completed_at: str
    terminal_status: TerminalStatusType
    expected_answer: Optional[Any] = None
    observed_answer: Optional[str] = None
    verification_status: Literal["verified", "failed", "not_applicable", "unverified"]
    verification_message: str
    step_count: int
    tool_call_count: int
    tool_error_count: int
    total_duration_ms: float
    model_tokens: Optional[Dict[str, int]] = None
    estimated_cost: Optional[float] = None
    trace_reference: Dict[str, str] = Field(default_factory=dict)
    failure_scenario_id: Optional[str] = None

class FailureDistribution(BaseModel):
    """Distribution of failure causes across attempted tasks."""
    incorrect_answers: int = 0
    tool_errors: int = 0
    timeouts: int = 0
    step_limit_exhaustion: int = 0
    missing_evidence: int = 0
    other_errors: int = 0
    total_failures: int = 0
    failure_percentages: Dict[str, float] = Field(default_factory=dict)

class EfficiencyMetrics(BaseModel):
    """Latency and resource efficiency metrics."""
    mean_duration_ms: float = 0.0
    median_duration_ms: float = 0.0
    p95_duration_ms: Optional[float] = None
    p95_sample_note: Optional[str] = None
    mean_tool_calls_per_task: float = 0.0
    mean_steps_per_task: float = 0.0
    total_tokens: Optional[int] = None
    mean_tokens_per_task: Optional[float] = None
    cost_per_task: Optional[float] = None
    cost_per_successful_task: Optional[float] = None

class ConfidenceInterval(BaseModel):
    """Confidence interval for success rate or accuracy metric."""
    point_estimate: float
    lower_bound: float
    upper_bound: float
    confidence_level: float = 0.95
    method: str = "Wilson score interval"
    sample_size: int
    warning: Optional[str] = None

class RepeatabilityMetrics(BaseModel):
    """Consistency metrics across task repetitions."""
    repetitions: int
    success_rate_per_rep: List[float] = Field(default_factory=list)
    duration_mean_ms: float = 0.0
    duration_std_ms: float = 0.0
    output_consistent: bool = True
    tool_sequence_consistent: bool = True

class EvaluationMetrics(BaseModel):
    """Aggregated evaluation metrics for an experiment run."""
    experiment_id: str
    benchmark_version: str
    agent_mode: str
    total_attempted: int
    successful_tasks: int
    unverified_tasks: int
    failed_tasks: int
    success_rate: float
    success_rate_ci: Optional[ConfidenceInterval] = None
    verification_accuracy: float
    verification_denominator: int
    tool_error_rate: float
    total_tool_calls: int
    failed_tool_calls: int
    failure_distribution: FailureDistribution
    efficiency: EfficiencyMetrics
    repeatability: Optional[RepeatabilityMetrics] = None

class ExperimentRunRequest(BaseModel):
    """Request payload to execute an evaluation experiment."""
    benchmark_version: str = Field("v1.0", description="Benchmark dataset version")
    task_ids: Optional[List[str]] = Field(None, description="Optional whitelist of task IDs to run")
    category: Optional[CategoryType] = Field(None, description="Optional category filter")
    agent_mode: str = Field("baseline", description="Agent mode under test (only 'baseline' supported in Milestone 2)")
    repetitions: int = Field(1, ge=1, le=20, description="Repetitions per task (default 1)")
    enable_failure_injection: bool = Field(False, description="Whether to activate controlled failure scenarios")
    max_steps: Optional[int] = Field(None, ge=1, le=50, description="Override maximum steps")
    timeout_seconds: Optional[float] = Field(None, ge=1.0, le=300.0, description="Override timeout")

    @model_validator(mode="after")
    def validate_agent_mode(self) -> "ExperimentRunRequest":
        if self.agent_mode != "baseline":
            raise ValueError(
                f"Agent mode '{self.agent_mode}' is not yet supported in Milestone 2. "
                "Only 'baseline' is currently executable; 'fixed_retry' and 'traceguard' are planned for future milestones."
            )
        return self

class ExperimentSummary(BaseModel):
    """Summary of an experiment run."""
    experiment_id: str
    benchmark_version: str
    agent_mode: str
    status: Literal["running", "completed", "failed"]
    total_tasks: int
    completed_tasks: int
    created_at: str
    completed_at: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)
    metrics: Optional[EvaluationMetrics] = None
