import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { trackEvent } from "../../../analytics.js";
import {
  MAX_COMPARE_PLAYERS,
  buildWatchlistCsv,
  playerWatchEntryFromRow,
  stablePlayerKeyFromRow,
} from "../../../app_state_storage.js";
import { downloadBlob } from "../../../download_helpers.js";

const CAREER_TOTALS_FILTER_VALUE = "__career_totals__";

function normalizeCompareKey(value) {
  return String(value || "").trim().toLowerCase();
}

function parseCompareKeysFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("compare") || "";
    const deduped = [];
    const seen = new Set();
    raw
      .split(",")
      .map(token => normalizeCompareKey(token))
      .filter(Boolean)
      .forEach(token => {
        if (seen.has(token)) return;
        seen.add(token);
        deduped.push(token);
      });
    return deduped.slice(0, MAX_COMPARE_PLAYERS);
  } catch {
    return [];
  }
}

function coerceRowYear(value) {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return Math.round(parsed);
}

function rowCompareIdentityKeys(row) {
  const keys = new Set();
  const entityKey = normalizeCompareKey(row?.PlayerEntityKey);
  const playerKey = normalizeCompareKey(row?.PlayerKey);
  const stableKey = normalizeCompareKey(stablePlayerKeyFromRow(row));
  if (entityKey) keys.add(entityKey);
  if (playerKey) keys.add(playerKey);
  if (stableKey) keys.add(stableKey);
  return keys;
}

function pickPreferredCompareRow(rows, { careerTotalsView, resolvedYearFilter }) {
  if (!Array.isArray(rows) || rows.length === 0) return null;
  if (careerTotalsView) {
    const careerRows = rows.filter(row => row && (row.Years != null || row.YearStart != null || row.YearEnd != null));
    if (careerRows.length > 0) return careerRows[0];
    return rows[0];
  }

  const yearFilter = String(resolvedYearFilter || "").trim();
  if (yearFilter && yearFilter !== CAREER_TOTALS_FILTER_VALUE) {
    const exactYearRow = rows.find(row => String(row?.Year ?? "").trim() === yearFilter);
    if (exactYearRow) return exactYearRow;
  }

  let latestRow = null;
  let latestYear = Number.NEGATIVE_INFINITY;
  rows.forEach(row => {
    const year = coerceRowYear(row?.Year);
    if (year != null && year > latestYear) {
      latestYear = year;
      latestRow = row;
    }
  });
  return latestRow || rows[0];
}

function profilePayloadRows(payload, { careerTotalsView }) {
  if (!payload || typeof payload !== "object") return [];
  if (careerTotalsView) {
    if (Array.isArray(payload.career_totals) && payload.career_totals.length > 0) {
      return payload.career_totals;
    }
  } else if (Array.isArray(payload.series) && payload.series.length > 0) {
    return payload.series;
  }
  return Array.isArray(payload.data) ? payload.data : [];
}

function mergeCompareRowsWithCap(current, rows) {
  const next = { ...(current || {}) };
  let count = Object.keys(next).length;
  rows.forEach(row => {
    if (!row || typeof row !== "object") return;
    const key = stablePlayerKeyFromRow(row);
    if (!key) return;
    if (next[key]) {
      next[key] = row;
      return;
    }
    if (count >= MAX_COMPARE_PLAYERS) return;
    next[key] = row;
    count += 1;
  });
  return next;
}

export function resolveCompareShareHydrationNotice({
  requestedKeys,
  matchedKeys,
}) {
  const requested = Array.isArray(requestedKeys)
    ? requestedKeys.map(token => normalizeCompareKey(token)).filter(Boolean)
    : [];
  if (requested.length === 0) return null;

  const matched = new Set(
    Array.isArray(matchedKeys)
      ? matchedKeys.map(token => normalizeCompareKey(token)).filter(Boolean)
      : []
  );
  const unresolved = requested.filter(key => !matched.has(key));
  if (unresolved.length === 0) return null;

  const resolvedCount = requested.length - unresolved.length;
  const preview = unresolved.slice(0, 3).join(", ");
  const previewSuffix = unresolved.length > 3 ? ` (+${unresolved.length - 3} more)` : "";
  if (resolvedCount > 0) {
    return {
      severity: "warning",
      message: `Loaded ${resolvedCount}/${requested.length} shared comparison players. Missing: ${preview}${previewSuffix}.`,
    };
  }
  return {
    severity: "error",
    message: `Unable to load shared comparison players from link. Missing: ${preview}${previewSuffix}.`,
  };
}

export function resolveProjectionDataset(tab) {
  if (tab === "bat" || tab === "pitch") return tab;
  return "all";
}

