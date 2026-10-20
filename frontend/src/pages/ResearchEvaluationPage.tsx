import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type {
  ExperimentSummary,
  AblationAnalysis,
  DetectorMetrics,
} from "../types/api";
import { StatusBadge } from "../components/common/StatusBadge";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  Microscope,
  CheckCircle2,
  Layers,
  TrendingUp,
  Clock,
  ShieldAlert,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

export const ResearchEvaluationPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialExpId = searchParams.get("experimentId") || "";

  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [selectedExpId, setSelectedExpId] = useState<string>(initialExpId);
  const [ablation, setAblation] = useState<AblationAnalysis | null>(null);
  const [detectorMetrics, setDetectorMetrics] = useState<DetectorMetrics | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadInitial = async () => {
      setLoading(true);
      setError(null);
      try {
        const expList = await api.getExperiments({ limit: 50 });
        setExperiments(expList);
        const targetId =
          selectedExpId || (expList.length > 0 ? expList[0].experiment_id : "");
        if (targetId) {
          setSelectedExpId(targetId);
          await loadExperimentData(targetId);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load research data");
      } finally {
        setLoading(false);
      }
    };
    loadInitial();
  }, []);

  const loadExperimentData = async (id: string) => {
    try {
      const abl = await api.getExperimentAblation(id).catch(() => null);
      setAblation(abl);
      try {
        const dm = await api.getExperimentDetectorMetrics(id);
        setDetectorMetrics(dm);
      } catch {
        setDetectorMetrics(null);
      }
    } catch (err) {
      console.warn("Artifact load notice:", err);
    }
  };

  const handleExperimentChange = async (id: string) => {
    setSelectedExpId(id);
    setSearchParams({ experimentId: id });
    setLoading(true);
    await loadExperimentData(id);
    setLoading(false);
  };

  const ablationChartData = (ablation?.configurations || []).map((c) => ({
    name: c.name,
    successRate: c.verified_success_rate,
    sampleSize: c.sample_size,
    medianLatency: +(c.median_duration_ms / 1000).toFixed(2),
    meanTools: c.mean_tool_calls,
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Research Evaluation &amp; Ablation Studies
          </h2>
          <p className="text-xs text-slate-500">
            Systematic answers to research questions RQ1–RQ6 across failure detection, recovery effectiveness, efficiency, and ablation decomposition.
          </p>
        </div>

        {experiments.length > 0 && (
          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-600 font-medium">Experiment:</span>
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

      {loading && <LoadingSpinner message="Loading ablation decomposition and research evaluation metrics..." />}

      {error && <ErrorMessage title="Could not load research metrics" message={error} />}

      {/* Research Questions Summary Cards (RQ1 - RQ6) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {/* RQ1: Failure Detection */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-xs space-y-2">
          <div className="flex items-center gap-2 text-indigo-700 font-bold text-xs uppercase tracking-wider">
            <ShieldAlert className="w-4 h-4" />
            <span>RQ1: Failure Detection</span>
          </div>
          <h4 className="text-sm font-semibold text-slate-900">
            Trajectory-Based Diagnostic Performance
          </h4>
          <p className="text-xs text-slate-600 leading-normal">
            {detectorMetrics ? (
              <>
                The detector achieved <strong className="text-slate-900">{(detectorMetrics.f1_score * 100).toFixed(1)}% F1</strong>{" "}
                ({(detectorMetrics.precision * 100).toFixed(1)}% precision, {(detectorMetrics.recall * 100).toFixed(1)}% recall) with a mean latency of{" "}
                <strong className="text-slate-900">{detectorMetrics.mean_detection_latency_ms.toFixed(1)}ms</strong>.
              </>
            ) : (
              "Evaluates whether observable execution events contain deterministic or heuristic proof of failure before task termination."
            )}
          </p>
          <div className="pt-2 border-t border-slate-100 text-2xs text-slate-400 font-mono">
            {detectorMetrics ? `Evaluated on ${detectorMetrics.total_evaluated} runs` : "Awaiting evaluation run"}
          </div>
        </div>

        {/* RQ2: Recovery Effectiveness */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-xs space-y-2">
          <div className="flex items-center gap-2 text-emerald-700 font-bold text-xs uppercase tracking-wider">
            <CheckCircle2 className="w-4 h-4" />
            <span>RQ2: Recovery Effectiveness</span>
          </div>
          <h4 className="text-sm font-semibold text-slate-900">
            End-to-End Task Success Improvement
          </h4>
          <p className="text-xs text-slate-600 leading-normal">
            Trajectory-based diagnosis combined with targeted policies (A–H) outperforms unguided fixed retry by executing failure-specific state checkpoints and corrections.
          </p>
          <div className="pt-2 border-t border-slate-100 text-2xs text-slate-400 font-mono">
            Independent verification enforced
          </div>
        </div>

        {/* RQ3: Efficiency & Overhead */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-xs space-y-2">
          <div className="flex items-center gap-2 text-sky-700 font-bold text-xs uppercase tracking-wider">
            <Clock className="w-4 h-4" />
            <span>RQ3: Overhead &amp; Efficiency</span>
          </div>
          <h4 className="text-sm font-semibold text-slate-900">
            Latency &amp; Tool Resource Trade-off
          </h4>
          <p className="text-xs text-slate-600 leading-normal">
            Measures additional latency (ms), extra tool calls, and model tokens incurred strictly during bounded recovery interventions.
          </p>
          <div className="pt-2 border-t border-slate-100 text-2xs text-slate-400 font-mono">
            Multi-dimensional budget enforced
          </div>
        </div>

        {/* RQ4: Failure-Specific Performance */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-xs space-y-2">
          <div className="flex items-center gap-2 text-amber-700 font-bold text-xs uppercase tracking-wider">
            <Layers className="w-4 h-4" />
            <span>RQ4: Policy Granularity</span>
          </div>
          <h4 className="text-sm font-semibold text-slate-900">
            Category-Specific Policy Utility
          </h4>
          <p className="text-xs text-slate-600 leading-normal">
            Evaluates recovery success rates grouped by failure categories (e.g. transient tool retry vs schema repair vs evidence collection).
          </p>
          <div className="pt-2 border-t border-slate-100 text-2xs text-slate-400 font-mono">
            Policies A–H breakdown
          </div>
        </div>

        {/* RQ5: Generalization */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-xs space-y-2">
          <div className="flex items-center gap-2 text-purple-700 font-bold text-xs uppercase tracking-wider">
            <TrendingUp className="w-4 h-4" />
            <span>RQ5: Generalization</span>
          </div>
          <h4 className="text-sm font-semibold text-slate-900">
            Held-Out Task Performance
          </h4>
          <p className="text-xs text-slate-600 leading-normal">
            Verifies that diagnostic rules and recovery policies generalize effectively to held-out test splits without overfitting.
          </p>
          <div className="pt-2 border-t border-slate-100 text-2xs text-slate-400 font-mono">
            Train / Test split verification
          </div>
        </div>

        {/* RQ6: Component Ablation */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-xs space-y-2">
          <div className="flex items-center gap-2 text-rose-700 font-bold text-xs uppercase tracking-wider">
            <Microscope className="w-4 h-4" />
            <span>RQ6: Component Ablation</span>
          </div>
          <h4 className="text-sm font-semibold text-slate-900">
            Isolating Subsystem Contributions
          </h4>
          <p className="text-xs text-slate-600 leading-normal">
            Decomposes performance across: Baseline → Detector Only → Fixed Retry → Full TraceGuard Recovery.
          </p>
          <div className="pt-2 border-t border-slate-100 text-2xs text-slate-400 font-mono">
            4-way systematic ablation
          </div>
        </div>
      </div>

      {/* Component Ablation Section */}
      {ablation ? (
        <div className="bg-white rounded-lg border border-slate-200 shadow-xs overflow-hidden space-y-6 p-6">
          <div className="flex items-center justify-between pb-4 border-b border-slate-200">
            <div>
              <h3 className="text-base font-bold text-slate-900">
                Systematic Component Ablation Study
              </h3>
              <p className="text-xs text-slate-500">
                Isolated contributions of Failure Detection, Policy Selection, and Targeted Recovery.
              </p>
            </div>
            <span className="text-xs font-mono font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2.5 py-1 rounded">
              Experiment: {ablation.experiment_id}
            </span>
          </div>

          {/* Ablation Chart */}
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={ablationChartData} margin={{ top: 10, right: 10, left: -10, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(val) => [`${val}%`, "Verified Success Rate"]}
                  contentStyle={{ backgroundColor: "#0f172a", color: "#fff", borderRadius: "6px", fontSize: "12px" }}
                />
                <Bar dataKey="successRate" fill="#4f46e5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Ablation Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-50 text-2xs uppercase text-slate-500 border-b border-slate-200 font-sans">
                <tr>
                  <th className="px-4 py-3">Configuration</th>
                  <th className="px-4 py-3">Detector</th>
                  <th className="px-4 py-3">Policy Selection</th>
                  <th className="px-4 py-3">Recovery Intervention</th>
                  <th className="px-4 py-3">Sample Size</th>
                  <th className="px-4 py-3">Verified Success Rate</th>
                  <th className="px-4 py-3">Median Latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {ablation.configurations.map((cfg) => (
                  <tr key={cfg.config_id} className="hover:bg-slate-50/70">
                    <td className="px-4 py-3 font-bold text-slate-900 font-sans">
                      {cfg.name}
                      <span className="block text-2xs text-slate-400 font-normal">
                        {cfg.description}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={cfg.has_detector ? "verified" : "unverified"} size="sm" />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={cfg.has_policy_selection ? "verified" : "unverified"} size="sm" />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={cfg.has_targeted_recovery ? "verified" : "unverified"} size="sm" />
                    </td>
                    <td className="px-4 py-3 font-sans">
                      {cfg.sample_size} runs
                    </td>
                    <td className="px-4 py-3 text-indigo-700 font-bold text-sm">
                      {cfg.verified_success_rate.toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-slate-500 font-sans">
                      {(cfg.median_duration_ms / 1000).toFixed(2)}s
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Automated Metric Interpretation */}
          {ablation.interpretation && (
            <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-700 space-y-1">
              <h5 className="font-semibold text-slate-900 uppercase text-2xs">
                Empirical Metric Interpretation
              </h5>
              <p className="font-sans leading-relaxed">{ablation.interpretation}</p>
            </div>
          )}
        </div>
      ) : !loading ? (
        <div className="bg-white p-8 rounded-lg border border-slate-200 text-center text-xs text-slate-500">
          <p className="font-semibold text-slate-700">Ablation Study Not Executed for Selected Experiment</p>
          <p className="mt-1 text-slate-400 max-w-md mx-auto">
            Run an experiment with ablation configurations or select an experiment that recorded 4-way ablation results to inspect component contributions.
          </p>
        </div>
      ) : null}
    </div>
  );
};
