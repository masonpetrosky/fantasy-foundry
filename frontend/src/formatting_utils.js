export function fmt(val, decimals = 1) {
  if (val == null || val === "" || isNaN(val)) return "—";
  return Number(val).toFixed(decimals);
}

export function fmtInt(val, useGrouping = true) {
  if (val == null || val === "" || isNaN(val)) return "—";
  return Math.round(Number(val)).toLocaleString(undefined, { useGrouping });
}

export const THREE_DECIMAL_COLS = new Set(["AVG", "OBP", "OPS"]);
export const TWO_DECIMAL_COLS = new Set(["ERA", "WHIP"]);
export const WHOLE_NUMBER_COLS = new Set([
  "AB", "R", "HR", "RBI", "SB", "IP", "W", "K", "SVH", "QS", "QA3",
  "G", "H", "2B", "3B", "BB", "SO", "GS", "L", "PitBB", "SV",
  "PitH", "PitHR", "ER",
]);
export const INT_COLS = new Set(["Rank", "Year", "Years", "Age", "ProjectionsUsed"]);

export function formatCellValue(col, val) {
  if (col === "DynastyValue" || col.startsWith("Value_")) return fmt(val, 2);
  if (TWO_DECIMAL_COLS.has(col)) return fmt(val, 2);
  if (THREE_DECIMAL_COLS.has(col)) return fmt(val, 3);
  if (WHOLE_NUMBER_COLS.has(col)) return fmtInt(val, true);
  if (INT_COLS.has(col)) return fmtInt(val, col !== "Year");
  if (typeof val === "number") return fmt(val);
  return val ?? "—";
}

export function parsePosTokens(posValue) {
  return String(posValue || "")
    .toUpperCase()
    .split("/")
    .map(token => token.trim())
    .filter(Boolean);
}

export function formatIsoDateLabel(value) {
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

export function resolveProjectionWindow(meta) {
  const years = Array.isArray(meta?.years)
    ? meta.years.map(Number).filter(Number.isFinite)
    : [];
  const metaStart = Number(meta?.projection_window_start);
  const metaEnd = Number(meta?.projection_window_end);
  const start = Number.isFinite(metaStart) ? metaStart : (years.length > 0 ? Math.min(...years) : null);
  const end = Number.isFinite(metaEnd) ? metaEnd : (years.length > 0 ? Math.max(...years) : null);
  const seasons = Number.isFinite(start) && Number.isFinite(end) && end >= start
    ? end - start + 1
    : null;
  return { start, end, seasons };
}
