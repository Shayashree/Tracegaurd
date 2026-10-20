import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { api } from "../../api/client";
import type { HealthResponse } from "../../types/api";
import { Database } from "lucide-react";

const pageTitles: Record<string, { title: string; subtitle: string }> = {
  "/": {
    title: "Executive Overview",
    subtitle: "Overall agent reliability, evaluated runs, and research performance metrics",
  },
  "/experiments": {
    title: "Experiment Management",
    subtitle: "Browse, filter, and inspect persisted evaluation experiments",
  },
  "/run-experiment": {
    title: "Launch Benchmark Experiment",
    subtitle: "Configure and run controlled multi-mode agent evaluations",
  },
  "/traces": {
    title: "Execution Trace Explorer",
    subtitle: "Chronological step-by-step trace events, tool executions, and state observations",
  },
  "/diagnostics": {
    title: "Failure Diagnostics Explorer",
    subtitle: "Trajectory-based failure findings across F1–F9 taxonomy with linked evidence",
  },
  "/recovery": {
    title: "Recovery Analysis",
    subtitle: "Failure-specific recovery interventions, budget usage, and independent verification",
  },
  "/comparison": {
    title: "Strategy Comparison",
    subtitle: "Rigorous statistical comparisons across Baseline, Fixed Retry, and TraceGuard",
  },
  "/evaluation": {
    title: "Research Evaluation & Ablation",
    subtitle: "Answers to RQ1–RQ6, component ablation decomposition, and held-out generalization",
  },
  "/reports": {
    title: "Reports & Exports",
    subtitle: "Download research manifests, markdown reports, and raw JSONL traces",
  },
  "/settings": {
    title: "Settings & System Configuration",
    subtitle: "Backend connection status, detector thresholds, and tool runtime parameters",
  },
};

export const Navbar: React.FC = () => {
  const location = useLocation();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [connected, setConnected] = useState<boolean | null>(null);

  useEffect(() => {
    let isMounted = true;
    api
      .getHealth()
      .then((data) => {
        if (isMounted) {
          setHealth(data);
          setConnected(true);
        }
      })
      .catch(() => {
        if (isMounted) {
          setConnected(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const currentPath = location.pathname;
  const currentMeta = pageTitles[currentPath] || {
    title: "TraceGuard Platform",
    subtitle: "Evidence-Driven Reliability & Recovery",
  };

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between shrink-0">
      <div>
        <h1 className="text-lg font-semibold text-slate-900 leading-tight">
          {currentMeta.title}
        </h1>
        <p className="text-xs text-slate-500 hidden sm:block">
          {currentMeta.subtitle}
        </p>
      </div>

      <div className="flex items-center gap-3">
        {/* Backend health status pill */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-full border border-slate-200 bg-slate-50 text-xs font-mono">
          <span
            className={`w-2 h-2 rounded-full ${
              connected === true
                ? "bg-emerald-500 animate-pulse"
                : connected === false
                ? "bg-rose-500"
                : "bg-slate-400"
            }`}
          />
          <span className="text-slate-600 font-sans text-xs">
            {connected === true
              ? `API Online (${health?.model_adapter || "adapter"})`
              : connected === false
              ? "API Disconnected"
              : "Connecting..."}
          </span>
        </div>

        {/* Database tag */}
        <div className="hidden md:flex items-center gap-1.5 px-2.5 py-1 rounded text-2xs font-mono bg-slate-100 text-slate-600 border border-slate-200">
          <Database className="w-3 h-3 text-slate-400" />
          <span>traceguard.db</span>
        </div>
      </div>
    </header>
  );
};
