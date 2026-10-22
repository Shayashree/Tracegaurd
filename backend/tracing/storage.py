"""SQLite and JSONL storage for tasks and execution traces."""
from __future__ import annotations
import json
import logging
import os
import shutil
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from backend.config import BASE_DIR, settings
from backend.models.schemas import TaskResponse, TraceEvent, VerificationResult

from contextlib import contextmanager

logger = logging.getLogger(__name__)

class TraceStorage:
    """Manages SQLite persistence and JSONL export for tasks and traces."""

    def __init__(self, db_path: Optional[str] = None):
        is_serverless = bool(
            os.environ.get("VERCEL")
            or os.environ.get("VERCEL_ENV")
            or os.environ.get("VERCEL_REGION")
            or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
            or os.environ.get("LAMBDA_TASK_ROOT")
            or str(Path(__file__).resolve()).startswith("/var/task")
        )
        if is_serverless and not db_path:
            import tempfile
            tmp_dir = Path(tempfile.gettempdir())
            tmp_dir.mkdir(parents=True, exist_ok=True)
            tmp_db = tmp_dir / "traceguard.db"
            if not tmp_db.exists():
                candidates = [
                    Path(BASE_DIR) / "data" / "traceguard.db",
                    Path(BASE_DIR) / "traceguard.db",
                    Path(__file__).resolve().parent.parent / "data" / "traceguard.db",
                    Path(__file__).resolve().parent.parent / "traceguard.db",
                    Path(__file__).resolve().parent.parent.parent / "data" / "traceguard.db",
                    Path(__file__).resolve().parent.parent.parent / "traceguard.db",
                    Path.cwd() / "data" / "traceguard.db",
                    Path.cwd() / "traceguard.db",
                    Path("/var/task") / "data" / "traceguard.db",
                    Path("/var/task") / "traceguard.db",
                ]
                for cand in candidates:
                    try:
                        if cand.exists():
                            shutil.copyfile(str(cand), str(tmp_db))
                            logger.info(f"Initialized Vercel SQLite storage at {tmp_db} from {cand}")
                            break
                    except Exception as e:
                        logger.warning(f"Could not copy seed database from {cand} to {tmp_db}: {e}")
            self.db_path = str(tmp_db)
        else:
            self.db_path = db_path or settings.DATABASE_PATH
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            try:
                conn.execute("PRAGMA journal_mode = WAL;")
            except Exception:
                pass
            conn.execute("PRAGMA busy_timeout = 15000;")
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        try:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            with self._lock, self._connection() as conn:
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
                # Milestone 2: Experiments table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS experiments (
                        experiment_id TEXT PRIMARY KEY,
                        benchmark_version TEXT NOT NULL,
                        agent_mode TEXT NOT NULL,
                        status TEXT NOT NULL,
                        config_json TEXT,
                        total_tasks INTEGER DEFAULT 0,
                        completed_tasks INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL,
                        completed_at TEXT
                    )
                """)
                # Milestone 2: Experiment Results table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS experiment_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        experiment_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        benchmark_version TEXT NOT NULL,
                        agent_mode TEXT NOT NULL,
                        terminal_status TEXT NOT NULL,
                        expected_answer TEXT,
                        observed_answer TEXT,
                        verification_status TEXT NOT NULL,
                        verification_message TEXT,
                        step_count INTEGER DEFAULT 0,
                        tool_call_count INTEGER DEFAULT 0,
                        tool_error_count INTEGER DEFAULT 0,
                        total_duration_ms REAL DEFAULT 0.0,
                        model_tokens_json TEXT,
                        estimated_cost REAL,
                        trace_reference_json TEXT,
                        failure_scenario_id TEXT,
                        started_at TEXT NOT NULL,
                        completed_at TEXT NOT NULL,
                        FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id)
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_exp_results_exp_id 
                    ON experiment_results(experiment_id, id)
                """)
                # Milestone 2: Experiment Metrics table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS experiment_metrics (
                        experiment_id TEXT PRIMARY KEY,
                        metrics_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id)
                    )
                """)
                # Milestone 3: Diagnostic Reports table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS diagnostic_reports (
                        diagnostic_id TEXT PRIMARY KEY,
                        experiment_id TEXT,
                        task_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        detector_version TEXT NOT NULL,
                        diagnostic_status TEXT NOT NULL,
                        primary_failure_category TEXT,
                        severity TEXT NOT NULL,
                        confirmation_status TEXT NOT NULL,
                        analysis_duration_ms REAL,
                        report_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_diag_run_id 
                    ON diagnostic_reports(run_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_diag_task_id 
                    ON diagnostic_reports(task_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_diag_experiment_id 
                    ON diagnostic_reports(experiment_id)
                """)
                # Milestone 3: Diagnostic Findings table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS diagnostic_findings (
                        finding_id TEXT PRIMARY KEY,
                        diagnostic_id TEXT NOT NULL,
                        rule_id TEXT NOT NULL,
                        failure_category TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        confirmation_status TEXT NOT NULL,
                        explanation TEXT,
                        recommended_next_action TEXT,
                        FOREIGN KEY(diagnostic_id) REFERENCES diagnostic_reports(diagnostic_id)
                    )
                """)

                # Milestone 4: Recovery Reports table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS recovery_reports (
                        recovery_id TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        recovery_attempt_id TEXT NOT NULL,
                        experiment_id TEXT,
                        policy_id TEXT NOT NULL,
                        policy_version TEXT NOT NULL,
                        initial_failure_category TEXT,
                        terminal_status TEXT NOT NULL,
                        original_status TEXT NOT NULL,
                        original_verification_status TEXT,
                        final_verification_status TEXT,
                        recovery_attempts_count INTEGER DEFAULT 1,
                        recovery_duration_ms REAL DEFAULT 0.0,
                        additional_tool_calls INTEGER DEFAULT 0,
                        additional_model_calls INTEGER DEFAULT 0,
                        budget_used_json TEXT,
                        final_answer TEXT,
                        report_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(task_id) REFERENCES tasks(task_id)
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_recovery_task_id 
                    ON recovery_reports(task_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_recovery_run_id 
                    ON recovery_reports(run_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_recovery_experiment_id 
                    ON recovery_reports(experiment_id)
                """)

                # Milestone 4: Recovery Attempts table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS recovery_attempts (
                        attempt_id TEXT PRIMARY KEY,
                        recovery_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        attempt_index INTEGER NOT NULL,
                        policy_id TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        duration_ms REAL DEFAULT 0.0,
                        error_info TEXT,
                        attempt_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(recovery_id) REFERENCES recovery_reports(recovery_id)
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_attempts_recovery_id 
                    ON recovery_attempts(recovery_id)
                """)

                # Milestone 5: Experiment Artifacts table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS experiment_artifacts (
                        experiment_id TEXT PRIMARY KEY,
                        configuration_hash TEXT,
                        manifest_json TEXT,
                        report_markdown TEXT,
                        comparisons_json TEXT,
                        failure_analysis_json TEXT,
                        ablation_json TEXT,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(experiment_id) REFERENCES experiments(experiment_id)
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_exp_artifacts_exp_id 
                    ON experiment_artifacts(experiment_id)
                """)

                # Safe migrations for trace_events recovery columns
                for col, col_type in [
                    ("recovery_attempt_id", "TEXT"),
                    ("policy_id", "TEXT"),
                    ("action_type", "TEXT"),
                    ("finding_ids_json", "TEXT"),
                    ("remaining_budget_json", "TEXT"),
                ]:
                    try:
                        cursor.execute(f"ALTER TABLE trace_events ADD COLUMN {col} {col_type}")
                    except sqlite3.OperationalError:
                        pass

                conn.commit()
        except Exception as e:
            logger.warning(f"Advisory during _init_db on {self.db_path}: {e}")

    def save_task(self, task: TaskResponse) -> None:
        """Upsert a task record."""
        verif_json = task.verification.model_dump_json() if task.verification else None
        with self._lock, self._connection() as conn:
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
        """Retrieve task by task_id, run_id, or benchmark task_id."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                # Resolve by run_id
                cursor.execute("SELECT * FROM tasks WHERE run_id = ?", (task_id,))
                row = cursor.fetchone()
            if not row:
                # Resolve by benchmark task_id from experiment_results
                cursor.execute(
                    "SELECT run_id FROM experiment_results WHERE task_id = ? ORDER BY id DESC LIMIT 1",
                    (task_id,)
                )
                res = cursor.fetchone()
                if res and res["run_id"]:
                    cursor.execute("SELECT * FROM tasks WHERE run_id = ?", (res["run_id"],))
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

    def get_recent_task_summaries(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch latest executed tasks with resolved benchmark task IDs and experiment references."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.task_id, t.run_id, t.task, t.status, t.steps_count, t.duration_ms, t.created_at,
                       er.task_id as benchmark_task_id, er.experiment_id
                FROM tasks t
                LEFT JOIN experiment_results er ON t.run_id = er.run_id
                ORDER BY t.created_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            result = []
            for r in rows:
                bench_id = r["benchmark_task_id"]
                tid = r["task_id"]
                if bench_id:
                    label = f"{bench_id} ({tid})"
                else:
                    snippet = (r["task"] or "").strip().replace("\n", " ")
                    short_snippet = snippet[:28] + ("..." if len(snippet) > 28 else "")
                    label = f"Custom: \"{short_snippet}\" ({tid})" if short_snippet else tid
                result.append({
                    "task_id": tid,
                    "run_id": r["run_id"],
                    "benchmark_task_id": bench_id,
                    "experiment_id": r["experiment_id"],
                    "task_prompt": r["task"],
                    "status": r["status"],
                    "steps_count": r["steps_count"],
                    "duration_ms": r["duration_ms"],
                    "created_at": r["created_at"],
                    "display_label": label,
                })
            return result

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
                e.recovery_attempt_id,
                e.policy_id,
                e.action_type,
                json.dumps(e.finding_ids) if e.finding_ids else None,
                json.dumps(e.remaining_budget) if e.remaining_budget else None,
            )
            for e in events
        ]
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO trace_events (
                    task_id, run_id, step_index, event_type, tool_name, status,
                    timestamp, duration_ms, input_summary, output_summary,
                    error_type, model_tokens_json, recovery_attempt_id, policy_id,
                    action_type, finding_ids_json, remaining_budget_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()

    def get_events(self, task_id: str) -> List[TraceEvent]:
        """Get ordered execution trace events for a given task, run_id, or benchmark task_id."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_id, run_id, step_index, event_type, tool_name, status,
                       timestamp, duration_ms, input_summary, output_summary,
                       error_type, model_tokens_json, recovery_attempt_id, policy_id,
                       action_type, finding_ids_json, remaining_budget_json
                FROM trace_events
                WHERE task_id = ?
                ORDER BY id ASC
            """, (task_id,))
            rows = cursor.fetchall()

            if not rows:
                # Check if task_id matches a run_id directly
                cursor.execute("""
                    SELECT task_id, run_id, step_index, event_type, tool_name, status,
                           timestamp, duration_ms, input_summary, output_summary,
                           error_type, model_tokens_json, recovery_attempt_id, policy_id,
                           action_type, finding_ids_json, remaining_budget_json
                    FROM trace_events
                    WHERE run_id = ?
                    ORDER BY id ASC
                """, (task_id,))
                rows = cursor.fetchall()

            if not rows:
                # Check if task_id matches a benchmark task_id in experiment_results
                cursor.execute(
                    "SELECT run_id FROM experiment_results WHERE task_id = ? ORDER BY id DESC LIMIT 1",
                    (task_id,)
                )
                res = cursor.fetchone()
                if res and res["run_id"]:
                    cursor.execute("""
                        SELECT task_id, run_id, step_index, event_type, tool_name, status,
                               timestamp, duration_ms, input_summary, output_summary,
                               error_type, model_tokens_json, recovery_attempt_id, policy_id,
                               action_type, finding_ids_json, remaining_budget_json
                        FROM trace_events
                        WHERE run_id = ?
                        ORDER BY id ASC
                    """, (res["run_id"],))
                    rows = cursor.fetchall()

            events = []
            for r in rows:
                tokens = json.loads(r["model_tokens_json"]) if r["model_tokens_json"] else None
                f_ids = json.loads(r["finding_ids_json"]) if "finding_ids_json" in r.keys() and r["finding_ids_json"] else None
                rem_b = json.loads(r["remaining_budget_json"]) if "remaining_budget_json" in r.keys() and r["remaining_budget_json"] else None
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
                    recovery_attempt_id=r["recovery_attempt_id"] if "recovery_attempt_id" in r.keys() else None,
                    policy_id=r["policy_id"] if "policy_id" in r.keys() else None,
                    action_type=r["action_type"] if "action_type" in r.keys() else None,
                    finding_ids=f_ids,
                    remaining_budget=rem_b,
                ))
            return events

    def export_jsonl(self, task_id: str) -> str:
        """Export execution trace for a task as a JSONL formatted string."""
        events = self.get_events(task_id)
        lines = [e.model_dump_json() for e in events]
        return "\n".join(lines) + ("\n" if lines else "")

    # -----------------------------------------------------------------------
    # Milestone 2: Experiment Storage
    # -----------------------------------------------------------------------

    def save_experiment(self, exp: Any) -> None:
        """Upsert experiment record."""
        config_str = json.dumps(exp.config) if hasattr(exp, "config") and exp.config else "{}"
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO experiments (
                    experiment_id, benchmark_version, agent_mode, status,
                    config_json, total_tasks, completed_tasks, created_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(experiment_id) DO UPDATE SET
                    status=excluded.status,
                    total_tasks=excluded.total_tasks,
                    completed_tasks=excluded.completed_tasks,
                    completed_at=excluded.completed_at
            """, (
                exp.experiment_id,
                exp.benchmark_version,
                exp.agent_mode,
                exp.status,
                config_str,
                exp.total_tasks,
                exp.completed_tasks,
                exp.created_at,
                exp.completed_at,
            ))
            conn.commit()

    def get_experiment(self, experiment_id: str) -> Optional[Any]:
        """Fetch experiment metadata by experiment_id."""
        from backend.evaluation.schemas import ExperimentSummary
        row = None
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM experiments WHERE experiment_id = ?", (experiment_id,))
            row = cursor.fetchone()
        if not row:
            return None
        cfg = json.loads(row["config_json"]) if row["config_json"] else {}
        metrics = self.get_experiment_metrics(experiment_id)
        return ExperimentSummary(
            experiment_id=row["experiment_id"],
            benchmark_version=row["benchmark_version"],
            agent_mode=row["agent_mode"],
            status=row["status"],
            total_tasks=row["total_tasks"],
            completed_tasks=row["completed_tasks"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            config=cfg,
            metrics=metrics,
        )

    def list_experiments(self) -> List[Any]:
        """List all experiments ordered by creation time descending."""
        from backend.evaluation.schemas import ExperimentSummary
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM experiments ORDER BY created_at DESC")
            rows = cursor.fetchall()
            summaries = []
            for row in rows:
                cfg = json.loads(row["config_json"]) if row["config_json"] else {}
                summaries.append(ExperimentSummary(
                    experiment_id=row["experiment_id"],
                    benchmark_version=row["benchmark_version"],
                    agent_mode=row["agent_mode"],
                    status=row["status"],
                    total_tasks=row["total_tasks"],
                    completed_tasks=row["completed_tasks"],
                    created_at=row["created_at"],
                    completed_at=row["completed_at"],
                    config=cfg,
                    metrics=None,
                ))
            return summaries

    def save_experiment_results(self, results: List[Any]) -> None:
        """Batch insert task execution results for an experiment."""
        if not results:
            return
        records = [
            (
                r.experiment_id,
                r.task_id,
                r.run_id,
                r.benchmark_version,
                r.agent_mode,
                r.terminal_status,
                json.dumps(r.expected_answer) if r.expected_answer is not None else None,
                r.observed_answer,
                r.verification_status,
                r.verification_message,
                r.step_count,
                r.tool_call_count,
                r.tool_error_count,
                r.total_duration_ms,
                json.dumps(r.model_tokens) if r.model_tokens else None,
                r.estimated_cost,
                json.dumps(r.trace_reference) if r.trace_reference else None,
                r.failure_scenario_id,
                r.started_at,
                r.completed_at,
            )
            for r in results
        ]
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.executemany("""
                INSERT INTO experiment_results (
                    experiment_id, task_id, run_id, benchmark_version, agent_mode,
                    terminal_status, expected_answer, observed_answer, verification_status,
                    verification_message, step_count, tool_call_count, tool_error_count,
                    total_duration_ms, model_tokens_json, estimated_cost, trace_reference_json,
                    failure_scenario_id, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()

    def get_experiment_results(self, experiment_id: str, limit: int = 500, offset: int = 0) -> List[Any]:
        """Fetch per-task execution results for an experiment."""
        from backend.evaluation.schemas import TaskExecutionResult
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM experiment_results
                WHERE experiment_id = ?
                ORDER BY id ASC
                LIMIT ? OFFSET ?
            """, (experiment_id, limit, offset))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                tokens = json.loads(r["model_tokens_json"]) if r["model_tokens_json"] else None
                trace_ref = json.loads(r["trace_reference_json"]) if r["trace_reference_json"] else {}
                expected = json.loads(r["expected_answer"]) if r["expected_answer"] is not None else None
                results.append(TaskExecutionResult(
                    experiment_id=r["experiment_id"],
                    task_id=r["task_id"],
                    run_id=r["run_id"],
                    benchmark_version=r["benchmark_version"],
                    agent_mode=r["agent_mode"],
                    started_at=r["started_at"],
                    completed_at=r["completed_at"],
                    terminal_status=r["terminal_status"],
                    expected_answer=expected,
                    observed_answer=r["observed_answer"],
                    verification_status=r["verification_status"],
                    verification_message=r["verification_message"],
                    step_count=r["step_count"],
                    tool_call_count=r["tool_call_count"],
                    tool_error_count=r["tool_error_count"],
                    total_duration_ms=r["total_duration_ms"],
                    model_tokens=tokens,
                    estimated_cost=r["estimated_cost"],
                    trace_reference=trace_ref,
                    failure_scenario_id=r["failure_scenario_id"],
                ))
            return results

    def save_experiment_metrics(self, experiment_id: str, metrics: Any) -> None:
        """Persist aggregated experiment metrics."""
        from backend.tracing.event_schema import current_utc_timestamp
        metrics_json = metrics.model_dump_json() if hasattr(metrics, "model_dump_json") else json.dumps(metrics)
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO experiment_metrics (experiment_id, metrics_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(experiment_id) DO UPDATE SET
                    metrics_json=excluded.metrics_json,
                    created_at=excluded.created_at
            """, (experiment_id, metrics_json, current_utc_timestamp()))
            conn.commit()

    def get_experiment_metrics(self, experiment_id: str) -> Optional[Any]:
        """Fetch aggregated experiment metrics."""
        from backend.evaluation.schemas import EvaluationMetrics
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT metrics_json FROM experiment_metrics WHERE experiment_id = ?", (experiment_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = json.loads(row["metrics_json"])
            return EvaluationMetrics.model_validate(data)

    def get_events_by_run_id(self, run_id: str) -> List[TraceEvent]:
        """Get ordered execution trace events for a given run_id."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT task_id, run_id, step_index, event_type, tool_name, status,
                       timestamp, duration_ms, input_summary, output_summary,
                       error_type, model_tokens_json
                FROM trace_events
                WHERE run_id = ?
                ORDER BY id ASC
            """, (run_id,))
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

    def save_diagnostic_report(self, report: Any) -> None:
        """Persist a diagnostic report and its associated findings."""
        from backend.reliability.diagnostic_report import DiagnosticReport
        if isinstance(report, dict):
            report_obj = DiagnosticReport.model_validate(report)
        else:
            report_obj = report

        report_json = report_obj.model_dump_json()
        primary_cat = report_obj.primary_failure_category.value if report_obj.primary_failure_category else None

        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO diagnostic_reports (
                    diagnostic_id, experiment_id, task_id, run_id, detector_version,
                    diagnostic_status, primary_failure_category, severity,
                    confirmation_status, analysis_duration_ms, report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(diagnostic_id) DO UPDATE SET
                    report_json=excluded.report_json,
                    diagnostic_status=excluded.diagnostic_status,
                    primary_failure_category=excluded.primary_failure_category,
                    severity=excluded.severity,
                    confirmation_status=excluded.confirmation_status
            """, (
                report_obj.diagnostic_id,
                report_obj.experiment_id,
                report_obj.task_id,
                report_obj.run_id,
                report_obj.detector_version,
                report_obj.diagnostic_status.value if hasattr(report_obj.diagnostic_status, "value") else str(report_obj.diagnostic_status),
                primary_cat,
                report_obj.severity.value if hasattr(report_obj.severity, "value") else str(report_obj.severity),
                report_obj.confirmation_status.value if hasattr(report_obj.confirmation_status, "value") else str(report_obj.confirmation_status),
                report_obj.analysis_duration_ms,
                report_json,
                report_obj.created_at,
            ))

            for f in report_obj.findings:
                cursor.execute("""
                    INSERT OR REPLACE INTO diagnostic_findings (
                        finding_id, diagnostic_id, rule_id, failure_category,
                        severity, confirmation_status, explanation, recommended_next_action
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f.finding_id,
                    report_obj.diagnostic_id,
                    f.rule_id,
                    f.failure_category.value if hasattr(f.failure_category, "value") else str(f.failure_category),
                    f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                    f.confirmation_status.value if hasattr(f.confirmation_status, "value") else str(f.confirmation_status),
                    f.explanation,
                    f.recommended_next_action,
                ))
            conn.commit()

    def get_diagnostic_report(self, diagnostic_id: str) -> Optional[Any]:
        """Fetch a diagnostic report by diagnostic_id."""
        from backend.reliability.diagnostic_report import DiagnosticReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT report_json FROM diagnostic_reports WHERE diagnostic_id = ?", (diagnostic_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = json.loads(row["report_json"])
            return DiagnosticReport.model_validate(data)

    def get_diagnostics_for_run(self, run_id: str) -> Optional[Any]:
        """Fetch latest diagnostic report for a specific run_id."""
        from backend.reliability.diagnostic_report import DiagnosticReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_json FROM diagnostic_reports
                WHERE run_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            data = json.loads(row["report_json"])
            return DiagnosticReport.model_validate(data)

    def get_diagnostics_for_task(self, task_id: str) -> List[Any]:
        """Fetch all diagnostic reports for a task_id, run_id, or benchmark task_id."""
        from backend.reliability.diagnostic_report import DiagnosticReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_json FROM diagnostic_reports
                WHERE task_id = ?
                ORDER BY created_at DESC
            """, (task_id,))
            rows = cursor.fetchall()
            if not rows:
                cursor.execute("""
                    SELECT report_json FROM diagnostic_reports
                    WHERE run_id = ?
                    ORDER BY created_at DESC
                """, (task_id,))
                rows = cursor.fetchall()
            if not rows:
                cursor.execute(
                    "SELECT run_id FROM experiment_results WHERE task_id = ? ORDER BY id DESC LIMIT 1",
                    (task_id,)
                )
                res = cursor.fetchone()
                if res and res["run_id"]:
                    cursor.execute("""
                        SELECT report_json FROM diagnostic_reports
                        WHERE run_id = ?
                        ORDER BY created_at DESC
                    """, (res["run_id"],))
                    rows = cursor.fetchall()
            return [DiagnosticReport.model_validate(json.loads(r["report_json"])) for r in rows]

    def get_diagnostics_for_experiment(self, experiment_id: str) -> List[Any]:
        """Fetch all diagnostic reports for an experiment_id."""
        from backend.reliability.diagnostic_report import DiagnosticReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_json FROM diagnostic_reports
                WHERE experiment_id = ?
                ORDER BY created_at ASC
            """, (experiment_id,))
            rows = cursor.fetchall()
            return [DiagnosticReport.model_validate(json.loads(r["report_json"])) for r in rows]

    def get_all_diagnostic_reports(
        self,
        limit: int = 50,
        offset: int = 0,
        experiment_id: Optional[str] = None,
        failure_category: Optional[str] = None,
        diagnostic_status: Optional[str] = None,
    ) -> List[Any]:
        """Fetch diagnostic reports with filtering and pagination."""
        from backend.reliability.diagnostic_report import DiagnosticReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []
            if experiment_id:
                conditions.append("experiment_id = ?")
                params.append(experiment_id)
            if failure_category:
                conditions.append("primary_failure_category = ?")
                params.append(failure_category)
            if diagnostic_status:
                conditions.append("diagnostic_status = ?")
                params.append(diagnostic_status)
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            query = f"""
                SELECT report_json FROM diagnostic_reports
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [DiagnosticReport.model_validate(json.loads(r["report_json"])) for r in rows]

    # -----------------------------------------------------------------------
    # Milestone 4: Recovery Storage
    # -----------------------------------------------------------------------
    def save_recovery_report(self, report: Any) -> None:
        """Persist a recovery report and its child attempt records."""
        from backend.reliability.recovery_report import RecoveryReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recovery_reports (
                    recovery_id, task_id, run_id, recovery_attempt_id, experiment_id,
                    policy_id, policy_version, initial_failure_category, terminal_status,
                    original_status, original_verification_status, final_verification_status,
                    recovery_attempts_count, recovery_duration_ms, additional_tool_calls,
                    additional_model_calls, budget_used_json, final_answer, report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(recovery_id) DO UPDATE SET
                    terminal_status=excluded.terminal_status,
                    final_verification_status=excluded.final_verification_status,
                    final_answer=excluded.final_answer,
                    recovery_duration_ms=excluded.recovery_duration_ms,
                    report_json=excluded.report_json
            """, (
                report.recovery_id,
                report.task_id,
                report.run_id,
                report.recovery_attempt_id,
                report.experiment_id,
                report.policy_id,
                report.policy_version,
                report.initial_failure_category,
                report.terminal_status.value if hasattr(report.terminal_status, "value") else str(report.terminal_status),
                report.original_status,
                report.original_verification_status,
                report.final_verification_status,
                len(report.attempts) or 1,
                report.total_recovery_duration_ms,
                report.additional_tool_calls,
                report.additional_model_calls,
                report.budget_usage.model_dump_json() if hasattr(report.budget_usage, "model_dump_json") else None,
                report.final_answer,
                report.model_dump_json(),
                report.created_at,
            ))

            # Save individual attempts
            for attempt in report.attempts:
                cursor.execute("""
                    INSERT OR REPLACE INTO recovery_attempts (
                        attempt_id, recovery_id, task_id, run_id, attempt_index,
                        policy_id, action_type, status, duration_ms, error_info,
                        attempt_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    attempt.attempt_id,
                    report.recovery_id,
                    report.task_id,
                    report.run_id,
                    attempt.attempt_index,
                    attempt.policy_id,
                    attempt.action_type,
                    attempt.status,
                    attempt.duration_ms,
                    attempt.error_message,
                    attempt.model_dump_json(),
                    report.created_at,
                ))
            conn.commit()

    def get_recovery_report(self, recovery_id: str) -> Optional[Any]:
        """Fetch recovery report by recovery_id."""
        from backend.reliability.recovery_report import RecoveryReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT report_json FROM recovery_reports WHERE recovery_id = ?", (recovery_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return RecoveryReport.model_validate(json.loads(row["report_json"]))

    def get_recovery_for_task(self, task_id: str) -> Optional[Any]:
        """Fetch latest recovery report for a specific task_id, run_id, or benchmark task_id."""
        from backend.reliability.recovery_report import RecoveryReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_json FROM recovery_reports
                WHERE task_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (task_id,))
            row = cursor.fetchone()
            if not row:
                cursor.execute("""
                    SELECT report_json FROM recovery_reports
                    WHERE run_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (task_id,))
                row = cursor.fetchone()
            if not row:
                cursor.execute(
                    "SELECT run_id FROM experiment_results WHERE task_id = ? ORDER BY id DESC LIMIT 1",
                    (task_id,)
                )
                res = cursor.fetchone()
                if res and res["run_id"]:
                    cursor.execute("""
                        SELECT report_json FROM recovery_reports
                        WHERE run_id = ?
                        ORDER BY created_at DESC LIMIT 1
                    """, (res["run_id"],))
                    row = cursor.fetchone()
            if not row:
                return None
            return RecoveryReport.model_validate(json.loads(row["report_json"]))

    def get_recovery_for_run(self, run_id: str) -> Optional[Any]:
        """Fetch latest recovery report for a specific run_id."""
        from backend.reliability.recovery_report import RecoveryReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_json FROM recovery_reports
                WHERE run_id = ?
                ORDER BY created_at DESC LIMIT 1
            """, (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return RecoveryReport.model_validate(json.loads(row["report_json"]))

    def get_recovery_reports_for_experiment(self, experiment_id: str) -> List[Any]:
        """Fetch all recovery reports for an experiment."""
        from backend.reliability.recovery_report import RecoveryReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_json FROM recovery_reports
                WHERE experiment_id = ?
                ORDER BY created_at ASC
            """, (experiment_id,))
            rows = cursor.fetchall()
            return [RecoveryReport.model_validate(json.loads(r["report_json"])) for r in rows]

    def get_all_recovery_reports(
        self,
        limit: int = 50,
        offset: int = 0,
        experiment_id: Optional[str] = None,
        policy_id: Optional[str] = None,
        terminal_status: Optional[str] = None,
    ) -> List[Any]:
        """Fetch recovery reports with filtering and pagination."""
        from backend.reliability.recovery_report import RecoveryReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            conditions = []
            params: List[Any] = []
            if experiment_id:
                conditions.append("experiment_id = ?")
                params.append(experiment_id)
            if policy_id:
                conditions.append("policy_id = ?")
                params.append(policy_id)
            if terminal_status:
                conditions.append("terminal_status = ?")
                params.append(terminal_status)
            where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            query = f"""
                SELECT report_json FROM recovery_reports
                {where_clause}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [RecoveryReport.model_validate(json.loads(r["report_json"])) for r in rows]

    # -----------------------------------------------------------------------
    # Milestone 5: Experiment Artifacts Storage & Pagination
    # -----------------------------------------------------------------------
    def save_experiment_artifacts(
        self,
        experiment_id: str,
        configuration_hash: str = "",
        manifest: Optional[Any] = None,
        report_md: Optional[str] = None,
        comparisons: Optional[Any] = None,
        failure_analysis: Optional[Any] = None,
        ablation: Optional[Any] = None,
    ) -> None:
        """Persist structured experiment artifacts (manifest, report, comparisons, ablation)."""
        from backend.tracing.event_schema import current_utc_timestamp
        manifest_str = manifest.model_dump_json() if hasattr(manifest, "model_dump_json") else (json.dumps(manifest) if manifest else None)
        comparisons_str = json.dumps([c.model_dump() if hasattr(c, "model_dump") else c for c in comparisons]) if comparisons else None
        failure_str = failure_analysis.model_dump_json() if hasattr(failure_analysis, "model_dump_json") else (json.dumps(failure_analysis) if failure_analysis else None)
        ablation_str = ablation.model_dump_json() if hasattr(ablation, "model_dump_json") else (json.dumps(ablation) if ablation else None)

        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO experiment_artifacts (
                    experiment_id, configuration_hash, manifest_json, report_markdown,
                    comparisons_json, failure_analysis_json, ablation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(experiment_id) DO UPDATE SET
                    configuration_hash=excluded.configuration_hash,
                    manifest_json=excluded.manifest_json,
                    report_markdown=excluded.report_markdown,
                    comparisons_json=excluded.comparisons_json,
                    failure_analysis_json=excluded.failure_analysis_json,
                    ablation_json=excluded.ablation_json
            """, (
                experiment_id,
                configuration_hash,
                manifest_str,
                report_md,
                comparisons_str,
                failure_str,
                ablation_str,
                current_utc_timestamp(),
            ))
            conn.commit()

    def get_experiment_manifest(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Fetch reproducibility manifest dictionary by experiment_id."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT manifest_json FROM experiment_artifacts WHERE experiment_id = ?", (experiment_id,))
            row = cursor.fetchone()
            if row and row["manifest_json"]:
                return json.loads(row["manifest_json"])
            return None

    def get_experiment_report(self, experiment_id: str) -> Optional[str]:
        """Fetch research report Markdown string by experiment_id."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT report_markdown FROM experiment_artifacts WHERE experiment_id = ?", (experiment_id,))
            row = cursor.fetchone()
            if row and row["report_markdown"]:
                return row["report_markdown"]
            return None

    def get_experiment_comparisons(self, experiment_id: str) -> Optional[List[Dict[str, Any]]]:
        """Fetch statistical paired comparisons by experiment_id."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT comparisons_json FROM experiment_artifacts WHERE experiment_id = ?", (experiment_id,))
            row = cursor.fetchone()
            if row and row["comparisons_json"]:
                return json.loads(row["comparisons_json"])
            return None

    def get_experiment_failure_analysis(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Fetch failure-specific analysis breakdown by experiment_id."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT failure_analysis_json FROM experiment_artifacts WHERE experiment_id = ?", (experiment_id,))
            row = cursor.fetchone()
            if row and row["failure_analysis_json"]:
                return json.loads(row["failure_analysis_json"])
            return None

    def get_experiment_ablation(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Fetch component ablation results by experiment_id."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ablation_json FROM experiment_artifacts WHERE experiment_id = ?", (experiment_id,))
            row = cursor.fetchone()
            if row and row["ablation_json"]:
                return json.loads(row["ablation_json"])
            return None

    def get_experiment_results_paginated(
        self,
        experiment_id: str,
        limit: int = 50,
        offset: int = 0,
        mode: Optional[str] = None
    ) -> Tuple[List[Any], int]:
        """Retrieve paginated task-level results for an experiment."""
        from backend.evaluation.schemas import TaskExecutionResult
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            count_query = "SELECT COUNT(*) as total FROM experiment_results WHERE experiment_id = ?"
            params: List[Any] = [experiment_id]
            if mode:
                count_query += " AND agent_mode = ?"
                params.append(mode)
            cursor.execute(count_query, params)
            total = cursor.fetchone()["total"]

            data_query = "SELECT * FROM experiment_results WHERE experiment_id = ?"
            data_params: List[Any] = [experiment_id]
            if mode:
                data_query += " AND agent_mode = ?"
                data_params.append(mode)
            data_query += " ORDER BY id ASC LIMIT ? OFFSET ?"
            data_params.extend([limit, offset])

            cursor.execute(data_query, data_params)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                trace_ref = json.loads(r["trace_reference_json"]) if r["trace_reference_json"] else {}
                model_toks = json.loads(r["model_tokens_json"]) if r["model_tokens_json"] else None
                results.append(TaskExecutionResult(
                    experiment_id=r["experiment_id"],
                    task_id=r["task_id"],
                    run_id=r["run_id"],
                    benchmark_version=r["benchmark_version"],
                    agent_mode=r["agent_mode"],
                    terminal_status=r["terminal_status"],
                    expected_answer=r["expected_answer"],
                    observed_answer=r["observed_answer"],
                    verification_status=r["verification_status"],
                    verification_message=r["verification_message"],
                    step_count=r["step_count"],
                    tool_call_count=r["tool_call_count"],
                    tool_error_count=r["tool_error_count"],
                    total_duration_ms=r["total_duration_ms"],
                    model_tokens=model_toks,
                    estimated_cost=r["estimated_cost"],
                    trace_reference=trace_ref,
                    failure_scenario_id=r["failure_scenario_id"],
                    started_at=r["started_at"],
                    completed_at=r["completed_at"],
                ))
            return results, total

    def export_experiment_jsonl(self, experiment_id: str) -> str:
        """Export all task execution results for an experiment in JSONL format."""
        results = self.get_experiment_results(experiment_id)
        lines = [r.model_dump_json() for r in results]
        return "\n".join(lines) + ("\n" if lines else "")

    # -----------------------------------------------------------------------
    # Milestone 7: Production Database Operations (Backup, Restore, Health)
    # -----------------------------------------------------------------------
    def backup_database(self, destination_path: str) -> str:
        """
        Execute an atomic online backup of the SQLite database.
        Safely copies data without locking concurrent readers.
        """
        dest_p = Path(destination_path)
        dest_p.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connection() as src_conn:
            dest_conn = sqlite3.connect(str(dest_p))
            try:
                src_conn.backup(dest_conn)
            finally:
                dest_conn.close()
        return str(dest_p.resolve())

    def restore_database(self, source_path: str) -> None:
        """
        Restore database atomically from a verified backup SQLite file.
        """
        src_p = Path(source_path)
        if not src_p.exists():
            raise FileNotFoundError(f"Backup file '{source_path}' does not exist.")
        with self._lock:
            src_conn = sqlite3.connect(str(src_p))
            dest_conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=15.0)
            try:
                src_conn.backup(dest_conn)
                return True
            finally:
                src_conn.close()
                dest_conn.close()

    def check_health(self) -> Dict[str, Any]:
        """Verify database connectivity, WAL mode, and table accessibility."""
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            journal_row = cursor.fetchone()
            journal_mode = journal_row[0] if journal_row else "unknown"

            cursor.execute("SELECT COUNT(*) as c FROM tasks;")
            tasks_count = cursor.fetchone()["c"]

            cursor.execute("SELECT COUNT(*) as c FROM experiments;")
            exp_count = cursor.fetchone()["c"]

            cursor.execute("SELECT COUNT(*) as c FROM trace_events;")
            traces_count = cursor.fetchone()["c"]

            return {
                "status": "connected",
                "database_path": str(Path(self.db_path).resolve()),
                "journal_mode": journal_mode,
                "counts": {
                    "tasks": tasks_count,
                    "experiments": exp_count,
                    "trace_events": traces_count,
                }
            }



