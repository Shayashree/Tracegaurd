"""Trajectory Feature Extractor for TraceGuard execution traces."""
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from backend.reliability.diagnostic_report import TrajectoryFeatures
from backend.tracing.event_schema import (
    EVENT_FINAL_ANSWER_PROPOSED,
    EVENT_MODEL_REQUEST,
    EVENT_STEP_LIMIT_REACHED,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_FAILED,
    EVENT_TASK_STARTED,
    EVENT_TOOL_CALL_REQUESTED,
    EVENT_TOOL_EXEC_COMPLETED,
    EVENT_TOOL_EXEC_FAILED,
    EVENT_TOOL_EXEC_STARTED,
    EVENT_VERIFICATION_COMPLETED,
    TraceEventModel,
)

logger = logging.getLogger(__name__)

def normalize_tool_arguments(args: Any) -> str:
    """
    Deterministically normalize tool arguments into canonical JSON string.
    Sorts dictionary keys, strips whitespace, standardizes numerical representations,
    and returns stable serialization.
    """
    if args is None:
        return "{}"
    if isinstance(args, str):
        trimmed = args.strip()
        if not trimmed:
            return "{}"
        try:
            parsed = json.loads(trimmed)
            return normalize_tool_arguments(parsed)
        except json.JSONDecodeError:
            # Clean string
            return json.dumps({"raw_string": trimmed.lower()}, sort_keys=True)

    if isinstance(args, dict):
        normalized_dict = {}
        for k in sorted(args.keys()):
            v = args[k]
            if isinstance(v, float):
                # Standardize floats (e.g., 20.0 vs 20)
                normalized_dict[str(k).lower().strip()] = round(v, 6) if not v.is_integer() else int(v)
            elif isinstance(v, str):
                normalized_dict[str(k).lower().strip()] = v.strip().lower()
            elif isinstance(v, (dict, list)):
                normalized_dict[str(k).lower().strip()] = json.loads(normalize_tool_arguments(v))
            else:
                normalized_dict[str(k).lower().strip()] = v
        return json.dumps(normalized_dict, sort_keys=True)

    if isinstance(args, (list, tuple)):
        normalized_list = []
        for item in args:
            if isinstance(item, (dict, list)):
                normalized_list.append(json.loads(normalize_tool_arguments(item)))
            elif isinstance(item, str):
                normalized_list.append(item.strip().lower())
            else:
                normalized_list.append(item)
        return json.dumps(normalized_list, sort_keys=True)

    return json.dumps({"val": args}, sort_keys=True)

