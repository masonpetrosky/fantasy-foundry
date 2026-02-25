import React, {
  Suspense,
  lazy,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  SortableHeaderCell,
} from "../../accessibility_components.jsx";
import {
  projectionRowKey,
  stablePlayerKeyFromRow,
} from "../../app_state_storage.js";
import { trackEvent } from "../../analytics.js";
import {
  INT_COLS,
  THREE_DECIMAL_COLS,
  TWO_DECIMAL_COLS,
  WHOLE_NUMBER_COLS,
  fmt,
  fmtInt,
  formatCellValue,
} from "../../formatting_utils.js";
import {
  useProjectionColumnVisibility,
} from "./hooks/useProjectionColumnVisibility.js";
import {
  useProjectionCollections,
} from "./hooks/useProjectionCollections.js";
import {
  useProjectionExport,
} from "./hooks/useProjectionExport.js";
import {
  useProjectionLayoutState,
} from "./hooks/useProjectionLayoutState.js";
import {
  useProjectionOverlay,
} from "./hooks/useProjectionOverlay.js";
import {
  useProjectionFilterPresets,
} from "./hooks/useProjectionFilterPresets.js";
import {
  CAREER_TOTALS_FILTER_VALUE,
  DEFAULT_PROJECTIONS_SORT_COL,
  DEFAULT_PROJECTIONS_SORT_DIR,
  DEFAULT_PROJECTIONS_TAB,
  useProjectionsData,
} from "../../hooks/useProjectionsData.js";
import {
  buildActiveFilterChips,
} from "./view_state.js";
import { ProjectionOverlayBanner } from "./components/ProjectionOverlayBanner.jsx";
import { ProjectionFilterBar } from "./components/ProjectionFilterBar.jsx";
import { ColumnChooserControl } from "../../ui_components.jsx";

