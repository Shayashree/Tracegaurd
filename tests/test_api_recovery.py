"""API endpoint tests for recovery actions, queries, and experiment metrics."""
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models.schemas import TaskCreateRequest, VerificationRule
from backend.tracing.storage import TraceStorage

client = TestClient(app)

@pytest.fixture
def clean_storage(tmp_path, monkeypatch):
    db_file = tmp_path / "test_api_recovery.db"
    storage = TraceStorage(db_path=str(db_file))
    from backend.api import tasks, experiments, diagnostics, recovery
    monkeypatch.setattr(tasks, "get_storage", lambda: storage)
    monkeypatch.setattr(experiments, "get_storage", lambda: storage)
    monkeypatch.setattr(diagnostics, "get_storage", lambda: storage)
    monkeypatch.setattr(recovery, "get_storage", lambda: storage)
    return storage

def test_api_task_recover_flow(clean_storage):
    """POST /tasks/{id}/recover triggers recovery and persists reports."""
    # 1. Create a task
    create_payload = {
        "task": "Compute 12 * 12",
        "allowed_tools": ["calculator"],
        "verification_rule": {
            "type": "numerical_tolerance",
            "expected_value": 144.0,
            "tolerance": 1e-4,
        },
    }
    task_res = client.post("/tasks", json=create_payload)
    assert task_res.status_code == 201
    task_data = task_res.json()
    task_id = task_data["task_id"]
    run_id = task_data["run_id"]

    # 2. Recover the task
    rec_res = client.post(f"/tasks/{task_id}/recover", json={})
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["task_id"] == task_id
    assert rec_data["recovery_id"] is not None
    recovery_id = rec_data["recovery_id"]

    # 3. GET /recovery/{recovery_id}
    query_res = client.get(f"/recovery/{recovery_id}")
    assert query_res.status_code == 200
    assert query_res.json()["recovery_id"] == recovery_id

    # 4. GET /tasks/{task_id}/recovery
    task_rec_res = client.get(f"/tasks/{task_id}/recovery")
    assert task_rec_res.status_code == 200
    assert task_rec_res.json()["task_id"] == task_id

    # 5. GET /runs/{run_id}/recovery
    run_rec_res = client.get(f"/runs/{run_id}/recovery")
    assert run_rec_res.status_code == 200
    assert run_rec_res.json()["run_id"] == run_id

def test_api_experiment_run_and_recovery_metrics(clean_storage):
    """POST /experiments/run with traceguard_recovery mode and fetch recovery-metrics."""
    run_payload = {
        "benchmark_version": "v1.0",
        "agent_mode": "traceguard_recovery",
        "category": "arithmetic",
        "repetitions": 1,
        "max_steps": 5,
    }
    exp_res = client.post("/experiments/run", json=run_payload)
    assert exp_res.status_code == 201
    exp_data = exp_res.json()
    exp_id = exp_data["experiment_id"]
    assert exp_data["agent_mode"] == "traceguard_recovery"

    # Fetch recovery metrics
    metrics_res = client.get(f"/experiments/{exp_id}/recovery-metrics")
    assert metrics_res.status_code == 200
    metrics_data = metrics_res.json()
    assert metrics_data["agent_mode"] == "traceguard_recovery"
    assert "end_to_end_success_rate" in metrics_data
    assert "recovery_success_rate_eligible" in metrics_data
    assert "efficiency" in metrics_data

def test_api_recovery_not_found(clean_storage):
    """Querying non-existent recovery records returns 404."""
    res1 = client.get("/recovery/rec_nonexistent")
    assert res1.status_code == 404

    res2 = client.get("/tasks/task_nonexistent/recovery")
    assert res2.status_code == 404

    res3 = client.get("/runs/run_nonexistent/recovery")
    assert res3.status_code == 404
