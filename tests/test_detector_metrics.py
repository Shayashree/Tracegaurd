"""Unit tests for detector performance metrics calculations."""
import pytest
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.detector_metrics import DetectorMetricsCalculator

def test_metrics_calculation_known_values():
    evaluations = [
        # 2 TP for repeated_tool_calls
        {"expected_failure_category": "repeated_tool_calls", "detected_categories": ["repeated_tool_calls"], "latency_ms": 2.0, "is_held_out": False},
        {"expected_failure_category": "repeated_tool_calls", "detected_categories": ["repeated_tool_calls"], "latency_ms": 3.0, "is_held_out": False},
        # 1 FN for repeated_tool_calls
        {"expected_failure_category": "repeated_tool_calls", "detected_categories": [], "latency_ms": 1.5, "is_held_out": False},
        # 1 FP for repeated_tool_calls on a healthy run
        {"expected_failure_category": None, "detected_categories": ["repeated_tool_calls"], "latency_ms": 2.5, "is_held_out": False},
        # 1 TN on healthy run with no detections
        {"expected_failure_category": None, "detected_categories": [], "latency_ms": 1.0, "is_held_out": True},
    ]

    metrics = DetectorMetricsCalculator.calculate_metrics(evaluations)
    assert metrics.total_runs_evaluated == 5
    assert metrics.total_failures_ground_truth == 3
    assert metrics.total_healthy_ground_truth == 2
    assert metrics.detected_failures_count == 2
    assert metrics.false_alarm_count == 1

    # Check repeated_tool_calls category
    f1_m = metrics.category_metrics["repeated_tool_calls"]
    assert f1_m.true_positives == 2
    assert f1_m.false_negatives == 1
    assert f1_m.false_positives == 1
    # Precision: 2 / (2 + 1) = 0.6667
    assert f1_m.precision == 0.6667
    # Recall: 2 / (2 + 1) = 0.6667
    assert f1_m.recall == 0.6667
    # F1: 0.6667
    assert f1_m.f1_score == 0.6667

def test_metrics_zero_denominators():
    # Empty evaluation list
    metrics = DetectorMetricsCalculator.calculate_metrics([])
    assert metrics.total_runs_evaluated == 0
    assert metrics.macro_precision is None
    assert metrics.macro_recall is None
    assert metrics.macro_f1 is None
    assert metrics.micro_precision is None

    # Healthy runs with zero failures
    evals_healthy = [
        {"expected_failure_category": None, "detected_categories": [], "latency_ms": 1.0, "is_held_out": False},
        {"expected_failure_category": None, "detected_categories": [], "latency_ms": 1.2, "is_held_out": False},
    ]
    metrics_h = DetectorMetricsCalculator.calculate_metrics(evals_healthy)
    assert metrics_h.total_runs_evaluated == 2
    assert metrics_h.total_failures_ground_truth == 0
    assert metrics_h.false_alarm_count == 0
    # No division by zero errors
    for cm in metrics_h.category_metrics.values():
        assert cm.precision is None
        assert cm.recall is None
        assert cm.f1_score is None

def test_benchmark_split_filtering():
    loader = BenchmarkDatasetLoader()
    train_tasks = loader.load_tasks(version="v1.0", split="train")
    val_tasks = loader.load_tasks(version="v1.0", split="val")
    test_tasks = loader.load_tasks(version="v1.0", split="test")

    total = len(train_tasks) + len(val_tasks) + len(test_tasks)
    assert total == 44
    assert len(train_tasks) > 0
    assert len(val_tasks) > 0
    assert len(test_tasks) > 0

    # Ensure no overlap between splits
    train_ids = {t.task_id for t in train_tasks}
    val_ids = {t.task_id for t in val_tasks}
    test_ids = {t.task_id for t in test_tasks}
    assert train_ids.isdisjoint(val_ids)
    assert train_ids.isdisjoint(test_ids)
    assert val_ids.isdisjoint(test_ids)
