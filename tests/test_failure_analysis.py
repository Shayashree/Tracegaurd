"""Unit tests for failure-specific analysis and category breakdown."""
from backend.evaluation.failure_analysis import compute_failure_analysis
from backend.evaluation.schemas import BenchmarkTask, TaskExecutionResult
from backend.reliability.diagnostic_report import (
    ConfirmationStatus,
    DiagnosticFinding,
    DiagnosticReport,
    DiagnosticStatus,
    FailureCategory,
    SeverityLevel,
    TrajectoryFeatures,
)
from backend.reliability.recovery_report import (
    RecoveryBudgetUsage,
    RecoveryReport,
    RecoveryTerminalStatus,
)

def test_compute_failure_analysis():
    """Verify category grouping, detection TP/FP/FN counts, and recovery metrics."""
    tasks = [
        BenchmarkTask(
            task_id="ARITH-001",
            category="arithmetic",
            task_description="Calculate 2 + 2",
        ),
        BenchmarkTask(
            task_id="FAIL-001",
            category="failure_scenario",
            task_description="Transient failure test",
        ),
    ]

    exec_results = [
        TaskExecutionResult(
            experiment_id="exp_test",
            task_id="ARITH-001",
            run_id="run_1",
            benchmark_version="v1.0",
            agent_mode="traceguard_recovery",
            terminal_status="successful_completion",
            verification_status="verified",
            verification_message="Matched",
            step_count=2,
            tool_call_count=1,
            tool_error_count=0,
            total_duration_ms=5.0,
            started_at="2026-10-20T00:00:00Z",
            completed_at="2026-10-20T00:00:01Z",
        ),
        TaskExecutionResult(
            experiment_id="exp_test",
            task_id="FAIL-001",
            run_id="run_2",
            benchmark_version="v1.0",
            agent_mode="traceguard_recovery",
            terminal_status="tool_error",
            verification_status="failed",
            verification_message="Tool error",
            step_count=3,
            tool_call_count=2,
            tool_error_count=1,
            total_duration_ms=10.0,
            started_at="2026-10-20T00:00:00Z",
            completed_at="2026-10-20T00:00:01Z",
        ),
    ]

    recovery_reports = [
        RecoveryReport(
            recovery_id="rec_1",
            task_id="FAIL-001",
            run_id="run_2",
            recovery_attempt_id="att_1",
            policy_id="policy_a_transient_tool_failure",
            initial_failure_category="tool_execution_failure",
            recovery_attempted=True,
            terminal_status=RecoveryTerminalStatus.RECOVERED_SUCCESSFULLY,
            original_status="failed",
            original_verification_status="failed",
            final_verification_status="verified",
            final_answer="Recovered result 42",
            total_recovery_duration_ms=8.5,
            additional_tool_calls=1,
            additional_model_calls=0,
            budget_usage=RecoveryBudgetUsage(),
            created_at="2026-10-20T00:00:01Z",
        )
    ]

    diag_reports = [
        DiagnosticReport(
            diagnostic_id="diag_1",
            task_id="FAIL-001",
            run_id="run_2",
            detector_version="v1.0",
            diagnostic_status=DiagnosticStatus.FAILURE_DETECTED,
            primary_failure_category=FailureCategory.TOOL_EXECUTION_FAILURE,
            severity=SeverityLevel.HIGH,
            confirmation_status=ConfirmationStatus.CONFIRMED,
            findings=[
                DiagnosticFinding(
                    finding_id="fnd_1",
                    rule_id="R2_PERSISTENT_TOOL_FAILURE",
                    failure_category=FailureCategory.TOOL_EXECUTION_FAILURE,
                    severity=SeverityLevel.HIGH,
                    confirmation_status=ConfirmationStatus.CONFIRMED,
                    explanation="Persistent failure on tool",
                    recommended_next_action="Retry operation",
                )
            ],
            features=TrajectoryFeatures(),
        )
    ]

    analysis = compute_failure_analysis(
        tasks=tasks,
        execution_results=exec_results,
        recovery_reports=recovery_reports,
        diagnostic_reports=diag_reports,
        experiment_id="exp_test"
    )

    assert analysis.total_categories_analyzed == 2
    assert "arithmetic" in analysis.categories
    assert "failure_scenario" in analysis.categories

    arith = analysis.categories["arithmetic"]
    assert arith.total_tasks == 1
    assert arith.actual_failures == 0
    assert arith.assessment == "inconclusive"  # sample size 1

    fail_cat = analysis.categories["failure_scenario"]
    assert fail_cat.total_tasks == 1
    assert fail_cat.actual_failures == 1
    assert fail_cat.detector_true_positives == 1
    assert fail_cat.detector_precision == 100.0
    assert fail_cat.detector_recall == 100.0
    assert fail_cat.verified_recovery_successes == 1
    assert fail_cat.recovery_success_rate == 100.0
