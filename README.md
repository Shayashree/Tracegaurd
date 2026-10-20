# TraceGuard: An Evidence-Driven Reliability and Recovery Platform for Tool-Using AI Agents

**Milestones 1–5: Baseline Agent, Benchmark Framework, Trajectory Failure Detector, Failure-Specific Recovery Engine, & Experimental Evaluation Framework**

TraceGuard is a research and reliability engineering platform designed for autonomous, tool-using AI agents.

- **Milestone 1** established the modular baseline agent architecture: task planning, deterministic tool execution, observable trace event recording, and deterministic outcome verification.
- **Milestone 2** introduced a reproducible, versioned benchmark dataset (44 tasks across 5 categories), a failure-injection framework covering 8 controlled failure modes, an experiment execution runner, robust evaluation metrics with Wilson score confidence intervals, and machine-readable experiment export endpoints.
- **Milestone 3** delivered a modular, trajectory-based failure detection engine (`backend/reliability/`) that extracts deterministic execution features, evaluates explainable detection rules (R1–R9), distinguishes observable failure patterns from unverified completions, supports both offline and live passive observation, and calculates detection precision, recall, and F1 metrics.
- **Milestone 4** implemented an intelligent, bounded, failure-specific recovery engine (`backend/reliability/`) that consumes Milestone 3 diagnostic reports, selects and executes targeted recovery policies (Policies A–H), enforces multi-dimensional safety budgets, safely checkpoints state with strict credential redaction, records recovery event trajectories, and independently verifies post-recovery outcomes.
- **Milestone 5** introduces a comprehensive, reproducible experimental evaluation and statistical comparative analysis framework (`backend/evaluation/`) answering 6 core research questions (RQ1–RQ6) across 5 experiment types (`standard`, `controlled_failure`, `held_out`, `repeated_stability`, `ablation`), evaluating paired hypothesis tests (McNemar exact and asymptotic Chi-Square, bootstrap confidence intervals), computing failure-specific category breakdowns, generating audit-grade reproducibility manifests, and assembling publication-ready Markdown research reports from persisted database records.

---

## 1. System Architecture

TraceGuard is organized into modular, decoupled packages:

