"""Deterministic Mock Model Adapter for Zero-Credential Testing and Benchmarking."""
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

KNOWN_PRODUCTS = [
    "Product A",
    "Product B",
    "Product C",
    "UltraWide Monitor",
    "USB-C Hub Pro",
    "Desk Mat Studio",
]

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
        # Scenario 1: Multi-Step Task: Product Lookup & Calculation
        # -------------------------------------------------------------
        is_multi_step = (
            hint == "product_combined_price"
            or ("product" in task_lower and any(w in task_lower for w in ["combined", "total", "difference", "calculate", "units", "shipping"]))
            or (any(p.lower() in task_lower for p in KNOWN_PRODUCTS) and any(w in task_lower for w in ["combined", "total", "difference", "units", "shipping"]))
        )

        if is_multi_step:
            has_lookup_result = False
            has_calc_result = False
            prices: List[float] = []
            found_items: List[Dict[str, Any]] = []
            calc_total = None

            for step in history:
                if step.role == "tool" and step.tool_result:
                    tr = step.tool_result
                    if tr.tool_name == "data_lookup" and tr.success and isinstance(tr.data, dict):
                        matches = tr.data.get("matches", [])
                        for item in matches:
                            if "price" in item:
                                prices.append(float(item["price"]))
                                found_items.append(item)
                        if len(prices) >= 1:
                            has_lookup_result = True
                    elif tr.tool_name == "calculator" and tr.success and isinstance(tr.data, dict):
                        calc_total = tr.data.get("result")
                        has_calc_result = True

            # Determine products mentioned in task
            mentioned = [p for p in KNOWN_PRODUCTS if re.search(r"\b" + re.escape(p.lower()) + r"\b", task_lower)]
            lookup_query = ", ".join(mentioned) if mentioned else "Product A, Product B"

            if not has_lookup_result:
                return ModelResponse(
                    is_final_answer=False,
                    tool_call=ToolCallRequest(
                        tool_name="data_lookup",
                        arguments={"query": lookup_query}
                    ),
                    model_name="mock-deterministic",
                    tokens_used=tokens
                )
            elif not has_calc_result:
                # Decide calculator operation based on task wording
                if "difference" in task_lower and len(prices) >= 2:
                    # Check order of products in task
                    idx0 = task_lower.find(mentioned[0].lower()) if len(mentioned) > 0 else 0
                    idx1 = task_lower.find(mentioned[1].lower()) if len(mentioned) > 1 else 1
                    # Find price for each mentioned item
                    p_map = {item["name"].lower(): float(item["price"]) for item in found_items}
                    m0_price = p_map.get(mentioned[0].lower(), prices[0])
                    m1_price = p_map.get(mentioned[1].lower(), prices[1]) if len(mentioned) > 1 else prices[1]
                    p_first = m0_price if idx0 < idx1 else m1_price
                    p_second = m1_price if idx0 < idx1 else m0_price
                    return ModelResponse(
                        is_final_answer=False,
                        tool_call=ToolCallRequest(
                            tool_name="calculator",
                            arguments={"operation": "subtract", "a": p_first, "b": p_second}
                        ),
                        model_name="mock-deterministic",
                        tokens_used=tokens
                    )
                elif "units" in task_lower:
                    qty_match = re.search(r"(\d+)\s+units", task_lower)
                    qty = float(qty_match.group(1)) if qty_match else 2.0
                    unit_price = prices[0] if prices else 45.0
                    return ModelResponse(
                        is_final_answer=False,
                        tool_call=ToolCallRequest(
                            tool_name="calculator",
                            arguments={"operation": "multiply", "a": qty, "b": unit_price}
                        ),
                        model_name="mock-deterministic",
                        tokens_used=tokens
                    )
                elif "shipping" in task_lower:
                    shipping_fee = 14.99
                    item_price = prices[0] if prices else 85.0
                    return ModelResponse(
                        is_final_answer=False,
                        tool_call=ToolCallRequest(
                            tool_name="calculator",
                            arguments={"operation": "add", "a": item_price, "b": shipping_fee}
                        ),
                        model_name="mock-deterministic",
                        tokens_used=tokens
                    )
                elif len(prices) == 3:
                    # Sum of 3 items
                    sum_two = prices[0] + prices[1]
                    return ModelResponse(
                        is_final_answer=False,
                        tool_call=ToolCallRequest(
                            tool_name="calculator",
                            arguments={"operation": "add", "a": sum_two, "b": prices[2]}
                        ),
                        model_name="mock-deterministic",
                        tokens_used=tokens
                    )
                else:
                    # Default: sum first two items
                    p1 = prices[0] if len(prices) > 0 else 45.0
                    p2 = prices[1] if len(prices) > 1 else 85.0
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
                # Step 3: Final Answer
                summary_items = [f"{item.get('name', 'Product')}: ${float(item.get('price', 0)):.2f}" for item in found_items]
                items_str = ", ".join(summary_items)
                return ModelResponse(
                    is_final_answer=True,
                    final_answer=(
                        f"Found items: {items_str}. "
                        f"The calculated total/result is ${calc_total:.2f}."
                    ),
                    model_name="mock-deterministic",
                    tokens_used=tokens
                )

        # -------------------------------------------------------------
        # Scenario 2: Direct Arithmetic Calculation
        # -------------------------------------------------------------
        if any(w in task_lower for w in ["calculate", "multiply", "add", "subtract", "sum", "+", "*", "-", "/"]):
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
            nums = re.findall(r"[-+]?\d+(?:\.\d+)?", task_lower)
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
        if any(w in task_lower for w in ["refund", "return", "shipping", "warranty", "policy", "faq", "terms", "company", "headquarters", "claim", "airline", "flight", "cancellation"]):
            for step in reversed(history):
                if step.role == "tool" and step.tool_result and step.tool_result.tool_name == "document_search":
                    matches = step.tool_result.data.get("matches", []) if step.tool_result.data else []
                    if matches:
                        doc_id = matches[0].get("document_id", "DOC-UNKNOWN")
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

            # Formulate query based on task keywords
            if "airline" in task_lower or "flight" in task_lower or "cancellation" in task_lower:
                search_query = "airline flight ticket cancellation"
            elif "shipping" in task_lower or "express" in task_lower or "transit" in task_lower:
                search_query = "shipping delivery timeline express international"
            elif "warranty" in task_lower or "claim" in task_lower or "coverage" in task_lower or "spill" in task_lower:
                search_query = "warranty hardware terms coverage claim"
            elif "headquarters" in task_lower or "company" in task_lower:
                search_query = "company overview headquarters Seattle"
            else:
                search_query = "refund return policy 30 days purchase receipt"

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
        # Scenario 4: Structured Data Lookup
        # -------------------------------------------------------------
        if any(w in task_lower for w in ["product", "price", "stock", "category", "prod_", "peripherals", "accessories"]):
            for step in reversed(history):
                if step.role == "tool" and step.tool_result and step.tool_result.tool_name == "data_lookup":
                    matches = step.tool_result.data.get("matches", []) if step.tool_result.data else []
                    if matches:
                        details = []
                        for p in matches:
                            stock_str = "in stock" if p.get("in_stock") else "out of stock (false)"
                            details.append(
                                f"{p.get('name')} (ID: {p.get('id')}, Category: {p.get('category')}, "
                                f"Price: ${p.get('price')}, Stock: {stock_str}, Description: {p.get('description')})"
                            )
                        return ModelResponse(
                            is_final_answer=True,
                            final_answer=f"Found records: {'; '.join(details)}",
                            model_name="mock-deterministic",
                            tokens_used=tokens
                        )
                    return ModelResponse(
                        is_final_answer=True,
                        final_answer="No matching records found in the catalog.",
                        model_name="mock-deterministic",
                        tokens_used=tokens
                    )

            # Build query or product_id or category
            id_match = re.search(r"prod_\d+", task_lower)
            if id_match:
                return ModelResponse(
                    is_final_answer=False,
                    tool_call=ToolCallRequest(
                        tool_name="data_lookup",
                        arguments={"product_id": id_match.group(0)}
                    ),
                    model_name="mock-deterministic",
                    tokens_used=tokens
                )
            elif "category" in task_lower or "accessories" in task_lower or "peripherals" in task_lower:
                cat = "Accessories" if "accessories" in task_lower else "Peripherals"
                return ModelResponse(
                    is_final_answer=False,
                    tool_call=ToolCallRequest(
                        tool_name="data_lookup",
                        arguments={"category": cat}
                    ),
                    model_name="mock-deterministic",
                    tokens_used=tokens
                )
            else:
                mentioned_known = [p for p in KNOWN_PRODUCTS if re.search(r"\b" + re.escape(p.lower()) + r"\b", task_lower)]
                if mentioned_known:
                    q_text = mentioned_known[0]
                elif "quantum" in task_lower or "hoverboard" in task_lower:
                    q_text = "Quantum Hoverboard X9000"
                else:
                    q_text = task
                return ModelResponse(
                    is_final_answer=False,
                    tool_call=ToolCallRequest(
                        tool_name="data_lookup",
                        arguments={"query": q_text}
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
