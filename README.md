# TraceGuard: An Evidence-Driven Reliability and Recovery Platform for Tool-Using AI Agents

**Milestone 1 & 2: Baseline Agent, Benchmark Dataset & Evaluation Framework**

TraceGuard is a research and reliability engineering platform designed for autonomous, tool-using AI agents. 

- **Milestone 1** established the modular baseline agent architecture: task planning, deterministic tool execution, observable trace event recording, and deterministic outcome verification.
- **Milestone 2** introduces a reproducible, versioned benchmark dataset (44 tasks across 5 categories), a failure-injection framework covering 8 controlled failure modes, an experiment execution runner, robust evaluation metrics with Wilson score confidence intervals, and machine-readable experiment export endpoints.

---

## 1. System Architecture

TraceGuard is organized into modular, extensible packages:

```
traceguard/
├── backend/
│   ├── agents/
│   │   ├── controller.py        # Baseline Agent execution loop & bounded lifecycle
│   │   ├── model_adapter.py     # BaseModelAdapter interface & OpenAI live adapter
│   │   ├── mock_model.py        # Deterministic mock adapter (zero API credentials required)
│   │   └── tool_registry.py     # ToolRegistry & ToolExecutor with validation & dispatch
│   ├── tools/
│   │   ├── base.py              # BaseTool interface with Pydantic argument validation
│   │   ├── calculator.py        # Safe arithmetic tool (rejects eval and division by zero)
│   │   ├── data_lookup.py       # Local product catalog query & exact ID lookup
│   │   └── document_search.py   # Document library passage & evidence retrieval
│   ├── tracing/
│   │   ├── event_schema.py      # Structured event schema & credential redactor
│   │   ├── collector.py         # Passive observable execution trace recorder
│   │   └── storage.py           # SQLite database persistence & JSONL export
│   ├── verification/
│   │   └── verifier.py          # Deterministic outcome verification framework
│   ├── evaluation/
│   │   ├── schemas.py           # Pydantic schemas for benchmark tasks, experiments, & metrics
│   │   ├── dataset.py           # BenchmarkDatasetLoader (JSONL loader, schema validation, filters)
│   │   ├── failure_injection.py # InjectedToolExecutor & InjectedModelAdapter (8 failure modes)
│   │   ├── statistics.py        # Wilson score confidence intervals & percentile distributions
│   │   ├── metrics.py           # Metrics calculation engine (success, accuracy, efficiency, errors)
│   │   └── benchmark_runner.py  # BenchmarkRunner orchestrator (task execution, metrics, persistence)
│   ├── models/
│   │   └── schemas.py           # Pydantic models for tasks, tools, traces, and API requests
│   ├── api/
│   │   ├── tasks.py             # REST endpoints: POST /tasks, GET /tasks/{id}
│   │   ├── traces.py            # REST endpoints: GET traces and JSONL export
│   │   ├── benchmarks.py        # REST endpoints: GET /benchmarks, GET /benchmarks/{v}/tasks
│   │   └── experiments.py       # REST endpoints: POST /experiments/run, GET /experiments/{id}/*
│   ├── config.py                # Environment configuration using pydantic-settings
│   └── main.py                  # FastAPI application entrypoint with health & CORS
├── data/
│   ├── products.json            # Synthetic product catalog dataset
│   ├── documents/               # Local markdown and text knowledge documents
│   └── benchmarks/
│       └── benchmark_v1.jsonl   # 44 versioned benchmark tasks across 5 categories
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
│   └── test_api_experiments.py # API endpoints for benchmarks and experiment runs
├── demo.py                      # Interactive CLI task demonstration runner
├── demo_benchmark.py            # Benchmark execution and evaluation metrics demo runner
├── verify_api.py                # Live HTTP server verification test script
├── requirements.txt             # Project dependencies
└── README.md                    # Project documentation
```

---

## 2. Benchmark Dataset (`benchmark_v1.jsonl`)

The benchmark dataset consists of **44 predefined, versioned tasks** stored in `data/benchmarks/benchmark_v1.jsonl` (one task per line, formatted as JSON).

### Category Distribution

| Category | Tasks | Description |
|---|---:|---|
| **Arithmetic & Calculation** (`arithmetic`) | 9 | Multi-operator arithmetic, decimal calculations, edge cases |
| **Structured Data Lookup** (`data_lookup`) | 9 | Product catalog search, ID lookups, category filtering |
| **Document QA** (`document_qa`) | 9 | Policy verification, warranty terms, shipping timelines |
| **Multi-Step Tool-Use** (`multi_step`) | 9 | Catalog lookup followed by price computation or quantity calculation |
| **Controlled Failure Scenarios** (`failure_scenario`) | 8 | Repeatable failure injections testing agent failure modes |
| **Total** | **44** | Exceeds minimum benchmark threshold (40) |

