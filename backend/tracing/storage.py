"""SQLite and JSONL storage for tasks and execution traces."""
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from backend.config import settings
from backend.models.schemas import TaskResponse, TraceEvent, VerificationResult

class TraceStorage:
    """Manages SQLite persistence and JSONL export for tasks and traces."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DATABASE_PATH
        self._lock = threading.Lock()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    final_answer TEXT,
                    error_info TEXT,
                    verification_json TEXT,
                    steps_count INTEGER DEFAULT 0,
                    duration_ms REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
            """)
            # Traces table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trace_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    tool_name TEXT,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    duration_ms REAL,
                    input_summary TEXT,
                    output_summary TEXT,
                    error_type TEXT,
                    model_tokens_json TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trace_events_task_id 
                ON trace_events(task_id, id)
            """)
            conn.commit()

    def save_task(self, task: TaskResponse) -> None:
        """Upsert a task record."""
        verif_json = task.verification.model_dump_json() if task.verification else None
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tasks (
                    task_id, run_id, task, status, final_answer, error_info,
                    verification_json, steps_count, duration_ms, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    status=excluded.status,
                    final_answer=excluded.final_answer,
                    error_info=excluded.error_info,
                    verification_json=excluded.verification_json,
                    steps_count=excluded.steps_count,
                    duration_ms=excluded.duration_ms,
                    completed_at=excluded.completed_at
            """, (
                task.task_id,
                task.run_id,
                task.task,
                task.status,
                task.final_answer,
                task.error_info,
                verif_json,
                task.steps_count,
                task.duration_ms,
                task.created_at,
                task.completed_at,
            ))
            conn.commit()

    def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """Retrieve task by task_id."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None

            verif_data = json.loads(row["verification_json"]) if row["verification_json"] else None
            verification = VerificationResult.model_validate(verif_data) if verif_data else None

            return TaskResponse(
                task_id=row["task_id"],
                run_id=row["run_id"],
                task=row["task"],
                status=row["status"],
                final_answer=row["final_answer"],
                error_info=row["error_info"],
                verification=verification,
                steps_count=row["steps_count"],
                duration_ms=row["duration_ms"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
            )

    def save_events(self, events: List[TraceEvent]) -> None:
        """Insert a batch of trace events."""
        if not events:
            return
        records = [
            (
                e.task_id,
                e.run_id,
                e.step_index,
                e.event_type,
                e.tool_name,
                e.status,
                e.timestamp,
                e.duration_ms,
                e.input_summary,
                e.output_summary,
                e.error_type,
                json.dumps(e.model_tokens) if e.model_tokens else None,
            )
            for e in events
        ]
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO trace_events (
                    task_id, run_id, step_index, event_type, tool_name, status,
                    timestamp, duration_ms, input_summary, output_summary,
                    error_type, model_tokens_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()

    def get_events(self, task_id: str) -> List[TraceEvent]:
        """Get ordered execution trace events for a given task."""
        with self._lock, self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_id, run_id, step_index, event_type, tool_name, status,
                       timestamp, duration_ms, input_summary, output_summary,
                       error_type, model_tokens_json
                FROM trace_events
                WHERE task_id = ?
                ORDER BY id ASC
            """, (task_id,))
            rows = cursor.fetchall()
            events = []
            for r in rows:
                tokens = json.loads(r["model_tokens_json"]) if r["model_tokens_json"] else None
                events.append(TraceEvent(
                    task_id=r["task_id"],
                    run_id=r["run_id"],
                    step_index=r["step_index"],
                    event_type=r["event_type"],
                    tool_name=r["tool_name"],
                    status=r["status"],
                    timestamp=r["timestamp"],
                    duration_ms=r["duration_ms"],
                    input_summary=r["input_summary"],
                    output_summary=r["output_summary"],
                    error_type=r["error_type"],
                    model_tokens=tokens,
                ))
            return events

    def export_jsonl(self, task_id: str) -> str:
        """Export execution trace for a task as a JSONL formatted string."""
        events = self.get_events(task_id)
        lines = [e.model_dump_json() for e in events]
        return "\n".join(lines) + ("\n" if lines else "")
