import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertOctagon, RotateCcw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("TraceGuard UI Error Boundary caught an error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 max-w-2xl mx-auto my-8 bg-white rounded-lg border border-rose-200 shadow-sm text-center">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-rose-50 flex items-center justify-center text-rose-600">
            <AlertOctagon className="w-6 h-6" />
          </div>
          <h2 className="text-lg font-bold text-slate-900 mb-2">
            {this.props.fallbackTitle || "Something went wrong loading this tab"}
          </h2>
          <p className="text-xs text-slate-600 mb-4 font-mono bg-slate-50 p-3 rounded border border-slate-200 overflow-x-auto text-left">
            {this.state.error?.message || "An unexpected rendering error occurred."}
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-md shadow-xs transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" /> Retry Tab
            </button>
            <a
              href="/"
              className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-md transition-colors"
            >
              Return to Overview
            </a>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
