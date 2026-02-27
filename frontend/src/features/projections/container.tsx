import React, { useCallback, useEffect, useMemo, useState } from "react";
import { formatCellValue } from "../../formatting_utils";
import { useProjectionColumnVisibility } from "./hooks/useProjectionColumnVisibility";
import { useProjectionCollections } from "./hooks/useProjectionCollections";
import { useProjectionLayoutState } from "./hooks/useProjectionLayoutState";
import { useProjectionOverlay } from "./hooks/useProjectionOverlay";
import { useProjectionComparisonComposition } from "./hooks/useProjectionComparisonComposition";
import { useProjectionExportPipeline } from "./hooks/useProjectionExportPipeline";
import { useProjectionFilterPresets } from "./hooks/useProjectionFilterPresets";
import { useProjectionTelemetry } from "./hooks/useProjectionTelemetry";
import { useProjectionRowsMarkup } from "./hooks/useProjectionRowsMarkup";
import { useProjectionWatchlistComposition } from "./hooks/useProjectionWatchlistComposition";
import { CAREER_TOTALS_FILTER_VALUE, DEFAULT_PROJECTIONS_SORT_COL, DEFAULT_PROJECTIONS_SORT_DIR, DEFAULT_PROJECTIONS_TAB, useProjectionsData } from "../../hooks/useProjectionsData";
import { buildActiveFilterChips, resolveProjectionEmptyStateModel, resolveProjectionSwipeHint } from "./view_state";
import { PlayerProfile } from "./components/PlayerProfile";
import { ProjectionCollectionsWorkspace } from "./components/ProjectionCollectionsWorkspace";
import { ProjectionEmptyStateActions } from "./components/ProjectionEmptyStateActions";
import { ProjectionFilterBar } from "./components/ProjectionFilterBar";
import { ProjectionLayoutControls } from "./components/ProjectionLayoutControls";
import { ProjectionOverlayBanner } from "./components/ProjectionOverlayBanner";
import { ProjectionResultsShell } from "./components/ProjectionResultsShell";
import { ProjectionSectionTabs } from "./components/ProjectionSectionTabs";
import { ProjectionStatusMessages } from "./components/ProjectionStatusMessages";
import type { TierLimits } from "../../premium";
import type { CalculatorSettings } from "../../dynasty_calculator_config";
import type { PlayerWatchEntry } from "../../app_state_storage";

interface ProjectionsExplorerProps {
  apiBase: string;
  meta: Record<string, unknown> & { years?: (string | number)[]; teams?: string[] };
  dataVersion: string;
  watchlist: Record<string, PlayerWatchEntry>;
  setWatchlist: React.Dispatch<React.SetStateAction<Record<string, PlayerWatchEntry>>>;
  hasSuccessfulCalcRun: boolean;
  activeCalculatorSettings: CalculatorSettings | null;
  calculatorOverlayByPlayerKey: Record<string, unknown> | null;
  calculatorOverlayActive: boolean;
  calculatorOverlayJobId: string;
  calculatorOverlayDataVersion: string;
  calculatorOverlayPlayerCount: number;
  calculatorOverlaySummary: Record<string, unknown> | null;
  onClearCalculatorOverlay: () => void;
  tierLimits: TierLimits | null;
}

