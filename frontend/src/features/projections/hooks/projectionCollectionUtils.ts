import {
  MAX_COMPARE_PLAYERS,
  stablePlayerKeyFromRow,
} from "../../../app_state_storage";
import type { ProjectionRow } from "../../../app_state_storage";

const CAREER_TOTALS_FILTER_VALUE = "__career_totals__";

export function normalizeCompareKey(value: unknown): string {
  return String(value || "").trim().toLowerCase();
}

export function parseCompareKeysFromUrl(): string[] {
  try {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("compare") || "";
    const deduped: string[] = [];
    const seen = new Set<string>();
    raw
      .split(",")
      .map(token => normalizeCompareKey(token))
      .filter(Boolean)
      .forEach(token => {
        if (seen.has(token)) return;
        seen.add(token);
        deduped.push(token);
      });
    return deduped.slice(0, MAX_COMPARE_PLAYERS);
  } catch {
    return [];
  }
}

export function coerceRowYear(value: unknown): number | null {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return Math.round(parsed);
}

export function rowCompareIdentityKeys(row: ProjectionRow | null | undefined): Set<string> {
  const keys = new Set<string>();
  const entityKey = normalizeCompareKey(row?.PlayerEntityKey);
  const playerKey = normalizeCompareKey(row?.PlayerKey);
  const stableKey = normalizeCompareKey(stablePlayerKeyFromRow(row));
  if (entityKey) keys.add(entityKey);
  if (playerKey) keys.add(playerKey);
  if (stableKey) keys.add(stableKey);
  return keys;
}

export interface PickPreferredCompareRowOptions {
  careerTotalsView: boolean;
  resolvedYearFilter: string;
}

export function pickPreferredCompareRow(
  rows: ProjectionRow[] | null | undefined,
  { careerTotalsView, resolvedYearFilter }: PickPreferredCompareRowOptions,
): ProjectionRow | null {
  if (!Array.isArray(rows) || rows.length === 0) return null;
  if (careerTotalsView) {
    const careerRows = rows.filter(row => row && (row.Years != null || row.YearStart != null || row.YearEnd != null));
    if (careerRows.length > 0) return careerRows[0];
    return rows[0];
  }

  const yearFilter = String(resolvedYearFilter || "").trim();
  if (yearFilter && yearFilter !== CAREER_TOTALS_FILTER_VALUE) {
    const exactYearRow = rows.find(row => String(row?.Year ?? "").trim() === yearFilter);
    if (exactYearRow) return exactYearRow;
  }

  let latestRow: ProjectionRow | null = null;
  let latestYear = Number.NEGATIVE_INFINITY;
  rows.forEach(row => {
    const year = coerceRowYear(row?.Year);
    if (year != null && year > latestYear) {
      latestYear = year;
      latestRow = row;
    }
  });
  return latestRow || rows[0];
}

export interface ProfilePayloadRowsOptions {
  careerTotalsView: boolean;
}

interface ProfilePayload {
  career_totals?: unknown[];
  series?: unknown[];
  data?: unknown[];
}

export function profilePayloadRows(
  payload: unknown,
  { careerTotalsView }: ProfilePayloadRowsOptions,
): ProjectionRow[] {
  if (!payload || typeof payload !== "object") return [];
  const p = payload as ProfilePayload;
  if (careerTotalsView) {
    if (Array.isArray(p.career_totals) && p.career_totals.length > 0) {
      return p.career_totals as ProjectionRow[];
    }
  } else if (Array.isArray(p.series) && p.series.length > 0) {
    return p.series as ProjectionRow[];
  }
  return Array.isArray(p.data) ? (p.data as ProjectionRow[]) : [];
}

export function mergeCompareRowsWithCap(
  current: Record<string, ProjectionRow> | null | undefined,
  rows: (ProjectionRow | null | undefined)[],
): Record<string, ProjectionRow> {
  const next: Record<string, ProjectionRow> = { ...(current || {}) };
  let count = Object.keys(next).length;
  rows.forEach(row => {
    if (!row || typeof row !== "object") return;
    const key = stablePlayerKeyFromRow(row);
    if (!key) return;
    if (next[key]) {
      next[key] = row;
      return;
    }
    if (count >= MAX_COMPARE_PLAYERS) return;
    next[key] = row;
    count += 1;
  });
  return next;
}

export interface CompareShareHydrationNotice {
  severity: "warning" | "error";
  message: string;
}

