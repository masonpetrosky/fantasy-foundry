export const PROJECTION_TABS = ["all", "bat", "pitch"];
export const PROJECTION_HITTER_CORE_STATS = ["AB", "R", "HR", "RBI", "SB", "AVG", "OPS"];
export const PROJECTION_PITCHER_CORE_STATS = ["IP", "W", "K", "SV", "ERA", "WHIP", "QS"];

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

export function projectionTableColumnCatalog(tab, seasonCol, dynastyYearCols) {
  const identityCols = ["Player", "Team", "Pos", "Age", "DynastyValue"];
  if (tab === "bat") {
    return uniqueColumnOrder([
      ...identityCols,
      ...PROJECTION_HITTER_CORE_STATS,
      ...(dynastyYearCols || []),
      "OBP",
      "OPS",
      "G",
      "H",
      "2B",
      "3B",
      "BB",
      "SO",
      "ProjectionsUsed",
      "OldestProjectionDate",
      seasonCol,
    ]);
  }
  if (tab === "pitch") {
    return uniqueColumnOrder([
      ...identityCols,
      ...PROJECTION_PITCHER_CORE_STATS,
      ...(dynastyYearCols || []),
      "QS",
      "G",
      "GS",
      "L",
      "BB",
      "H",
      "HR",
      "ER",
      "SVH",
      "ProjectionsUsed",
      "OldestProjectionDate",
      seasonCol,
    ]);
  }
  return uniqueColumnOrder([
    ...identityCols,
    ...PROJECTION_HITTER_CORE_STATS,
    ...PROJECTION_PITCHER_CORE_STATS,
    ...(dynastyYearCols || []),
    "OBP",
    "OPS",
    "QS",
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
    "ProjectionsUsed",
    "OldestProjectionDate",
    seasonCol,
    "Type",
  ]);
}

export function projectionCardColumnCatalog(tab, seasonCol, dynastyYearCols) {
  if (tab === "bat") {
    return uniqueColumnOrder([
      ...PROJECTION_HITTER_CORE_STATS,
      "Rank",
      "DynastyValue",
      ...(dynastyYearCols || []),
      seasonCol,
      "OBP",
      "G",
      "H",
      "2B",
      "3B",
      "BB",
      "SO",
      "ProjectionsUsed",
      "OldestProjectionDate",
    ]);
  }
  if (tab === "pitch") {
    return uniqueColumnOrder([
      ...PROJECTION_PITCHER_CORE_STATS,
      "Rank",
      "DynastyValue",
      ...(dynastyYearCols || []),
      seasonCol,
      "G",
      "GS",
      "L",
      "BB",
      "H",
      "HR",
      "ER",
      "SVH",
      "ProjectionsUsed",
      "OldestProjectionDate",
    ]);
  }
  return uniqueColumnOrder([
    ...PROJECTION_HITTER_CORE_STATS,
    ...PROJECTION_PITCHER_CORE_STATS,
    "Rank",
    "DynastyValue",
    ...(dynastyYearCols || []),
    seasonCol,
    "Type",
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

export function resolveProjectionTableColumns(tab, seasonCol, dynastyYearCols, hiddenOverrides = {}) {
  return projectionTableColumnCatalog(tab, seasonCol, dynastyYearCols)
    .filter(col => !isProjectionTableColumnHidden(tab, col, hiddenOverrides));
}

export function resolveProjectionCardCoreColumnsForRow(tab, row) {
  if (tab === "bat") return PROJECTION_HITTER_CORE_STATS;
  if (tab === "pitch") return PROJECTION_PITCHER_CORE_STATS;
  const side = String(row?.Type || "").trim().toUpperCase();
  if (side === "P") return PROJECTION_PITCHER_CORE_STATS;
  if (side === "H") return PROJECTION_HITTER_CORE_STATS;
  return [...PROJECTION_HITTER_CORE_STATS, ...PROJECTION_PITCHER_CORE_STATS];
}

export function projectionCardOptionalColumnHiddenByDefault(col) {
  if (col === "Rank" || col === "DynastyValue") return false;
  return true;
}

export function isProjectionCardOptionalColumnHidden(col, coreUnionSet, hiddenOverrides = {}) {
  if (coreUnionSet.has(col)) return false;
  if (Object.prototype.hasOwnProperty.call(hiddenOverrides, col)) {
    return Boolean(hiddenOverrides[col]);
  }
  return projectionCardOptionalColumnHiddenByDefault(col);
}

export function resolveProjectionCardColumns(tab, seasonCol, dynastyYearCols, row, hiddenOverrides = {}) {
  const catalog = projectionCardColumnCatalog(tab, seasonCol, dynastyYearCols);
  const coreUnion = tab === "bat"
    ? [...PROJECTION_HITTER_CORE_STATS]
    : tab === "pitch"
      ? [...PROJECTION_PITCHER_CORE_STATS]
      : [...PROJECTION_HITTER_CORE_STATS, ...PROJECTION_PITCHER_CORE_STATS];
  const coreUnionSet = new Set(coreUnion);
  const coreCols = resolveProjectionCardCoreColumnsForRow(tab, row);
  const optionalCols = catalog.filter(col => !coreUnionSet.has(col));
  const visibleOptional = optionalCols.filter(col => (
    !isProjectionCardOptionalColumnHidden(col, coreUnionSet, hiddenOverrides)
  ));
  return uniqueColumnOrder([
    ...coreCols,
    ...visibleOptional,
  ]);
}
