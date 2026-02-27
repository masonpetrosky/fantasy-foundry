import React, { Suspense, lazy } from "react";

const LazyProjectionComparisonPanel = lazy(() => (
  import("./ProjectionComparisonPanel.jsx").then(module => ({
    default: module.ProjectionComparisonPanel,
  }))
));
const LazyProjectionWatchlistPanel = lazy(() => (
  import("./ProjectionWatchlistPanel").then(module => ({
    default: module.ProjectionWatchlistPanel,
  }))
));

export const ProjectionCollectionsWorkspace = React.memo(function ProjectionCollectionsWorkspace({
  showCollectionsWorkspace,
  watchlistCount,
  watchlistOnly,
  watchlist,
  watchlistEntries,
  clearWatchlist,
  exportWatchlistCsv,
  removeWatchlistEntry,
  compareRowsCount,
  maxComparePlayers,
  clearCompareRows,
  compareRows,
  comparisonColumns,
  removeCompareRow,
  copyCompareShareLink,
  colLabels,
  formatCellValue,
}) {
  if (!showCollectionsWorkspace) {
    return (
      <div className="collection-toolbar collection-toolbar-hint" role="note">
        Run dynasty rankings first to unlock your watchlist and comparison workspace.
      </div>
    );
  }

  return (
    <>
      <div className="collection-toolbar" role="group" aria-label="Watchlist and comparison actions">
        <span className="collection-toolbar-label">Watchlist: {watchlistCount}</span>
        <span className="collection-toolbar-label">View: {watchlistOnly ? "Watchlist" : "All Players"}</span>
        <button type="button" className="inline-btn" onClick={exportWatchlistCsv} disabled={watchlistCount === 0}>
          Export Watchlist CSV
        </button>
        <button type="button" className="inline-btn" onClick={clearWatchlist} disabled={watchlistCount === 0}>
          Clear Watchlist
        </button>
        <span className="collection-toolbar-label">Compare: {compareRowsCount}/{maxComparePlayers}</span>
        <button type="button" className="inline-btn" onClick={clearCompareRows} disabled={compareRowsCount === 0}>
          Clear Compare
        </button>
        {copyCompareShareLink && (
          <button type="button" className="inline-btn" onClick={copyCompareShareLink} disabled={compareRowsCount === 0}>
            Copy Share Link
          </button>
        )}
      </div>
      {compareRowsCount > 0 && (
        <Suspense fallback={null}>
          <LazyProjectionComparisonPanel
            compareRows={compareRows}
            maxComparePlayers={maxComparePlayers}
            comparisonColumns={comparisonColumns}
            colLabels={colLabels}
            formatCellValue={formatCellValue}
            removeCompareRow={removeCompareRow}
            copyCompareShareLink={copyCompareShareLink}
          />
        </Suspense>
      )}
      {watchlistCount > 0 && (
        <Suspense fallback={null}>
          <LazyProjectionWatchlistPanel
            watchlistCount={watchlistCount}
            watchlist={watchlist}
            watchlistEntries={watchlistEntries}
            removeWatchlistEntry={removeWatchlistEntry}
          />
        </Suspense>
      )}
    </>
  );
});
