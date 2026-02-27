import React, { useId, useRef, useState } from "react";
import { MenuButton, useMenuInteractions } from "./accessibility_components";

/* ------------------------------------------------------------------ */
/*  ColumnChooserControl                                              */
/* ------------------------------------------------------------------ */

interface ColumnChooserControlProps {
  columns: string[];
  hiddenCols: Record<string, boolean>;
  requiredCols: Set<string>;
  onToggleColumn: (col: string) => void;
  onShowAllColumns?: (() => void) | null;
  buttonLabel?: string;
  columnLabels?: Record<string, string> | null;
}

export function ColumnChooserControl({
  columns,
  hiddenCols,
  requiredCols,
  onToggleColumn,
  onShowAllColumns,
  buttonLabel = "Columns",
  columnLabels,
}: ColumnChooserControlProps): React.ReactElement {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
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

/* ------------------------------------------------------------------ */
/*  ExplainabilityCard                                                */
/* ------------------------------------------------------------------ */

interface YearEntry {
  year?: number | string;
  year_value?: number;
  discount_factor?: number;
  discounted_contribution?: number;
  points?: Record<string, unknown>;
}

interface Explanation {
  player?: string;
  team?: string;
  pos?: string;
  mode?: string;
  raw_dynasty_value?: number;
  dynasty_value?: number;
  per_year?: YearEntry[];
}

interface ExplainabilityCardProps {
  explanation: Explanation | null | undefined;
  selectedYear: string;
  onSelectedYearChange: (year: string) => void;
  fmt: (val: unknown, decimals?: number) => string;
}

export function ExplainabilityCard({
  explanation,
  selectedYear,
  onSelectedYearChange,
  fmt,
}: ExplainabilityCardProps): React.ReactElement | null {
  if (!explanation) return null;
  const years: YearEntry[] = Array.isArray(explanation?.per_year) ? explanation.per_year : [];
  if (years.length === 0) return null;
  const activeYear = !selectedYear
    ? years[0]
    : years.find(entry => String(entry?.year) === selectedYear) || years[0];
  const points: Record<string, unknown> = (activeYear?.points || {}) as Record<string, unknown>;
  const pointsHitting = points.hitting && typeof points.hitting === "object" ? points.hitting as Record<string, unknown> : {};
  const pointsPitching = points.pitching && typeof points.pitching === "object" ? points.pitching as Record<string, unknown> : {};
  const hittingRulePoints = pointsHitting.rule_points && typeof pointsHitting.rule_points === "object"
    ? pointsHitting.rule_points as Record<string, unknown>
    : {};
  const pitchingRulePoints = pointsPitching.rule_points && typeof pointsPitching.rule_points === "object"
    ? pointsPitching.rule_points as Record<string, unknown>
    : {};
  const HITTING_POINT_EVENT_ORDER = ["1B", "2B", "3B", "HR", "R", "RBI", "SB", "BB", "SO"];
  const PITCHING_POINT_EVENT_ORDER = ["IP", "W", "L", "K", "SV", "SVH", "H", "ER", "BB"];
  const HITTING_POINT_LABELS: Record<string, string> = {};
  const PITCHING_POINT_LABELS: Record<string, string> = { SVH: "SVH", H: "H Allowed", BB: "BB Allowed" };

  const formatPointLabel = (key: string): string => String(key || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, char => char.toUpperCase());

  const formatPointValue = (value: unknown): string => {
    if (typeof value === "number" && Number.isFinite(value)) return fmt(value, 2);
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (value == null || value === "") return "\u2014";
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  };

  const orderedPointEntries = (valueMap: Record<string, unknown> | null | undefined, order: string[]): [string, unknown][] => {
    const orderIndex = new Map(order.map((key, idx) => [key, idx]));
    return Object.entries(valueMap || {}).sort(([left], [right]) => {
      const leftIdx = orderIndex.has(left) ? orderIndex.get(left)! : Number.MAX_SAFE_INTEGER;
      const rightIdx = orderIndex.has(right) ? orderIndex.get(right)! : Number.MAX_SAFE_INTEGER;
      if (leftIdx !== rightIdx) return leftIdx - rightIdx;
      return left.localeCompare(right);
    });
  };

  const renderPointList = (title: string, valueMap: Record<string, unknown>, order: string[], labels: Record<string, string>): React.ReactElement => {
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

  const pointSummaryRows: [string, unknown][] = [
    ["Hitting Points", (points as Record<string, unknown>).hitting_points],
    ["Pitching Points", (points as Record<string, unknown>).pitching_points],
    ["Selected Points", (points as Record<string, unknown>).selected_points],
    ["Selected Side", (points as Record<string, unknown>).selected_side],
    ["Hitting Best Slot", (points as Record<string, unknown>).hitting_best_slot],
    ["Pitching Best Slot", (points as Record<string, unknown>).pitching_best_slot],
    ["Hitting Value", (points as Record<string, unknown>).hitting_value],
    ["Pitching Value", (points as Record<string, unknown>).pitching_value],
    ["Hitting Assignment Slot", (points as Record<string, unknown>).hitting_assignment_slot],
    ["Pitching Assignment Slot", (points as Record<string, unknown>).pitching_assignment_slot],
    ["Hitting Assignment Value", (points as Record<string, unknown>).hitting_assignment_value],
    ["Pitching Assignment Value", (points as Record<string, unknown>).pitching_assignment_value],
    ["Hitting Assignment Replacement", (points as Record<string, unknown>).hitting_assignment_replacement],
    ["Pitching Assignment Replacement", (points as Record<string, unknown>).pitching_assignment_replacement],
    ["Keep/Drop Value", (points as Record<string, unknown>).keep_drop_value],
    ["Keep/Drop Hold Value", (points as Record<string, unknown>).keep_drop_hold_value],
    ["Keep/Drop Keep", (points as Record<string, unknown>).keep_drop_keep],
  ];

  return (
    <div className="explain-card">
      <h4>Value Breakdown: {explanation.player || "Player"}</h4>
      <div className="explain-meta">
        <span>{explanation.team || "\u2014"} · {explanation.pos || "\u2014"}</span>
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
                  <tr key={label as string}>
                    <td>{label as string}</td>
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
