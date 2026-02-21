import { useCallback, useEffect, useMemo, useState } from "react";
import {
  MAX_COMPARE_PLAYERS,
  buildWatchlistCsv,
  playerWatchEntryFromRow,
  stablePlayerKeyFromRow,
} from "../../../app_state_storage.js";
import { downloadBlob } from "../../../download_helpers.js";

export function useProjectionCollections({ watchlist, setWatchlist, data }) {
  const [compareRowsByKey, setCompareRowsByKey] = useState({});

  useEffect(() => {
    if (!Array.isArray(data) || data.length === 0) return;
    setCompareRowsByKey(current => {
      const keys = Object.keys(current || {});
      if (keys.length === 0) return current;
      const latestByKey = {};
      data.forEach(row => {
        latestByKey[stablePlayerKeyFromRow(row)] = row;
      });
      let changed = false;
      const next = { ...current };
      keys.forEach(key => {
        const latest = latestByKey[key];
        if (latest && next[key] !== latest) {
          next[key] = latest;
          changed = true;
        }
      });
      return changed ? next : current;
    });
  }, [data]);

  const compareRows = useMemo(
    () => Object.values(compareRowsByKey || {}).filter(Boolean),
    [compareRowsByKey]
  );

  const watchlistCount = Object.keys(watchlist).length;

  const isRowWatched = useCallback(row => {
    const key = stablePlayerKeyFromRow(row);
    return Boolean(watchlist[key]);
  }, [watchlist]);

  const toggleRowWatch = useCallback(row => {
    const nextEntry = playerWatchEntryFromRow(row);
    setWatchlist(current => {
      const next = { ...current };
      if (next[nextEntry.key]) {
        delete next[nextEntry.key];
      } else {
        next[nextEntry.key] = nextEntry;
      }
      return next;
    });
  }, [setWatchlist]);

  const removeWatchlistEntry = useCallback(key => {
    setWatchlist(current => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }, [setWatchlist]);

  const clearWatchlist = useCallback(() => {
    setWatchlist({});
  }, [setWatchlist]);

  const exportWatchlistCsv = useCallback(() => {
    const csv = buildWatchlistCsv(watchlist);
    downloadBlob("player-watchlist.csv", csv, "text/csv;charset=utf-8");
  }, [watchlist]);

  const toggleCompareRow = useCallback(row => {
    const key = stablePlayerKeyFromRow(row);
    setCompareRowsByKey(current => {
      if (current[key]) {
        const next = { ...current };
        delete next[key];
        return next;
      }
      if (Object.keys(current).length >= MAX_COMPARE_PLAYERS) return current;
      return { ...current, [key]: row };
    });
  }, []);

  const clearCompareRows = useCallback(() => {
    setCompareRowsByKey({});
  }, []);

  const removeCompareRow = useCallback(key => {
    setCompareRowsByKey(current => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }, []);

  return {
    watchlistCount,
    compareRowsByKey,
    compareRows,
    isRowWatched,
    toggleRowWatch,
    removeWatchlistEntry,
    clearWatchlist,
    exportWatchlistCsv,
    toggleCompareRow,
    clearCompareRows,
    removeCompareRow,
    maxComparePlayers: MAX_COMPARE_PLAYERS,
  };
}
