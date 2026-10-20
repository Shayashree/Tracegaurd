"""SQLite and JSONL storage for tasks and execution traces."""
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional
from backend.config import settings
from backend.models.schemas import TaskResponse, TraceEvent, VerificationResult

from contextlib import contextmanager

class TraceStorage:
    """Manages SQLite persistence and JSONL export for tasks and traces."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.DATABASE_PATH
        self._lock = threading.RLock()
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
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
            conn.commit()

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
        """Retrieve task by task_id."""
        with self._lock, self._connection() as conn:
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
        with self._lock, self._connection() as conn:
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
        with self._lock, self._connection() as conn:
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
        """Fetch all diagnostic reports for a task_id."""
        from backend.reliability.diagnostic_report import DiagnosticReport
        with self._lock, self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT report_json FROM diagnostic_reports
                WHERE task_id = ?
                ORDER BY created_at DESC
            """, (task_id,))
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

