import React, { useEffect, useState, useMemo } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { api } from "../api/client";
import type { ExperimentSummary, TaskExecutionResult } from "../types/api";
import { StatusBadge } from "../components/common/StatusBadge";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  Search,
  Filter,
  PlayCircle,
  ChevronRight,
  Download,
  FileText,
  ShieldAlert,
  GitCommitVertical,
} from "lucide-react";

export const ExperimentsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [searchTerm, setSearchTerm] = useState<string>(searchParams.get("search") || "");
  const [modeFilter, setModeFilter] = useState<string>(searchParams.get("mode") || "all");
  const [statusFilter, setStatusFilter] = useState<string>(searchParams.get("status") || "all");

  // Selected Experiment Detail
  const selectedExpId = searchParams.get("id");
  const [selectedExp, setSelectedExp] = useState<ExperimentSummary | null>(null);
  const [results, setResults] = useState<TaskExecutionResult[]>([]);
  const [loadingResults, setLoadingResults] = useState<boolean>(false);
  const [resultsError, setResultsError] = useState<string | null>(null);

  const fetchExperiments = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getExperiments({ limit: 100 });
      setExperiments(data);
      if (selectedExpId) {
        const found = data.find((e) => e.experiment_id === selectedExpId);
        if (found) {
          setSelectedExp(found);
        } else {
          // Try fetching by ID
          const single = await api.getExperiment(selectedExpId);
          setSelectedExp(single);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load experiments");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchExperiments();
  }, []);

  // Fetch results when an experiment is selected
  useEffect(() => {
    if (!selectedExpId) {
      setSelectedExp(null);
      setResults([]);
      return;
    }
    const loadResults = async () => {
      setLoadingResults(true);
      setResultsError(null);
      try {
        const expData = experiments.find((e) => e.experiment_id === selectedExpId);
        if (expData) {
          setSelectedExp(expData);
        } else {
          const single = await api.getExperiment(selectedExpId);
          setSelectedExp(single);
        }
        const taskResults = await api.getExperimentResults(selectedExpId, { limit: 200 });
        setResults(taskResults);
      } catch (err) {
        setResultsError(err instanceof Error ? err.message : "Failed to load experiment results");
      } finally {
        setLoadingResults(false);
      }
    };
    loadResults();
  }, [selectedExpId, experiments]);

  const filteredExperiments = useMemo(() => {
    return experiments.filter((exp) => {
      const matchesSearch =
        searchTerm === "" ||
        exp.experiment_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        exp.agent_mode.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesMode = modeFilter === "all" || exp.agent_mode === modeFilter;
      const matchesStatus = statusFilter === "all" || exp.status === statusFilter;
      return matchesSearch && matchesMode && matchesStatus;
    });
  }, [experiments, searchTerm, modeFilter, statusFilter]);

  const selectExperiment = (id: string) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("id", id);
      return next;
    });
  };

  const clearSelection = () => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("id");
      return next;
    });
  };

  if (loading) {
    return <LoadingSpinner message="Fetching experiment registry from backend..." />;
  }

  if (error) {
    return (
      <ErrorMessage
        title="Could not load experiments"
        message={error}
        onRetry={fetchExperiments}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Experiment Registry</h2>
          <p className="text-xs text-slate-500">
            {experiments.length} persisted benchmark evaluation runs recorded in SQLite
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/run-experiment"
            className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-white bg-slate-900 hover:bg-slate-800 rounded-md shadow-xs transition-colors"
          >
            <PlayCircle className="w-4 h-4" />
            Launch Experiment
          </Link>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1 min-w-[260px]">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by experiment ID or mode..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 text-xs rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
            />
          </div>
          {searchTerm && (
            <button
              onClick={() => setSearchTerm("")}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              Clear
            </button>
          )}
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 text-xs text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>Mode:</span>
            <select
              value={modeFilter}
              onChange={(e) => setModeFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded px-2.5 py-1 bg-white focus:outline-none"
            >
              <option value="all">All Modes</option>
              <option value="baseline">Baseline</option>
              <option value="fixed_retry">Fixed Retry</option>
              <option value="traceguard">TraceGuard (Detector)</option>
              <option value="traceguard_recovery">TraceGuard Recovery</option>
            </select>
          </div>

          <div className="flex items-center gap-2 text-xs text-slate-600">
            <span>Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded px-2.5 py-1 bg-white focus:outline-none"
            >
              <option value="all">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="running">Running</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Content Layout: Table or Split View */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Experiments Table (collapses to 5 cols if an experiment is selected) */}
        <div className={selectedExpId ? "lg:col-span-5" : "lg:col-span-12"}>
          <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
            <div className="px-5 py-3.5 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-wider">
                Evaluation Runs ({filteredExperiments.length})
              </h3>
              {selectedExpId && (
                <button
                  onClick={clearSelection}
                  className="text-2xs text-indigo-600 hover:text-indigo-800 font-semibold"
                >
                  Deselect
                </button>
              )}
            </div>

            {filteredExperiments.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No experiments match the filter criteria.
              </div>
            ) : (
              <div className="divide-y divide-slate-100 max-h-[700px] overflow-y-auto font-mono text-xs">
                {filteredExperiments.map((exp) => {
                  const isSelected = exp.experiment_id === selectedExpId;
                  return (
                    <div
                      key={exp.experiment_id}
                      onClick={() => selectExperiment(exp.experiment_id)}
                      className={`p-4 cursor-pointer transition-colors flex items-center justify-between ${
                        isSelected
                          ? "bg-indigo-50/80 border-l-4 border-indigo-600"
                          : "hover:bg-slate-50"
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-slate-900">
                            {exp.experiment_id}
                          </span>
                          <StatusBadge status={exp.status} size="sm" />
                        </div>
                        <div className="flex items-center gap-3 text-slate-500 font-sans text-2xs">
                          <span className="capitalize font-mono text-slate-700 font-medium">
                            {exp.agent_mode.replace(/_/g, " ")}
                          </span>
                          <span>•</span>
                          <span>{exp.benchmark_version}</span>
                          <span>•</span>
                          <span>{exp.completed_tasks}/{exp.total_tasks} tasks</span>
                        </div>
                        <div className="text-slate-400 font-sans text-2xs">
                          {new Date(exp.created_at).toLocaleString()}
                        </div>
                      </div>
                      <ChevronRight
                        className={`w-4 h-4 ${
                          isSelected ? "text-indigo-600" : "text-slate-300"
                        }`}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Selected Experiment Results Panel */}
        {selectedExpId && (
          <div className="lg:col-span-7 space-y-4">
            {loadingResults ? (
              <div className="bg-white rounded-lg border border-slate-200 p-8">
                <LoadingSpinner message={`Loading task results for ${selectedExpId}...`} />
              </div>
            ) : resultsError ? (
              <ErrorMessage
                title="Error Loading Results"
                message={resultsError}
                onRetry={() => selectExperiment(selectedExpId)}
              />
            ) : selectedExp ? (
              <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
                {/* Experiment Summary Banner */}
                <div className="p-5 border-b border-slate-200 bg-slate-50">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs uppercase font-semibold text-slate-500 font-sans">
                          Experiment Detail
                        </span>
                        <StatusBadge status={selectedExp.status} size="sm" />
                      </div>
                      <h3 className="text-base font-bold text-slate-900 font-mono mt-1">
                        {selectedExp.experiment_id}
                      </h3>
                      <p className="text-xs text-slate-600 mt-1 font-sans">
                        Mode: <span className="font-semibold">{selectedExp.agent_mode}</span> | Benchmark: <span className="font-semibold">{selectedExp.benchmark_version}</span> | Tasks: <span className="font-semibold">{selectedExp.completed_tasks} / {selectedExp.total_tasks}</span>
                      </p>
                    </div>

                    {/* Quick Action Buttons */}
                    <div className="flex items-center gap-2">
                      <a
                        href={api.getExperimentExportUrl(selectedExp.experiment_id, "json")}
                        download={`${selectedExp.experiment_id}.json`}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors shadow-2xs"
                        title="Download raw JSON"
                      >
                        <Download className="w-3.5 h-3.5 text-slate-500" /> JSON
                      </a>
                      <Link
                        to={`/reports?id=${selectedExp.experiment_id}`}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded transition-colors shadow-2xs"
                        title="View Research Report"
                      >
                        <FileText className="w-3.5 h-3.5" /> Report
                      </Link>
                    </div>
                  </div>
                </div>

                {/* Task Execution Results Table */}
                <div className="p-4 border-b border-slate-200 bg-white">
                  <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-700 font-sans">
                    Evaluated Tasks ({results.length})
                  </h4>
                </div>

                <div className="overflow-x-auto max-h-[550px] overflow-y-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-50 text-2xs uppercase text-slate-500 border-b border-slate-200 font-sans sticky top-0">
                      <tr>
                        <th className="px-4 py-2.5">Task ID</th>
                        <th className="px-4 py-2.5">Terminal Status</th>
                        <th className="px-4 py-2.5">Verification</th>
                        <th className="px-4 py-2.5">Steps</th>
                        <th className="px-4 py-2.5">Tools</th>
                        <th className="px-4 py-2.5">Duration</th>
                        <th className="px-4 py-2.5 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {results.map((r) => (
                        <tr key={r.task_id} className="hover:bg-slate-50/80">
                          <td className="px-4 py-3 font-semibold text-slate-900">
                            {r.task_id}
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge status={r.terminal_status} size="sm" />
                          </td>
                          <td className="px-4 py-3">
                            <StatusBadge status={r.verification_status} size="sm" />
                          </td>
                          <td className="px-4 py-3 font-sans">
                            {r.step_count}
                          </td>
                          <td className="px-4 py-3 font-sans">
                            {r.tool_call_count} {r.tool_error_count > 0 && <span className="text-rose-600 font-semibold font-mono">({r.tool_error_count} err)</span>}
                          </td>
                          <td className="px-4 py-3 text-slate-500 font-sans">
                            {(r.total_duration_ms / 1000).toFixed(2)}s
                          </td>
                          <td className="px-4 py-3 text-right space-x-2 font-sans">
                            <Link
                              to={`/traces?taskId=${r.task_id}`}
                              className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-0.5"
                              title="Inspect Trace Events"
                            >
                              <GitCommitVertical className="w-3.5 h-3.5" /> Trace
                            </Link>
                            <Link
                              to={`/diagnostics?taskId=${r.task_id}`}
                              className="text-slate-600 hover:text-slate-900 font-medium inline-flex items-center gap-0.5"
                              title="Inspect Diagnostics"
                            >
                              <ShieldAlert className="w-3.5 h-3.5" /> Diag
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};
