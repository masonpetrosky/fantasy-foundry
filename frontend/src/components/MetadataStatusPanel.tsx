import React from "react";

export interface MetadataStatusPanelProps {
  metaLoading: boolean;
  metaError: string;
  metaReady: boolean;
  onRetry: () => void;
  onOpenMethodology: () => void;
}

export function MetadataStatusPanel({
  metaLoading,
  metaError,
  metaReady,
  onRetry,
  onOpenMethodology,
}: MetadataStatusPanelProps): React.ReactElement | null {
  if (metaLoading && !metaError && !metaReady) {
    return <p className="methodology-note" role="status" aria-live="polite">Loading projections metadata...</p>;
  }

  if (!metaError) {
    return null;
  }

  return (
    <section className="meta-error-panel" role="alert" aria-live="assertive">
      <h2>Unable to load projections metadata</h2>
      <p>{metaError}</p>
      <p>Try reloading metadata now. If this keeps failing, check backend readiness at <code>/api/ready</code>.</p>
      <div className="meta-error-actions">
        <button type="button" className="inline-btn" onClick={onRetry}>
          Retry metadata request
        </button>
        <button type="button" className="inline-btn" onClick={onOpenMethodology}>
          Open Methodology
        </button>
      </div>
    </section>
  );
}
