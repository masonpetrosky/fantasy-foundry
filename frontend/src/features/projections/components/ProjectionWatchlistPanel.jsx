import React, { useMemo } from "react";

export const ProjectionWatchlistPanel = React.memo(function ProjectionWatchlistPanel({
  watchlistCount,
  watchlist,
  watchlistEntries,
  removeWatchlistEntry,
}) {
  const sortedEntries = useMemo(() => (
    Array.isArray(watchlistEntries)
      ? watchlistEntries
      : Object.values(watchlist)
        .sort((a, b) => String(a.player || "").localeCompare(String(b.player || "")))
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
            <small>{entry.team || "—"} · {entry.pos || "—"}</small>
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
