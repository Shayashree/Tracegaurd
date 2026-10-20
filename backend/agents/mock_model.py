"""Deterministic Mock Model Adapter for Zero-Credential Testing and Demonstrations."""
import logging
import re
from typing import Any, Callable, Dict, List, Optional
from backend.agents.model_adapter import BaseModelAdapter
from backend.models.schemas import (
    InteractionStep,
    ModelResponse,
    ModelTokens,
    ToolCallRequest,
    ToolDefinition,
)

logger = logging.getLogger(__name__)

class MockModelAdapter(BaseModelAdapter):
    """
    Deterministic model adapter executing tool-calling sequences based on
    task intent, history state, or explicit scripted actions.
    """

    def __init__(self, script: Optional[List[ModelResponse]] = None):
        self.script = script or []
        self._step_counter = 0

    def generate_next_step(
        self,
        task: str,
        tool_definitions: List[ToolDefinition],
        history: List[InteractionStep],
        scenario_hint: Optional[str] = None
    ) -> ModelResponse:
        tokens = ModelTokens(prompt_tokens=42, completion_tokens=18, total_tokens=60)

        # If an explicit pre-scripted sequence was provided (for testing)
        if self.script:
            if self._step_counter < len(self.script):
                res = self.script[self._step_counter]
                self._step_counter += 1
                return res
            return ModelResponse(
                is_final_answer=True,
                final_answer="Script completed.",
                model_name="mock-deterministic",
                tokens_used=tokens
            )

        task_lower = (task or "").lower()
        hint = (scenario_hint or "").lower()

        # -------------------------------------------------------------
        # Scenario: Infinite Loop / Step Limit Reached
        # -------------------------------------------------------------
        if "infinite" in task_lower or "step limit" in task_lower or hint == "infinite_loop":
            return ModelResponse(
                is_final_answer=False,
                tool_call=ToolCallRequest(
                    tool_name="calculator",
                    arguments={"operation": "add", "a": 1, "b": 1}
                ),
                model_name="mock-deterministic",
                tokens_used=tokens
            )

        # -------------------------------------------------------------
        # Scenario: Controlled Tool Error (e.g. Division by Zero)
        # -------------------------------------------------------------
        if ("divide" in task_lower and "0" in task_lower) or hint == "division_by_zero":
            # Check if calculator was already called
            for step in reversed(history):
                if step.role == "tool" and step.tool_result and step.tool_result.tool_name == "calculator":
                    err = step.tool_result.error or "Arithmetic error"
                    return ModelResponse(
                        is_final_answer=True,
                        final_answer=f"The operation could not be completed: {err}.",
                        model_name="mock-deterministic",
                        tokens_used=tokens
                    )
            return ModelResponse(
                is_final_answer=False,
                tool_call=ToolCallRequest(
                    tool_name="calculator",
                    arguments={"operation": "divide", "a": 100.0, "b": 0.0}
                ),
                model_name="mock-deterministic",
                tokens_used=tokens
            )

        # -------------------------------------------------------------
        # Scenario 1: Multi-Step Task: Product A + Product B Price Lookup & Total
        # -------------------------------------------------------------
        if ("product a" in task_lower and "product b" in task_lower) or hint == "product_combined_price":
            # Check history to see what has been done
            has_lookup_result = False
            has_calc_result = False
            prices = []
            calc_total = None

            for step in history:
                if step.role == "tool" and step.tool_result:
                    tr = step.tool_result
                    if tr.tool_name == "data_lookup" and tr.success and isinstance(tr.data, dict):
                        matches = tr.data.get("matches", [])
                        for item in matches:
                            if "price" in item:
                                prices.append(float(item["price"]))
                        if len(prices) >= 2:
                            has_lookup_result = True
                    elif tr.tool_name == "calculator" and tr.success and isinstance(tr.data, dict):
                        calc_total = tr.data.get("result")
                        has_calc_result = True

            if not has_lookup_result:
                # Step 1: Request structured data lookup
                return ModelResponse(
                    is_final_answer=False,
                    tool_call=ToolCallRequest(
                        tool_name="data_lookup",
                        arguments={"query": "Product A, Product B"}
                    ),
                    model_name="mock-deterministic",
                    tokens_used=tokens
                )
            elif not has_calc_result:
                # Step 2: Request calculator operation using observed prices
                p1, p2 = prices[0], prices[1]
                return ModelResponse(
                    is_final_answer=False,
                    tool_call=ToolCallRequest(
                        tool_name="calculator",
                        arguments={"operation": "add", "a": p1, "b": p2}
                    ),
                    model_name="mock-deterministic",
                    tokens_used=tokens
                )
            else:
                # Step 3: Propose final answer
                return ModelResponse(
                    is_final_answer=True,
                    final_answer=(
                        f"The price of Product A is ${prices[0]:.2f} and Product B is ${prices[1]:.2f}. "
                        f"Their combined total price is ${calc_total:.2f}."
                    ),
                    model_name="mock-deterministic",
                    tokens_used=tokens
                )

        # -------------------------------------------------------------
        # Scenario 2: Direct Arithmetic Calculation
        # -------------------------------------------------------------
        if any(w in task_lower for w in ["calculate", "multiply", "add", "subtract", "sum", "+", "*", "-", "/"]):
            # Check if calculator was executed
            for step in reversed(history):
                if step.role == "tool" and step.tool_result and step.tool_result.tool_name == "calculator":
                    res = step.tool_result.data.get("result") if step.tool_result.data else None
                    return ModelResponse(
                        is_final_answer=True,
                        final_answer=f"The calculated result is {res}.",
                        model_name="mock-deterministic",
                        tokens_used=tokens
                    )

            # Parse numbers and operation from task
            nums = re.findall(r"\d+(?:\.\d+)?", task_lower)
            a = float(nums[0]) if len(nums) > 0 else 25.0
            b = float(nums[1]) if len(nums) > 1 else 4.0
            
            if "*" in task_lower or "multiply" in task_lower:
                op = "multiply"
            elif "/" in task_lower or "divide" in task_lower:
                op = "divide"
            elif "-" in task_lower or "subtract" in task_lower:
                op = "subtract"
            else:
                op = "add"

            return ModelResponse(
                is_final_answer=False,
                tool_call=ToolCallRequest(
                    tool_name="calculator",
                    arguments={"operation": op, "a": a, "b": b}
                ),
                model_name="mock-deterministic",
                tokens_used=tokens
            )

        # -------------------------------------------------------------
        # Scenario 3: Document Question (Search Tool)
        # -------------------------------------------------------------
        if any(w in task_lower for w in ["refund", "return", "shipping", "warranty", "policy", "faq", "terms", "company"]):
            for step in reversed(history):
                if step.role == "tool" and step.tool_result and step.tool_result.tool_name == "document_search":
                    matches = step.tool_result.data.get("matches", []) if step.tool_result.data else []
                    if matches:
                        doc_id = matches[0].get("document_id", "DOC-UNKNOWN")
                        # Combine relevant excerpts from search matches
                        snippets = [m.get("snippet", "") for m in matches[:3] if m.get("snippet")]
                        combined_snippet = " \n".join(snippets)
                        return ModelResponse(
                            is_final_answer=True,
                            final_answer=f"According to {doc_id}: {combined_snippet}",
                            model_name="mock-deterministic",
                            tokens_used=tokens
                        )
                    else:
                        return ModelResponse(
                            is_final_answer=True,
                            final_answer="No relevant policy evidence was found in the document library.",
                            model_name="mock-deterministic",
                            tokens_used=tokens
                        )

            # Formulate query
            search_query = "refund return policy"
            if "shipping" in task_lower:
                search_query = "shipping delivery timeline"
            elif "warranty" in task_lower:
                search_query = "warranty hardware terms"
            elif "company" in task_lower:
                search_query = "company overview mission"

            return ModelResponse(
                is_final_answer=False,
                tool_call=ToolCallRequest(
                    tool_name="document_search",
                    arguments={"query": search_query}
                ),
                model_name="mock-deterministic",
                tokens_used=tokens
            )

        # -------------------------------------------------------------
        # Fallback Single Product Lookup
        # -------------------------------------------------------------
        if "product" in task_lower or "price" in task_lower:
            for step in reversed(history):
                if step.role == "tool" and step.tool_result and step.tool_result.tool_name == "data_lookup":
                    matches = step.tool_result.data.get("matches", []) if step.tool_result.data else []
                    if matches:
                        p = matches[0]
                        return ModelResponse(
                            is_final_answer=True,
                            final_answer=f"Found product {p.get('name')} (ID: {p.get('id')}) priced at ${p.get('price')}.",
                            model_name="mock-deterministic",
                            tokens_used=tokens
                        )
                    return ModelResponse(
                        is_final_answer=True,
                        final_answer="No matching products found in the catalog.",
                        model_name="mock-deterministic",
                        tokens_used=tokens
                    )
            return ModelResponse(
                is_final_answer=False,
                tool_call=ToolCallRequest(
                    tool_name="data_lookup",
                    arguments={"query": task}
                ),
                model_name="mock-deterministic",
                tokens_used=tokens
            )

        # Default direct answer
        return ModelResponse(
            is_final_answer=True,
            final_answer=f"Task acknowledged: {task}",
            model_name="mock-deterministic",
            tokens_used=tokens
        )
