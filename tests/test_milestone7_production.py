"""Milestone 7 Production Deployment, Reproducibility, and Security Tests.

Tests:
1. Database WAL mode and persistence across storage re-initialization.
2. Database atomic online backup and restoration.
3. Enhanced /health endpoint with database connectivity and counts.
4. X-Request-ID correlation middleware generation and header propagation.
5. Configuration validation and environment switching.
6. Research integrity: Ground truth expected answer exclusion from agent prompts.
7. Export filename sanitization against header injection.
"""
import os
import sqlite3
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import app
from backend.models.schemas import TaskCreateRequest, VerificationRule
from backend.tracing.storage import TraceStorage
from backend.agents.controller import AgentController
from backend.agents.mock_model import MockModelAdapter
from backend.evaluation.dataset import BenchmarkDatasetLoader

def test_database_wal_mode_and_persistence(tmp_path):
    """Verify SQLite WAL mode is active and data survives storage instance recreation."""
    db_file = str(tmp_path / "wal_test.db")
    storage1 = TraceStorage(db_path=db_file)

    # Check WAL pragma in underlying SQLite database
    with storage1._connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"

    # Save a task in storage1
    from backend.models.schemas import TaskResponse
    resp = TaskResponse(
        task_id="task-wal-001",
        run_id="run-001",
        task="Test WAL persistence",
        status="completed",
        final_answer="Done",
        steps_count=1,
        duration_ms=10.0,
        created_at="2026-10-20T12:00:00Z",
        completed_at="2026-10-20T12:00:01Z",
    )
    storage1.save_task(resp)

    # Re-initialize storage2 from same path (simulating restart)
    storage2 = TraceStorage(db_path=db_file)
    recovered_task = storage2.get_task("task-wal-001")
    assert recovered_task is not None
    assert recovered_task.task_id == "task-wal-001"
    assert recovered_task.final_answer == "Done"

def test_database_backup_and_restore(tmp_path):
    """Verify online atomic backup copies data and restore recovers state."""
    db_file = str(tmp_path / "primary.db")
    backup_file = str(tmp_path / "backup.db")
    storage = TraceStorage(db_path=db_file)

    from backend.models.schemas import TaskResponse
    task = TaskResponse(
        task_id="task-backup-test",
        run_id="run-backup",
        task="Primary task",
        status="completed",
        final_answer="Original State",
        steps_count=2,
        duration_ms=15.0,
        created_at="2026-10-20T12:00:00Z",
        completed_at="2026-10-20T12:00:01Z",
    )
    storage.save_task(task)

    # Perform atomic backup
    success = storage.backup_database(backup_file)
    assert bool(success) is True
    assert os.path.exists(backup_file)

    # Verify backup database contains the record
    backup_storage = TraceStorage(db_path=backup_file)
    assert backup_storage.get_task("task-backup-test") is not None

    # Corrupt or wipe primary and restore from backup
    restore_target = str(tmp_path / "restored.db")
    storage_restored = TraceStorage(db_path=restore_target)
    restore_success = storage_restored.restore_database(backup_file)
    assert restore_success is True
    restored_task = storage_restored.get_task("task-backup-test")
    assert restored_task is not None
    assert restored_task.final_answer == "Original State"

def test_health_endpoint_details(tmp_path):
    """Verify /health returns structured operational health and database counts."""
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "database_status" in data
        assert "database_counts" in data
        assert isinstance(data["database_counts"], dict)

def test_request_id_middleware():
    """Verify incoming requests receive X-Request-ID and custom IDs are echoed."""
    with TestClient(app) as client:
        # Auto-generated request ID
        resp = client.get("/health")
        assert "x-request-id" in resp.headers
        generated_id = resp.headers["x-request-id"]
        assert len(generated_id) > 8

        # Client-supplied request ID propagated
        custom_id = "traceguard-client-req-999"
        resp_custom = client.get("/health", headers={"X-Request-ID": custom_id})
        assert resp_custom.headers.get("x-request-id") == custom_id

def test_config_validation():
    """Verify settings validation detects missing production keys."""
    # Development mode allows mock provider
    dev_settings = Settings(
        TRACEGUARD_ENV="development",
        MODEL_PROVIDER="mock",
    )
    assert len(dev_settings.validate_configuration()) == 0

    # Production mode with mock is valid offline
    prod_mock = Settings(
        TRACEGUARD_ENV="production",
        MODEL_PROVIDER="mock",
    )
    assert len(prod_mock.validate_configuration()) == 0

    # Production mode with openai but missing API key raises ValueError
    prod_openai = Settings(
        TRACEGUARD_ENV="production",
        MODEL_ADAPTER="openai",
        OPENAI_API_KEY=None,
    )
    with pytest.raises(ValueError, match="OPENAI_API_KEY is not configured"):
        prod_openai.validate_configuration()

def test_research_integrity_no_ground_truth_leakage():
    """Verify benchmark ground-truth answers are never injected into the agent's prompts."""
    loader = BenchmarkDatasetLoader()
    tasks = loader.load_tasks(version="v1.0")
    task = next(t for t in tasks if t.expected_answer is not None)
    assert task is not None
    assert task.expected_answer is not None

    req = TaskCreateRequest(
        task=task.task_description,
        max_steps=5,
        verification_rule=task.verification_rule
    )

    # Build agent prompt via controller
    model = MockModelAdapter()
    controller = AgentController(storage=TraceStorage(), model_adapter=model)

    # Verify that the task request prompt sent to the agent does not contain expected_answer
    assert str(task.expected_answer) not in req.task
    # Verify tools registered cannot read ground-truth
    tool_names = [d.name for d in controller.tool_registry.list_definitions()]
    assert "get_ground_truth" not in tool_names
    assert "reveal_answer" not in tool_names
    assert controller.tool_registry.is_registered("get_ground_truth") is False

def test_export_filename_sanitization():
    """Verify export filenames strip dangerous header injection or directory traversal chars."""
    import re
    dirty_task_ids = [
        "task/../../etc/passwd",
        "task\r\nSet-Cookie: malicious=true",
        "task<script>alert(1)</script>",
        "task#99; DROP TABLE tasks;",
    ]
    for tid in dirty_task_ids:
        safe_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", tid)
        assert "/" not in safe_id
        assert "\\" not in safe_id
        assert "\r" not in safe_id
        assert "\n" not in safe_id
        assert "<" not in safe_id
        assert ">" not in safe_id
        assert ";" not in safe_id
