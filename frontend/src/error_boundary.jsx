import React from "react";
import { captureException } from "./sentry.js";

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    captureException(error, { componentStack: errorInfo?.componentStack });
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
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
