"""Unit tests for recovery evaluation metrics and comparative calculations."""
import pytest
from backend.evaluation.recovery_metrics import (
    ComparativeMetricsSummary,
    RecoveryEfficiencyMetrics,
    RecoveryMetricsSummary,
    compute_comparative_metrics,
    compute_recovery_metrics,
)
from backend.reliability.recovery_report import (
    RecoveryAttemptReport,
    RecoveryBudgetUsage,
    RecoveryReport,
    RecoveryTerminalStatus,
)

def test_recovery_metrics_zero_denominator():
    """Metrics calculator handles zero attempted tasks gracefully without division by zero."""
    res = compute_recovery_metrics([], agent_mode="traceguard_recovery", total_attempted_override=0)
    assert res.total_attempted == 0
    assert res.end_to_end_success_rate == 0.0
    assert res.recovery_success_rate_eligible == 0.0
    assert res.recovery_attempt_rate == 0.0

def test_recovery_metrics_known_values():
    """Verify exact formula calculation against known inputs."""
    reports = [
        # Task 1: Initially successful, no recovery attempted
        RecoveryReport(
            recovery_id="r1",
            task_id="t1",
            run_id="run1",
            recovery_attempt_id="a1",
            recovery_attempted=False,
            policy_id="policy_none",
            terminal_status=RecoveryTerminalStatus.SUCCESS_WITHOUT_RECOVERY,
            original_status="completed",
            original_verification_status="verified",
            final_verification_status="verified",
            budget_usage=RecoveryBudgetUsage(),
        ),
        # Task 2: Initially failed, recovered successfully
        RecoveryReport(
            recovery_id="r2",
            task_id="t2",
            run_id="run2",
            recovery_attempt_id="a2",
            recovery_attempted=True,
            policy_id="policy_a_transient_tool_failure",
            terminal_status=RecoveryTerminalStatus.RECOVERED_SUCCESSFULLY,
            original_status="failed",
            original_verification_status="failed",
            final_verification_status="verified",
            total_recovery_duration_ms=50.0,
            total_execution_duration_ms=150.0,
            additional_tool_calls=1,
            budget_usage=RecoveryBudgetUsage(attempts=1, steps=1, tool_calls=1),
            attempts=[RecoveryAttemptReport(attempt_id="a2", attempt_index=1, policy_id="p", action_type="act", status="completed")],
        ),
        # Task 3: Initially failed, recovery failed
        RecoveryReport(
            recovery_id="r3",
            task_id="t3",
            run_id="run3",
            recovery_attempt_id="a3",
            recovery_attempted=True,
            policy_id="policy_b_invalid_tool_arguments",
            terminal_status=RecoveryTerminalStatus.FAILED_AFTER_RECOVERY,
            original_status="failed",
            original_verification_status="failed",
            final_verification_status="failed",
            total_recovery_duration_ms=80.0,
            total_execution_duration_ms=180.0,
            additional_tool_calls=1,
            budget_usage=RecoveryBudgetUsage(attempts=1, steps=2, tool_calls=1),
            attempts=[RecoveryAttemptReport(attempt_id="a3", attempt_index=1, policy_id="p", action_type="act", status="failed")],
        ),
        # Task 4: Initially failed, not eligible for recovery
        RecoveryReport(
            recovery_id="r4",
            task_id="t4",
            run_id="run4",
            recovery_attempt_id="a4",
            recovery_attempted=False,
            policy_id="policy_none",
            terminal_status=RecoveryTerminalStatus.UNRESOLVED,
            original_status="failed",
            original_verification_status="failed",
            final_verification_status="failed",
            budget_usage=RecoveryBudgetUsage(),
        ),
    ]

    metrics = compute_recovery_metrics(reports, agent_mode="traceguard_recovery", total_attempted_override=4)

    assert metrics.total_attempted == 4
    assert metrics.initial_successful_tasks == 1
    assert metrics.initial_unsuccessful_tasks == 3
    # Tasks 2 & 3 had eligible policies
    assert metrics.eligible_for_recovery == 2
    # Tasks 2 & 3 had recovery attempted
    assert metrics.recovery_interventions_initiated == 2
    # Task 2 recovered successfully
    assert metrics.recovered_successful_tasks == 1
    # Tasks 1 & 2 are final verified successes
    assert metrics.final_verified_successful_tasks == 2

    # End-to-end success rate: (2 / 4) * 100 = 50.0%
    assert metrics.end_to_end_success_rate == 50.0
    # Recovery success rate (eligible): (1 / 2) * 100 = 50.0%
    assert metrics.recovery_success_rate_eligible == 50.0
    # Recovery success rate (all unsuccessful): (1 / 3) * 100 = 33.33%
    assert metrics.recovery_success_rate_all_unsuccessful == 33.33
    # Recovery attempt rate: (2 / 4) * 100 = 50.0%
    assert metrics.recovery_attempt_rate == 50.0
    # Unnecessary intervention rate: 0.0% (Task 1 was not intervened)
    assert metrics.unnecessary_intervention_rate == 0.0

def test_comparative_metrics_calculation():
    """Verify absolute percentage point and relative percentage difference math."""
    base_summary = RecoveryMetricsSummary(
        agent_mode="baseline",
        total_attempted=100,
        final_verified_successful_tasks=60,
        end_to_end_success_rate=60.0,
        efficiency=RecoveryEfficiencyMetrics(mean_total_latency_ms=100.0),
    )
    fixed_summary = RecoveryMetricsSummary(
        agent_mode="fixed_retry",
        total_attempted=100,
        final_verified_successful_tasks=70,
        end_to_end_success_rate=70.0,
        efficiency=RecoveryEfficiencyMetrics(mean_total_latency_ms=120.0),
    )
    traceguard_summary = RecoveryMetricsSummary(
        agent_mode="traceguard_recovery",
        total_attempted=100,
        final_verified_successful_tasks=85,
        end_to_end_success_rate=85.0,
        efficiency=RecoveryEfficiencyMetrics(mean_total_latency_ms=150.0),
    )

    comp = compute_comparative_metrics(base_summary, fixed_summary, traceguard_summary)

    # Absolute pp deltas
    assert comp.delta_fixed_retry_vs_baseline_pp == 10.0
    assert comp.delta_traceguard_vs_baseline_pp == 25.0
    assert comp.delta_traceguard_vs_fixed_retry_pp == 15.0

    # Relative percentage gains
    assert comp.relative_gain_fixed_retry_pct == 16.67
    assert comp.relative_gain_traceguard_pct == 41.67
    assert comp.relative_gain_traceguard_vs_fixed_pct == 21.43

    # Latency overheads
    assert comp.latency_overhead_fixed_retry_ms == 20.0
    assert comp.latency_overhead_traceguard_ms == 50.0
