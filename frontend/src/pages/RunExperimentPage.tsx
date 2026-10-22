import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { BenchmarkTask, CategoryType } from "../types/api";
import { LoadingSpinner } from "../components/common/LoadingSpinner";
import { ErrorMessage } from "../components/common/ErrorMessage";
import {
  PlayCircle,
  CheckCircle2,
  Layers,
  Settings2,
  Sliders,
  Check,
  Sparkles,
} from "lucide-react";

export const RunExperimentPage: React.FC = () => {
  const navigate = useNavigate();

  // Benchmarks list and tasks
  const [benchmarks, setBenchmarks] = useState<string[]>(["v1.0"]);
  const [selectedVersion, setSelectedVersion] = useState<string>("v1.0");
  const [tasks, setTasks] = useState<BenchmarkTask[]>([]);

  // Configuration Form State
  const [taskSelectionMode, setTaskSelectionMode] = useState<"all" | "category" | "custom">("all");
  const [selectedCategory, setSelectedCategory] = useState<CategoryType | "">("");
  const [selectedTaskIds, setSelectedTaskIds] = useState<string[]>([]);
  const [agentMode, setAgentMode] = useState<string>("traceguard_recovery");
  const [repetitions, setRepetitions] = useState<number>(1);
  const [enableFailureInjection, setEnableFailureInjection] = useState<boolean>(false);
  const [maxSteps, setMaxSteps] = useState<number>(10);
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(30);

  // Execution State
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createdExperimentId, setCreatedExperimentId] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<string | null>(null);

  useEffect(() => {
    const loadBenchmarks = async () => {
      try {
        const bms = await api.getBenchmarks();
        if (bms && bms.length > 0) {
          setBenchmarks(bms);
          if (!selectedVersion) {
            setSelectedVersion(typeof bms[0] === "string" ? bms[0] : (bms[0] as any).benchmark_version || "v1.0");
          }
        }
      } catch (err) {
        console.error("Failed to load benchmarks:", err);
      }
    };
    loadBenchmarks();
  }, []);

  useEffect(() => {
    if (!selectedVersion) return;
    const loadTasks = async () => {
      try {
        const taskList = await api.getBenchmarkTasks(selectedVersion);
        setTasks(taskList);
      } catch (err) {
        console.error("Failed to load benchmark tasks:", err);
      }
    };
    loadTasks();
  }, [selectedVersion]);

  // Handle task checkbox toggle
  const toggleTaskId = (taskId: string) => {
    setSelectedTaskIds((prev) =>
      prev.includes(taskId) ? prev.filter((id) => id !== taskId) : [...prev, taskId]
    );
  };

  // Determine effective task IDs
  const effectiveTaskCount = React.useMemo(() => {
    if (taskSelectionMode === "all") return tasks.length;
    if (taskSelectionMode === "category") {
      return tasks.filter((t) => t.category === selectedCategory).length;
    }
    return selectedTaskIds.length;
  }, [taskSelectionMode, tasks, selectedCategory, selectedTaskIds]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    setCreatedExperimentId(null);

    let taskIdsToSend: string[] | undefined = undefined;
    let categoryToSend: CategoryType | undefined = undefined;

    if (taskSelectionMode === "custom") {
      if (selectedTaskIds.length === 0) {
        setSubmitError("Please select at least one task ID.");
        setSubmitting(false);
        return;
      }
      taskIdsToSend = selectedTaskIds;
    } else if (taskSelectionMode === "category") {
      if (!selectedCategory) {
        setSubmitError("Please choose a category filter.");
        setSubmitting(false);
        return;
      }
      categoryToSend = selectedCategory as CategoryType;
    }

    try {
      const response = await api.runExperiment({
        benchmark_version: selectedVersion,
        task_ids: taskIdsToSend,
        category: categoryToSend,
        agent_mode: agentMode,
        repetitions,
        enable_failure_injection: enableFailureInjection,
        max_steps: maxSteps,
        timeout_seconds: timeoutSeconds,
      });

      setCreatedExperimentId(response.experiment_id);
      setRunStatus(response.status);

      // If already completed synchronously, show completed
      if (response.status === "completed") {
        setSubmitting(false);
      } else {
        // Poll status
        let attempts = 0;
        const interval = setInterval(async () => {
          attempts++;
          try {
            const exp = await api.getExperiment(response.experiment_id);
            setRunStatus(exp.status);
            if (exp.status === "completed" || exp.status === "failed" || attempts >= 20) {
              clearInterval(interval);
              setSubmitting(false);
            }
          } catch {
            clearInterval(interval);
            setSubmitting(false);
          }
        }, 1500);
      }
    } catch (err) {
      setSubmitError(
        err instanceof ApiError ? err.message : "Failed to launch experiment. Check backend."
      );
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white p-5 rounded-xl border border-slate-200 shadow-2xs">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Launch Benchmark Evaluation Experiment
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Execute controlled tasks under Baseline, Fixed Retry, or TraceGuard Recovery modes.
          </p>
        </div>
        <Link
          to="/traces?assign=true"
          className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700 hover:bg-indigo-100 text-xs font-semibold transition-colors shrink-0 shadow-2xs"
        >
          <Sparkles className="w-3.5 h-3.5 text-indigo-600" />
          Assign Custom Task instead &rarr;
        </Link>
      </div>

      {createdExperimentId && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-5 text-emerald-900 shadow-xs">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-6 h-6 text-emerald-600 shrink-0" />
              <div>
                <h3 className="text-sm font-semibold">
                  Experiment {runStatus === "completed" ? "Successfully Completed!" : "Running..."}
                </h3>
                <p className="text-xs text-emerald-800 mt-1 font-mono">
                  ID: <span className="font-bold">{createdExperimentId}</span> ({runStatus})
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => navigate(`/experiments?id=${createdExperimentId}`)}
                className="px-2.5 py-1.5 text-xs font-semibold text-white bg-emerald-700 hover:bg-emerald-800 rounded transition-colors shadow-2xs"
              >
                Inspect Results
              </button>
              <button
                onClick={() => navigate(`/traces`)}
                className="px-2.5 py-1.5 text-xs font-semibold text-emerald-900 bg-white border border-emerald-300 hover:bg-emerald-100 rounded transition-colors shadow-2xs"
              >
                Execution Traces
              </button>
              <button
                onClick={() => navigate(`/diagnostics?experimentId=${createdExperimentId}`)}
                className="px-2.5 py-1.5 text-xs font-semibold text-emerald-900 bg-white border border-emerald-300 hover:bg-emerald-100 rounded transition-colors shadow-2xs"
              >
                Diagnostics
              </button>
              <button
                onClick={() => navigate(`/recovery?experimentId=${createdExperimentId}`)}
                className="px-2.5 py-1.5 text-xs font-semibold text-emerald-900 bg-white border border-emerald-300 hover:bg-emerald-100 rounded transition-colors shadow-2xs"
              >
                Recovery
              </button>
              <button
                onClick={() => navigate(`/reports?id=${createdExperimentId}`)}
                className="px-2.5 py-1.5 text-xs font-semibold text-emerald-800 bg-emerald-100/60 border border-emerald-300 hover:bg-emerald-200 rounded transition-colors"
              >
                View Report
              </button>
            </div>
          </div>
        </div>
      )}

      {submitError && (
        <ErrorMessage title="Validation or Execution Error" message={submitError} />
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Section A: Benchmark Configuration */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100 text-slate-900 font-semibold text-sm">
            <Layers className="w-4 h-4 text-indigo-600" />
            <span>A. Benchmark Dataset &amp; Task Scope</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Benchmark Version
              </label>
              <select
                value={selectedVersion}
                onChange={(e) => setSelectedVersion(e.target.value)}
                className="w-full text-xs border border-slate-200 rounded p-2 focus:ring-1 focus:ring-indigo-500 font-mono"
              >
                {benchmarks.map((b) => {
                  const val = typeof b === "string" ? b : String((b as any)?.benchmark_version || b);
                  return (
                    <option key={val} value={val}>
                      {val} (TraceGuard Evaluation Suite)
                    </option>
                  );
                })}
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Controlled Failure Injections
              </label>
              <div className="flex items-center gap-3 mt-2">
                <input
                  type="checkbox"
                  id="failure_injection"
                  checked={enableFailureInjection}
                  onChange={(e) => setEnableFailureInjection(e.target.checked)}
                  className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                />
                <label htmlFor="failure_injection" className="text-xs text-slate-700 cursor-pointer">
                  Activate controlled failure scenarios (transient errors, bad args, missing evidence)
                </label>
              </div>
            </div>
          </div>

          {/* Task Selection Mode */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-2">
              Task Scope
            </label>
            <div className="grid grid-cols-3 gap-3">
              {[
                { id: "all", label: "All Benchmark Tasks", desc: `All ${tasks.length} tasks` },
                { id: "category", label: "Filter by Category", desc: "Select specific problem domain" },
                { id: "custom", label: "Select Individual Tasks", desc: "Cherry-pick task IDs" },
              ].map((m) => (
                <div
                  key={m.id}
                  onClick={() => setTaskSelectionMode(m.id as "all" | "category" | "custom")}
                  className={`p-3 rounded border text-xs cursor-pointer transition-colors ${
                    taskSelectionMode === m.id
                      ? "border-indigo-600 bg-indigo-50/50 text-indigo-900 font-medium"
                      : "border-slate-200 hover:bg-slate-50 text-slate-700"
                  }`}
                >
                  <p className="font-semibold">{m.label}</p>
                  <p className="text-2xs text-slate-500 mt-0.5">{m.desc}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Category Dropdown */}
          {taskSelectionMode === "category" && (
            <div className="p-3 bg-slate-50 rounded border border-slate-200">
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Select Benchmark Category:
              </label>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value as CategoryType)}
                className="w-full text-xs border border-slate-200 rounded p-2 bg-white"
              >
                <option value="">-- Choose Category --</option>
                <option value="arithmetic">Arithmetic (math tools)</option>
                <option value="data_lookup">Data Lookup (database queries)</option>
                <option value="document_qa">Document QA (search and synthesis)</option>
                <option value="multi_step">Multi-Step (compositional pipelines)</option>
                <option value="failure_scenario">Controlled Failure Scenarios</option>
              </select>
            </div>
          )}

          {/* Custom Task Checkboxes */}
          {taskSelectionMode === "custom" && (
            <div className="p-3 bg-slate-50 rounded border border-slate-200 max-h-48 overflow-y-auto space-y-1.5 font-mono text-xs">
              {tasks.map((t) => (
                <label
                  key={t.task_id}
                  className="flex items-center gap-2 p-1.5 hover:bg-white rounded cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedTaskIds.includes(t.task_id)}
                    onChange={() => toggleTaskId(t.task_id)}
                    className="rounded border-slate-300 text-indigo-600 h-3.5 w-3.5"
                  />
                  <span className="font-bold text-slate-800">{t.task_id}</span>
                  <span className="text-slate-500 text-2xs truncate">
                    ({t.category}) — {t.task_description}
                  </span>
                </label>
              ))}
            </div>
          )}
        </div>

        {/* Section B: Execution Modes */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100 text-slate-900 font-semibold text-sm">
            <Sliders className="w-4 h-4 text-indigo-600" />
            <span>B. Agent Execution Mode</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              {
                id: "baseline",
                title: "Baseline Agent",
                desc: "Standard prompt-and-tool loop with passive trace recording. Fails upon unhandled error.",
              },
              {
                id: "fixed_retry",
                title: "Fixed Retry Agent",
                desc: "Retries the entire task execution upon failure blindly without diagnosis up to budget.",
              },
              {
                id: "traceguard_recovery",
                title: "TraceGuard Recovery",
                desc: "Trajectory-based failure detection, policy selection (A–H), bounded intervention, & verification.",
              },
            ].map((mode) => (
              <div
                key={mode.id}
                onClick={() => setAgentMode(mode.id)}
                className={`p-4 rounded-lg border cursor-pointer transition-all ${
                  agentMode === mode.id
                    ? "border-indigo-600 bg-indigo-50/70 shadow-xs ring-1 ring-indigo-600"
                    : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <h4 className="text-xs font-bold text-slate-900">{mode.title}</h4>
                  {agentMode === mode.id && <Check className="w-4 h-4 text-indigo-600" />}
                </div>
                <p className="text-2xs text-slate-600 leading-normal">{mode.desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Section C: Constraints */}
        <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100 text-slate-900 font-semibold text-sm">
            <Settings2 className="w-4 h-4 text-indigo-600" />
            <span>C. Execution Constraints &amp; Repetitions</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Repetitions per Task
              </label>
              <input
                type="number"
                min={1}
                max={20}
                value={repetitions}
                onChange={(e) => setRepetitions(parseInt(e.target.value) || 1)}
                className="w-full text-xs border border-slate-200 rounded p-2 focus:ring-1 focus:ring-indigo-500 font-mono"
              />
              <span className="text-2xs text-slate-400 mt-1 block">Default: 1 repetition</span>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Max Steps per Run
              </label>
              <input
                type="number"
                min={1}
                max={50}
                value={maxSteps}
                onChange={(e) => setMaxSteps(parseInt(e.target.value) || 10)}
                className="w-full text-xs border border-slate-200 rounded p-2 focus:ring-1 focus:ring-indigo-500 font-mono"
              />
              <span className="text-2xs text-slate-400 mt-1 block">Hard bound (1–50)</span>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-700 mb-1">
                Timeout per Task (seconds)
              </label>
              <input
                type="number"
                min={1}
                max={300}
                value={timeoutSeconds}
                onChange={(e) => setTimeoutSeconds(parseFloat(e.target.value) || 30)}
                className="w-full text-xs border border-slate-200 rounded p-2 focus:ring-1 focus:ring-indigo-500 font-mono"
              />
              <span className="text-2xs text-slate-400 mt-1 block">Time limit per agent task</span>
            </div>
          </div>
        </div>

        {/* Section D: Launch Button */}
        <div className="bg-slate-900 rounded-lg p-5 text-white flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-sm">
          <div>
            <h4 className="text-sm font-semibold">Launch Summary</h4>
            <p className="text-xs text-slate-400 mt-0.5">
              Evaluating <span className="text-white font-bold">{effectiveTaskCount}</span> tasks in{" "}
              <span className="text-white font-bold capitalize">{agentMode.replace(/_/g, " ")}</span> mode{" "}
              ({repetitions} {repetitions === 1 ? "rep" : "reps"}).
            </p>
          </div>

          <button
            type="submit"
            disabled={submitting || effectiveTaskCount === 0}
            className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-md text-xs font-semibold shadow-xs transition-colors ${
              submitting || effectiveTaskCount === 0
                ? "bg-slate-700 text-slate-400 cursor-not-allowed"
                : "bg-indigo-600 hover:bg-indigo-500 text-white"
            }`}
          >
            {submitting ? (
              <>
                <LoadingSpinner size="sm" message="" />
                <span>Running Evaluation...</span>
              </>
            ) : (
              <>
                <PlayCircle className="w-4 h-4" />
                <span>Submit &amp; Execute Experiment</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
