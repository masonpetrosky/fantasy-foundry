import {
  POINTS_SCORING_FIELDS,
  ROTO_HITTER_CATEGORY_FIELDS,
  ROTO_PITCHER_CATEGORY_FIELDS,
  coerceBooleanSetting,
} from "./dynasty_calculator_config.js";

export const PROJECTION_TABS = ["all", "bat", "pitch"];
export const PROJECTION_HITTER_CORE_STATS = ["AB", "R", "HR", "RBI", "SB", "AVG", "OPS"];
export const PROJECTION_PITCHER_CORE_STATS = ["IP", "W", "K", "SV", "ERA", "WHIP", "QS", "QA3"];

const POINTS_RULE_COLUMN_MAP = {
  pts_hit_1b: { bat: "H", all_hit: "H" },
  pts_hit_2b: { bat: "2B", all_hit: "2B" },
  pts_hit_3b: { bat: "3B", all_hit: "3B" },
  pts_hit_hr: { bat: "HR", all_hit: "HR" },
  pts_hit_r: { bat: "R", all_hit: "R" },
  pts_hit_rbi: { bat: "RBI", all_hit: "RBI" },
  pts_hit_sb: { bat: "SB", all_hit: "SB" },
  pts_hit_bb: { bat: "BB", all_hit: "BB" },
  pts_hit_so: { bat: "SO", all_hit: "SO" },
  pts_pit_ip: { pitch: "IP", all_pitch: "IP" },
  pts_pit_w: { pitch: "W", all_pitch: "W" },
  pts_pit_l: { pitch: "L", all_pitch: "L" },
  pts_pit_k: { pitch: "K", all_pitch: "K" },
  pts_pit_sv: { pitch: "SV", all_pitch: "SV" },
  pts_pit_svh: { pitch: "SVH", all_pitch: "SVH" },
  pts_pit_h: { pitch: "H", all_pitch: "PitH" },
  pts_pit_er: { pitch: "ER", all_pitch: "ER" },
  pts_pit_bb: { pitch: "BB", all_pitch: "PitBB" },
};

function isSettingsObject(value) {
  return value && typeof value === "object" && !Array.isArray(value);
}

function resolveScoringMode(settings) {
  if (!isSettingsObject(settings)) return "roto";
  const mode = String(settings.scoring_mode || "").trim().toLowerCase();
  return mode === "points" ? "points" : "roto";
}

function resolveRowSide(tab, row) {
  if (tab === "bat") return "H";
  if (tab === "pitch") return "P";
  const side = String(row?.Type || "").trim().toUpperCase();
  if (side === "H" || side === "P") return side;
  return "BOTH";
}

function forcedUsageStats(tab, row) {
  if (tab === "bat") return ["AB"];
  if (tab === "pitch") return ["IP"];
  const side = resolveRowSide(tab, row);
  if (side === "H") return ["AB"];
  if (side === "P") return ["IP"];
  return ["AB", "IP"];
}

function fallbackCoreStats(tab, row) {
  if (tab === "bat") return [...PROJECTION_HITTER_CORE_STATS];
  if (tab === "pitch") return [...PROJECTION_PITCHER_CORE_STATS];
  const side = resolveRowSide(tab, row);
  if (side === "H") return [...PROJECTION_HITTER_CORE_STATS];
  if (side === "P") return [...PROJECTION_PITCHER_CORE_STATS];
  return [...PROJECTION_HITTER_CORE_STATS, ...PROJECTION_PITCHER_CORE_STATS];
}

function resolveSelectedRotoStats(tab, row, settings) {
  if (!isSettingsObject(settings)) return [];
  const selectedHit = ROTO_HITTER_CATEGORY_FIELDS
    .filter(field => coerceBooleanSetting(settings[field.key], field.defaultValue))
    .map(field => field.statCol);
  const selectedPitch = ROTO_PITCHER_CATEGORY_FIELDS
    .filter(field => coerceBooleanSetting(settings[field.key], field.defaultValue))
    .map(field => field.statCol);

  if (tab === "bat") return selectedHit;
  if (tab === "pitch") return selectedPitch;

  const side = resolveRowSide(tab, row);
  if (side === "H") return selectedHit;
  if (side === "P") return selectedPitch;
  return [...selectedHit, ...selectedPitch];
}

function resolvePointsColumnsForRule(ruleKey, tab, row) {
  const mapping = POINTS_RULE_COLUMN_MAP[ruleKey];
  if (!mapping) return [];

  if (tab === "bat") return mapping.bat ? [mapping.bat] : [];
  if (tab === "pitch") return mapping.pitch ? [mapping.pitch] : [];

  const side = resolveRowSide(tab, row);
  if (side === "H") return mapping.all_hit ? [mapping.all_hit] : [];
  if (side === "P") return mapping.all_pitch ? [mapping.all_pitch] : [];

  return [mapping.all_hit, mapping.all_pitch].filter(Boolean);
}

