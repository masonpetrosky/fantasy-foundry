import React, { useCallback, useId, useMemo, useRef, useState } from "react";
import { ColumnChooserControl } from "../../../ui_components.jsx";
import {
  MenuButton,
  VisuallyHidden,
  useMenuInteractions,
} from "../../../accessibility_components.jsx";
import { parsePosTokens } from "../../../formatting_utils.js";
import { DEFAULT_FILTER_SUMMARY_FALLBACK } from "../view_state.js";
import { CAREER_TOTALS_FILTER_VALUE } from "../../../hooks/useProjectionsData.js";

export const ProjectionFilterBar = React.memo(function ProjectionFilterBar({
  tab,
  meta,
  search,
  resolvedYearFilter,
  teamFilter,
  posFilters,
  watchlistOnly,
  watchlistCount,
  totalRows,
  loading,
  searchIsDebouncing,
  setSearch,
  setTeamFilter,
  setYearFilter,
  setPosFilters,
  setWatchlistOnly,
  activeProjectionPresetKey,
  projectionFilterPresets,
  applyProjectionFilterPreset,
  saveCustomProjectionPreset,
  clearAllFilters,
  hasActiveFilters,
  activeFilterChips,
  tableColumnCatalog,
  resolvedProjectionTableHiddenCols,
  requiredProjectionTableCols,
  toggleProjectionTableColumn,
  showAllProjectionTableColumns,
  colLabels,
  exportingFormat,
  exportCurrentProjections,
  tierLimits,
}) {
  const [showPosMenu, setShowPosMenu] = useState(false);
  const [filterExpanded, setFilterExpanded] = useState(false);
  const posMenuRef = useRef(null);
  const posMenuTriggerRef = useRef(null);
  const posMenuId = useId();
  const posMenuTriggerId = `${posMenuId}-trigger`;

  useMenuInteractions({
    open: showPosMenu,
    setOpen: setShowPosMenu,
    menuRef: posMenuRef,
    triggerRef: posMenuTriggerRef,
  });

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

  const posFilterLabel = posFilters.length === 0
    ? "All Positions"
    : posFilters.length <= 2
      ? posFilters.join(", ")
      : `${posFilters.length} Positions`;

  function togglePosFilter(pos) {
    setPosFilters(curr => (
      curr.includes(pos) ? curr.filter(p => p !== pos) : [...curr, pos]
    ));
  }

  const filterToggleId = `${posMenuId}-filter-toggle`;
  const [filterDiscoverable, setFilterDiscoverable] = useState(() => {
    try { return !localStorage.getItem("ff:filter-drawer-discovered"); } catch { return false; }
  });
  const handleFilterToggle = useCallback(() => {
    setFilterExpanded(v => {
      if (!v && filterDiscoverable) {
        try { localStorage.setItem("ff:filter-drawer-discovered", "1"); } catch { /* noop */ }
        setFilterDiscoverable(false);
      }
      return !v;
    });
  }, [filterDiscoverable]);

  return (
    <>
      <div className="filter-bar-mobile-row">
        <button
          id={filterToggleId}
          type="button"
          className={`inline-btn filter-mobile-toggle${filterExpanded ? " open" : ""}${filterDiscoverable && !filterExpanded ? " discoverable" : ""}`}
          aria-expanded={filterExpanded}
          aria-controls="filter-controls-panel"
          onClick={handleFilterToggle}
        >
          {hasActiveFilters ? `Filters (${activeFilterChips.length} active)` : "Filters"}
          <span aria-hidden="true">{filterExpanded ? " ▲" : " ▼"}</span>
        </button>
        <div className="active-filter-chip-row active-filter-chip-row-mobile" role="status" aria-live="polite">
          {hasActiveFilters ? activeFilterChips.map(chip => (
            <span key={chip} className="filter-chip">{chip}</span>
          )) : (
            <span className="filter-chip filter-chip-empty">No active filters</span>
          )}
        </div>
      </div>

      <div
        id="filter-controls-panel"
        className={`filter-controls-panel ${filterExpanded ? "filter-controls-open" : ""}`.trim()}
      >
      <div className="filter-preset-row" role="group" aria-label="Projection filter presets">
        <span className="filter-preset-label">Presets</span>
        <button
          type="button"
          className={`inline-btn ${activeProjectionPresetKey === "all" ? "open" : ""}`.trim()}
          onClick={() => applyProjectionFilterPreset("all")}
        >
          All
        </button>
        <button
          type="button"
          className={`inline-btn ${activeProjectionPresetKey === "watchlist" ? "open" : ""}`.trim()}
          onClick={() => applyProjectionFilterPreset("watchlist")}
          disabled={watchlistCount === 0}
        >
          My Watchlist
        </button>
        <button
          type="button"
          className={`inline-btn ${activeProjectionPresetKey === "hitters" ? "open" : ""}`.trim()}
          onClick={() => applyProjectionFilterPreset("hitters")}
        >
          Hitters
        </button>
        <button
          type="button"
          className={`inline-btn ${activeProjectionPresetKey === "pitchers" ? "open" : ""}`.trim()}
          onClick={() => applyProjectionFilterPreset("pitchers")}
        >
          Pitchers
        </button>
        <button
          type="button"
          className={`inline-btn ${activeProjectionPresetKey === "custom" ? "open" : ""}`.trim()}
          onClick={() => applyProjectionFilterPreset("custom")}
          disabled={!projectionFilterPresets?.custom}
        >
          Custom
        </button>
        <button
          type="button"
          className="inline-btn"
          onClick={saveCustomProjectionPreset}
        >
          Save Current As Custom
        </button>
      </div>

      <div className="filter-bar">
        <VisuallyHidden as="label" htmlFor="projections-search">Search player name</VisuallyHidden>
        <input
          id="projections-search"
          type="text"
          placeholder="Search player name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <VisuallyHidden as="label" htmlFor="projections-year-filter">Projection year view</VisuallyHidden>
        <select id="projections-year-filter" value={resolvedYearFilter} onChange={e => setYearFilter(e.target.value)}>
          <option value={CAREER_TOTALS_FILTER_VALUE}>Rest of Career Totals</option>
          {meta.years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <VisuallyHidden as="label" htmlFor="projections-team-filter">Team filter</VisuallyHidden>
        <select id="projections-team-filter" value={teamFilter} onChange={e => setTeamFilter(e.target.value)}>
          <option value="">All Teams</option>
          {meta.teams.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <div className="multi-select" ref={posMenuRef}>
          <MenuButton
            controlsId={posMenuId}
            open={showPosMenu}
            onToggle={() => setShowPosMenu(open => !open)}
            buttonRef={posMenuTriggerRef}
            id={posMenuTriggerId}
            className={`multi-select-trigger ${showPosMenu ? "open" : ""}`}
            aria-label="Filter positions"
            label={(
              <span className="multi-select-label">
                <span>{posFilterLabel}</span>
                <span className="multi-select-chevron" aria-hidden="true">{showPosMenu ? "▲" : "▼"}</span>
              </span>
            )}
          >
          </MenuButton>
          {showPosMenu && (
            <div
              id={posMenuId}
              className="multi-select-menu"
              role="group"
              aria-labelledby={posMenuTriggerId}
            >
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
          disabled={Boolean(exportingFormat) || (tierLimits && !tierLimits.allowExport)}
        >
          {tierLimits && !tierLimits.allowExport ? "Export CSV (Pro)" : exportingFormat === "csv" ? "Exporting CSV..." : "Export CSV"}
        </button>
        <button
          type="button"
          className="inline-btn"
          onClick={() => exportCurrentProjections("xlsx")}
          disabled={Boolean(exportingFormat) || (tierLimits && !tierLimits.allowExport)}
        >
          {tierLimits && !tierLimits.allowExport ? "Export XLSX (Pro)" : exportingFormat === "xlsx" ? "Exporting XLSX..." : "Export XLSX"}
        </button>
      </div>
      </div>{/* end filter-controls-panel */}

      <div className="active-filter-row" role="status" aria-live="polite">
        <span className="active-filter-label">Active filters</span>
        <div className="active-filter-chip-row">
          {hasActiveFilters ? activeFilterChips.map(chip => (
            <span key={chip} className="filter-chip">{chip}</span>
          )) : (
            <span className="filter-chip filter-chip-empty">{DEFAULT_FILTER_SUMMARY_FALLBACK}</span>
          )}
        </div>
        <button
          type="button"
          className="inline-btn"
          onClick={clearAllFilters}
          disabled={!hasActiveFilters}
        >
          Clear All Filters
        </button>
      </div>
    </>
  );
});
