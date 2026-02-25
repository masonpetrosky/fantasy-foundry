import { useMemo } from "react";

export function buildSortedWatchlistEntries(watchlist, limit = 40) {
  return Object.values(watchlist || {})
    .filter(entry => entry && typeof entry === "object")
    .sort((a, b) => String(a.player || "").localeCompare(String(b.player || "")))
    .slice(0, Math.max(0, Number(limit) || 0));
}

export function useProjectionWatchlistComposition({
  collections,
  watchlist,
}) {
  const sortedWatchlistEntries = useMemo(
    () => buildSortedWatchlistEntries(watchlist, 40),
    [watchlist]
  );

  return {
    watchlistCount: collections.watchlistCount,
    watchlist,
    sortedWatchlistEntries,
    isRowWatched: collections.isRowWatched,
    toggleRowWatch: collections.toggleRowWatch,
    removeWatchlistEntry: collections.removeWatchlistEntry,
    clearWatchlist: collections.clearWatchlist,
    exportWatchlistCsv: collections.exportWatchlistCsv,
    quickAddRow: collections.quickAddRow,
    workspaceHasWatchlistActivity: collections.watchlistCount > 0,
  };
}
