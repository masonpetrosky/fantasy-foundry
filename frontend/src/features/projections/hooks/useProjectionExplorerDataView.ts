import { useEffect, useMemo, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import type { ProjectionRow } from "../../../app_state_storage";
import type { DeltaMap } from "../../../hooks/useProjectionDeltas";

interface ProjectionToastContextLike {
  addToast: (message: string, options?: { type?: "success" | "error" | "info"; duration?: number }) => unknown;
}

interface UseProjectionExplorerDataViewInput {
  toastCtx: ProjectionToastContextLike | null;
  dataVersion: string;
  baseData: ProjectionRow[];
  applyCalculatorOverlayToRows: (rows: ProjectionRow[]) => ProjectionRow[];
  deltaMap: DeltaMap;
  rosterOnly: boolean;
  fantraxRosterPlayerKeys?: Set<string>;
  tab: string;
  search: string;
  teamFilter: string;
  resolvedYearFilter: string;
  posFilters: string[];
  watchlistOnly: boolean;
  sortCol: string;
  sortDir: string;
  setTab: Dispatch<SetStateAction<string>>;
  setSearch: Dispatch<SetStateAction<string>>;
  setTeamFilter: Dispatch<SetStateAction<string>>;
  setYearFilter: Dispatch<SetStateAction<string>>;
  setPosFilters: Dispatch<SetStateAction<string[]>>;
  setWatchlistOnly: Dispatch<SetStateAction<boolean>>;
  setSortCol: Dispatch<SetStateAction<string>>;
  setSortDir: Dispatch<SetStateAction<string>>;
  setOffset: Dispatch<SetStateAction<number>>;
}

interface UseProjectionExplorerDataViewReturn {
  data: ProjectionRow[];
  filteredData: ProjectionRow[];
  filterActions: {
    setTab: Dispatch<SetStateAction<string>>;
    setSearch: Dispatch<SetStateAction<string>>;
    setTeamFilter: Dispatch<SetStateAction<string>>;
    setYearFilter: Dispatch<SetStateAction<string>>;
    setPosFilters: Dispatch<SetStateAction<string[]>>;
    setWatchlistOnly: Dispatch<SetStateAction<boolean>>;
    setSortCol: Dispatch<SetStateAction<string>>;
    setSortDir: Dispatch<SetStateAction<string>>;
    setOffset: Dispatch<SetStateAction<number>>;
  };
  filterState: {
    tab: string;
    search: string;
    teamFilter: string;
    resolvedYearFilter: string;
    posFilters: string[];
    watchlistOnly: boolean;
    sortCol: string;
    sortDir: string;
  };
}

export function useProjectionExplorerDataView({
  toastCtx,
  dataVersion,
  baseData,
  applyCalculatorOverlayToRows,
  deltaMap,
  rosterOnly,
  fantraxRosterPlayerKeys,
  tab,
  search,
  teamFilter,
  resolvedYearFilter,
  posFilters,
  watchlistOnly,
  sortCol,
  sortDir,
  setTab,
  setSearch,
  setTeamFilter,
  setYearFilter,
  setPosFilters,
  setWatchlistOnly,
  setSortCol,
  setSortDir,
  setOffset,
}: UseProjectionExplorerDataViewInput): UseProjectionExplorerDataViewReturn {
  const prevDataVersionRef = useRef(dataVersion);

  useEffect(() => {
    if (prevDataVersionRef.current && prevDataVersionRef.current !== dataVersion) {
      toastCtx?.addToast("Projection data has been updated.", { type: "info" });
    }
    prevDataVersionRef.current = dataVersion;
  }, [dataVersion, toastCtx]);

  const data = useMemo(() => {
    const overlaid = applyCalculatorOverlayToRows(baseData);
    return Object.keys(deltaMap).length === 0
      ? overlaid
      : overlaid.map((row) => {
        const key = String(row.PlayerEntityKey || row.PlayerKey || "");
        const delta = deltaMap[key];
        if (!delta) return row;
        return { ...row, ProjectionDelta: delta.composite_delta };
      });
  }, [applyCalculatorOverlayToRows, baseData, deltaMap]);

  const filteredData = useMemo(() => {
    if (!rosterOnly || !fantraxRosterPlayerKeys || fantraxRosterPlayerKeys.size === 0) {
      return data;
    }
    return data.filter((row) => {
      const key = String(row.PlayerEntityKey || row.PlayerKey || "");
      return key && fantraxRosterPlayerKeys.has(key);
    });
  }, [data, fantraxRosterPlayerKeys, rosterOnly]);

  const filterActions = useMemo(() => ({
    setTab,
    setSearch,
    setTeamFilter,
    setYearFilter,
    setPosFilters,
    setWatchlistOnly,
    setSortCol,
    setSortDir,
    setOffset,
  }), [setOffset, setPosFilters, setSearch, setSortCol, setSortDir, setTab, setTeamFilter, setWatchlistOnly, setYearFilter]);

  const filterState = useMemo(() => ({
    tab,
    search,
    teamFilter,
    resolvedYearFilter,
    posFilters,
    watchlistOnly,
    sortCol,
    sortDir,
  }), [posFilters, resolvedYearFilter, search, sortCol, sortDir, tab, teamFilter, watchlistOnly]);

  return {
    data,
    filteredData,
    filterActions,
    filterState,
  };
}
