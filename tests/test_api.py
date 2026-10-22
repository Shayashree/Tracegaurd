"""Integration tests for FastAPI REST API endpoints using TestClient."""
import json
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.api.tasks import get_controller, get_storage
from backend.agents.controller import AgentController
from backend.agents.mock_model import MockModelAdapter
from backend.tracing.storage import TraceStorage

@pytest.fixture
def client(tmp_path):
    # Set up isolated storage and controller for API tests
    test_storage = TraceStorage(db_path=str(tmp_path / "api_test.db"))
    test_controller = AgentController(storage=test_storage, model_adapter=MockModelAdapter())

    app.dependency_overrides[get_storage] = lambda: test_storage
    app.dependency_overrides[get_controller] = lambda: test_controller

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

def test_api_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["service"] == "traceguard-baseline-agent"

def test_api_create_and_get_task(client):
    payload = {
        "task": "Find the prices of Product A and Product B, then calculate their combined price.",
        "max_steps": 8,
        "verification_rule": {
            "type": "numerical_tolerance",
            "expected_value": 130.0,
            "tolerance": 0.01
        }
    }

    # 1. Submit Task
    post_resp = client.post("/tasks", json=payload)
    assert post_resp.status_code == 201
    task_data = post_resp.json()
    assert "task_id" in task_data
    assert "run_id" in task_data
    assert task_data["status"] == "completed"
    assert "130" in task_data["final_answer"]
    assert task_data["verification"]["verified"] is True
    assert task_data["steps_count"] >= 2

    task_id = task_data["task_id"]

    # 2. Get Task by ID
    get_resp = client.get(f"/tasks/{task_id}")
    assert get_resp.status_code == 200
    fetched_data = get_resp.json()
    assert fetched_data["task_id"] == task_id
    assert fetched_data["final_answer"] == task_data["final_answer"]

def test_api_get_traces(client):
    # Create task first
    post_resp = client.post("/tasks", json={"task": "Calculate 15 + 25"})
    assert post_resp.status_code == 201
    task_id = post_resp.json()["task_id"]

    # Fetch traces
    traces_resp = client.get(f"/tasks/{task_id}/traces")
    assert traces_resp.status_code == 200
    events = traces_resp.json()
    assert isinstance(events, list)
    assert len(events) >= 3

    event_types = [e["event_type"] for e in events]
    assert "task_started" in event_types
    assert "task_completed" in event_types

def test_api_export_traces_jsonl(client):
    post_resp = client.post("/tasks", json={"task": "What is the return policy?"})
    assert post_resp.status_code == 201
    task_id = post_resp.json()["task_id"]

    export_resp = client.get(f"/tasks/{task_id}/traces/export")
    assert export_resp.status_code == 200
    assert "application/x-ndjson" in export_resp.headers["content-type"]
    assert f'filename="{task_id}_trace.jsonl"' in export_resp.headers["content-disposition"]

    lines = [l for l in export_resp.text.splitlines() if l.strip()]
    assert len(lines) >= 3
    first_event = json.loads(lines[0])
    assert first_event["task_id"] == task_id
    assert first_event["event_type"] == "task_started"

def test_api_not_found_errors(client):
    resp = client.get("/tasks/non_existent_id")
    assert resp.status_code == 404

    resp_traces = client.get("/tasks/non_existent_id/traces")
    assert resp_traces.status_code == 404

    resp_export = client.get("/tasks/non_existent_id/traces/export")
    assert resp_export.status_code == 404

def test_api_invalid_request(client):
    # Missing required 'task' field
    resp = client.post("/tasks", json={})
    assert resp.status_code == 422

def test_api_assign_custom_task(client):
    payload = {
        "task": "Find the prices of Product A and Product B, then calculate their combined price.",
        "max_steps": 6,
        "timeout_seconds": 25.0,
        "allowed_tools": ["calculator", "data_lookup"],
        "verification_rule": {
            "type": "numerical_tolerance",
            "expected_value": 130.0,
            "tolerance": 0.05
        },
        "agent_mode": "traceguard_recovery"
    }
    resp = client.post("/tasks", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "completed"
    assert "130" in data["final_answer"]
    assert data["verification"]["verified"] is True

    # Check recent tasks listing
    recent_resp = client.get("/tasks/recent?limit=10")
    assert recent_resp.status_code == 200
    recent = recent_resp.json()
    assert len(recent) > 0
    latest = recent[0]
    assert latest["task_id"] == data["task_id"]
    assert "Custom:" in latest["display_label"]
