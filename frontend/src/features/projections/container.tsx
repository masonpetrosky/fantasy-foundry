import React, { useCallback, useState } from "react";
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
import { useProjectionExplorerDataView } from "./hooks/useProjectionExplorerDataView";
import { useProjectionEmptyState, useProjectionExplorerShell } from "./hooks/useProjectionExplorerShell";
import { useProjectionWatchlistComposition } from "./hooks/useProjectionWatchlistComposition";
import { CAREER_TOTALS_FILTER_VALUE, useProjectionsData } from "../../hooks/useProjectionsData";
import { useProjectionDeltas } from "../../hooks/useProjectionDeltas";
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
import { useCalculatorOverlayContext } from "../../contexts/CalculatorOverlayContext";
import { useToastContext } from "../../Toast";

interface ProjectionsExplorerProps {
  apiBase: string;
  meta: Record<string, unknown> & { years?: (string | number)[]; teams?: string[] };
  dataVersion: string;
  watchlist: Record<string, PlayerWatchEntry>;
  setWatchlist: React.Dispatch<React.SetStateAction<Record<string, PlayerWatchEntry>>>;
  hasSuccessfulCalcRun: boolean;
  activeCalculatorSettings: CalculatorSettings | null;
  tierLimits: TierLimits | null;
  fantraxRosterPlayerKeys?: Set<string>;
}

export function ProjectionsExplorer({
  apiBase,
  meta,
  dataVersion,
  watchlist,
  setWatchlist,
  hasSuccessfulCalcRun,
  activeCalculatorSettings,
  tierLimits,
  fantraxRosterPlayerKeys,
}: ProjectionsExplorerProps): React.ReactElement {
  const toastCtx = useToastContext();
  const isPointsFocused = String(activeCalculatorSettings?.scoring_mode || "").trim().toLowerCase() === "points";

  const {
    calculatorOverlayByPlayerKey,
    calculatorOverlayActive,
    calculatorOverlayJobId,
    calculatorOverlayDataVersion,
    calculatorOverlayPlayerCount,
    calculatorOverlaySummary,
    clearCalculatorOverlay: onClearCalculatorOverlay,
  } = useCalculatorOverlayContext();
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

  const [rosterOnly, setRosterOnly] = useState(false);
  const closePosMenu = useCallback(() => {}, []);
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
    calculatorOverlayByPlayerKey,
    calculatorOverlayActive,
    calculatorOverlayJobId,
    calculatorOverlayDataVersion,
    calculatorOverlayPlayerCount,
    calculatorOverlaySummary,
    dataVersion,
  });

  const { deltaMap } = useProjectionDeltas(apiBase);
  const {
    data,
    filteredData,
    filterActions,
    filterState,
  } = useProjectionExplorerDataView({
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
  });

  const { projectionFilterPresets, applyProjectionFilterPreset, saveCustomProjectionPreset, activeProjectionPresetKey, clearAllFilters } = useProjectionFilterPresets({
    filterActions,
    filterState,
    setShowPosMenu: closePosMenu,
  });

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

  const seasonCol = careerTotalsView ? "Years" : "Year";
  const dynastyYearCols = selectedDynastyYears.map(year => `Value_${year}`);
  const showCards = mobileLayoutMode === "cards";
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
    activeFilterChips,
    hasActiveFilters,
    handleSort,
    handleSelectTab,
    colLabels,
    swipeHintModel,
    showMobileSwipeHint,
  } = useProjectionExplorerShell({
    isPointsFocused,
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
    colsLength: cols.length,
    displayedPageLength: filteredData.length,
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
  });

  const { exportError, exportingFormat, exportCurrentProjections, clearExportError } = useProjectionExportPipeline({
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

  const displayedPage = filteredData;
  const showInitialLoadSkeleton = loading && displayedPage.length === 0;
  const showInlineRefreshError = Boolean(error) && displayedPage.length > 0;
  const searchIsDebouncing = search !== debouncedSearch;

  const showCollectionsWorkspace = Boolean(hasSuccessfulCalcRun) || workspaceHasWatchlistActivity || workspaceHasComparisonActivity;
  const emptyStateModel = useProjectionEmptyState({
    watchlistOnly,
    resolvedYearFilter,
    hasActiveFilters,
  });

  const { lastRefreshedLabel } = useProjectionTelemetry({
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

  const { cardRowsMarkup, tableRowsMarkup } = useProjectionRowsMarkup({
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

  const emptyStateActions = (
    <ProjectionEmptyStateActions clearAllFilters={clearAllFilters} clearFiltersDisabled={emptyStateModel.clearFiltersDisabled} showTurnOffWatchlistAction={emptyStateModel.showTurnOffWatchlistAction} setWatchlistOnly={setWatchlistOnly} applyProjectionFilterPreset={applyProjectionFilterPreset} setSearch={setSearch} showSwitchToCareerTotalsAction={emptyStateModel.showSwitchToCareerTotalsAction} setYearFilter={setYearFilter} careerTotalsFilterValue={CAREER_TOTALS_FILTER_VALUE} />
  );

  return (
    <main id="main-content" className="fade-up fade-up-1">
      <ProjectionSectionTabs tab={tab as "bat" | "pitch" | "all"} onSelectTab={handleSelectTab} />

      <ProjectionFilterBar
        filterState={{
          tab,
          meta: meta as { bat_positions?: string[]; pit_positions?: string[]; years: (string | number)[]; teams: string[] },
          search,
          resolvedYearFilter,
          teamFilter,
          posFilters,
          watchlistOnly,
          watchlistCount,
          totalRows,
          loading,
          searchIsDebouncing,
          hasActiveFilters,
          activeFilterChips,
        }}
        filterActions={{
          setSearch,
          setTeamFilter,
          setYearFilter,
          setPosFilters,
          setWatchlistOnly,
          clearAllFilters,
        }}
        presetConfig={{
          activeProjectionPresetKey,
          projectionFilterPresets,
          applyProjectionFilterPreset,
          saveCustomProjectionPreset,
        }}
        columnConfig={{
          tableColumnCatalog,
          resolvedProjectionTableHiddenCols: resolvedProjectionTableHiddenCols as Record<string, boolean>,
          requiredProjectionTableCols: requiredProjectionTableCols as Set<string>,
          toggleProjectionTableColumn,
          showAllProjectionTableColumns,
          colLabels,
        }}
        exportConfig={{
          exportingFormat,
          exportCurrentProjections,
        }}
        tierLimits={tierLimits}
        rosterOnly={rosterOnly}
        setRosterOnly={setRosterOnly}
        rosterCount={fantraxRosterPlayerKeys?.size || 0}
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
        projectionTableScrollRef={projectionTableScrollRef}
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
    </main>
  );
}
