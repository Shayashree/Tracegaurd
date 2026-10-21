import { describe, it, vi } from "vitest";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OverviewPage } from "../pages/OverviewPage";
import { ExperimentsPage } from "../pages/ExperimentsPage";
import { RunExperimentPage } from "../pages/RunExperimentPage";
import { TracesPage } from "../pages/TracesPage";
import { DiagnosticsPage } from "../pages/DiagnosticsPage";
import { RecoveryAnalysisPage } from "../pages/RecoveryAnalysisPage";
import { StrategyComparisonPage } from "../pages/StrategyComparisonPage";
import { ResearchEvaluationPage } from "../pages/ResearchEvaluationPage";
import { ReportsPage } from "../pages/ReportsPage";
import { SettingsPage } from "../pages/SettingsPage";

vi.mock("../api/client", () => ({
  api: {
    getHealth: vi.fn().mockResolvedValue({ status: "ok", database_status: "connected" }),
    getOverviewStats: vi.fn().mockResolvedValue({}),
    getExperiments: vi.fn().mockResolvedValue([]),
    getExperiment: vi.fn().mockResolvedValue({}),
    getBenchmarks: vi.fn().mockResolvedValue([]),
    getBenchmarkTasks: vi.fn().mockResolvedValue([]),
    getDiagnostics: vi.fn().mockResolvedValue([]),
    getDetectorConfig: vi.fn().mockResolvedValue({}),
    getRecoveryReports: vi.fn().mockResolvedValue([]),
    getTaskTraces: vi.fn().mockResolvedValue([]),
    getExperimentComparisons: vi.fn().mockResolvedValue([]),
    getExperimentFailureAnalysis: vi.fn().mockResolvedValue({}),
    getExperimentAblation: vi.fn().mockResolvedValue({}),
    getExperimentDetectorMetrics: vi.fn().mockResolvedValue({}),
    getExperimentReport: vi.fn().mockResolvedValue({}),
    getExperimentManifest: vi.fn().mockResolvedValue({}),
    getTaskTraceExportUrl: vi.fn().mockReturnValue(""),
    getExperimentExportUrl: vi.fn().mockReturnValue(""),
  },
}));

describe("All Pages Render Test", () => {
  it("renders OverviewPage without crashing", () => {
    render(<MemoryRouter><OverviewPage /></MemoryRouter>);
  });
  it("renders ExperimentsPage without crashing", () => {
    render(<MemoryRouter><ExperimentsPage /></MemoryRouter>);
  });
  it("renders RunExperimentPage without crashing", () => {
    render(<MemoryRouter><RunExperimentPage /></MemoryRouter>);
  });
  it("renders TracesPage without crashing", () => {
    render(<MemoryRouter><TracesPage /></MemoryRouter>);
  });
  it("renders DiagnosticsPage without crashing", () => {
    render(<MemoryRouter><DiagnosticsPage /></MemoryRouter>);
  });
  it("renders RecoveryAnalysisPage without crashing", () => {
    render(<MemoryRouter><RecoveryAnalysisPage /></MemoryRouter>);
  });
  it("renders StrategyComparisonPage without crashing", () => {
    render(<MemoryRouter><StrategyComparisonPage /></MemoryRouter>);
  });
  it("renders ResearchEvaluationPage without crashing", () => {
    render(<MemoryRouter><ResearchEvaluationPage /></MemoryRouter>);
  });
  it("renders ReportsPage without crashing", () => {
    render(<MemoryRouter><ReportsPage /></MemoryRouter>);
  });
  it("renders SettingsPage without crashing", () => {
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
  });
});
