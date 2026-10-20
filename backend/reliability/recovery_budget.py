"""Centralized recovery budget enforcement and resource tracking."""
import logging
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field
from backend.reliability.recovery_report import RecoveryBudgetUsage

logger = logging.getLogger(__name__)

class RecoveryBudgetConfig(BaseModel):
    """Configuration limits for recovery interventions."""
    max_recovery_attempts: int = Field(default=2, ge=1, le=5)
    max_retries_per_tool: int = Field(default=2, ge=1, le=5)
    max_recovery_steps: int = Field(default=5, ge=1, le=10)
    max_recovery_duration_sec: float = Field(default=30.0, ge=1.0, le=120.0)
    max_total_task_duration_sec: float = Field(default=60.0, ge=1.0, le=300.0)
    max_recovery_model_calls: int = Field(default=4, ge=0, le=10)
    max_recovery_tool_calls: int = Field(default=5, ge=0, le=15)
    max_estimated_cost: Optional[float] = Field(default=None)

class RecoveryBudgetTracker:
    """Tracks and bounds resource consumption during recovery attempts."""

    def __init__(self, config: Optional[RecoveryBudgetConfig] = None, initial_task_duration_ms: float = 0.0):
        self.config = config or RecoveryBudgetConfig()
        self.initial_task_duration_ms = initial_task_duration_ms

        self.attempts_used: int = 0
        self.steps_used: int = 0
        self.model_calls_used: int = 0
        self.tool_calls_used: int = 0
        self.recovery_duration_ms: float = 0.0
        self.tool_retries_used: Dict[str, int] = {}
        self.estimated_cost_used: float = 0.0

        self.exhausted_limit: Optional[str] = None

    @property
    def total_duration_ms(self) -> float:
        return self.initial_task_duration_ms + self.recovery_duration_ms

    @property
    def is_exhausted(self) -> bool:
        return self.exhausted_limit is not None

    def check_can_attempt(self) -> Tuple[bool, Optional[str]]:
        """Verify if a new recovery attempt is permitted under the budget."""
        if self.exhausted_limit:
            return False, f"Budget already exhausted: {self.exhausted_limit}"
        if self.attempts_used >= self.config.max_recovery_attempts:
            self.exhausted_limit = f"max_recovery_attempts ({self.config.max_recovery_attempts}) reached"
            return False, self.exhausted_limit
        if (self.recovery_duration_ms / 1000.0) >= self.config.max_recovery_duration_sec:
            self.exhausted_limit = f"max_recovery_duration_sec ({self.config.max_recovery_duration_sec}s) reached"
            return False, self.exhausted_limit
        if (self.total_duration_ms / 1000.0) >= self.config.max_total_task_duration_sec:
            self.exhausted_limit = f"max_total_task_duration_sec ({self.config.max_total_task_duration_sec}s) reached"
            return False, self.exhausted_limit
        return True, None

    def check_can_execute_step(self) -> Tuple[bool, Optional[str]]:
        """Verify if an additional recovery step is permitted."""
        if self.exhausted_limit:
            return False, f"Budget exhausted: {self.exhausted_limit}"
        if self.steps_used >= self.config.max_recovery_steps:
            self.exhausted_limit = f"max_recovery_steps ({self.config.max_recovery_steps}) reached"
            return False, self.exhausted_limit
        return self.check_can_attempt()

    def check_can_call_model(self) -> Tuple[bool, Optional[str]]:
        """Verify if another model invocation during recovery is permitted."""
        if self.exhausted_limit:
            return False, f"Budget exhausted: {self.exhausted_limit}"
        if self.model_calls_used >= self.config.max_recovery_model_calls:
            self.exhausted_limit = f"max_recovery_model_calls ({self.config.max_recovery_model_calls}) reached"
            return False, self.exhausted_limit
        return self.check_can_execute_step()

    def check_can_call_tool(self, tool_name: str, is_retry: bool = False) -> Tuple[bool, Optional[str]]:
        """Verify if executing/retrying a tool is permitted."""
        if self.exhausted_limit:
            return False, f"Budget exhausted: {self.exhausted_limit}"
        if self.tool_calls_used >= self.config.max_recovery_tool_calls:
            self.exhausted_limit = f"max_recovery_tool_calls ({self.config.max_recovery_tool_calls}) reached"
            return False, self.exhausted_limit
        if is_retry:
            retries = self.tool_retries_used.get(tool_name, 0)
            if retries >= self.config.max_retries_per_tool:
                self.exhausted_limit = f"max_retries_per_tool for '{tool_name}' ({self.config.max_retries_per_tool}) reached"
                return False, self.exhausted_limit
        return self.check_can_execute_step()

    def record_attempt(self) -> None:
        self.attempts_used += 1

    def record_step(self) -> None:
        self.steps_used += 1

    def record_model_call(self) -> None:
        self.model_calls_used += 1

    def record_tool_call(self, tool_name: str, is_retry: bool = False) -> None:
        self.tool_calls_used += 1
        if is_retry:
            self.tool_retries_used[tool_name] = self.tool_retries_used.get(tool_name, 0) + 1

    def record_duration(self, duration_ms: float) -> None:
        self.recovery_duration_ms += duration_ms
        if (self.recovery_duration_ms / 1000.0) >= self.config.max_recovery_duration_sec:
            self.exhausted_limit = f"max_recovery_duration_sec ({self.config.max_recovery_duration_sec}s) reached"
        elif (self.total_duration_ms / 1000.0) >= self.config.max_total_task_duration_sec:
            self.exhausted_limit = f"max_total_task_duration_sec ({self.config.max_total_task_duration_sec}s) reached"

    def to_usage_model(self) -> RecoveryBudgetUsage:
        """Export current usage as a structured model."""
        return RecoveryBudgetUsage(
            attempts=self.attempts_used,
            steps=self.steps_used,
            tool_calls=self.tool_calls_used,
            model_calls=self.model_calls_used,
            duration_ms=round(self.recovery_duration_ms, 2),
            estimated_cost=round(self.estimated_cost_used, 4) if self.estimated_cost_used else None,
            exhausted_limit=self.exhausted_limit,
        )

    def remaining_summary(self) -> Dict[str, Any]:
        """Summary of remaining allowances for logging in traces."""
        return {
            "remaining_attempts": max(0, self.config.max_recovery_attempts - self.attempts_used),
            "remaining_steps": max(0, self.config.max_recovery_steps - self.steps_used),
            "remaining_model_calls": max(0, self.config.max_recovery_model_calls - self.model_calls_used),
            "remaining_tool_calls": max(0, self.config.max_recovery_tool_calls - self.tool_calls_used),
            "remaining_duration_sec": max(0.0, round(self.config.max_recovery_duration_sec - (self.recovery_duration_ms / 1000.0), 2)),
            "exhausted_limit": self.exhausted_limit,
        }
