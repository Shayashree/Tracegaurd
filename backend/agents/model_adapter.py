"""Model Adapter Interface and Implementations."""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from backend.config import settings
from backend.models.schemas import (
    InteractionStep,
    ModelResponse,
    ModelTokens,
    ToolCallRequest,
    ToolDefinition,
)

logger = logging.getLogger(__name__)

class BaseModelAdapter(ABC):
    """Abstract interface for LLM / model adapters in TraceGuard."""

    @abstractmethod
    def generate_next_step(
        self,
        task: str,
        tool_definitions: List[ToolDefinition],
        history: List[InteractionStep],
        scenario_hint: Optional[str] = None
    ) -> ModelResponse:
        """Decide the next action: either request a tool call or propose a final answer."""
        pass

class OpenAIModelAdapter(BaseModelAdapter):
    """OpenAI-compatible LLM adapter for live execution if credentials exist."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_name = model_name or settings.OPENAI_MODEL_NAME
        self.base_url = base_url or settings.OPENAI_BASE_URL
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not set. Use MockModelAdapter or configure credentials.")

    def generate_next_step(
        self,
        task: str,
        tool_definitions: List[ToolDefinition],
        history: List[InteractionStep],
        scenario_hint: Optional[str] = None
    ) -> ModelResponse:
        import json
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url or 'https://api.openai.com/v1'}/chat/completions"

        # Format messages
        messages = [
            {"role": "system", "content": "You are TraceGuard Baseline Agent. You solve tasks using available tools."}
        ]
        messages.append({"role": "user", "content": task})

        for step in history:
            if step.role == "assistant":
                if step.tool_call:
                    messages.append({
                        "role": "assistant",
                        "tool_calls": [{
                            "id": f"call_{step.step_index}",
                            "type": "function",
                            "function": {
                                "name": step.tool_call.tool_name,
                                "arguments": json.dumps(step.tool_call.arguments)
                            }
                        }]
                    })
                elif step.content:
                    messages.append({"role": "assistant", "content": step.content})
            elif step.role == "tool" and step.tool_result:
                messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{step.step_index}",
                    "content": json.dumps(step.tool_result.data if step.tool_result.success else {"error": step.tool_result.error})
                })

        tools_payload = [
            {
                "type": "function",
                "function": {
                    "name": td.name,
                    "description": td.description,
                    "parameters": td.parameters
                }
            }
            for td in tool_definitions
        ] if tool_definitions else None

        body: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.0
        }
        if tools_payload:
            body["tools"] = tools_payload

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]["message"]
        usage = data.get("usage", {})
        tokens = ModelTokens(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0)
        )

        tool_calls = choice.get("tool_calls")
        if tool_calls and len(tool_calls) > 0:
            tc = tool_calls[0]["function"]
            try:
                args = json.loads(tc.get("arguments", "{}"))
            except Exception:
                args = {}
            return ModelResponse(
                is_final_answer=False,
                tool_call=ToolCallRequest(tool_name=tc["name"], arguments=args),
                model_name=self.model_name,
                tokens_used=tokens
            )

        content = choice.get("content") or ""
        return ModelResponse(
            is_final_answer=True,
            final_answer=content,
            model_name=self.model_name,
            tokens_used=tokens
        )
