import React, { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { TraceEvent } from "../types/api";
import { StatusBadge } from "../components/common/StatusBadge";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { EmptyState } from "../components/common/EmptyState";
import {
  GitCommitVertical,
  Search,
  Filter,
  Download,
  ChevronRight,
  Copy,
  Check,
} from "lucide-react";

export const TracesPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlTaskId = searchParams.get("taskId") || "";

  const [taskIdInput, setTaskIdInput] = useState<string>(urlTaskId);
  const [currentTaskId, setCurrentTaskId] = useState<string>(urlTaskId);
  const [traces, setTraces] = useState<TraceEvent[]>([]);
  const [recentTasks, setRecentTasks] = useState<Array<{
    task_id: string;
    run_id: string;
    benchmark_task_id?: string;
    display_label: string;
    status: string;
  }>>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedEventType, setSelectedEventType] = useState<string>("all");
  const [selectedTool, setSelectedTool] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [recoveryOnly, setRecoveryOnly] = useState<boolean>(false);

  // Selected event for detail side panel
  const [selectedEvent, setSelectedEvent] = useState<TraceEvent | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  const loadTraces = async (id: string) => {
    if (!id.trim()) return;
    setLoading(true);
    setError(null);
    setSelectedEvent(null);
    try {
      const events = await api.getTaskTraces(id.trim());
      setTraces(events);
      if (events.length > 0) {
        setSelectedEvent(events[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load traces");
    } finally {
      setLoading(false);
    }
  };

  // Load recent tasks list on mount
  useEffect(() => {
    const fetchRecent = async () => {
      try {
        const list = await api.getRecentTasks(30);
        setRecentTasks(list);
        if (!urlTaskId && list.length > 0) {
          const defaultTarget = list[0].benchmark_task_id || list[0].task_id;
          setTaskIdInput(defaultTarget);
          setCurrentTaskId(defaultTarget);
          loadTraces(defaultTarget);
        }
      } catch (err) {
        console.error("Could not fetch recent tasks:", err);
      }
    };
    fetchRecent();
  }, []);

  useEffect(() => {
    if (urlTaskId) {
      setTaskIdInput(urlTaskId);
      setCurrentTaskId(urlTaskId);
      loadTraces(urlTaskId);
    }
  }, [urlTaskId]);

  const handleSelectRecentTask = (targetId: string) => {
    if (!targetId) return;
    setTaskIdInput(targetId);
    setCurrentTaskId(targetId);
    setSearchParams({ taskId: targetId });
    loadTraces(targetId);
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (taskIdInput.trim()) {
      setSearchParams({ taskId: taskIdInput.trim() });
      setCurrentTaskId(taskIdInput.trim());
      loadTraces(taskIdInput.trim());
    }
  };

  // Unique tools and event types for filter options
  const uniqueEventTypes = useMemo(() => {
    return Array.from(new Set(traces.map((t) => t.event_type))).filter(Boolean);
  }, [traces]);

  const uniqueTools = useMemo(() => {
    return Array.from(new Set(traces.map((t) => t.tool_name).filter(Boolean))) as string[];
  }, [traces]);

  // Filtered trace list
  const filteredTraces = useMemo(() => {
    return traces.filter((event) => {
      const matchType = selectedEventType === "all" || event.event_type === selectedEventType;
      const matchTool = selectedTool === "all" || event.tool_name === selectedTool;
      const matchStatus = statusFilter === "all" || event.status === statusFilter;
      const isRecovery =
        Boolean(event.recovery_attempt_id) ||
        Boolean(event.policy_id) ||
        event.event_type.includes("recovery");
      const matchRecovery = !recoveryOnly || isRecovery;
      return matchType && matchTool && matchStatus && matchRecovery;
    });
  }, [traces, selectedEventType, selectedTool, statusFilter, recoveryOnly]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header and Search Form */}
      <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Execution Trace Explorer</h2>
          <p className="text-xs text-slate-500">
            Chronological observable execution timeline with state, input/output summaries, and recovery records.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
          {recentTasks.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-2xs font-semibold text-slate-500 uppercase shrink-0">Recent:</span>
              <select
                value={recentTasks.some(r => (r.benchmark_task_id || r.task_id) === currentTaskId) ? currentTaskId : ""}
                onChange={(e) => handleSelectRecentTask(e.target.value)}
                className="text-xs border border-slate-200 rounded px-2.5 py-2 bg-white font-mono text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500 max-w-[220px] truncate"
              >
                <option value="" disabled>Select Recent Task...</option>
                {recentTasks.map((t) => {
                  const val = t.benchmark_task_id || t.task_id;
                  return (
                    <option key={t.task_id} value={val}>
                      {t.display_label} - {t.status}
                    </option>
                  );
                })}
              </select>
            </div>
          )}

          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
            <div className="relative min-w-[220px]">
              <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Task ID (e.g. ARITH-001)..."
                value={taskIdInput}
                onChange={(e) => setTaskIdInput(e.target.value)}
                className="w-full pl-9 pr-3 py-2 text-xs rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
              />
            </div>
            <button
              type="submit"
              className="px-3.5 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded transition-colors shadow-2xs shrink-0"
            >
              Load
            </button>
          </form>
        </div>
      </div>

      {loading && <LoadingSpinner message={`Loading execution trace for task '${currentTaskId}'...`} />}

      {error && (
        <ErrorMessage
          title="Could not load execution trace"
          message={error}
          onRetry={() => loadTraces(currentTaskId)}
        />
      )}

      {!loading && !error && traces.length === 0 && (
        <EmptyState
          title="No Execution Trace Loaded"
          description="Enter a valid Task ID from your experiment results or select one from the Experiments page to inspect its step-by-step observable trajectory."
          icon={<GitCommitVertical className="w-8 h-8 text-indigo-500" />}
        />
      )}

      {!loading && traces.length > 0 && (
        <div className="space-y-4">
          {/* Controls & Export Header */}
          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="font-bold text-slate-900 text-sm">{currentTaskId}</span>
              <span className="text-slate-500 font-sans">
                {traces.length} Total Events | Showing {filteredTraces.length}
              </span>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              {/* Event Type Filter */}
              <div className="flex items-center gap-1.5 text-xs text-slate-600">
                <Filter className="w-3.5 h-3.5 text-slate-400" />
                <span>Type:</span>
                <select
                  value={selectedEventType}
                  onChange={(e) => setSelectedEventType(e.target.value)}
                  className="text-xs border border-slate-200 rounded px-2 py-1 bg-white"
                >
                  <option value="all">All Events</option>
                  {uniqueEventTypes.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              {/* Tool Filter */}
              {uniqueTools.length > 0 && (
                <div className="flex items-center gap-1.5 text-xs text-slate-600">
                  <span>Tool:</span>
                  <select
                    value={selectedTool}
                    onChange={(e) => setSelectedTool(e.target.value)}
                    className="text-xs border border-slate-200 rounded px-2 py-1 bg-white font-mono"
                  >
                    <option value="all">All Tools</option>
                    {uniqueTools.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Status Filter */}
              <div className="flex items-center gap-1.5 text-xs text-slate-600">
                <span>Status:</span>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="text-xs border border-slate-200 rounded px-2 py-1 bg-white font-mono"
                >
                  <option value="all">All Statuses</option>
                  <option value="success">Success</option>
                  <option value="failed">Failed / Error</option>
                  <option value="running">Running</option>
                </select>
              </div>

              {/* Recovery Only Checkbox */}
              <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={recoveryOnly}
                  onChange={(e) => setRecoveryOnly(e.target.checked)}
                  className="rounded border-slate-300 text-indigo-600 h-3.5 w-3.5"
                />
                <span>Recovery Events Only</span>
              </label>

              {/* Export JSONL Button */}
              <a
                href={api.getTaskTraceExportUrl(currentTaskId)}
                download={`${currentTaskId}_trace.jsonl`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded border border-slate-200 transition-colors"
              >
                <Download className="w-3.5 h-3.5" /> Export JSONL
              </a>
            </div>
          </div>

          {/* Timeline and Details Side Panel Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Chronological Timeline List */}
            <div className="lg:col-span-7 space-y-2 max-h-[750px] overflow-y-auto pr-1">
              {filteredTraces.map((event, idx) => {
                const isSelected = selectedEvent === event;
                const isRecovery =
                  Boolean(event.recovery_attempt_id) ||
                  Boolean(event.policy_id) ||
                  event.event_type.includes("recovery");
                const isError =
                  event.status === "failed" ||
                  event.status === "error" ||
                  Boolean(event.error_type);

                return (
                  <div
                    key={`${event.step_index}-${idx}`}
                    onClick={() => setSelectedEvent(event)}
                    className={`p-4 rounded-lg border transition-all cursor-pointer relative ${
                      isSelected
                        ? "border-indigo-600 bg-indigo-50/70 shadow-xs ring-1 ring-indigo-600"
                        : isRecovery
                        ? "border-emerald-200 bg-emerald-50/30 hover:bg-emerald-50/60"
                        : isError
                        ? "border-rose-200 bg-rose-50/40 hover:bg-rose-50/70"
                        : "border-slate-200 bg-white hover:bg-slate-50"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="w-6 h-6 rounded-full bg-slate-900 text-white text-2xs font-bold font-mono flex items-center justify-center shrink-0">
                          {event.step_index}
                        </span>
                        <span className="text-xs font-bold font-mono text-slate-900">
                          {event.event_type}
                        </span>
                        {event.tool_name && (
                          <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-2xs font-mono font-medium border border-slate-200">
                            tool: {event.tool_name}
                          </span>
                        )}
                        {isRecovery && (
                          <span className="px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 text-2xs font-mono font-bold border border-emerald-300">
                            RECOVERY
                          </span>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <StatusBadge status={event.status} size="sm" />
                        <ChevronRight className="w-4 h-4 text-slate-300" />
                      </div>
                    </div>

                    {/* Summary snippets */}
                    <div className="mt-2 text-xs font-sans text-slate-600 space-y-1">
                      {event.input_summary && (
                        <p className="line-clamp-2">
                          <span className="font-semibold text-slate-500 font-mono text-2xs uppercase">Input:</span>{" "}
                          {event.input_summary}
                        </p>
                      )}
                      {event.output_summary && (
                        <p className="line-clamp-2 text-slate-700">
                          <span className="font-semibold text-slate-500 font-mono text-2xs uppercase">Output:</span>{" "}
                          {event.output_summary}
                        </p>
                      )}
                      {event.error_type && (
                        <p className="text-rose-700 font-mono text-2xs font-semibold">
                          Error: {event.error_type}
                        </p>
                      )}
                    </div>

                    {/* Timestamp & Duration footer */}
                    <div className="mt-2 flex items-center gap-3 text-2xs text-slate-400 font-mono">
                      <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
                      {event.duration_ms !== null && event.duration_ms !== undefined && (
                        <span>• {event.duration_ms.toFixed(1)}ms</span>
                      )}
                      {event.policy_id && (
                        <span className="text-indigo-600 font-semibold">• Policy: {event.policy_id}</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Event Detail Side Panel */}
            <div className="lg:col-span-5">
              {selectedEvent ? (
                <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden sticky top-6">
                  <div className="px-5 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs uppercase font-semibold text-slate-500">
                          Step #{selectedEvent.step_index} Details
                        </span>
                        <StatusBadge status={selectedEvent.status} size="sm" />
                      </div>
                      <h4 className="text-sm font-bold text-slate-900 font-mono mt-0.5">
                        {selectedEvent.event_type}
                      </h4>
                    </div>
                    <button
                      onClick={() => copyToClipboard(JSON.stringify(selectedEvent, null, 2))}
                      className="p-1.5 text-slate-400 hover:text-slate-600 rounded hover:bg-slate-200 transition-colors"
                      title="Copy JSON"
                    >
                      {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                    </button>
                  </div>

                  <div className="p-5 space-y-4 max-h-[600px] overflow-y-auto text-xs">
                    {/* Tool & Timing */}
                    <div className="grid grid-cols-2 gap-3 p-3 bg-slate-50 rounded border border-slate-200 font-mono text-2xs">
                      <div>
                        <span className="text-slate-400 block">Tool Name</span>
                        <span className="font-bold text-slate-800">
                          {selectedEvent.tool_name || "None (Agent internal)"}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Duration</span>
                        <span className="font-bold text-slate-800">
                          {selectedEvent.duration_ms !== null && selectedEvent.duration_ms !== undefined
                            ? `${selectedEvent.duration_ms.toFixed(2)} ms`
                            : "N/A"}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Timestamp</span>
                        <span className="text-slate-700">
                          {new Date(selectedEvent.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Run ID</span>
                        <span className="text-slate-700 truncate block">
                          {selectedEvent.run_id}
                        </span>
                      </div>
                    </div>

                    {/* Input Summary */}
                    {selectedEvent.input_summary && (
                      <div>
                        <h5 className="font-semibold text-slate-700 uppercase tracking-wider text-2xs mb-1">
                          Input Summary / Arguments
                        </h5>
                        <pre className="p-3 bg-slate-900 text-slate-200 rounded font-mono text-2xs whitespace-pre-wrap overflow-x-auto">
                          {selectedEvent.input_summary}
                        </pre>
                      </div>
                    )}

                    {/* Output Summary */}
                    {selectedEvent.output_summary && (
                      <div>
                        <h5 className="font-semibold text-slate-700 uppercase tracking-wider text-2xs mb-1">
                          Output / Execution Result
                        </h5>
                        <pre className="p-3 bg-slate-900 text-emerald-300 rounded font-mono text-2xs whitespace-pre-wrap overflow-x-auto">
                          {selectedEvent.output_summary}
                        </pre>
                      </div>
                    )}

                    {/* Error Details */}
                    {selectedEvent.error_type && (
                      <div className="p-3 bg-rose-50 border border-rose-200 rounded text-rose-800">
                        <span className="font-bold uppercase text-2xs block">Observed Error</span>
                        <p className="font-mono text-xs mt-1">{selectedEvent.error_type}</p>
                      </div>
                    )}

                    {/* Recovery Annotations */}
                    {(selectedEvent.policy_id || selectedEvent.recovery_attempt_id) && (
                      <div className="p-3 bg-indigo-50 border border-indigo-200 rounded space-y-1.5 font-mono text-2xs">
                        <span className="font-bold text-indigo-900 uppercase block">
                          Recovery Intervention Metadata
                        </span>
                        {selectedEvent.policy_id && (
                          <p>
                            <span className="text-slate-500">Policy:</span> {selectedEvent.policy_id}
                          </p>
                        )}
                        {selectedEvent.action_type && (
                          <p>
                            <span className="text-slate-500">Action Type:</span> {selectedEvent.action_type}
                          </p>
                        )}
                        {selectedEvent.recovery_attempt_id && (
                          <p>
                            <span className="text-slate-500">Attempt ID:</span> {selectedEvent.recovery_attempt_id}
                          </p>
                        )}
                        {selectedEvent.finding_ids && selectedEvent.finding_ids.length > 0 && (
                          <p>
                            <span className="text-slate-500">Diagnostic Findings:</span>{" "}
                            {selectedEvent.finding_ids.join(", ")}
                          </p>
                        )}
                      </div>
                    )}

                    {/* Token Consumption */}
                    {selectedEvent.model_tokens && (
                      <div className="p-3 bg-slate-50 border border-slate-200 rounded font-mono text-2xs">
                        <span className="font-bold text-slate-700 uppercase block mb-1">
                          Model Token Usage
                        </span>
                        <div className="flex gap-4 text-slate-600">
                          <span>Prompt: {selectedEvent.model_tokens.prompt_tokens || 0}</span>
                          <span>Completion: {selectedEvent.model_tokens.completion_tokens || 0}</span>
                          <span className="font-bold text-slate-900">
                            Total: {selectedEvent.model_tokens.total_tokens || 0}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="p-8 text-center bg-white rounded-lg border border-slate-200 text-slate-400 text-xs">
                  Click on an execution step in the timeline to view structured event inputs and outputs.
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
