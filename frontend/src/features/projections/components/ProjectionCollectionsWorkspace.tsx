import React, { Suspense, lazy } from "react";
import type { ProjectionRow } from "../../../app_state_storage";
import type { PlayerWatchEntry } from "../../../app_state_storage";

const LazyProjectionComparisonPanel = lazy(() => (
  import("./ProjectionComparisonPanel").then(module => ({
    default: module.ProjectionComparisonPanel,
  }))
));
const LazyProjectionWatchlistPanel = lazy(() => (
  import("./ProjectionWatchlistPanel").then(module => ({
    default: module.ProjectionWatchlistPanel,
  }))
));

interface WatchlistRecord {
  player?: string;
  [key: string]: unknown;
}

interface ProjectionCollectionsWorkspaceProps {
  showCollectionsWorkspace: boolean;
  watchlistCount: number;
  watchlistOnly: boolean;
  watchlist: Record<string, WatchlistRecord>;
  watchlistEntries: PlayerWatchEntry[];
  clearWatchlist: () => void;
  exportWatchlistCsv: () => void;
  removeWatchlistEntry: (key: string) => void;
  compareRowsCount: number;
  maxComparePlayers: number;
  clearCompareRows: () => void;
  compareRows: ProjectionRow[];
  comparisonColumns: string[];
  removeCompareRow: (key: string) => void;
  copyCompareShareLink?: (() => void) | null;
  colLabels: Record<string, string>;
  formatCellValue: (col: string, val: unknown) => string;
}

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
}: ProjectionCollectionsWorkspaceProps): React.ReactElement {
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
