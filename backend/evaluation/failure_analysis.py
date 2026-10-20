"""Failure-specific performance evaluation and category breakdown for TraceGuard Milestone 5."""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
from backend.reliability.recovery_report import RecoveryReport, RecoveryTerminalStatus

CategoryAssessment = Literal["beneficial", "neutral", "ineffective", "inconclusive"]

class CategoryFailureSummary(BaseModel):
    """Evaluation summary for a specific task category or failure mode."""
    category_name: str
    total_tasks: int = 0
    actual_failures: int = 0
    initial_success_count: int = 0
    # Detection metrics
    detector_detected_count: int = 0
    detector_true_positives: int = 0
    detector_false_positives: int = 0
    detector_false_negatives: int = 0
    detector_precision: float = 0.0
    detector_recall: float = 0.0
    detector_f1: float = 0.0
    # Recovery metrics
    eligible_for_recovery: int = 0
    recovery_attempts: int = 0
    verified_recovery_successes: int = 0
    unresolved_outcomes: int = 0
    recovery_success_rate: float = 0.0
    recovery_attempt_rate: float = 0.0
    budget_exhausted_count: int = 0
    budget_exhaustion_rate: float = 0.0
    # Efficiency overhead
    mean_additional_latency_ms: float = 0.0
    mean_additional_tool_calls: float = 0.0
    mean_additional_model_calls: float = 0.0
    # Assessment
    assessment: CategoryAssessment = "inconclusive"
    assessment_reason: str = ""

class FailureAnalysisReport(BaseModel):
    """Complete cross-category failure analysis breakdown."""
    experiment_id: str
    total_categories_analyzed: int = 0
    categories: Dict[str, CategoryFailureSummary] = Field(default_factory=dict)
    beneficial_categories: List[str] = Field(default_factory=list)
    ineffective_categories: List[str] = Field(default_factory=list)
    inconclusive_categories: List[str] = Field(default_factory=list)
    summary_notes: str = ""

