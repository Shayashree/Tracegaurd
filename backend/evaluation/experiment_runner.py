"""Comprehensive Experiment Runner for TraceGuard Milestone 5.
Executes multi-mode benchmark comparisons, statistical tests, failure analysis, ablation, and report generation.
"""
import logging
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.agents.controller import AgentController
from backend.agents.mock_model import MockModelAdapter
from backend.agents.tool_registry import ToolRegistry
from backend.evaluation.ablation_analysis import AblationAnalysisResult, compute_ablation_analysis
from backend.evaluation.benchmark_runner import BenchmarkRunner
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.experiment_config import ExperimentConfig
from backend.evaluation.failure_analysis import FailureAnalysisReport, compute_failure_analysis
from backend.evaluation.manifest import ReproducibilityManifest, create_reproducibility_manifest
from backend.evaluation.recovery_metrics import (
    ComparativeMetricsSummary,
    RecoveryMetricsSummary,
    compute_recovery_metrics,
)
from backend.evaluation.report_generator import ResearchReportGenerator
from backend.evaluation.schemas import BenchmarkTask, ExperimentRunRequest, TaskExecutionResult
from backend.evaluation.statistical_tests import (
    PairedComparisonMetric,
    perform_mcnemar_test,
    perform_paired_latency_comparison,
)
from backend.tracing.event_schema import current_utc_timestamp
from backend.tracing.storage import TraceStorage

logger = logging.getLogger(__name__)

class ExperimentExecutionSummary(BaseModel):
    """Unified result container for a multi-mode Milestone 5 experiment execution."""
    experiment_id: str
    configuration_hash: str
    benchmark_version: str
    dataset_split: str
    experiment_type: str
    agent_modes: List[str]
    status: str
    total_tasks: int
    completed_tasks: int
    started_at: str
    completed_at: str
    mode_metrics: Dict[str, RecoveryMetricsSummary] = Field(default_factory=dict)
    comparative_metrics: Optional[ComparativeMetricsSummary] = None
    statistical_comparisons: List[PairedComparisonMetric] = Field(default_factory=list)
    failure_analysis: Optional[FailureAnalysisReport] = None
    ablation_results: Optional[AblationAnalysisResult] = None
    manifest: Optional[ReproducibilityManifest] = None
    report_markdown: Optional[str] = None

