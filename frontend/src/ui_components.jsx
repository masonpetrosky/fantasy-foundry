import React, { useId, useRef, useState } from "react";
import { MenuButton, useMenuInteractions } from "./accessibility_components";

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
  const triggerRef = useRef(null);
  const menuId = useId();
  const triggerId = `${menuId}-trigger`;
  const optionalColumns = columns.filter(col => !requiredCols.has(col));
  const hiddenOptionalCount = optionalColumns.filter(col => hiddenCols[col]).length;
  const visibleCount = columns.length - Object.keys(hiddenCols || {}).length;

  useMenuInteractions({
    open,
    setOpen,
    menuRef,
    triggerRef,
  });

  return (
    <div className="multi-select" ref={menuRef}>
      <MenuButton
        controlsId={menuId}
        open={open}
        buttonRef={triggerRef}
        id={triggerId}
        className={`inline-btn ${open ? "open" : ""}`}
        onToggle={() => setOpen(value => !value)}
        label={`${buttonLabel} (${visibleCount}/${columns.length})`}
      />
      {open && (
        <div
          id={menuId}
          className="multi-select-menu"
          role="group"
          aria-labelledby={triggerId}
        >
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
  const hittingRulePoints = pointsHitting.rule_points && typeof pointsHitting.rule_points === "object"
    ? pointsHitting.rule_points
    : {};
  const pitchingRulePoints = pointsPitching.rule_points && typeof pointsPitching.rule_points === "object"
    ? pointsPitching.rule_points
    : {};
  const HITTING_POINT_EVENT_ORDER = ["1B", "2B", "3B", "HR", "R", "RBI", "SB", "BB", "SO"];
  const PITCHING_POINT_EVENT_ORDER = ["IP", "W", "L", "K", "SV", "SVH", "H", "ER", "BB"];
  const HITTING_POINT_LABELS = {};
  const PITCHING_POINT_LABELS = { SVH: "SVH", H: "H Allowed", BB: "BB Allowed" };

  const formatPointLabel = key => String(key || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, char => char.toUpperCase());

  const formatPointValue = value => {
    if (typeof value === "number" && Number.isFinite(value)) return fmt(value, 2);
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (value == null || value === "") return "—";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  const orderedPointEntries = (valueMap, order) => {
    const orderIndex = new Map(order.map((key, idx) => [key, idx]));
    return Object.entries(valueMap || {}).sort(([left], [right]) => {
      const leftIdx = orderIndex.has(left) ? orderIndex.get(left) : Number.MAX_SAFE_INTEGER;
      const rightIdx = orderIndex.has(right) ? orderIndex.get(right) : Number.MAX_SAFE_INTEGER;
      if (leftIdx !== rightIdx) return leftIdx - rightIdx;
      return left.localeCompare(right);
    });
  };

  const renderPointList = (title, valueMap, order, labels) => {
    const entries = orderedPointEntries(valueMap, order);
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
                <td>{labels[key] || formatPointLabel(key)}</td>
                <td className="num">{formatPointValue(value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const pointSummaryRows = [
    ["Hitting Points", points.hitting_points],
    ["Pitching Points", points.pitching_points],
    ["Selected Points", points.selected_points],
    ["Selected Side", points.selected_side],
    ["Hitting Best Slot", points.hitting_best_slot],
    ["Pitching Best Slot", points.pitching_best_slot],
    ["Hitting Value", points.hitting_value],
    ["Pitching Value", points.pitching_value],
    ["Hitting Assignment Slot", points.hitting_assignment_slot],
    ["Pitching Assignment Slot", points.pitching_assignment_slot],
    ["Hitting Assignment Value", points.hitting_assignment_value],
    ["Pitching Assignment Value", points.pitching_assignment_value],
    ["Hitting Assignment Replacement", points.hitting_assignment_replacement],
    ["Pitching Assignment Replacement", points.pitching_assignment_replacement],
    ["Keep/Drop Value", points.keep_drop_value],
    ["Keep/Drop Hold Value", points.keep_drop_hold_value],
    ["Keep/Drop Keep", points.keep_drop_keep],
  ];

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
          <div className="explain-points-card">
            <h5>Point Summary</h5>
            <table className="explain-mini-table">
              <tbody>
                {pointSummaryRows.map(([label, value]) => (
                  <tr key={label}>
                    <td>{label}</td>
                    <td className="num">{formatPointValue(value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {renderPointList("Hitting Rule Points", hittingRulePoints, HITTING_POINT_EVENT_ORDER, HITTING_POINT_LABELS)}
          {renderPointList("Pitching Rule Points", pitchingRulePoints, PITCHING_POINT_EVENT_ORDER, PITCHING_POINT_LABELS)}
        </div>
      )}
    </div>
  );
}
