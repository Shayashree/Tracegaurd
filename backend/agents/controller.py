"""Agent Controller managing the baseline agent execution loop."""
import json
import logging
import time
import uuid
from typing import Any, List, Optional
from backend.agents.mock_model import MockModelAdapter
from backend.agents.model_adapter import BaseModelAdapter, OpenAIModelAdapter
from backend.agents.tool_registry import ToolExecutor, ToolRegistry
from backend.config import settings
from backend.models.schemas import (
    InteractionStep,
    ModelResponse,
    TaskCreateRequest,
    TaskResponse,
    ToolCallRequest,
    VerificationResult,
)
from backend.tracing.collector import TraceCollector
from backend.tracing.event_schema import (
    EVENT_FINAL_ANSWER_PROPOSED,
    EVENT_MODEL_REQUEST,
    EVENT_STEP_LIMIT_REACHED,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_FAILED,
    EVENT_TOOL_CALL_REQUESTED,
    EVENT_TOOL_EXEC_COMPLETED,
    EVENT_TOOL_EXEC_FAILED,
    EVENT_TOOL_EXEC_STARTED,
    EVENT_VERIFICATION_COMPLETED,
    current_utc_timestamp,
)
from backend.tracing.storage import TraceStorage
from backend.verification.verifier import OutcomeVerifier

logger = logging.getLogger(__name__)

