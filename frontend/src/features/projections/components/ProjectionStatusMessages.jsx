import React from "react";

export const ProjectionStatusMessages = React.memo(function ProjectionStatusMessages({
  pageResetNotice,
  clearPageResetNotice,
  exportError,
  clearExportError,
  compareShareCopyNotice,
  clearCompareShareCopyNotice,
  compareShareHydrating,
  compareShareNotice,
  clearCompareShareNotice,
  lastRefreshedLabel,
}) {
  if (
    !pageResetNotice
    && !exportError
    && !compareShareCopyNotice
    && !compareShareHydrating
    && !compareShareNotice
    && !lastRefreshedLabel
  ) {
    return null;
  }

  return (
    <>
      {pageResetNotice && (
        <div className="table-refresh-message page-reset-notice" role="status" aria-live="polite">
          <span>{pageResetNotice}</span>
          <button type="button" className="inline-btn" onClick={clearPageResetNotice}>Dismiss</button>
        </div>
      )}
      {exportError && (
        <div className="table-refresh-message error" role="alert" aria-live="assertive">
          <span>Export failed. {exportError}</span>
          <button type="button" className="inline-btn" onClick={clearExportError}>Dismiss</button>
        </div>
      )}
      {compareShareCopyNotice && (
        <div className="table-refresh-message" role="status" aria-live="polite">
          <span>{compareShareCopyNotice}</span>
          {clearCompareShareCopyNotice && (
            <button type="button" className="inline-btn" onClick={clearCompareShareCopyNotice}>Dismiss</button>
          )}
        </div>
      )}
      {compareShareHydrating && (
        <div className="table-refresh-message" role="status" aria-live="polite">
          Loading shared comparison players from link...
        </div>
      )}
      {compareShareNotice && (
        <div
          className={`table-refresh-message ${compareShareNotice.severity === "error" ? "error" : "warning"}`.trim()}
          role={compareShareNotice.severity === "error" ? "alert" : "status"}
          aria-live={compareShareNotice.severity === "error" ? "assertive" : "polite"}
        >
          <span>{compareShareNotice.message}</span>
          {clearCompareShareNotice && (
            <button type="button" className="inline-btn" onClick={clearCompareShareNotice}>Dismiss</button>
          )}
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
