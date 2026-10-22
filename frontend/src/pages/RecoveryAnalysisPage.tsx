import React, { useEffect, useState, useMemo } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { RecoveryReport } from "../types/api";
import { StatusBadge } from "../components/common/StatusBadge";
import { MetricCard } from "../components/common/MetricCard";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { EmptyState } from "../components/common/EmptyState";
import {
  LifeBuoy,
  Search,
  Filter,
  ArrowRight,
  ShieldCheck,
  Clock,
  Wrench,
  ChevronDown,
  ChevronUp,
  GitCommitVertical,
} from "lucide-react";

export const RecoveryAnalysisPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const urlTaskId = searchParams.get("taskId") || "";

  const [reports, setReports] = useState<RecoveryReport[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState<string>(urlTaskId);
  const [policyFilter, setPolicyFilter] = useState<string>("all");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Selected report for side panel
  const [selectedReport, setSelectedReport] = useState<RecoveryReport | null>(null);
  const [expandedAttempts, setExpandedAttempts] = useState<Record<string, boolean>>({});

  const fetchReports = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getRecoveryReports({ limit: 100 });
      setReports(data);
      if (data.length > 0) {
        if (urlTaskId) {
          const match = data.find(
            (r) =>
              r.task_id.toLowerCase().includes(urlTaskId.toLowerCase()) ||
              r.run_id.toLowerCase().includes(urlTaskId.toLowerCase())
          );
          setSelectedReport(match || data[0]);
        } else {
          setSelectedReport(data[0]);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load recovery reports");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const toggleAttempt = (id: string) => {
    setExpandedAttempts((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  // Filtered reports
  const filteredReports = useMemo(() => {
    return reports.filter((r) => {
      const matchSearch =
        searchQuery === "" ||
        r.task_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (r.run_id && r.run_id.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (r.initial_failure_category && r.initial_failure_category.toLowerCase().includes(searchQuery.toLowerCase())) ||
        (r.selection_reason && r.selection_reason.toLowerCase().includes(searchQuery.toLowerCase())) ||
        r.policy_id.toLowerCase().includes(searchQuery.toLowerCase());
      const matchPolicy = policyFilter === "all" || r.policy_id === policyFilter;
      const matchStatus = statusFilter === "all" || r.terminal_status === statusFilter;
      return matchSearch && matchPolicy && matchStatus;
    });
  }, [reports, searchQuery, policyFilter, statusFilter]);

  // Aggregate recovery KPIs
  const totalReports = reports.length;
  const recoveredCount = reports.filter((r) => r.terminal_status === "recovered_successfully").length;
  const recoveryRate = totalReports > 0 ? ((recoveredCount / totalReports) * 100).toFixed(1) : "0.0";
  const meanRecoveryDuration =
    totalReports > 0
      ? (reports.reduce((acc, r) => acc + (r.total_recovery_duration_ms || 0), 0) / totalReports).toFixed(1)
      : "0";
  const avgAdditionalTools =
    totalReports > 0
      ? (reports.reduce((acc, r) => acc + (r.additional_tool_calls || 0), 0) / totalReports).toFixed(1)
      : "0";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">Recovery Analysis</h2>
        <p className="text-xs text-slate-500">
          Inspection of targeted failure interventions, policy execution, budget bounds, and verified post-recovery outcomes.
        </p>
      </div>

      {/* Lifecycle Flow Diagram */}
      <div className="bg-slate-900 text-white rounded-lg p-5 shadow-xs">
        <h3 className="text-2xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
          Evidence-Driven Recovery Lifecycle
        </h3>
        <div className="flex flex-wrap items-center gap-2 text-2xs font-mono font-medium">
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-slate-300">
            1. Observable Trajectory
          </span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-amber-300">
            2. Failure Diagnosis (F1–F9)
          </span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-indigo-300">
            3. Policy Selection (A–H)
          </span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-slate-300">
            4. Budget Check
          </span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-indigo-300">
            5. State Intervention
          </span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-slate-300">
            6. Re-execution
          </span>
          <ArrowRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
          <span className="px-2.5 py-1 rounded bg-slate-800 border border-slate-700 text-emerald-400">
            7. Verifier Proof
          </span>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Interventions"
          value={totalReports}
          subtext="Executed recovery attempts"
          icon={<LifeBuoy className="w-5 h-5 text-indigo-600" />}
        />
        <MetricCard
          label="Recovery Success Rate"
          value={`${recoveryRate}%`}
          subtext={`${recoveredCount} recovered successfully`}
          icon={<ShieldCheck className="w-5 h-5 text-emerald-600" />}
        />
        <MetricCard
          label="Mean Recovery Latency"
          value={`${meanRecoveryDuration} ms`}
          subtext="Intervention duration"
          icon={<Clock className="w-5 h-5" />}
        />
        <MetricCard
          label="Overhead Tool Calls"
          value={avgAdditionalTools}
          subtext="Average extra calls per recovery"
          icon={<Wrench className="w-5 h-5" />}
        />
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3 flex-1 min-w-[260px]">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by Task ID or Policy ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-1.5 text-xs rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-indigo-500 font-mono"
            />
          </div>
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              Clear
            </button>
          )}
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Policy Filter */}
          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>Policy:</span>
            <select
              value={policyFilter}
              onChange={(e) => setPolicyFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded px-2.5 py-1 bg-white focus:outline-none"
            >
              <option value="all">All Policies (A–H)</option>
              <option value="policy_a_transient_tool_failure">Policy A: Transient Tool Failure</option>
              <option value="policy_b_invalid_tool_arguments">Policy B: Invalid Tool Arguments</option>
              <option value="policy_c_repeated_actions">Policy C: Repeated Actions</option>
              <option value="policy_d_missing_evidence">Policy D: Missing Evidence</option>
              <option value="policy_e_incorrect_answer">Policy E: Incorrect Answer</option>
              <option value="policy_f_step_limit_exhaustion">Policy F: Step-Limit Exhaustion</option>
              <option value="policy_g_unverified_completion">Policy G: Unverified Completion</option>
              <option value="policy_h_malformed_output">Policy H: Malformed Output</option>
            </select>
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-1.5 text-xs text-slate-600">
            <span>Terminal Status:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-xs border border-slate-200 rounded px-2.5 py-1 bg-white focus:outline-none"
            >
              <option value="all">All Outcomes</option>
              <option value="recovered_successfully">Recovered Successfully</option>
              <option value="failed_after_recovery">Failed After Recovery</option>
              <option value="unresolved">Unresolved</option>
              <option value="budget_exhausted">Budget Exhausted</option>
            </select>
          </div>
        </div>
      </div>

      {loading && <LoadingSpinner message="Loading recovery reports and intervention trajectories..." />}

      {error && (
        <ErrorMessage
          title="Could not load recovery reports"
          message={error}
          onRetry={fetchReports}
        />
      )}

      {!loading && reports.length === 0 && (
        <EmptyState
          title="No Recovery Reports Found"
          description="Execute benchmark experiments with 'traceguard_recovery' mode enabled to observe targeted recovery interventions and post-intervention verification."
          icon={<LifeBuoy className="w-8 h-8 text-indigo-500" />}
        />
      )}

      {!loading && reports.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Recovery Reports List */}
          <div className="lg:col-span-7 space-y-3 max-h-[750px] overflow-y-auto pr-1">
            {filteredReports.map((report) => {
              const isSelected = selectedReport?.recovery_id === report.recovery_id;
              const isRecovered = report.terminal_status === "recovered_successfully";

              return (
                <div
                  key={report.recovery_id}
                  onClick={() => setSelectedReport(report)}
                  className={`p-4 rounded-lg border transition-all cursor-pointer ${
                    isSelected
                      ? "border-indigo-600 bg-indigo-50/70 shadow-xs ring-1 ring-indigo-600"
                      : isRecovered
                      ? "border-emerald-200 bg-white hover:bg-emerald-50/20"
                      : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold font-mono text-xs text-slate-900">
                          {report.task_id}
                        </span>
                        <StatusBadge status={report.terminal_status} size="sm" />
                      </div>
                      <p className="text-2xs text-slate-400 font-mono mt-0.5">
                        Recovery ID: {report.recovery_id} | Policy: {report.policy_id}
                      </p>
                    </div>

                    <div className="text-right text-2xs text-slate-500 font-mono">
                      <span>{report.total_recovery_duration_ms.toFixed(1)}ms</span>
                      <span className="block text-slate-400">
                        +{report.additional_tool_calls} tools
                      </span>
                    </div>
                  </div>

                  {/* Policy Selection Reason */}
                  {report.selection_reason && (
                    <div className="mt-2.5 p-2 rounded bg-slate-50 border border-slate-200 text-xs text-slate-700">
                      <span className="font-semibold text-slate-500 uppercase text-2xs block">
                        Selection Rationale:
                      </span>
                      <p className="mt-0.5">{report.selection_reason}</p>
                    </div>
                  )}

                  {/* Outcome details */}
                  <div className="mt-3 flex items-center justify-between text-2xs font-mono text-slate-500 pt-2 border-t border-slate-100">
                    <span>
                      Initial: <span className="text-rose-600 font-semibold">{report.original_status}</span>
                    </span>
                    <ArrowRight className="w-3 h-3 text-slate-400" />
                    <span>
                      Final Verifier:{" "}
                      <span
                        className={`font-semibold ${
                          report.final_verification_status === "verified"
                            ? "text-emerald-600"
                            : "text-slate-600"
                        }`}
                      >
                        {report.final_verification_status || "None"}
                      </span>
                    </span>
                    <span>{report.attempts.length} attempts</span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Recovery Details Side Panel */}
          <div className="lg:col-span-5">
            {selectedReport ? (
              <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden sticky top-6">
                <div className="p-5 border-b border-slate-200 bg-slate-50">
                  <div className="flex items-center justify-between">
                    <span className="text-2xs uppercase font-semibold text-slate-500 font-mono">
                      {selectedReport.policy_id} ({selectedReport.policy_version})
                    </span>
                    <StatusBadge status={selectedReport.terminal_status} size="sm" />
                  </div>
                  <h4 className="text-sm font-bold text-slate-900 font-mono mt-1">
                    Task: {selectedReport.task_id}
                  </h4>
                  <div className="mt-2 flex items-center gap-3">
                    <Link
                      to={`/traces?taskId=${selectedReport.task_id}`}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-semibold inline-flex items-center gap-1"
                    >
                      <GitCommitVertical className="w-3.5 h-3.5" /> Inspect Execution Trace
                    </Link>
                  </div>
                </div>

                <div className="p-5 space-y-4 max-h-[600px] overflow-y-auto text-xs">
                  {/* Budget Usage Breakdown */}
                  <div>
                    <h5 className="font-semibold text-slate-700 uppercase tracking-wider text-2xs mb-2">
                      Multi-Dimensional Budget Usage
                    </h5>
                    <div className="grid grid-cols-2 gap-2 bg-slate-50 p-3 rounded border border-slate-200 font-mono text-2xs">
                      <div>
                        <span className="text-slate-400 block">Attempts</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.budget_usage.attempts}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Steps Used</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.budget_usage.steps}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Tool Calls</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.budget_usage.tool_calls}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Model Calls</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.budget_usage.model_calls}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Overhead Latency</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.budget_usage.duration_ms.toFixed(1)} ms
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block">Exhausted Limit</span>
                        <span className="font-bold text-slate-800">
                          {selectedReport.budget_usage.exhausted_limit || "None"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Final Answer */}
                  {selectedReport.final_answer && (
                    <div>
                      <h5 className="font-semibold text-slate-700 uppercase tracking-wider text-2xs mb-1">
                        Post-Recovery Verified Answer
                      </h5>
                      <div className="p-3 bg-slate-900 text-emerald-300 rounded font-mono text-2xs whitespace-pre-wrap">
                        {selectedReport.final_answer}
                      </div>
                    </div>
                  )}

                  {/* Attempts & Actions */}
                  <div>
                    <h5 className="font-semibold text-slate-700 uppercase tracking-wider text-2xs mb-2">
                      Intervention Attempts ({selectedReport.attempts.length})
                    </h5>
                    <div className="space-y-3">
                      {selectedReport.attempts.map((attempt) => {
                        const isExpanded = expandedAttempts[attempt.attempt_id] ?? true;
                        return (
                          <div
                            key={attempt.attempt_id}
                            className="border border-slate-200 rounded overflow-hidden"
                          >
                            <div
                              onClick={() => toggleAttempt(attempt.attempt_id)}
                              className="p-3 bg-slate-50 flex items-center justify-between cursor-pointer hover:bg-slate-100"
                            >
                              <div className="flex items-center gap-2">
                                <span className="font-bold font-mono text-xs text-slate-800">
                                  Attempt #{attempt.attempt_index + 1}: {attempt.action_type}
                                </span>
                                <StatusBadge status={attempt.status} size="sm" />
                              </div>
                              {isExpanded ? (
                                <ChevronUp className="w-4 h-4 text-slate-400" />
                              ) : (
                                <ChevronDown className="w-4 h-4 text-slate-400" />
                              )}
                            </div>

                            {isExpanded && (
                              <div className="p-3 bg-white space-y-2 text-2xs font-mono">
                                <div className="text-slate-500">
                                  Duration: {attempt.duration_ms.toFixed(1)}ms
                                </div>
                                {attempt.actions.map((act) => (
                                  <div
                                    key={act.action_id}
                                    className="p-2 bg-slate-50 rounded border border-slate-100"
                                  >
                                    <span className="font-bold text-slate-900 block">
                                      {act.action_type}: {act.status}
                                    </span>
                                    <p className="font-sans text-slate-600 mt-0.5">
                                      {act.description}
                                    </p>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center bg-white rounded-lg border border-slate-200 text-slate-400 text-xs">
                Select a recovery report from the list to view policy interventions and budget consumption.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