### Task Schema
Each task record strictly conforms to `BenchmarkTask`:
- `task_id`: Stable unique identifier (e.g., `ARITH-001`, `DATA-004`, `FAIL-001`).
- `benchmark_version`: Dataset version (e.g., `v1.0`).
- `category`: Task category.
- `task_description`: Natural language instructions for the agent.
- `allowed_tools`: Authorized tool list (e.g., `["calculator"]`).
- `expected_answer`: Ground-truth expected answer or structured payload.
- `verification_rule`: Deterministic verification configuration (`numerical_tolerance`, `field_presence`, `evidence_reference`, `exact_match`).
- `expected_tool_sequence`: Recommended/expected sequence of tool invocations.
- `difficulty`: `easy`, `medium`, or `hard`.
- `tags`: Classification tags.
- `failure_scenario`: Optional `FailureScenarioConfig` (only for failure injection tasks).

---

## 3. Controlled Failure Scenarios

TraceGuard implements 8 configurable failure injection modes via `InjectedToolExecutor` and `InjectedModelAdapter`. Failure injection is **disabled by default** and only activated when explicitly requested by benchmark configuration.

| Scenario ID | Failure Type | Mechanism | Expected Observation | Expected Status |
|---|---|---|---|---|
| `FAIL-001` | **Transient tool failure** | Intercepts tool on configured attempt (e.g. attempt 1) and returns simulated HTTP 503 error | Service Temporarily Unavailable | `tool_error` |
| `FAIL-002` | **Invalid tool arguments** | Model adapter injects schema-invalid arguments (e.g. string for numeric field) | Pydantic validation error | `tool_error` |
| `FAIL-003` | **Repeated tool calls** | Model adapter loops repeating identical queries without progress | Repeated tool call without progress | `step_limit_exhaustion` |
| `FAIL-004` | **Missing evidence** | Task requests knowledge nonexistent in document collection | Document search returns 0 matches | `successful_completion` |
| `FAIL-005` | **Incorrect final answer** | Model adapter injects hallucinated value (`99999`) | Verifier detects mismatch against ground truth | `incorrect_answer` |
| `FAIL-006` | **Step-limit exhaustion** | Model adapter endlessly requests tool calls until step limit is hit | Step limit exceeded | `step_limit_exhaustion` |
| `FAIL-007` | **Tool timeout** | Tool executor simulates timeout exception | Execution exceeded timeout limit | `timeout` / `tool_error` |
| `FAIL-008` | **No matching record** | Catalog lookup for non-existent item (`Quantum Hoverboard X9000`) | Catalog search returns 0 matches | `successful_completion` |

---

## 4. Evaluation Metrics & Statistical Reporting

The evaluation engine calculates comprehensive metrics across every experiment run:

### Core Metrics

1. **Task Success Rate**:
   $$\text{Success Rate} = \frac{\text{Correctly completed tasks}}{\text{All attempted tasks}} \times 100$$
   - Tasks ending in timeout, step-limit exhaustion, tool error, or unverified output are treated as unsuccessful.
2. **Wilson Score 95% Confidence Interval**:
   - Computes an asymmetric confidence interval $[p_l, p_u]$ for the success rate.
   - For sample sizes $N < 30$, a clear warning is flagged: *"Small sample size ($N < 30$). Confidence interval should be interpreted with caution."*
3. **Verification Accuracy**:
   - Measures the percentage of verified tasks against ground-truth deterministic rules:
   $$\text{Verification Accuracy} = \frac{\text{Verified tasks}}{\text{Tasks with verification rules}} \times 100$$
4. **Tool Execution Error Rate**:
   - Proportion of tool invocations that failed:
   $$\text{Tool Error Rate} = \frac{\text{Failed tool calls}}{\text{Total tool calls}} \times 100$$
5. **Task Failure Distribution**:
   - Categorizes failures into distinct buckets: `incorrect_answer`, `tool_error`, `timeout`, `step_limit_exhaustion`, `missing_evidence`, and `other_errors`, along with percentage distributions.
6. **Efficiency & Latency**:
   - `mean_duration_ms`, `median_duration_ms`, `p95_duration_ms` (annotated if sample size is small).
   - `mean_steps_per_task` and `mean_tool_calls_per_task`.
   - `model_tokens` and `estimated_cost` (reported as `null` when pricing/token data is unavailable; never invented).
7. **Repeatability**:
   - For repeated runs ($R > 1$), tracks per-repetition success rates, standard deviation of latency, and consistency of tool sequences and final outputs.

---

## 5. REST API Endpoints

### Benchmark Inspection

