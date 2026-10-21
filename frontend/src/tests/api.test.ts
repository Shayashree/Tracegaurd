import { describe, it, expect, vi, beforeEach } from "vitest";
import { api, ApiError } from "../api/client";

describe("Frontend API Client Test Suite", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("handles getHealth success response", async () => {
    const mockHealth = {
      status: "ok",
      version: "0.4.0",
      service: "traceguard-platform",
      model_adapter: "mock",
      default_max_steps: 10,
    };

    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: {
        get: () => "application/json",
      },
      json: async () => mockHealth,
    });

    const res = await api.getHealth();
    expect(res.status).toBe("ok");
    expect(res.model_adapter).toBe("mock");
  });

  it("throws structured ApiError on 404 or backend failure", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      headers: {
        get: () => "application/json",
      },
      json: async () => ({ detail: "Experiment 'exp_missing' not found." }),
    });

    await expect(api.getExperiment("exp_missing")).rejects.toThrow(ApiError);
  });

  it("constructs correct query parameters for getExperiments", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: async () => [],
    });
    globalThis.fetch = fetchSpy;

    await api.getExperiments({ limit: 10, offset: 20, mode: "traceguard_recovery", status: "completed" });
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/experiments?limit=10&offset=20&mode=traceguard_recovery&status=completed",
      expect.anything()
    );
  });

  it("submits POST payload for runExperiment correctly", async () => {
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: async () => ({
        experiment_id: "exp_123",
        status: "running",
        total_tasks: 5,
        completed_tasks: 0,
      }),
    });
    globalThis.fetch = fetchSpy;

    await api.runExperiment({
      benchmark_version: "v1.0",
      agent_mode: "traceguard_recovery",
      repetitions: 2,
      max_steps: 12,
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/experiments/run",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          benchmark_version: "v1.0",
          agent_mode: "traceguard_recovery",
          repetitions: 2,
          max_steps: 12,
        }),
      })
    );
  });

  it("generates correct export URLs for trace and experiment", () => {
    const traceUrl = api.getTaskTraceExportUrl("task_add_01");
    expect(traceUrl).toContain("/tasks/task_add_01/traces/export");

    const expUrl = api.getExperimentExportUrl("exp_001", "jsonl");
    expect(expUrl).toContain("/experiments/exp_001/export?format=jsonl");
  });
});
