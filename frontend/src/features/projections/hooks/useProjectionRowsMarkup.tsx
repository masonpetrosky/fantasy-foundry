import React, { useCallback, useMemo } from "react";
import {
  projectionRowKey,
  stablePlayerKeyFromRow,
} from "../../../app_state_storage";
import type { ProjectionRow } from "../../../app_state_storage";
import {
  INT_COLS,
  THREE_DECIMAL_COLS,
  TWO_DECIMAL_COLS,
  WHOLE_NUMBER_COLS,
  fmt,
  fmtInt,
  formatCellValue,
} from "../../../formatting_utils";
import { isRotoStatDynastyCol } from "../../../dynasty_calculator_config";

export interface UseProjectionRowsMarkupInput {
  showCards: boolean;
  displayedPage: ProjectionRow[];
  offset: number;
  cols: string[];
  colLabels: Record<string, string>;
  projectionCardColumnsForRow: (row: ProjectionRow) => string[];
  isRowWatched: (row: ProjectionRow) => boolean;
  compareRowsByKey: Record<string, ProjectionRow>;
  compareRowsCount: number;
  maxComparePlayers: number;
  toggleRowWatch: (row: ProjectionRow) => void;
  toggleCompareRow: (row: ProjectionRow) => void;
  quickAddRow: (row: ProjectionRow) => void;
  onViewProfile: ((row: ProjectionRow) => void) | null | undefined;
}

export interface UseProjectionRowsMarkupResult {
  cardRowsMarkup: React.ReactElement[];
  tableRowsMarkup: React.ReactElement[];
}

