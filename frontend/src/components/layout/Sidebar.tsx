import React from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  FlaskConical,
  PlayCircle,
  GitCommitVertical,
  ShieldAlert,
  LifeBuoy,
  Scale,
  Microscope,
  FileText,
  Settings,
  ShieldCheck,
} from "lucide-react";

interface NavItem {
  name: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { name: "Overview", path: "/", icon: LayoutDashboard },
  { name: "Experiments", path: "/experiments", icon: FlaskConical },
  { name: "Run Experiment", path: "/run-experiment", icon: PlayCircle },
  { name: "Execution Traces", path: "/traces", icon: GitCommitVertical },
  { name: "Failure Diagnostics", path: "/diagnostics", icon: ShieldAlert },
  { name: "Recovery Analysis", path: "/recovery", icon: LifeBuoy },
  { name: "Strategy Comparison", path: "/comparison", icon: Scale },
  { name: "Research Evaluation", path: "/evaluation", icon: Microscope },
  { name: "Reports & Exports", path: "/reports", icon: FileText },
  { name: "Settings & Config", path: "/settings", icon: Settings },
];

export const Sidebar: React.FC = () => {
  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0 min-h-screen border-r border-slate-800">
      {/* Brand Header */}
      <div className="h-16 flex items-center gap-3 px-5 border-b border-slate-800 bg-slate-950/40">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-xs">
          <ShieldCheck className="w-5 h-5" />
        </div>
        <div>
          <span className="font-bold text-base text-white tracking-tight">TraceGuard</span>
          <span className="text-2xs block text-slate-400 font-mono">Reliability & Recovery</span>
        </div>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        <div className="px-3 pb-2 text-2xs font-semibold uppercase tracking-wider text-slate-400">
          Research Platform
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.path === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-600 text-white shadow-xs font-semibold"
                    : "text-slate-300 hover:text-white hover:bg-slate-800/70"
                }`
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.name}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Footer / Build info */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/30 text-xs text-slate-400">
        <div className="flex items-center justify-between mb-1">
          <span className="font-medium text-slate-300">Milestone 6</span>
          <span className="inline-block px-1.5 py-0.5 rounded text-2xs bg-slate-800 text-slate-300 font-mono">
            v0.4.0
          </span>
        </div>
        <p className="text-2xs text-slate-400 leading-tight">
          Evidence-Driven Reliability &amp; Recovery Platform
        </p>
      </div>
    </aside>
  );
};
