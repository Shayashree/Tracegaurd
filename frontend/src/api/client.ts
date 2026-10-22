/**
 * Central typed API client for TraceGuard dashboard.
 */
import type {
  BenchmarkTask,
  DetectorConfig,
  DetectorMetrics,
  DiagnosticReport,
  ExperimentSummary,
  HealthResponse,
  OverviewStats,
  RecoveryReport,
  StatisticalComparison,
  AblationAnalysis,
  FailureAnalysis,
  TaskExecutionResult,
  TraceEvent,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers = {
    "Content-Type": "application/json",
    Accept: "application/json",
    ...(options.headers || {}),
  };

  try {
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      let errorBody: unknown;
      try {
        errorBody = await response.json();
      } catch {
        errorBody = await response.text();
      }
      const message =
        typeof errorBody === "object" && errorBody !== null && "detail" in errorBody
          ? String((errorBody as { detail: unknown }).detail)
          : `HTTP ${response.status}: ${response.statusText}`;
      throw new ApiError(response.status, message, errorBody);
    }

    // Check if expected empty body or text
    const contentType = response.headers.get("content-type");
    if (contentType && contentType.includes("application/json")) {
      return (await response.json()) as T;
    }
    return (await response.text()) as unknown as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(0, error instanceof Error ? error.message : "Network error");
  }
}

