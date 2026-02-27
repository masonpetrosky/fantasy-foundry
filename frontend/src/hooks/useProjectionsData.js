import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useDebouncedValue } from "../request_helpers";

export const DEFAULT_PROJECTIONS_TAB = "all";
export const DEFAULT_PROJECTIONS_SORT_COL = "DynastyValue";
export const DEFAULT_PROJECTIONS_SORT_DIR = "desc";
export const CAREER_TOTALS_FILTER_VALUE = "__career_totals__";

const PROJECTION_PAGE_CACHE_MAX = 80;
const PROJECTION_SEARCH_DEBOUNCE_MS = 220;
const PROJECTION_INITIAL_FETCH_DELAY_MS = 0;

function projectionCacheGet(cacheMapRef, cacheOrderRef, cacheKey) {
  const cached = cacheMapRef.current.get(cacheKey);
  if (!cached) return null;

  const idx = cacheOrderRef.current.indexOf(cacheKey);
  if (idx !== -1) {
    cacheOrderRef.current.splice(idx, 1);
  }
  cacheOrderRef.current.push(cacheKey);
  return cached;
}

function projectionCacheSet(cacheMapRef, cacheOrderRef, cacheKey, payload) {
  cacheMapRef.current.set(cacheKey, payload);

  const idx = cacheOrderRef.current.indexOf(cacheKey);
  if (idx !== -1) {
    cacheOrderRef.current.splice(idx, 1);
  }
  cacheOrderRef.current.push(cacheKey);

  while (cacheOrderRef.current.length > PROJECTION_PAGE_CACHE_MAX) {
    const oldest = cacheOrderRef.current.shift();
    if (oldest) {
      cacheMapRef.current.delete(oldest);
    }
  }
}

export function buildProjectionCacheKey(resolvedDataVersion, endpointTab, params) {
  return `${resolvedDataVersion}:${endpointTab}?${params.toString()}`;
}

export function buildProjectionQueryParams({
  debouncedSearch,
  teamFilter,
  watchlistOnly,
  watchlistKeysFilter,
  careerTotalsView,
  resolvedYearFilter,
  posFilters,
  selectedDynastyYears,
  calculatorJobId,
}) {
  const baseParams = new URLSearchParams();
  if (debouncedSearch) baseParams.set("player", debouncedSearch);
  if (teamFilter) baseParams.set("team", teamFilter);
  if (watchlistOnly && watchlistKeysFilter) {
    baseParams.set("player_keys", watchlistKeysFilter);
  }
  if (careerTotalsView) {
    baseParams.set("career_totals", "true");
  } else {
    baseParams.set("year", resolvedYearFilter);
  }
  if (posFilters.length > 0) baseParams.set("pos", posFilters.join(","));
  if (selectedDynastyYears.length > 0) baseParams.set("dynasty_years", selectedDynastyYears.join(","));
  baseParams.set("include_dynasty", "true");
  if (calculatorJobId) baseParams.set("calculator_job_id", calculatorJobId);

  return {
    baseParams,
    shouldReturnEmptyWatchlist: Boolean(watchlistOnly && !watchlistKeysFilter),
  };
}

