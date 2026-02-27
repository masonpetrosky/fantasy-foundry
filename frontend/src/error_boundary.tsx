import React from "react";
import { captureException } from "./sentry";

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    captureException(error, { componentStack: errorInfo?.componentStack });
  }

  handleReset = (): void => {
    this.setState({ error: null });
  };

  render(): React.ReactNode {
    if (!this.state.error) return this.props.children;

    const message = String(this.state.error?.message || "").trim() || "An unexpected error occurred.";

    return (
      <div className="error-boundary-panel" role="alert">
        <h2>Something went wrong</h2>
        <p>{message}</p>
        <div className="error-boundary-actions">
          <button type="button" className="inline-btn" onClick={this.handleReset}>
            Try again
          </button>
          <button type="button" className="inline-btn" onClick={() => window.location.reload()}>
            Reload page
          </button>
        </div>
      </div>
    );
  }
}
