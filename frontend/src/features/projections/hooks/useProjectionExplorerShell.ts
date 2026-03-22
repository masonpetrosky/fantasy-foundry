import { useCallback, useEffect, useMemo } from "react";
import type { Dispatch, RefObject, SetStateAction } from "react";
import { trackEvent } from "../../../analytics";
import {
  isRotoStatDynastyCol,
  rotoStatDynastyLabel,
} from "../../../dynasty_calculator_config";
import {
  CAREER_TOTALS_FILTER_VALUE,
  DEFAULT_PROJECTIONS_SORT_COL,
  DEFAULT_PROJECTIONS_SORT_DIR,
  DEFAULT_PROJECTIONS_TAB,
} from "../../../hooks/useProjectionsData";
import {
  buildActiveFilterChips,
  resolveProjectionEmptyStateModel,
  resolveProjectionSwipeHint,
} from "../view_state";

interface UseProjectionExplorerShellInput {
  search: string;
  teamFilter: string;
  resolvedYearFilter: string;
  posFilters: string[];
  watchlistOnly: boolean;
  sortCol: string;
  sortDir: string;
  tab: string;
  selectedDynastyYears: string[];
  tableColumnCatalog: string[];
  canScrollLeft: boolean;
  canScrollRight: boolean;
  showCards: boolean;
  isMobileViewport: boolean;
  mobileLayoutMode: string;
  colsLength: number;
  displayedPageLength: number;
  loading: boolean;
  totalRows: number;
  offset: number;
  projectionTableScrollRef: RefObject<HTMLDivElement | null>;
  updateProjectionHorizontalAffordance: () => void;
  setTab: Dispatch<SetStateAction<string>>;
  setSortCol: Dispatch<SetStateAction<string>>;
  setSortDir: Dispatch<SetStateAction<string>>;
  setOffset: Dispatch<SetStateAction<number>>;
  setPosFilters: Dispatch<SetStateAction<string[]>>;
}

interface UseProjectionExplorerShellReturn {
  activeFilterChips: string[];
  hasActiveFilters: boolean;
  handleSort: (col: string) => void;
  handleSelectTab: (nextTab: string) => void;
  colLabels: Record<string, string>;
  swipeHintModel: {
    showSwipeHint: boolean;
    swipeHintText: string;
  };
  showMobileSwipeHint: boolean;
}

export function useProjectionExplorerShell({
  search,
  teamFilter,
  resolvedYearFilter,
  posFilters,
  watchlistOnly,
  sortCol,
  sortDir,
  tab,
  selectedDynastyYears,
  tableColumnCatalog,
  canScrollLeft,
  canScrollRight,
  showCards,
  isMobileViewport,
  mobileLayoutMode,
  colsLength,
  displayedPageLength,
  loading,
  totalRows,
  offset,
  projectionTableScrollRef,
  updateProjectionHorizontalAffordance,
  setTab,
  setSortCol,
  setSortDir,
  setOffset,
  setPosFilters,
}: UseProjectionExplorerShellInput): UseProjectionExplorerShellReturn {
  const activeFilterChips = useMemo(() => buildActiveFilterChips({
    search,
    teamFilter,
    resolvedYearFilter,
    posFilters,
    watchlistOnly,
    careerTotalsFilterValue: CAREER_TOTALS_FILTER_VALUE,
  }), [posFilters, resolvedYearFilter, search, teamFilter, watchlistOnly]);
  const hasActiveFilters = activeFilterChips.length > 0;

  const handleSort = useCallback((col: string): void => {
    const nextDir = sortCol === col
      ? (sortDir === "asc" ? "desc" : "asc")
      : (col === "Player" || col === "Team" || col === "Pos" || col === "Type" || col === "Year" || col === "Years" ? "asc" : "desc");
    if (sortCol === col) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir(nextDir);
    }
    trackEvent("ff_projection_sort", { column: col, direction: nextDir, tab });
  }, [setSortCol, setSortDir, sortCol, sortDir, tab]);

  const handleSelectTab = useCallback((nextTab: string): void => {
    const resolvedTab = nextTab === "bat" || nextTab === "pitch"
      ? nextTab
      : DEFAULT_PROJECTIONS_TAB;
    setTab(resolvedTab);
    setSortCol(DEFAULT_PROJECTIONS_SORT_COL);
    setSortDir(DEFAULT_PROJECTIONS_SORT_DIR);
    setOffset(0);
    setPosFilters([]);
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [setOffset, setPosFilters, setSortCol, setSortDir, setTab]);

  const colLabels = useMemo(() => {
    const labels: Record<string, string> = {
      Type: "Side",
      OldestProjectionDate: "Oldest Proj Date",
      Rank: "Rank",
      DynastyValue: "Dynasty Value",
      AuctionDollars: "Auction $",
      ProjectionDelta: "\u0394 Proj",
      Years: "Years",
      PitH: "P H",
      PitHR: "P HR",
      PitBB: "P BB",
    };
    selectedDynastyYears.forEach((year) => {
      labels[`Value_${year}`] = `${year} Dyn Value`;
    });
    tableColumnCatalog.forEach((col) => {
      if (isRotoStatDynastyCol(col)) {
        labels[col] = rotoStatDynastyLabel(col);
      }
    });
    return labels;
  }, [selectedDynastyYears, tableColumnCatalog]);

  const swipeHintModel = useMemo(() => resolveProjectionSwipeHint({
    canScrollLeft,
    canScrollRight,
  }), [canScrollLeft, canScrollRight]);
  const showMobileSwipeHint = !showCards
    && isMobileViewport
    && swipeHintModel.showSwipeHint;

  useEffect(() => {
    const onResize = (): void => updateProjectionHorizontalAffordance();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [updateProjectionHorizontalAffordance]);

  useEffect(() => {
    const raf = window.requestAnimationFrame(() => updateProjectionHorizontalAffordance());
    return () => window.cancelAnimationFrame(raf);
  }, [updateProjectionHorizontalAffordance, colsLength, displayedPageLength, loading, totalRows, tab, offset, mobileLayoutMode]);

  useEffect(() => {
    if (!isMobileViewport) return;
    if (mobileLayoutMode === "cards") {
      return;
    }
    const el = projectionTableScrollRef.current;
    if (!el) return;
    el.scrollLeft = 0;
    updateProjectionHorizontalAffordance();
  }, [isMobileViewport, mobileLayoutMode, projectionTableScrollRef, tab, updateProjectionHorizontalAffordance]);

  return {
    activeFilterChips,
    hasActiveFilters,
    handleSort,
    handleSelectTab,
    colLabels,
    swipeHintModel,
    showMobileSwipeHint,
  };
}

interface UseProjectionEmptyStateInput {
  watchlistOnly: boolean;
  resolvedYearFilter: string;
  hasActiveFilters: boolean;
}

export function useProjectionEmptyState({
  watchlistOnly,
  resolvedYearFilter,
  hasActiveFilters,
}: UseProjectionEmptyStateInput) {
  return useMemo(() => resolveProjectionEmptyStateModel({
    watchlistOnly,
    resolvedYearFilter,
    hasActiveFilters,
    careerTotalsFilterValue: CAREER_TOTALS_FILTER_VALUE,
  }), [hasActiveFilters, resolvedYearFilter, watchlistOnly]);
}
