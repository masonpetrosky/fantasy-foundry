import { useCallback, useEffect, useMemo, useState } from "react";
import { useDebouncedValue } from "../request_helpers";
import { useProjectionsQuery } from "./useProjectionsQuery";
import type { ProjectionRow } from "../app_state_storage";

export const DEFAULT_PROJECTIONS_TAB = "all";
export const DEFAULT_PROJECTIONS_SORT_COL = "DynastyValue";
export const DEFAULT_PROJECTIONS_SORT_DIR = "desc";
export const CAREER_TOTALS_FILTER_VALUE = "__career_totals__";

const PROJECTION_SEARCH_DEBOUNCE_MS = 220;

type ProjectionTab = "all" | "bat" | "pitch";

export function buildProjectionCacheKey(
  resolvedDataVersion: string,
  endpointTab: string,
  params: URLSearchParams,
): string {
  return `${resolvedDataVersion}:${endpointTab}?${params.toString()}`;
}

export interface BuildProjectionQueryParamsInput {
  debouncedSearch: string;
  teamFilter: string;
  watchlistOnly: boolean;
  watchlistKeysFilter: string;
  careerTotalsView: boolean;
  resolvedYearFilter: string;
  posFilters: string[];
  selectedDynastyYears: string[];
  calculatorJobId?: string;
}

