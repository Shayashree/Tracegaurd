import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { StatusBadge } from "../components/common/StatusBadge";
import { MetricCard } from "../components/common/MetricCard";
import { EmptyState } from "../components/common/EmptyState";
import { Sidebar } from "../components/layout/Sidebar";

describe("Frontend Components Test Suite", () => {
  it("renders StatusBadge with green color scheme for verified status", () => {
    const { container } = render(<StatusBadge status="verified" />);
    expect(screen.getByText("verified")).toBeDefined();
    expect(container.firstChild).toHaveProperty("className");
    const classNames = (container.firstChild as HTMLElement).className;
    expect(classNames).toContain("bg-emerald-50");
  });

  it("renders StatusBadge with amber color scheme for suspected/warning status", () => {
    const { container } = render(<StatusBadge status="warning" />);
    expect(screen.getByText("warning")).toBeDefined();
    const classNames = (container.firstChild as HTMLElement).className;
    expect(classNames).toContain("bg-amber-50");
  });

  it("renders StatusBadge with rose color scheme for failure_detected status", () => {
    const { container } = render(<StatusBadge status="failure_detected" />);
    expect(screen.getByText("failure detected")).toBeDefined();
    const classNames = (container.firstChild as HTMLElement).className;
    expect(classNames).toContain("bg-rose-50");
  });

  it("renders MetricCard correctly with label, value, and subtext", () => {
    render(
      <MetricCard
        label="Success Rate"
        value="87.5%"
        subtext="Evaluated over 44 runs"
      />
    );
    expect(screen.getByText("Success Rate")).toBeDefined();
    expect(screen.getByText("87.5%")).toBeDefined();
    expect(screen.getByText("Evaluated over 44 runs")).toBeDefined();
  });

  it("renders EmptyState with custom title and action button", () => {
    let clicked = false;
    render(
      <EmptyState
        title="No Experiments"
        description="Run a new evaluation experiment."
        actionText="Create Experiment"
        onAction={() => {
          clicked = true;
        }}
      />
    );
    expect(screen.getByText("No Experiments")).toBeDefined();
    expect(screen.getByText("Run a new evaluation experiment.")).toBeDefined();
    const btn = screen.getByText("Create Experiment");
    btn.click();
    expect(clicked).toBe(true);
  });

  it("renders Sidebar navigation with all 10 core pages", () => {
    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );
    expect(screen.getByText("Overview")).toBeDefined();
    expect(screen.getByText("Experiments")).toBeDefined();
    expect(screen.getByText("Run Experiment")).toBeDefined();
    expect(screen.getByText("Execution Traces")).toBeDefined();
    expect(screen.getByText("Failure Diagnostics")).toBeDefined();
    expect(screen.getByText("Recovery Analysis")).toBeDefined();
    expect(screen.getByText("Strategy Comparison")).toBeDefined();
    expect(screen.getByText("Research Evaluation")).toBeDefined();
    expect(screen.getByText("Reports & Exports")).toBeDefined();
    expect(screen.getByText("Settings & Config")).toBeDefined();
  });
});
