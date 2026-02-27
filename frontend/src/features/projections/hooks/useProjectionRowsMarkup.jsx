import { useCallback, useMemo } from "react";
import {
  projectionRowKey,
  stablePlayerKeyFromRow,
} from "../../../app_state_storage";
import {
  INT_COLS,
  THREE_DECIMAL_COLS,
  TWO_DECIMAL_COLS,
  WHOLE_NUMBER_COLS,
  fmt,
  fmtInt,
  formatCellValue,
} from "../../../formatting_utils";

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
}) {
  const threeDecimalCols = THREE_DECIMAL_COLS;
  const twoDecimalCols = TWO_DECIMAL_COLS;
  const wholeNumberCols = WHOLE_NUMBER_COLS;
  const intCols = INT_COLS;

  const formatProjectionCell = useCallback((col, row) => {
    const val = row[col];
    if (col === "Player") return <td key={col} className="player-name">{val}</td>;
    if (col === "Pos") return <td key={col} className="pos">{val}</td>;
    if (col === "Team") return <td key={col} className="team">{val}</td>;
    if (col === "DynastyValue" || col.startsWith("Value_")) {
      if ((val == null || val === "") && col === "DynastyValue" && row.DynastyMatchStatus === "no_unique_match") {
        return <td key={col} className="num" style={{ color: "var(--text-muted)" }}>No unique match</td>;
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
