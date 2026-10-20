"""Trajectory Failure Detection Engine."""
import logging
import time
import uuid
from typing import Any, Dict, List, Optional
from backend.reliability.detector_config import DetectorConfig, default_detector_config
from backend.reliability.diagnostic_report import (
    DiagnosticFinding,
    DiagnosticReport,
    DiagnosticStatus,
    TrajectoryFeatures,
)
from backend.reliability.failure_classifier import FailureClassifier
from backend.reliability.failure_rules import DEFAULT_FAILURE_RULES, BaseFailureRule
from backend.reliability.feature_extractor import TrajectoryFeatureExtractor
from backend.tracing.event_schema import current_utc_timestamp

logger = logging.getLogger(__name__)

class TrajectoryFailureDetector:
    """
    Modular, trajectory-based failure detection engine.
    Analyzes observable execution traces, extracts deterministic features,
    evaluates explainable detection rules, and outputs structured diagnostic reports.
    Does NOT alter agent state, retry operations, or modify task execution.
    """

    def __init__(
        self,
        config: Optional[DetectorConfig] = None,
        rules: Optional[List[BaseFailureRule]] = None
    ):
        self.config = config or default_detector_config
        self.rules = rules or list(DEFAULT_FAILURE_RULES)

    def analyze(
        self,
        events: List[Any],
        task_id: str,
        run_id: str,
        experiment_id: Optional[str] = None,
        task_context: Optional[Dict[str, Any]] = None
    ) -> DiagnosticReport:
        """
        Analyze an execution trace and produce a complete diagnostic report.
        Deterministic: identical events and configuration yield identical reports.
        """
        start_time = time.perf_counter()
        diag_id = f"diag_{uuid.uuid4().hex[:12]}"

        # Standardize events
        parsed_events: List[Dict[str, Any]] = []
        for e in events:
            if isinstance(e, dict):
                parsed_events.append(e)
            elif hasattr(e, "model_dump"):
                parsed_events.append(e.model_dump())
            elif hasattr(e, "__dict__"):
                parsed_events.append(e.__dict__)

        ctx = task_context or {}
        configured_step_limit = ctx.get("max_steps")
        has_evidence_rule = (
            isinstance(ctx.get("verification_rule"), dict)
            and ctx["verification_rule"].get("type") in ("evidence_reference", "field_presence")
        )

        # 1. Feature Extraction
        features: TrajectoryFeatures = TrajectoryFeatureExtractor.extract_features(
            parsed_events,
            configured_step_limit=configured_step_limit,
            evidence_required=has_evidence_rule
        )

        # 2. Rule Evaluation
        findings: List[DiagnosticFinding] = []
        for rule in self.rules:
            try:
                finding = rule.evaluate(
                    features=features,
                    events=parsed_events,
                    config=self.config,
                    task_context=ctx
                )
                if finding is not None:
                    findings.append(finding)
            except Exception as e:
                logger.warning(f"Error evaluating rule {rule.rule_id}: {e}")

        # 3. Classification & Report Synthesis
        status, primary_cat, severity, confirmation, explanation = FailureClassifier.classify(
            features=features,
            findings=findings
        )

        all_evidence_ids = []
        for f in findings:
            all_evidence_ids.extend(f.evidence_event_ids)
        unique_evidence_ids = list(dict.fromkeys(all_evidence_ids))

        duration_ms = round((time.perf_counter() - start_time) * 1000, 3)

        return DiagnosticReport(
            diagnostic_id=diag_id,
            experiment_id=experiment_id,
            task_id=task_id,
            run_id=run_id,
            detector_version=self.config.detector_version,
            diagnostic_status=status,
            features=features,
            findings=findings,
            primary_failure_category=primary_cat,
            severity=severity,
            evidence_event_ids=unique_evidence_ids,
            explanation=explanation,
            confirmation_status=confirmation,
            analysis_duration_ms=duration_ms,
            created_at=current_utc_timestamp(),
        )

    def on_event(
        self,
        event: Any,
        task_id: str,
        run_id: str,
        history_events: Optional[List[Any]] = None
    ) -> Optional[DiagnosticFinding]:
        """
        Passive observation hook for live execution monitoring.
        Inspects an event snapshot without altering agent decisions or tool behavior.
        """
        if not self.config.enable_live_observation:
            return None

        ev_dict = event if isinstance(event, dict) else (event.model_dump() if hasattr(event, "model_dump") else getattr(event, "__dict__", {}))
        ev_type = ev_dict.get("event_type")

        # Fast live detection of immediate high-severity anomalies
        if ev_type == "tool_execution_failed":
            err_type = ev_dict.get("error_type") or "ToolExecutionError"
            return DiagnosticFinding(
                finding_id=f"live_{uuid.uuid4().hex[:8]}",
                rule_id="LIVE_TOOL_FAILURE",
                failure_category="tool_execution_failure",
                severity="high",
                confirmation_status="confirmed",
                confidence=1.0,
                evidence_event_ids=[f"step_{ev_dict.get('step_index', 0)}"],
                explanation=f"Live observation: Tool execution failure detected in {ev_dict.get('tool_name')}: {ev_dict.get('output_summary')}",
                recommended_next_action="Monitor trajectory for potential persistent tool failure pattern."
            )

        return None
