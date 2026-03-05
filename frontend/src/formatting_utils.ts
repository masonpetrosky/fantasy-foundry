export function fmt(val: unknown, decimals = 1): string {
  if (val == null || val === "" || isNaN(val as number)) return "\u2014";
  return Number(val).toFixed(decimals);
}

export function fmtInt(val: unknown, useGrouping = true): string {
  if (val == null || val === "" || isNaN(val as number)) return "\u2014";
  return Math.round(Number(val)).toLocaleString(undefined, { useGrouping });
}

export const THREE_DECIMAL_COLS: ReadonlySet<string> = new Set(["AVG", "OBP", "OPS"]);
export const TWO_DECIMAL_COLS: ReadonlySet<string> = new Set(["ERA", "WHIP"]);
export const WHOLE_NUMBER_COLS: ReadonlySet<string> = new Set([
  "AB", "R", "HR", "RBI", "SB", "IP", "W", "K", "SVH", "QS", "QA3",
  "G", "H", "2B", "3B", "BB", "SO", "GS", "L", "PitBB", "SV",
  "PitH", "PitHR", "ER",
]);
export const INT_COLS: ReadonlySet<string> = new Set(["Rank", "Year", "Years", "Age"]);

export function fmtSigned(val: unknown, decimals = 2): string {
  if (val == null || val === "" || isNaN(val as number)) return "\u2014";
  const n = Number(val);
  const prefix = n > 0 ? "+" : n < 0 ? "\u2212" : "";
  return `${prefix}${Math.abs(n).toFixed(decimals)}`;
}

export function formatCellValue(col: string, val: unknown): string {
  if (col === "DynastyValue" || col.startsWith("Value_")) return fmtSigned(val, 2);
  if (TWO_DECIMAL_COLS.has(col)) return fmt(val, 2);
  if (THREE_DECIMAL_COLS.has(col)) return fmt(val, 3);
  if (WHOLE_NUMBER_COLS.has(col)) return fmtInt(val as number, true);
  if (INT_COLS.has(col)) return fmtInt(val as number, col !== "Year");
  if (typeof val === "number") return fmt(val);
  return (val as string) ?? "\u2014";
}

export function parsePosTokens(posValue: unknown): string[] {
  return String(posValue || "")
    .toUpperCase()
    .split("/")
    .map(token => token.trim())
    .filter(Boolean);
}

export function formatIsoDateLabel(value: unknown): string {
  const text = String(value || "").trim();
  if (!text) return "Unknown";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export interface ProjectionWindowMeta {
  years?: unknown[];
  projection_window_start?: unknown;
  projection_window_end?: unknown;
}

export interface ProjectionWindow {
  start: number | null;
  end: number | null;
  seasons: number | null;
}

export function resolveProjectionWindow(meta: ProjectionWindowMeta | null | undefined): ProjectionWindow {
  const years = Array.isArray(meta?.years)
    ? meta.years.map(Number).filter(Number.isFinite)
    : [];
  const metaStart = Number(meta?.projection_window_start);
  const metaEnd = Number(meta?.projection_window_end);
  const start = Number.isFinite(metaStart) ? metaStart : (years.length > 0 ? Math.min(...years) : null);
  const end = Number.isFinite(metaEnd) ? metaEnd : (years.length > 0 ? Math.max(...years) : null);
  const seasons = Number.isFinite(start) && Number.isFinite(end) && end! >= start!
    ? end! - start! + 1
    : null;
  return { start, end, seasons };
}
