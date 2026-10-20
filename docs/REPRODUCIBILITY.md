# TraceGuard Research Reproducibility Guide

## 1. Reproducibility Philosophy

Scientific reproducibility is a foundational requirement for TraceGuard. Benchmark evaluations must be fully repeatable by independent reviewers without requiring paid API keys, active internet connections, or non-deterministic external services.

TraceGuard achieves this through:
1. **Deterministic Mock Model Adapter**: A repeatable scenario-driven adapter that deterministically generates tool requests, arguments, final answers, or controlled failures based on seed configurations.
2. **Versioned Benchmark Datasets**: All benchmark tasks (`v1.0`) are version-controlled with immutable task IDs, fixed descriptions, and deterministic verification rules.
3. **Immutable Reproducibility Manifests**: Every executed experiment records a cryptographically hashed configuration manifest including code version, seed, task splits, model parameters, and timestamps.
4. **Isolated Ground Truth**: Expected answers are exclusively accessible to the Outcome Verifier, eliminating prompt leakage.

---

## 2. Benchmark Versioning and Task Splits

### Benchmark Version: `v1.0`
The benchmark dataset consists of 40 diverse tasks across 4 core domains:
- **Arithmetic**: Multi-step mathematical reasoning using the `calculator` tool.
- **Data Lookup**: Querying structured inventory, product specifications, and pricing from `data/products.json` using the `data_lookup` tool.
- **Document QA**: Text comprehension and snippet extraction from `data/documents/*.txt` using the `document_search` tool.
- **Multi-Step Compositional**: Complex tasks requiring chaining multiple tools (e.g. searching document policies, looking up catalog prices, and calculating discounts).

---

## 3. Execution Modes Compared

To answer the core research question, TraceGuard compares three execution modes over the exact same task set:

1. **`baseline`**: Standard tool-using agent without runtime failure detection or intervention. Halts upon final answer proposal, step exhaustion, or fatal tool error.
2. **`fixed_retry`**: Naive recovery agent that blindly retries failed tool calls or steps up to a fixed retry count without diagnosing the root cause.
3. **`traceguard` / `traceguard_recovery`**: Evidence-driven agent combining trajectory-based failure detection with targeted recovery policies matched to specific diagnostic findings.

---

## 4. Reproducing Experiments

### Option A: Command-Line Reproduction Script
Run the automated comparison script across all three modes in deterministic offline mode:
```bash
python run_experiments.py
```
This runs the full benchmark across `baseline`, `fixed_retry`, and `traceguard` modes, computes statistical significance tests (McNemar's test and paired t-tests), generates a markdown research report, and persists results to `traceguard.db`.

### Option B: Interactive Dashboard Reproduction
1. Open the TraceGuard Dashboard at `http://localhost:5173` (or `http://localhost:3000` under Docker).
2. Navigate to **Run Experiments** in the sidebar.
3. Select Benchmark Version: `v1.0`.
4. Select Execution Modes: `baseline`, `fixed_retry`, `traceguard`.
5. Select Model: `deterministic-mock-v1` (Mock).
6. Click **Launch Benchmark Experiment**.
7. Once completed, review the generated comparison charts, latency overhead, recovery lift, and download the full JSON or JSONL export.

---

## 5. Experiment Manifest Schema

Each experiment generates a manifest accessible via `GET /experiments/{experiment_id}/manifest`:
```json
{
  "experiment_id": "exp_20261020_001",
  "benchmark_version": "v1.0",
  "agent_modes": ["baseline", "fixed_retry", "traceguard"],
  "model_adapter": "mock",
  "model_name": "deterministic-mock-v1",
  "task_count": 40,
  "config_hash": "a4f89d9e...",
  "recovery_budgets": {
    "max_attempts": 2,
    "max_steps": 5,
    "max_tools": 5
  },
  "started_at": "2026-10-20T10:00:00Z",
  "completed_at": "2026-10-20T10:00:35Z"
}
```

---

## 6. Sources of Variation with Live External LLMs

When running against commercial LLMs (e.g. `MODEL_ADAPTER=openai`, `gpt-4o-mini`):
- Non-zero temperature settings and backend non-determinism from multi-tenant cloud providers introduce sampling variations.
- TraceGuard logs the exact model name, temperature, prompt tokens, completion tokens, and latency for every step to enable transparent empirical analysis despite provider variance.
