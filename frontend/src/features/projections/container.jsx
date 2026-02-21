import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ColumnChooserControl } from "../../ui_components.jsx";
import {
  projectionRowKey,
  stablePlayerKeyFromRow,
} from "../../app_state_storage.js";
import {
  INT_COLS,
  THREE_DECIMAL_COLS,
  TWO_DECIMAL_COLS,
  WHOLE_NUMBER_COLS,
  fmt,
  fmtInt,
  formatCellValue,
  parsePosTokens,
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
import { ProjectionComparisonPanel } from "./components/ProjectionComparisonPanel.jsx";
import { ProjectionWatchlistPanel } from "./components/ProjectionWatchlistPanel.jsx";
import {
  CAREER_TOTALS_FILTER_VALUE,
  DEFAULT_PROJECTIONS_SORT_COL,
  DEFAULT_PROJECTIONS_SORT_DIR,
  DEFAULT_PROJECTIONS_TAB,
  useProjectionsData,
} from "../../hooks/useProjectionsData.js";
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
  calculatorOverlayPlayerCount,
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

  const [showPosMenu, setShowPosMenu] = useState(false);
  const posMenuRef = useRef(null);

  const resolvedCalculatorOverlayByPlayerKey = useMemo(() => (
    calculatorOverlayByPlayerKey && typeof calculatorOverlayByPlayerKey === "object" && !Array.isArray(calculatorOverlayByPlayerKey)
      ? calculatorOverlayByPlayerKey
      : {}
  ), [calculatorOverlayByPlayerKey]);
  const resolvedCalculatorOverlayPlayerCount = useMemo(
    () => Number.isFinite(Number(calculatorOverlayPlayerCount))
      ? Math.max(0, Number(calculatorOverlayPlayerCount))
      : Object.keys(resolvedCalculatorOverlayByPlayerKey).length,
    [calculatorOverlayPlayerCount, resolvedCalculatorOverlayByPlayerKey]
  );
  const hasCalculatorOverlay = Boolean(calculatorOverlayActive) && resolvedCalculatorOverlayPlayerCount > 0;
  const applyCalculatorOverlayToRows = useCallback(rows => {
    if (!Array.isArray(rows) || rows.length === 0) return [];
    if (!hasCalculatorOverlay) return rows;
    return rows.map(row => {
      const key = stablePlayerKeyFromRow(row);
      const overlay = resolvedCalculatorOverlayByPlayerKey[key];
      if (!overlay || typeof overlay !== "object") return row;
      return { ...row, ...overlay, DynastyMatchStatus: "matched" };
    });
  }, [hasCalculatorOverlay, resolvedCalculatorOverlayByPlayerKey]);
  const data = useMemo(
    () => applyCalculatorOverlayToRows(baseData),
    [applyCalculatorOverlayToRows, baseData]
  );

  useEffect(() => {
    function handleOutsideClick(event) {
      if (posMenuRef.current && !posMenuRef.current.contains(event.target)) {
        setShowPosMenu(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  const positionOptions = useMemo(() => {
    const rawPositions = tab === "all"
      ? [...(meta.bat_positions || []), ...(meta.pit_positions || [])]
      : tab === "bat"
        ? (meta.bat_positions || [])
        : (meta.pit_positions || []);
    const uniq = new Set();
    rawPositions.forEach(pos => {
      parsePosTokens(pos).forEach(token => uniq.add(token));
    });
    if (tab === "bat") uniq.delete("SP");

    const order = ["C", "1B", "2B", "3B", "SS", "OF", "DH", "UT", "SP", "RP"];
    return Array.from(uniq).sort((a, b) => {
      const ai = order.indexOf(a);
      const bi = order.indexOf(b);
      if (ai !== -1 || bi !== -1) {
        if (ai === -1) return 1;
        if (bi === -1) return -1;
        return ai - bi;
      }
      return a.localeCompare(b);
    });
  }, [tab, meta.bat_positions, meta.pit_positions]);

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
  const posFilterLabel = posFilters.length === 0
    ? "All Positions"
    : posFilters.length <= 2
      ? posFilters.join(", ")
      : `${posFilters.length} Positions`;
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

  function togglePosFilter(pos) {
    setPosFilters(curr => (
      curr.includes(pos) ? curr.filter(p => p !== pos) : [...curr, pos]
    ));
  }

  useEffect(() => {
    const onResize = () => updateProjectionHorizontalAffordance();
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
  }, [tab, mobileLayoutMode, isMobileViewport, updateProjectionHorizontalAffordance]);

  return (
    <div className="fade-up fade-up-1">
      <div className="section-tabs">
        <button className={`section-tab ${tab==="all"?"active":""}`} onClick={() => {setTab(DEFAULT_PROJECTIONS_TAB); setSortCol(DEFAULT_PROJECTIONS_SORT_COL); setSortDir(DEFAULT_PROJECTIONS_SORT_DIR); setOffset(0); setPosFilters([]); setShowPosMenu(false);}} aria-pressed={tab==="all"}>All</button>
        <button className={`section-tab ${tab==="bat"?"active":""}`} onClick={() => {setTab("bat"); setSortCol(DEFAULT_PROJECTIONS_SORT_COL); setSortDir(DEFAULT_PROJECTIONS_SORT_DIR); setOffset(0); setPosFilters([]); setShowPosMenu(false);}} aria-pressed={tab==="bat"}>Hitters</button>
        <button className={`section-tab ${tab==="pitch"?"active":""}`} onClick={() => {setTab("pitch"); setSortCol(DEFAULT_PROJECTIONS_SORT_COL); setSortDir(DEFAULT_PROJECTIONS_SORT_DIR); setOffset(0); setPosFilters([]); setShowPosMenu(false);}} aria-pressed={tab==="pitch"}>Pitchers</button>
      </div>

      <div className="filter-bar">
        <label className="sr-only" htmlFor="projections-search">Search player name</label>
        <input
          id="projections-search"
          type="text"
          placeholder="Search player name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <label className="sr-only" htmlFor="projections-year-filter">Projection year view</label>
        <select id="projections-year-filter" value={resolvedYearFilter} onChange={e => setYearFilter(e.target.value)}>
          <option value={CAREER_TOTALS_FILTER_VALUE}>Rest of Career Totals</option>
          {meta.years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <label className="sr-only" htmlFor="projections-team-filter">Team filter</label>
        <select id="projections-team-filter" value={teamFilter} onChange={e => setTeamFilter(e.target.value)}>
          <option value="">All Teams</option>
          {meta.teams.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <div className="multi-select" ref={posMenuRef}>
          <button
            type="button"
            className={`multi-select-trigger ${showPosMenu ? "open" : ""}`}
            onClick={() => setShowPosMenu(open => !open)}
            aria-haspopup="listbox"
            aria-expanded={showPosMenu}
            aria-controls="projections-position-menu"
            aria-label="Filter positions"
          >
            <span className="multi-select-label">
              <span>{posFilterLabel}</span>
              <span className="multi-select-chevron">{showPosMenu ? "▲" : "▼"}</span>
            </span>
          </button>
          {showPosMenu && (
            <div id="projections-position-menu" className="multi-select-menu" role="listbox" aria-multiselectable="true">
              <button
                type="button"
                className="multi-select-clear"
                onClick={() => setPosFilters([])}
                disabled={posFilters.length === 0}
              >
                Clear position filters
              </button>
              {positionOptions.map(pos => (
                <label key={pos} className="multi-select-option">
                  <input
                    type="checkbox"
                    checked={posFilters.includes(pos)}
                    onChange={() => togglePosFilter(pos)}
                  />
                  <span>{pos}</span>
                </label>
              ))}
            </div>
          )}
        </div>
        {ColumnChooserControl && (
          <ColumnChooserControl
            buttonLabel="Table Columns"
            columns={tableColumnCatalog}
            hiddenCols={resolvedProjectionTableHiddenCols}
            requiredCols={requiredProjectionTableCols}
            onToggleColumn={toggleProjectionTableColumn}
            onShowAllColumns={showAllProjectionTableColumns}
            columnLabels={colLabels}
          />
        )}
        <span className={`result-count ${loading || searchIsDebouncing ? "loading" : ""}`.trim()} aria-live="polite" aria-atomic="true" aria-busy={loading || searchIsDebouncing}>
          {watchlistOnly ? `${totalRows.toLocaleString()} watchlist rows` : `${totalRows.toLocaleString()} rows`}
          {searchIsDebouncing ? " · typing..." : loading ? " · refreshing..." : ""}
        </span>
        <button
          type="button"
          className={`inline-btn ${watchlistOnly ? "open" : ""}`.trim()}
          onClick={() => setWatchlistOnly(value => !value)}
          disabled={watchlistCount === 0}
        >
          {watchlistOnly ? "All Players View" : "Watchlist View"}
        </button>
        <button
          type="button"
          className="inline-btn"
          onClick={() => exportCurrentProjections("csv")}
          disabled={Boolean(exportingFormat)}
        >
          {exportingFormat === "csv" ? "Exporting CSV..." : "Export CSV"}
        </button>
        <button
          type="button"
          className="inline-btn"
          onClick={() => exportCurrentProjections("xlsx")}
          disabled={Boolean(exportingFormat)}
        >
          {exportingFormat === "xlsx" ? "Exporting XLSX..." : "Export XLSX"}
        </button>
      </div>
      {hasCalculatorOverlay && (
        <div className="table-refresh-message projections-overlay-message" role="status" aria-live="polite">
          Showing calculator-adjusted dynasty values for matched players ({resolvedCalculatorOverlayPlayerCount.toLocaleString()} available).
        </div>
      )}
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
        <span className="collection-toolbar-label">Compare: {compareRows.length}/{maxComparePlayers}</span>
        <button type="button" className="inline-btn" onClick={clearCompareRows} disabled={compareRows.length === 0}>
          Clear Compare
        </button>
      </div>
      <ProjectionComparisonPanel
        compareRows={compareRows}
        maxComparePlayers={maxComparePlayers}
        comparisonColumns={comparisonColumns}
        colLabels={colLabels}
        formatCellValue={formatCellValue}
        removeCompareRow={removeCompareRow}
      />
      <ProjectionWatchlistPanel
        watchlistCount={watchlistCount}
        watchlist={watchlist}
        removeWatchlistEntry={removeWatchlistEntry}
      />
      <div className="projection-layout-controls" role="group" aria-label="Projection layout controls">
          <div className="projection-layout-row">
            <span className="label">Layout</span>
            <div className="projection-view-toggle">
              <button
                type="button"
                className={`projection-view-btn ${mobileLayoutMode === "cards" ? "active" : ""}`.trim()}
                onClick={() => setMobileLayoutMode("cards")}
                aria-pressed={mobileLayoutMode === "cards"}
              >
                Cards
              </button>
              <button
                type="button"
                className={`projection-view-btn ${mobileLayoutMode === "table" ? "active" : ""}`.trim()}
                onClick={() => setMobileLayoutMode("table")}
                aria-pressed={mobileLayoutMode === "table"}
              >
                Table
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
            <div className="projection-card-empty">No results found for this page.</div>
          ) : (
            displayedPage.map((row, idx) => {
              const rowWatch = isRowWatched(row);
              const compareKey = stablePlayerKeyFromRow(row);
              const isCompared = Boolean(compareRowsByKey[compareKey]);
              const rowWithRank = { ...row, Rank: offset + idx + 1 };
              const cardCols = projectionCardColumnsForRow(rowWithRank);
              return (
                <article className="projection-card" key={projectionRowKey(row, offset + idx)}>
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
                        disabled={!isCompared && compareRows.length >= maxComparePlayers}
                      >
                        {isCompared ? "Compared" : "Compare"}
                      </button>
                    </div>
                  </div>
                  <p className="projection-card-meta">{row.Team || "—"} · {row.Pos || "—"}</p>
                  <dl>
                    {cardCols.map(col => (
                      <div className="projection-card-stat" key={`${projectionRowKey(row, offset + idx)}-${col}`}>
                        <dt>{colLabels[col] || col}</dt>
                        <dd>{formatCellValue(col, rowWithRank[col])}</dd>
                      </div>
                    ))}
                  </dl>
                </article>
              );
            })
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
                    <th
                      key={c}
                      scope="col"
                      className={`${sortCol === c ? "sorted" : ""}${c === "Player" ? " player-col" : ""}`.trim()}
                      onClick={() => handleSort(c)}
                      onKeyDown={event => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          handleSort(c);
                        }
                      }}
                      tabIndex={0}
                      aria-sort={sortCol === c ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                      aria-label={`Sort by ${colLabels[c] || c}`}
                    >
                      {colLabels[c] || c}
                      {sortCol === c && <span className="sort-arrow">{sortDir === "asc" ? "▲" : "▼"}</span>}
                    </th>
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
                  <tr><td colSpan={cols.length + 2} style={{textAlign:"center",padding:"40px",color:"var(--text-muted)"}}>No results found</td></tr>
                ) : (
                  displayedPage.map((row, i) => {
                    const rowWatch = isRowWatched(row);
                    const compareKey = stablePlayerKeyFromRow(row);
                    const isCompared = Boolean(compareRowsByKey[compareKey]);
                    return (
                      <tr key={projectionRowKey(row, offset + i)}>
                        <td className="num index-col" style={{color:"var(--text-muted)"}}>{offset + i + 1}</td>
                        {cols.map(c => {
                          const val = row[c];
                          if (c === "Player") return <td key={c} className="player-name">{val}</td>;
                          if (c === "Pos") return <td key={c} className="pos">{val}</td>;
                          if (c === "Team") return <td key={c} className="team">{val}</td>;
                          if (c === "DynastyValue" || c.startsWith("Value_")) {
                            if ((val == null || val === "") && c === "DynastyValue" && row.DynastyMatchStatus === "no_unique_match") {
                              return <td key={c} className="num" style={{color:"var(--text-muted)"}}>No unique match</td>;
                            }
                            const n = Number(val);
                            const cls = n > 0 ? "value-positive" : n < 0 ? "value-negative" : "";
                            return <td key={c} className={`num ${cls}`}>{fmt(val, 2)}</td>;
                          }
                          if (twoDecimalCols.has(c)) return <td key={c} className="num">{fmt(val, 2)}</td>;
                          if (threeDecimalCols.has(c)) return <td key={c} className="num">{fmt(val, 3)}</td>;
                          if (wholeNumberCols.has(c)) return <td key={c} className="num">{fmtInt(val, true)}</td>;
                          if (intCols.has(c)) return <td key={c} className="num">{fmtInt(val, c !== "Year")}</td>;
                          if (typeof val === "number") return <td key={c} className="num">{fmt(val)}</td>;
                          return <td key={c}>{val ?? "—"}</td>;
                        })}
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
                            disabled={!isCompared && compareRows.length >= maxComparePlayers}
                          >
                            {isCompared ? "Compared" : "Compare"}
                          </button>
                        </td>
                      </tr>
                    );
                  })
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