export function buildProjectionCompareHydrationRequest({
  apiBase,
  compareKeys,
  tab,
  careerTotalsView,
  resolvedYearFilter,
  calculatorJobId,
}) {
  const base = String(apiBase || "").trim().replace(/\/+$/, "");
  const requestedKeys = Array.isArray(compareKeys)
    ? compareKeys.map(token => normalizeCompareKey(token)).filter(Boolean)
    : [];
  if (!base || requestedKeys.length < 2) return "";

  const url = new URL(`${base}/api/projections/compare`);
  url.searchParams.set("player_keys", requestedKeys.join(","));
  url.searchParams.set("dataset", resolveProjectionDataset(tab));
  url.searchParams.set("career_totals", careerTotalsView ? "true" : "false");
  const normalizedYearFilter = String(resolvedYearFilter || "").trim();
  if (!careerTotalsView && normalizedYearFilter && normalizedYearFilter !== CAREER_TOTALS_FILTER_VALUE) {
    url.searchParams.set("year", normalizedYearFilter);
  }
  url.searchParams.set("include_dynasty", "true");
  const normalizedCalculatorJobId = String(calculatorJobId || "").trim();
  if (normalizedCalculatorJobId) {
    url.searchParams.set("calculator_job_id", normalizedCalculatorJobId);
  }
  return url.toString();
}

export function selectHydratedCompareRows({
  rows,
  requestedKeys,
  careerTotalsView,
  resolvedYearFilter,
}) {
  const normalizedRequestedKeys = Array.isArray(requestedKeys)
    ? requestedKeys.map(token => normalizeCompareKey(token)).filter(Boolean)
    : [];
  if (!Array.isArray(rows) || rows.length === 0 || normalizedRequestedKeys.length === 0) {
    return {};
  }

  const candidatesByKey = new Map();
  rows.forEach(row => {
    rowCompareIdentityKeys(row).forEach(identityKey => {
      const candidates = candidatesByKey.get(identityKey) || [];
      candidates.push(row);
      candidatesByKey.set(identityKey, candidates);
    });
  });

  const selectedRowsByKey = {};
  normalizedRequestedKeys.forEach(requestedKey => {
    const candidates = candidatesByKey.get(requestedKey);
    const selectedRow = pickPreferredCompareRow(candidates, {
      careerTotalsView: Boolean(careerTotalsView),
      resolvedYearFilter,
    });
    if (!selectedRow) return;
    selectedRowsByKey[stablePlayerKeyFromRow(selectedRow)] = selectedRow;
  });
  return selectedRowsByKey;
}