export interface BuildProjectionQueryParamsResult {
  baseParams: URLSearchParams;
  shouldReturnEmptyWatchlist: boolean;
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
}: BuildProjectionQueryParamsInput): BuildProjectionQueryParamsResult {
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

export interface UseProjectionsDataInput {
  apiBase: string;
  meta: { years?: (string | number)[] } | null;
  watchlist: Record<string, unknown>;
  dataVersion: string;
  calculatorJobId: string;
}

export interface UseProjectionsDataReturn {
  tab: string;
  setTab: React.Dispatch<React.SetStateAction<string>>;
  search: string;
  setSearch: React.Dispatch<React.SetStateAction<string>>;
  debouncedSearch: string;
  watchlistOnly: boolean;
  setWatchlistOnly: React.Dispatch<React.SetStateAction<boolean>>;
  teamFilter: string;
  setTeamFilter: React.Dispatch<React.SetStateAction<string>>;
  yearFilter: string;
  setYearFilter: React.Dispatch<React.SetStateAction<string>>;
  posFilters: string[];
  setPosFilters: React.Dispatch<React.SetStateAction<string[]>>;
  baseData: ProjectionRow[];
  totalRows: number;
  loading: boolean;
  error: string;
  pageResetNotice: string;
  offset: number;
  setOffset: React.Dispatch<React.SetStateAction<number>>;
  sortCol: string;
  setSortCol: React.Dispatch<React.SetStateAction<string>>;
  sortDir: string;
  setSortDir: React.Dispatch<React.SetStateAction<string>>;
  limit: number;
  availableProjectionYears: string[];
  resolvedYearFilter: string;
  careerTotalsView: boolean;
  watchlistKeysFilter: string;
  selectedDynastyYears: string[];
  resolvedDataVersion: string;
  retryFetch: () => void;
  clearPageResetNotice: () => void;
}

export function useProjectionsData({
  apiBase,
  meta,
  watchlist,
  dataVersion,
  calculatorJobId,
}: UseProjectionsDataInput): UseProjectionsDataReturn {
  const API = String(apiBase || "").trim();
  const [tab, setTab] = useState<string>(DEFAULT_PROJECTIONS_TAB);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, PROJECTION_SEARCH_DEBOUNCE_MS);
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [teamFilter, setTeamFilter] = useState("");
  const [yearFilter, setYearFilter] = useState(CAREER_TOTALS_FILTER_VALUE);
  const [posFilters, setPosFilters] = useState<string[]>([]);
  const [pageResetNotice, setPageResetNotice] = useState("");
  const [offset, setOffset] = useState(0);
  const [sortCol, setSortCol] = useState(DEFAULT_PROJECTIONS_SORT_COL);
  const [sortDir, setSortDir] = useState(DEFAULT_PROJECTIONS_SORT_DIR);
  const limit = 100;

  const availableProjectionYears = useMemo(
    () => ((meta as Record<string, unknown> | null)?.years as (string | number)[] || []).map(String),
    [meta],
  );
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
    [watchlist],
  );
  const selectedDynastyYears = useMemo(() => {
    if (careerTotalsView) return availableProjectionYears;
    return [resolvedYearFilter];
  }, [availableProjectionYears, careerTotalsView, resolvedYearFilter]);

  const resetOffsetWithNotice = useCallback((message: string) => {
    setOffset(current => {
      if (current === 0) return current;
      setPageResetNotice(message);
      return 0;
    });
  }, []);

  // Build query params for React Query
  const { baseParams, shouldReturnEmptyWatchlist } = useMemo(
    () => buildProjectionQueryParams({
      debouncedSearch,
      teamFilter,
      watchlistOnly,
      watchlistKeysFilter,
      careerTotalsView,
      resolvedYearFilter,
      posFilters,
      selectedDynastyYears,
      calculatorJobId,
    }),
    [debouncedSearch, teamFilter, watchlistOnly, watchlistKeysFilter, careerTotalsView, resolvedYearFilter, posFilters, selectedDynastyYears, calculatorJobId],
  );

  const endpointTab: ProjectionTab = tab === "bat" ? "bat" : tab === "pitch" ? "pitch" : "all";

  const fullParams = useMemo(() => {
    const params = new URLSearchParams(baseParams);
    params.set("limit", String(limit));
    params.set("sort_col", sortCol);
    params.set("sort_dir", sortDir);
    params.set("offset", String(offset));
    return params;
  }, [baseParams, limit, sortCol, sortDir, offset]);

  // Prefetch next page params
  const nextPageParams = useMemo(() => {
    const params = new URLSearchParams(baseParams);
    params.set("limit", String(limit));
    params.set("sort_col", sortCol);
    params.set("sort_dir", sortDir);
    params.set("offset", String(offset + limit));
    return params;
  }, [baseParams, limit, sortCol, sortDir, offset]);

  const {
    data: queryData,
    isLoading,
    isError,
    error: queryError,
    prefetchNextPage,
    invalidateAll,
  } = useProjectionsQuery({
    apiBase: API,
    endpointTab,
    params: fullParams,
    enabled: !shouldReturnEmptyWatchlist,
    resolvedDataVersion,
  });

  // Map React Query state to the existing interface
  const baseData = shouldReturnEmptyWatchlist ? [] : (queryData?.rows ?? []);
  const totalRows = shouldReturnEmptyWatchlist ? 0 : (queryData?.total ?? 0);
  const loading = isLoading;
  const error = isError ? queryError : "";

  // Prefetch next page when current data loads
  useEffect(() => {
    if (queryData && totalRows > offset + limit) {
      prefetchNextPage(nextPageParams);
    }
  }, [queryData, totalRows, offset, limit, prefetchNextPage, nextPageParams]);

  // Clear watchlist filter when watchlist becomes empty
  useEffect(() => {
    if (watchlistOnly && Object.keys(watchlist).length === 0) {
      setWatchlistOnly(false);
    }
  }, [watchlistOnly, watchlist]);

  // Reset offset on data version change
  useEffect(() => {
    resetOffsetWithNotice("Page reset to 1 after projections data refreshed.");
  }, [resolvedDataVersion, resetOffsetWithNotice]);

  // Reset offset on filter/sort change
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

  // Sync yearFilter with resolved value
  useEffect(() => {
    if (yearFilter !== resolvedYearFilter) {
      setYearFilter(resolvedYearFilter);
    }
  }, [resolvedYearFilter, yearFilter]);

  const retryFetch = useCallback(() => {
    invalidateAll();
  }, [invalidateAll]);

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
