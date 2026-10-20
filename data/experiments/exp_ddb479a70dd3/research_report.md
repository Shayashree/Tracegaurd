# TraceGuard Research Report: Experimental Evaluation (exp_ddb479a70dd3)

**Experiment Identifier:** `exp_ddb479a70dd3`  
**Experiment Type:** `ablation`  
**Benchmark Dataset Version:** `v1.0` (Split: `all`)  
**Configuration Hash:** `b36fd4bc60708b147a4863ff0562c06aad8f321f69547427cffe5ef1e462c4b8`  
**Generated:** `2026-10-20T07:39:00.202+00:00`  

---

## 1. Research Questions
- **RQ1 (Reliability):** Does TraceGuard recovery improve verified task success compared with baseline execution and fixed retry?
- **RQ2 (Failure Detection):** How accurately does the trajectory detector identify the benchmark's predefined failure categories?
- **RQ3 (Recovery Effectiveness):** For tasks that initially fail and are eligible for recovery, how often does the recovery engine produce a verified successful outcome?
- **RQ4 (Efficiency Trade-off):** What additional latency, tool calls, model calls, and cost are associated with TraceGuard?
- **RQ5 (Failure-Specific Performance):** Which failure categories benefit from targeted recovery, and which remain difficult to resolve?
- **RQ6 (Generalization):** Does the detector and recovery policy generalize to held-out test tasks and failure scenarios?

---

## 2. Experimental Setup & Controls
The experiment evaluated **4 agent modes** across **1 repetition(s)** with a maximum step limit of **8 steps** and task timeout ceiling of **30.0 seconds**.

**Experimental Fairness Guarantees:**
1. **Information Isolation:** No hidden benchmark ground truth or expected answers were supplied to the detector or recovery model.
2. **Independent Outcome Verification:** All modes were evaluated using identical, deterministic outcome verification rules.
3. **Uniform Budgets:** All modes operated under documented, equivalent execution limits.
4. **Preservation of Failures:** Initial failures are preserved alongside recovery traces without overwriting.

---

## 3. Comparative Reliability and Efficiency Results (RQ1 & RQ4)
| Agent Mode | Attempted | Initial Success | Verified Final Success | Success Rate (95% CI) | Interventions | Mean Latency | Mean Add'l Latency | Mean Tool Calls |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`baseline`** | 44 | 38 | 38 | **86.4%** | 0 | 1.9 ms | +0.0 ms | +0.00 |
| **`detection_only`** | 44 | 38 | 38 | **86.4%** | 0 | 2.0 ms | +0.0 ms | +0.00 |
| **`fixed_retry`** | 44 | 38 | 38 | **86.4%** | 1 | 1.8 ms | +0.0 ms | +0.02 |
| **`traceguard_recovery`** | 44 | 38 | 38 | **86.4%** | 6 | 2.6 ms | +0.6 ms | +0.05 |

**Comparative Deltas:**
- **Fixed Retry vs Baseline:** +0.00 pp (Latency: -0.1 ms)
- **TraceGuard vs Baseline:** +0.00 pp (Latency: +0.6 ms)
- **TraceGuard vs Fixed Retry:** +0.00 pp

---

## 4. Statistical Hypothesis Testing (Paired Comparisons)
| Comparison | Metric | Sample Size | Difference (pp) | 95% Bootstrap CI | Statistical Test | p-value | Significant (α=0.05)? |
|---|---|:---:|:---:|:---:|---|:---:|:---:|
| **fixed_retry vs baseline** | task_success_rate | 44 | **+0.00** | [+0.00, +0.00] | McNemar (Zero Discordant Pairs) | 1.0000 | No |
| **fixed_retry vs baseline** | mean_latency_ms | 44 | **-0.11** | [-0.36, +0.10] | Paired Bootstrap (1000 resamples) | N/A | No |
| **traceguard_recovery vs baseline** | task_success_rate | 44 | **+0.00** | [+0.00, +0.00] | McNemar (Zero Discordant Pairs) | 1.0000 | No |
| **traceguard_recovery vs baseline** | mean_latency_ms | 44 | **+0.63** | [-0.06, +1.76] | Paired Bootstrap (1000 resamples) | N/A | No |
| **traceguard_recovery vs fixed_retry** | task_success_rate | 44 | **+0.00** | [+0.00, +0.00] | McNemar (Zero Discordant Pairs) | 1.0000 | No |
| **traceguard_recovery vs fixed_retry** | mean_latency_ms | 44 | **+0.74** | [+0.06, +1.83] | Paired Bootstrap (1000 resamples) | N/A | Yes |

**Statistical Notes and Limitations:**
- *fixed_retry vs baseline:* Identical paired outcomes across all 44 tasks. Difference is exactly 0.0 pp. No evidence of differential performance.
- *fixed_retry vs baseline:* Mean latency: fixed_retry (1.83ms) vs baseline (1.94ms). Overhead: -0.11ms (95% bootstrap CI: [-0.36, +0.10]ms).
- *traceguard_recovery vs baseline:* Identical paired outcomes across all 44 tasks. Difference is exactly 0.0 pp. No evidence of differential performance.
- *traceguard_recovery vs baseline:* Mean latency: traceguard_recovery (2.57ms) vs baseline (1.94ms). Overhead: +0.63ms (95% bootstrap CI: [-0.06, +1.76]ms).
- *traceguard_recovery vs fixed_retry:* Identical paired outcomes across all 44 tasks. Difference is exactly 0.0 pp. No evidence of differential performance.
- *traceguard_recovery vs fixed_retry:* Mean latency: traceguard_recovery (2.57ms) vs fixed_retry (1.83ms). Overhead: +0.74ms (95% bootstrap CI: [+0.06, +1.83]ms).

