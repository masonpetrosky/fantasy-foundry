import React from "react";

export const ProjectionStatusMessages = React.memo(function ProjectionStatusMessages({
  pageResetNotice,
  clearPageResetNotice,
  exportError,
  clearExportError,
  lastRefreshedLabel,
}) {
  if (!pageResetNotice && !exportError && !lastRefreshedLabel) return null;

  return (
    <>
      {pageResetNotice && (
        <div className="table-refresh-message page-reset-notice" role="status" aria-live="polite">
          <span>{pageResetNotice}</span>
          <button type="button" className="inline-btn" onClick={clearPageResetNotice}>Dismiss</button>
        </div>
      )}
      {exportError && (
        <div className="table-refresh-message error" role="status" aria-live="polite">
          <span>Export failed. {exportError}</span>
          <button type="button" className="inline-btn" onClick={clearExportError}>Dismiss</button>
        </div>
      )}
      {lastRefreshedLabel && (
        <div className="table-refresh-message table-last-refreshed" role="status" aria-live="polite">
          Data last refreshed at {lastRefreshedLabel}.
        </div>
      )}
    </>
  );
});
