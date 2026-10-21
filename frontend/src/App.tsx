import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
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
      <ErrorBoundary fallbackTitle="Application Shell Error">
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<ErrorBoundary fallbackTitle="Overview Error"><OverviewPage /></ErrorBoundary>} />
            <Route path="experiments" element={<ErrorBoundary fallbackTitle="Experiments Error"><ExperimentsPage /></ErrorBoundary>} />
            <Route path="run-experiment" element={<ErrorBoundary fallbackTitle="Run Experiment Error"><RunExperimentPage /></ErrorBoundary>} />
            <Route path="traces" element={<ErrorBoundary fallbackTitle="Traces Error"><TracesPage /></ErrorBoundary>} />
            <Route path="diagnostics" element={<ErrorBoundary fallbackTitle="Diagnostics Error"><DiagnosticsPage /></ErrorBoundary>} />
            <Route path="recovery" element={<ErrorBoundary fallbackTitle="Recovery Analysis Error"><RecoveryAnalysisPage /></ErrorBoundary>} />
            <Route path="comparison" element={<ErrorBoundary fallbackTitle="Strategy Comparison Error"><StrategyComparisonPage /></ErrorBoundary>} />
            <Route path="evaluation" element={<ErrorBoundary fallbackTitle="Research Evaluation Error"><ResearchEvaluationPage /></ErrorBoundary>} />
            <Route path="reports" element={<ErrorBoundary fallbackTitle="Reports Error"><ReportsPage /></ErrorBoundary>} />
            <Route path="settings" element={<ErrorBoundary fallbackTitle="Settings Error"><SettingsPage /></ErrorBoundary>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  );
};

export default App;
