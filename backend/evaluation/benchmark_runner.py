"""Benchmark Runner orchestrating reproducible experiments against baseline agent."""
import logging
import uuid
from typing import Any, Dict, List, Optional
from backend.agents.controller import AgentController
from backend.agents.mock_model import MockModelAdapter
from backend.agents.tool_registry import ToolRegistry
from backend.config import settings
from backend.evaluation.dataset import BenchmarkDatasetLoader
from backend.evaluation.failure_injection import InjectedModelAdapter, InjectedToolExecutor
from backend.evaluation.metrics import compute_experiment_metrics
from backend.evaluation.schemas import (
    BenchmarkTask,
    ExperimentRunRequest,
    ExperimentSummary,
    TaskExecutionResult,
    TerminalStatusType,
)
from backend.models.schemas import TaskCreateRequest, TaskResponse
from backend.tracing.event_schema import current_utc_timestamp
from backend.tracing.storage import TraceStorage
from backend.verification.verifier import OutcomeVerifier

logger = logging.getLogger(__name__)

class BenchmarkRunner:
    """Executes benchmark tasks, records evaluation metrics, and persists experiment runs."""

    def __init__(
        self,
        dataset_loader: Optional[BenchmarkDatasetLoader] = None,
        storage: Optional[TraceStorage] = None
    ):
        self.dataset_loader = dataset_loader or BenchmarkDatasetLoader()
        self.storage = storage or TraceStorage()

    def run_experiment(self, request: ExperimentRunRequest) -> ExperimentSummary:
        """Execute a full benchmark experiment according to requested configuration."""
        tasks: List[BenchmarkTask] = self.dataset_loader.load_tasks(
            version=request.benchmark_version,
            task_ids=request.task_ids,
            category=request.category
        )

        experiment_id = f"exp_{uuid.uuid4().hex[:12]}"
        created_at = current_utc_timestamp()
        total_executions = len(tasks) * request.repetitions

        logger.info(
            f"Starting Experiment [{experiment_id}]: {len(tasks)} tasks x {request.repetitions} reps "
            f"= {total_executions} executions (Mode: {request.agent_mode}, Failure Injection: {request.enable_failure_injection})"
        )

        initial_summary = ExperimentSummary(
            experiment_id=experiment_id,
            benchmark_version=request.benchmark_version,
            agent_mode=request.agent_mode,
            status="running",
            total_tasks=total_executions,
            completed_tasks=0,
            created_at=created_at,
            config=request.model_dump(),
            metrics=None,
        )
        self.storage.save_experiment(initial_summary)

        results: List[TaskExecutionResult] = []
        completed_count = 0

        for rep in range(1, request.repetitions + 1):
            for task in tasks:
                res = self._execute_single_task(
                    experiment_id=experiment_id,
                    task=task,
                    request=request,
                    repetition_index=rep
                )
                results.append(res)
                completed_count += 1

        completed_at = current_utc_timestamp()

        # Compute Aggregated Metrics
        metrics = compute_experiment_metrics(
            results=results,
            experiment_id=experiment_id,
            benchmark_version=request.benchmark_version,
            agent_mode=request.agent_mode,
            repetitions=request.repetitions
        )

        # Persist Per-Task Results, Metrics, and Final Experiment Summary
        self.storage.save_experiment_results(results)
        self.storage.save_experiment_metrics(experiment_id, metrics)

        final_summary = ExperimentSummary(
            experiment_id=experiment_id,
            benchmark_version=request.benchmark_version,
            agent_mode=request.agent_mode,
            status="completed",
            total_tasks=total_executions,
            completed_tasks=completed_count,
            created_at=created_at,
            completed_at=completed_at,
            config=request.model_dump(),
            metrics=metrics,
        )
        self.storage.save_experiment(final_summary)

        logger.info(
            f"Experiment [{experiment_id}] completed with Success Rate: {metrics.success_rate}% "
            f"({metrics.successful_tasks}/{metrics.total_attempted})"
        )
        return final_summary

    def _execute_single_task(
        self,
        experiment_id: str,
        task: BenchmarkTask,
        request: ExperimentRunRequest,
        repetition_index: int
    ) -> TaskExecutionResult:
        """Execute a single benchmark task and record its evaluation result."""
        started_at = current_utc_timestamp()

        # Build custom controller if failure injection is requested for this task
        failure_scenario = task.failure_scenario if request.enable_failure_injection else None

        registry = ToolRegistry()
        base_model = MockModelAdapter()

        if failure_scenario:
            tool_executor = InjectedToolExecutor(registry, failure_config=failure_scenario)
            model_adapter = InjectedModelAdapter(base_model, failure_config=failure_scenario)
            controller = AgentController(
                tool_registry=registry,
                model_adapter=model_adapter,
                storage=self.storage
            )
            controller.tool_executor = tool_executor
        else:
            controller = AgentController(
                tool_registry=registry,
                model_adapter=base_model,
                storage=self.storage
            )

        task_create_req = TaskCreateRequest(
            task=task.task_description,
            max_steps=request.max_steps or 8,
            timeout_seconds=request.timeout_seconds or 30.0,
            allowed_tools=task.allowed_tools,
            verification_rule=task.verification_rule
        )

        task_response: TaskResponse = controller.run_task(task_create_req)
        completed_at = current_utc_timestamp()

        # Classify Terminal Status
        terminal_status: TerminalStatusType
        if task_response.status == "step_limit_reached":
            terminal_status = "step_limit_exhaustion"
        elif task_response.status == "timed_out":
            terminal_status = "timeout"
        elif task_response.status == "failed":
            if "tool" in (task_response.error_info or "").lower() or (failure_scenario and "tool" in failure_scenario.failure_type):
                terminal_status = "tool_error"
            else:
                terminal_status = "internal_error"
        else:
            # Agent completed
            if task_response.verification:
                if task_response.verification.status == "verified":
                    terminal_status = "successful_completion"
                elif task_response.verification.status == "failed":
                    terminal_status = "incorrect_answer"
                else:
                    terminal_status = "unverified_completion"
            else:
                # No verification rule
                if failure_scenario and failure_scenario.expected_terminal_status:
                    terminal_status = failure_scenario.expected_terminal_status
                else:
                    terminal_status = "unverified_completion"

        # Count tool calls and errors from trace events
        trace_events = self.storage.get_events(task_response.task_id)
        tool_call_count = sum(1 for e in trace_events if e.event_type == "tool_execution_started")
        tool_error_count = sum(1 for e in trace_events if e.event_type == "tool_execution_failed")

        verif_status = task_response.verification.status if task_response.verification else "not_applicable"
        verif_msg = task_response.verification.verification_message if task_response.verification else "No verification rule applied."

        # Model tokens from final event if present
        model_tokens = None
        for ev in reversed(trace_events):
            if ev.model_tokens:
                model_tokens = ev.model_tokens
                break

        return TaskExecutionResult(
            experiment_id=experiment_id,
            task_id=task.task_id,
            run_id=task_response.run_id,
            benchmark_version=task.benchmark_version,
            agent_mode=request.agent_mode,
            started_at=started_at,
            completed_at=completed_at,
            terminal_status=terminal_status,
            expected_answer=task.expected_answer,
            observed_answer=task_response.final_answer,
            verification_status=verif_status,
            verification_message=verif_msg,
            step_count=task_response.steps_count,
            tool_call_count=tool_call_count,
            tool_error_count=tool_error_count,
            total_duration_ms=task_response.duration_ms,
            model_tokens=model_tokens,
            estimated_cost=None,  # Price unknown for mock model; reported as None
            trace_reference={"task_id": task_response.task_id, "run_id": task_response.run_id},
            failure_scenario_id=failure_scenario.scenario_id if failure_scenario else None,
        )
