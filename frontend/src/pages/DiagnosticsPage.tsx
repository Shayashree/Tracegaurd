import React, { useEffect, useState, useMemo } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { api } from "../api/client";
import type { DiagnosticReport, DiagnosticFinding, DetectorMetrics } from "../types/api";
import { StatusBadge } from "../components/common/StatusBadge";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { EmptyState } from "../components/common/EmptyState";
import {
  ShieldAlert,
  Search,
  Filter,
  FileSearch,
  ChevronRight,
  Target,
} from "lucide-react";

export const DiagnosticsPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const urlTaskId = searchParams.get("taskId") || "";
  const urlExpId = searchParams.get("experimentId") || "";

  const [reports, setReports] = useState<DiagnosticReport[]>([]);
  const [detectorMetrics, setDetectorMetrics] = useState<DetectorMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [confirmationFilter, setConfirmationFilter] = useState<string>("all");
  const [searchTask, setSearchTask] = useState<string>(urlTaskId);

  // Selected report for side panel
  const [selectedReport, setSelectedReport] = useState<DiagnosticReport | null>(null);

  const fetchDiagnostics = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getDiagnostics({ limit: 100 });
      setReports(data);
      if (data.length > 0) {
        setSelectedReport(data[0]);
      }

      // If we have an experiment ID, load detector metrics for it
      const expIdToQuery = urlExpId || (data.length > 0 && data[0].experiment_id ? data[0].experiment_id : "");
      if (expIdToQuery) {
        try {
          const metrics = await api.getExperimentDetectorMetrics(expIdToQuery);
          setDetectorMetrics(metrics);
        } catch {
          // Detector metrics might not exist for non-benchmark runs
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load diagnostic reports");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDiagnostics();
  }, []);

  // Filtered reports
  const filteredReports = useMemo(() => {
    return reports.filter((r) => {
      const matchTask =
        searchTask === "" ||
        r.task_id.toLowerCase().includes(searchTask.toLowerCase()) ||
        r.run_id.toLowerCase().includes(searchTask.toLowerCase());
      const matchCat =
        categoryFilter === "all" ||
        r.primary_failure_category === categoryFilter ||
        r.findings.some((f) => f.failure_category === categoryFilter);
      const matchSev = severityFilter === "all" || r.severity === severityFilter;
      const matchConf = confirmationFilter === "all" || r.confirmation_status === confirmationFilter;
      return matchTask && matchCat && matchSev && matchConf;
    });
  }, [reports, searchTask, categoryFilter, severityFilter, confirmationFilter]);

  // Aggregate all findings
  const allFindings = useMemo(() => {
    const list: Array<{ report: DiagnosticReport; finding: DiagnosticFinding }> = [];
    filteredReports.forEach((r) => {
      r.findings.forEach((f) => {
        list.push({ report: r, finding: f });
      });
    });
    return list;
  }, [filteredReports]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Failure Diagnostics Explorer</h2>
          <p className="text-xs text-slate-500">
            Explainable trajectory-based diagnosis across failure categories (F1–F9) backed by deterministic proof or heuristics.
          </p>
        </div>
      </div>

      {/* Detector Ground-Truth Performance Metrics (When available) */}
      {detectorMetrics && (
        <div className="bg-slate-900 text-white rounded-lg p-5 shadow-xs">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-4">
            <div className="flex items-center gap-2">
              <Target className="w-4 h-4 text-indigo-400" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Ground-Truth Detector Evaluation Metrics ({detectorMetrics.detector_version})
              </h3>
            </div>
            <span className="text-2xs font-mono text-slate-400">
              Evaluated on {detectorMetrics.total_evaluated} benchmark runs
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <div className="bg-slate-800/80 p-3 rounded">
              <span className="text-2xs text-slate-400 uppercase block">Precision</span>
              <span className="text-xl font-bold font-mono text-white">
                {(detectorMetrics.precision * 100).toFixed(1)}%
              </span>
            </div>
            <div className="bg-slate-800/80 p-3 rounded">
              <span className="text-2xs text-slate-400 uppercase block">Recall</span>
              <span className="text-xl font-bold font-mono text-white">
                {(detectorMetrics.recall * 100).toFixed(1)}%
              </span>
            </div>
            <div className="bg-slate-800/80 p-3 rounded">
              <span className="text-2xs text-slate-400 uppercase block">F1 Score</span>
              <span className="text-xl font-bold font-mono text-indigo-300">
                {(detectorMetrics.f1_score * 100).toFixed(1)}%
              </span>
            </div>
            <div className="bg-slate-800/80 p-3 rounded">
              <span className="text-2xs text-slate-400 uppercase block">False Positive Rate</span>
              <span className="text-xl font-bold font-mono text-amber-300">
                {(detectorMetrics.false_positive_rate * 100).toFixed(1)}%
              </span>
            </div>
            <div className="bg-slate-800/80 p-3 rounded">
              <span className="text-2xs text-slate-400 uppercase block">Coverage</span>
              <span className="text-xl font-bold font-mono text-emerald-300">
                {(detectorMetrics.coverage_rate * 100).toFixed(1)}%
              </span>
            </div>
            <div className="bg-slate-800/80 p-3 rounded">
              <span className="text-2xs text-slate-400 uppercase block">Mean Detection Latency</span>
              <span className="text-xl font-bold font-mono text-white">
                {detectorMetrics.mean_detection_latency_ms.toFixed(1)}ms
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1 min-w-[260px]">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by Task ID or Run ID..."
              value={searchTask}
              onChange={(e) => setSearchTask(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 text-xs rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
            />
          </div>
          {searchTask && (
            <button
              onClick={() => setSearchTask("")}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              Clear
            </button>
          )}
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Category Filter */}
          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>Taxonomy:</span>
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded px-2.5 py-1 bg-white focus:outline-none"
            >
              <option value="all">All Categories (F1–F9)</option>
              <option value="repeated_tool_calls">F1: Repeated tool calls</option>
              <option value="invalid_tool_arguments">F2: Invalid tool arguments</option>
              <option value="tool_execution_failure">F3: Tool execution failure</option>
              <option value="lack_of_progress">F4: Lack of progress</option>
              <option value="missing_evidence">F5: Missing evidence</option>
              <option value="incorrect_final_answer">F6: Incorrect final answer</option>
              <option value="step_limit_exhaustion">F7: Step-limit exhaustion</option>
              <option value="invalid_model_output">F8: Invalid model output</option>
              <option value="unverified_completion">F9: Unverified completion</option>
            </select>
          </div>

          {/* Severity Filter */}
          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <span>Severity:</span>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded px-2.5 py-1 bg-white focus:outline-none"
            >
              <option value="all">All Severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
              <option value="info">Info</option>
            </select>
          </div>

          {/* Confirmation Filter */}
          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <span>Certainty:</span>
            <select
              value={confirmationFilter}
              onChange={(e) => setConfirmationFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded px-2.5 py-1 bg-white focus:outline-none"
            >
              <option value="all">All Certainties</option>
              <option value="confirmed">Confirmed (Deterministic)</option>
              <option value="suspected">Suspected (Heuristic)</option>
              <option value="unverified">Unverified</option>
            </select>
          </div>
        </div>
      </div>

      {loading && <LoadingSpinner message="Loading failure findings and diagnostic reports..." />}

      {error && (
        <ErrorMessage
          title="Could not load diagnostics"
          message={error}
          onRetry={fetchDiagnostics}
        />
      )}

      {!loading && reports.length === 0 && (
        <EmptyState
          title="No Diagnostic Reports Available"
          description="Run an evaluation experiment or task under TraceGuard mode to produce trajectory diagnostic findings."
          icon={<ShieldAlert className="w-8 h-8 text-indigo-500" />}
        />
      )}

      {!loading && reports.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Diagnostic Reports & Findings List */}
          <div className="lg:col-span-7 space-y-3 max-h-[750px] overflow-y-auto pr-1">
            <div className="flex items-center justify-between text-xs text-slate-500 px-1">
              <span>Showing {filteredReports.length} reports ({allFindings.length} individual findings)</span>
            </div>

            {filteredReports.map((report) => {
              const isSelected = selectedReport?.diagnostic_id === report.diagnostic_id;
              const hasFailure = report.diagnostic_status === "failure_detected";

              return (
                <div
                  key={report.diagnostic_id}
                  onClick={() => setSelectedReport(report)}
                  className={`p-4 rounded-lg border transition-all cursor-pointer ${
                    isSelected
                      ? "border-indigo-600 bg-indigo-50/70 shadow-xs ring-1 ring-indigo-600"
                      : hasFailure
                      ? "border-rose-200 bg-white hover:bg-rose-50/30"
                      : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold font-mono text-xs text-slate-900">
                          {report.task_id}
                        </span>
                        <StatusBadge status={report.diagnostic_status} size="sm" />
                        <StatusBadge status={report.confirmation_status} size="sm" />
                      </div>
                      <p className="text-2xs text-slate-400 font-mono mt-0.5">
                        Run: {report.run_id} | Analysis: {report.analysis_duration_ms.toFixed(1)}ms
                      </p>
                    </div>

                    <ChevronRight
                      className={`w-4 h-4 ${isSelected ? "text-indigo-600" : "text-slate-300"}`}
                    />
                  </div>

                  {/* Findings Tags */}
                  {report.findings.length > 0 ? (
                    <div className="mt-3 space-y-2">
                      {report.findings.map((f) => (
                        <div
                          key={f.finding_id}
                          className="p-2.5 rounded bg-slate-50 border border-slate-200 text-xs"
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-bold text-slate-900 font-mono text-2xs uppercase">
                              {f.failure_category.replace(/_/g, " ")} ({f.rule_id})
                            </span>
                            <StatusBadge status={f.severity} size="sm" />
                          </div>
                          <p className="text-slate-700 text-xs leading-normal font-sans">
                            {f.explanation}
                          </p>
                          {f.evidence_event_ids.length > 0 && (
                            <div className="mt-1.5 flex items-center gap-1.5 font-mono text-2xs text-slate-500">
                              <span>Evidence Events:</span>
                              {f.evidence_event_ids.map((id) => (
                                <span
                                  key={id}
                                  className="px-1.5 py-0.5 rounded bg-slate-200 text-slate-800 font-semibold"
                                >
                                  {id}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-2xs text-slate-500 italic">
                      Trajectory examined: No failure pattern observed. Status: Healthy.
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {/* Diagnostic Details Side Panel */}
          <div className="lg:col-span-5">
            {selectedReport ? (
              <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden sticky top-6">
                <div className="p-5 border-b border-slate-200 bg-slate-50">
                  <div className="flex items-center justify-between">
                    <span className="text-2xs uppercase font-semibold text-slate-500">
                      Report #{selectedReport.diagnostic_id}
                    </span>
                    <StatusBadge status={selectedReport.diagnostic_status} size="sm" />
                  </div>
                  <h4 className="text-sm font-bold text-slate-900 font-mono mt-1">
                    Task: {selectedReport.task_id}
                  </h4>
                  <div className="flex items-center gap-3 mt-2">
                    <Link
                      to={`/traces?taskId=${selectedReport.task_id}`}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1"
                    >
                      <FileSearch className="w-3.5 h-3.5" /> Inspect Trace Events
                    </Link>
                  </div>
                </div>

                <div className="p-5 space-y-4 max-h-[600px] overflow-y-auto text-xs">
                  {/* Trajectory Feature Summary */}
                  <div>
                    <h5 className="font-semibold text-slate-700 uppercase tracking-wider text-2xs mb-2">
                      Extracted Trajectory Features
                    </h5>
                    <div className="grid grid-cols-2 gap-2 bg-slate-50 p-3 rounded border border-slate-200 font-mono text-2xs">
                      <div>
                        <span className="text-slate-400 block">Total Steps</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.features.total_steps}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Tool Calls</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.features.total_tool_calls}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Tool Failures</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.features.tool_execution_failures}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Repetition Ratio</span>
                        <span className="font-bold text-slate-800">
                          {(selectedReport.features.tool_call_repetition_ratio * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Step Limit Exhausted</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.features.step_limit_reached ? "Yes" : "No"}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Mean Step Latency</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.features.mean_step_duration_ms.toFixed(1)}ms
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Findings List */}
                  <div>
                    <h5 className="font-semibold text-slate-700 uppercase tracking-wider text-2xs mb-2">
                      Triggered Diagnostic Findings ({selectedReport.findings.length})
                    </h5>
                    {selectedReport.findings.length === 0 ? (
                      <p className="text-xs text-slate-500 italic p-3 bg-slate-50 rounded">
                        No heuristic or deterministic failure conditions triggered.
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {selectedReport.findings.map((finding) => (
                          <div
                            key={finding.finding_id}
                            className="p-3 bg-white rounded border border-slate-200 shadow-2xs space-y-1.5"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-xs font-mono text-slate-900">
                                {finding.failure_category}
                              </span>
                              <StatusBadge status={finding.confirmation_status} size="sm" />
                            </div>
                            <p className="text-slate-700 text-xs font-sans">
                              {finding.explanation}
                            </p>
                            <div className="pt-2 border-t border-slate-100 font-sans text-2xs">
                              <span className="text-slate-500 font-semibold block">
                                Recommended Action / Recovery:
                              </span>
                              <span className="text-indigo-700 font-medium">
                                {finding.recommended_next_action}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center bg-white rounded-lg border border-slate-200 text-slate-400 text-xs">
                Select a diagnostic report from the list to view trajectory features and rule explanations.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
