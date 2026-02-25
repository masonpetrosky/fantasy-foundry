import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { trackEvent } from "../../../analytics.js";
import {
  MAX_COMPARE_PLAYERS,
  buildWatchlistCsv,
  playerWatchEntryFromRow,
  stablePlayerKeyFromRow,
} from "../../../app_state_storage.js";
import { downloadBlob } from "../../../download_helpers.js";

function parseCompareKeysFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("compare") || "";
    return raw
      .split(",")
      .map(k => k.trim().toLowerCase())
      .filter(Boolean);
  } catch {
    return [];
  }
}

export function useProjectionCollections({ watchlist, setWatchlist, data }) {
  const [compareRowsByKey, setCompareRowsByKey] = useState({});
  const pendingCompareKeys = useRef(parseCompareKeysFromUrl());

  // Seed compare rows from URL param on first data load
  useEffect(() => {
    if (!Array.isArray(data) || data.length === 0) return;
    const pending = pendingCompareKeys.current;
    if (pending.length === 0) return;
    pendingCompareKeys.current = [];
    const seeds = {};
    data.forEach(row => {
      const key = stablePlayerKeyFromRow(row);
      if (pending.includes(key.toLowerCase()) && Object.keys(seeds).length < MAX_COMPARE_PLAYERS) {
        seeds[key] = row;
      }
    });
    if (Object.keys(seeds).length > 0) {
      setCompareRowsByKey(seeds);
    }
  }, [data]);

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

  const quickAddRow = useCallback(row => {
    const key = stablePlayerKeyFromRow(row);
    const nextEntry = playerWatchEntryFromRow(row);
    const alreadyWatched = Boolean(watchlist[key]);
    if (!alreadyWatched) {
      setWatchlist(current => ({ ...current, [nextEntry.key]: nextEntry }));
    }

    const alreadyCompared = Boolean(compareRowsByKey[key]);
    const compareAtCapacity = Object.keys(compareRowsByKey).length >= MAX_COMPARE_PLAYERS;
    const addedCompare = !alreadyCompared && !compareAtCapacity;
    if (addedCompare) {
      setCompareRowsByKey(current => ({ ...current, [key]: row }));
    }

    trackEvent("ff_compare_quick_add", {
      player_key: key,
      added_watchlist: !alreadyWatched,
      added_compare: addedCompare,
      compare_capacity_reached: !alreadyCompared && compareAtCapacity,
    });
  }, [compareRowsByKey, setWatchlist, watchlist]);

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
    quickAddRow,
    clearCompareRows,
    removeCompareRow,
    maxComparePlayers: MAX_COMPARE_PLAYERS,
  };
}
