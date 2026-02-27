import React from "react";
import { captureException } from "./sentry.js";

export class FeatureErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, errorInfo) {
    captureException(error, {
      feature: this.props.featureName,
      componentStack: errorInfo?.componentStack,
    });
  }

  handleReset = () => {
    this.setState({ error: null });
  };

  render() {
    if (!this.state.error) return this.props.children;

    const featureName = this.props.featureName || "This feature";
    const message = String(this.state.error?.message || "").trim() || "An unexpected error occurred.";

    return (
      <div className="error-boundary-panel" role="alert">
        <h2>{featureName} encountered an error</h2>
        <p>{message}</p>
        <div className="error-boundary-actions">
          <button type="button" className="inline-btn" onClick={this.handleReset}>
            Try again
          </button>
        </div>
      </div>
    );
  }
}
