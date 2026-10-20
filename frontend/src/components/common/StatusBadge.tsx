import React from "react";

interface StatusBadgeProps {
  status: string | null | undefined;
  size?: "sm" | "md";
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, size = "md" }) => {
  if (!status) {
    return <span className="text-slate-400 italic text-xs">unknown</span>;
  }

  const s = status.toLowerCase();

  // Green (verified success)
  const isGreen =
    s === "verified" ||
    s === "successful_completion" ||
    s === "recovered_successfully" ||
    s === "success_without_recovery" ||
    s === "healthy" ||
    s === "confirmed" ||
    s === "completed";

  // Amber (warnings / in-progress / bounded halts)
  const isAmber =
    s === "warning" ||
    s === "step_limit_reached" ||
    s === "step_limit_exhaustion" ||
    s === "timeout" ||
    s === "suspected" ||
    s === "running" ||
    s === "unresolved" ||
    s === "budget_exhausted" ||
    s === "medium";

  // Red (confirmed failure / critical error)
  const isRed =
    s === "failed" ||
    s === "incorrect_answer" ||
    s === "tool_error" ||
    s === "failure_detected" ||
    s === "failed_after_recovery" ||
    s === "critical" ||
    s === "high";

  let colorClasses = "bg-slate-100 text-slate-700 border-slate-200";
  if (isGreen) {
    colorClasses = "bg-emerald-50 text-emerald-700 border-emerald-200";
  } else if (isAmber) {
    colorClasses = "bg-amber-50 text-amber-800 border-amber-200";
  } else if (isRed) {
    colorClasses = "bg-rose-50 text-rose-700 border-rose-200";
  }

  const padding = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs font-medium";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border ${padding} ${colorClasses} tracking-tight font-mono capitalize`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          isGreen
            ? "bg-emerald-500"
            : isAmber
            ? "bg-amber-500"
            : isRed
            ? "bg-rose-500"
            : "bg-slate-400"
        }`}
      />
      {status.replace(/_/g, " ")}
    </span>
  );
};