#### `GET /benchmarks`
Lists available benchmark versions and task counts by category.
```json
[
  {
    "benchmark_version": "v1.0",
    "filename": "benchmark_v1.jsonl",
    "total_tasks": 44,
    "categories": {
      "arithmetic": 9,
      "data_lookup": 9,
      "document_qa": 9,
      "multi_step": 9,
      "failure_scenario": 8
    }
  }
]
```

#### `GET /benchmarks/{benchmark_version}/tasks?category=arithmetic&limit=10&offset=0`
Lists tasks with metadata, pagination, and optional category filtering.

---

### Experiment Execution & Analysis

#### `POST /experiments/run`
Starts an experiment evaluation run.
```json
{
  "benchmark_version": "v1.0",
  "category": "arithmetic",
  "agent_mode": "baseline",
  "repetitions": 1,
  "enable_failure_injection": false,
  "max_steps": 6,
  "timeout_seconds": 30.0
}
```

*Note: Only `agent_mode: "baseline"` is supported in Milestone 2. Other modes (`fixed_retry`, `traceguard`) are rejected with HTTP 400 until implemented in subsequent milestones.*

#### `GET /experiments/{experiment_id}`
Returns experiment execution metadata, progress, and status (`running`, `completed`, `failed`).

#### `GET /experiments/{experiment_id}/results`
Returns per-task execution results, terminal status, verification outcomes, durations, and trace references.

#### `GET /experiments/{experiment_id}/metrics`
Returns aggregated experiment metrics, Wilson confidence intervals, failure distributions, and efficiency statistics.

#### `GET /experiments/{experiment_id}/export?format=jsonl`
Exports machine-readable task execution results in `json` or `jsonl` format.

---

## 6. How to Run the Benchmark

### 1. Run Automated Test Suite
Execute the full test suite (all 79 unit, integration, failure-injection, and regression tests):
```bash
python -m pytest -v
```

### 2. Run CLI Benchmark Demo
Run the sample benchmark demonstration script:
```bash
# Run arithmetic category (9 tasks)
python demo_benchmark.py

# Run all categories (44 tasks, including controlled failure injection)
python demo_benchmark.py --all

# Run a specific category
python demo_benchmark.py --category multi_step
```

### 3. Run FastAPI Server
Start the TraceGuard API server:
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive Swagger API documentation is available at `http://127.0.0.1:8000/docs`.

---

## 7. Sample Experiment Output (Real Data)

Below is an actual benchmark experiment execution across all 44 benchmark tasks generated by the running system (`exp_498de69219d4`):

```json
{
  "experiment_id": "exp_498de69219d4",
  "benchmark_version": "v1.0",
  "agent_mode": "baseline",
  "total_attempted": 44,
  "successful_tasks": 37,
  "unverified_tasks": 0,
  "failed_tasks": 7,
  "success_rate": 84.1,
  "success_rate_ci": {
    "point_estimate": 84.1,
    "lower_bound": 70.6,
    "upper_bound": 92.1,
    "confidence_level": 0.95,
    "method": "Wilson score interval",
    "sample_size": 44,
    "warning": null
  },
  "verification_accuracy": 94.9,
  "verification_denominator": 39,
  "tool_error_rate": 6.0,
  "total_tool_calls": 67,
  "failed_tool_calls": 4,
  "failure_distribution": {
    "incorrect_answer": 2,
    "tool_error": 3,
    "timeout": 0,
    "step_limit_exhaustion": 2,
    "missing_evidence": 0,
    "other_errors": 0,
    "total_failures": 7,
    "failure_percentages": {
      "incorrect_answer": 28.57,
      "tool_error": 42.86,
      "step_limit_exhaustion": 28.57
    }
  },
  "efficiency": {
    "mean_duration_ms": 2.38,
    "median_duration_ms": 1.98,
    "p95_duration_ms": 6.19,
    "mean_tool_calls_per_task": 1.52,
    "mean_steps_per_task": 2.45,
    "total_tokens": null,
    "cost_per_task": null
  }
}
```

---

## 8. Known Limitations & Milestone 3 Roadmap

### Current Limitations (Milestone 2)
1. **Agent Modes**: Only `agent_mode: "baseline"` is executable. Dynamic retry and targeted recovery policies will be introduced in Milestones 3 & 4.
2. **Synchronous Execution**: Experiments run synchronously within the API runner loop; background task queues (e.g. Celery / RQ) are reserved for scaling later.
3. **Pricing and Cost Data**: Cost calculations require external model pricing metadata. In mock mode, costs are reported as `null` rather than estimated or fabricated.

### Next Milestone: Milestone 3
- **Trajectory Failure Detector**: Implement runtime diagnosis of execution trajectories to detect tool failures, repetitive loops, hallucinated arguments, and evidence divergence before terminal step limits are reached.
- **Adaptive Recovery Engine**: Implement targeted recovery strategies (state rollback, tool retry with constraint injection, and alternative strategy exploration).
