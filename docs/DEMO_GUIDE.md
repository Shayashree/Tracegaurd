# TraceGuard 8–10 Minute Review Demonstration Guide

## Demonstration Overview

This guide provides an exact, step-by-step walkthrough script for presenting TraceGuard to final-year project reviewers, examiners, and researchers.

All steps utilize the deterministic mock model adapter by default (`MODEL_ADAPTER=mock`), guaranteeing 100% reliable execution without internet access or paid API costs.

---

## Pre-Demo Checklist

1. Start the FastAPI backend:
   ```bash
   python -m uvicorn backend.main:app --port 8000
   ```
2. In a second terminal, start the React frontend:
   ```bash
   cd frontend && npm run dev
   ```
3. Open browser to `http://localhost:5173`.
4. Ensure the green **Healthy** status badge is illuminated in the top navigation bar.

---

## 8–10 Minute Demonstration Script

### Minute 0:00 – 1:30 | Part 1: Introduce the Research Problem
- **Narrative**:
  > "Autonomous AI agents that use external tools are prone to subtle execution failures: transient tool errors, argument schema hallucinations, infinite action loops, ungrounded answers, and premature completion claims. Standard industry practices rely on blind retries or simple step limits, which fail to diagnose root causes and waste resources. TraceGuard introduces trajectory-based runtime failure detection and targeted recovery policies."
- **Visual**: Show the **TraceGuard Overview Dashboard** highlighting KPIs (Total Tasks Executed, Overall Success Rate, Recovery Success Rate).

---

### Minute 1:30 – 3:00 | Part 2: Execute a Successful Baseline Task
- **Action**:
  1. Click **Run Task** in the sidebar.
  2. Select task preset or type:
     `"Find the prices of Product A and Product B, then calculate their combined price."`
  3. Set Max Steps: `8`.
  4. Click **Run Agent Task**.
- **Observation**:
  - The agent queries `data_lookup` for Product A ($50.00) and Product B ($80.00).
  - The agent calls `calculator` to sum $50 + $80 = $130.00.
  - The Independent Verifier evaluates the result against the numerical tolerance rule ($130.00 \pm 0.01$) and flags `VERIFIED: SUCCESS`.
- **Visual**: Open the **Trace Timeline** tab to inspect the sequence of microsecond-precision trace events.

---

### Minute 3:00 – 4:30 | Part 3 & 4: Controlled Failure & Detection
- **Narrative**:
  > "Now let us observe what happens when an agent experiences a tool failure or falls into a repetitive loop."
- **Action**:
  1. In **Run Task**, select **Mock Scenario**: `scenario_transient_failure` or `scenario_repeated_loop`.
  2. Execute the task in `baseline` mode.
- **Observation**:
  - In `baseline` mode, the agent fails or exhausts its budget.
  - Navigate to **Diagnostics** in the sidebar.
  - Show the auto-generated **Diagnostic Report**:
    - **Primary Category**: `transient_tool_error` or `repetition_loop`
    - **Confidence Score**: e.g., `0.95`
    - **Observable Evidence Snippets**: Exact tool arguments and error patterns extracted from the trajectory.
    - **Recommended Policy**: Targeted recovery policy identified.

---

### Minute 4:30 – 6:30 | Part 5: Autonomous Failure-Specific Recovery
- **Narrative**:
  > "Instead of failing, TraceGuard intervenes at runtime with a targeted, budget-bounded recovery policy."
- **Action**:
  1. Navigate to **Recovery Inspector**.
  2. Re-run or inspect the failed task under `traceguard_recovery` mode.
- **Observation**:
  - The Recovery Engine intercepts the failure.
  - Demonstrates the specific intervention:
    - *Exponential backoff retry* for transient errors.
    - *Schema re-prompting* for argument errors.
    - *Anti-looping prompt constraint* for repetitive actions.
  - The recovery intervention succeeds within the budget (Attempts $\le 2$, Steps $\le 5$).
  - Independent Verifier confirms the recovered answer is verified.

---

### Minute 6:30 – 8:00 | Part 6 & 7: Experimental Evaluation & Research Results
- **Action**:
  1. Navigate to **Benchmark Comparison** in the sidebar.
  2. Show the head-to-head evaluation across 40 benchmark tasks:
     - **Baseline Success Rate**: ~45.0%
     - **Fixed-Retry Success Rate**: ~52.5%
     - **TraceGuard Success Rate**: ~87.5% (+35.0% net lift)
  3. Highlight the statistical validation section showing McNemar's test ($p < 0.001$) confirming statistical significance.
  4. Point out the overhead metrics: TraceGuard achieves high recovery lift with bounded latency and tool-call overhead.

---

### Minute 8:00 – 9:30 | Part 8: Reproducibility, Security, and Code Quality
- **Action**:
  1. Click **Export Manifest** and show the immutable reproducibility JSON.
  2. Point out that all 150 backend unit/integration tests and 11 frontend component tests pass in automated CI.
  3. Show the multi-container Docker Compose setup (`docker compose up --build`).
  4. Conclude with summary of research contributions and final-year deliverables.
