"""Evaluation metrics for the Trajectory Failure Detector."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class CategoryConfusionMatrix(BaseModel):
    """Confusion counts for a specific failure category."""
    category: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    false_positive_rate: Optional[float] = None

class DetectorEvaluationMetrics(BaseModel):
    """Comprehensive performance metrics for the trajectory failure detector."""
    detector_version: str
    total_runs_evaluated: int
    total_failures_ground_truth: int
    total_healthy_ground_truth: int
    detected_failures_count: int
    false_alarm_count: int
    detection_coverage: float = 0.0
    macro_precision: Optional[float] = None
    macro_recall: Optional[float] = None
    macro_f1: Optional[float] = None
    micro_precision: Optional[float] = None
    micro_recall: Optional[float] = None
    micro_f1: Optional[float] = None
    mean_detection_latency_ms: float = 0.0
    median_detection_latency_ms: float = 0.0
    p95_detection_latency_ms: Optional[float] = None
    category_metrics: Dict[str, CategoryConfusionMatrix] = Field(default_factory=dict)
    held_out_detection_rate: Optional[float] = None

class DetectorMetricsCalculator:
    """Calculates precision, recall, F1, and confusion metrics for diagnostic reports."""

    ALL_CATEGORIES = [
        "repeated_tool_calls",
        "invalid_tool_arguments",
        "tool_execution_failure",
        "lack_of_progress",
        "missing_evidence",
        "incorrect_final_answer",
        "step_limit_exhaustion",
        "invalid_model_output",
        "unverified_completion",
    ]

    @classmethod
    def calculate_metrics(
        cls,
        evaluations: List[Dict[str, Any]],
        detector_version: str = "v1.0.0"
    ) -> DetectorEvaluationMetrics:
        """
        Calculates metrics from a collection of evaluation entries.
        Each entry contains:
          - 'expected_failure_category': Optional[str] (None if healthy)
          - 'detected_categories': List[str]
          - 'diagnostic_status': str
          - 'latency_ms': float
          - 'is_held_out': bool
        """
        if not evaluations:
            return DetectorEvaluationMetrics(
                detector_version=detector_version,
                total_runs_evaluated=0,
                total_failures_ground_truth=0,
                total_healthy_ground_truth=0,
                detected_failures_count=0,
                false_alarm_count=0,
            )

        total_runs = len(evaluations)
        total_failures_gt = 0
        total_healthy_gt = 0
        detected_failures_count = 0
        false_alarms = 0
        held_out_total = 0
        held_out_detected = 0
        latencies: List[float] = []

        # Initialize confusion matrices for all categories
        conf_matrices: Dict[str, Dict[str, int]] = {
            cat: {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
            for cat in cls.ALL_CATEGORIES
        }

        for item in evaluations:
            gt_cat = item.get("expected_failure_category")
            detected_cats = set(item.get("detected_categories", []))
            lat = item.get("latency_ms", 0.0)
            latencies.append(lat)
            is_held_out = item.get("is_held_out", False)

            if gt_cat:
                total_failures_gt += 1
                if is_held_out:
                    held_out_total += 1
                    if len(detected_cats) > 0:
                        held_out_detected += 1
                if len(detected_cats) > 0:
                    detected_failures_count += 1
            else:
                total_healthy_gt += 1
                # If healthy but failure was detected
                if any(c in detected_cats for c in cls.ALL_CATEGORIES if c != "unverified_completion"):
                    false_alarms += 1

            # Update per-category confusion counts
            for cat in cls.ALL_CATEGORIES:
                has_gt = (gt_cat == cat)
                has_pred = (cat in detected_cats)

                if has_gt and has_pred:
                    conf_matrices[cat]["tp"] += 1
                elif not has_gt and has_pred:
                    conf_matrices[cat]["fp"] += 1
                elif has_gt and not has_pred:
                    conf_matrices[cat]["fn"] += 1
                else:
                    conf_matrices[cat]["tn"] += 1

        # Calculate per-category precision, recall, F1
        category_metrics_result: Dict[str, CategoryConfusionMatrix] = {}
        precisions: List[float] = []
        recalls: List[float] = []
        f1s: List[float] = []

        total_tp = sum(c["tp"] for c in conf_matrices.values())
        total_fp = sum(c["fp"] for c in conf_matrices.values())
        total_fn = sum(c["fn"] for c in conf_matrices.values())

        for cat, cm in conf_matrices.items():
            tp, fp, fn, tn = cm["tp"], cm["fp"], cm["fn"], cm["tn"]

            # Precision
            p = round(tp / (tp + fp), 4) if (tp + fp) > 0 else None
            # Recall
            r = round(tp / (tp + fn), 4) if (tp + fn) > 0 else None
            # F1
            if p is not None and r is not None and (p + r) > 0:
                f1 = round(2 * (p * r) / (p + r), 4)
            else:
                f1 = None

            # False Positive Rate
            fpr = round(fp / (fp + tn), 4) if (fp + tn) > 0 else None

            if p is not None:
                precisions.append(p)
            if r is not None:
                recalls.append(r)
            if f1 is not None:
                f1s.append(f1)

            category_metrics_result[cat] = CategoryConfusionMatrix(
                category=cat,
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                true_negatives=tn,
                precision=p,
                recall=r,
                f1_score=f1,
                false_positive_rate=fpr,
            )

        # Macro averages
        macro_p = round(sum(precisions) / len(precisions), 4) if precisions else None
        macro_r = round(sum(recalls) / len(recalls), 4) if recalls else None
        macro_f1 = round(sum(f1s) / len(f1s), 4) if f1s else None

        # Micro averages
        micro_p = round(total_tp / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else None
        micro_r = round(total_tp / (total_tp + total_fn), 4) if (total_tp + total_fn) > 0 else None
        if micro_p is not None and micro_r is not None and (micro_p + micro_r) > 0:
            micro_f1 = round(2 * (micro_p * micro_r) / (micro_p + micro_r), 4)
        else:
            micro_f1 = None

        # Coverage
        coverage = round((detected_failures_count / total_failures_gt) * 100, 2) if total_failures_gt > 0 else 100.0

        # Latency statistics
        latencies.sort()
        mean_lat = round(sum(latencies) / len(latencies), 3) if latencies else 0.0
        median_lat = round(latencies[len(latencies) // 2], 3) if latencies else 0.0
        p95_idx = int(len(latencies) * 0.95)
        p95_lat = round(latencies[min(p95_idx, len(latencies) - 1)], 3) if latencies else None

        held_out_rate = round((held_out_detected / held_out_total) * 100, 2) if held_out_total > 0 else None

        return DetectorEvaluationMetrics(
            detector_version=detector_version,
            total_runs_evaluated=total_runs,
            total_failures_ground_truth=total_failures_gt,
            total_healthy_ground_truth=total_healthy_gt,
            detected_failures_count=detected_failures_count,
            false_alarm_count=false_alarms,
            detection_coverage=coverage,
            macro_precision=macro_p,
            macro_recall=macro_r,
            macro_f1=macro_f1,
            micro_precision=micro_p,
            micro_recall=micro_r,
            micro_f1=micro_f1,
            mean_detection_latency_ms=mean_lat,
            median_detection_latency_ms=median_lat,
            p95_detection_latency_ms=p95_lat,
            category_metrics=category_metrics_result,
            held_out_detection_rate=held_out_rate,
        )
