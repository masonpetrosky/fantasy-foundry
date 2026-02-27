import { useMemo } from "react";
import type { PlayerWatchEntry, ProjectionRow } from "../../../app_state_storage";

export interface WatchlistCollections {
  watchlistCount: number;
  isRowWatched: (row: ProjectionRow) => boolean;
  toggleRowWatch: (row: ProjectionRow) => void;
  removeWatchlistEntry: (key: string) => void;
  clearWatchlist: () => void;
  exportWatchlistCsv: () => void;
  quickAddRow: (row: ProjectionRow) => void;
}

export function buildSortedWatchlistEntries(
  watchlist: Record<string, PlayerWatchEntry | null | undefined> | null | undefined,
  limit = 40,
): PlayerWatchEntry[] {
  return Object.values(watchlist || {})
    .filter((entry): entry is PlayerWatchEntry => entry != null && typeof entry === "object")
    .sort((a, b) => String(a.player || "").localeCompare(String(b.player || "")))
    .slice(0, Math.max(0, Number(limit) || 0));
}

export interface UseProjectionWatchlistCompositionInput {
  collections: WatchlistCollections;
  watchlist: Record<string, PlayerWatchEntry>;
}

export interface UseProjectionWatchlistCompositionResult {
  watchlistCount: number;
  watchlist: Record<string, PlayerWatchEntry>;
  sortedWatchlistEntries: PlayerWatchEntry[];
  isRowWatched: (row: ProjectionRow) => boolean;
  toggleRowWatch: (row: ProjectionRow) => void;
  removeWatchlistEntry: (key: string) => void;
  clearWatchlist: () => void;
  exportWatchlistCsv: () => void;
  quickAddRow: (row: ProjectionRow) => void;
  workspaceHasWatchlistActivity: boolean;
}

export function useProjectionWatchlistComposition({
  collections,
  watchlist,
}: UseProjectionWatchlistCompositionInput): UseProjectionWatchlistCompositionResult {
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