def compute_failure_analysis(
    tasks: List[Any],
    execution_results: List[Any],
    recovery_reports: Optional[List[RecoveryReport]] = None,
    diagnostic_reports: Optional[List[Any]] = None,
    experiment_id: str = "exp_analysis"
) -> FailureAnalysisReport:
    """
    Computes fine-grained failure detection and recovery metrics grouped by task category
    and controlled failure scenario.
    """
    recovery_by_task = {}
    if recovery_reports:
        for r in recovery_reports:
            recovery_by_task[r.task_id] = r

    diag_by_task = {}
    if diagnostic_reports:
        for d in diagnostic_reports:
            diag_by_task[getattr(d, "task_id", "")] = d

    task_map = {t.task_id: t for t in tasks}

    # Group execution results by category or specific failure scenario type
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for res in execution_results:
        t_id = getattr(res, "task_id", "")
        task = task_map.get(t_id)
        cat = "unknown"
        if task:
            if getattr(task, "failure_scenario", None) and getattr(task.failure_scenario, "failure_type", None):
                cat = f"failure_scenario:{task.failure_scenario.failure_type}"
            else:
                cat = str(getattr(task, "category", "general"))

        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append({
            "result": res,
            "task": task,
            "recovery": recovery_by_task.get(t_id),
            "diag": diag_by_task.get(t_id),
        })

    category_summaries: Dict[str, CategoryFailureSummary] = {}
    beneficial = []
    ineffective = []
    inconclusive = []

    for cat_name, items in sorted(grouped.items(), key=lambda x: x[0]):
        n_tasks = len(items)
        initial_successes = sum(
            1 for item in items
            if getattr(item["result"], "terminal_status", "") == "successful_completion"
            or (item["recovery"] and item["recovery"].original_status == "completed" and item["recovery"].original_verification_status == "verified")
        )
        actual_failures = n_tasks - initial_successes

        # Detection evaluation
        tp = 0
        fp = 0
        fn = 0
        detected_count = 0
        for item in items:
            diag = item["diag"]
            is_failure = (getattr(item["result"], "terminal_status", "") != "successful_completion")
            has_detection = False
            if diag:
                status_val = getattr(diag, "diagnostic_status", None)
                status_str = status_val.value if hasattr(status_val, "value") else str(status_val or "")
                if status_str == "failure_detected" or len(getattr(diag, "findings", [])) > 0:
                    has_detection = True

            if has_detection:
                detected_count += 1
                if is_failure:
                    tp += 1
                else:
                    fp += 1
            else:
                if is_failure:
                    fn += 1

        det_prec = round((tp / (tp + fp)) * 100.0, 2) if (tp + fp) > 0 else (100.0 if actual_failures == 0 else 0.0)
        det_rec = round((tp / (tp + fn)) * 100.0, 2) if (tp + fn) > 0 else (100.0 if actual_failures == 0 else 0.0)
        det_f1 = round(2.0 * (det_prec * det_rec) / (det_prec + det_rec), 2) if (det_prec + det_rec) > 0 else 0.0

        # Recovery evaluation
        eligible = 0
        rec_attempts = 0
        rec_successes = 0
        unresolved = 0
        budget_exhausted = 0
        add_lats = []
        add_tools = []
        add_models = []

        for item in items:
            rec_rep = item["recovery"]
            if rec_rep:
                if rec_rep.initial_failure_category and rec_rep.initial_failure_category != "None":
                    eligible += 1
                if rec_rep.recovery_attempted:
                    rec_attempts += 1
                    term = rec_rep.terminal_status.value if hasattr(rec_rep.terminal_status, "value") else str(rec_rep.terminal_status)
                    if term == "recovered_successfully":
                        rec_successes += 1
                    elif term in ("unresolved", "failed_after_recovery"):
                        unresolved += 1
                    elif term == "budget_exhausted":
                        budget_exhausted += 1

                    add_lats.append(rec_rep.total_recovery_duration_ms)
                    add_tools.append(rec_rep.additional_tool_calls)
                    add_models.append(rec_rep.additional_model_calls)

        rec_sr = round((rec_successes / eligible) * 100.0, 2) if eligible > 0 else 0.0
        rec_att_rate = round((rec_attempts / eligible) * 100.0, 2) if eligible > 0 else 0.0
        budget_rate = round((budget_exhausted / rec_attempts) * 100.0, 2) if rec_attempts > 0 else 0.0

        mean_lat = round(sum(add_lats) / len(add_lats), 2) if add_lats else 0.0
        mean_tools = round(sum(add_tools) / len(add_tools), 2) if add_tools else 0.0
        mean_models = round(sum(add_models) / len(add_models), 2) if add_models else 0.0

        # Assessment determination
        if eligible == 0 or n_tasks < 2:
            assessment: CategoryAssessment = "inconclusive"
            reason = "Sample size too small or no recovery-eligible failures observed."
            inconclusive.append(cat_name)
        elif rec_successes > 0 and rec_sr >= 50.0:
            assessment = "beneficial"
            reason = f"High recovery success rate ({rec_sr}%) across {eligible} eligible task(s)."
            beneficial.append(cat_name)
        elif rec_attempts > 0 and rec_successes == 0:
            assessment = "ineffective"
            reason = f"Recovery intervened on {rec_attempts} task(s) but produced 0 verified recoveries."
            ineffective.append(cat_name)
        else:
            assessment = "neutral"
            reason = f"Neutral recovery impact ({rec_sr}% success rate) across {eligible} eligible task(s)."
            inconclusive.append(cat_name)

        summary = CategoryFailureSummary(
            category_name=cat_name,
            total_tasks=n_tasks,
            actual_failures=actual_failures,
            initial_success_count=initial_successes,
            detector_detected_count=detected_count,
            detector_true_positives=tp,
            detector_false_positives=fp,
            detector_false_negatives=fn,
            detector_precision=det_prec,
            detector_recall=det_rec,
            detector_f1=det_f1,
            eligible_for_recovery=eligible,
            recovery_attempts=rec_attempts,
            verified_recovery_successes=rec_successes,
            unresolved_outcomes=unresolved,
            recovery_success_rate=rec_sr,
            recovery_attempt_rate=rec_att_rate,
            budget_exhausted_count=budget_exhausted,
            budget_exhaustion_rate=budget_rate,
            mean_additional_latency_ms=mean_lat,
            mean_additional_tool_calls=mean_tools,
            mean_additional_model_calls=mean_models,
            assessment=assessment,
            assessment_reason=reason
        )
        category_summaries[cat_name] = summary

    notes = (
        f"Analyzed {len(category_summaries)} categories across {len(execution_results)} executions. "
        f"Beneficial: {len(beneficial)}, Ineffective: {len(ineffective)}, Inconclusive/Neutral: {len(inconclusive)}."
    )

    return FailureAnalysisReport(
        experiment_id=experiment_id,
        total_categories_analyzed=len(category_summaries),
        categories=category_summaries,
        beneficial_categories=beneficial,
        ineffective_categories=ineffective,
        inconclusive_categories=inconclusive,
        summary_notes=notes
    )