class AgentController:
    """Orchestrates baseline agent execution, tool dispatch, tracing, and verification."""

    def __init__(
        self,
        tool_registry: Optional[ToolRegistry] = None,
        model_adapter: Optional[BaseModelAdapter] = None,
        storage: Optional[TraceStorage] = None,
        failure_detector: Optional[Any] = None,
    ):
        self.tool_registry = tool_registry or ToolRegistry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.storage = storage or TraceStorage()
        self.model_adapter = model_adapter or self._init_default_adapter()
        self.failure_detector = failure_detector

    def _init_default_adapter(self) -> BaseModelAdapter:
        if settings.MODEL_ADAPTER == "openai" and settings.OPENAI_API_KEY:
            try:
                return OpenAIModelAdapter()
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI adapter ({e}), falling back to mock adapter.")
        return MockModelAdapter()

    def run_task(self, request: TaskCreateRequest) -> TaskResponse:
        """Execute task synchronously through the baseline loop."""
        start_wall_time = time.time()
        start_perf_time = time.perf_counter()

        task_id = f"task_{uuid.uuid4().hex[:12]}"
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        created_at = current_utc_timestamp()

        max_steps = request.max_steps if request.max_steps is not None else settings.DEFAULT_MAX_STEPS
        timeout_seconds = request.timeout_seconds if request.timeout_seconds is not None else settings.DEFAULT_TIMEOUT_SECONDS

        collector = TraceCollector(task_id=task_id, run_id=run_id, storage=self.storage)
        collector.record_task_started(request.task)

        # Retrieve allowed tool definitions
        allowed_tools = request.allowed_tools
        tool_definitions = self.tool_registry.list_definitions(allowed_tools)

        history: List[InteractionStep] = []
        step_index = 0
        final_answer: Optional[str] = None
        error_info: Optional[str] = None
        task_status: str = "running"
        verification_result: Optional[VerificationResult] = None

        logger.info(f"Starting task execution [{task_id}], max_steps={max_steps}, timeout={timeout_seconds}s")

        while step_index < max_steps:
            # Check for timeout
            elapsed_sec = time.time() - start_wall_time
            if elapsed_sec > timeout_seconds:
                task_status = "timed_out"
                error_info = f"Execution exceeded timeout limit of {timeout_seconds}s (elapsed: {elapsed_sec:.2f}s)."
                total_duration_ms = (time.perf_counter() - start_perf_time) * 1000
                collector.record_task_failed(
                    step_index=step_index,
                    error_message=error_info,
                    duration_ms=total_duration_ms,
                    error_type="ExecutionTimeout"
                )
                break

            step_index += 1

            # 1. Model Request
            model_start = time.perf_counter()
            try:
                model_response: ModelResponse = self.model_adapter.generate_next_step(
                    task=request.task,
                    tool_definitions=tool_definitions,
                    history=history,
                    scenario_hint=request.mock_scenario,
                )
            except Exception as e:
                model_dur = (time.perf_counter() - model_start) * 1000
                task_status = "failed"
                error_info = f"Model generation error: {str(e)}"
                collector.record_event(
                    step_index=step_index,
                    event_type=EVENT_MODEL_REQUEST,
                    status="failed",
                    duration_ms=model_dur,
                    output_summary=error_info,
                    error_type="ModelAdapterError"
                )
                collector.record_task_failed(
                    step_index=step_index,
                    error_message=error_info,
                    duration_ms=(time.perf_counter() - start_perf_time) * 1000,
                    error_type="ModelAdapterError"
                )
                break

            model_dur = (time.perf_counter() - model_start) * 1000
            collector.record_model_request(
                step_index=step_index,
                prompt_summary=f"Step {step_index} model query",
                duration_ms=model_dur,
                model_tokens=model_response.tokens_used.model_dump() if model_response.tokens_used else None,
            )

            # 2. Process Model Output
            if model_response.is_final_answer:
                final_answer = model_response.final_answer or ""
                collector.record_final_answer_proposed(
                    step_index=step_index,
                    final_answer=final_answer
                )

                # Outcome Verification
                verif_start = time.perf_counter()
                verification_result = OutcomeVerifier.verify(
                    final_answer=final_answer,
                    rule=request.verification_rule
                )
                verif_dur = (time.perf_counter() - verif_start) * 1000

                collector.record_verification_completed(
                    step_index=step_index,
                    verification_status=verification_result.status,
                    summary=verification_result.verification_message
                )

                task_status = "completed"
                total_duration_ms = (time.perf_counter() - start_perf_time) * 1000
                collector.record_task_completed(
                    step_index=step_index,
                    final_answer=final_answer,
                    duration_ms=total_duration_ms
                )
                break

            # Handle Tool Call Request
            tool_call = model_response.tool_call
            if not tool_call:
                # Malformed model response: neither final answer nor tool call
                task_status = "failed"
                error_info = "Model responded with neither a tool call nor a final answer."
                collector.record_task_failed(
                    step_index=step_index,
                    error_message=error_info,
                    duration_ms=(time.perf_counter() - start_perf_time) * 1000,
                    error_type="MalformedModelResponse"
                )
                break

            args_str = json.dumps(tool_call.arguments)
            collector.record_tool_call_requested(
                step_index=step_index,
                tool_name=tool_call.tool_name,
                arguments_summary=args_str
            )

            # 3. Tool Execution
            collector.record_tool_exec_started(
                step_index=step_index,
                tool_name=tool_call.tool_name,
                arguments_summary=args_str
            )

            try:
                tool_result = self.tool_executor.execute(tool_call, allowed_tools=allowed_tools)
            except TimeoutError as te:
                task_status = "failed"
                error_info = f"Tool execution timed out: {str(te)}"
                collector.record_tool_exec_failed(
                    step_index=step_index,
                    tool_name=tool_call.tool_name,
                    error_message=error_info,
                    duration_ms=0.0,
                    error_type="ToolTimeoutError"
                )
                collector.record_task_failed(
                    step_index=step_index,
                    error_message=error_info,
                    duration_ms=(time.perf_counter() - start_perf_time) * 1000,
                    error_type="ToolTimeoutError"
                )
                break
            except Exception as e:
                task_status = "failed"
                error_info = f"Tool execution failed: {str(e)}"
                collector.record_tool_exec_failed(
                    step_index=step_index,
                    tool_name=tool_call.tool_name,
                    error_message=error_info,
                    duration_ms=0.0,
                    error_type="ToolExecutionError"
                )
                collector.record_task_failed(
                    step_index=step_index,
                    error_message=error_info,
                    duration_ms=(time.perf_counter() - start_perf_time) * 1000,
                    error_type="ToolExecutionError"
                )
                break

            if tool_result.success:
                result_str = json.dumps(tool_result.data) if tool_result.data is not None else "Success"
                collector.record_tool_exec_completed(
                    step_index=step_index,
                    tool_name=tool_call.tool_name,
                    output_summary=result_str,
                    duration_ms=tool_result.duration_ms or 0.0
                )
            else:
                err_str = tool_result.error or "Unknown tool error"
                collector.record_tool_exec_failed(
                    step_index=step_index,
                    tool_name=tool_call.tool_name,
                    error_message=err_str,
                    duration_ms=tool_result.duration_ms or 0.0,
                    error_type="ToolExecutionError"
                )

            # Record step in interaction history
            history.append(InteractionStep(
                step_index=step_index,
                role="assistant",
                tool_call=tool_call
            ))
            history.append(InteractionStep(
                step_index=step_index,
                role="tool",
                tool_result=tool_result
            ))

        # Check if loop exited due to step limit
        if final_answer is None and task_status == "running":
            task_status = "step_limit_reached"
            error_info = f"Agent stopped: maximum step limit ({max_steps}) was reached without proposing a final answer."
            collector.record_step_limit_reached(step_index=step_index, max_steps=max_steps)
            total_duration_ms = (time.perf_counter() - start_perf_time) * 1000
            collector.record_task_failed(
                step_index=step_index,
                error_message=error_info,
                duration_ms=total_duration_ms,
                error_type="StepLimitExceeded"
            )

        total_duration_ms = (time.perf_counter() - start_perf_time) * 1000
        completed_at = current_utc_timestamp()

        # Build final response object
        response = TaskResponse(
            task_id=task_id,
            run_id=run_id,
            task=request.task,
            status=task_status,
            final_answer=final_answer,
            error_info=error_info,
            verification=verification_result,
            steps_count=step_index,
            duration_ms=round(total_duration_ms, 2),
            created_at=created_at,
            completed_at=completed_at,
        )

        # Persist task record and flush traces
        collector.flush()
        self.storage.save_task(response)

        # Passive diagnostic report generation if detector is configured
        if self.failure_detector:
            try:
                events = collector.get_events()
                task_ctx = {
                    "task_description": request.task,
                    "max_steps": max_steps,
                    "allowed_tools": allowed_tools,
                    "verification_rule": request.verification_rule.model_dump() if request.verification_rule else None,
                    "verification_status": verification_result.status if verification_result else "unverified",
                    "terminal_status": task_status,
                }
                diag_report = self.failure_detector.analyze(
                    events=events,
                    task_id=task_id,
                    run_id=run_id,
                    task_context=task_ctx,
                )
                self.storage.save_diagnostic_report(diag_report)

                mode = getattr(request, "agent_mode", "baseline")
                if mode in ("traceguard_recovery", "traceguard") and diag_report and diag_report.findings:
                    from backend.reliability.recovery_engine import RecoveryEngine
                    from backend.reliability.recovery_report import RecoveryTerminalStatus
                    rec_engine = RecoveryEngine(tool_registry=self.tool_registry, storage=self.storage, model_adapter=self.model_adapter)
                    rec_rep = rec_engine.recover(
                        task_response=response,
                        task_context=task_ctx,
                        initial_trace_events=events,
                        diag_report=diag_report,
                    )
                    if rec_rep and rec_rep.recovery_attempted:
                        response.recovery_status = rec_rep.terminal_status.value
                        if rec_rep.terminal_status == RecoveryTerminalStatus.RECOVERED_SUCCESSFULLY:
                            response.status = "completed"
                            if rec_rep.final_answer:
                                response.final_answer = rec_rep.final_answer
                            if response.verification:
                                response.verification.verified = True
                                response.verification.status = "verified"
                                response.verification.verification_message = f"Recovered successfully: {rec_rep.terminal_status.value}"
                        self.storage.save_task(response)
            except Exception as e:
                logger.warning(f"Passive diagnostic/recovery analysis error for task [{task_id}]: {e}")

        logger.info(f"Task completed [{task_id}] with status={task_status} in {total_duration_ms:.1f}ms")
        return response
