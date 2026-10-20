"""Base class and interface for tools."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Type
import time
from pydantic import BaseModel, ValidationError
from backend.models.schemas import ToolDefinition, ToolResult

class BaseTool(ABC):
    """Abstract base class for all tools in TraceGuard."""
    name: str
    description: str
    args_schema: Type[BaseModel]

    def to_definition(self) -> ToolDefinition:
        """Returns JSON-schema compatible definition for LLM tool consumption."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.args_schema.model_json_schema()
        )

    def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """Validates arguments against schema and executes the tool."""
        start_time = time.perf_counter()
        try:
            validated_args = self.args_schema.model_validate(arguments)
        except ValidationError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                tool_name=self.name,
                success=False,
                data=None,
                error=f"Invalid arguments for tool '{self.name}': {e.errors()}",
                duration_ms=round(duration_ms, 2)
            )

        try:
            result_data = self._run(validated_args)
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                tool_name=self.name,
                success=True,
                data=result_data,
                error=None,
                duration_ms=round(duration_ms, 2)
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ToolResult(
                tool_name=self.name,
                success=False,
                data=None,
                error=f"Execution error in tool '{self.name}': {str(e)}",
                duration_ms=round(duration_ms, 2)
            )

    @abstractmethod
    def _run(self, args: BaseModel) -> Any:
        """Tool-specific execution logic."""
        pass