export const api = {
  // System Health
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },

  // Overview Stats
  async getOverviewStats(): Promise<OverviewStats> {
    return request<OverviewStats>("/experiments/overview/stats");
  },

  // Benchmarks
  async getBenchmarks(): Promise<string[]> {
    const data = await request<unknown[]>("/benchmarks");
    if (Array.isArray(data)) {
      return data.map((b) =>
        typeof b === "string" ? b : (b as { benchmark_version?: string }).benchmark_version || String(b)
      );
    }
    return ["v1.0"];
  },

  async getBenchmarkTasks(version: string = "v1.0", category?: string): Promise<BenchmarkTask[]> {
    const q = category ? `?category=${encodeURIComponent(category)}` : "";
    return request<BenchmarkTask[]>(`/benchmarks/${encodeURIComponent(version)}/tasks${q}`);
  },

  // Experiments
  async getExperiments(params?: {
    limit?: number;
    offset?: number;
    mode?: string;
    status?: string;
  }): Promise<ExperimentSummary[]> {
    const sp = new URLSearchParams();
    if (params?.limit) sp.set("limit", String(params.limit));
    if (params?.offset) sp.set("offset", String(params.offset));
    if (params?.mode) sp.set("mode", params.mode);
    if (params?.status) sp.set("status", params.status);
    const qs = sp.toString() ? `?${sp.toString()}` : "";
    return request<ExperimentSummary[]>(`/experiments${qs}`);
  },

  async getExperiment(experimentId: string): Promise<ExperimentSummary> {
    return request<ExperimentSummary>(`/experiments/${encodeURIComponent(experimentId)}`);
  },

  async runExperiment(payload: {
    benchmark_version?: string;
    task_ids?: string[];
    category?: string;
    agent_mode?: string;
    repetitions?: number;
    enable_failure_injection?: boolean;
    max_steps?: number;
    timeout_seconds?: number;
  }): Promise<ExperimentSummary> {
    return request<ExperimentSummary>("/experiments/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async getExperimentResults(
    experimentId: string,
    params?: { limit?: number; offset?: number; mode?: string }
  ): Promise<TaskExecutionResult[]> {
    const sp = new URLSearchParams();
    if (params?.limit) sp.set("limit", String(params.limit));
    if (params?.offset) sp.set("offset", String(params.offset));
    if (params?.mode) sp.set("mode", params.mode);
    const qs = sp.toString() ? `?${sp.toString()}` : "";
    return request<TaskExecutionResult[]>(
      `/experiments/${encodeURIComponent(experimentId)}/results${qs}`
    );
  },

  async getExperimentComparisons(experimentId: string): Promise<StatisticalComparison[]> {
    return request<StatisticalComparison[]>(
      `/experiments/${encodeURIComponent(experimentId)}/comparisons`
    );
  },

  async getExperimentFailureAnalysis(experimentId: string): Promise<FailureAnalysis> {
    return request<FailureAnalysis>(
      `/experiments/${encodeURIComponent(experimentId)}/failure-analysis`
    );
  },

  async getExperimentAblation(experimentId: string): Promise<AblationAnalysis> {
    return request<AblationAnalysis>(
      `/experiments/${encodeURIComponent(experimentId)}/ablation`
    );
  },

  async getExperimentReport(
    experimentId: string,
    format: "markdown" | "text" | "json" = "markdown"
  ): Promise<{ experiment_id?: string; format?: string; report_markdown?: string; report?: string } | string> {
    return request(`/experiments/${encodeURIComponent(experimentId)}/report?format=${format}`);
  },

  async generateExperimentReport(
    experimentId: string
  ): Promise<{ status: string; experiment_id: string; report_markdown: string; manifest: Record<string, unknown> }> {
    return request(`/experiments/${encodeURIComponent(experimentId)}/generate-report`, {
      method: "POST",
    });
  },

  async getExperimentManifest(experimentId: string): Promise<Record<string, unknown>> {
    return request(`/experiments/${encodeURIComponent(experimentId)}/manifest`);
  },

  getExperimentExportUrl(experimentId: string, format: "json" | "jsonl" = "json"): string {
    return `${BASE_URL}/experiments/${encodeURIComponent(experimentId)}/export?format=${format}`;
  },

  // Traces & Tasks
  async getRecentTasks(limit: number = 25): Promise<Array<{
    task_id: string;
    run_id: string;
    task_prompt: string;
    status: string;
    steps_count: number;
    duration_ms: number;
    created_at: string;
    benchmark_task_id?: string;
    experiment_id?: string;
    display_label: string;
  }>> {
    return request(`/tasks/recent?limit=${limit}`);
  },

  async getTaskTraces(taskId: string): Promise<TraceEvent[]> {
    return request<TraceEvent[]>(`/tasks/${encodeURIComponent(taskId)}/traces`);
  },

  getTaskTraceExportUrl(taskId: string): string {
    return `${BASE_URL}/tasks/${encodeURIComponent(taskId)}/traces/export`;
  },

  // Diagnostics
  async getDiagnostics(params?: {
    limit?: number;
    offset?: number;
    experiment_id?: string;
    failure_category?: string;
    status?: string;
  }): Promise<DiagnosticReport[]> {
    const sp = new URLSearchParams();
    if (params?.limit) sp.set("limit", String(params.limit));
    if (params?.offset) sp.set("offset", String(params.offset));
    if (params?.experiment_id) sp.set("experiment_id", params.experiment_id);
    if (params?.failure_category) sp.set("failure_category", params.failure_category);
    if (params?.status) sp.set("status", params.status);
    const qs = sp.toString() ? `?${sp.toString()}` : "";
    return request<DiagnosticReport[]>(`/diagnostics${qs}`);
  },

  async getDiagnosticReport(diagnosticId: string): Promise<DiagnosticReport> {
    return request<DiagnosticReport>(`/diagnostics/${encodeURIComponent(diagnosticId)}`);
  },

  async getTaskDiagnostics(taskId: string): Promise<DiagnosticReport[]> {
    return request<DiagnosticReport[]>(`/tasks/${encodeURIComponent(taskId)}/diagnostics`);
  },

  async getDetectorConfig(): Promise<DetectorConfig> {
    return request<DetectorConfig>("/diagnostics/config");
  },

  async getExperimentDetectorMetrics(experimentId: string): Promise<DetectorMetrics> {
    return request<DetectorMetrics>(
      `/experiments/${encodeURIComponent(experimentId)}/detector-metrics`
    );
  },

  // Recovery
  async getRecoveryReports(params?: {
    limit?: number;
    offset?: number;
    experiment_id?: string;
    policy_id?: string;
    status?: string;
  }): Promise<RecoveryReport[]> {
    const sp = new URLSearchParams();
    if (params?.limit) sp.set("limit", String(params.limit));
    if (params?.offset) sp.set("offset", String(params.offset));
    if (params?.experiment_id) sp.set("experiment_id", params.experiment_id);
    if (params?.policy_id) sp.set("policy_id", params.policy_id);
    if (params?.status) sp.set("status", params.status);
    const qs = sp.toString() ? `?${sp.toString()}` : "";
    return request<RecoveryReport[]>(`/recovery/reports${qs}`);
  },

  async getRecoveryReport(recoveryId: string): Promise<RecoveryReport> {
    return request<RecoveryReport>(`/recovery/${encodeURIComponent(recoveryId)}`);
  },

  async getTaskRecovery(taskId: string): Promise<RecoveryReport> {
    return request<RecoveryReport>(`/tasks/${encodeURIComponent(taskId)}/recovery`);
  },
};
