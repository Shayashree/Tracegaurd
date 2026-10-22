"""Artifact generation utility for creating and persisting research reports and manifests."""
import logging
from typing import Any, Dict, List, Optional, Tuple

from backend.evaluation.ablation_analysis import compute_ablation_analysis
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.experiment_config import ExperimentConfig
from backend.evaluation.failure_analysis import compute_failure_analysis
from backend.evaluation.manifest import create_reproducibility_manifest
from backend.evaluation.recovery_metrics import (
    ComparativeMetricsSummary,
    RecoveryMetricsSummary,
    compute_recovery_metrics,
)
from backend.evaluation.report_generator import ResearchReportGenerator
from backend.evaluation.statistical_tests import (
    PairedComparisonMetric,
    perform_mcnemar_test,
    perform_paired_latency_comparison,
)
from backend.tracing.storage import TraceStorage

logger = logging.getLogger(__name__)


def generate_and_save_experiment_artifacts(
    storage: TraceStorage,
    experiment_id: str,
    force: bool = False,
) -> Optional[Tuple[str, Dict[str, Any]]]:
    """
    Generate or retrieve research report markdown and reproducibility manifest for an experiment.
    If force is False and artifacts already exist, returns existing (report_markdown, manifest_dict).
    Otherwise, generates artifacts from persisted task executions, metrics, and failure diagnostics,
    persists them to experiment_artifacts, and returns (report_markdown, manifest_dict).
    """
    if not force:
        existing_report = storage.get_experiment_report(experiment_id)
        existing_manifest = storage.get_experiment_manifest(experiment_id)
        if existing_report and existing_manifest:
            return existing_report, existing_manifest

    exp = storage.get_experiment(experiment_id)
    if not exp:
        logger.warning(f"Cannot generate artifacts: Experiment '{experiment_id}' not found.")
        return None

    results = storage.get_experiment_results(experiment_id, limit=5000, offset=0)
    raw_cfg = exp.config or {}

    # Extract distinct agent modes from results, falling back to exp.agent_mode
    modes_in_results = list(dict.fromkeys(r.agent_mode for r in results if r.agent_mode))
    if not modes_in_results:
        modes_in_results = [exp.agent_mode] if exp.agent_mode else ["baseline"]

    # Reconstruct configuration
    cfg = ExperimentConfig(
        experiment_id=exp.experiment_id,
        experiment_version=raw_cfg.get("experiment_version", "v1.0"),
        benchmark_version=exp.benchmark_version or raw_cfg.get("benchmark_version", "v1.0"),
        dataset_split=raw_cfg.get("dataset_split", "all"),
        experiment_type=raw_cfg.get("experiment_type", "standard"),
        agent_modes=modes_in_results,
        task_ids=raw_cfg.get("task_ids"),
        category=raw_cfg.get("category"),
        repetitions=raw_cfg.get("repetitions", 1),
        model_configuration=raw_cfg.get("model_configuration", {"model_adapter": "mock", "temperature": 0.0}),
        tool_configuration=raw_cfg.get("tool_configuration", {}),
        failure_injection_configuration=raw_cfg.get("failure_injection_configuration", {}),
        step_limit=int(raw_cfg.get("max_steps") or raw_cfg.get("step_limit") or 8),
        task_timeout=float(raw_cfg.get("timeout_seconds") or raw_cfg.get("task_timeout") or 30.0),
    )

    # 1. Reproducibility Manifest
    manifest = create_reproducibility_manifest(
        config=cfg,
        artifact_references={
            "database_path": str(storage.db_path),
            "total_tasks_evaluated": str(len(results)),
            "experiment_id": exp.experiment_id,
        }
    )

    # 2. Mode Metrics and Variant Data
    mode_metrics: Dict[str, RecoveryMetricsSummary] = {}
    variant_data: Dict[str, Dict[str, Any]] = {}
    all_rec_reports = storage.get_recovery_reports_for_experiment(exp.experiment_id)

    for mode in modes_in_results:
        mode_results = [r for r in results if r.agent_mode == mode]
        if not mode_results and len(modes_in_results) == 1:
            mode_results = results
        mode_rec_reports = [rep for rep in all_rec_reports if getattr(rep, "agent_mode", mode) == mode]
        if not mode_rec_reports and len(modes_in_results) == 1:
            mode_rec_reports = all_rec_reports

        m = compute_recovery_metrics(
            recovery_reports=mode_rec_reports,
            agent_mode=mode,
            total_attempted_override=len(mode_results) if mode_results else exp.total_tasks,
            experiment_results=mode_results,
        )
        mode_metrics[mode] = m

        variant_data[mode] = {
            "sample_size": len(mode_results),
            "success_rate": m.end_to_end_success_rate,
            "total_failures": m.initial_unsuccessful_tasks,
            "interventions_initiated": m.recovery_interventions_initiated,
            "mean_latency_ms": m.efficiency.mean_total_latency_ms,
            "mean_tool_calls": m.efficiency.mean_additional_tool_calls,
            "mean_model_calls": m.efficiency.mean_additional_model_calls,
        }

    # 3. Comparative Metrics (if baseline and retry/traceguard exist)
    comparative_metrics = None
    if "baseline" in mode_metrics and ("fixed_retry" in mode_metrics or "traceguard_recovery" in mode_metrics or "traceguard" in mode_metrics):
        base_m = mode_metrics["baseline"]
        fixed_m = mode_metrics.get("fixed_retry", RecoveryMetricsSummary(agent_mode="fixed_retry"))
        tg_m = mode_metrics.get("traceguard_recovery") or mode_metrics.get("traceguard", RecoveryMetricsSummary(agent_mode="traceguard_recovery"))

        d_fixed = round(fixed_m.end_to_end_success_rate - base_m.end_to_end_success_rate, 2)
        d_tg = round(tg_m.end_to_end_success_rate - base_m.end_to_end_success_rate, 2)
        d_tg_fixed = round(tg_m.end_to_end_success_rate - fixed_m.end_to_end_success_rate, 2)

        rel_fixed = round((d_fixed / base_m.end_to_end_success_rate) * 100.0, 2) if base_m.end_to_end_success_rate > 0 else 0.0
        rel_tg = round((d_tg / base_m.end_to_end_success_rate) * 100.0, 2) if base_m.end_to_end_success_rate > 0 else 0.0
        rel_tg_fixed = round((d_tg_fixed / fixed_m.end_to_end_success_rate) * 100.0, 2) if fixed_m.end_to_end_success_rate > 0 else 0.0

        comparative_metrics = ComparativeMetricsSummary(
            baseline_success_rate=base_m.end_to_end_success_rate,
            fixed_retry_success_rate=fixed_m.end_to_end_success_rate,
            traceguard_success_rate=tg_m.end_to_end_success_rate,
            delta_fixed_retry_vs_baseline_pp=d_fixed,
            delta_traceguard_vs_baseline_pp=d_tg,
            delta_traceguard_vs_fixed_retry_pp=d_tg_fixed,
            relative_gain_fixed_retry_pct=rel_fixed,
            relative_gain_traceguard_pct=rel_tg,
            relative_gain_traceguard_vs_fixed_pct=rel_tg_fixed,
            mean_latency_baseline_ms=base_m.efficiency.mean_total_latency_ms,
            mean_latency_fixed_retry_ms=fixed_m.efficiency.mean_total_latency_ms,
            mean_latency_traceguard_ms=tg_m.efficiency.mean_total_latency_ms,
            latency_overhead_fixed_retry_ms=round(fixed_m.efficiency.mean_total_latency_ms - base_m.efficiency.mean_total_latency_ms, 2),
            latency_overhead_traceguard_ms=round(tg_m.efficiency.mean_total_latency_ms - base_m.efficiency.mean_total_latency_ms, 2),
        )

    # 4. Paired Statistical Comparisons
    statistical_comparisons: List[PairedComparisonMetric] = []
    pairs_to_test = [
        ("baseline", "fixed_retry"),
        ("baseline", "traceguard_recovery"),
        ("fixed_retry", "traceguard_recovery"),
    ]
    all_results_by_mode = {
        mode: [r for r in results if r.agent_mode == mode]
        for mode in modes_in_results
    }
    num_pairs = len([p for p in pairs_to_test if p[0] in all_results_by_mode and p[1] in all_results_by_mode])

    for mode_a, mode_b in pairs_to_test:
        if mode_a in all_results_by_mode and mode_b in all_results_by_mode:
            res_a = all_results_by_mode[mode_a]
            res_b = all_results_by_mode[mode_b]
            map_a = {r.task_id: r for r in res_a}
            map_b = {r.task_id: r for r in res_b}
            common_ids = [tid for tid in map_a if tid in map_b]

            if common_ids:
                bin_a = [1 if map_a[tid].terminal_status == "successful_completion" else 0 for tid in common_ids]
                bin_b = [1 if map_b[tid].terminal_status == "successful_completion" else 0 for tid in common_ids]
                lats_a = [map_a[tid].total_duration_ms for tid in common_ids]
                lats_b = [map_b[tid].total_duration_ms for tid in common_ids]

                try:
                    mcnemar_res = perform_mcnemar_test(
                        outcomes_a=bin_a,
                        outcomes_b=bin_b,
                        mode_a_name=mode_a,
                        mode_b_name=mode_b,
                        num_comparisons=num_pairs,
                    )
                    statistical_comparisons.append(mcnemar_res)

                    lat_res = perform_paired_latency_comparison(
                        latencies_a=lats_a,
                        latencies_b=lats_b,
                        mode_a_name=mode_a,
                        mode_b_name=mode_b,
                    )
                    statistical_comparisons.append(lat_res)
                except Exception as e:
                    logger.debug(f"Statistical comparison notice: {e}")

    # 5. Failure Analysis
    failure_analysis = None
    try:
        tasks = BenchmarkDatasetLoader().load_tasks(version=cfg.benchmark_version)
        diag_reports = storage.get_diagnostics_for_experiment(exp.experiment_id)
        primary_mode = "traceguard_recovery" if "traceguard_recovery" in modes_in_results else modes_in_results[0]
        failure_analysis = compute_failure_analysis(
            tasks=tasks,
            execution_results=all_results_by_mode.get(primary_mode, results),
            recovery_reports=all_rec_reports,
            diagnostic_reports=diag_reports,
            experiment_id=exp.experiment_id,
        )
    except Exception as e:
        logger.warning(f"Failure analysis advisory for {exp.experiment_id}: {e}")

    # 6. Ablation (if applicable)
    ablation_results = None
    if cfg.experiment_type == "ablation" or len(modes_in_results) >= 3:
        try:
            ablation_results = compute_ablation_analysis(
                experiment_id=cfg.experiment_id,
                variant_results=variant_data,
            )
        except Exception as e:
            logger.debug(f"Ablation analysis advisory: {e}")

    # 7. Generate Research Report Markdown
    report_md = ResearchReportGenerator.generate_markdown_report(
        config=cfg,
        manifest=manifest,
        mode_metrics=mode_metrics,
        comparative_metrics=comparative_metrics,
        statistical_comparisons=statistical_comparisons,
        failure_analysis=failure_analysis,
        ablation_results=ablation_results,
    )

    # 8. Save Artifacts to Storage
    storage.save_experiment_artifacts(
        experiment_id=cfg.experiment_id,
        configuration_hash=cfg.configuration_hash or "",
        manifest=manifest,
        report_md=report_md,
        comparisons=statistical_comparisons,
        failure_analysis=failure_analysis,
        ablation=ablation_results,
    )

    manifest_dict = manifest.model_dump()
    return report_md, manifest_dict
