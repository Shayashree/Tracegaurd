import React, { useState, useEffect } from "react";
import { api, ApiError } from "../../api/client";
import type { TaskCreatePayload, TaskResponse, VerificationRule } from "../../types/api";
import { StatusBadge } from "../common/StatusBadge";
import { LoadingSpinner } from "../common/LoadingSpinner";
import { ErrorMessage } from "../common/ErrorMessage";
import {
  X,
  Play,
  Sparkles,
  RotateCcw,
  Sliders,
  Check,
  Copy,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Calculator,
  Database,
  FileSearch,
} from "lucide-react";

interface AssignCustomTaskModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTaskCompleted?: (taskResponse: TaskResponse) => void;
}

interface QuickTemplate {
  name: string;
  icon: string;
  description: string;
  task: string;
  allowedTools: string[];
  agentMode: string;
  maxSteps: number;
  verificationRule?: VerificationRule;
}

const TEMPLATES: QuickTemplate[] = [
  {
    name: "Product Pricing & Math",
    icon: "🛒",
    description: "Look up products and sum their prices with calculator",
    task: "Find the prices of Product A and Product B, then calculate their combined price.",
    allowedTools: ["data_lookup", "calculator"],
    agentMode: "traceguard_recovery",
    maxSteps: 8,
    verificationRule: {
      type: "numerical_tolerance",
      expected_value: 130.0,
      tolerance: 0.05,
    },
  },
  {
    name: "Document Policy Search",
    icon: "📄",
    description: "Search corporate knowledge base for return policy",
    task: "What is the policy for processing returns within 30 days?",
    allowedTools: ["document_search"],
    agentMode: "traceguard_recovery",
    maxSteps: 6,
  },
  {
    name: "Compound Arithmetic",
    icon: "🧮",
    description: "Multi-operation math computation",
    task: "Calculate ((250 * 4) + 150) / 5",
    allowedTools: ["calculator"],
    agentMode: "traceguard_recovery",
    maxSteps: 6,
    verificationRule: {
      type: "numerical_tolerance",
      expected_value: 230.0,
      tolerance: 0.01,
    },
  },
  {
    name: "Self-Healing Recovery Test",
    icon: "🛡️",
    description: "Multi-step lookup with parameter diagnosis & recovery",
    task: "Look up inventory stock for ultra-wide monitors and handle parameter validation.",
    allowedTools: ["data_lookup", "calculator"],
    agentMode: "traceguard_recovery",
    maxSteps: 10,
  },
];

