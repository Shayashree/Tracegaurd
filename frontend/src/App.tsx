import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { OverviewPage } from "./pages/OverviewPage";
import { ExperimentsPage } from "./pages/ExperimentsPage";
import { RunExperimentPage } from "./pages/RunExperimentPage";
import { TracesPage } from "./pages/TracesPage";
import { DiagnosticsPage } from "./pages/DiagnosticsPage";
import { RecoveryAnalysisPage } from "./pages/RecoveryAnalysisPage";
import { StrategyComparisonPage } from "./pages/StrategyComparisonPage";
import { ResearchEvaluationPage } from "./pages/ResearchEvaluationPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SettingsPage } from "./pages/SettingsPage";

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppLayout />}>
          <Route index element={<OverviewPage />} />
          <Route path="experiments" element={<ExperimentsPage />} />
          <Route path="run-experiment" element={<RunExperimentPage />} />
          <Route path="traces" element={<TracesPage />} />
          <Route path="diagnostics" element={<DiagnosticsPage />} />
          <Route path="recovery" element={<RecoveryAnalysisPage />} />
          <Route path="comparison" element={<StrategyComparisonPage />} />
          <Route path="evaluation" element={<ResearchEvaluationPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
