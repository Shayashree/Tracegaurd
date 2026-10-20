"""Safe deterministic calculator tool."""
from typing import Literal, Union
from pydantic import BaseModel, Field
from backend.tools.base import BaseTool

class CalculatorArgs(BaseModel):
    operation: Literal["add", "subtract", "multiply", "divide", "+", "-", "*", "/"] = Field(
        ...,
        description="Arithmetic operation to perform"
    )
    a: float = Field(..., description="First operand (number)")
    b: float = Field(..., description="Second operand (number)")

class CalculatorTool(BaseTool):
    name = "calculator"
    description = (
        "Perform basic safe arithmetic operations: addition ('add' or '+'), "
        "subtraction ('subtract' or '-'), multiplication ('multiply' or '*'), "
        "and division ('divide' or '/'). Never executes arbitrary code."
    )
    args_schema = CalculatorArgs

    def _run(self, args: CalculatorArgs) -> dict:
        op = args.operation.lower()
        a = args.a
        b = args.b

        if op in ("add", "+"):
            res = a + b
        elif op in ("subtract", "-"):
            res = a - b
        elif op in ("multiply", "*"):
            res = a * b
        elif op in ("divide", "/"):
            if b == 0:
                raise ZeroDivisionError("Cannot divide by zero.")
            res = a / b
        else:
            raise ValueError(f"Unsupported operation '{args.operation}'")

        # Clean integer representation if whole number
        formatted_result = int(res) if res.is_integer() else round(res, 6)

        return {
            "operation": op,
            "a": a,
            "b": b,
            "result": formatted_result
        }
