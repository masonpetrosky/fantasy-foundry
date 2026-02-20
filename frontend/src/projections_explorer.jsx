import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ColumnChooserControl } from "./ui_components.jsx";
import { parseDownloadFilename } from "./download_filename.js";
import { downloadBlob, triggerBlobDownload } from "./download_helpers.js";
import {
  MAX_COMPARE_PLAYERS,
  PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY,
  PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY,
  PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY,
  buildWatchlistCsv,
  playerWatchEntryFromRow,
  projectionRowKey,
  readHiddenColumnOverridesByTab,
  safeReadStorage,
  safeWriteStorage,
  stablePlayerKeyFromRow,
  writeHiddenColumnOverridesByTab,
} from "./app_state_storage.js";
import {
  INT_COLS,
  THREE_DECIMAL_COLS,
  TWO_DECIMAL_COLS,
  WHOLE_NUMBER_COLS,
  fmt,
  fmtInt,
  formatCellValue,
  parsePosTokens,
} from "./formatting_utils.js";
import { formatApiError, readResponsePayload } from "./request_helpers.js";
import {
  PROJECTION_HITTER_CORE_STATS,
  PROJECTION_PITCHER_CORE_STATS,
  normalizeHiddenColumnOverridesByTab,
  projectionCardColumnCatalog,
  projectionCardOptionalColumnHiddenByDefault,
  projectionTableColumnCatalog,
  projectionTableColumnHiddenByDefault,
  uniqueColumnOrder,
} from "./projections_view_config.js";
import {
  CAREER_TOTALS_FILTER_VALUE,
  DEFAULT_PROJECTIONS_SORT_COL,
  DEFAULT_PROJECTIONS_SORT_DIR,
  DEFAULT_PROJECTIONS_TAB,
  useProjectionsData,
} from "./hooks/useProjectionsData.js";
export function ProjectionsExplorer({
  apiBase,
  meta,
  dataVersion,
  watchlist,
  setWatchlist,
  calculatorOverlayByPlayerKey,
  calculatorOverlayActive,
  calculatorOverlayPlayerCount,
}) {
  const API = String(apiBase || "").trim();
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
  });
  const [isMobileViewport, setIsMobileViewport] = useState(() => (
    window.matchMedia("(max-width: 768px)").matches
  ));
  const [mobileLayoutMode, setMobileLayoutMode] = useState(() => {
    const saved = String(safeReadStorage(PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY) || "").trim().toLowerCase();
    if (saved === "cards" || saved === "table") return saved;
    return window.matchMedia("(max-width: 768px)").matches ? "cards" : "table";
  });
  const [projectionTableHiddenColsByTab, setProjectionTableHiddenColsByTab] = useState(() => (
    readHiddenColumnOverridesByTab(PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY)
  ));
  const [projectionCardHiddenColsByTab, setProjectionCardHiddenColsByTab] = useState(() => (
    readHiddenColumnOverridesByTab(PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY)
  ));
  const [compareRowsByKey, setCompareRowsByKey] = useState({});
  const [showPosMenu, setShowPosMenu] = useState(false);
  const posMenuRef = useRef(null);
  const [exportError, setExportError] = useState("");
  const [exportingFormat, setExportingFormat] = useState("");
  const projectionTableScrollRef = useRef(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
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

  const updateProjectionHorizontalAffordance = useCallback(() => {
    const el = projectionTableScrollRef.current;
    if (!el || !isMobileViewport) {
      setCanScrollLeft(false);
      setCanScrollRight(false);
      return;
    }
    const maxLeft = Math.max(0, el.scrollWidth - el.clientWidth);
    setCanScrollLeft(el.scrollLeft > 2);
    setCanScrollRight(el.scrollLeft < maxLeft - 2);
  }, [isMobileViewport]);

  const handleProjectionTableScroll = useCallback(() => {
    updateProjectionHorizontalAffordance();
  }, [updateProjectionHorizontalAffordance]);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 768px)");
    const onViewportChange = event => {
      setIsMobileViewport(Boolean(event.matches));
    };

    setIsMobileViewport(mediaQuery.matches);
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", onViewportChange);
      return () => mediaQuery.removeEventListener("change", onViewportChange);
    }
    mediaQuery.addListener(onViewportChange);
    return () => mediaQuery.removeListener(onViewportChange);
  }, []);

  useEffect(() => {
    safeWriteStorage(PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY, mobileLayoutMode);
  }, [mobileLayoutMode]);

  useEffect(() => {
    writeHiddenColumnOverridesByTab(PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY, projectionTableHiddenColsByTab);
  }, [projectionTableHiddenColsByTab]);

  useEffect(() => {
    writeHiddenColumnOverridesByTab(PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY, projectionCardHiddenColsByTab);
  }, [projectionCardHiddenColsByTab]);

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
  const watchlistCount = Object.keys(watchlist).length;
  const compareRows = useMemo(
    () => Object.values(compareRowsByKey || {}).filter(Boolean),
    [compareRowsByKey]
  );

  function isRowWatched(row) {
    const key = stablePlayerKeyFromRow(row);
    return Boolean(watchlist[key]);
  }

  function toggleRowWatch(row) {
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
  }

  function removeWatchlistEntry(key) {
    setWatchlist(current => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function clearWatchlist() {
    setWatchlist({});
  }

  function exportWatchlistCsv() {
    const csv = buildWatchlistCsv(watchlist);
    downloadBlob("player-watchlist.csv", csv, "text/csv;charset=utf-8");
  }

  function toggleCompareRow(row) {
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
  }

  function clearCompareRows() {
    setCompareRowsByKey({});
  }

  function removeCompareRow(key) {
    setCompareRowsByKey(current => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function handleSort(col) {
    if (sortCol === col) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir(col === "Player" || col === "Team" || col === "Pos" || col === "Type" || col === "Year" || col === "Years" ? "asc" : "desc");
    }
  }

  async function exportCurrentProjections(format) {
    const endpointTab = tab === "all" ? "all" : tab;
    const params = new URLSearchParams();
    if (search) params.set("player", search);
    if (teamFilter) params.set("team", teamFilter);
    if (watchlistOnly && watchlistKeysFilter) params.set("player_keys", watchlistKeysFilter);
    if (careerTotalsView) {
      params.set("career_totals", "true");
    } else {
      params.set("year", resolvedYearFilter);
    }
    if (posFilters.length > 0) params.set("pos", posFilters.join(","));
    if (selectedDynastyYears.length > 0) params.set("dynasty_years", selectedDynastyYears.join(","));
    params.set("include_dynasty", "true");
    params.set("sort_col", sortCol);
    params.set("sort_dir", sortDir);
    if (cols.length > 0) params.set("columns", cols.join(","));
    params.set("format", format);
    const href = `${API}/api/projections/export/${endpointTab}?${params.toString()}`;

    try {
      setExportingFormat(format);
      setExportError("");
      const response = await fetch(href, {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });
      if (!response.ok) {
        const parsed = await readResponsePayload(response);
        throw new Error(formatApiError(response.status, parsed.payload, parsed.rawText));
      }
      const blob = await response.blob();
      const fallback = `projections-${endpointTab}.${format}`;
      const filename = parseDownloadFilename(response.headers.get("content-disposition"), fallback);
      triggerBlobDownload(filename, blob);
    } catch (err) {
      setExportError(err?.message || "Failed to export projections");
    } finally {
      setExportingFormat("");
    }
  }

  const seasonCol = careerTotalsView ? "Years" : "Year";
  const dynastyYearCols = selectedDynastyYears.map(year => `Value_${year}`);
  const tableColumnCatalog = useMemo(
    () => projectionTableColumnCatalog(tab, seasonCol, dynastyYearCols),
    [tab, seasonCol, dynastyYearCols]
  );
  const activeProjectionTableHiddenCols = projectionTableHiddenColsByTab[tab] || {};
  const requiredProjectionTableCols = useMemo(() => new Set(["Player"]), []);
  const isProjectionTableColHidden = useCallback((col, hiddenOverrides = activeProjectionTableHiddenCols) => {
    if (Object.prototype.hasOwnProperty.call(hiddenOverrides, col)) {
      return Boolean(hiddenOverrides[col]);
    }
    return projectionTableColumnHiddenByDefault(tab, col);
  }, [tab, activeProjectionTableHiddenCols]);
  const resolvedProjectionTableHiddenCols = useMemo(() => {
    const hidden = {};
    tableColumnCatalog.forEach(col => {
      if (isProjectionTableColHidden(col)) hidden[col] = true;
    });
    return hidden;
  }, [tableColumnCatalog, isProjectionTableColHidden]);
  const cols = useMemo(
    () => tableColumnCatalog.filter(col => !isProjectionTableColHidden(col)),
    [tableColumnCatalog, isProjectionTableColHidden]
  );

  const cardColumnCatalog = useMemo(
    () => projectionCardColumnCatalog(tab, seasonCol, dynastyYearCols),
    [tab, seasonCol, dynastyYearCols]
  );
  const projectionCardCoreUnionCols = useMemo(() => (
    tab === "bat"
      ? [...PROJECTION_HITTER_CORE_STATS]
      : tab === "pitch"
        ? [...PROJECTION_PITCHER_CORE_STATS]
        : [...PROJECTION_HITTER_CORE_STATS, ...PROJECTION_PITCHER_CORE_STATS]
  ), [tab]);
  const projectionCardCoreUnionSet = useMemo(
    () => new Set(projectionCardCoreUnionCols),
    [projectionCardCoreUnionCols]
  );
  const activeProjectionCardHiddenCols = projectionCardHiddenColsByTab[tab] || {};
  const isProjectionCardOptionalColHidden = useCallback((col, hiddenOverrides = activeProjectionCardHiddenCols) => {
    if (projectionCardCoreUnionSet.has(col)) return false;
    if (Object.prototype.hasOwnProperty.call(hiddenOverrides, col)) {
      return Boolean(hiddenOverrides[col]);
    }
    return projectionCardOptionalColumnHiddenByDefault(col);
  }, [activeProjectionCardHiddenCols, projectionCardCoreUnionSet]);
  const cardOptionalCols = useMemo(
    () => cardColumnCatalog.filter(col => !projectionCardCoreUnionSet.has(col)),
    [cardColumnCatalog, projectionCardCoreUnionSet]
  );
  const visibleCardOptionalCols = useMemo(
    () => cardOptionalCols.filter(col => !isProjectionCardOptionalColHidden(col)),
    [cardOptionalCols, isProjectionCardOptionalColHidden]
  );
  const requiredProjectionCardCols = useMemo(
    () => new Set(projectionCardCoreUnionCols),
    [projectionCardCoreUnionCols]
  );
  const resolvedProjectionCardHiddenCols = useMemo(() => {
    const hidden = {};
    cardColumnCatalog.forEach(col => {
      if (isProjectionCardOptionalColHidden(col)) hidden[col] = true;
    });
    return hidden;
  }, [cardColumnCatalog, isProjectionCardOptionalColHidden]);
  const projectionCardCoreColumnsForRow = useCallback(row => {
    if (tab === "bat") return PROJECTION_HITTER_CORE_STATS;
    if (tab === "pitch") return PROJECTION_PITCHER_CORE_STATS;
    const side = String(row?.Type || "").trim().toUpperCase();
    if (side === "P") return PROJECTION_PITCHER_CORE_STATS;
    if (side === "H") return PROJECTION_HITTER_CORE_STATS;
    return [...PROJECTION_HITTER_CORE_STATS, ...PROJECTION_PITCHER_CORE_STATS];
  }, [tab]);
  const projectionCardColumnsForRow = useCallback(row => (
    uniqueColumnOrder([
      ...projectionCardCoreColumnsForRow(row),
      ...visibleCardOptionalCols,
    ])
  ), [projectionCardCoreColumnsForRow, visibleCardOptionalCols]);

  function setProjectionTableColumnHidden(col, hidden) {
    setProjectionTableHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      const defaultHidden = projectionTableColumnHiddenByDefault(tab, col);
      if (hidden === defaultHidden) {
        delete nextTab[col];
      } else {
        nextTab[col] = hidden;
      }
      next[tab] = nextTab;
      return next;
    });
  }

  function toggleProjectionTableColumn(col) {
    if (requiredProjectionTableCols.has(col)) return;
    const currentlyHidden = isProjectionTableColHidden(col);
    setProjectionTableColumnHidden(col, !currentlyHidden);
  }

  function showAllProjectionTableColumns() {
    setProjectionTableHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      tableColumnCatalog.forEach(col => {
        if (requiredProjectionTableCols.has(col)) return;
        nextTab[col] = false;
      });
      next[tab] = nextTab;
      return next;
    });
  }

  function setProjectionCardOptionalColumnHidden(col, hidden) {
    if (projectionCardCoreUnionSet.has(col)) return;
    setProjectionCardHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      const defaultHidden = projectionCardOptionalColumnHiddenByDefault(col);
      if (hidden === defaultHidden) {
        delete nextTab[col];
      } else {
        nextTab[col] = hidden;
      }
      next[tab] = nextTab;
      return next;
    });
  }

  function toggleProjectionCardColumn(col) {
    if (requiredProjectionCardCols.has(col)) return;
    const currentlyHidden = isProjectionCardOptionalColHidden(col);
    setProjectionCardOptionalColumnHidden(col, !currentlyHidden);
  }

  function showAllProjectionCardColumns() {
    setProjectionCardHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      cardOptionalCols.forEach(col => {
        nextTab[col] = false;
      });
      next[tab] = nextTab;
      return next;
    });
  }

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
      setCanScrollLeft(false);
      setCanScrollRight(false);
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
        <span className="collection-toolbar-label">Compare: {compareRows.length}/{MAX_COMPARE_PLAYERS}</span>
        <button type="button" className="inline-btn" onClick={clearCompareRows} disabled={compareRows.length === 0}>
          Clear Compare
        </button>
      </div>
      {compareRows.length > 0 && (
        <div className="comparison-panel" role="region" aria-label="Player comparison">
          <div className="comparison-header">
            <strong>Player Comparison</strong>
            <span>{compareRows.length}/{MAX_COMPARE_PLAYERS} selected</span>
          </div>
          <div className="comparison-grid">
            {compareRows.map(row => {
              const compareKey = stablePlayerKeyFromRow(row);
              return (
                <article className="comparison-card" key={compareKey}>
                  <div className="comparison-card-head">
                    <h4>{row.Player || "Player"}</h4>
                    <button type="button" className="inline-btn" onClick={() => removeCompareRow(compareKey)}>Remove</button>
                  </div>
                  <p>{row.Team || "—"} · {row.Pos || "—"}</p>
                  <dl>
                    {comparisonColumns.map(col => (
                      <React.Fragment key={`${compareKey}-${col}`}>
                        <dt>{colLabels[col] || col}</dt>
                        <dd>{formatCellValue(col, row[col])}</dd>
                      </React.Fragment>
                    ))}
                  </dl>
                </article>
              );
            })}
          </div>
        </div>
      )}
      {watchlistCount > 0 && (
        <div className="watchlist-panel" role="region" aria-label="Saved watchlist">
          <div className="watchlist-panel-head">
            <strong>Saved Watchlist</strong>
            <span>{watchlistCount} players</span>
          </div>
          <div className="watchlist-chip-grid">
            {Object.values(watchlist)
              .sort((a, b) => String(a.player || "").localeCompare(String(b.player || "")))
              .slice(0, 40)
              .map(entry => (
                <div key={entry.key} className="watchlist-chip">
                  <span>{entry.player}</span>
                  <small>{entry.team || "—"} · {entry.pos || "—"}</small>
                  <button type="button" onClick={() => removeWatchlistEntry(entry.key)} aria-label={`Remove ${entry.player}`}>
                    ×
                  </button>
                </div>
              ))}
          </div>
          {watchlistCount > 40 && <p className="calc-note">Showing first 40 watchlist entries.</p>}
        </div>
      )}
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
                        disabled={!isCompared && compareRows.length >= MAX_COMPARE_PLAYERS}
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
                            disabled={!isCompared && compareRows.length >= MAX_COMPARE_PLAYERS}
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