---

## 5. Recovery Effectiveness & Safety Metrics (RQ3)
- **Recovery Success Rate (Eligible Tasks):** 0.0%
- **Recovery Success Rate (All Unsuccessful Tasks):** 0.0%
- **Recovery Intervention Attempt Rate:** 13.6%
- **Unnecessary Intervention Rate (False Alarms on Healthy Tasks):** 0.0%
- **Failure Recurrence Rate:** 16.7%
- **Mean Additional Recovery Latency:** 0.6 ms

---

## 6. Failure-Specific Performance Breakdown (RQ5)
| Category / Failure Mode | Total Tasks | Actual Failures | Detector F1 | Eligible Recov | Recov Attempts | Recov Successes | Recov Success Rate | Assessment |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `arithmetic` | 9 | 0 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `data_lookup` | 9 | 1 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `document_qa` | 9 | 0 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `failure_scenario:incorrect_final_answer` | 1 | 0 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `failure_scenario:invalid_tool_arguments` | 1 | 1 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `failure_scenario:missing_evidence` | 1 | 0 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `failure_scenario:no_matching_record` | 1 | 0 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `failure_scenario:repeated_tool_calls` | 1 | 1 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `failure_scenario:step_limit_exhaustion` | 1 | 1 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `failure_scenario:tool_timeout` | 1 | 1 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `failure_scenario:transient_tool_failure` | 1 | 1 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |
| `multi_step` | 9 | 0 | 100.0% | 0 | 0 | 0 | 0.0% | **INCONCLUSIVE** |

*Analyzed 12 categories across 44 executions. Beneficial: 0, Ineffective: 0, Inconclusive/Neutral: 12.*

---

## 7. Component Ablation Study
| Component Variant | Success Rate | Mean Latency | Mean Tools | Interventions | Marginal Contribution Assessment |
|---|:---:|:---:|:---:|:---:|---|
| **`baseline`** | 86.4% | 1.9 ms | 0.00 | 0 | Baseline agent execution without failure detection or recovery interventions |
| **`detection_only`** | 86.4% | 2.0 ms | 0.00 | 0 | Trajectory failure detection active passively; recovery disabled |
| **`fixed_retry`** | 86.4% | 1.8 ms | 0.02 | 1 | Blind bounded retries on transient errors without diagnosis or replanning |
| **`traceguard_recovery`** | 86.4% | 2.6 ms | 0.05 | 6 | Full system: trajectory diagnosis + targeted failure-specific recovery |

**Marginal Subsystem Contributions:**
- **Trajectory Failure Detection (Passive):** Detection introduces minimal latency overhead (+0.10ms) and 0 execution interventions (delta success rate: +0.00 pp).
- **Blind Fixed Retry:** Fixed retry produced +0.00 pp success change with -0.11ms latency and +0.02 additional tool calls.
- **Failure-Specific Diagnosis & Recovery vs Fixed Retry:** Targeted recovery vs fixed retry delta: +0.00 pp success with +0.74ms additional latency.
- **Full TraceGuard Platform (E2E vs Baseline):** Full TraceGuard produced +0.00 pp overall task success change with +0.63ms total latency overhead.

---

## 8. Generalization to Held-Out Data (RQ6)
Evaluated on dataset split: `all`. For held-out test splits, rules tuned on train/dev sets were executed without parameter alteration. Refer to the failure-specific breakdown for performance on unseen problem instances.

---

## 9. Threats to Validity & Limitations
1. **Internal Validity:** Deterministic synthetic tools and mock LLM fixtures were used to guarantee reproducible execution without non-deterministic API drift.
2. **External Validity:** Synthetic product catalog and arithmetic tasks may not fully capture the complexity of open-ended web navigation or human dialog.
3. **Statistical Power:** Controlled failure benchmarks with small sample sizes ($N < 20$) possess limited power to detect marginal gains; non-significance should not be conflated with equivalence.
4. **Ground-Truth Verification Dependency:** Tasks lacking explicit verification rules strictly produce `unverified` status, which appropriately constrains reported recovery claims.

---

## 10. Conclusions Supported by Evidence
1. **Reliability Impact:** TraceGuard recovery achieved a **86.4%** verified success rate compared to **86.4%** for baseline (+0.00 pp) and **86.4%** for fixed retry (+0.00 pp).
2. **Overhead Profile:** Trajectory diagnosis and bounded recovery introduced measurable but controlled latency without triggering runaway execution or infinite retry loops.
3. **Intervention Safety:** Zero false alarms were observed on healthy, verified tasks, confirming that recovery policies respect diagnostic gates and preserve healthy trajectories.

---

## 11. Reproducibility Instructions
To reproduce this exact experiment:
```bash
# Run Experiment exp_ddb479a70dd3 via CLI
python -m backend.evaluation.experiment_runner --config-hash b36fd4bc60708b147a4863ff0562c06aad8f321f69547427cffe5ef1e462c4b8
```
**Reproducibility Manifest:** Artifact `exp_ddb479a70dd3_manifest.json` (Canonical Hash: `b36fd4bc60708b147a4863ff0562c06aad8f321f69547427cffe5ef1e462c4b8`).