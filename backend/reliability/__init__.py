"""Reliability and failure detection package for TraceGuard."""
from backend.reliability.detector_config import DetectorConfig, default_detector_config
from backend.reliability.diagnostic_report import (
    ConfirmationStatus,
    DiagnosticFinding,
    DiagnosticReport,
    DiagnosticStatus,
    FailureCategory,
    SeverityLevel,
    TrajectoryFeatures,
)
from backend.reliability.failure_classifier import FailureClassifier
from backend.reliability.failure_detector import TrajectoryFailureDetector
from backend.reliability.failure_rules import DEFAULT_FAILURE_RULES, BaseFailureRule
from backend.reliability.feature_extractor import TrajectoryFeatureExtractor, normalize_tool_arguments

__all__ = [
    "DetectorConfig",
    "default_detector_config",
    "FailureCategory",
    "DiagnosticStatus",
    "ConfirmationStatus",
    "SeverityLevel",
    "TrajectoryFeatures",
    "DiagnosticFinding",
    "DiagnosticReport",
    "TrajectoryFeatureExtractor",
    "normalize_tool_arguments",
    "BaseFailureRule",
    "DEFAULT_FAILURE_RULES",
    "FailureClassifier",
    "TrajectoryFailureDetector",
]