export function ProjectionsExplorer({
  apiBase,
  meta,
  dataVersion,
  watchlist,
  setWatchlist,
  hasSuccessfulCalcRun,
  activeCalculatorSettings,
  calculatorOverlayByPlayerKey,
  calculatorOverlayActive,
  calculatorOverlayJobId,
  calculatorOverlayDataVersion,
  calculatorOverlayPlayerCount,
  calculatorOverlaySummary,
  onClearCalculatorOverlay,
  tierLimits,
}: ProjectionsExplorerProps): React.ReactElement {
  const activeCalculatorJobId = calculatorOverlayActive
    ? String(calculatorOverlayJobId || "").trim()
    : "";
  const {
    tab,
    setTab,
    search,
    setSearch,
    debouncedSearch,
    watchlistOnly,
    setWatchlistOnly,
    teamFilter,
    setTeamFilter,
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
    resolvedYearFilter,
    careerTotalsView,
    watchlistKeysFilter,
    selectedDynastyYears,
    retryFetch,
    clearPageResetNotice,
  } = useProjectionsData({
    apiBase,
    meta,
    watchlist,
    dataVersion,
    calculatorJobId: activeCalculatorJobId,
  });
  const {
    isMobileViewport,
    mobileLayoutMode,
    setMobileLayoutMode,
    projectionTableScrollRef,
    canScrollLeft,
    canScrollRight,
    updateProjectionHorizontalAffordance,
    handleProjectionTableScroll,
  } = useProjectionLayoutState();

  const [, setShowPosMenu] = useState(false);
  const [profileRow, setProfileRow] = useState<Record<string, unknown> | null>(null);
  const handleViewProfile = useCallback((row: Record<string, unknown>) => setProfileRow(row), []);
  const handleCloseProfile = useCallback(() => setProfileRow(null), []);

  const {
    hasCalculatorOverlay,
    resolvedCalculatorOverlayPlayerCount,
    overlayStatusMeta,
    showOverlayWhy,
    setShowOverlayWhy,
    applyCalculatorOverlayToRows,
  } = useProjectionOverlay({
    // @ts-expect-error - overlay map is structurally compatible
    calculatorOverlayByPlayerKey,
    calculatorOverlayActive,
    calculatorOverlayJobId,
    calculatorOverlayDataVersion,
    calculatorOverlayPlayerCount,
    calculatorOverlaySummary,
    dataVersion,
  });

  const activeFilterChips = useMemo(() => buildActiveFilterChips({
    search,
    teamFilter,
    resolvedYearFilter,
    posFilters,
    watchlistOnly,
    careerTotalsFilterValue: CAREER_TOTALS_FILTER_VALUE,
  }), [posFilters, resolvedYearFilter, search, teamFilter, watchlistOnly]);
  const hasActiveFilters = activeFilterChips.length > 0;

  const data = useMemo(
    () => applyCalculatorOverlayToRows(baseData),
    [applyCalculatorOverlayToRows, baseData]
  );

  const filterActions = useMemo(() => ({
    setTab, setSearch, setTeamFilter, setYearFilter, setPosFilters,
    setWatchlistOnly, setSortCol, setSortDir, setOffset,
  }), [setTab, setSearch, setTeamFilter, setYearFilter, setPosFilters, setWatchlistOnly, setSortCol, setSortDir, setOffset]);

  const filterState = useMemo(() => ({
    tab, search, teamFilter, resolvedYearFilter, posFilters, watchlistOnly, sortCol, sortDir,
  }), [tab, search, teamFilter, resolvedYearFilter, posFilters, watchlistOnly, sortCol, sortDir]);

  const {
    projectionFilterPresets,
    applyProjectionFilterPreset,
    saveCustomProjectionPreset,
    activeProjectionPresetKey,
    clearAllFilters,
  } = useProjectionFilterPresets({ filterActions, filterState, setShowPosMenu });

  const page = data;
  const collections = useProjectionCollections({
    watchlist,
    setWatchlist,
    data,
    apiBase,
    tab,
    careerTotalsView,
    resolvedYearFilter,
    calculatorJobId: activeCalculatorJobId,
  });
  const {
    watchlistCount,
    watchlist: resolvedWatchlist,
    sortedWatchlistEntries,
    isRowWatched,
    toggleRowWatch,
    removeWatchlistEntry,
    clearWatchlist,
    exportWatchlistCsv,
    quickAddRow,
    workspaceHasWatchlistActivity,
  } = useProjectionWatchlistComposition({
    collections,
    watchlist,
  });
  const {
    compareRowsByKey,
    compareRows,
    compareRowsCount,
    maxComparePlayers,
    toggleCompareRow,
    removeCompareRow,
    clearCompareRows,
    comparisonColumns,
    copyCompareShareLink,
    compareShareCopyNotice,
    clearCompareShareCopyNotice,
    compareShareHydrating,
    compareShareNotice,
    clearCompareShareNotice,
    workspaceHasComparisonActivity,
  } = useProjectionComparisonComposition({
    collections,
    tab,
    seasonCol: careerTotalsView ? "Years" : "Year",
  });

  function handleSort(col: string): void {
    if (sortCol === col) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir(col === "Player" || col === "Team" || col === "Pos" || col === "Type" || col === "Year" || col === "Years" ? "asc" : "desc");
    }
  }

  function handleSelectTab(nextTab: string): void {
    const resolvedTab = nextTab === "bat" || nextTab === "pitch"
      ? nextTab
      : DEFAULT_PROJECTIONS_TAB;
    setTab(resolvedTab);
    setSortCol(DEFAULT_PROJECTIONS_SORT_COL);
    setSortDir(DEFAULT_PROJECTIONS_SORT_DIR);
    setOffset(0);
    setPosFilters([]);
    setShowPosMenu(false);
  }

  const seasonCol = careerTotalsView ? "Years" : "Year";
  const dynastyYearCols = selectedDynastyYears.map(year => `Value_${year}`);
  const {
    tableColumnCatalog,
    requiredProjectionTableCols,
    resolvedProjectionTableHiddenCols,
    cols,
    toggleProjectionTableColumn,
    showAllProjectionTableColumns,
    cardColumnCatalog,
    requiredProjectionCardCols,
    resolvedProjectionCardHiddenCols,
    projectionCardColumnsForRow,
    toggleProjectionCardColumn,
    showAllProjectionCardColumns,
  } = useProjectionColumnVisibility({
    tab,
    seasonCol,
    dynastyYearCols,
    activeCalculatorSettings,
  });

  const {
    exportError,
    exportingFormat,
    exportCurrentProjections,
    clearExportError,
  } = useProjectionExportPipeline({
    apiBase,
    tab,
    search,
    teamFilter,
    watchlistOnly,
    watchlistKeysFilter,
    careerTotalsView,
    resolvedYearFilter,
    posFilters,
    selectedDynastyYears,
    activeCalculatorJobId,
    sortCol,
    sortDir,
    cols,
  });

  const colLabels = useMemo(() => {
    const labels: Record<string, string> = {
      Type: "Side",
      ProjectionsUsed: "Proj Count",
      OldestProjectionDate: "Oldest Proj Date",
      Rank: "Rank",
      DynastyValue: "Dynasty Value",
      Years: "Years",
      PitH: "P H",
      PitHR: "P HR",
      PitBB: "P BB",
    };
    dynastyYearCols.forEach(col => {
      labels[col] = `${col.replace("Value_", "")} Dyn Value`;
    });
    return labels;
  }, [dynastyYearCols]);

  const displayedPage = page;
  const showCards = mobileLayoutMode === "cards";
  const showInitialLoadSkeleton = loading && displayedPage.length === 0;
  const showInlineRefreshError = Boolean(error) && displayedPage.length > 0;
  const searchIsDebouncing = search !== debouncedSearch;

  const swipeHintModel = useMemo(() => resolveProjectionSwipeHint({
    canScrollLeft,
    canScrollRight,
  }), [canScrollLeft, canScrollRight]);
  const showMobileSwipeHint = !showCards
    && isMobileViewport
    && swipeHintModel.showSwipeHint;

  const showCollectionsWorkspace = Boolean(hasSuccessfulCalcRun)
    || workspaceHasWatchlistActivity
    || workspaceHasComparisonActivity;

  const emptyStateModel = useMemo(() => resolveProjectionEmptyStateModel({
    watchlistOnly,
    resolvedYearFilter,
    hasActiveFilters,
    careerTotalsFilterValue: CAREER_TOTALS_FILTER_VALUE,
  }), [hasActiveFilters, resolvedYearFilter, watchlistOnly]);

  const {
    lastRefreshedLabel,
  } = useProjectionTelemetry({
    loading,
    error,
    displayedPage,
    tab,
    resolvedYearFilter,
    teamFilter,
    watchlistOnly,
    search,
    posFilters,
    offset,
    totalRows,
  });

  const {
    cardRowsMarkup,
    tableRowsMarkup,
  } = useProjectionRowsMarkup({
    showCards,
    displayedPage,
    offset,
    cols,
    colLabels,
    projectionCardColumnsForRow,
    isRowWatched,
    compareRowsByKey,
    compareRowsCount,
    maxComparePlayers,
    toggleRowWatch,
    toggleCompareRow,
    quickAddRow,
    onViewProfile: handleViewProfile,
  });

  useEffect(() => {
    const onResize = (): void => updateProjectionHorizontalAffordance();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [updateProjectionHorizontalAffordance]);

  useEffect(() => {
    const raf = window.requestAnimationFrame(() => updateProjectionHorizontalAffordance());
    return () => window.cancelAnimationFrame(raf);
  }, [updateProjectionHorizontalAffordance, cols.length, displayedPage.length, loading, totalRows, tab, offset, mobileLayoutMode]);

  useEffect(() => {
    if (!isMobileViewport) return;
    if (mobileLayoutMode === "cards") {
      return;
    }
    const el = projectionTableScrollRef.current;
    if (!el) return;
    el.scrollLeft = 0;
    updateProjectionHorizontalAffordance();
  }, [tab, mobileLayoutMode, isMobileViewport, updateProjectionHorizontalAffordance, projectionTableScrollRef]);

  const emptyStateActions = (
    <ProjectionEmptyStateActions
      clearAllFilters={clearAllFilters}
      clearFiltersDisabled={emptyStateModel.clearFiltersDisabled}
      showTurnOffWatchlistAction={emptyStateModel.showTurnOffWatchlistAction}
      setWatchlistOnly={setWatchlistOnly}
      applyProjectionFilterPreset={applyProjectionFilterPreset}
      setSearch={setSearch}
      showSwitchToCareerTotalsAction={emptyStateModel.showSwitchToCareerTotalsAction}
      setYearFilter={setYearFilter}
      careerTotalsFilterValue={CAREER_TOTALS_FILTER_VALUE}
    />
  );

  return (
    <div className="fade-up fade-up-1">
      <ProjectionSectionTabs tab={tab as "bat" | "pitch" | "all"} onSelectTab={handleSelectTab} />

      <ProjectionFilterBar
        tab={tab}
        meta={meta as { years: (string | number)[]; teams: string[] }}
        search={search}
        resolvedYearFilter={resolvedYearFilter}
        teamFilter={teamFilter}
        posFilters={posFilters}
        watchlistOnly={watchlistOnly}
        watchlistCount={watchlistCount}
        totalRows={totalRows}
        loading={loading}
        searchIsDebouncing={searchIsDebouncing}
        setSearch={setSearch}
        setTeamFilter={setTeamFilter}
        setYearFilter={setYearFilter}
        setPosFilters={setPosFilters}
        setWatchlistOnly={setWatchlistOnly}
        activeProjectionPresetKey={activeProjectionPresetKey}
        projectionFilterPresets={projectionFilterPresets}
        applyProjectionFilterPreset={applyProjectionFilterPreset}
        saveCustomProjectionPreset={saveCustomProjectionPreset}
        clearAllFilters={clearAllFilters}
        hasActiveFilters={hasActiveFilters}
        activeFilterChips={activeFilterChips}
        tableColumnCatalog={tableColumnCatalog}
        resolvedProjectionTableHiddenCols={resolvedProjectionTableHiddenCols as Record<string, boolean>}
        requiredProjectionTableCols={requiredProjectionTableCols as Set<string>}
        toggleProjectionTableColumn={toggleProjectionTableColumn}
        showAllProjectionTableColumns={showAllProjectionTableColumns}
        colLabels={colLabels}
        exportingFormat={exportingFormat}
        exportCurrentProjections={exportCurrentProjections}
        tierLimits={tierLimits}
      />
      <ProjectionOverlayBanner
        hasCalculatorOverlay={hasCalculatorOverlay}
        resolvedCalculatorOverlayPlayerCount={resolvedCalculatorOverlayPlayerCount}
        overlayStatusMeta={overlayStatusMeta}
        showOverlayWhy={showOverlayWhy}
        setShowOverlayWhy={setShowOverlayWhy as React.Dispatch<React.SetStateAction<boolean>>}
        onClearCalculatorOverlay={onClearCalculatorOverlay}
      />
      <ProjectionStatusMessages
        pageResetNotice={pageResetNotice}
        clearPageResetNotice={clearPageResetNotice}
        exportError={exportError}
        clearExportError={clearExportError}
        compareShareCopyNotice={compareShareCopyNotice}
        clearCompareShareCopyNotice={clearCompareShareCopyNotice}
        compareShareHydrating={compareShareHydrating}
        compareShareNotice={compareShareNotice}
        clearCompareShareNotice={clearCompareShareNotice}
        lastRefreshedLabel={lastRefreshedLabel}
      />

      <ProjectionCollectionsWorkspace
        showCollectionsWorkspace={showCollectionsWorkspace}
        watchlistCount={watchlistCount}
        watchlistOnly={watchlistOnly}
        watchlist={resolvedWatchlist as unknown as Record<string, { player?: string; [key: string]: unknown }>}
        watchlistEntries={sortedWatchlistEntries}
        clearWatchlist={clearWatchlist}
        exportWatchlistCsv={exportWatchlistCsv}
        removeWatchlistEntry={removeWatchlistEntry}
        compareRowsCount={compareRowsCount}
        maxComparePlayers={maxComparePlayers}
        clearCompareRows={clearCompareRows}
        compareRows={compareRows}
        comparisonColumns={comparisonColumns}
        removeCompareRow={removeCompareRow}
        copyCompareShareLink={copyCompareShareLink}
        colLabels={colLabels}
        formatCellValue={formatCellValue}
      />

      <ProjectionLayoutControls
        isMobileViewport={isMobileViewport}
        mobileLayoutMode={mobileLayoutMode}
        setMobileLayoutMode={setMobileLayoutMode as (mode: string) => void}
        cardColumnCatalog={cardColumnCatalog}
        resolvedProjectionCardHiddenCols={resolvedProjectionCardHiddenCols as Record<string, boolean>}
        requiredProjectionCardCols={requiredProjectionCardCols as Set<string>}
        toggleProjectionCardColumn={toggleProjectionCardColumn}
        showAllProjectionCardColumns={showAllProjectionCardColumns}
        colLabels={colLabels}
      />

      <ProjectionResultsShell
        showCards={showCards}
        displayedPage={displayedPage}
        showInitialLoadSkeleton={showInitialLoadSkeleton}
        error={error}
        retryFetch={retryFetch}
        emptyStateHeadline={emptyStateModel.headline}
        emptyStateGuidance={emptyStateModel.guidance}
        emptyStateActions={emptyStateActions}
        cardRowsMarkup={cardRowsMarkup}
        showMobileSwipeHint={showMobileSwipeHint}
        swipeHintText={swipeHintModel.swipeHintText}
        canScrollLeft={canScrollLeft}
        canScrollRight={canScrollRight}
        showInlineRefreshError={showInlineRefreshError}
        loading={loading}
        cols={cols}
        colLabels={colLabels}
        sortCol={sortCol}
        sortDir={sortDir as "asc" | "desc"}
        onSort={handleSort}
        projectionTableScrollRef={projectionTableScrollRef as React.RefObject<HTMLDivElement | null>}
        onTableScroll={handleProjectionTableScroll}
        tableRowsMarkup={tableRowsMarkup}
        totalRows={totalRows}
        limit={limit}
        offset={offset}
        setOffset={setOffset}
      />

      {profileRow && (
        <PlayerProfile
          row={profileRow}
          tab={tab}
          apiBase={apiBase}
          calculatorJobId={activeCalculatorJobId}
          onClose={handleCloseProfile}
        />
      )}
    </div>
  );
}
