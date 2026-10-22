"""Integration tests for Milestone 5 REST API endpoints."""
import pytest
from fastapi.testclient import TestClient
from backend.api.tasks import get_storage
from backend.main import app
from backend.tracing.storage import TraceStorage

@pytest.fixture
def test_client(tmp_path):
    db_file = tmp_path / "test_api_m5.db"
    storage = TraceStorage(db_path=str(db_file))
    app.dependency_overrides[get_storage] = lambda: storage
    client = TestClient(app)
    yield client, storage
    app.dependency_overrides.clear()

def test_api_full_experiment_workflow(test_client):
    """End-to-end API test: run experiment, retrieve report, manifest, comparisons, and export."""
    client, storage = test_client

    payload = {
        "task_ids": ["ARITH-001"],
        "agent_modes": ["baseline", "traceguard_recovery"],
        "experiment_type": "standard",
    }

    # 1. POST /experiments/run
    res = client.post("/experiments/run", json=payload)
    assert res.status_code == 201
    data = res.json()
    exp_id = data["experiment_id"]
    assert exp_id.startswith("exp_")

    # 2. GET /experiments/{id}/manifest
    res_man = client.get(f"/experiments/{exp_id}/manifest")
    assert res_man.status_code == 200
    man = res_man.json()
    assert man["experiment_id"] == exp_id
    assert "configuration_hash" in man

    # 3. GET /experiments/{id}/report
    res_rep = client.get(f"/experiments/{exp_id}/report")
    assert res_rep.status_code == 200
    assert "# TraceGuard Research Report" in res_rep.text

    # 4. GET /experiments/{id}/comparisons
    res_comp = client.get(f"/experiments/{exp_id}/comparisons")
    assert res_comp.status_code == 200
    comps = res_comp.json()
    assert len(comps) > 0

    # 5. GET /experiments/{id}/failure-analysis
    res_fail = client.get(f"/experiments/{exp_id}/failure-analysis")
    assert res_fail.status_code == 200
    fail_data = res_fail.json()
    assert "categories" in fail_data

    # 6. GET /experiments/{id}/results with pagination
    res_res = client.get(f"/experiments/{exp_id}/results?limit=1&offset=0")
    assert res_res.status_code == 200
    items = res_res.json()
    assert len(items) == 1

    # 7. GET /experiments/{id}/export format=json and jsonl
    res_exp_json = client.get(f"/experiments/{exp_id}/export?format=json")
    assert res_exp_json.status_code == 200
    assert "results" in res_exp_json.json()

    res_exp_jsonl = client.get(f"/experiments/{exp_id}/export?format=jsonl")
    assert res_exp_jsonl.status_code == 200
    assert res_exp_jsonl.text.strip() != ""

def test_api_generate_report_endpoint_and_ondemand(test_client):
    """Test explicit generate-report endpoint and on-demand report generation."""
    client, storage = test_client

    # Run single-mode benchmark request that does not run full multi-mode pipeline
    payload = {
        "benchmark_version": "v1.0",
        "task_ids": ["ARITH-001"],
        "agent_mode": "baseline",
        "repetitions": 1,
    }
    res = client.post("/experiments/run", json=payload)
    assert res.status_code == 201
    exp_id = res.json()["experiment_id"]

    # 1. On-demand GET report
    res_rep = client.get(f"/experiments/{exp_id}/report")
    assert res_rep.status_code == 200
    assert "# TraceGuard Research Report" in res_rep.text

    # 2. JSON format report
    res_json = client.get(f"/experiments/{exp_id}/report?format=json")
    assert res_json.status_code == 200
    data = res_json.json()
    assert data["experiment_id"] == exp_id
    assert "report_markdown" in data

    # 3. Explicit POST generate-report
    res_gen = client.post(f"/experiments/{exp_id}/generate-report")
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["status"] == "success"
    assert "report_markdown" in gen_data
    assert "manifest" in gen_data

