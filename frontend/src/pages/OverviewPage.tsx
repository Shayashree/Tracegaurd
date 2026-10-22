import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { OverviewStats, ExperimentSummary } from "../types/api";
import { MetricCard } from "../components/common/MetricCard";
import { StatusBadge } from "../components/common/StatusBadge";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { EmptyState } from "../components/common/EmptyState";
import {
  FlaskConical,
  CheckCircle2,
  LifeBuoy,
  Clock,
  Wrench,
  DollarSign,
  PlayCircle,
  ArrowRight,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";

export const OverviewPage: React.FC = () => {
  const navigate = useNavigate();
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [recentExperiments, setRecentExperiments] = useState<ExperimentSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [overviewData, expData] = await Promise.all([
        api.getOverviewStats(),
        api.getExperiments({ limit: 5 }),
      ]);
      setStats(overviewData);
      setRecentExperiments(expData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load overview data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return <LoadingSpinner message="Calculating platform statistics from SQLite database..." />;
  }

  if (error) {
    return (
      <ErrorMessage
        title="Could not load overview statistics"
        message={error}
        onRetry={fetchData}
      />
    );
  }

  if (!stats || stats.total_experiments === 0) {
    return (
      <EmptyState
        title="No Experiments Found"
        description="Run your first evaluation benchmark across Baseline, Fixed Retry, and TraceGuard recovery modes to populate dashboard reliability metrics."
        actionText="Launch Benchmark Experiment"
        onAction={() => navigate("/run-experiment")}
        icon={<FlaskConical className="w-8 h-8 text-indigo-500" />}
      />
    );
  }

  // Format mode names for display
  const modeChartData = (stats.mode_breakdown || []).map((m) => ({
    name: m.mode.replace(/_/g, " "),
    modeKey: m.mode,
    successRate: m.success_rate,
    totalRuns: m.total_runs,
    verifiedRuns: m.verified_runs,
    meanLatencySec: +(m.mean_latency_ms / 1000).toFixed(2),
    avgTools: m.avg_tool_calls,
  }));

  const failureChartData = (stats.failure_distribution || []).map((f) => ({
    category: f.category.replace(/_/g, " "),
    count: f.count,
  }));

  const MODE_COLORS: Record<string, string> = {
    baseline: "#64748b",
    fixed_retry: "#3b82f6",
    traceguard: "#8b5cf6",
    traceguard_recovery: "#10b981",
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-gradient-to-r from-slate-900 to-indigo-950 rounded-xl p-6 text-white shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-500/20 text-indigo-200 border border-indigo-400/30 mb-2">
            Research Evaluation Platform
          </span>
          <h2 className="text-xl font-bold tracking-tight">Agent Reliability &amp; Autonomous Recovery</h2>
          <p className="text-sm text-slate-300 mt-1 max-w-2xl">
            TraceGuard monitors tool-using AI agent trajectories in real time, diagnoses deterministic and heuristic failure patterns, and executes bounded, policy-specific interventions with independent outcome verification.
          </p>
        </div>
        <div className="shrink-0 flex items-center gap-3">
          <Link
            to="/traces?assign=true"
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg shadow-sm transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            Assign Custom Task
          </Link>
          <Link
            to="/run-experiment"
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-slate-900 bg-white hover:bg-slate-100 rounded-lg shadow-sm transition-colors"
          >
            <PlayCircle className="w-4 h-4 text-indigo-600" />
            New Experiment
          </Link>
          <Link
            to="/comparison"
            className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-semibold text-slate-200 hover:text-white hover:bg-white/10 rounded-lg transition-colors border border-white/20"
          >
            Compare Strategies
          </Link>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Experiments"
          value={stats.total_experiments}
          subtext={`${stats.total_runs_evaluated} evaluated agent runs`}
          icon={<FlaskConical className="w-5 h-5" />}
        />
        <MetricCard
          label="Verified Success Rate"
          value={`${stats.verified_task_success_rate}%`}
          subtext="Outcome verified by deterministic rules"
          icon={<CheckCircle2 className="w-5 h-5 text-emerald-600" />}
        />
        <MetricCard
          label="Recovery Success Rate"
          value={`${stats.recovery_success_rate}%`}
          subtext={`${stats.total_recovery_interventions} recovery attempts`}
          icon={<LifeBuoy className="w-5 h-5 text-indigo-600" />}
        />
        <MetricCard
          label="Median Latency"
          value={`${(stats.median_latency_ms / 1000).toFixed(2)}s`}
          subtext={`Mean: ${(stats.mean_latency_ms / 1000).toFixed(2)}s`}
          icon={<Clock className="w-5 h-5" />}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Avg Tool Calls / Task"
          value={stats.average_tool_calls_per_task}
          subtext="Observable interaction overhead"
          icon={<Wrench className="w-5 h-5" />}
        />
        <MetricCard
          label="Total Measured Cost"
          value={`$${stats.total_measured_cost.toFixed(4)}`}
          subtext="Model token usage tracking"
          icon={<DollarSign className="w-5 h-5" />}
        />
        <MetricCard
          label="Total Interventions"
          value={stats.total_recovery_interventions}
          subtext="Bounded failure-specific triggers"
          icon={<ShieldAlert className="w-5 h-5 text-amber-600" />}
        />
        <MetricCard
          label="Sample Coverage"
          value={`${stats.total_runs_evaluated} runs`}
          subtext="Persisted in SQLite database"
          icon={<FlaskConical className="w-5 h-5" />}
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Success Rate by Execution Mode */}
        <div className="bg-white p-6 rounded-lg border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Verified Success Rate by Agent Mode
              </h3>
              <p className="text-xs text-slate-500">
                Comparison across baseline, fixed retry, and recovery
              </p>
            </div>
            <span className="text-xs font-mono text-slate-400">Higher is better</span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={modeChartData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(val) => [`${val}%`, "Success Rate"]}
                  contentStyle={{ backgroundColor: "#0f172a", color: "#fff", borderRadius: "6px", fontSize: "12px" }}
                />
                <Bar dataKey="successRate" radius={[4, 4, 0, 0]}>
                  {modeChartData.map((entry) => (
                    <Cell
                      key={`cell-${entry.modeKey}`}
                      fill={MODE_COLORS[entry.modeKey] || "#4f46e5"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Failure Categories Distribution */}
        <div className="bg-white p-6 rounded-lg border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Failure Distribution by Category
              </h3>
              <p className="text-xs text-slate-500">
                Observed failure causes across all evaluated runs
              </p>
            </div>
            <span className="text-xs font-mono text-slate-400">Total: {failureChartData.reduce((acc, x) => acc + x.count, 0)}</span>
          </div>
          <div className="h-64">
            {failureChartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs text-slate-400 italic">
                No failure events recorded in current database runs.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={failureChartData}
                  layout="vertical"
                  margin={{ top: 5, right: 20, left: 40, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis dataKey="category" type="category" tick={{ fontSize: 11 }} width={120} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#0f172a", color: "#fff", borderRadius: "6px", fontSize: "12px" }}
                  />
                  <Bar dataKey="count" fill="#ef4444" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Latency and Overhead Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latency by Mode */}
        <div className="bg-white p-6 rounded-lg border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Mean Execution Latency by Mode
              </h3>
              <p className="text-xs text-slate-500">Duration in seconds per task</p>
            </div>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={modeChartData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis unit="s" tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(val) => [`${val}s`, "Mean Duration"]}
                  contentStyle={{ backgroundColor: "#0f172a", color: "#fff", borderRadius: "6px", fontSize: "12px" }}
                />
                <Bar dataKey="meanLatencySec" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Tool Calls by Mode */}
        <div className="bg-white p-6 rounded-lg border border-slate-200 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Average Tool Calls by Mode
              </h3>
              <p className="text-xs text-slate-500">Interaction steps per task</p>
            </div>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={modeChartData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(val) => [val, "Avg Tool Calls"]}
                  contentStyle={{ backgroundColor: "#0f172a", color: "#fff", borderRadius: "6px", fontSize: "12px" }}
                />
                <Bar dataKey="avgTools" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Recent Experiments Table */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Recent Experiments</h3>
            <p className="text-xs text-slate-500">Latest executed benchmark evaluations</p>
          </div>
          <Link
            to="/experiments"
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
          >
            View All ({stats.total_experiments}) <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-6 py-3">Experiment ID</th>
                <th className="px-6 py-3">Benchmark</th>
                <th className="px-6 py-3">Agent Mode</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Tasks</th>
                <th className="px-6 py-3">Created</th>
                <th className="px-6 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono text-xs">
              {recentExperiments.map((exp) => (
                <tr key={exp.experiment_id} className="hover:bg-slate-50/70 transition-colors">
                  <td className="px-6 py-3.5 font-semibold text-slate-900">
                    {exp.experiment_id}
                  </td>
                  <td className="px-6 py-3.5 text-slate-600 font-sans">
                    {exp.benchmark_version}
                  </td>
                  <td className="px-6 py-3.5 font-sans capitalize">
                    {exp.agent_mode.replace(/_/g, " ")}
                  </td>
                  <td className="px-6 py-3.5">
                    <StatusBadge status={exp.status} size="sm" />
                  </td>
                  <td className="px-6 py-3.5">
                    {exp.completed_tasks} / {exp.total_tasks}
                  </td>
                  <td className="px-6 py-3.5 text-slate-400 font-sans">
                    {new Date(exp.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-3.5 text-right font-sans">
                    <Link
                      to={`/experiments?id=${exp.experiment_id}`}
                      className="text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1"
                    >
                      Inspect <ArrowRight className="w-3 h-3" />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
