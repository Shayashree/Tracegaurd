"""Configuration settings and configurable thresholds for the failure detector."""
from pydantic import BaseModel, Field

class DetectorConfig(BaseModel):
    """Configuration settings for TrajectoryFailureDetector."""
    detector_version: str = "v1.0.0"
    repeated_call_threshold: int = Field(
        3, ge=2, description="Number of equivalent tool calls producing no progress required to trigger F1"
    )
    persistent_tool_failure_threshold: int = Field(
        2, ge=1, description="Number of tool failures within trajectory required to trigger persistent tool failure"
    )
    lack_of_progress_threshold: int = Field(
        3, ge=2, description="Number of consecutive steps with empty/stale observations required to trigger F4"
    )
    enable_live_observation: bool = Field(
        True, description="Whether to allow passive observation hook during live agent execution"
    )
    max_observation_events: int = Field(
        200, ge=10, description="Maximum number of events to process in a single pass"
    )
    min_steps_for_progress_eval: int = Field(
        3, ge=2, description="Minimum trajectory length before lack-of-progress rule activates"
    )

default_detector_config = DetectorConfig()
