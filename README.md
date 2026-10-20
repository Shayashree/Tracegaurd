# TraceGuard: An Evidence-Driven Reliability and Recovery Platform for Tool-Using AI Agents

**Milestone 1: Baseline Tool-Using AI Agent**

TraceGuard is a research and reliability engineering platform designed for autonomous, tool-using AI agents. Milestone 1 establishes a modular baseline agent architecture that receives a user task, plans and selects tools, executes them deterministically, records observable execution events, and validates the task outcome against deterministic rules.

Future milestones build on this baseline to introduce trajectory analysis, failure detection, targeted recovery, experiment comparison, and an interactive React dashboard—without modifying the baseline agent execution loop.

---

## 1. System Architecture

TraceGuard Milestone 1 is structured into modular components:

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
│   ├── models/
│   │   └── schemas.py           # Pydantic models for tasks, tools, and traces
│   ├── api/
│   │   ├── tasks.py             # REST endpoints: POST /tasks, GET /tasks/{id}
│   │   └── traces.py            # REST endpoints: GET traces and JSONL export
│   ├── config.py                # Environment configuration using pydantic-settings
│   └── main.py                  # FastAPI application entrypoint with health & CORS
├── data/
│   ├── products.json            # Sample product catalog dataset
│   └── documents/               # Local markdown and text knowledge documents
├── tests/
│   ├── test_tools.py            # Unit tests for Calculator, Data Lookup, & Doc Search
│   ├── test_agent_controller.py # Multi-step execution, limits, and error handling
│   ├── test_tracing.py          # Trace schemas, ordering, redaction, & JSONL
│   ├── test_verifier.py         # Numerical, field, and evidence verification
│   └── test_api.py              # FastAPI endpoint integration tests
├── demo.py                      # Interactive CLI demonstration runner
├── verify_api.py                # Live HTTP server verification test script
├── requirements.txt             # Project dependencies
├── .env.example                 # Template environment variables
├── .gitignore                   # Version control ignore rules
└── README.md                    # Project documentation
```

### Key Architectural Modules

1. **Agent Controller (`backend/agents/controller.py`)**:
   Coordinates the bounded execution loop. Dispatches queries to the model adapter, receives tool calls or final answers, coordinates tool execution, manages step limits (default: 8) and timeout ceilings, and passes final answers to outcome verification.
2. **Pluggable Model Adapter (`backend/agents/model_adapter.py`)**:
   Abstracts the model interface. Supports deterministic `MockModelAdapter` for local, zero-credential reproducibility, as well as an `OpenAIModelAdapter` for live API interaction.
3. **Tool Registry & Executor (`backend/agents/tool_registry.py`)**:
   Maintains tool definitions, enforces allowed tool whitelisting, validates arguments against Pydantic schemas, and captures execution results or errors without crashing the agent.
4. **Observable Trace Collector (`backend/tracing/collector.py`)**:
   Passively records observable events (`task_started`, `model_request`, `tool_call_requested`, `tool_execution_started`, `tool_execution_completed`, `tool_execution_failed`, `final_answer_proposed`, `verification_completed`, `task_completed`, `task_failed`, `step_limit_reached`). Automatically redacts credentials and API keys.
5. **Trace Storage (`backend/tracing/storage.py`)**:
   Persists tasks and execution events into SQLite (`traceguard.db`) and exports structured JSONL traces.
6. **Outcome Verifier (`backend/verification/verifier.py`)**:
   Deterministically verifies task results using numerical tolerance matching, field/record presence, evidence reference checks, and exact matching. Clearly flags unverified tasks when no rule applies.
7. **REST API (`backend/api/`)**:
   FastAPI endpoints for submitting tasks, inspecting results, querying ordered trace histories, and downloading JSONL export files.

---

## 2. Setup and Installation

### Prerequisites
- Python 3.11+
- Git

### 1. Clone & Navigate to Repository
```bash
git clone <repo-url>
cd "1C Project"
```

### 2. Create and Activate Virtual Environment
On Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

On Linux/macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Default settings in `.env`:
```ini
TRACEGUARD_ENV=development
LOG_LEVEL=INFO
DEFAULT_MAX_STEPS=8
DEFAULT_TIMEOUT_SECONDS=30.0
DATABASE_PATH=traceguard.db
DATA_DIR=./data
MODEL_ADAPTER=mock
```
*Note: To run with OpenAI, set `MODEL_ADAPTER=openai`, `OPENAI_API_KEY=your_key`, and `OPENAI_MODEL_NAME=gpt-4o-mini`.*

---

## 3. Running the Server

Start the FastAPI application with Uvicorn:
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API documentation will be available at:
- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 4. Running the Demonstrations

TraceGuard comes with a demonstration runner showcasing all five core scenarios:

```bash
python demo.py
```

### Included Demonstrations:
1. **Multi-Step Task**:
   - Prompt: `"Find the prices of Product A and Product B, then calculate their combined price."`
   - Flow: Agent queries `data_lookup` -> receives $45.00 and $85.00 -> calls `calculator` -> calculates $130.00 -> returns final answer -> verified with numerical tolerance.
2. **Direct Calculation**:
   - Prompt: `"Calculate 25 * 4"` -> calls `calculator` multiplication -> returns 100.
3. **Document Question**:
   - Prompt: `"What is the return policy for purchases?"` -> queries `document_search` -> retrieves DOC-REFUND-001 -> answers with policy details -> verified with evidence references.
4. **Controlled Tool Error**:
   - Prompt: `"Divide 100 by 0"` -> calls `calculator` -> receives division-by-zero error -> safely proposes answer explaining arithmetic failure.
5. **Step Limit Bound Enforcement**:
   - Prompt: `"Run endless loop to trigger step limit"` (max_steps=4) -> reaches step limit safely -> records `step_limit_reached` event -> returns structured failure details.

---

## 5. API Reference & Usage

### A. Health Check
```http
GET /health
```
**Response (200 OK):**
```json
{
  "status": "ok",
  "version": "0.1.0",
  "service": "traceguard-baseline-agent",
  "model_adapter": "mock",
  "default_max_steps": 8
}
```

### B. Submit a Task
```http
POST /tasks
Content-Type: application/json

