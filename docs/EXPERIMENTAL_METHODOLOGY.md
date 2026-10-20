# TraceGuard Experimental Methodology

## 1. Research Questions

This research investigates the reliability and resilience of tool-using AI agents through the following primary questions:

1. **RQ1 (Detection Accuracy)**: Can trajectory-based failure detection accurately identify agent failures prior to task completion, and which trajectory features provide the strongest predictive signals?
2. **RQ2 (Recovery Effectiveness)**: Does trajectory-guided, failure-specific recovery significantly improve end-to-end task success compared to an unassisted baseline agent and a naive fixed-retry baseline?
3. **RQ3 (Operational Overhead)**: What are the latency, tool invocation, and token overhead costs incurred by runtime failure detection and targeted recovery?

---

## 2. Experimental Design

### Controlled Task Sets
All comparative evaluations are conducted across identical splits of the 40 benchmark tasks (`v1.0`). To ensure fair comparisons, identical task configurations, tools, and execution environments are provided to each agent mode.

### Controlled Failure Scenarios
TraceGuard injects deterministic failure modes to assess recovery capabilities under repeatable conditions:
- **`transient_tool_failure`**: Tool returns a temporary HTTP 503 / timeout error on initial attempt.
- **`invalid_tool_arguments`**: Model submits invalid types or missing keys.
- **`repeated_tool_calls`**: Agent falls into an unproductive repetitive loop with identical arguments.
- **`missing_evidence`**: Agent attempts to answer without gathering required data points.
- **`incorrect_final_answer`**: Agent proposes an incorrect arithmetic or factual result.

---

## 3. Evaluation Metrics

### Task Success Metrics
- **Verified Success Rate ($SR$)**: Percentage of tasks whose final answer passes deterministic verification against ground-truth criteria:
  $$SR = \frac{\sum \text{Verified Tasks}}{\text{Total Tasks}} \times 100\%$$
- **Absolute Net Lift ($\Delta SR$)**: Absolute percentage-point improvement achieved over baseline:
  $$\Delta SR = SR_{\text{TraceGuard}} - SR_{\text{Baseline}}$$
- **Relative Improvement ($RI$)**:
  $$RI = \frac{SR_{\text{TraceGuard}} - SR_{\text{Baseline}}}{SR_{\text{Baseline}}} \times 100\%$$

### Detection Metrics
Evaluated on trajectory failure classification:
- **Precision**: Proportion of predicted failures that were genuine task failures.
- **Recall**: Proportion of actual task failures successfully flagged by the detector.
- **F1 Score**: Harmonic mean of Precision and Recall.

### Recovery Metrics
- **Recovery Success Rate ($RSR$)**: Proportion of detected failures where the recovery engine successfully restored the agent to a verified task outcome.
- **Mean Recovery Latency**: Additional time spent during recovery interventions.
- **Overhead Multiplier**: Ratio of total tool calls in recovery mode compared to baseline mode.

---

## 4. Statistical Significance Testing

To rigorously confirm that observed improvements are not artifacts of random variation:
1. **McNemar's Test**: Non-parametric test applied to paired binary task outcomes (success/failure) between baseline and TraceGuard. A $p$-value $< 0.05$ indicates statistically significant improvement.
2. **Paired T-Tests**: Applied to continuous operational metrics (execution duration, tool call counts) across paired task runs.
3. **95% Confidence Intervals**: Calculated via Wilson score intervals for binomial success rates.
