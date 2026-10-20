import React, { type ReactNode } from "react";

interface MetricCardProps {
  label: string;
  value: string | number;
  subtext?: string;
  icon?: ReactNode;
  badge?: ReactNode;
  trend?: {
    text: string;
    positive?: boolean;
  };
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  icon,
  badge,
  trend,
}) => {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-xs hover:border-slate-300 transition-colors flex flex-col justify-between">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wider text-slate-500">
          {label}
        </p>
        {icon && <div className="text-slate-400 p-1 bg-slate-50 rounded">{icon}</div>}
      </div>
      <div className="mt-3">
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-semibold tracking-tight text-slate-900">
            {value}
          </span>
          {badge}
        </div>
        {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
        {trend && (
          <p
            className={`text-xs mt-1 font-medium ${
              trend.positive ? "text-emerald-600" : "text-rose-600"
            }`}
          >
            {trend.text}
          </p>
        )}
      </div>
    </div>
  );
};