export function useProjectionCollections({
  watchlist,
  setWatchlist,
  data,
  apiBase,
  tab,
  careerTotalsView,
  resolvedYearFilter,
  calculatorJobId,
}) {
  const [compareRowsByKey, setCompareRowsByKey] = useState({});
  const [compareShareHydrating, setCompareShareHydrating] = useState(false);
  const [compareShareNotice, setCompareShareNotice] = useState(null);
  const pendingCompareKeys = useRef(parseCompareKeysFromUrl());
  const compareHydrationAbortRef = useRef(null);
  const compareHydrationRequestSeqRef = useRef(0);
  const normalizedApiBase = String(apiBase || "").trim();
  const normalizedCalculatorJobId = String(calculatorJobId || "").trim();

  // Seed compare rows from currently loaded page rows before API hydration.
  useEffect(() => {
    const pending = pendingCompareKeys.current;
    if (pending.length === 0) return;
    if (!Array.isArray(data) || data.length === 0) return;

    const seededRowsByKey = selectHydratedCompareRows({
      rows: data,
      requestedKeys: pending,
      careerTotalsView,
      resolvedYearFilter,
    });

    const matchedPendingKeys = new Set();
    Object.values(seededRowsByKey).forEach(row => {
      rowCompareIdentityKeys(row).forEach(key => {
        if (pending.includes(key)) matchedPendingKeys.add(key);
      });
    });
    pendingCompareKeys.current = pending.filter(key => !matchedPendingKeys.has(key));

    const seededRows = Object.values(seededRowsByKey);
    if (seededRows.length === 0) return;
    setCompareRowsByKey(current => mergeCompareRowsWithCap(current, seededRows));
  }, [careerTotalsView, data, resolvedYearFilter]);

  // Hydrate unresolved compare share keys directly from API.
  useEffect(() => {
    const pending = pendingCompareKeys.current;
    if (pending.length === 0) return;
    if (!normalizedApiBase) return;

    const requestedKeys = pending.slice(0, MAX_COMPARE_PLAYERS);
    pendingCompareKeys.current = [];
    setCompareShareHydrating(true);
    setCompareShareNotice(null);

    const requestSeq = compareHydrationRequestSeqRef.current + 1;
    compareHydrationRequestSeqRef.current = requestSeq;
    if (compareHydrationAbortRef.current) {
      compareHydrationAbortRef.current.abort();
    }
    const controller = new AbortController();
    compareHydrationAbortRef.current = controller;

    const hydratedRowsByStableKey = {};
    const matchedRequestedKeys = new Set();
    const requestedKeySet = new Set(requestedKeys);
    const pushHydratedRow = row => {
      if (!row || typeof row !== "object") return;
      const stableKey = stablePlayerKeyFromRow(row);
      if (!stableKey) return;
      hydratedRowsByStableKey[stableKey] = row;
      rowCompareIdentityKeys(row).forEach(key => {
        if (requestedKeySet.has(key)) matchedRequestedKeys.add(key);
      });
    };

    const dataset = resolveProjectionDataset(tab);

    const hydrateCompareRows = async () => {
      try {
        if (requestedKeys.length >= 2) {
          const compareRequestHref = buildProjectionCompareHydrationRequest({
            apiBase: normalizedApiBase,
            compareKeys: requestedKeys,
            tab: dataset,
            careerTotalsView,
            resolvedYearFilter,
            calculatorJobId: normalizedCalculatorJobId,
          });
          if (compareRequestHref) {
            try {
              const response = await fetch(compareRequestHref, {
                signal: controller.signal,
                cache: "no-store",
                headers: { "Cache-Control": "no-cache" },
              });
              if (response.ok) {
                const payload = await response.json();
                const selectedRowsByKey = selectHydratedCompareRows({
                  rows: Array.isArray(payload?.data) ? payload.data : [],
                  requestedKeys,
                  careerTotalsView,
                  resolvedYearFilter,
                });
                Object.values(selectedRowsByKey).forEach(pushHydratedRow);
              }
            } catch {
              // Best-effort hydration only; unresolved keys fall back to profile endpoint.
            }
          }
        }

        const unresolvedKeys = requestedKeys.filter(key => !matchedRequestedKeys.has(key));
        if (unresolvedKeys.length > 0) {
          await Promise.all(unresolvedKeys.map(async key => {
            try {
              const profileUrl = new URL(
                `${normalizedApiBase.replace(/\/+$/, "")}/api/projections/profile/${encodeURIComponent(key)}`
              );
              profileUrl.searchParams.set("dataset", dataset);
              profileUrl.searchParams.set("include_dynasty", "true");
              if (normalizedCalculatorJobId) {
                profileUrl.searchParams.set("calculator_job_id", normalizedCalculatorJobId);
              }
              const response = await fetch(profileUrl.toString(), {
                signal: controller.signal,
                cache: "no-store",
                headers: { "Cache-Control": "no-cache" },
              });
              if (!response.ok) return;
              const payload = await response.json();
              const selectedRow = pickPreferredCompareRow(
                profilePayloadRows(payload, { careerTotalsView }),
                { careerTotalsView, resolvedYearFilter }
              );
              pushHydratedRow(selectedRow);
            } catch {
              // Best-effort profile fallback; unresolved rows are ignored.
            }
          }));
        }

        if (controller.signal.aborted || requestSeq !== compareHydrationRequestSeqRef.current) {
          return;
        }
        const hydratedRows = Object.values(hydratedRowsByStableKey);
        if (hydratedRows.length > 0) {
          setCompareRowsByKey(current => mergeCompareRowsWithCap(current, hydratedRows));
        }
        setCompareShareNotice(resolveCompareShareHydrationNotice({
          requestedKeys,
          matchedKeys: Array.from(matchedRequestedKeys),
        }));
      } finally {
        if (!controller.signal.aborted && requestSeq === compareHydrationRequestSeqRef.current) {
          setCompareShareHydrating(false);
        }
      }
    };

    hydrateCompareRows().finally(() => {
      if (compareHydrationAbortRef.current === controller) {
        compareHydrationAbortRef.current = null;
      }
    });

    return () => {
      controller.abort();
      if (compareHydrationAbortRef.current === controller) {
        compareHydrationAbortRef.current = null;
      }
    };
  }, [
    careerTotalsView,
    normalizedApiBase,
    normalizedCalculatorJobId,
    resolvedYearFilter,
    tab,
  ]);

  useEffect(() => {
    return () => {
      compareHydrationRequestSeqRef.current += 1;
      if (compareHydrationAbortRef.current) {
        compareHydrationAbortRef.current.abort();
        compareHydrationAbortRef.current = null;
      }
    }
  }, []);

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

  const clearCompareShareNotice = useCallback(() => {
    setCompareShareNotice(null);
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
    compareShareHydrating,
    compareShareNotice,
    isRowWatched,
    toggleRowWatch,
    removeWatchlistEntry,
    clearWatchlist,
    exportWatchlistCsv,
    toggleCompareRow,
    quickAddRow,
    clearCompareShareNotice,
    clearCompareRows,
    removeCompareRow,
    maxComparePlayers: MAX_COMPARE_PLAYERS,
  };
}
