export function ProjectionWatchlistPanel({ watchlistCount, watchlist, removeWatchlistEntry }) {
  if (watchlistCount === 0) return null;

  return (
    <div className="watchlist-panel" role="region" aria-label="Saved watchlist">
      <div className="watchlist-panel-head">
        <strong>Saved Watchlist</strong>
        <span>{watchlistCount} players</span>
      </div>
      <div className="watchlist-chip-grid">
        {Object.values(watchlist)
          .sort((a, b) => String(a.player || "").localeCompare(String(b.player || "")))
          .slice(0, 40)
          .map(entry => (
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
}
