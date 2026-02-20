import React from "react";
import { ColumnChooserControl, ExplainabilityCard } from "./ui_components.jsx";
import {
  MAX_COMPARE_PLAYERS,
  calculationRowExplainKey,
  stablePlayerKeyFromRow,
} from "./app_state_storage.js";
import {
  POINTS_RESULT_NUMERIC_COLS,
  POINTS_RESULT_SLOT_COLS,
  ROTO_COUNTING_STAT_COLS,
  ROTO_RATE_STAT_COLS,
  ROTO_THREE_DECIMAL_RATE_COLS,
} from "./dynasty_calculator_config.js";
import { fmt } from "./formatting_utils.js";

const POSITION_FILTER_OPTIONS = ["C", "1B", "2B", "3B", "SS", "OF", "SP", "RP"];

export function DynastyCalculatorResults({ results, state, refs, actions }) {
  if (!results) {
    return (
      <div className="calc-empty-state">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v6l4 2" />
        </svg>
        <p>Configure your league settings and click <strong>Generate Rankings</strong></p>
      </div>
    );
  }

  const {
    activeExplanation,
    compareYearCols,
    columnLabels,
    displayCols,
    hasRankFilters,
    hiddenRankCols,
    pinRankKeyColumns,
    posFilter,
    rankCompareRows,
    rankCompareRowsByKey,
    rankedFiltered,
    rankSearchIsDebouncing,
    rankWatchlistOnly,
    searchInput,
    selectedExplainKey,
    selectedExplainYear,
    sortCol,
    sortDir,
    sortedAll,
    virtualBottomPad,
    virtualRows,
    virtualStartIndex,
    virtualTopPad,
    visibleRankCols,
    watchlist,
    watchlistCount,
    requiredRankCols,
  } = state;
  const {
    clearRankCompareRows,
    clearRankFilters,
    clearWatchlist,
    exportRankings,
    exportWatchlistCsv,
    handleSort,
    removeRankCompareRow,
    setPinRankKeyColumns,
    setPosFilter,
    setRankWatchlistOnly,
    setSearchInput,
    setSelectedExplainKey,
    setSelectedExplainYear,
    showAllRankColumns,
    toggleRankColumn,
    toggleRankCompareRow,
    toggleRowWatch,
  } = actions;
  const { handleRankScroll, rankTableScrollRef } = refs;

  return (
    <>
      <div className="filter-bar calc-results-toolbar">
        <label className="sr-only" htmlFor="calculator-rank-search">Search ranked players</label>
        <input
          id="calculator-rank-search"
          type="text"
          placeholder="Search ranked players…"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
        />
        <label className="sr-only" htmlFor="calculator-rank-pos-filter">Position filter</label>
        <select id="calculator-rank-pos-filter" value={posFilter} onChange={e => setPosFilter(e.target.value)}>
          <option value="">All Positions</option>
          {POSITION_FILTER_OPTIONS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>
        <span className={`result-count ${rankSearchIsDebouncing ? "loading" : ""}`.trim()} aria-live="polite" aria-atomic="true">
          {rankedFiltered.length.toLocaleString()} / {sortedAll.length.toLocaleString()} players
          {rankSearchIsDebouncing ? " · filtering..." : ""}
        </span>
        <button type="button" className="inline-btn" onClick={clearRankFilters} disabled={!hasRankFilters}>
          Reset Filters
        </button>
        <button
          type="button"
          className={`inline-btn ${rankWatchlistOnly ? "open" : ""}`.trim()}
          onClick={() => setRankWatchlistOnly(value => !value)}
          disabled={watchlistCount === 0}
        >
          {rankWatchlistOnly ? "All Ranked Players" : "Watchlist Only"}
        </button>
        {ColumnChooserControl && (
          <ColumnChooserControl
            columns={displayCols}
            hiddenCols={hiddenRankCols}
            requiredCols={requiredRankCols}
            onToggleColumn={toggleRankColumn}
            onShowAllColumns={showAllRankColumns}
            columnLabels={columnLabels}
          />
        )}
        <button type="button" className="inline-btn" onClick={() => setPinRankKeyColumns(v => !v)}>
          {pinRankKeyColumns ? "Unpin Key Columns" : "Pin Key Columns"}
        </button>
        <button type="button" className="inline-btn" onClick={exportWatchlistCsv} disabled={watchlistCount === 0}>
          Export Watchlist CSV
        </button>
        <button type="button" className="inline-btn" onClick={clearWatchlist} disabled={watchlistCount === 0}>
          Clear Watchlist
        </button>
        <button type="button" className="inline-btn" onClick={clearRankCompareRows} disabled={rankCompareRows.length === 0}>
          Clear Compare
        </button>
        <button type="button" className="inline-btn" onClick={() => exportRankings("csv")}>Export CSV</button>
        <button type="button" className="inline-btn" onClick={() => exportRankings("xlsx")}>Export XLSX</button>
      </div>
      {rankCompareRows.length > 0 && (
        <div className="comparison-panel" role="region" aria-label="Ranked player comparison">
          <div className="comparison-header">
            <strong>Ranked Player Comparison</strong>
            <span>{rankCompareRows.length}/{MAX_COMPARE_PLAYERS} selected</span>
          </div>
          <div className="comparison-grid">
            {rankCompareRows.map(row => {
              const key = stablePlayerKeyFromRow(row);
              return (
                <article className="comparison-card" key={`rank-compare-${key}`}>
                  <div className="comparison-card-head">
                    <h4>{row.Player || "Player"}</h4>
                    <button type="button" className="inline-btn" onClick={() => removeRankCompareRow(key)}>Remove</button>
                  </div>
                  <p>{row.Team || "—"} · {row.Pos || "—"} · Age {fmt(row.Age, 0)}</p>
                  <dl>
                    <dt>Dynasty Value</dt>
                    <dd>{fmt(row.DynastyValue, 2)}</dd>
                    {compareYearCols.map(col => (
                      <React.Fragment key={`${key}-${col}`}>
                        <dt>{col.replace("Value_", "")}</dt>
                        <dd>{fmt(row[col], 2)}</dd>
                      </React.Fragment>
                    ))}
                  </dl>
                </article>
              );
            })}
          </div>
        </div>
      )}
      <p className="calc-results-hint">Click or press Enter on a row to inspect its value breakdown.</p>
      <div className="table-wrapper">
        <div
          className="table-scroll"
          ref={rankTableScrollRef}
          onScroll={handleRankScroll}
        >
          <table className="rankings-table">
            <thead>
              <tr>
                <th scope="col" style={{ width: 40 }} className={pinRankKeyColumns ? "rank-pin-rank" : ""}>#</th>
                {visibleRankCols.map(c => (
                  <th
                    key={c}
                    scope="col"
                    className={[
                      sortCol === c ? "sorted" : "",
                      c === "Player" ? "player-col" : "",
                      pinRankKeyColumns && c === "Player" ? "rank-pin-player" : "",
                      pinRankKeyColumns && c === "DynastyValue" ? "rank-pin-value" : "",
                    ].join(" ").trim()}
                    onClick={() => handleSort(c)}
                    onKeyDown={event => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        handleSort(c);
                      }
                    }}
                    tabIndex={0}
                    aria-sort={sortCol === c ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                  >
                    {columnLabels[c] || c.replace("Value_", "")}
                    {sortCol === c && <span className="sort-arrow">{sortDir === "asc" ? "▲" : "▼"}</span>}
                  </th>
                ))}
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {virtualTopPad > 0 && (
                <tr aria-hidden="true">
                  <td colSpan={visibleRankCols.length + 2} style={{ height: virtualTopPad, padding: 0, border: "none" }} />
                </tr>
              )}
              {virtualRows.map(({ row, rank }, i) => {
                const explainKey = calculationRowExplainKey(row);
                const isSelected = selectedExplainKey === explainKey;
                const watchKey = stablePlayerKeyFromRow(row);
                const isWatched = Boolean(watchlist[watchKey]);
                const isCompared = Boolean(rankCompareRowsByKey[watchKey]);
                return (
                  <tr
                    key={virtualStartIndex + i}
                    className={`clickable-row ${isSelected ? "rank-row-selected" : ""}`.trim()}
                    onClick={() => setSelectedExplainKey(explainKey)}
                    onKeyDown={event => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedExplainKey(explainKey);
                      }
                    }}
                    aria-selected={isSelected}
                    tabIndex={0}
                  >
                    <td className={`num ${pinRankKeyColumns ? "rank-pin-rank" : ""}`.trim()} style={{ color: "var(--text-muted)" }}>{rank}</td>
                    {visibleRankCols.map(c => {
                      const val = row[c];
                      const pinClass = pinRankKeyColumns && c === "Player"
                        ? "rank-pin-player"
                        : pinRankKeyColumns && c === "DynastyValue"
                          ? "rank-pin-value"
                          : "";
                      if (c === "Player") return <td key={c} className={`player-name ${pinClass}`.trim()}>{val}</td>;
                      if (c === "Pos") return <td key={c} className={`pos ${pinClass}`.trim()}>{val}</td>;
                      if (c === "Team") return <td key={c} className={`team ${pinClass}`.trim()}>{val}</td>;
                      if (c === "DynastyValue" || c.startsWith("Value_")) {
                        const n = Number(val);
                        const cls = n > 0 ? "value-positive" : n < 0 ? "value-negative" : "";
                        return <td key={c} className={`num ${cls} ${pinClass}`.trim()}>{fmt(val, 2)}</td>;
                      }
                      if (POINTS_RESULT_NUMERIC_COLS.has(c)) {
                        return <td key={c} className={`num ${pinClass}`.trim()}>{fmt(val, 2)}</td>;
                      }
                      if (POINTS_RESULT_SLOT_COLS.has(c)) {
                        return <td key={c} className={pinClass}>{val || "—"}</td>;
                      }
                      if (ROTO_COUNTING_STAT_COLS.has(c)) {
                        return <td key={c} className={`num ${pinClass}`.trim()}>{fmt(val, 0)}</td>;
                      }
                      if (ROTO_RATE_STAT_COLS.has(c)) {
                        const decimals = ROTO_THREE_DECIMAL_RATE_COLS.has(c) ? 3 : 2;
                        return <td key={c} className={`num ${pinClass}`.trim()}>{fmt(val, decimals)}</td>;
                      }
                      if (typeof val === "number") return <td key={c} className={`num ${pinClass}`.trim()}>{fmt(val, Number.isInteger(val) ? 0 : 1)}</td>;
                      return <td key={c} className={pinClass}>{val ?? "—"}</td>;
                    })}
                    <td className="row-actions-cell">
                      <button
                        type="button"
                        className={`inline-btn ${isWatched ? "open" : ""}`.trim()}
                        onClick={event => {
                          event.stopPropagation();
                          toggleRowWatch(row);
                        }}
                      >
                        {isWatched ? "Tracked" : "Track"}
                      </button>
                      <button
                        type="button"
                        className={`inline-btn ${isCompared ? "open" : ""}`.trim()}
                        disabled={!isCompared && rankCompareRows.length >= MAX_COMPARE_PLAYERS}
                        onClick={event => {
                          event.stopPropagation();
                          toggleRankCompareRow(row);
                        }}
                      >
                        {isCompared ? "Compared" : "Compare"}
                      </button>
                    </td>
                  </tr>
                );
              })}
              {virtualBottomPad > 0 && (
                <tr aria-hidden="true">
                  <td colSpan={visibleRankCols.length + 2} style={{ height: virtualBottomPad, padding: 0, border: "none" }} />
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      {ExplainabilityCard && (
        <ExplainabilityCard
          explanation={activeExplanation}
          selectedYear={selectedExplainYear}
          onSelectedYearChange={setSelectedExplainYear}
          fmt={fmt}
        />
      )}
    </>
  );
}
