import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { ExperimentSummary, StatisticalComparison, OverviewStats } from "../types/api";
import { StatusBadge } from "../components/common/StatusBadge";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import { Scale } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

export const StrategyComparisonPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialExpId = searchParams.get("experimentId") || "";

  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [selectedExpId, setSelectedExpId] = useState<string>(initialExpId);
  const [comparisons, setComparisons] = useState<StatisticalComparison[]>([]);
  const [overviewStats, setOverviewStats] = useState<OverviewStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      setError(null);
      try {
        const [expList, stats] = await Promise.all([
          api.getExperiments({ limit: 50 }),
          api.getOverviewStats(),
        ]);
        setExperiments(expList);
        setOverviewStats(stats);

        // Pick experiment ID
        const targetId =
          selectedExpId || (expList.length > 0 ? expList[0].experiment_id : "");
        if (targetId) {
          setSelectedExpId(targetId);
          const compData = await api.getExperimentComparisons(targetId);
          setComparisons(compData);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load comparisons");
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const handleExperimentChange = async (id: string) => {
    setSelectedExpId(id);
    setSearchParams({ experimentId: id });
    setLoading(true);
    setError(null);
    try {
      const compData = await api.getExperimentComparisons(id);
      setComparisons(compData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load comparisons for selected experiment");
    } finally {
      setLoading(false);
    }
  };

  // Prepare chart data from mode breakdown in overviewStats
  const modeChartData = (overviewStats?.mode_breakdown || []).map((m) => ({
    name: m.mode.replace(/_/g, " "),
    mode: m.mode,
    successRate: m.success_rate,
    totalRuns: m.total_runs,
    meanDurationSec: +(m.mean_latency_ms / 1000).toFixed(2),
    avgTools: m.avg_tool_calls,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Strategy Comparison &amp; Hypothesis Testing</h2>
          <p className="text-xs text-slate-500">
            Rigorous paired comparisons (Baseline vs. Fixed Retry vs. TraceGuard Recovery) with McNemar hypothesis testing and confidence intervals.
          </p>
        </div>

        {experiments.length > 0 && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-600 font-medium">Select Experiment:</span>
            <select
              value={selectedExpId}
              onChange={(e) => handleExperimentChange(e.target.value)}
              className="border border-slate-200 rounded px-3 py-1.5 bg-white font-mono text-xs focus:ring-1 focus:ring-indigo-500"
            >
              {experiments.map((e) => (
                <option key={e.experiment_id} value={e.experiment_id}>
                  {e.experiment_id} ({e.agent_mode})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {loading && <LoadingSpinner message="Calculating paired hypothesis statistics..." />}

      {error && (
        <ErrorMessage
          title="Could not load comparison data"
          message={error}
          onRetry={() => handleExperimentChange(selectedExpId)}
        />
      )}

      {/* Overview Comparison Visualizations */}
      {!loading && modeChartData.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Success Rate Comparison */}
          <div className="bg-white p-6 rounded-lg border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Verified Task Success Rate Comparison
                </h3>
                <p className="text-xs text-slate-500">
                  Percentage of tasks passing independent verifier
                </p>
              </div>
              <span className="text-xs font-mono text-emerald-600 font-semibold">Higher is better</span>
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
                  <Bar dataKey="successRate" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Efficiency / Latency Comparison */}
          <div className="bg-white p-6 rounded-lg border border-slate-200 shadow-xs">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-900">
                  Mean Latency Overhead (Seconds)
                </h3>
                <p className="text-xs text-slate-500">
                  Execution duration comparison across modes
                </p>
              </div>
            </div>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={modeChartData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                  <YAxis unit="s" tick={{ fontSize: 11 }} />
                  <Tooltip
                    formatter={(val) => [`${val}s`, "Mean Duration"]}
                    contentStyle={{ backgroundColor: "#0f172a", color: "#fff", borderRadius: "6px", fontSize: "12px" }}
                  />
                  <Bar dataKey="meanDurationSec" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Paired Statistical Comparison Tables */}
      {!loading && comparisons.length > 0 ? (
        <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">
                Paired Statistical Hypothesis Tests
              </h3>
              <p className="text-xs text-slate-500">
                McNemar test of marginal homogeneity on paired task runs (Significance threshold α = 0.05)
              </p>
            </div>
            <span className="text-2xs font-mono bg-indigo-50 text-indigo-700 px-2 py-1 rounded border border-indigo-200 font-semibold">
              Experiment: {selectedExpId}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 text-2xs uppercase text-slate-500 border-b border-slate-200 font-sans">
                <tr>
                  <th className="px-6 py-3">Comparison</th>
                  <th className="px-6 py-3">Sample Pairs</th>
                  <th className="px-6 py-3">Baseline SR</th>
                  <th className="px-6 py-3">Treatment SR</th>
                  <th className="px-6 py-3">Absolute Gain</th>
                  <th className="px-6 py-3">Test Statistic</th>
                  <th className="px-6 py-3">p-value</th>
                  <th className="px-6 py-3">Significant (p &lt; 0.05)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {comparisons.map((c, i) => (
                  <tr key={i} className="hover:bg-slate-50/70">
                    <td className="px-6 py-4 font-bold text-slate-900">
                      <span className="capitalize">{c.baseline_mode.replace(/_/g, " ")}</span>
                      <span className="text-slate-400 font-normal"> vs </span>
                      <span className="capitalize text-indigo-600 font-bold">
                        {c.treatment_mode.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-sans">
                      {c.paired_pairs} pairs
                    </td>
                    <td className="px-6 py-4">
                      {c.baseline_success_rate.toFixed(1)}%
                    </td>
                    <td className="px-6 py-4 text-indigo-700 font-bold">
                      {c.treatment_success_rate.toFixed(1)}%
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={`font-semibold ${
                          c.absolute_gain > 0
                            ? "text-emerald-600"
                            : c.absolute_gain < 0
                            ? "text-rose-600"
                            : "text-slate-500"
                        }`}
                      >
                        {c.absolute_gain > 0 ? "+" : ""}
                        {c.absolute_gain.toFixed(1)}% pts
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      {c.test_type_used} (stat={c.statistic.toFixed(3)})
                    </td>
                    <td className="px-6 py-4 font-bold">
                      {c.p_value < 0.001 ? "< 0.001" : c.p_value.toFixed(4)}
                    </td>
                    <td className="px-6 py-4 font-sans">
                      <StatusBadge
                        status={c.is_significant ? "confirmed" : "unverified"}
                        size="sm"
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Details / Warnings */}
          <div className="p-4 bg-slate-50 border-t border-slate-200 text-2xs text-slate-600 space-y-1 font-sans">
            <p className="font-semibold text-slate-700">Methodology &amp; Validity Notes:</p>
            <p>
              • McNemar's exact binomial test is utilized when discordant pairs (b + c) &lt; 25, while Edwards' continuity-corrected asymptotic chi-square is applied for larger sample sizes.
            </p>
            <p>
              • Comparisons are computed strictly over paired benchmark tasks evaluated under identical configurations.
            </p>
          </div>
        </div>
      ) : !loading ? (
        <div className="bg-white p-8 rounded-lg border border-slate-200 text-center text-xs text-slate-500">
          <Scale className="w-8 h-8 text-slate-300 mx-auto mb-2" />
          <p className="font-semibold text-slate-700">No Paired Comparisons Available for this Experiment</p>
          <p className="mt-1 max-w-md mx-auto text-slate-400">
            Paired statistical tests require multi-mode evaluations (e.g. baseline and traceguard_recovery runs over the same task set).
          </p>
        </div>
      ) : null}
    </div>
  );
};
