"""Tool Registry and Execution Dispatcher."""
import logging
from typing import Dict, List, Optional
from backend.models.schemas import ToolCallRequest, ToolDefinition, ToolResult
from backend.tools.base import BaseTool
from backend.tools.calculator import CalculatorTool
from backend.tools.data_lookup import DataLookupTool
from backend.tools.document_search import DocumentSearchTool

logger = logging.getLogger(__name__)

class ToolRegistry:
    """Registry managing available tools and their schemas."""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        # Register default baseline tools
        self.register(CalculatorTool())
        self.register(DataLookupTool())
        self.register(DocumentSearchTool())

    def register(self, tool: BaseTool) -> None:
        """Register a new tool instance."""
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[BaseTool]:
        """Retrieve tool by name."""
        return self._tools.get(name)

    def get_definition(self, name: str) -> Optional[ToolDefinition]:
        """Retrieve tool definition by name."""
        tool = self._tools.get(name)
        return tool.to_definition() if tool else None

    def list_definitions(self, allowed_tools: Optional[List[str]] = None) -> List[ToolDefinition]:
        """Return tool definitions for LLM, optionally filtered by whitelist."""
        defs = []
        for name, tool in self._tools.items():
            if allowed_tools is None or name in allowed_tools:
                defs.append(tool.to_definition())
        return defs

    def is_registered(self, name: str) -> bool:
        return name in self._tools

class ToolExecutor:
    """Safely dispatches and executes tools."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, tool_call: ToolCallRequest, allowed_tools: Optional[List[str]] = None) -> ToolResult:
        """Validates tool authorization and executes safely."""
        name = tool_call.tool_name

        if allowed_tools is not None and name not in allowed_tools:
            return ToolResult(
                tool_name=name,
                success=False,
                data=None,
                error=f"Tool '{name}' is not in the allowed tools list for this task.",
                duration_ms=0.0
            )

        tool = self.registry.get(name)
        if not tool:
            return ToolResult(
                tool_name=name,
                success=False,
                data=None,
                error=f"Tool '{name}' is not recognized or registered.",
                duration_ms=0.0
            )

        return tool.execute(tool_call.arguments)
