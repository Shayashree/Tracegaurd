"""Evaluation metrics calculation for failure-specific recovery and comparative experiments."""
import math
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.reliability.recovery_report import RecoveryReport, RecoveryTerminalStatus

class RecoveryEfficiencyMetrics(BaseModel):
    """Latency, call counts, and resource overhead metrics."""
    mean_total_latency_ms: float = 0.0
    median_total_latency_ms: float = 0.0
    mean_additional_recovery_latency_ms: float = 0.0
    mean_additional_tool_calls: float = 0.0
    mean_additional_model_calls: float = 0.0
    mean_recovery_attempts: float = 0.0
    cost_per_task: Optional[float] = None
    cost_per_successful_task: Optional[float] = None

class RecoveryMetricsSummary(BaseModel):
    """Comprehensive recovery evaluation metrics according to Milestone 4 specification."""
    agent_mode: str
    total_attempted: int = 0
    initial_successful_tasks: int = 0
    initial_unsuccessful_tasks: int = 0
    eligible_for_recovery: int = 0
    recovery_interventions_initiated: int = 0
    recovered_successful_tasks: int = 0
    final_verified_successful_tasks: int = 0
    # Core rates
    end_to_end_success_rate: float = 0.0
    recovery_success_rate_eligible: float = 0.0
    recovery_success_rate_all_unsuccessful: float = 0.0
    recovery_attempt_rate: float = 0.0
    unnecessary_intervention_rate: float = 0.0
    failure_recurrence_rate: float = 0.0
    efficiency: RecoveryEfficiencyMetrics = Field(default_factory=RecoveryEfficiencyMetrics)

class ComparativeMetricsSummary(BaseModel):
    """Comparative evaluation across Baseline, Fixed Retry, and TraceGuard Recovery modes."""
    baseline_success_rate: float = 0.0
    fixed_retry_success_rate: float = 0.0
    traceguard_success_rate: float = 0.0
    # Percentage point differences (absolute change)
    delta_fixed_retry_vs_baseline_pp: float = 0.0
    delta_traceguard_vs_baseline_pp: float = 0.0
    delta_traceguard_vs_fixed_retry_pp: float = 0.0
    # Relative gains in percentage (%)
    relative_gain_fixed_retry_pct: Optional[float] = None
    relative_gain_traceguard_pct: Optional[float] = None
    relative_gain_traceguard_vs_fixed_pct: Optional[float] = None
    # Latency overheads
    mean_latency_baseline_ms: float = 0.0
    mean_latency_fixed_retry_ms: float = 0.0
    mean_latency_traceguard_ms: float = 0.0
    latency_overhead_fixed_retry_ms: float = 0.0
    latency_overhead_traceguard_ms: float = 0.0

