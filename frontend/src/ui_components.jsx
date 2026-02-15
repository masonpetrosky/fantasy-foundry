import React, { useEffect, useRef, useState } from "react";

export function ColumnChooserControl({
  columns,
  hiddenCols,
  requiredCols,
  onToggleColumn,
  onShowAllColumns,
  buttonLabel = "Columns",
  columnLabels,
}) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef(null);
  const optionalColumns = columns.filter(col => !requiredCols.has(col));
  const hiddenOptionalCount = optionalColumns.filter(col => hiddenCols[col]).length;
  const visibleCount = columns.length - Object.keys(hiddenCols || {}).length;

  useEffect(() => {
    const onOutsideClick = event => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const onEscape = event => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onOutsideClick);
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("mousedown", onOutsideClick);
      document.removeEventListener("keydown", onEscape);
    };
  }, []);

  return (
    <div className="multi-select" ref={menuRef}>
      <button
        type="button"
        className={`inline-btn ${open ? "open" : ""}`}
        onClick={() => setOpen(value => !value)}
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        {buttonLabel} ({visibleCount}/{columns.length})
      </button>
      {open && (
        <div className="multi-select-menu" role="listbox" aria-multiselectable="true">
          {onShowAllColumns && (
            <button
              type="button"
              className="multi-select-clear"
              onClick={onShowAllColumns}
              disabled={hiddenOptionalCount === 0}
            >
              Show All Optional Columns
            </button>
          )}
          {columns.map(col => {
            const isRequired = requiredCols.has(col);
            return (
              <label key={col} className="multi-select-option">
                <input
                  type="checkbox"
                  checked={!hiddenCols[col]}
                  disabled={isRequired}
                  onChange={() => onToggleColumn(col)}
                />
                <span>{(columnLabels && columnLabels[col]) || col.replace("Value_", "")}{isRequired ? " (Required)" : ""}</span>
              </label>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function ExplainabilityCard({
  explanation,
  selectedYear,
  onSelectedYearChange,
  fmt,
}) {
  if (!explanation) return null;
  const years = Array.isArray(explanation?.per_year) ? explanation.per_year : [];
  if (years.length === 0) return null;
  const activeYear = !selectedYear
    ? years[0]
    : years.find(entry => String(entry?.year) === selectedYear) || years[0];
  const points = activeYear?.points || {};
  const pointsHitting = points.hitting && typeof points.hitting === "object" ? points.hitting : {};
  const pointsPitching = points.pitching && typeof points.pitching === "object" ? points.pitching : {};

  const formatPointLabel = key => String(key || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, char => char.toUpperCase());

  const formatPointValue = value => {
    if (typeof value === "number" && Number.isFinite(value)) return fmt(value, 2);
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (value == null) return "0";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  const renderPointList = (title, valueMap) => {
    const entries = Object.entries(valueMap || {});
    if (entries.length === 0) {
      return (
        <div className="explain-points-card">
          <h5>{title}</h5>
          <p className="calc-note" style={{ margin: 0 }}>No point events recorded for this year.</p>
        </div>
      );
    }

    return (
      <div className="explain-points-card">
        <h5>{title}</h5>
        <table className="explain-mini-table">
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td>{formatPointLabel(key)}</td>
                <td className="num">{formatPointValue(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="explain-card">
      <h4>Value Breakdown: {explanation.player || "Player"}</h4>
      <div className="explain-meta">
        <span>{explanation.team || "—"} · {explanation.pos || "—"}</span>
        <span>Mode: {String(explanation.mode || "").toUpperCase()}</span>
        <span>Raw {fmt(explanation.raw_dynasty_value, 2)}</span>
        <span>Centered {fmt(explanation.dynasty_value, 2)}</span>
      </div>
      {years.length > 1 && (
        <div className="form-group" style={{maxWidth: 220, marginBottom: 10}}>
          <label>Detail Year</label>
          <select
            value={selectedYear}
            onChange={e => onSelectedYearChange(e.target.value)}
          >
            {years.map(entry => (
              <option key={String(entry?.year)} value={String(entry?.year)}>{entry?.year}</option>
            ))}
          </select>
        </div>
      )}
      <table className="explain-table">
        <thead>
          <tr>
            <th>Year</th>
            <th>Year Value</th>
            <th>Discount</th>
            <th>Discounted</th>
          </tr>
        </thead>
        <tbody>
          {years.map(entry => (
            <tr key={String(entry?.year)}>
              <td>{entry?.year}</td>
              <td className="num">{fmt(entry?.year_value, 2)}</td>
              <td className="num">{fmt(entry?.discount_factor, 3)}</td>
              <td className="num">{fmt(entry?.discounted_contribution, 2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {explanation.mode === "points" && (
        <div className="explain-points-grid">
          {renderPointList("Hitting Points", pointsHitting)}
          {renderPointList("Pitching Points", pointsPitching)}
        </div>
      )}
    </div>
  );
}