export function useProjectionRowsMarkup({
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
  onViewProfile,
}: UseProjectionRowsMarkupInput): UseProjectionRowsMarkupResult {
  const threeDecimalCols = THREE_DECIMAL_COLS;
  const twoDecimalCols = TWO_DECIMAL_COLS;
  const wholeNumberCols = WHOLE_NUMBER_COLS;
  const intCols = INT_COLS;

  const formatProjectionCell = useCallback((col: string, row: ProjectionRow): React.ReactElement => {
    const val = row[col];
    if (col === "Player") return <td key={col} className="player-name">{val as React.ReactNode}</td>;
    if (col === "Pos") return <td key={col} className="pos">{val as React.ReactNode}</td>;
    if (col === "Team") return <td key={col} className="team">{val as React.ReactNode}</td>;
    if (col === "AuctionDollars") {
      if (val == null || val === "") return <td key={col} className="num">{"\u2014"}</td>;
      return <td key={col} className="num">${fmtInt(val, true)}</td>;
    }
    if (col === "ProjectionDelta") {
      if (val == null || val === "" || val === 0) return <td key={col} className="num">{"\u2014"}</td>;
      const n = Number(val);
      const arrow = n > 0 ? "\u2191" : "\u2193";
      const cls = n > 0 ? "value-positive" : "value-negative";
      return <td key={col} className={`num ${cls}`}>{arrow} {Math.abs(n).toFixed(2)}</td>;
    }
    if (col === "DynastyValue" || col.startsWith("Value_")) {
      if ((val == null || val === "") && col === "DynastyValue" && row.DynastyMatchStatus === "no_unique_match") {
        return <td key={col} className="num" style={{ color: "var(--text-muted)" }}>No unique match</td>;
      }
      const n = Number(val);
      const cls = n > 0 ? "value-positive" : n < 0 ? "value-negative" : "";
      const prefix = n > 0 ? "+" : n < 0 ? "\u2212" : "";
      const display = val == null || val === "" || isNaN(n) ? "\u2014" : `${prefix}${Math.abs(n).toFixed(2)}`;
      return <td key={col} className={`num ${cls}`}>{display}</td>;
    }
    if (isRotoStatDynastyCol(col)) {
      const n = Number(val);
      const cls = n > 0 ? "value-positive" : n < 0 ? "value-negative" : "";
      const prefix = n > 0 ? "+" : n < 0 ? "\u2212" : "";
      const display = val == null || val === "" || isNaN(n) ? "\u2014" : `${prefix}${Math.abs(n).toFixed(2)}`;
      return <td key={col} className={`num ${cls}`}>{display}</td>;
    }
    if (twoDecimalCols.has(col)) return <td key={col} className="num">{fmt(val, 2)}</td>;
    if (threeDecimalCols.has(col)) return <td key={col} className="num">{fmt(val, 3)}</td>;
    if (wholeNumberCols.has(col)) return <td key={col} className="num">{fmtInt(val, true)}</td>;
    if (intCols.has(col)) return <td key={col} className="num">{fmtInt(val, col !== "Year")}</td>;
    if (typeof val === "number") return <td key={col} className="num">{fmt(val)}</td>;
    return <td key={col}>{(val as React.ReactNode) ?? "\u2014"}</td>;
  }, [intCols, threeDecimalCols, twoDecimalCols, wholeNumberCols]);

  const cardRowsMarkup = useMemo(() => {
    if (!showCards || displayedPage.length === 0) return [];

    return displayedPage.map((row, idx) => {
      const rowWatch = isRowWatched(row);
      const compareKey = stablePlayerKeyFromRow(row);
      const isCompared = Boolean(compareRowsByKey[compareKey]);
      const rowWithRank: ProjectionRow = { ...row, Rank: offset + idx + 1 };
      const cardCols = projectionCardColumnsForRow(rowWithRank);
      const rowKey = projectionRowKey(row, offset + idx);

      return (
        <article className="projection-card" key={rowKey}>
          <div className="projection-card-head">
            <h4>{(row.Player as React.ReactNode) || "Player"}</h4>
            <div className="projection-card-actions">
              <button
                type="button"
                className={`inline-btn ${rowWatch ? "open" : ""}`.trim()}
                onClick={() => toggleRowWatch(row)}
                aria-pressed={rowWatch}
              >
                {rowWatch ? "Tracked" : "Track"}
              </button>
              <button
                type="button"
                className={`inline-btn ${isCompared ? "open" : ""}`.trim()}
                onClick={() => toggleCompareRow(row)}
                disabled={!isCompared && compareRowsCount >= maxComparePlayers}
                aria-pressed={isCompared}
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
              {onViewProfile && (
                <button
                  type="button"
                  className="inline-btn"
                  onClick={() => onViewProfile(row)}
                  aria-label={`View profile for ${row.Player || "player"}`}
                >
                  Profile
                </button>
              )}
            </div>
          </div>
          <p className="projection-card-meta">{(row.Team as React.ReactNode) || "\u2014"} · {(row.Pos as React.ReactNode) || "\u2014"}</p>
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
    onViewProfile,
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
          <td className="num index-col" style={{ color: "var(--text-muted)" }}>{offset + i + 1}</td>
          {cols.map(col => formatProjectionCell(col, row))}
          <td className="row-actions-cell">
            <button
              type="button"
              className={`inline-btn ${rowWatch ? "open" : ""}`.trim()}
              onClick={() => toggleRowWatch(row)}
              aria-pressed={rowWatch}
            >
              {rowWatch ? "Tracked" : "Track"}
            </button>
            <button
              type="button"
              className={`inline-btn ${isCompared ? "open" : ""}`.trim()}
              onClick={() => toggleCompareRow(row)}
              disabled={!isCompared && compareRowsCount >= maxComparePlayers}
              aria-pressed={isCompared}
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
            {onViewProfile && (
              <button
                type="button"
                className="inline-btn"
                onClick={() => onViewProfile(row)}
                aria-label={`View profile for ${row.Player || "player"}`}
              >
                Profile
              </button>
            )}
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
    onViewProfile,
  ]);

  return {
    cardRowsMarkup,
    tableRowsMarkup,
  };
}