def compute_recovery_metrics(
    recovery_reports: List[RecoveryReport],
    agent_mode: str = "traceguard_recovery",
    total_attempted_override: Optional[int] = None,
    experiment_results: Optional[List[Any]] = None,
) -> RecoveryMetricsSummary:
    """Calculate all Section 12 recovery evaluation metrics from persisted recovery reports."""
    if experiment_results and not recovery_reports:
        total_attempted = len(experiment_results)
        success_count = sum(1 for r in experiment_results if getattr(r, "terminal_status", "") == "successful_completion")
        latencies = [getattr(r, "total_duration_ms", 0.0) for r in experiment_results]
        mean_lat = round(sum(latencies) / len(latencies), 2) if latencies else 0.0
        sorted_lats = sorted(latencies)
        med_lat = round(sorted_lats[len(sorted_lats) // 2], 2) if sorted_lats else 0.0
        return RecoveryMetricsSummary(
            agent_mode=agent_mode,
            total_attempted=total_attempted,
            initial_successful_tasks=success_count,
            initial_unsuccessful_tasks=total_attempted - success_count,
            final_verified_successful_tasks=success_count,
            end_to_end_success_rate=round((success_count / total_attempted) * 100.0, 2) if total_attempted > 0 else 0.0,
            efficiency=RecoveryEfficiencyMetrics(
                mean_total_latency_ms=mean_lat,
                median_total_latency_ms=med_lat,
            ),
        )

    total_attempted = total_attempted_override if total_attempted_override is not None else len(recovery_reports)
    if total_attempted == 0:
        return RecoveryMetricsSummary(agent_mode=agent_mode)

    initial_successful = 0
    initial_unsuccessful = 0
    eligible_for_recovery = 0
    interventions_initiated = 0
    recovered_successful = 0
    final_verified_successful = 0
    unnecessary_interventions = 0
    recurrence_count = 0

    total_latencies = []
    recovery_latencies = []
    additional_tool_calls = []
    additional_model_calls = []
    attempts_per_task = []

    for rep in recovery_reports:
        orig_success = (rep.original_status == "completed" and rep.original_verification_status == "verified")
        if orig_success:
            initial_successful += 1
        else:
            initial_unsuccessful += 1
            # Eligible if policy is not none and supported
            if rep.policy_id != "policy_none":
                eligible_for_recovery += 1

        if rep.recovery_attempted:
            interventions_initiated += 1
            if orig_success:
                unnecessary_interventions += 1

        if rep.terminal_status == RecoveryTerminalStatus.RECOVERED_SUCCESSFULLY:
            recovered_successful += 1
            final_verified_successful += 1
        elif rep.terminal_status == RecoveryTerminalStatus.SUCCESS_WITHOUT_RECOVERY or (orig_success and not rep.recovery_attempted):
            final_verified_successful += 1

        # Check failure recurrence: if recovery failed and same category persisted
        if rep.recovery_attempted and rep.terminal_status in (RecoveryTerminalStatus.FAILED_AFTER_RECOVERY, RecoveryTerminalStatus.UNRESOLVED):
            recurrence_count += 1

        total_latencies.append(rep.total_execution_duration_ms)
        recovery_latencies.append(rep.total_recovery_duration_ms)
        additional_tool_calls.append(rep.additional_tool_calls)
        additional_model_calls.append(rep.additional_model_calls)
        attempts_per_task.append(len(rep.attempts) if rep.recovery_attempted else 0)

    # Rates
    end_to_end_success_rate = round((final_verified_successful / total_attempted) * 100.0, 2)
    rec_success_rate_eligible = round((recovered_successful / eligible_for_recovery * 100.0), 2) if eligible_for_recovery > 0 else 0.0
    rec_success_rate_all_unsuccessful = round((recovered_successful / initial_unsuccessful * 100.0), 2) if initial_unsuccessful > 0 else 0.0
    rec_attempt_rate = round((interventions_initiated / total_attempted) * 100.0, 2)
    unnecessary_rate = round((unnecessary_interventions / interventions_initiated * 100.0), 2) if interventions_initiated > 0 else 0.0
    recurrence_rate = round((recurrence_count / interventions_initiated * 100.0), 2) if interventions_initiated > 0 else 0.0

    # Efficiency
    mean_total_lat = round(sum(total_latencies) / len(total_latencies), 2) if total_latencies else 0.0
    sorted_lats = sorted(total_latencies)
    med_total_lat = round(sorted_lats[len(sorted_lats) // 2], 2) if sorted_lats else 0.0
    mean_rec_lat = round(sum(recovery_latencies) / len(recovery_latencies), 2) if recovery_latencies else 0.0
    mean_tool_calls = round(sum(additional_tool_calls) / len(additional_tool_calls), 2) if additional_tool_calls else 0.0
    mean_model_calls = round(sum(additional_model_calls) / len(additional_model_calls), 2) if additional_model_calls else 0.0
    mean_attempts = round(sum(attempts_per_task) / len(attempts_per_task), 2) if attempts_per_task else 0.0

    efficiency = RecoveryEfficiencyMetrics(
        mean_total_latency_ms=mean_total_lat,
        median_total_latency_ms=med_total_lat,
        mean_additional_recovery_latency_ms=mean_rec_lat,
        mean_additional_tool_calls=mean_tool_calls,
        mean_additional_model_calls=mean_model_calls,
        mean_recovery_attempts=mean_attempts,
    )

    return RecoveryMetricsSummary(
        agent_mode=agent_mode,
        total_attempted=total_attempted,
        initial_successful_tasks=initial_successful,
        initial_unsuccessful_tasks=initial_unsuccessful,
        eligible_for_recovery=eligible_for_recovery,
        recovery_interventions_initiated=interventions_initiated,
        recovered_successful_tasks=recovered_successful,
        final_verified_successful_tasks=final_verified_successful,
        end_to_end_success_rate=end_to_end_success_rate,
        recovery_success_rate_eligible=rec_success_rate_eligible,
        recovery_success_rate_all_unsuccessful=rec_success_rate_all_unsuccessful,
        recovery_attempt_rate=rec_attempt_rate,
        unnecessary_intervention_rate=unnecessary_rate,
        failure_recurrence_rate=recurrence_rate,
        efficiency=efficiency,
    )

def compute_comparative_metrics(
    baseline_metrics: RecoveryMetricsSummary,
    fixed_retry_metrics: RecoveryMetricsSummary,
    traceguard_metrics: RecoveryMetricsSummary,
) -> ComparativeMetricsSummary:
    """Compare baseline, fixed retry, and traceguard recovery on paired tasks."""
    b_sr = baseline_metrics.end_to_end_success_rate
    f_sr = fixed_retry_metrics.end_to_end_success_rate
    t_sr = traceguard_metrics.end_to_end_success_rate

    delta_fb = round(f_sr - b_sr, 2)
    delta_tb = round(t_sr - b_sr, 2)
    delta_tf = round(t_sr - f_sr, 2)

    rel_fb = round(((f_sr - b_sr) / b_sr) * 100.0, 2) if b_sr > 0 else None
    rel_tb = round(((t_sr - b_sr) / b_sr) * 100.0, 2) if b_sr > 0 else None
    rel_tf = round(((t_sr - f_sr) / f_sr) * 100.0, 2) if f_sr > 0 else None

    b_lat = baseline_metrics.efficiency.mean_total_latency_ms
    f_lat = fixed_retry_metrics.efficiency.mean_total_latency_ms
    t_lat = traceguard_metrics.efficiency.mean_total_latency_ms

    return ComparativeMetricsSummary(
        baseline_success_rate=b_sr,
        fixed_retry_success_rate=f_sr,
        traceguard_success_rate=t_sr,
        delta_fixed_retry_vs_baseline_pp=delta_fb,
        delta_traceguard_vs_baseline_pp=delta_tb,
        delta_traceguard_vs_fixed_retry_pp=delta_tf,
        relative_gain_fixed_retry_pct=rel_fb,
        relative_gain_traceguard_pct=rel_tb,
        relative_gain_traceguard_vs_fixed_pct=rel_tf,
        mean_latency_baseline_ms=b_lat,
        mean_latency_fixed_retry_ms=f_lat,
        mean_latency_traceguard_ms=t_lat,
        latency_overhead_fixed_retry_ms=round(f_lat - b_lat, 2),
        latency_overhead_traceguard_ms=round(t_lat - b_lat, 2),
    )
