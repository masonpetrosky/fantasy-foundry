import React, { useMemo } from "react";
import { stablePlayerKeyFromRow } from "../../../app_state_storage";

const SPARKLINE_COLORS = ["var(--accent)", "var(--green)", "var(--blue)", "var(--red)"];

function extractYearValues(row) {
  const entries = [];
  for (const key of Object.keys(row)) {
    if (key.startsWith("Value_")) {
      const year = parseInt(key.slice(6), 10);
      const val = Number(row[key]);
      if (Number.isFinite(year) && Number.isFinite(val)) {
        entries.push({ year, val });
      }
    }
  }
  entries.sort((a, b) => a.year - b.year);
  return entries;
}

function ComparisonSparklines({ compareRows }) {
  const allSeries = useMemo(() => compareRows.map(row => ({
    key: stablePlayerKeyFromRow(row),
    name: row.Player || "Player",
    values: extractYearValues(row),
  })), [compareRows]);

  const hasData = allSeries.some(s => s.values.length >= 2);
  if (!hasData) return null;

  const allVals = allSeries.flatMap(s => s.values.map(v => v.val));
  const allYears = allSeries.flatMap(s => s.values.map(v => v.year));
  const minVal = Math.min(...allVals);
  const maxVal = Math.max(...allVals);
  const minYear = Math.min(...allYears);
  const maxYear = Math.max(...allYears);
  const rangeVal = maxVal - minVal || 1;
  const rangeYear = maxYear - minYear || 1;
  const W = 280;
  const H = 80;
  const pad = 6;

  return (
    <div className="comparison-sparklines" aria-label="Dynasty value comparison chart">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-hidden="true">
        {allSeries.map((series, idx) => {
          if (series.values.length < 2) return null;
          const color = SPARKLINE_COLORS[idx % SPARKLINE_COLORS.length];
          const points = series.values.map(v => {
            const x = pad + ((v.year - minYear) / rangeYear) * (W - pad * 2);
            const y = pad + (H - pad * 2) - ((v.val - minVal) / rangeVal) * (H - pad * 2);
            return `${x.toFixed(1)},${y.toFixed(1)}`;
          }).join(" ");
          return (
            <polyline
              key={series.key}
              points={points}
              fill="none"
              stroke={color}
              strokeWidth="1.5"
              strokeLinejoin="round"
              strokeLinecap="round"
              opacity="0.85"
            />
          );
        })}
      </svg>
      <div className="comparison-sparkline-legend">
        {allSeries.filter(s => s.values.length >= 2).map((series, idx) => (
          <span key={series.key} className="comparison-sparkline-legend-item">
            <span className="comparison-sparkline-swatch" style={{ background: SPARKLINE_COLORS[idx % SPARKLINE_COLORS.length] }} />
            {series.name}
          </span>
        ))}
      </div>
    </div>
  );
}

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
      <ComparisonSparklines compareRows={compareRows} />
      <div className="comparison-grid">
        {compareRows.map(row => {
          const compareKey = stablePlayerKeyFromRow(row);
          return (
            <article className="comparison-card" key={compareKey}>
              <div className="comparison-card-head">
                <h4>{row.Player || "Player"}</h4>
                <button type="button" className="inline-btn" aria-label={`Remove ${row.Player || "player"} from comparison`} onClick={() => removeCompareRow(compareKey)}>Remove</button>
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