class FullExperimentRunner:
    """Orchestrates comprehensive multi-mode experimental evaluations."""

    def __init__(
        self,
        dataset_loader: Optional[BenchmarkDatasetLoader] = None,
        storage: Optional[TraceStorage] = None
    ):
        self.dataset_loader = dataset_loader or BenchmarkDatasetLoader()
        self.storage = storage or TraceStorage()
        self.benchmark_runner = BenchmarkRunner(dataset_loader=self.dataset_loader, storage=self.storage)

    def run_experiment(self, config: ExperimentConfig) -> ExperimentExecutionSummary:
        """Executes all requested agent modes on the specified benchmark tasks and calculates full analytics."""
        logger.info(
            f"Starting Full Experiment [{config.experiment_id}] (Type: {config.experiment_type}, "
            f"Split: {config.dataset_split}, Modes: {config.agent_modes})"
        )

        # Resolve dataset split
        split_param = None
        if config.dataset_split in ("train", "val", "test"):
            split_param = config.dataset_split
        elif config.dataset_split == "held_out":
            split_param = "test"

        tasks: List[BenchmarkTask] = self.dataset_loader.load_tasks(
            version=config.benchmark_version,
            task_ids=config.task_ids,
            category=config.category,
            split=split_param
        )

        enable_fi = (
            config.experiment_type == "controlled_failure"
            or config.failure_injection_configuration.get("enable_failure_injection", False)
            or config.category == "failure_scenario"
        )

        all_results_by_mode: Dict[str, List[TaskExecutionResult]] = {}
        recovery_reports_by_mode: Dict[str, List[Any]] = {}
        diagnostic_reports_by_mode: Dict[str, List[Any]] = {}

        # 1. Execute Each Configured Agent Mode
        for mode in config.agent_modes:
            mode_runner_req = ExperimentRunRequest(
                benchmark_version=config.benchmark_version,
                task_ids=[t.task_id for t in tasks],
                category=config.category,
                agent_mode="baseline" if mode == "detection_only" else mode,
                repetitions=config.repetitions,
                enable_failure_injection=enable_fi,
                max_steps=config.step_limit,
                timeout_seconds=config.task_timeout,
            )

            # Run through benchmark runner
            sub_summary = self.benchmark_runner.run_experiment(mode_runner_req)
            sub_results = self.storage.get_experiment_results(sub_summary.experiment_id)

            # Link results, recovery, and diagnostics to parent experiment_id
            parent_results = []
            for r in sub_results:
                copied = r.model_copy(update={"experiment_id": config.experiment_id, "agent_mode": mode})
                parent_results.append(copied)
            self.storage.save_experiment_results(parent_results)
            all_results_by_mode[mode] = parent_results

            recs = self.storage.get_recovery_reports_for_experiment(sub_summary.experiment_id)
            for rec in recs:
                rec_copy = rec.model_copy(update={"experiment_id": config.experiment_id})
                self.storage.save_recovery_report(rec_copy)
            recovery_reports_by_mode[mode] = recs

            diags = self.storage.get_diagnostics_for_experiment(sub_summary.experiment_id)
            for diag in diags:
                diag_copy = diag.model_copy(update={"experiment_id": config.experiment_id})
                self.storage.save_diagnostic_report(diag_copy)
            diagnostic_reports_by_mode[mode] = diags

        # 2. Compute Mode-Level Recovery and Efficiency Metrics
        mode_metrics: Dict[str, RecoveryMetricsSummary] = {}
        variant_data: Dict[str, Dict[str, Any]] = {}

        for mode, results in all_results_by_mode.items():
            recs = recovery_reports_by_mode.get(mode, [])
            m = compute_recovery_metrics(
                recovery_reports=recs,
                agent_mode=mode,
                total_attempted_override=len(results),
                experiment_results=results,
            )
            mode_metrics[mode] = m

            # Format for ablation
            variant_data[mode] = {
                "sample_size": len(results),
                "success_rate": m.end_to_end_success_rate,
                "total_failures": m.initial_unsuccessful_tasks,
                "interventions_initiated": m.recovery_interventions_initiated,
                "mean_latency_ms": m.efficiency.mean_total_latency_ms,
                "mean_tool_calls": m.efficiency.mean_additional_tool_calls,
                "mean_model_calls": m.efficiency.mean_additional_model_calls,
            }

        # 3. Comparative Metrics
        comparative_metrics = None
        if "baseline" in mode_metrics and ("fixed_retry" in mode_metrics or "traceguard_recovery" in mode_metrics):
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
        num_pairs = len([p for p in pairs_to_test if p[0] in all_results_by_mode and p[1] in all_results_by_mode])

        for mode_a, mode_b in pairs_to_test:
            if mode_a in all_results_by_mode and mode_b in all_results_by_mode:
                res_a = all_results_by_mode[mode_a]
                res_b = all_results_by_mode[mode_b]
                # Match by task_id
                map_a = {r.task_id: r for r in res_a}
                map_b = {r.task_id: r for r in res_b}
                common_ids = [t.task_id for t in tasks if t.task_id in map_a and t.task_id in map_b]

                if common_ids:
                    bin_a = [1 if map_a[tid].terminal_status == "successful_completion" else 0 for tid in common_ids]
                    bin_b = [1 if map_b[tid].terminal_status == "successful_completion" else 0 for tid in common_ids]
                    lats_a = [map_a[tid].total_duration_ms for tid in common_ids]
                    lats_b = [map_b[tid].total_duration_ms for tid in common_ids]

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

        # 5. Failure-Specific Breakdown
        primary_mode = "traceguard_recovery" if "traceguard_recovery" in all_results_by_mode else config.agent_modes[0]
        failure_analysis = compute_failure_analysis(
            tasks=tasks,
            execution_results=all_results_by_mode.get(primary_mode, []),
            recovery_reports=recovery_reports_by_mode.get(primary_mode, []),
            diagnostic_reports=diagnostic_reports_by_mode.get(primary_mode, []),
            experiment_id=config.experiment_id,
        )

        # 6. Ablation Analysis
        ablation_results = None
        if config.experiment_type == "ablation" or len(config.agent_modes) >= 3:
            ablation_results = compute_ablation_analysis(
                experiment_id=config.experiment_id,
                variant_results=variant_data,
            )

        # 7. Reproducibility Manifest
        manifest = create_reproducibility_manifest(
            config=config,
            artifact_references={
                "database_path": str(self.storage.db_path),
                "total_tasks_evaluated": str(len(tasks)),
                "experiment_id": config.experiment_id,
            }
        )

        # 8. Research Report Generation
        report_md = ResearchReportGenerator.generate_markdown_report(
            config=config,
            manifest=manifest,
            mode_metrics=mode_metrics,
            comparative_metrics=comparative_metrics,
            statistical_comparisons=statistical_comparisons,
            failure_analysis=failure_analysis,
            ablation_results=ablation_results,
        )

        # 9. Persist Experiment Artifacts to Storage
        self.storage.save_experiment_artifacts(
            experiment_id=config.experiment_id,
            configuration_hash=config.configuration_hash or "",
            manifest=manifest,
            report_md=report_md,
            comparisons=statistical_comparisons,
            failure_analysis=failure_analysis,
            ablation=ablation_results,
        )

        completed_at = current_utc_timestamp()

        # Update experiment in DB
        from backend.evaluation.schemas import ExperimentSummary
        exp_summary = ExperimentSummary(
            experiment_id=config.experiment_id,
            benchmark_version=config.benchmark_version,
            agent_mode=primary_mode,
            status="completed",
            total_tasks=len(tasks) * len(config.agent_modes),
            completed_tasks=len(tasks) * len(config.agent_modes),
            created_at=config.started_at,
            completed_at=completed_at,
            config=config.model_dump(),
        )
        self.storage.save_experiment(exp_summary)

        return ExperimentExecutionSummary(
            experiment_id=config.experiment_id,
            configuration_hash=config.configuration_hash or "",
            benchmark_version=config.benchmark_version,
            dataset_split=config.dataset_split,
            experiment_type=config.experiment_type,
            agent_modes=config.agent_modes,
            status="completed",
            total_tasks=len(tasks) * len(config.agent_modes),
            completed_tasks=len(tasks) * len(config.agent_modes),
            started_at=config.started_at,
            completed_at=completed_at,
            mode_metrics=mode_metrics,
            comparative_metrics=comparative_metrics,
            statistical_comparisons=statistical_comparisons,
            failure_analysis=failure_analysis,
            ablation_results=ablation_results,
            manifest=manifest,
            report_markdown=report_md,
        )
