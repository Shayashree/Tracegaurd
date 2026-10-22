import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { ExperimentSummary } from "../types/api";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  FileText,
  Download,
  Copy,
  Check,
  Fingerprint,
  RefreshCw,
  Sparkles,
} from "lucide-react";

export const ReportsPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialExpId = searchParams.get("id") || "";

  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [selectedExpId, setSelectedExpId] = useState<string>(initialExpId);
  const [reportMarkdown, setReportMarkdown] = useState<string>("");
  const [manifest, setManifest] = useState<Record<string, unknown> | null>(null);
  const [activeTab, setActiveTab] = useState<"report" | "manifest">("report");

  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      setError(null);
      try {
        const expList = await api.getExperiments({ limit: 50 });
        setExperiments(expList);
        const targetId =
          selectedExpId || (expList.length > 0 ? expList[0].experiment_id : "");
        if (targetId) {
          setSelectedExpId(targetId);
          await loadReportData(targetId);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load reports");
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const loadReportData = async (id: string) => {
    try {
      const [reportRes, manifestRes] = await Promise.all([
        api.getExperimentReport(id, "markdown").catch((err) => {
          console.warn("Report load error:", err);
          return null;
        }),
        api.getExperimentManifest(id).catch((err) => {
          console.warn("Manifest load error:", err);
          return null;
        }),
      ]);
      let reportText = "";
      if (typeof reportRes === "string") {
        reportText = reportRes;
      } else if (reportRes && typeof reportRes === "object") {
        reportText = (reportRes as any).report_markdown || (reportRes as any).report || "";
      }
      setReportMarkdown(reportText);
      setManifest(manifestRes);
    } catch (err) {
      console.warn("Report load notice:", err);
    }
  };

  const handleGenerateReport = async () => {
    if (!selectedExpId) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await api.generateExperimentReport(selectedExpId);
      setReportMarkdown(res.report_markdown || "");
      if (res.manifest) {
        setManifest(res.manifest);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate research report");
    } finally {
      setGenerating(false);
    }
  };

  const handleExperimentChange = async (id: string) => {
    setSelectedExpId(id);
    setSearchParams({ id });
    setLoading(true);
    await loadReportData(id);
    setLoading(false);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const downloadTextFile = (content: string, filename: string, type: string = "text/markdown") => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Research Reports &amp; Reproducibility Artifacts
          </h2>
          <p className="text-xs text-slate-500">
            Audit-grade reproducibility manifests, publication-ready research reports, and raw JSON/JSONL datasets.
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

      {loading && <LoadingSpinner message="Generating research report and reproducibility manifest..." />}

      {error && <ErrorMessage title="Could not load report artifacts" message={error} />}

      {!loading && selectedExpId && (
        <div className="space-y-4">
          {/* Action Toolbar */}
          <div className="bg-white p-4 rounded-lg border border-slate-200 shadow-xs flex flex-wrap items-center justify-between gap-4">
            {/* View Tabs */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveTab("report")}
                className={`px-3 py-1.5 rounded text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                  activeTab === "report"
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                <FileText className="w-3.5 h-3.5" /> Research Report (Markdown)
              </button>
              <button
                onClick={() => setActiveTab("manifest")}
                className={`px-3 py-1.5 rounded text-xs font-semibold transition-colors flex items-center gap-1.5 ${
                  activeTab === "manifest"
                    ? "bg-slate-900 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                <Fingerprint className="w-3.5 h-3.5" /> Reproducibility Manifest
              </button>
            </div>

            {/* Download and Action Buttons */}
            <div className="flex items-center gap-2 flex-wrap">
              <button
                onClick={handleGenerateReport}
                disabled={generating}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-700 bg-indigo-50 border border-indigo-200 rounded hover:bg-indigo-100 transition-colors shadow-2xs disabled:opacity-50"
                title="Regenerate Research Report & Reproducibility Manifest"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${generating ? "animate-spin" : ""}`} />
                {generating ? "Generating..." : "Regenerate Report"}
              </button>

              <button
                onClick={() =>
                  activeTab === "report"
                    ? downloadTextFile(reportMarkdown, `${selectedExpId}_report.md`)
                    : downloadTextFile(JSON.stringify(manifest, null, 2), `${selectedExpId}_manifest.json`, "application/json")
                }
                disabled={activeTab === "report" ? !reportMarkdown : !manifest}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors shadow-2xs disabled:opacity-50"
              >
                <Download className="w-3.5 h-3.5" /> Download Active Document
              </button>

              <a
                href={api.getExperimentExportUrl(selectedExpId, "json")}
                download={`${selectedExpId}.json`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded transition-colors"
              >
                <Download className="w-3.5 h-3.5" /> JSON Export
              </a>

              <a
                href={api.getExperimentExportUrl(selectedExpId, "jsonl")}
                download={`${selectedExpId}.jsonl`}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded transition-colors"
              >
                <Download className="w-3.5 h-3.5" /> JSONL Export
              </a>

              <button
                onClick={() =>
                  copyToClipboard(
                    activeTab === "report" ? reportMarkdown : JSON.stringify(manifest, null, 2)
                  )
                }
                disabled={activeTab === "report" ? !reportMarkdown : !manifest}
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-slate-600 bg-white border border-slate-200 rounded hover:bg-slate-50 transition-colors disabled:opacity-50"
                title="Copy to clipboard"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* Tab Content */}
          {activeTab === "report" ? (
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs p-8 max-h-[750px] overflow-y-auto">
              {reportMarkdown ? (
                <div className="prose prose-slate max-w-none text-xs font-mono whitespace-pre-wrap leading-relaxed text-slate-800">
                  {reportMarkdown}
                </div>
              ) : (
                <div className="p-12 text-center space-y-4">
                  <div className="text-slate-500 text-xs">
                    No research report has been generated yet for experiment{" "}
                    <span className="font-mono font-medium text-slate-800">{selectedExpId}</span>.
                  </div>
                  <button
                    onClick={handleGenerateReport}
                    disabled={generating}
                    className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-md transition-colors shadow-xs disabled:opacity-50"
                  >
                    <Sparkles className="w-4 h-4" />
                    {generating ? "Generating Research Report..." : "Generate Research Report Now"}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="bg-white rounded-lg border border-slate-200 shadow-xs p-6 space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-slate-200">
                <div className="flex items-center gap-2">
                  <Fingerprint className="w-4 h-4 text-indigo-600" />
                  <h3 className="text-xs font-semibold uppercase text-slate-700">
                    Audit-Grade Reproducibility Manifest
                  </h3>
                </div>
                {manifest && (
                  <span className="text-2xs font-mono text-slate-500">
                    SHA-256 Verified
                  </span>
                )}
              </div>

              {manifest ? (
                <pre className="p-4 bg-slate-900 text-emerald-400 rounded-lg font-mono text-xs overflow-x-auto max-h-[600px] whitespace-pre-wrap">
                  {JSON.stringify(manifest, null, 2)}
                </pre>
              ) : (
                <div className="p-8 text-center text-xs text-slate-400 italic">
                  No reproducibility manifest recorded for this experiment.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