```
traceguard/
├── backend/
│   ├── agents/
│   │   ├── controller.py        # Baseline Agent execution loop & passive observation hook
│   │   ├── model_adapter.py     # BaseModelAdapter interface & OpenAI live adapter
│   │   ├── mock_model.py        # Deterministic mock adapter (zero API credentials required)
│   │   └── tool_registry.py     # ToolRegistry & ToolExecutor with validation & schema dispatch
│   ├── tools/
│   │   ├── base.py              # BaseTool interface with Pydantic argument validation
│   │   ├── calculator.py        # Safe arithmetic tool (rejects eval and division by zero)
│   │   ├── data_lookup.py       # Local product catalog query & exact ID lookup
│   │   └── document_search.py   # Document library passage & evidence retrieval
│   ├── tracing/
│   │   ├── event_schema.py      # Structured event schema (25 events) & credential redactor
│   │   ├── collector.py         # Observable execution trace recorder & recovery event tracer
│   │   └── storage.py           # SQLite persistence, migrations, JSONL export, and artifact storage
│   ├── verification/
│   │   └── verifier.py          # Deterministic outcome verification framework
│   ├── reliability/             # [Milestones 3 & 4: Diagnosis & Recovery Subsystem]
│   │   ├── detector_config.py   # Configurable thresholds and detector parameters
│   │   ├── diagnostic_report.py # Structured schemas (DiagnosticReport, DiagnosticFinding, enums)
│   │   ├── feature_extractor.py # Deterministic feature extraction & stable argument normalizer
│   │   ├── failure_rules.py     # Explainable rules R1-R9 with evidence references
│   │   ├── failure_classifier.py# Diagnostic synthesis, severity ranking, and primary category
│   │   ├── failure_detector.py  # TrajectoryFailureDetector (offline analysis & live hook)
│   │   ├── recovery_report.py   # Recovery enums, attempt records, and structured report schemas
│   │   ├── recovery_budget.py   # Centralized multi-dimensional recovery budget tracker
│   │   ├── recovery_state.py    # RecoveryStateManager & recursive credential-sanitizing checkpointing
│   │   ├── recovery_policy.py   # Explainable rule-based PolicySelector (Policies A-H)
│   │   ├── recovery_actions.py  # Safe, bounded recovery action implementations
│   │   ├── recovery_verifier.py # Independent post-recovery outcome verifier & terminal status mapper
│   │   └── recovery_engine.py   # RecoveryEngine (diagnosis-driven) & FixedRetryEngine (baseline)
│   ├── evaluation/              # [Milestones 2 & 5: Benchmark & Experimental Evaluation]
│   │   ├── schemas.py           # Schemas for benchmark tasks, experiments, and metrics
│   │   ├── dataset.py           # BenchmarkDatasetLoader (JSONL loader, train/val/test splits)
│   │   ├── failure_injection.py # InjectedToolExecutor & InjectedModelAdapter (8 failure modes)
│   │   ├── statistics.py        # Wilson score confidence intervals & percentile distributions
│   │   ├── metrics.py           # Baseline agent evaluation metrics (success, accuracy, efficiency)
│   │   ├── detector_metrics.py  # Detector evaluation metrics (precision, recall, F1, confusion)
│   │   ├── recovery_metrics.py  # Comprehensive recovery metrics & comparative delta statistics
│   │   ├── experiment_config.py # [M5] Versioned ExperimentConfig & canonical SHA-256 hashing
│   │   ├── statistical_tests.py # [M5] McNemar paired test (exact & Chi2), bootstrap CIs, Bonferroni
│   │   ├── failure_analysis.py  # [M5] Cross-category failure aggregation & assessment
│   │   ├── ablation_analysis.py # [M5] Marginal component contribution decomposition
│   │   ├── manifest.py          # [M5] Audit-grade reproducibility manifest & environment capture
│   │   ├── report_generator.py  # [M5] Automated publication-ready Markdown research report generator
│   │   ├── benchmark_runner.py  # BenchmarkRunner orchestrator for execution and metrics
│   │   └── experiment_runner.py # [M5] FullExperimentRunner orchestrating multi-mode evaluations
│   ├── models/
│   │   └── schemas.py           # Pydantic models for tasks, tools, traces, and API requests
│   ├── api/
│   │   ├── tasks.py             # REST endpoints: POST /tasks, GET /tasks/{id}
│   │   ├── traces.py            # REST endpoints: GET traces and JSONL export
│   │   ├── benchmarks.py        # REST endpoints: GET /benchmarks, GET /benchmarks/{v}/tasks
│   │   ├── experiments.py       # [M5] REST endpoints: POST run, GET results/metrics/comparisons/ablation/manifest/report/export
│   │   ├── diagnostics.py       # REST endpoints: POST /diagnostics/run, GET diagnostics & metrics
│   │   └── recovery.py          # REST endpoints: POST /tasks/{id}/recover, GET recovery reports
│   ├── config.py                # Environment configuration using pydantic-settings
│   └── main.py                  # FastAPI application entrypoint with health & CORS
├── data/
│   ├── products.json            # Synthetic product catalog dataset
│   ├── documents/               # Local markdown and text knowledge documents
│   ├── benchmarks/
│   │   └── benchmark_v1.jsonl   # 44 versioned benchmark tasks across 5 categories
│   └── experiments/             # Experiment outputs (reports, manifests, exports)
├── tests/
│   ├── test_tools.py            # Unit tests for Calculator, Data Lookup, & Doc Search
│   ├── test_agent_controller.py # Multi-step execution, limits, and error handling
│   ├── test_tracing.py          # Trace schemas, ordering, redaction, & JSONL
│   ├── test_verifier.py         # Numerical, field, and evidence verification
│   ├── test_api.py              # Tasks & traces API endpoint tests
│   ├── test_benchmark_dataset.py# Benchmark dataset loading, schema validation, & filtering
│   ├── test_failure_injection.py# All 8 controlled failure injection scenarios
│   ├── test_evaluation_metrics.py# Metric calculations, Wilson CI, percentiles, zero denominators
│   ├── test_benchmark_runner.py # Execution, category filters, repetitions, & reproducibility
│   ├── test_api_experiments.py # API endpoints for benchmarks and experiment runs
│   ├── test_feature_extractor.py# Deterministic feature extraction and canonical argument normalizer
│   ├── test_failure_detector.py # All failure categories, rules R1-R9, persistence, passive hook
│   ├── test_detector_metrics.py # Precision, recall, F1, confusion matrices, dataset splits
│   ├── test_api_diagnostics.py  # Diagnostics REST API endpoints integration tests
│   ├── test_recovery_policies.py# Failure-specific recovery policies A-H & safety constraints
│   ├── test_recovery_engine.py  # RecoveryEngine workflow, FixedRetryEngine, checkpoints, & persistence
│   ├── test_recovery_metrics.py # Recovery formulas, denominators, comparative deltas, & zero safety
│   ├── test_api_recovery.py     # Recovery REST API endpoints integration tests
│   ├── test_experiment_config.py# [M5] ExperimentConfig validation & canonical SHA-256 hashing
│   ├── test_statistical_tests.py# [M5] McNemar tests, exact binomial p-values, paired bootstrap CIs
│   ├── test_failure_analysis.py # [M5] Cross-category breakdown, TP/FP/FN detection, recovery assessment
│   ├── test_ablation_analysis.py# [M5] Component marginal decomposition across 4 variants
│   ├── test_report_manifest.py  # [M5] Manifest credential sanitization & research report generation
│   ├── test_experiment_runner.py# [M5] FullExperimentRunner comparative and ablation workflows
│   └── test_api_milestone5.py   # [M5] Milestone 5 REST API integration tests
├── demo.py                      # Interactive CLI task demonstration runner
├── demo_benchmark.py            # Comparative evaluation & trajectory recovery demo runner
├── run_experiments.py           # [M5] CLI experiment runner & research report generator
├── verify_api.py                # Live HTTP server verification test script
├── requirements.txt             # Project dependencies
└── README.md                    # Project documentation
```

