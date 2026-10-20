"""Experiment configuration schemas and canonical configuration hashing for Milestone 5."""
import hashlib
import json
import uuid
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator
from backend.tracing.event_schema import current_utc_timestamp

DatasetSplitType = Literal["all", "train", "val", "test", "held_out"]
ExperimentType = Literal[
    "standard",
    "controlled_failure",
    "held_out",
    "repeated_stability",
    "ablation"
]
SupportedAgentMode = Literal[
    "baseline",
    "detection_only",
    "fixed_retry",
    "traceguard_recovery",
    "traceguard"
]

SECRET_KEYS = {
    "api_key", "apikey", "token", "secret", "password",
    "authorization", "bearer", "private_key", "secret_key"
}

def sanitize_dict_for_hashing(obj: Any) -> Any:
    """Recursively sanitize credentials and sensitive parameters prior to hashing or persisting."""
    if isinstance(obj, dict):
        clean = {}
        for k, v in sorted(obj.items(), key=lambda x: str(x[0])):
            if str(k).lower() in SECRET_KEYS:
                clean[k] = "[REDACTED]"
            else:
                clean[k] = sanitize_dict_for_hashing(v)
        return clean
    elif isinstance(obj, list):
        return [sanitize_dict_for_hashing(item) for item in obj]
    return obj

def compute_configuration_hash(config_dict: Dict[str, Any]) -> str:
    """
    Computes a deterministic, canonical SHA-256 hash for an experiment configuration.
    Excludes runtime volatile fields (experiment_id, started_at, configuration_hash).
    """
    excluded_fields = {"experiment_id", "started_at", "configuration_hash"}
    filtered = {
        k: v for k, v in config_dict.items()
        if k not in excluded_fields
    }
    sanitized = sanitize_dict_for_hashing(filtered)
    canonical_json = json.dumps(sanitized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

class ExperimentConfig(BaseModel):
    """Versioned experiment configuration for reproducible evaluation."""
    experiment_id: str = Field(
        default_factory=lambda: f"exp_{uuid.uuid4().hex[:12]}",
        description="Unique experiment identifier"
    )
    experiment_version: str = Field(
        default="v1.0",
        description="Configuration version string"
    )
    benchmark_version: str = Field(
        default="v1.0",
        description="Target benchmark dataset version"
    )
    dataset_split: DatasetSplitType = Field(
        default="all",
        description="Dataset split to evaluate ('all', 'train', 'val', 'test', 'held_out')"
    )
    experiment_type: ExperimentType = Field(
        default="standard",
        description="Experimental protocol category"
    )
    agent_modes: List[str] = Field(
        default_factory=lambda: ["baseline", "fixed_retry", "traceguard_recovery"],
        description="Agent execution modes to run and compare"
    )
    task_ids: Optional[List[str]] = Field(
        default=None,
        description="Explicit task ID whitelist filter"
    )
    category: Optional[str] = Field(
        default=None,
        description="Task category filter"
    )
    repetitions: int = Field(
        default=1,
        ge=1,
        le=50,
        description="Number of repetitions per task"
    )
    model_configuration: Dict[str, Any] = Field(
        default_factory=lambda: {"model_adapter": "mock", "temperature": 0.0},
        description="Model adapter configuration"
    )
    tool_configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool permissions and settings"
    )
    failure_injection_configuration: Dict[str, Any] = Field(
        default_factory=dict,
        description="Settings for controlled failure injection scenarios"
    )
    step_limit: int = Field(
        default=8,
        ge=1,
        le=100,
        description="Maximum execution step ceiling per task attempt"
    )
    task_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=300.0,
        description="Task execution timeout in seconds"
    )
    recovery_budget: Dict[str, Any] = Field(
        default_factory=lambda: {
            "max_recovery_interventions": 2,
            "max_retries_per_tool": 2,
            "max_recovery_steps": 5,
            "max_recovery_model_calls": 3,
            "max_recovery_duration_seconds": 30.0,
        },
        description="Recovery engine budget limits"
    )
    random_seed: Optional[int] = Field(
        default=42,
        description="Optional seed for deterministic reproducibility"
    )
    started_at: str = Field(
        default_factory=current_utc_timestamp,
        description="UTC start timestamp"
    )
    configuration_hash: Optional[str] = Field(
        default=None,
        description="Canonical SHA-256 hash of configuration"
    )

    @model_validator(mode="after")
    def validate_and_compute_hash(self) -> "ExperimentConfig":
        valid_modes = {"baseline", "detection_only", "fixed_retry", "traceguard_recovery", "traceguard"}
        for mode in self.agent_modes:
            if mode not in valid_modes:
                raise ValueError(
                    f"Unsupported agent mode '{mode}'. Supported modes are: {sorted(list(valid_modes))}."
                )

        if not self.agent_modes:
            raise ValueError("At least one agent mode must be specified.")

        # Ensure experiment type constraints
        if self.experiment_type == "controlled_failure":
            if not self.failure_injection_configuration:
                self.failure_injection_configuration = {"enable_failure_injection": True}
            else:
                self.failure_injection_configuration["enable_failure_injection"] = True
        elif self.experiment_type == "held_out" and self.dataset_split == "all":
            self.dataset_split = "held_out"
        elif self.experiment_type == "ablation":
            ablation_modes = ["baseline", "detection_only", "fixed_retry", "traceguard_recovery"]
            # Ensure full ablation modes if user didn't customize
            if len(self.agent_modes) <= 2:
                self.agent_modes = ablation_modes

        # Auto-compute canonical hash if not provided
        if not self.configuration_hash:
            self.configuration_hash = compute_configuration_hash(self.model_dump())

        return self