class TrajectoryFeatureExtractor:
    """
    Extracts structured, deterministic feature vectors from ordered trace events.
    Handles missing fields explicitly without inventing data.
    """

    @classmethod
    def extract_features(
        cls,
        events: List[Any],
        configured_step_limit: Optional[int] = None,
        evidence_required: Optional[bool] = None
    ) -> TrajectoryFeatures:
        if not events:
            return TrajectoryFeatures(
                total_steps=0,
                total_tool_calls=0,
                unique_tools_used=0,
                terminal_status="no_events",
            )

        # Standardize events to dicts or models
        parsed_events: List[Dict[str, Any]] = []
        for e in events:
            if isinstance(e, dict):
                parsed_events.append(e)
            elif hasattr(e, "model_dump"):
                parsed_events.append(e.model_dump())
            elif hasattr(e, "__dict__"):
                parsed_events.append(e.__dict__)

        # Sort chronologically by step_index and timestamp
        parsed_events.sort(key=lambda x: (x.get("step_index", 0), x.get("timestamp", "")))

        total_tool_calls = 0
        tool_names_sequence: List[str] = []
        tool_call_signatures: List[Tuple[str, str]] = []  # (tool_name, normalized_args)
        tool_failure_counts: Dict[str, int] = {}
        tool_exec_failures = 0
        validation_failures = 0
        empty_tool_results = 0
        successful_tool_results = 0
        final_answer_attempts = 0
        step_limit_reached = False
        final_answer_produced = False
        terminal_status: Optional[str] = None
        verification_status: Optional[str] = None
        evidence_retrieval_occurred = False
        evidence_policy_satisfied: Optional[bool] = None
        durations: List[float] = []

        distinct_arg_set = set()
        current_consecutive_ident = 1
        max_consecutive_ident = 0
        consecutive_empty_count = 0
        max_consecutive_empty = 0

        last_sig: Optional[Tuple[str, str]] = None

        for ev in parsed_events:
            ev_type = ev.get("event_type")
            t_name = ev.get("tool_name") or ""
            dur = ev.get("duration_ms")
            if dur is not None and isinstance(dur, (int, float)):
                durations.append(float(dur))

            # 1. Tool Call Requests
            if ev_type == EVENT_TOOL_CALL_REQUESTED:
                total_tool_calls += 1
                tool_names_sequence.append(t_name)
                norm_args = normalize_tool_arguments(ev.get("input_summary") or ev.get("arguments_summary"))
                sig = (t_name.lower(), norm_args)
                tool_call_signatures.append(sig)
                distinct_arg_set.add(norm_args)

                if last_sig == sig:
                    current_consecutive_ident += 1
                else:
                    current_consecutive_ident = 1
                if current_consecutive_ident > max_consecutive_ident:
                    max_consecutive_ident = current_consecutive_ident
                last_sig = sig

            # 2. Tool Execution Completed
            elif ev_type == EVENT_TOOL_EXEC_COMPLETED:
                successful_tool_results += 1
                out_summary = (ev.get("output_summary") or "").lower()
                is_empty = (
                    '"matches": []' in out_summary
                    or '"count": 0' in out_summary
                    or "no matching records" in out_summary
                    or "no relevant evidence" in out_summary
                    or "0 matches" in out_summary
                )
                if is_empty:
                    empty_tool_results += 1
                    consecutive_empty_count += 1
                else:
                    consecutive_empty_count = 0

                if consecutive_empty_count > max_consecutive_empty:
                    max_consecutive_empty = consecutive_empty_count

                if t_name == "document_search" and not is_empty:
                    evidence_retrieval_occurred = True

            # 3. Tool Execution Failed
            elif ev_type == EVENT_TOOL_EXEC_FAILED:
                tool_exec_failures += 1
                consecutive_empty_count += 1
                if consecutive_empty_count > max_consecutive_empty:
                    max_consecutive_empty = consecutive_empty_count

                tool_failure_counts[t_name] = tool_failure_counts.get(t_name, 0) + 1
                err_type = ev.get("error_type") or ""
                err_msg = (ev.get("output_summary") or "").lower()
                if "validation" in err_type.lower() or "invalid arguments" in err_msg or "schema" in err_msg:
                    validation_failures += 1

            # 4. Final Answer & Verification
            elif ev_type == EVENT_FINAL_ANSWER_PROPOSED:
                final_answer_attempts += 1
                final_answer_produced = True

            elif ev_type == EVENT_VERIFICATION_COMPLETED:
                v_stat = ev.get("status")
                # Also check output_summary
                out_summary = ev.get("output_summary") or ""
                if v_stat in ("verified", "failed", "unverified", "not_applicable"):
                    verification_status = v_stat
                elif "verified" in out_summary.lower():
                    verification_status = "verified"
                elif "failed" in out_summary.lower():
                    verification_status = "failed"
                else:
                    verification_status = "unverified"

                if evidence_required is True:
                    evidence_policy_satisfied = (verification_status == "verified")

            # 5. Terminal status
            elif ev_type == EVENT_STEP_LIMIT_REACHED:
                step_limit_reached = True
                terminal_status = "step_limit_reached"

            elif ev_type == EVENT_TASK_COMPLETED:
                terminal_status = "completed"
                final_answer_produced = True

            elif ev_type == EVENT_TASK_FAILED:
                err_type = ev.get("error_type") or ""
                if "timeout" in err_type.lower():
                    terminal_status = "timeout"
                elif "steplimit" in err_type.lower():
                    terminal_status = "step_limit_reached"
                    step_limit_reached = True
                else:
                    terminal_status = "failed"

        # Unique tools used
        unique_tools = len(set(tool_names_sequence))

        # Repetition ratio
        if total_tool_calls > 0:
            unique_sigs = len(set(tool_call_signatures))
            rep_ratio = round(1.0 - (unique_sigs / total_tool_calls), 4)
        else:
            rep_ratio = 0.0

        # Persistent tool failures
        persistent_tool_failures = sum(1 for cnt in tool_failure_counts.values() if cnt >= 2)

        # Step count
        max_step_index = max((e.get("step_index", 0) for e in parsed_events), default=0)
        total_steps = max_step_index + 1

        # Check if step limit was hit based on configured limit
        if configured_step_limit and total_steps >= configured_step_limit and terminal_status != "completed":
            step_limit_reached = True
            if not terminal_status:
                terminal_status = "step_limit_reached"

        # Stalled progress: 3+ consecutive empty/stale observations or repeating signatures
        observable_progress_stalled = (max_consecutive_ident >= 3) or (max_consecutive_empty >= 3)

        mean_dur = round(sum(durations) / len(durations), 2) if durations else 0.0
        total_dur = round(sum(durations), 2)

        return TrajectoryFeatures(
            total_steps=total_steps,
            total_tool_calls=total_tool_calls,
            unique_tools_used=unique_tools,
            tool_call_repetition_ratio=rep_ratio,
            distinct_argument_patterns=len(distinct_arg_set),
            max_consecutive_identical_tool_calls=max_consecutive_ident,
            tool_execution_failures=tool_exec_failures,
            persistent_tool_failures=persistent_tool_failures,
            validation_failures=validation_failures,
            empty_tool_results=empty_tool_results,
            successful_tool_results=successful_tool_results,
            final_answer_attempts=final_answer_attempts,
            step_limit_reached=step_limit_reached,
            final_answer_produced=final_answer_produced,
            terminal_status=terminal_status or "completed",
            verification_status=verification_status,
            evidence_retrieval_occurred=evidence_retrieval_occurred,
            evidence_policy_satisfied=evidence_policy_satisfied,
            mean_step_duration_ms=mean_dur,
            total_duration_ms=total_dur,
            observable_progress_stalled=observable_progress_stalled,
            tool_names_sequence=tool_names_sequence,
        )
