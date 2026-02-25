import React from "react";
import { stablePlayerKeyFromRow } from "../../../app_state_storage.js";

export const ProjectionComparisonPanel = React.memo(function ProjectionComparisonPanel({
  compareRows,
  maxComparePlayers,
  comparisonColumns,
  colLabels,
  formatCellValue,
  removeCompareRow,
  copyCompareShareLink,
}) {
  if (compareRows.length === 0) return null;

  return (
    <div className="comparison-panel" role="region" aria-label="Player comparison">
      <div className="comparison-header">
        <strong>Player Comparison</strong>
        <span>{compareRows.length}/{maxComparePlayers} selected</span>
        {copyCompareShareLink && (
          <button type="button" className="inline-btn" onClick={copyCompareShareLink} aria-label="Copy shareable comparison link">
            Share
          </button>
        )}
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
  );
});