const LazyProjectionComparisonPanel = lazy(() => (
  import("./components/ProjectionComparisonPanel.jsx").then(module => ({
    default: module.ProjectionComparisonPanel,
  }))
));
const LazyProjectionWatchlistPanel = lazy(() => (
  import("./components/ProjectionWatchlistPanel.jsx").then(module => ({
    default: module.ProjectionWatchlistPanel,
  }))
));
export function ProjectionsExplorer({
  apiBase,
  meta,
  dataVersion,
  watchlist,
  setWatchlist,
  activeCalculatorSettings,
  calculatorOverlayByPlayerKey,
  calculatorOverlayActive,
  calculatorOverlayJobId,
  calculatorOverlayDataVersion,
  calculatorOverlayPlayerCount,
  calculatorOverlaySummary,
  onClearCalculatorOverlay,
}) {
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
  const emptyStateTrackedRef = useRef("");

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
    setTab, setSearch, setTeamFilter, setYearFilter,
    setPosFilters, setWatchlistOnly, setSortCol, setSortDir, setOffset,
  }), [setTab, setSearch, setTeamFilter, setYearFilter,
       setPosFilters, setWatchlistOnly, setSortCol, setSortDir, setOffset]);

  const filterState = useMemo(() => ({
    tab, search, teamFilter, resolvedYearFilter,
    posFilters, watchlistOnly, sortCol, sortDir,
  }), [tab, search, teamFilter, resolvedYearFilter,
       posFilters, watchlistOnly, sortCol, sortDir]);

  const {
    projectionFilterPresets,
    applyProjectionFilterPreset,
    saveCustomProjectionPreset,
    activeProjectionPresetKey,
    clearAllFilters,
  } = useProjectionFilterPresets({ filterActions, filterState, setShowPosMenu });

  const page = data;
  const {
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
    maxComparePlayers,
  } = useProjectionCollections({
    watchlist,
    setWatchlist,
    data,
  });

  function handleSort(col) {
    if (sortCol === col) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir(col === "Player" || col === "Team" || col === "Pos" || col === "Type" || col === "Year" || col === "Years" ? "asc" : "desc");
    }
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
  } = useProjectionExport({
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
    const labels = {
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
  const threeDecimalCols = THREE_DECIMAL_COLS;
  const twoDecimalCols = TWO_DECIMAL_COLS;
  const wholeNumberCols = WHOLE_NUMBER_COLS;
  const intCols = INT_COLS;
  const displayedPage = page;
  const showCards = mobileLayoutMode === "cards";
  const showInitialLoadSkeleton = loading && displayedPage.length === 0;
  const showInlineRefreshError = Boolean(error) && displayedPage.length > 0;
  const searchIsDebouncing = search !== debouncedSearch;
  const showMobileSwipeHint = !showCards && isMobileViewport && (canScrollLeft || canScrollRight);
  const swipeHintText = !canScrollLeft && canScrollRight
    ? "Swipe left for more columns →"
    : canScrollLeft && canScrollRight
      ? "← Swipe both directions for more columns →"
      : "← Swipe right to return";
  const comparisonColumns = tab === "bat"
    ? [seasonCol, "DynastyValue", "AB", "R", "HR", "RBI", "SB", "AVG"]
    : tab === "pitch"
      ? [seasonCol, "DynastyValue", "IP", "W", "K", "SV", "ERA", "WHIP"]
      : [seasonCol, "DynastyValue", "AB", "R", "HR", "RBI", "SB", "IP", "W", "K", "SV", "ERA", "WHIP"];
  const compareRowsCount = compareRows.length;

  const formatProjectionCell = useCallback((col, row) => {
    const val = row[col];
    if (col === "Player") return <td key={col} className="player-name">{val}</td>;
    if (col === "Pos") return <td key={col} className="pos">{val}</td>;
    if (col === "Team") return <td key={col} className="team">{val}</td>;
    if (col === "DynastyValue" || col.startsWith("Value_")) {
      if ((val == null || val === "") && col === "DynastyValue" && row.DynastyMatchStatus === "no_unique_match") {
        return <td key={col} className="num" style={{color:"var(--text-muted)"}}>No unique match</td>;
      }
      const n = Number(val);
      const cls = n > 0 ? "value-positive" : n < 0 ? "value-negative" : "";
      return <td key={col} className={`num ${cls}`}>{fmt(val, 2)}</td>;
    }
    if (twoDecimalCols.has(col)) return <td key={col} className="num">{fmt(val, 2)}</td>;
    if (threeDecimalCols.has(col)) return <td key={col} className="num">{fmt(val, 3)}</td>;
    if (wholeNumberCols.has(col)) return <td key={col} className="num">{fmtInt(val, true)}</td>;
    if (intCols.has(col)) return <td key={col} className="num">{fmtInt(val, col !== "Year")}</td>;
    if (typeof val === "number") return <td key={col} className="num">{fmt(val)}</td>;
    return <td key={col}>{val ?? "—"}</td>;
  }, [intCols, threeDecimalCols, twoDecimalCols, wholeNumberCols]);
  const cardRowsMarkup = useMemo(() => {
    if (!showCards || displayedPage.length === 0) return [];

    return displayedPage.map((row, idx) => {
      const rowWatch = isRowWatched(row);
      const compareKey = stablePlayerKeyFromRow(row);
      const isCompared = Boolean(compareRowsByKey[compareKey]);
      const rowWithRank = { ...row, Rank: offset + idx + 1 };
      const cardCols = projectionCardColumnsForRow(rowWithRank);
      const rowKey = projectionRowKey(row, offset + idx);

      return (
        <article className="projection-card" key={rowKey}>
          <div className="projection-card-head">
            <h4>{row.Player || "Player"}</h4>
            <div className="projection-card-actions">
              <button
                type="button"
                className={`inline-btn ${rowWatch ? "open" : ""}`.trim()}
                onClick={() => toggleRowWatch(row)}
              >
                {rowWatch ? "Tracked" : "Track"}
              </button>
              <button
                type="button"
                className={`inline-btn ${isCompared ? "open" : ""}`.trim()}
                onClick={() => toggleCompareRow(row)}
                disabled={!isCompared && compareRowsCount >= maxComparePlayers}
              >
                {isCompared ? "Compared" : "Compare"}
              </button>
              <button
                type="button"
                className={`inline-btn ${rowWatch && isCompared ? "open" : ""}`.trim()}
                onClick={() => quickAddRow(row)}
                disabled={!isCompared && !rowWatch && compareRowsCount >= maxComparePlayers}
                aria-label="Quick add to watchlist and compare"
              >
                {rowWatch && isCompared ? "Quick Added" : "Quick +"}
              </button>
            </div>
          </div>
          <p className="projection-card-meta">{row.Team || "—"} · {row.Pos || "—"}</p>
          <dl>
            {cardCols.map(col => (
              <div className="projection-card-stat" key={`${rowKey}-${col}`}>
                <dt>{colLabels[col] || col}</dt>
                <dd>{formatCellValue(col, rowWithRank[col])}</dd>
              </div>
            ))}
          </dl>
        </article>
      );
    });
  }, [
    showCards,
    displayedPage,
    isRowWatched,
    compareRowsByKey,
    offset,
    projectionCardColumnsForRow,
    compareRowsCount,
    maxComparePlayers,
    colLabels,
    toggleRowWatch,
    toggleCompareRow,
    quickAddRow,
  ]);
  const tableRowsMarkup = useMemo(() => {
    if (showCards || displayedPage.length === 0) return [];

    return displayedPage.map((row, i) => {
      const rowWatch = isRowWatched(row);
      const compareKey = stablePlayerKeyFromRow(row);
      const isCompared = Boolean(compareRowsByKey[compareKey]);
      const rowKey = projectionRowKey(row, offset + i);

      return (
        <tr key={rowKey}>
          <td className="num index-col" style={{color:"var(--text-muted)"}}>{offset + i + 1}</td>
          {cols.map(col => formatProjectionCell(col, row))}
          <td className="row-actions-cell">
            <button
              type="button"
              className={`inline-btn ${rowWatch ? "open" : ""}`.trim()}
              onClick={() => toggleRowWatch(row)}
            >
              {rowWatch ? "Tracked" : "Track"}
            </button>
            <button
              type="button"
              className={`inline-btn ${isCompared ? "open" : ""}`.trim()}
              onClick={() => toggleCompareRow(row)}
              disabled={!isCompared && compareRowsCount >= maxComparePlayers}
            >
              {isCompared ? "Compared" : "Compare"}
            </button>
            <button
              type="button"
              className={`inline-btn ${rowWatch && isCompared ? "open" : ""}`.trim()}
              onClick={() => quickAddRow(row)}
              disabled={!isCompared && !rowWatch && compareRowsCount >= maxComparePlayers}
              aria-label="Quick add to watchlist and compare"
            >
              {rowWatch && isCompared ? "Quick Added" : "Quick +"}
            </button>
          </td>
        </tr>
      );
    });
  }, [
    showCards,
    displayedPage,
    isRowWatched,
    compareRowsByKey,
    offset,
    cols,
    formatProjectionCell,
    toggleRowWatch,
    toggleCompareRow,
    quickAddRow,
    compareRowsCount,
    maxComparePlayers,
  ]);

  useEffect(() => {
    const onResize = () => updateProjectionHorizontalAffordance();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [updateProjectionHorizontalAffordance]);

  useEffect(() => {
    if (loading || error || displayedPage.length > 0) return;
    const marker = [
      tab,
      resolvedYearFilter,
      teamFilter,
      watchlistOnly ? "watchlist" : "all",
      search.trim(),
      posFilters.join(","),
    ].join("|");
    if (emptyStateTrackedRef.current === marker) return;
    emptyStateTrackedRef.current = marker;
    trackEvent("ff_projection_empty_state_seen", {
      tab,
      watchlist_only: watchlistOnly,
      has_search: Boolean(search.trim()),
      has_team_filter: Boolean(teamFilter),
      has_pos_filters: posFilters.length > 0,
      year_view: resolvedYearFilter,
    });
  }, [displayedPage.length, error, loading, posFilters, resolvedYearFilter, search, tab, teamFilter, watchlistOnly]);

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
  }, [tab, mobileLayoutMode, isMobileViewport, updateProjectionHorizontalAffordance]);

  const emptyStateActions = (
    <div className="empty-state-actions">
      <button type="button" className="inline-btn" onClick={clearAllFilters} disabled={!hasActiveFilters}>
        Clear Filters
      </button>
      <button type="button" className="inline-btn" onClick={() => applyProjectionFilterPreset("all", "empty_state")}>
        Show All Players
      </button>
      <button type="button" className="inline-btn" onClick={() => setSearch("Rodriguez")}>
        Try Example Search
      </button>
      {resolvedYearFilter !== CAREER_TOTALS_FILTER_VALUE && (
        <button type="button" className="inline-btn" onClick={() => setYearFilter(CAREER_TOTALS_FILTER_VALUE)}>
          Switch To Career Totals
        </button>
      )}
    </div>
  );

  return (
    <div className="fade-up fade-up-1">
      <div className="section-tabs">
        <button className={`section-tab ${tab==="all"?"active":""}`} onClick={() => {setTab(DEFAULT_PROJECTIONS_TAB); setSortCol(DEFAULT_PROJECTIONS_SORT_COL); setSortDir(DEFAULT_PROJECTIONS_SORT_DIR); setOffset(0); setPosFilters([]); setShowPosMenu(false);}} aria-pressed={tab==="all"}>All</button>
        <button className={`section-tab ${tab==="bat"?"active":""}`} onClick={() => {setTab("bat"); setSortCol(DEFAULT_PROJECTIONS_SORT_COL); setSortDir(DEFAULT_PROJECTIONS_SORT_DIR); setOffset(0); setPosFilters([]); setShowPosMenu(false);}} aria-pressed={tab==="bat"}>Hitters</button>
        <button className={`section-tab ${tab==="pitch"?"active":""}`} onClick={() => {setTab("pitch"); setSortCol(DEFAULT_PROJECTIONS_SORT_COL); setSortDir(DEFAULT_PROJECTIONS_SORT_DIR); setOffset(0); setPosFilters([]); setShowPosMenu(false);}} aria-pressed={tab==="pitch"}>Pitchers</button>
      </div>

      <ProjectionFilterBar
        tab={tab}
        meta={meta}
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
        resolvedProjectionTableHiddenCols={resolvedProjectionTableHiddenCols}
        requiredProjectionTableCols={requiredProjectionTableCols}
        toggleProjectionTableColumn={toggleProjectionTableColumn}
        showAllProjectionTableColumns={showAllProjectionTableColumns}
        colLabels={colLabels}
        exportingFormat={exportingFormat}
        exportCurrentProjections={exportCurrentProjections}
      />
      {pageResetNotice && (
        <div className="table-refresh-message page-reset-notice" role="status" aria-live="polite">
          <span>{pageResetNotice}</span>
          <button type="button" className="inline-btn" onClick={clearPageResetNotice}>Dismiss</button>
        </div>
      )}
      <ProjectionOverlayBanner
        hasCalculatorOverlay={hasCalculatorOverlay}
        resolvedCalculatorOverlayPlayerCount={resolvedCalculatorOverlayPlayerCount}
        overlayStatusMeta={overlayStatusMeta}
        showOverlayWhy={showOverlayWhy}
        setShowOverlayWhy={setShowOverlayWhy}
        onClearCalculatorOverlay={onClearCalculatorOverlay}
      />
      {exportError && (
        <div className="table-refresh-message error" role="status" aria-live="polite">
          Export failed. {exportError}
        </div>
      )}
      <div className="collection-toolbar" role="group" aria-label="Watchlist and comparison actions">
        <span className="collection-toolbar-label">Watchlist: {watchlistCount}</span>
        <span className="collection-toolbar-label">View: {watchlistOnly ? "Watchlist" : "All Players"}</span>
        <button type="button" className="inline-btn" onClick={exportWatchlistCsv} disabled={watchlistCount === 0}>
          Export Watchlist CSV
        </button>
        <button type="button" className="inline-btn" onClick={clearWatchlist} disabled={watchlistCount === 0}>
          Clear Watchlist
        </button>
        <span className="collection-toolbar-label">Compare: {compareRowsCount}/{maxComparePlayers}</span>
        <button type="button" className="inline-btn" onClick={clearCompareRows} disabled={compareRowsCount === 0}>
          Clear Compare
        </button>
      </div>
      {compareRowsCount > 0 && (
        <Suspense fallback={null}>
          <LazyProjectionComparisonPanel
            compareRows={compareRows}
            maxComparePlayers={maxComparePlayers}
            comparisonColumns={comparisonColumns}
            colLabels={colLabels}
            formatCellValue={formatCellValue}
            removeCompareRow={removeCompareRow}
          />
        </Suspense>
      )}
      {watchlistCount > 0 && (
        <Suspense fallback={null}>
          <LazyProjectionWatchlistPanel
            watchlistCount={watchlistCount}
            watchlist={watchlist}
            removeWatchlistEntry={removeWatchlistEntry}
          />
        </Suspense>
      )}
      <div className="projection-layout-controls" role="group" aria-label="Projection layout controls">
          <div className="projection-layout-row">
            <span className="label">
              Layout
              {isMobileViewport ? ` · Viewing ${mobileLayoutMode === "cards" ? "Cards" : "Table"}` : ""}
            </span>
            <div className="projection-view-toggle">
              <button
                type="button"
                className={`projection-view-btn ${mobileLayoutMode === "cards" ? "active" : ""}`.trim()}
                onClick={() => setMobileLayoutMode("cards")}
                aria-pressed={mobileLayoutMode === "cards"}
              >
                Card View
              </button>
              <button
                type="button"
                className={`projection-view-btn ${mobileLayoutMode === "table" ? "active" : ""}`.trim()}
                onClick={() => setMobileLayoutMode("table")}
                aria-pressed={mobileLayoutMode === "table"}
              >
                Table View
              </button>
            </div>
          </div>
          {mobileLayoutMode === "cards" && ColumnChooserControl && (
            <div className="projection-layout-row">
              <span className="label">Cards</span>
              <ColumnChooserControl
                buttonLabel="Card Stats"
                columns={cardColumnCatalog}
                hiddenCols={resolvedProjectionCardHiddenCols}
                requiredCols={requiredProjectionCardCols}
                onToggleColumn={toggleProjectionCardColumn}
                onShowAllColumns={showAllProjectionCardColumns}
                columnLabels={colLabels}
              />
            </div>
          )}
      </div>
      {showCards && (
        <div className="projection-card-list">
          {showInitialLoadSkeleton ? (
            Array.from({ length: 8 }).map((_, idx) => (
              <div className="projection-card" key={`loading-card-${idx}`}>
                <div className="loading-shimmer" style={{ width: "60%", margin: 0 }} />
                <div className="loading-shimmer" style={{ width: "90%", marginTop: 10 }} />
              </div>
            ))
          ) : error && displayedPage.length === 0 ? (
            <div className="projection-card-empty">Unable to load projections. {error}{" "}<button type="button" className="inline-btn" onClick={retryFetch}>Retry</button></div>
          ) : displayedPage.length === 0 ? (
            <div className="projection-card-empty">
              <p>No projections matched these filters.</p>
              {emptyStateActions}
            </div>
          ) : (
            cardRowsMarkup
          )}
        </div>
      )}
      {showMobileSwipeHint && (
        <div className="table-swipe-hint" role="note">
          {swipeHintText}
        </div>
      )}
      {showInlineRefreshError && (
        <div className="table-refresh-message error" role="status" aria-live="polite">
          Refresh failed. Showing last loaded page. {error}
        </div>
      )}
      {loading && displayedPage.length > 0 && !showInlineRefreshError && (
        <div className="table-refresh-message" role="status" aria-live="polite">
          Refreshing results...
        </div>
      )}

      {(!showCards || totalRows > limit) && (
      <div className="table-wrapper">
        {!showCards && (
          <div className="table-scroll" ref={projectionTableScrollRef} onScroll={handleProjectionTableScroll}>
            <table className="projections-table">
              <thead>
                <tr>
                  <th scope="col" className="index-col" style={{width:40}}>#</th>
                  {cols.map(c => (
                    <SortableHeaderCell
                      key={c}
                      columnKey={c}
                      label={colLabels[c] || c}
                      sortCol={sortCol}
                      sortDir={sortDir}
                      onSort={handleSort}
                      className={`${sortCol === c ? "sorted" : ""}${c === "Player" ? " player-col" : ""}`.trim()}
                    />
                  ))}
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {showInitialLoadSkeleton ? (
                  Array.from({length: 15}).map((_,i) => (
                    <tr key={i}>
                      <td className="index-col"><div className="loading-shimmer" style={{width: 24}}/></td>
                      {cols.map((c,j) => <td key={j}><div className="loading-shimmer" style={{width: c==="Player"?120:50}}/></td>)}
                      <td><div className="loading-shimmer" style={{width: 90}}/></td>
                    </tr>
                  ))
                ) : error && displayedPage.length === 0 ? (
                  <tr>
                    <td colSpan={cols.length + 2} style={{textAlign:"center",padding:"40px",color:"var(--red)"}}>
                      Unable to load projections. {error}{" "}<button type="button" className="inline-btn" onClick={retryFetch}>Retry</button>
                    </td>
                  </tr>
                ) : displayedPage.length === 0 ? (
                  <tr>
                    <td colSpan={cols.length + 2} style={{ textAlign: "center", padding: "34px", color: "var(--text-muted)" }}>
                      <p style={{ marginBottom: "12px" }}>No projections matched these filters.</p>
                      {emptyStateActions}
                    </td>
                  </tr>
                ) : (
                  tableRowsMarkup
                )}
              </tbody>
            </table>
          </div>
        )}
        {totalRows > limit && (
          <div className="pagination">
            <button aria-label="Previous page" disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - limit))}>← Previous</button>
            <span className="page-info">
              {totalRows === 0 ? 0 : offset + 1}–{Math.min(offset + limit, totalRows)} of {totalRows}
            </span>
            <button aria-label="Next page" disabled={offset + limit >= totalRows || loading} onClick={() => setOffset(offset + limit)}>Next →</button>
          </div>
        )}
      </div>
      )}
    </div>
  );
}
