"""Integration tests for experiment and benchmark API endpoints."""
import json
import pytest
from fastapi.testclient import TestClient
from backend.api.tasks import get_controller, get_storage
from backend.main import app
from backend.tracing.storage import TraceStorage

@pytest.fixture
def client(tmp_path):
    test_storage = TraceStorage(db_path=str(tmp_path / "api_exp_test.db"))
    app.dependency_overrides[get_storage] = lambda: test_storage

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

def test_api_list_benchmarks(client):
    resp = client.get("/benchmarks")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["total_tasks"] >= 40

def test_api_get_benchmark_tasks(client):
    resp = client.get("/benchmarks/v1.0/tasks?category=arithmetic&limit=5")
    assert resp.status_code == 200
    tasks = resp.json()
    assert len(tasks) == 5
    for t in tasks:
        assert t["category"] == "arithmetic"

def test_api_reject_unsupported_agent_mode(client):
    payload = {
        "benchmark_version": "v1.0",
        "agent_mode": "fixed_retry",
        "task_ids": ["ARITH-001"]
    }
    resp = client.post("/experiments/run", json=payload)
    assert resp.status_code == 422
    assert "not yet supported in Milestone 2" in resp.text

def test_api_run_and_query_experiment(client):
    payload = {
        "benchmark_version": "v1.0",
        "task_ids": ["ARITH-001", "DATA-001"],
        "agent_mode": "baseline",
        "repetitions": 1
    }

    # 1. Start experiment
    post_resp = client.post("/experiments/run", json=payload)
    assert post_resp.status_code == 201
    exp_data = post_resp.json()
    exp_id = exp_data["experiment_id"]
    assert exp_data["status"] == "completed"
    assert exp_data["total_tasks"] == 2
    assert exp_data["metrics"]["successful_tasks"] == 2

    # 2. Get experiment metadata
    get_resp = client.get(f"/experiments/{exp_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["experiment_id"] == exp_id

    # 3. Get experiment results
    res_resp = client.get(f"/experiments/{exp_id}/results?limit=10")
    assert res_resp.status_code == 200
    results = res_resp.json()
    assert len(results) == 2
    assert results[0]["terminal_status"] == "successful_completion"
    assert "task_id" in results[0]["trace_reference"]

    # 4. Get experiment metrics
    metrics_resp = client.get(f"/experiments/{exp_id}/metrics")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert metrics["success_rate"] == 100.0
    assert metrics["total_attempted"] == 2

    # 5. Export JSON
    export_json = client.get(f"/experiments/{exp_id}/export?format=json")
    assert export_json.status_code == 200
    assert "application/json" in export_json.headers["content-type"]
    json_data = export_json.json()
    assert "results" in json_data
    assert len(json_data["results"]) == 2

    # 6. Export JSONL
    export_jsonl = client.get(f"/experiments/{exp_id}/export?format=jsonl")
    assert export_jsonl.status_code == 200
    assert "application/x-ndjson" in export_jsonl.headers["content-type"]
    lines = [l for l in export_jsonl.text.strip().splitlines() if l.strip()]
    assert len(lines) == 2

def test_api_experiment_not_found(client):
    assert client.get("/experiments/non_existent_exp").status_code == 404
    assert client.get("/experiments/non_existent_exp/results").status_code == 404
    assert client.get("/experiments/non_existent_exp/metrics").status_code == 404
    assert client.get("/experiments/non_existent_exp/export").status_code == 404