{
  "task": "Find the prices of Product A and Product B, then calculate their combined price.",
  "max_steps": 8,
  "verification_rule": {
    "type": "numerical_tolerance",
    "expected_value": 130.0,
    "tolerance": 0.01
  }
}
```
**Response (201 Created):**
```json
{
  "task_id": "task_5df78d463761",
  "run_id": "run_cd39f984ef96",
  "task": "Find the prices of Product A and Product B, then calculate their combined price.",
  "status": "completed",
  "final_answer": "The price of Product A is $45.00 and Product B is $85.00. Their combined total price is $130.00.",
  "error_info": null,
  "verification": {
    "verified": true,
    "status": "verified",
    "verification_method": "numerical_tolerance",
    "expected_result": 130.0,
    "observed_result": 130.0,
    "verification_message": "Observed number 130.0 matches expected 130.0 (tolerance 0.01)."
  },
  "steps_count": 3,
  "duration_ms": 13.6,
  "created_at": "2026-10-20T05:10:58.041+00:00",
  "completed_at": "2026-10-20T05:10:58.055+00:00"
}
```

### C. Retrieve Task Status
```http
GET /tasks/{task_id}
```

### D. Retrieve Observable Trace Events
```http
GET /tasks/{task_id}/traces
```
Returns chronological list of structured execution events.

### E. Export Trace as JSONL
```http
GET /tasks/{task_id}/traces/export
```
Returns a downloadable `.jsonl` stream with media type `application/x-ndjson`.

---

## 6. Running Automated Tests

Run the complete test suite with `pytest`:

```bash
python -m pytest -v
```

The test suite covers:
- **`tests/test_tools.py`**: Arithmetic bounds, division by zero, type validation, data lookup exact and multi-query matches, document search relevance and snippet extraction.
- **`tests/test_agent_controller.py`**: Multi-step pipeline, direct calculation, document QA, tool errors, step limit enforcement, timeout bounds, and tool whitelisting.
- **`tests/test_tracing.py`**: Structured event schema, step ordering, credential redaction, SQLite persistence, and JSONL format compliance.
- **`tests/test_verifier.py`**: Numerical tolerance, field presence, evidence reference, exact match, and unverified fallback.
- **`tests/test_api.py`**: FastAPI endpoints, request validation, 404 responses, and JSONL export via `TestClient`.

---

## 7. Current Limitations & Planned Milestones

### Current Limitations (Milestone 1)
- **Synchronous Execution**: Tasks are processed synchronously during the HTTP request. Asynchronous background queueing (Celery / Redis / BackgroundTasks) will be added in future milestones.
- **Passive Tracing**: Traces are recorded passively without real-time diagnosis or self-correction, as specified by Milestone 1 research requirements.
- **Initial Toolset**: Three deterministic tools (Calculator, Data Lookup, Document Search) are implemented.
- **No GUI**: Interactions currently occur via REST API or CLI demonstration scripts.

### Planned Milestones
- **Milestone 2**: Failure Detection & Trajectory Analysis (detecting loops, tool argument errors, hallucinated tools, and evidence divergence).
- **Milestone 3**: Targeted Recovery Engine (state rollback, tool retry with constraint injection, and alternative strategy exploration).
- **Milestone 4**: Benchmark & Evaluation Suite (comparing Baseline vs. Fixed-Retry vs. TraceGuard Recovery across agent failure datasets).
- **Milestone 5**: Interactive React Dashboard & Trace Explorer.
