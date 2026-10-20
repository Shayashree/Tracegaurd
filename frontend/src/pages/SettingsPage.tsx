import React, { useEffect, useState } from "react";
import { api } from "../api/client";
import type { HealthResponse, DetectorConfig } from "../types/api";
import { StatusBadge } from "../components/common/StatusBadge";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  Server,
  ShieldCheck,
  Wrench,
  Sliders,
} from "lucide-react";

export const SettingsPage: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [detectorConfig, setDetectorConfig] = useState<DetectorConfig | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchConfig = async () => {
      setLoading(true);
      setError(null);
      try {
        const [h, dc] = await Promise.all([
          api.getHealth(),
          api.getDetectorConfig().catch(() => null),
        ]);
        setHealth(h);
        setDetectorConfig(dc);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load system configuration");
      } finally {
        setLoading(false);
      }
    };
    fetchConfig();
  }, []);

  if (loading) {
    return <LoadingSpinner message="Checking backend connection and reading system configuration..." />;
  }

  if (error) {
    return <ErrorMessage title="Could not connect to backend" message={error} />;
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">System Settings &amp; Configuration</h2>
        <p className="text-xs text-slate-500">
          Inspect backend runtime status, model adapter parameters, detector thresholds, and tool capabilities.
        </p>
      </div>

      {/* Backend API Status */}
      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Server className="w-4 h-4 text-indigo-600" />
            <h3 className="text-sm font-semibold text-slate-900">Backend API Status</h3>
          </div>
          <StatusBadge status={health?.status === "ok" ? "healthy" : "unverified"} />
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs font-mono">
          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-2xs text-slate-500 uppercase block">Active Service</span>
            <span className="font-bold text-slate-800 text-sm">{health?.service}</span>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-2xs text-slate-500 uppercase block">Platform API Version</span>
            <span className="font-bold text-slate-800 text-sm">{health?.version}</span>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-2xs text-slate-500 uppercase block">Pluggable Model Adapter</span>
            <span className="font-bold text-indigo-700 text-sm">{health?.model_adapter}</span>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-2xs text-slate-500 uppercase block">Default Max Step Budget</span>
            <span className="font-bold text-slate-800 text-sm">{health?.default_max_steps} steps</span>
          </div>
        </div>
      </div>

      {/* Detector Thresholds */}
      {detectorConfig && (
        <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-indigo-600" />
              <h3 className="text-sm font-semibold text-slate-900">
                Trajectory Failure Detector Configuration ({detectorConfig.detector_version})
              </h3>
            </div>
            <span className="text-2xs font-mono text-slate-400">Deterministic &amp; Heuristic</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs font-mono">
            <div className="p-3 bg-slate-50 rounded border border-slate-200">
              <span className="text-2xs text-slate-500 uppercase block">
                Max Consecutive Repetition Threshold
              </span>
              <span className="font-bold text-slate-800">
                {detectorConfig.max_repetition_threshold} consecutive calls
              </span>
            </div>

            <div className="p-3 bg-slate-50 rounded border border-slate-200">
              <span className="text-2xs text-slate-500 uppercase block">
                Tool Call Repetition Ratio
              </span>
              <span className="font-bold text-slate-800">
                {(detectorConfig.repetition_ratio_threshold * 100).toFixed(0)}%
              </span>
            </div>

            <div className="p-3 bg-slate-50 rounded border border-slate-200">
              <span className="text-2xs text-slate-500 uppercase block">
                Stagnation Step Limit
              </span>
              <span className="font-bold text-slate-800">
                {detectorConfig.stagnation_step_threshold} steps
              </span>
            </div>

            <div className="p-3 bg-slate-50 rounded border border-slate-200">
              <span className="text-2xs text-slate-500 uppercase block">
                Max Tolerated Tool Failures
              </span>
              <span className="font-bold text-slate-800">
                {detectorConfig.max_allowed_tool_failures} failures
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Recovery Engine Budget Bounds */}
      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-indigo-600" />
            <h3 className="text-sm font-semibold text-slate-900">
              Autonomous Recovery Safety Bounds (Milestone 4 Engine)
            </h3>
          </div>
          <span className="text-2xs font-mono text-emerald-600 font-semibold">Strictly Bounded</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-2xs text-slate-500 uppercase block">Max Attempts per Task</span>
            <span className="font-bold text-slate-800">2 attempts</span>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-2xs text-slate-500 uppercase block">Max Steps per Attempt</span>
            <span className="font-bold text-slate-800">5 steps</span>
          </div>

          <div className="p-3 bg-slate-50 rounded border border-slate-200">
            <span className="text-2xs text-slate-500 uppercase block">Max Additional Tool Calls</span>
            <span className="font-bold text-slate-800">5 calls</span>
          </div>
        </div>
      </div>

      {/* Supported Tools Registry */}
      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
          <Wrench className="w-4 h-4 text-indigo-600" />
          <h3 className="text-sm font-semibold text-slate-900">Registered Deterministic Tools</h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
          {[
            {
              name: "calculator",
              desc: "Evaluates exact arithmetic expressions deterministically.",
            },
            {
              name: "database_lookup",
              desc: "Structured record querying across customers, orders, inventory, and users.",
            },
            {
              name: "document_search",
              desc: "Keyword and passage retrieval over company policies and technical documentation.",
            },
            {
              name: "string_length",
              desc: "Calculates character length of input string safely.",
            },
            {
              name: "get_weather",
              desc: "Deterministic mock meteorological condition lookup by city.",
            },
          ].map((tool) => (
            <div key={tool.name} className="p-3 bg-slate-50 rounded border border-slate-200 font-mono">
              <span className="font-bold text-slate-900 block text-xs">{tool.name}</span>
              <p className="text-slate-600 font-sans text-2xs mt-0.5">{tool.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
