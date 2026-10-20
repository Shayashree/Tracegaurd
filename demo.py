"""Demonstration script showcasing TraceGuard Baseline Agent capabilities."""
import json
from backend.agents.controller import AgentController
from backend.models.schemas import TaskCreateRequest, VerificationRule
from backend.tracing.storage import TraceStorage

def run_demo():
    print("=" * 80)
    print(" TraceGuard Milestone 1: Baseline AI Agent Demonstration")
    print("=" * 80)

    storage = TraceStorage("traceguard.db")
    controller = AgentController(storage=storage)

    demos = [
        {
            "name": "Demo 1: Multi-Step Task (Data Lookup + Calculator + Verification)",
            "request": TaskCreateRequest(
                task="Find the prices of Product A and Product B, then calculate their combined price.",
                verification_rule=VerificationRule(type="numerical_tolerance", expected_value=130.0, tolerance=0.01)
            )
        },
        {
            "name": "Demo 2: Direct Calculation Task",
            "request": TaskCreateRequest(
                task="Calculate 25 * 4",
                verification_rule=VerificationRule(type="numerical_tolerance", expected_value=100.0)
            )
        },
        {
            "name": "Demo 3: Document Question (Knowledge Base Policy Search)",
            "request": TaskCreateRequest(
                task="What is the return policy for purchases?",
                verification_rule=VerificationRule(
                    type="evidence_reference",
                    required_snippets=["DOC-REFUND-001", "30 days"]
                )
            )
        },
        {
            "name": "Demo 4: Controlled Tool Error Handling (Division by Zero)",
            "request": TaskCreateRequest(
                task="Divide 100 by 0",
                mock_scenario="division_by_zero"
            )
        },
        {
            "name": "Demo 5: Step Limit Bound Enforcement",
            "request": TaskCreateRequest(
                task="Run endless loop to trigger step limit",
                max_steps=4,
                mock_scenario="infinite_loop"
            )
        }
    ]

    for i, demo in enumerate(demos, 1):
        print(f"\n[{i}] {demo['name']}")
        print(f"Task Prompt: '{demo['request'].task}'")
        resp = controller.run_task(demo["request"])
        print(f"Status      : {resp.status}")
        print(f"Steps Count : {resp.steps_count}")
        print(f"Duration    : {resp.duration_ms:.2f} ms")
        print(f"Final Answer: {resp.final_answer or resp.error_info}")
        if resp.verification:
            print(f"Verification: {resp.verification.status.upper()} (Method: {resp.verification.verification_method})")
            print(f"Message     : {resp.verification.verification_message}")

        # Show observable traces
        events = storage.get_events(resp.task_id)
        print("Observable Traces:")
        for ev in events:
            summary = ev.output_summary or ev.input_summary or ""
            if len(summary) > 60:
                summary = summary[:57] + "..."
            print(f"  - Step {ev.step_index:02d} | {ev.event_type:<26} | Status: {ev.status:<10} | {summary}")

    print("\n" + "=" * 80)
    print(" Demonstrations completed successfully!")
    print("=" * 80)

if __name__ == "__main__":
    run_demo()