export const AssignCustomTaskModal: React.FC<AssignCustomTaskModalProps> = ({
  isOpen,
  onClose,
  onTaskCompleted,
}) => {
  // Form State
  const [taskPrompt, setTaskPrompt] = useState<string>("");
  const [agentMode, setAgentMode] = useState<string>("traceguard_recovery");
  const [selectedTools, setSelectedTools] = useState<string[]>([
    "calculator",
    "data_lookup",
    "document_search",
  ]);
  const [maxSteps, setMaxSteps] = useState<number>(8);
  const [timeoutSeconds, setTimeoutSeconds] = useState<number>(30);

  // Verification options
  const [enableVerification, setEnableVerification] = useState<boolean>(false);
  const [verificationType, setVerificationType] = useState<
    "numerical_tolerance" | "exact_match" | "field_presence"
  >("numerical_tolerance");
  const [expectedValue, setExpectedValue] = useState<string>("");
  const [tolerance, setTolerance] = useState<number>(0.01);

  // Collapsible Advanced section
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  // Execution state
  const [executing, setExecuting] = useState<boolean>(false);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [executedTask, setExecutedTask] = useState<TaskResponse | null>(null);
  const [copiedId, setCopiedId] = useState<boolean>(false);

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setExecutionError(null);
      setExecutedTask(null);
      setCopiedId(false);
      if (!taskPrompt) {
        // Prefill with first template for convenient demonstration
        applyTemplate(TEMPLATES[0]);
      }
    }
  }, [isOpen]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen && !executing) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, executing, onClose]);

  const applyTemplate = (tpl: QuickTemplate) => {
    setTaskPrompt(tpl.task);
    setSelectedTools(tpl.allowedTools);
    setAgentMode(tpl.agentMode);
    setMaxSteps(tpl.maxSteps);
    if (tpl.verificationRule) {
      setEnableVerification(true);
      setVerificationType(tpl.verificationRule.type as any);
      setExpectedValue(String(tpl.verificationRule.expected_value ?? ""));
      setTolerance(tpl.verificationRule.tolerance ?? 0.01);
    } else {
      setEnableVerification(false);
      setExpectedValue("");
    }
  };

  const toggleTool = (toolName: string) => {
    setSelectedTools((prev) =>
      prev.includes(toolName)
        ? prev.filter((t) => t !== toolName)
        : [...prev, toolName]
    );
  };

  const handleExecute = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskPrompt.trim()) {
      setExecutionError("Task prompt cannot be empty.");
      return;
    }
    if (selectedTools.length === 0) {
      setExecutionError("Please enable at least one tool for the agent.");
      return;
    }

    setExecuting(true);
    setExecutionError(null);
    setExecutedTask(null);

    let rule: VerificationRule | undefined = undefined;
    if (enableVerification && expectedValue.trim()) {
      let parsedExpected: unknown = expectedValue.trim();
      if (verificationType === "numerical_tolerance") {
        const num = parseFloat(expectedValue.trim());
        if (!isNaN(num)) {
          parsedExpected = num;
        }
      }
      rule = {
        type: verificationType,
        expected_value: parsedExpected,
        tolerance: verificationType === "numerical_tolerance" ? tolerance : undefined,
      };
    }

    const payload: TaskCreatePayload = {
      task: taskPrompt.trim(),
      max_steps: maxSteps,
      timeout_seconds: timeoutSeconds,
      allowed_tools: selectedTools,
      verification_rule: rule,
      agent_mode: agentMode,
    };

    try {
      const response = await api.createTask(payload);
      setExecutedTask(response);
    } catch (err) {
      console.error("Failed to execute custom task:", err);
      setExecutionError(
        err instanceof ApiError ? err.message : "Failed to execute custom agent task."
      );
    } finally {
      setExecuting(false);
    }
  };

  const handleCopyTaskId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(true);
    setTimeout(() => setCopiedId(false), 2000);
  };

  const handleInspectTrace = () => {
    if (executedTask) {
      onTaskCompleted?.(executedTask);
      onClose();
    }
  };

  const handleResetForNewTask = () => {
    setExecutedTask(null);
    setExecutionError(null);
    setTaskPrompt("");
    setEnableVerification(false);
    setExpectedValue("");
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div
        className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-2xl w-full overflow-hidden transition-all my-8 animate-in fade-in zoom-in-95 duration-150"
        role="dialog"
        aria-modal="true"
        aria-labelledby="assign-task-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-slate-50/70">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 id="assign-task-title" className="text-lg font-bold text-slate-900">
                Assign Custom Agent Task
              </h2>
              <p className="text-xs text-slate-500">
                Execute an ad-hoc natural language task with live tracing and self-healing recovery.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={executing}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
            title="Close modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 max-h-[75vh] overflow-y-auto space-y-6">
          {executionError && (
            <ErrorMessage
              message={executionError}
              onRetry={() => setExecutionError(null)}
            />
          )}

          {/* Outcome Result Card (if task finished) */}
          {executedTask && (
            <div className="p-5 rounded-xl border border-emerald-200 bg-emerald-50/60 space-y-4">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-emerald-600 text-white flex items-center justify-center">
                    <Check className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-emerald-950">
                      Task Execution Completed
                    </h3>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="font-mono text-xs text-slate-600">
                        {executedTask.task_id}
                      </span>
                      <button
                        type="button"
                        onClick={() => handleCopyTaskId(executedTask.task_id)}
                        className="text-slate-400 hover:text-slate-700 transition-colors"
                        title="Copy Task ID"
                      >
                        {copiedId ? (
                          <Check className="w-3.5 h-3.5 text-emerald-600" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <StatusBadge status={executedTask.status} />
                  {executedTask.verification && (
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-semibold ${
                        executedTask.verification.verified
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-rose-100 text-rose-800"
                      }`}
                    >
                      {executedTask.verification.verified
                        ? "Verified"
                        : "Verification Failed"}
                    </span>
                  )}
                </div>
              </div>

              {/* Final Answer Block */}
              <div className="p-3.5 rounded-lg bg-white border border-emerald-100 shadow-2xs">
                <div className="text-2xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
                  Final Agent Proposed Answer
                </div>
                <div className="text-sm font-medium text-slate-800 whitespace-pre-wrap">
                  {executedTask.final_answer || "(No answer proposed)"}
                </div>
              </div>

              {/* Verification Message if available */}
              {executedTask.verification?.verification_message && (
                <div className="text-xs text-slate-600 bg-white/70 p-2.5 rounded border border-emerald-100/70">
                  <span className="font-medium text-slate-700">Verification note: </span>
                  {executedTask.verification.verification_message}
                </div>
              )}

              {/* Execution Summary Stats */}
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="p-2 rounded bg-white border border-emerald-100">
                  <span className="text-2xs uppercase text-slate-400 block">Steps</span>
                  <span className="text-sm font-bold text-slate-700">
                    {executedTask.steps_count}
                  </span>
                </div>
                <div className="p-2 rounded bg-white border border-emerald-100">
                  <span className="text-2xs uppercase text-slate-400 block">Duration</span>
                  <span className="text-sm font-bold text-slate-700">
                    {executedTask.duration_ms.toFixed(0)} ms
                  </span>
                </div>
                <div className="p-2 rounded bg-white border border-emerald-100">
                  <span className="text-2xs uppercase text-slate-400 block">Recovery</span>
                  <span className="text-sm font-bold text-slate-700">
                    {executedTask.recovery_status || "Standard"}
                  </span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 pt-1">
                <button
                  type="button"
                  onClick={handleResetForNewTask}
                  className="px-3.5 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 text-xs font-semibold transition-colors flex items-center gap-1.5"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  Assign Another Task
                </button>
                <button
                  type="button"
                  onClick={handleInspectTrace}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Inspect Full Trace &amp; Steps
                </button>
              </div>
            </div>
          )}

          {/* Form to submit (hidden or collapsible after completion) */}
          {(!executedTask || executing) && (
            <form onSubmit={handleExecute} className="space-y-5">
              {/* Quick Template Chips */}
              <div>
                <label className="block text-xs font-semibold text-slate-600 uppercase tracking-wider mb-2">
                  Quick Templates &amp; Demonstrations
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {TEMPLATES.map((tpl) => (
                    <button
                      key={tpl.name}
                      type="button"
                      onClick={() => applyTemplate(tpl)}
                      disabled={executing}
                      className="flex items-start gap-2.5 p-2.5 rounded-lg border border-slate-200 text-left hover:border-indigo-300 hover:bg-indigo-50/40 transition-all group disabled:opacity-50"
                    >
                      <span className="text-base select-none">{tpl.icon}</span>
                      <div className="min-w-0">
                        <div className="text-xs font-semibold text-slate-800 group-hover:text-indigo-600 truncate">
                          {tpl.name}
                        </div>
                        <div className="text-2xs text-slate-500 truncate">
                          {tpl.description}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Task Prompt Textarea */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label
                    htmlFor="task-prompt-input"
                    className="text-xs font-semibold text-slate-700 uppercase tracking-wider flex items-center gap-1"
                  >
                    Task Goal / Prompt <span className="text-rose-500">*</span>
                  </label>
                  <span className="text-2xs text-slate-400">
                    {taskPrompt.length} characters
                  </span>
                </div>
                <textarea
                  id="task-prompt-input"
                  rows={3}
                  value={taskPrompt}
                  onChange={(e) => setTaskPrompt(e.target.value)}
                  disabled={executing}
                  placeholder="e.g. Find the prices of Product A and Product B, then calculate their combined price."
                  className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 text-sm text-slate-800 placeholder-slate-400 font-sans resize-y transition-colors disabled:bg-slate-50"
                  required
                />
              </div>

              {/* Agent Mode Selector */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Agent Reliability Mode
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    {
                      id: "traceguard_recovery",
                      name: "TraceGuard Recovery",
                      badge: "Recommended",
                      desc: "Intelligent failure detection + targeted recovery",
                    },
                    {
                      id: "baseline",
                      name: "Baseline Agent",
                      desc: "Unassisted standard execution loop",
                    },
                    {
                      id: "fixed_retry",
                      name: "Fixed Retry",
                      desc: "Blind retry on tool exceptions",
                    },
                  ].map((mode) => (
                    <button
                      key={mode.id}
                      type="button"
                      onClick={() => setAgentMode(mode.id)}
                      disabled={executing}
                      className={`p-3 rounded-lg border text-left transition-all ${
                        agentMode === mode.id
                          ? "border-indigo-600 bg-indigo-50/60 ring-1 ring-indigo-600"
                          : "border-slate-200 hover:border-slate-300 bg-white"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-slate-800">
                          {mode.name}
                        </span>
                        {mode.badge && (
                          <span className="text-3xs bg-indigo-100 text-indigo-700 font-bold px-1.5 py-0.5 rounded">
                            {mode.badge}
                          </span>
                        )}
                      </div>
                      <p className="text-2xs text-slate-500 leading-tight">
                        {mode.desc}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Tool Selection */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-2">
                  Allowed Tools Whitelist
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    {
                      id: "calculator",
                      name: "Calculator",
                      icon: Calculator,
                      desc: "Arithmetic & formulas",
                    },
                    {
                      id: "data_lookup",
                      name: "Data Lookup",
                      icon: Database,
                      desc: "Products, orders, catalog",
                    },
                    {
                      id: "document_search",
                      name: "Doc Search",
                      icon: FileSearch,
                      desc: "Knowledge base & policies",
                    },
                  ].map((tool) => {
                    const isSelected = selectedTools.includes(tool.id);
                    const Icon = tool.icon;
                    return (
                      <button
                        key={tool.id}
                        type="button"
                        onClick={() => toggleTool(tool.id)}
                        disabled={executing}
                        className={`flex items-center gap-2.5 p-2.5 rounded-lg border text-left transition-all ${
                          isSelected
                            ? "border-indigo-500 bg-indigo-50/40 text-slate-800"
                            : "border-slate-200 text-slate-400 bg-slate-50/50"
                        }`}
                      >
                        <div
                          className={`w-7 h-7 rounded flex items-center justify-center shrink-0 ${
                            isSelected
                              ? "bg-indigo-600 text-white"
                              : "bg-slate-200 text-slate-400"
                          }`}
                        >
                          <Icon className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <div className="text-xs font-semibold truncate">
                            {tool.name}
                          </div>
                          <div className="text-3xs text-slate-500 truncate">
                            {tool.desc}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Advanced Settings Collapsible Toggle */}
              <div className="border border-slate-200 rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="w-full flex items-center justify-between px-4 py-2.5 bg-slate-50 text-slate-700 text-xs font-semibold hover:bg-slate-100 transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <Sliders className="w-3.5 h-3.5 text-slate-500" />
                    Execution Limits &amp; Deterministic Verification Rules
                  </span>
                  {showAdvanced ? (
                    <ChevronUp className="w-4 h-4 text-slate-500" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-500" />
                  )}
                </button>

                {showAdvanced && (
                  <div className="p-4 space-y-4 bg-white border-t border-slate-200">
                    {/* Constraints */}
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-2xs font-semibold text-slate-600 uppercase mb-1">
                          Max Execution Steps
                        </label>
                        <input
                          type="number"
                          min={1}
                          max={50}
                          value={maxSteps}
                          onChange={(e) =>
                            setMaxSteps(Math.max(1, parseInt(e.target.value) || 8))
                          }
                          disabled={executing}
                          className="w-full px-3 py-1.5 text-xs rounded border border-slate-300 focus:border-indigo-500 font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-2xs font-semibold text-slate-600 uppercase mb-1">
                          Timeout (Seconds)
                        </label>
                        <input
                          type="number"
                          min={2}
                          max={300}
                          value={timeoutSeconds}
                          onChange={(e) =>
                            setTimeoutSeconds(
                              Math.max(2, parseInt(e.target.value) || 30)
                            )
                          }
                          disabled={executing}
                          className="w-full px-3 py-1.5 text-xs rounded border border-slate-300 focus:border-indigo-500 font-mono"
                        />
                      </div>
                    </div>

                    {/* Verification Toggle */}
                    <div className="pt-2 border-t border-slate-100 space-y-3">
                      <div className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id="enable-verification-check"
                          checked={enableVerification}
                          onChange={(e) => setEnableVerification(e.target.checked)}
                          disabled={executing}
                          className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 h-4 w-4"
                        />
                        <label
                          htmlFor="enable-verification-check"
                          className="text-xs font-semibold text-slate-700 cursor-pointer"
                        >
                          Enable Deterministic Outcome Verification
                        </label>
                      </div>

                      {enableVerification && (
                        <div className="grid grid-cols-3 gap-3 p-3 rounded-lg bg-slate-50 border border-slate-200">
                          <div>
                            <label className="block text-3xs font-semibold text-slate-500 uppercase mb-1">
                              Verification Rule
                            </label>
                            <select
                              value={verificationType}
                              onChange={(e) =>
                                setVerificationType(e.target.value as any)
                              }
                              disabled={executing}
                              className="w-full px-2 py-1.5 text-xs rounded border border-slate-300 bg-white"
                            >
                              <option value="numerical_tolerance">
                                Numerical Tolerance
                              </option>
                              <option value="exact_match">Exact Match</option>
                              <option value="field_presence">
                                Field Presence
                              </option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-3xs font-semibold text-slate-500 uppercase mb-1">
                              Expected Value
                            </label>
                            <input
                              type="text"
                              value={expectedValue}
                              onChange={(e) => setExpectedValue(e.target.value)}
                              placeholder="e.g. 130.0"
                              disabled={executing}
                              className="w-full px-2 py-1.5 text-xs rounded border border-slate-300 font-mono"
                            />
                          </div>
                          {verificationType === "numerical_tolerance" && (
                            <div>
                              <label className="block text-3xs font-semibold text-slate-500 uppercase mb-1">
                                Tolerance (±)
                              </label>
                              <input
                                type="number"
                                step="0.001"
                                value={tolerance}
                                onChange={(e) =>
                                  setTolerance(parseFloat(e.target.value) || 0.01)
                                }
                                disabled={executing}
                                className="w-full px-2 py-1.5 text-xs rounded border border-slate-300 font-mono"
                              />
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Submit Button */}
              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-200">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={executing}
                  className="px-4 py-2 text-xs font-semibold text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={executing || !taskPrompt.trim()}
                  className="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-bold shadow-md hover:shadow-indigo-500/25 transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                >
                  {executing ? (
                    <>
                      <LoadingSpinner size="sm" />
                      <span>Executing Agent Trajectory...</span>
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5 fill-current" />
                      <span>Execute Custom Task</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