export function useProjectionsData({ apiBase, meta, watchlist, dataVersion, calculatorJobId }) {
  const API = String(apiBase || "").trim();
  const [tab, setTab] = useState(DEFAULT_PROJECTIONS_TAB); // all | bat | pitch
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, PROJECTION_SEARCH_DEBOUNCE_MS);
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [teamFilter, setTeamFilter] = useState("");
  const [yearFilter, setYearFilter] = useState(CAREER_TOTALS_FILTER_VALUE);
  const [posFilters, setPosFilters] = useState([]);
  const [baseData, setBaseData] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pageResetNotice, setPageResetNotice] = useState("");
  const [retryTrigger, setRetryTrigger] = useState(0);
  const [offset, setOffset] = useState(0);
  const [sortCol, setSortCol] = useState(DEFAULT_PROJECTIONS_SORT_COL);
  const [sortDir, setSortDir] = useState(DEFAULT_PROJECTIONS_SORT_DIR);
  const requestSeqRef = useRef(0);
  const abortControllerRef = useRef(null);
  const hasLoadedProjectionPageRef = useRef(false);
  const projectionCacheMapRef = useRef(new Map());
  const projectionCacheOrderRef = useRef([]);
  const limit = 100;
  const availableProjectionYears = useMemo(() => (meta.years || []).map(String), [meta.years]);
  const resolvedYearFilter = useMemo(() => {
    const value = String(yearFilter || "").trim();
    if (value === CAREER_TOTALS_FILTER_VALUE) return CAREER_TOTALS_FILTER_VALUE;
    if (availableProjectionYears.includes(value)) return value;
    return CAREER_TOTALS_FILTER_VALUE;
  }, [availableProjectionYears, yearFilter]);
  const careerTotalsView = resolvedYearFilter === CAREER_TOTALS_FILTER_VALUE;
  const resolvedDataVersion = String(dataVersion || "").trim();
  const watchlistKeysFilter = useMemo(
    () => Object.keys(watchlist).sort().join(","),
    [watchlist]
  );
  const selectedDynastyYears = useMemo(() => {
    if (careerTotalsView) return availableProjectionYears;
    return [resolvedYearFilter];
  }, [availableProjectionYears, careerTotalsView, resolvedYearFilter]);
  const resetOffsetWithNotice = useCallback(message => {
    setOffset(current => {
      if (current === 0) return current;
      setPageResetNotice(message);
      return 0;
    });
  }, []);

  const prefetchProjectionPage = useCallback(async (endpointTab, paramsWithoutOffset, nextOffset) => {
    if (nextOffset < 0) return;
    const nextParams = new URLSearchParams(paramsWithoutOffset);
    nextParams.set("offset", String(nextOffset));
    const nextCacheKey = buildProjectionCacheKey(resolvedDataVersion, endpointTab, nextParams);
    if (projectionCacheMapRef.current.has(nextCacheKey)) return;

    try {
      const response = await fetch(`${API}/api/projections/${endpointTab}?${nextParams}`, {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });
      if (!response.ok) return;
      const payload = await response.json();
      const pageRows = Array.isArray(payload.data) ? payload.data : [];
      const parsedTotal = Number(payload.total);
      const resolvedTotal = Number.isFinite(parsedTotal) && parsedTotal >= 0 ? parsedTotal : pageRows.length;
      const typeTag = endpointTab === "bat" ? "H" : endpointTab === "pitch" ? "P" : "";
      const rows = typeTag ? pageRows.map(row => ({ ...row, Type: typeTag })) : pageRows;
      projectionCacheSet(
        projectionCacheMapRef,
        projectionCacheOrderRef,
        nextCacheKey,
        { rows, total: resolvedTotal }
      );
    } catch {
      // Prefetch is best-effort only.
    }
  }, [API, resolvedDataVersion]);

  const fetchData = useCallback(async () => {
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const { baseParams, shouldReturnEmptyWatchlist } = buildProjectionQueryParams({
      debouncedSearch,
      teamFilter,
      watchlistOnly,
      watchlistKeysFilter,
      careerTotalsView,
      resolvedYearFilter,
      posFilters,
      selectedDynastyYears,
      calculatorJobId,
    });

    if (shouldReturnEmptyWatchlist) {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
      hasLoadedProjectionPageRef.current = true;
      setLoading(false);
      setError("");
      setBaseData([]);
      setTotalRows(0);
      return;
    }

    try {
      const endpointTab = tab === "all" ? "all" : tab;
      const paramsWithoutOffset = new URLSearchParams(baseParams);
      paramsWithoutOffset.set("limit", String(limit));
      paramsWithoutOffset.set("sort_col", sortCol);
      paramsWithoutOffset.set("sort_dir", sortDir);
      const params = new URLSearchParams(paramsWithoutOffset);
      params.set("offset", String(offset));
      const cacheKey = buildProjectionCacheKey(resolvedDataVersion, endpointTab, params);

      const cached = projectionCacheGet(projectionCacheMapRef, projectionCacheOrderRef, cacheKey);
      if (cached) {
        if (requestSeq !== requestSeqRef.current) return;
        hasLoadedProjectionPageRef.current = true;
        setError("");
        setBaseData(Array.isArray(cached.rows) ? cached.rows : []);
        setTotalRows(Number.isFinite(cached.total) ? cached.total : 0);
        setLoading(false);
        if (cached.total > offset + limit) {
          prefetchProjectionPage(endpointTab, paramsWithoutOffset, offset + limit);
        }
        return;
      }

      setLoading(true);
      setError("");

      const response = await fetch(`${API}/api/projections/${endpointTab}?${params}`, {
        signal: controller.signal,
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });
      if (!response.ok) {
        throw new Error(`Server returned ${response.status} while loading projections`);
      }

      const payload = await response.json();
      if (requestSeq !== requestSeqRef.current || controller.signal.aborted) return;

      const pageRows = Array.isArray(payload.data) ? payload.data : [];
      const parsedTotal = Number(payload.total);
      const resolvedTotal = Number.isFinite(parsedTotal) && parsedTotal >= 0 ? parsedTotal : pageRows.length;
      const typeTag = endpointTab === "bat" ? "H" : endpointTab === "pitch" ? "P" : "";
      const rows = typeTag ? pageRows.map(row => ({ ...row, Type: typeTag })) : pageRows;

      if (requestSeq !== requestSeqRef.current || controller.signal.aborted) return;
      projectionCacheSet(
        projectionCacheMapRef,
        projectionCacheOrderRef,
        cacheKey,
        { rows, total: resolvedTotal }
      );
      hasLoadedProjectionPageRef.current = true;
      setBaseData(rows);
      setTotalRows(resolvedTotal);
      setLoading(false);
      if (resolvedTotal > offset + limit) {
        prefetchProjectionPage(endpointTab, paramsWithoutOffset, offset + limit);
      }
    } catch (err) {
      if (requestSeq !== requestSeqRef.current) return;
      if (err?.name === "AbortError") return;
      setLoading(false);
      setError(err.message || "Failed to load projections");
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
    }
  }, [
    API,
    tab,
    debouncedSearch,
    teamFilter,
    watchlistOnly,
    watchlistKeysFilter,
    careerTotalsView,
    resolvedYearFilter,
    posFilters,
    selectedDynastyYears,
    calculatorJobId,
    offset,
    sortCol,
    sortDir,
    limit,
    resolvedDataVersion,
    prefetchProjectionPage,
    retryTrigger,
  ]);

  useEffect(() => {
    if (watchlistOnly && Object.keys(watchlist).length === 0) {
      setWatchlistOnly(false);
    }
  }, [watchlistOnly, watchlist]);

  useEffect(() => {
    const delayMs = hasLoadedProjectionPageRef.current ? 0 : PROJECTION_INITIAL_FETCH_DELAY_MS;
    const timer = window.setTimeout(fetchData, delayMs);
    return () => {
      window.clearTimeout(timer);
    };
  }, [fetchData]);

  useEffect(() => {
    return () => {
      requestSeqRef.current += 1;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      hasLoadedProjectionPageRef.current = false;
      projectionCacheMapRef.current.clear();
      projectionCacheOrderRef.current = [];
    };
  }, []);

  useEffect(() => {
    projectionCacheMapRef.current.clear();
    projectionCacheOrderRef.current = [];
    hasLoadedProjectionPageRef.current = false;
    resetOffsetWithNotice("Page reset to 1 after projections data refreshed.");
  }, [resolvedDataVersion, resetOffsetWithNotice]);

  useEffect(() => {
    resetOffsetWithNotice("Page reset to 1 after filters or sorting changed.");
  }, [
    tab,
    search,
    teamFilter,
    watchlistOnly,
    watchlistKeysFilter,
    resolvedYearFilter,
    posFilters,
    calculatorJobId,
    sortCol,
    sortDir,
    resetOffsetWithNotice,
  ]);

  useEffect(() => {
    if (yearFilter !== resolvedYearFilter) {
      setYearFilter(resolvedYearFilter);
    }
  }, [resolvedYearFilter, yearFilter]);

  const retryFetch = useCallback(() => {
    setRetryTrigger(n => n + 1);
  }, []);
  const clearPageResetNotice = useCallback(() => {
    setPageResetNotice("");
  }, []);

  useEffect(() => {
    if (offset > 0 && pageResetNotice) {
      setPageResetNotice("");
    }
  }, [offset, pageResetNotice]);

  return {
    tab,
    setTab,
    search,
    setSearch,
    debouncedSearch,
    watchlistOnly,
    setWatchlistOnly,
    teamFilter,
    setTeamFilter,
    yearFilter,
    setYearFilter,
    posFilters,
    setPosFilters,
    baseData,
    totalRows,
    loading,
    error,
    pageResetNotice,
    offset,
    setOffset,
    sortCol,
    setSortCol,
    sortDir,
    setSortDir,
    limit,
    availableProjectionYears,
    resolvedYearFilter,
    careerTotalsView,
    watchlistKeysFilter,
    selectedDynastyYears,
    resolvedDataVersion,
    retryFetch,
    clearPageResetNotice,
  };
}
