"""Failure classifier and diagnostic report synthesizer."""
from typing import List, Optional, Tuple
from backend.reliability.diagnostic_report import (
    ConfirmationStatus,
    DiagnosticFinding,
    DiagnosticStatus,
    FailureCategory,
    SeverityLevel,
    TrajectoryFeatures,
)

SEVERITY_ORDER = {
    SeverityLevel.CRITICAL: 5,
    SeverityLevel.HIGH: 4,
    SeverityLevel.MEDIUM: 3,
    SeverityLevel.LOW: 2,
    SeverityLevel.INFO: 1,
}

CONFIRMATION_ORDER = {
    ConfirmationStatus.CONFIRMED: 3,
    ConfirmationStatus.SUSPECTED: 2,
    ConfirmationStatus.UNVERIFIED: 1,
}

class FailureClassifier:
    """Aggregates rule findings to determine overall status and primary failure category."""

    @classmethod
    def classify(
        cls,
        features: TrajectoryFeatures,
        findings: List[DiagnosticFinding]
    ) -> Tuple[DiagnosticStatus, Optional[FailureCategory], SeverityLevel, ConfirmationStatus, str]:
        """
        Synthesizes findings into diagnostic status, primary failure category,
        severity, confirmation status, and summary explanation.
        """
        if features.total_steps == 0 or features.terminal_status == "no_events":
            return (
                DiagnosticStatus.INSUFFICIENT_DATA,
                None,
                SeverityLevel.INFO,
                ConfirmationStatus.UNVERIFIED,
                "Insufficient trace events to perform diagnostic evaluation."
            )

        if not findings:
            if features.terminal_status in ("completed", "successful_completion") and features.verification_status == "verified":
                return (
                    DiagnosticStatus.HEALTHY,
                    None,
                    SeverityLevel.INFO,
                    ConfirmationStatus.CONFIRMED,
                    "Trajectory executed successfully with deterministic ground-truth verification."
                )
            elif features.terminal_status in ("completed", "successful_completion"):
                return (
                    DiagnosticStatus.HEALTHY,
                    None,
                    SeverityLevel.INFO,
                    ConfirmationStatus.UNVERIFIED,
                    "Trajectory completed without observable errors."
                )
            else:
                return (
                    DiagnosticStatus.WARNING,
                    None,
                    SeverityLevel.LOW,
                    ConfirmationStatus.SUSPECTED,
                    f"Trajectory ended with status '{features.terminal_status}' but no specific failure rule triggered."
                )

        # Sort findings by:
        # 1. Severity weight descending
        # 2. Confirmation weight descending
        sorted_findings = sorted(
            findings,
            key=lambda f: (
                SEVERITY_ORDER.get(f.severity, 0),
                CONFIRMATION_ORDER.get(f.confirmation_status, 0)
            ),
            reverse=True
        )

        top_finding = sorted_findings[0]
        primary_category = top_finding.failure_category
        max_severity = top_finding.severity
        top_confirmation = top_finding.confirmation_status

        # Determine diagnostic status
        if any(f.severity in (SeverityLevel.CRITICAL, SeverityLevel.HIGH) for f in findings):
            diag_status = DiagnosticStatus.FAILURE_DETECTED
        elif any(f.confirmation_status == ConfirmationStatus.CONFIRMED for f in findings):
            diag_status = DiagnosticStatus.FAILURE_DETECTED
        elif any(f.severity == SeverityLevel.MEDIUM for f in findings):
            diag_status = DiagnosticStatus.WARNING
        elif all(f.failure_category == FailureCategory.UNVERIFIED_COMPLETION for f in findings):
            diag_status = DiagnosticStatus.HEALTHY
        else:
            diag_status = DiagnosticStatus.WARNING

        summary_explanation = f"Primary diagnostic finding: {top_finding.explanation}"
        if len(findings) > 1:
            summary_explanation += f" ({len(findings)} total finding(s) detected)"

        return (
            diag_status,
            primary_category,
            max_severity,
            top_confirmation,
            summary_explanation
        )