---

## 2. Experimental Research Questions (Milestone 5)

TraceGuard Milestone 5 formalizes and evaluates 6 fundamental research questions:

- **RQ1 — Reliability:** Does trajectory-based failure detection combined with failure-specific recovery improve verified task success compared with a baseline agent and a fixed-retry strategy?
- **RQ2 — Failure Detection:** How accurately does the trajectory detector identify the benchmark's predefined failure categories (precision, recall, F1, false-alarm rate)?
- **RQ3 — Recovery Effectiveness:** For tasks that initially fail and are eligible for recovery, how often does the recovery engine produce an independently verified successful outcome?
- **RQ4 — Efficiency Trade-offs:** What additional latency, tool calls, model calls, and cost are associated with trajectory diagnosis and recovery?
- **RQ5 — Failure-Specific Performance:** Which failure categories benefit from targeted recovery, and which remain difficult or impossible to resolve?
- **RQ6 — Generalization:** Does the detector and recovery policy generalize to held-out test tasks and failure variations not used during development?

---

## 3. Experimental Protocol & Experiment Types

TraceGuard supports 5 distinct experimental protocols executed through [`backend/evaluation/experiment_runner.py`](file:///d:/1C%20Project/backend/evaluation/experiment_runner.py):

1. **`standard` (Standard Benchmark):** Runs all available benchmark tasks without deliberate failure injection to establish baseline task success, normal latency overhead, and false-alarm intervention rates.
2. **`controlled_failure` (Controlled Failure Benchmark):** Evaluates tasks under 8 predefined controlled failure scenarios (transient tool failure, invalid arguments, repeated tool calls, missing evidence, incorrect answer, step-limit exhaustion, tool timeout, no matching record).
3. **`held_out` (Held-Out Test Split):** Evaluates the system on held-out tasks and unseen failure variations (`test` split) without tuning rules or thresholds against test data.
4. **`repeated_stability` (Repeated-Run Stability):** Executes selected tasks multiple times under identical deterministic configurations to verify output stability and tool sequence consistency.
5. **`ablation` (Component Ablation Study):** Evaluates 4 systematic subsystem variants to isolate the individual contributions of diagnosis and recovery:
   - `baseline`: No failure detection, no recovery interventions.
   - `detection_only`: Passive trajectory diagnosis active; recovery interventions disabled.
   - `fixed_retry`: Blind bounded retries on transient tool errors without diagnosis or replanning.
   - `traceguard_recovery`: Full trajectory diagnosis + targeted failure-specific recovery policies.

### Experimental Fairness Controls
- **Information Isolation:** No hidden benchmark ground truth, expected answers, or labels are supplied to the detector or recovery model (Policy E isolates expected values).
- **Independent Outcome Verification:** All modes are evaluated using identical, deterministic outcome verification rules.
- **Budget Parity:** All agent modes operate under strictly documented, equivalent execution limits.
- **Trace & Failure Preservation:** Initial failure trajectories and diagnostics are preserved alongside recovery traces without overwriting.

---

## 4. Statistical Methodology

Implemented in [`backend/evaluation/statistical_tests.py`](file:///d:/1C%20Project/backend/evaluation/statistical_tests.py):

### 4.1 Paired Binary Outcome Comparison (McNemar's Test)
For paired task success outcomes between two agent modes on the exact same $N$ benchmark tasks:
- **Contingency Table of Discordant Pairs:**
  - $b$: Mode A succeeded, Mode B failed
  - $c$: Mode A failed, Mode B succeeded
  - Total discordant pairs $d = b + c$.
- **Exact Binomial Test ($d < 25$):** When the number of discordant pairs is small ($d < 25$), calculates the exact two-sided binomial p-value under $H_0: p = 0.5$ using pure Python combinatorics.
- **Asymptotic Chi-Square Test ($d \ge 25$):** When $d \ge 25$, computes the McNemar statistic with Edwards continuity correction:
  $$\chi^2 = \frac{(|b - c| - 1)^2}{b + c}, \quad \text{df} = 1$$
  and evaluates p-values via the survival function $\text{erfc}(z/\sqrt{2})$.
- **Zero Discordant Pairs:** When $b + c = 0$, outcomes are identical on all tasks; difference is exactly $0.0$ pp and $p = 1.0000$.

### 4.2 Paired Bootstrap Confidence Intervals
Computes 95% bootstrap percentile confidence intervals (1,000 resamples with deterministic seed) for:
- Absolute percentage-point differences in verified task success rate ($\Delta \text{pp} = \text{rate}_B - \text{rate}_A$).
- Latency overhead differences ($\Delta \text{latency} = \text{mean}_B - \text{mean}_A$).

### 4.3 Multi-Comparison Corrections
Reports both unadjusted p-values and Bonferroni-corrected significance thresholds ($\alpha_{adj} = 0.05 / k$, where $k$ is the number of paired comparisons performed) to prevent family-wise error inflation.

---

## 5. Failure-Specific Breakdown & Component Ablation

- **Failure Analysis ([`backend/evaluation/failure_analysis.py`](file:///d:/1C%20Project/backend/evaluation/failure_analysis.py)):** Groups tasks by category and controlled failure mode, reporting eligible tasks, actual failures, detector precision/recall/F1, recovery attempts, verified recovery successes, recovery success rate, and structured assessment (`beneficial`, `neutral`, `ineffective`, `inconclusive`).
- **Ablation Analysis ([`backend/evaluation/ablation_analysis.py`](file:///d:/1C%20Project/backend/evaluation/ablation_analysis.py)):** Decomposes marginal contributions across subsystems:
  - Marginal overhead of detection alone (passive diagnostic latency, zero mutations).
  - Marginal gain of blind fixed retry vs baseline.
  - Marginal gain of failure-specific recovery vs fixed retry.
  - Full platform end-to-end contribution vs baseline.

---

## 6. Audit-Grade Reproducibility & Research Reporting

- **Canonical Configuration Hashing ([`backend/evaluation/experiment_config.py`](file:///d:/1C%20Project/backend/evaluation/experiment_config.py)):** Computes a deterministic SHA-256 hash from a sorted canonical JSON representation of the configuration with credentials strictly redacted.
- **Reproducibility Manifest ([`backend/evaluation/manifest.py`](file:///d:/1C%20Project/backend/evaluation/manifest.py)):** Captures execution limits, model/tool configs, random seed, environment info (Python version, OS platform, CPU, Git commit SHA), installed package versions, and artifact references.
- **Automated Research Report Generator ([`backend/evaluation/report_generator.py`](file:///d:/1C%20Project/backend/evaluation/report_generator.py)):** Assembles a comprehensive, publication-ready Markdown research report directly from persisted SQLite database records answering RQ1–RQ6 with full tables, statistical tests, limitations, and threats to validity.

---

## 7. REST API Reference (Milestone 5 Extensions)

TraceGuard provides a comprehensive FastAPI REST API for experiment execution, results querying, statistical analysis, and artifact export:

| HTTP Method | Endpoint | Description |
|---|---|---|
| `POST` | `/experiments/run` | Execute an experiment using `ExperimentConfig` (Milestone 5) or `ExperimentRunRequest` (Milestones 2–4). |
| `GET` | `/experiments/{id}` | Retrieve experiment metadata, status, task count, and completion timestamps. |
| `GET` | `/experiments/{id}/results` | Retrieve paginated task execution results (`limit`, `offset`, optional `mode` filter). |
| `GET` | `/experiments/{id}/metrics` | Retrieve aggregated reliability, accuracy, efficiency, and failure distribution metrics. |
| `GET` | `/experiments/{id}/recovery-metrics` | Retrieve recovery success rates (eligible vs all unsuccessful), attempt rates, and overheads. |
| `GET` | `/experiments/{id}/comparisons` | Retrieve paired McNemar statistical hypothesis tests and bootstrap confidence intervals. |
| `GET` | `/experiments/{id}/failure-analysis` | Retrieve granular results grouped by failure category and controlled scenario. |
| `GET` | `/experiments/{id}/ablation` | Retrieve component ablation study results decomposing marginal contributions. |
| `GET` | `/experiments/{id}/report` | Retrieve the generated publication-ready Markdown research report. |
| `GET` | `/experiments/{id}/manifest` | Retrieve the immutable reproducibility manifest with sanitized credentials. |
| `GET` | `/experiments/{id}/export` | Export experiment records as JSON (`?format=json`) or JSON Lines (`?format=jsonl`). |

---

## 8. How to Run Experiments & Test Suite

### 1. Run Complete Automated Test Suite (143 tests)
All 143 unit and integration tests across Milestones 1–5 run fully offline without external API keys:
```bash
python -m pytest -v
```

### 2. Run Experiments via CLI (`run_experiments.py`)

```bash
# Run 4-mode component ablation experiment across all 44 benchmark tasks
python run_experiments.py --type ablation

# Run controlled failure scenarios benchmark
python run_experiments.py --type controlled_failure --category failure_scenario

# Run held-out generalization benchmark on test split
python run_experiments.py --type held_out --split held_out

# Run standard comparative experiment on specific categories
python run_experiments.py --type standard --category arithmetic --modes baseline traceguard_recovery
```

All experiment runs automatically persist task results, trace events, diagnostic reports, recovery reports, statistical comparisons, reproducibility manifests, and research reports to `data/traceguard.db` and export artifacts to `data/experiments/{experiment_id}/`.

---

## 9. Actual Experimental Evaluation Results (Real Data)

The following metrics represent actual empirical measurements obtained from a complete 4-mode ablation experiment across the entire 44-task benchmark dataset (`exp_ddb479a70dd3`):

### 9.1 Comparative Reliability and Efficiency Summary (All 44 Benchmark Tasks)

| Agent Mode | Attempted | Initial Success | Verified Final Success | Success Rate (Wilson 95% CI) | Interventions | Mean Latency | Mean Add'l Latency | Mean Tool Calls |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **`baseline`** | 44 | 38 | 38 | **86.4%** [73.3%, 93.6%] | 0 | 1.9 ms | +0.0 ms | +0.00 |
| **`detection_only`** | 44 | 38 | 38 | **86.4%** [73.3%, 93.6%] | 0 | 2.0 ms | +0.0 ms | +0.00 |
| **`fixed_retry`** | 44 | 38 | 38 | **86.4%** [73.3%, 93.6%] | 1 | 1.8 ms | +0.0 ms | +0.02 |
| **`traceguard_recovery`** | 44 | 38 | 38 | **86.4%** [73.3%, 93.6%] | 6 | 2.6 ms | +0.6 ms | +0.05 |

### 9.2 Paired Statistical Hypothesis Testing (McNemar & Paired Bootstrap)

| Comparison | Metric | Sample Size | Difference (pp) | 95% Bootstrap CI | Statistical Test | p-value | Significant (α=0.05)? |
|---|---|:---:|:---:|:---:|---|:---:|:---:|
| **`fixed_retry` vs `baseline`** | task_success_rate | 44 | **+0.00** | [+0.00, +0.00] | McNemar (Zero Discordant Pairs) | 1.0000 | No |
| **`fixed_retry` vs `baseline`** | mean_latency_ms | 44 | **-0.11** | [-0.36, +0.10] | Paired Bootstrap (1000 resamples) | N/A | No |
| **`traceguard_recovery` vs `baseline`** | task_success_rate | 44 | **+0.00** | [+0.00, +0.00] | McNemar (Zero Discordant Pairs) | 1.0000 | No |
| **`traceguard_recovery` vs `baseline`** | mean_latency_ms | 44 | **+0.63** | [-0.06, +1.76] | Paired Bootstrap (1000 resamples) | N/A | No |
| **`traceguard_recovery` vs `fixed_retry`** | task_success_rate | 44 | **+0.00** | [+0.00, +0.00] | McNemar (Zero Discordant Pairs) | 1.0000 | No |
| **`traceguard_recovery` vs `fixed_retry`** | mean_latency_ms | 44 | **+0.74** | [+0.06, +1.83] | Paired Bootstrap (1000 resamples) | N/A | Yes |

### 9.3 Component Ablation Decomposition

| Component Variant | Success Rate | Mean Latency | Mean Add'l Tools | Interventions | Marginal Contribution Assessment |
|---|:---:|:---:|:---:|:---:|---|
| **`baseline`** | 86.4% | 1.9 ms | 0.00 | 0 | Baseline agent execution without failure detection or recovery interventions |
| **`detection_only`** | 86.4% | 2.0 ms | 0.00 | 0 | Passive detection introduces negligible latency (+0.10 ms) with zero state mutations |
| **`fixed_retry`** | 86.4% | 1.8 ms | +0.02 | 1 | Fixed retry produced +0.00 pp success change with -0.11 ms latency and +0.02 tool calls |
| **`traceguard_recovery`** | 86.4% | 2.6 ms | +0.05 | 6 | Full targeted recovery introduced +0.63 ms latency overhead without runaway retries |

### 9.4 Key Empirical Findings & Honest Assessment
1. **Measured Safety & Zero False Alarms:** The recovery engine triggered zero false-alarm interventions on healthy, verified tasks, respecting diagnostic gates and preserving healthy trajectories.
2. **Sub-Millisecond Passive Diagnostic Overhead:** Trajectory feature extraction and rule evaluation added only **+0.10 ms** mean latency overhead in `detection_only` mode.
3. **Statistical Inconclusiveness on Small Synthetic Benchmarks:** Across the 44 deterministic tasks, all 3 comparison modes produced identical overall verified success rates (86.4%), resulting in zero discordant pairs ($p = 1.0000$). The framework honestly reports non-significance rather than fabricating claims of superiority.
4. **Controlled Recovery Overhead:** Targeted failure-specific recovery added only **+0.63 ms** mean latency overhead and **+0.05** additional tool calls per task, strictly bounded by the multi-dimensional recovery budget.

---

### Milestone 6: Interactive Dashboard, Backend Integration, and Research Visualization (Completed)
- **Modern Full-Stack Web Application:** High-performance React 19 + TypeScript + Vite + Tailwind CSS v4 dashboard providing transparent visibility into agent reliability, trajectories, failure diagnostics, targeted recovery, and statistical evaluations.
- **10 Dedicated Research Pages:**
  1. **Overview Dashboard:** Platform-wide KPI cards, mode-by-mode verified success comparisons, empirical failure distribution bar charts, latency overhead distributions, and recent experiment logs.
  2. **Experiments Registry:** Real-time database inspection with search, mode/status filtering, pagination, and drill-down into task execution records.
  3. **Run Experiment Wizard:** Multi-section experiment configuration interface supporting benchmark versioning, task selection (all, category, or cherry-picked IDs), controlled failure injection, agent mode selection (`baseline`, `fixed_retry`, `traceguard_recovery`), step/timeout constraints, duplicate submission guards, and bounded progress tracking.
  4. **Execution Trace Explorer:** Chronological step-by-step observable trajectory viewer with event type / tool filters, error highlights, recovery event badges, structured input/output previews, and one-click JSONL export.
  5. **Failure Diagnostics Explorer:** Complete F1–F9 taxonomy findings with deterministic/heuristic certainty status (`confirmed`, `suspected`), severity classification, linked evidence event IDs, and ground-truth detector evaluation metrics ($P$, $R$, $F_1$, latency).
  6. **Recovery Analysis:** Complete 7-stage lifecycle visualization (Trajectory → Diagnosis → Policy Selection → Budget Check → Intervention → Re-execution → Verification), policy selection rationales (Policies A–H), multi-dimensional budget consumption, and verifier proof.
  7. **Strategy Comparison:** Rigorous paired statistical evaluations (Baseline vs. Fixed Retry vs. TraceGuard Recovery) computing Wilson 95% confidence intervals, absolute/relative gains, Edwards continuity-corrected McNemar $\chi^2$ and exact binomial hypothesis tests ($p < 0.05$).
  8. **Research Evaluation & Ablation:** Systematic evaluation of research questions RQ1–RQ6, 4-way component ablation decomposition (`baseline`, `detection_only`, `fixed_retry`, `traceguard_recovery`), and automated empirical metric interpretation.
  9. **Reports & Exports:** Formatted Markdown research report viewer, SHA-256 reproducibility manifest inspector, and direct download links for JSON, JSONL, and Markdown research artifacts.
  10. **Settings & Configuration:** Live backend health status, active model adapter parameters, detector thresholds, default recovery budget bounds, and registered tool capabilities.

---

## 10. Startup and Run Instructions

### 10.1 Prerequisites
- **Python**: 3.11+
- **Node.js**: 18+ (tested on Node v24.14.0, npm 11.9.0)

### 10.2 Installation

#### Backend
```bash
# Clone or navigate to the repository
cd traceguard

# Install Python backend dependencies
pip install -r requirements.txt
```

#### Frontend
```bash
# Navigate to the frontend directory
cd frontend

# Install frontend dependencies
npm install
```

### 10.3 Configuration
Backend configuration is managed via environment variables (or `.env` file):
```bash
# Example .env (no secrets required for local deterministic mode)
MODEL_ADAPTER=mock
DEFAULT_MAX_STEPS=10
DATABASE_PATH=data/traceguard.db
LOG_LEVEL=INFO
```

Frontend configuration (optional override in `frontend/.env`):
```bash
VITE_API_BASE_URL=http://127.0.0.1:8000
```
*(By default, Vite's internal development server proxy automatically forwards `/health`, `/experiments`, `/tasks`, `/benchmarks`, `/diagnostics`, and `/recovery` to `http://127.0.0.1:8000`).*

### 10.4 Starting the Application

#### Step 1: Start the FastAPI Backend
From the repository root:
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
The backend API and Swagger OpenAPI documentation will be available at:
- **API Health Check:** `http://127.0.0.1:8000/health`
- **Interactive OpenAPI Docs:** `http://127.0.0.1:8000/docs`

#### Step 2: Start the React Frontend Dashboard
In a separate terminal:
```bash
cd frontend
npm run dev
```
Open your browser to:
- **Dashboard URL:** `http://localhost:5173`

### 10.5 Running Test Suites

#### Backend Test Suite (Milestones 1–5 regression test suite)
```bash
# Run all 143 backend tests
python -m pytest
```

#### Frontend Test Suite (Components, layout, and API client)
```bash
cd frontend
npm test
```

#### Frontend Production Build
```bash
cd frontend
npm run build
```

---

## 11. Known Limitations & Research Threats to Validity

1. **Synthetic Deterministic Fixtures:** Core experiments utilize deterministic mock tools and local models to ensure reproducible, zero-cost benchmarking without network drift or external API rate limits.
2. **Stateless Tool Environments:** Benchmark tools operate in-memory; evaluating stateful real-world environments (e.g. bash file mutations, production database commits) requires sandboxed transactional rollback.
3. **Paired Statistical Sample Size Requirements:** Paired hypothesis testing requires running multi-mode evaluations over identical benchmark task sets. When evaluating single-mode runs, comparative metrics indicate that a paired baseline is required.