export function resolveCompareShareHydrationNotice({
  requestedKeys,
  matchedKeys,
}: {
  requestedKeys: unknown[];
  matchedKeys: unknown[];
}): CompareShareHydrationNotice | null {
  const requested = Array.isArray(requestedKeys)
    ? requestedKeys.map(token => normalizeCompareKey(token)).filter(Boolean)
    : [];
  if (requested.length === 0) return null;

  const matched = new Set(
    Array.isArray(matchedKeys)
      ? matchedKeys.map(token => normalizeCompareKey(token)).filter(Boolean)
      : []
  );
  const unresolved = requested.filter(key => !matched.has(key));
  if (unresolved.length === 0) return null;

  const resolvedCount = requested.length - unresolved.length;
  const preview = unresolved.slice(0, 3).join(", ");
  const previewSuffix = unresolved.length > 3 ? ` (+${unresolved.length - 3} more)` : "";
  if (resolvedCount > 0) {
    return {
      severity: "warning",
      message: `Loaded ${resolvedCount}/${requested.length} shared comparison players. Missing: ${preview}${previewSuffix}.`,
    };
  }
  return {
    severity: "error",
    message: `Unable to load shared comparison players from link. Missing: ${preview}${previewSuffix}.`,
  };
}

export type ProjectionDataset = "bat" | "pitch" | "all";

export function resolveProjectionDataset(tab: string): ProjectionDataset {
  if (tab === "bat" || tab === "pitch") return tab;
  return "all";
}

export interface BuildProjectionCompareHydrationRequestOptions {
  apiBase: string;
  compareKeys: unknown[];
  tab: string;
  careerTotalsView: boolean;
  resolvedYearFilter: string;
  calculatorJobId: string;
}

export function buildProjectionCompareHydrationRequest({
  apiBase,
  compareKeys,
  tab,
  careerTotalsView,
  resolvedYearFilter,
  calculatorJobId,
}: BuildProjectionCompareHydrationRequestOptions): string {
  const base = String(apiBase || "").trim().replace(/\/+$/, "");
  const requestedKeys = Array.isArray(compareKeys)
    ? compareKeys.map(token => normalizeCompareKey(token)).filter(Boolean)
    : [];
  if (!base || requestedKeys.length < 2) return "";

  const url = new URL(`${base}/api/projections/compare`);
  url.searchParams.set("player_keys", requestedKeys.join(","));
  url.searchParams.set("dataset", resolveProjectionDataset(tab));
  url.searchParams.set("career_totals", careerTotalsView ? "true" : "false");
  const normalizedYearFilter = String(resolvedYearFilter || "").trim();
  if (!careerTotalsView && normalizedYearFilter && normalizedYearFilter !== CAREER_TOTALS_FILTER_VALUE) {
    url.searchParams.set("year", normalizedYearFilter);
  }
  url.searchParams.set("include_dynasty", "true");
  const normalizedCalculatorJobId = String(calculatorJobId || "").trim();
  if (normalizedCalculatorJobId) {
    url.searchParams.set("calculator_job_id", normalizedCalculatorJobId);
  }
  return url.toString();
}

export interface SelectHydratedCompareRowsOptions {
  rows: ProjectionRow[];
  requestedKeys: string[];
  careerTotalsView: boolean;
  resolvedYearFilter: string;
}

export function selectHydratedCompareRows({
  rows,
  requestedKeys,
  careerTotalsView,
  resolvedYearFilter,
}: SelectHydratedCompareRowsOptions): Record<string, ProjectionRow> {
  const normalizedRequestedKeys = Array.isArray(requestedKeys)
    ? requestedKeys.map(token => normalizeCompareKey(token)).filter(Boolean)
    : [];
  if (!Array.isArray(rows) || rows.length === 0 || normalizedRequestedKeys.length === 0) {
    return {};
  }

  const candidatesByKey = new Map<string, ProjectionRow[]>();
  rows.forEach(row => {
    rowCompareIdentityKeys(row).forEach(identityKey => {
      const candidates = candidatesByKey.get(identityKey) || [];
      candidates.push(row);
      candidatesByKey.set(identityKey, candidates);
    });
  });

  const selectedRowsByKey: Record<string, ProjectionRow> = {};
  normalizedRequestedKeys.forEach(requestedKey => {
    const candidates = candidatesByKey.get(requestedKey);
    const selectedRow = pickPreferredCompareRow(candidates, {
      careerTotalsView: Boolean(careerTotalsView),
      resolvedYearFilter,
    });
    if (!selectedRow) return;
    selectedRowsByKey[stablePlayerKeyFromRow(selectedRow)] = selectedRow;
  });
  return selectedRowsByKey;
}
