import React, { useMemo } from "react";

interface WatchlistEntry {
  key: string;
  player: string;
  team?: string;
  pos?: string;
}

interface WatchlistRecord {
  player?: string;
  [key: string]: unknown;
}

interface ProjectionWatchlistPanelProps {
  watchlistCount: number;
  watchlist: Record<string, WatchlistRecord>;
  watchlistEntries?: WatchlistEntry[] | null;
  removeWatchlistEntry: (key: string) => void;
}

export const ProjectionWatchlistPanel = React.memo(function ProjectionWatchlistPanel({
  watchlistCount,
  watchlist,
  watchlistEntries,
  removeWatchlistEntry,
}: ProjectionWatchlistPanelProps): React.ReactElement | null {
  const sortedEntries = useMemo((): WatchlistEntry[] => (
    Array.isArray(watchlistEntries)
      ? watchlistEntries
      : Object.values(watchlist)
        .sort((a, b) => String(a.player || "").localeCompare(String(b.player || "")))
        .map(entry => entry as unknown as WatchlistEntry)
        .slice(0, 40)
  ), [watchlist, watchlistEntries]);
  if (watchlistCount === 0) return null;

  return (
    <div className="watchlist-panel" role="region" aria-label="Saved watchlist">
      <div className="watchlist-panel-head">
        <strong>Saved Watchlist</strong>
        <span>{watchlistCount} players</span>
      </div>
      <div className="watchlist-chip-grid">
        {sortedEntries.map(entry => (
          <div key={entry.key} className="watchlist-chip">
            <span>{entry.player}</span>
            <small>{entry.team || "\u2014"} · {entry.pos || "\u2014"}</small>
            <button type="button" onClick={() => removeWatchlistEntry(entry.key)} aria-label={`Remove ${entry.player}`}>
              ×
            </button>
          </div>
        ))}
      </div>
      {watchlistCount > 40 && <p className="calc-note">Showing first 40 watchlist entries.</p>}
    </div>
  );
});