function resolveSelectedPointsStats(tab, row, settings) {
  if (!isSettingsObject(settings)) return [];
  const selected = [];
  POINTS_SCORING_FIELDS.forEach(field => {
    const rawValue = Number(settings[field.key]);
    if (!Number.isFinite(rawValue) || Math.abs(rawValue) <= 1e-9) return;
    selected.push(...resolvePointsColumnsForRule(field.key, tab, row));
  });
  return uniqueColumnOrder(selected);
}

export function resolveProjectionPriorityStats(tab, row, calculatorSettings) {
  const forced = forcedUsageStats(tab, row);
  const mode = resolveScoringMode(calculatorSettings);
  const fromMetrics = mode === "points"
    ? resolveSelectedPointsStats(tab, row, calculatorSettings)
    : resolveSelectedRotoStats(tab, row, calculatorSettings);
  const fallback = fromMetrics.length > 0 ? [] : fallbackCoreStats(tab, row);
  return uniqueColumnOrder([...forced, ...fromMetrics, ...fallback]);
}

function filterToCandidates(priorityStats, candidates) {
  const allowed = new Set(candidates);
  return uniqueColumnOrder((priorityStats || []).filter(col => allowed.has(col)));
}

export function uniqueColumnOrder(columns) {
  const seen = new Set();
  const ordered = [];
  (columns || []).forEach(col => {
    const key = String(col || "").trim();
    if (!key || seen.has(key)) return;
    seen.add(key);
    ordered.push(key);
  });
  return ordered;
}

export function normalizeHiddenColumnOverridesByTab(raw) {
  const normalized = Object.fromEntries(PROJECTION_TABS.map(tab => [tab, {}]));
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return normalized;
  PROJECTION_TABS.forEach(tab => {
    const source = raw[tab];
    if (!source || typeof source !== "object" || Array.isArray(source)) return;
    const mapped = {};
    Object.entries(source).forEach(([rawCol, rawHidden]) => {
      const col = String(rawCol || "").trim();
      if (!col) return;
      mapped[col] = Boolean(rawHidden);
    });
    normalized[tab] = mapped;
  });
  return normalized;
}

export function projectionTableColumnCatalog(tab, seasonCol, dynastyYearCols, calculatorSettings = null) {
  const identityCols = ["Player", "Team", "Pos", "Age", "DynastyValue"];

  if (tab === "bat") {
    const statCandidates = uniqueColumnOrder([
      ...PROJECTION_HITTER_CORE_STATS,
      "OBP",
      "G",
      "H",
      "2B",
      "3B",
      "BB",
      "SO",
    ]);
    const priorityStats = filterToCandidates(resolveProjectionPriorityStats(tab, null, calculatorSettings), statCandidates);
    const remainingStats = statCandidates.filter(col => !priorityStats.includes(col));
    return uniqueColumnOrder([
      ...identityCols,
      ...priorityStats,
      ...(dynastyYearCols || []),
      ...remainingStats,
      "ProjectionsUsed",
      "OldestProjectionDate",
      seasonCol,
    ]);
  }

  if (tab === "pitch") {
    const statCandidates = uniqueColumnOrder([
      ...PROJECTION_PITCHER_CORE_STATS,
      "G",
      "GS",
      "L",
      "BB",
      "H",
      "HR",
      "ER",
      "SVH",
    ]);
    const priorityStats = filterToCandidates(resolveProjectionPriorityStats(tab, null, calculatorSettings), statCandidates);
    const remainingStats = statCandidates.filter(col => !priorityStats.includes(col));
    return uniqueColumnOrder([
      ...identityCols,
      ...priorityStats,
      ...(dynastyYearCols || []),
      ...remainingStats,
      "ProjectionsUsed",
      "OldestProjectionDate",
      seasonCol,
    ]);
  }

  const statCandidates = uniqueColumnOrder([
    ...PROJECTION_HITTER_CORE_STATS,
    ...PROJECTION_PITCHER_CORE_STATS,
    "OBP",
    "G",
    "H",
    "2B",
    "3B",
    "BB",
    "SO",
    "GS",
    "L",
    "PitBB",
    "PitH",
    "PitHR",
    "ER",
    "SVH",
  ]);
  const priorityStats = filterToCandidates(resolveProjectionPriorityStats(tab, null, calculatorSettings), statCandidates);
  const remainingStats = statCandidates.filter(col => !priorityStats.includes(col));
  return uniqueColumnOrder([
    ...identityCols,
    ...priorityStats,
    ...(dynastyYearCols || []),
    ...remainingStats,
    "ProjectionsUsed",
    "OldestProjectionDate",
    seasonCol,
    "Type",
  ]);
}

