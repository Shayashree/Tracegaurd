"""Integration tests for FastAPI Diagnostics API endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.tracing.storage import TraceStorage

@pytest.fixture
def client(tmp_path):
    storage = TraceStorage(db_path=str(tmp_path / "api_diag_test.db"))
    app.dependency_overrides = {}
    from backend.api.diagnostics import get_storage
    from backend.api.tasks import get_storage as get_tasks_storage
    from backend.api.traces import get_storage as get_traces_storage
    from backend.api.experiments import get_storage as get_exp_storage

    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_tasks_storage] = lambda: storage
    app.dependency_overrides[get_traces_storage] = lambda: storage
    app.dependency_overrides[get_exp_storage] = lambda: storage

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def test_api_diagnostics_config(client):
    resp = client.get("/diagnostics/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "detector_version" in data
    assert "repeated_call_threshold" in data
    assert data["repeated_call_threshold"] == 3

def test_api_run_and_get_diagnostics(client):
    # 1. Run a task first via /tasks
    task_payload = {
        "task": "Calculate 12 * 8",
        "max_steps": 5,
        "allowed_tools": ["calculator"],
        "verification_rule": {
            "type": "numerical_tolerance",
            "expected_value": 96.0,
            "tolerance": 0.01
        }
    }
    task_resp = client.post("/tasks", json=task_payload)
    assert task_resp.status_code == 201
    task_data = task_resp.json()
    task_id = task_data["task_id"]
    run_id = task_data["run_id"]

    # 2. Trigger diagnostic run via POST /diagnostics/run
    diag_req = {"run_id": run_id, "task_id": task_id}
    diag_resp = client.post("/diagnostics/run", json=diag_req)
    assert diag_resp.status_code == 200
    diag_data = diag_resp.json()
    assert diag_data["task_id"] == task_id
    assert diag_data["run_id"] == run_id
    assert diag_data["diagnostic_status"] == "healthy"
    diagnostic_id = diag_data["diagnostic_id"]

    # 3. Retrieve by diagnostic_id via GET /diagnostics/{id}
    get_resp = client.get(f"/diagnostics/{diagnostic_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["diagnostic_id"] == diagnostic_id

    # 4. Retrieve by task_id via GET /tasks/{task_id}/diagnostics
    task_diag_resp = client.get(f"/tasks/{task_id}/diagnostics")
    assert task_diag_resp.status_code == 200
    assert len(task_diag_resp.json()) >= 1

    # 5. Retrieve by run_id via GET /runs/{run_id}/diagnostics
    run_diag_resp = client.get(f"/runs/{run_id}/diagnostics")
    assert run_diag_resp.status_code == 200
    assert run_diag_resp.json()["diagnostic_id"] == diagnostic_id

def test_api_diagnostics_not_found(client):
    resp = client.get("/diagnostics/nonexistent_id")
    assert resp.status_code == 404

    resp_run = client.get("/runs/nonexistent_run/diagnostics")
    assert resp_run.status_code == 404

    resp_post = client.post("/diagnostics/run", json={"run_id": "nonexistent_run"})
    assert resp_post.status_code == 404

def test_api_experiment_diagnostics_and_metrics(client):
    # 1. Run small experiment first via /experiments/run
    exp_payload = {
        "benchmark_version": "v1.0",
        "task_ids": ["ARITH-001"],
        "agent_mode": "baseline",
        "repetitions": 1,
        "enable_failure_injection": False
    }
    exp_resp = client.post("/experiments/run", json=exp_payload)
    assert exp_resp.status_code == 201
    exp_id = exp_resp.json()["experiment_id"]

    # 2. Run diagnostics for experiment via POST /experiments/{id}/diagnostics
    diag_run_resp = client.post(f"/experiments/{exp_id}/diagnostics")
    assert diag_run_resp.status_code == 200
    data = diag_run_resp.json()
    assert data["experiment_id"] == exp_id
    assert data["total_analyzed"] == 1

    # 3. Fetch detector metrics via GET /experiments/{id}/detector-metrics
    metrics_resp = client.get(f"/experiments/{exp_id}/detector-metrics")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert metrics_data["total_runs_evaluated"] == 1
    assert "category_metrics" in metrics_data
