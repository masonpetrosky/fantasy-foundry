import {
  MAX_COMPARE_PLAYERS,
  stablePlayerKeyFromRow,
} from "../../../app_state_storage";

const CAREER_TOTALS_FILTER_VALUE = "__career_totals__";

export function normalizeCompareKey(value) {
  return String(value || "").trim().toLowerCase();
}

export function parseCompareKeysFromUrl() {
  try {
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("compare") || "";
    const deduped = [];
    const seen = new Set();
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

export function coerceRowYear(value) {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return Math.round(parsed);
}

export function rowCompareIdentityKeys(row) {
  const keys = new Set();
  const entityKey = normalizeCompareKey(row?.PlayerEntityKey);
  const playerKey = normalizeCompareKey(row?.PlayerKey);
  const stableKey = normalizeCompareKey(stablePlayerKeyFromRow(row));
  if (entityKey) keys.add(entityKey);
  if (playerKey) keys.add(playerKey);
  if (stableKey) keys.add(stableKey);
  return keys;
}

export function pickPreferredCompareRow(rows, { careerTotalsView, resolvedYearFilter }) {
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

  let latestRow = null;
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

export function profilePayloadRows(payload, { careerTotalsView }) {
  if (!payload || typeof payload !== "object") return [];
  if (careerTotalsView) {
    if (Array.isArray(payload.career_totals) && payload.career_totals.length > 0) {
      return payload.career_totals;
    }
  } else if (Array.isArray(payload.series) && payload.series.length > 0) {
    return payload.series;
  }
  return Array.isArray(payload.data) ? payload.data : [];
}

export function mergeCompareRowsWithCap(current, rows) {
  const next = { ...(current || {}) };
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

export function resolveCompareShareHydrationNotice({
  requestedKeys,
  matchedKeys,
}) {
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

export function resolveProjectionDataset(tab) {
  if (tab === "bat" || tab === "pitch") return tab;
  return "all";
}

export function buildProjectionCompareHydrationRequest({
  apiBase,
  compareKeys,
  tab,
  careerTotalsView,
  resolvedYearFilter,
  calculatorJobId,
}) {
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

export function selectHydratedCompareRows({
  rows,
  requestedKeys,
  careerTotalsView,
  resolvedYearFilter,
}) {
  const normalizedRequestedKeys = Array.isArray(requestedKeys)
    ? requestedKeys.map(token => normalizeCompareKey(token)).filter(Boolean)
    : [];
  if (!Array.isArray(rows) || rows.length === 0 || normalizedRequestedKeys.length === 0) {
    return {};
  }

  const candidatesByKey = new Map();
  rows.forEach(row => {
    rowCompareIdentityKeys(row).forEach(identityKey => {
      const candidates = candidatesByKey.get(identityKey) || [];
      candidates.push(row);
      candidatesByKey.set(identityKey, candidates);
    });
  });

  const selectedRowsByKey = {};
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