export function projectionCardColumnCatalog(tab, seasonCol, dynastyYearCols, calculatorSettings = null) {
  if (tab === "bat") {
    const statCandidates = uniqueColumnOrder([
      ...PROJECTION_HITTER_CORE_STATS,
      "OBP",
      "G",
      "H",
      "2B",
      "3B",
      "BB",
      "SO",
    ]);
    const priorityStats = filterToCandidates(resolveProjectionPriorityStats(tab, null, calculatorSettings), statCandidates);
    const remainingStats = statCandidates.filter(col => !priorityStats.includes(col));
    return uniqueColumnOrder([
      ...priorityStats,
      ...remainingStats,
      "Rank",
      "DynastyValue",
      ...(dynastyYearCols || []),
      seasonCol,
      "ProjectionsUsed",
      "OldestProjectionDate",
    ]);
  }

  if (tab === "pitch") {
    const statCandidates = uniqueColumnOrder([
      ...PROJECTION_PITCHER_CORE_STATS,
      "G",
      "GS",
      "L",
      "BB",
      "H",
      "HR",
      "ER",
      "SVH",
    ]);
    const priorityStats = filterToCandidates(resolveProjectionPriorityStats(tab, null, calculatorSettings), statCandidates);
    const remainingStats = statCandidates.filter(col => !priorityStats.includes(col));
    return uniqueColumnOrder([
      ...priorityStats,
      ...remainingStats,
      "Rank",
      "DynastyValue",
      ...(dynastyYearCols || []),
      seasonCol,
      "ProjectionsUsed",
      "OldestProjectionDate",
    ]);
  }

  const statCandidates = uniqueColumnOrder([
    ...PROJECTION_HITTER_CORE_STATS,
    ...PROJECTION_PITCHER_CORE_STATS,
    "OBP",
    "G",
    "H",
    "2B",
    "3B",
    "BB",
    "SO",
    "GS",
    "L",
    "PitBB",
    "PitH",
    "PitHR",
    "ER",
    "SVH",
  ]);
  const priorityStats = filterToCandidates(resolveProjectionPriorityStats(tab, null, calculatorSettings), statCandidates);
  const remainingStats = statCandidates.filter(col => !priorityStats.includes(col));
  return uniqueColumnOrder([
    ...priorityStats,
    ...remainingStats,
    "Rank",
    "DynastyValue",
    ...(dynastyYearCols || []),
    seasonCol,
    "Type",
    "ProjectionsUsed",
    "OldestProjectionDate",
  ]);
}

export function projectionTableColumnHiddenByDefault(tab, col) {
  if (col === "Years") return true;
  if (tab === "all" && col === "Type") return true;
  return false;
}

export function isProjectionTableColumnHidden(tab, col, hiddenOverrides = {}) {
  if (Object.prototype.hasOwnProperty.call(hiddenOverrides, col)) {
    return Boolean(hiddenOverrides[col]);
  }
  return projectionTableColumnHiddenByDefault(tab, col);
}

export function resolveProjectionTableColumns(tab, seasonCol, dynastyYearCols, hiddenOverrides = {}, calculatorSettings = null) {
  return projectionTableColumnCatalog(tab, seasonCol, dynastyYearCols, calculatorSettings)
    .filter(col => !isProjectionTableColumnHidden(tab, col, hiddenOverrides));
}

export function resolveProjectionCardCoreColumnsForRow(tab, row, calculatorSettings = null) {
  return resolveProjectionPriorityStats(tab, row, calculatorSettings);
}

export function projectionCardDefaultVisibleColumns(tab, row, calculatorSettings = null) {
  return uniqueColumnOrder([
    ...resolveProjectionCardCoreColumnsForRow(tab, row, calculatorSettings),
    "Rank",
    "DynastyValue",
  ]);
}

export function projectionCardOptionalColumnHiddenByDefault(col, defaultVisibleSet = new Set(["Rank", "DynastyValue"])) {
  return !defaultVisibleSet.has(col);
}

export function isProjectionCardOptionalColumnHidden(col, defaultVisibleSet, hiddenOverrides = {}) {
  if (Object.prototype.hasOwnProperty.call(hiddenOverrides, col)) {
    return Boolean(hiddenOverrides[col]);
  }
  return projectionCardOptionalColumnHiddenByDefault(col, defaultVisibleSet);
}

export function resolveProjectionCardColumns(tab, seasonCol, dynastyYearCols, row, hiddenOverrides = {}, calculatorSettings = null) {
  const catalog = projectionCardColumnCatalog(tab, seasonCol, dynastyYearCols, calculatorSettings);
  const defaultVisibleSet = new Set(projectionCardDefaultVisibleColumns(tab, row, calculatorSettings));
  return catalog.filter(col => !isProjectionCardOptionalColumnHidden(col, defaultVisibleSet, hiddenOverrides));
}
