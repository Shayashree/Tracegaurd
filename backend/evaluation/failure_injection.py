"""Configurable Failure Injection System for Benchmark Testing."""
import logging
from typing import Any, Dict, List, Optional
from backend.agents.model_adapter import BaseModelAdapter
from backend.agents.tool_registry import ToolExecutor, ToolRegistry
from backend.evaluation.schemas import FailureScenarioConfig
from backend.models.schemas import (
    InteractionStep,
    ModelResponse,
    ModelTokens,
    ToolCallRequest,
    ToolDefinition,
    ToolResult,
)

logger = logging.getLogger(__name__)

class InjectedToolExecutor(ToolExecutor):
    """
    ToolExecutor wrapper that intercepts tool calls to deterministically inject
    simulated failures (transient errors, timeouts) when configured.
    """

    def __init__(self, registry: ToolRegistry, failure_config: Optional[FailureScenarioConfig] = None):
        super().__init__(registry)
        self.failure_config = failure_config
        self._tool_call_counts: Dict[str, int] = {}

    def execute(self, tool_call: ToolCallRequest, allowed_tools: Optional[List[str]] = None) -> ToolResult:
        tool_name = tool_call.tool_name
        self._tool_call_counts[tool_name] = self._tool_call_counts.get(tool_name, 0) + 1
        current_attempt = self._tool_call_counts[tool_name]

        if self.failure_config:
            f_type = self.failure_config.failure_type
            trigger = self.failure_config.trigger_condition
            params = self.failure_config.injection_parameters

            # 1. Transient Tool Failure
            if f_type == "transient_tool_failure":
                target_tool = trigger.get("tool", tool_name)
                trigger_attempt = trigger.get("attempt", 1)
                if tool_name == target_tool and current_attempt == trigger_attempt:
                    err_msg = params.get("error_message", "Transient error: Service Temporarily Unavailable")
                    logger.info(f"Injecting transient tool failure for '{tool_name}' on attempt {current_attempt}")
                    return ToolResult(
                        tool_name=tool_name,
                        success=False,
                        data=None,
                        error=f"Injected transient error: {err_msg}",
                        duration_ms=5.0
                    )

            # 2. Simulated Tool Timeout
            elif f_type == "tool_timeout":
                target_tool = trigger.get("tool", tool_name)
                if tool_name == target_tool:
                    logger.info(f"Injecting simulated timeout for tool '{tool_name}'")
                    raise TimeoutError(f"Simulated timeout limit reached in tool '{tool_name}'")

        return super().execute(tool_call, allowed_tools=allowed_tools)

class InjectedModelAdapter(BaseModelAdapter):
    """
    ModelAdapter wrapper that intercepts model requests to inject malformed arguments,
    repeated tool calls, incorrect answers, or endless loop scenarios.
    """

    def __init__(self, base_adapter: BaseModelAdapter, failure_config: Optional[FailureScenarioConfig] = None):
        self.base_adapter = base_adapter
        self.failure_config = failure_config
        self._request_counter = 0

    def generate_next_step(
        self,
        task: str,
        tool_definitions: List[ToolDefinition],
        history: List[InteractionStep],
        scenario_hint: Optional[str] = None
    ) -> ModelResponse:
        self._request_counter += 1
        tokens = ModelTokens(prompt_tokens=45, completion_tokens=15, total_tokens=60)

        if self.failure_config:
            f_type = self.failure_config.failure_type
            params = self.failure_config.injection_parameters

            # 1. Invalid Tool Arguments
            if f_type == "invalid_tool_arguments":
                if self._request_counter == 1:
                    invalid_args = params.get("invalid_payload", {"operation": "add", "a": "invalid_string_operand"})
                    target_tool = params.get("tool", "calculator")
                    logger.info(f"Injecting invalid tool arguments: {invalid_args}")
                    return ModelResponse(
                        is_final_answer=False,
                        tool_call=ToolCallRequest(tool_name=target_tool, arguments=invalid_args),
                        model_name="mock-failure-injector",
                        tokens_used=tokens
                    )

            # 2. Repeated Tool Calls
            elif f_type == "repeated_tool_calls":
                repeat_query = params.get("query", "stuck_query")
                target_tool = params.get("tool", "data_lookup")
                logger.info(f"Injecting repeated tool call #{self._request_counter} for '{target_tool}'")
                return ModelResponse(
                    is_final_answer=False,
                    tool_call=ToolCallRequest(tool_name=target_tool, arguments={"query": repeat_query}),
                    model_name="mock-failure-injector",
                    tokens_used=tokens
                )

            # 3. Step Limit Exhaustion (Infinite Tool Calls)
            elif f_type == "step_limit_exhaustion":
                logger.info(f"Injecting step-limit exhaustion call #{self._request_counter}")
                return ModelResponse(
                    is_final_answer=False,
                    tool_call=ToolCallRequest(
                        tool_name="calculator",
                        arguments={"operation": "add", "a": 1, "b": 1}
                    ),
                    model_name="mock-failure-injector",
                    tokens_used=tokens
                )

            # 4. Incorrect Final Answer
            elif f_type == "incorrect_final_answer":
                # Let tool run on step 1 if needed, then output hallucinated answer
                if len(history) >= 2 or self._request_counter > 1:
                    wrong_ans = params.get("hallucinated_answer", "The calculated result is 99999.")
                    logger.info(f"Injecting incorrect final answer: {wrong_ans}")
                    return ModelResponse(
                        is_final_answer=True,
                        final_answer=wrong_ans,
                        model_name="mock-failure-injector",
                        tokens_used=tokens
                    )

        # Fallback to standard base adapter behavior
        return self.base_adapter.generate_next_step(task, tool_definitions, history, scenario_hint)
