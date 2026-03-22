import { normalizeHiddenColumnOverridesByTab } from "./projections_view_config";
export {
  CALC_PRESETS_STORAGE_KEY,
  CLOUD_PREFERENCES_VERSION,
  CLOUD_SYNC_DEBOUNCE_MS,
  FANTRAX_LEAGUE_STORAGE_KEY,
  FIRST_RUN_SESSION_LANDING_TS_STORAGE_KEY,
  FIRST_RUN_SESSION_SUCCESS_STORAGE_KEY,
  FIRST_RUN_STATE_COMPLETED,
  FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS,
  FIRST_RUN_STATE_NEW,
  FIRST_RUN_STATE_STORAGE_KEY,
  ONBOARDING_DISMISSED_STORAGE_KEY,
  PLAYER_WATCHLIST_STORAGE_KEY,
  buildCloudPreferencesPayload,
  calculatorPresetsEqual,
  formatAuthError,
  mergeCalculatorPresetsPreferLocal,
  normalizeCloudPreferences,
  readCalculatorPresets,
  readFantraxLeague,
  readFirstRunState,
  readOnboardingDismissed,
  readPlayerWatchlist,
  readSessionFirstRunLandingTimestamp,
  readSessionFirstRunSuccessRecorded,
  safeReadSessionStorage,
  safeReadStorage,
  safeWriteSessionStorage,
  safeWriteStorage,
  writeCalculatorPresets,
  writeFantraxLeague,
  writeFirstRunState,
  writeOnboardingDismissed,
  writePlayerWatchlist,
  writeSessionFirstRunLandingTimestamp,
  writeSessionFirstRunSuccessRecorded,
} from "./app_state_storage_core";
import {
  readBooleanStorage,
  safeReadStorage,
  safeWriteStorage,
  writeBooleanStorage,
  type PlayerWatchEntry,
} from "./app_state_storage_core";

export type {
  CalculatorPreset,
  CloudPreferences,
  CloudPreferencesPayload,
  FantraxLeagueState,
  PlayerWatchEntry,
} from "./app_state_storage_core";

export interface ProjectionFilterPreset {
  tab: string;
  search: string;
  teamFilter: string;
  yearFilter: string;
  posFilters: string[];
  watchlistOnly: boolean;
  sortCol: string;
  sortDir: string;
}

export interface ProjectionFilterPresetBundle {
  custom: ProjectionFilterPreset | null;
}

export interface SuccessfulCalcRun {
  scoringMode: string;
  teams: number;
  horizon: number;
  startYear: number | null;
  playerCount: number;
  completedAt: string;
}

export interface ProjectionRow {
  PlayerEntityKey?: string;
  PlayerKey?: string;
  Player?: string;
  Team?: string;
  Year?: string | number;
  Type?: string;
  Pos?: string;
  [key: string]: unknown;
}

export const BUILD_STORAGE_KEY = "ff:lastBuildId";
export const BUILD_QUERY_PARAM = "build";
export const CALC_LINK_QUERY_PARAM = "calc";
export const CALC_PANEL_OPEN_STORAGE_KEY = "ff:calc-panel-open:v1";
export const CALC_LAST_SUCCESSFUL_RUN_STORAGE_KEY = "ff:last-successful-calc-run:v1";
export const PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY = "ff:proj-mobile-layout-mode:v2";
export const PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY = "ff:proj-table-hidden-cols:v1";
export const PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY = "ff:proj-card-hidden-cols:v1";
export const PROJECTION_FILTER_PRESETS_STORAGE_KEY = "ff:proj-filter-presets:v1";
export const MAX_COMPARE_PLAYERS = 4;

export function readCalculatorPanelOpenPreference(): boolean | null {
  return readBooleanStorage(CALC_PANEL_OPEN_STORAGE_KEY);
}

export function writeCalculatorPanelOpenPreference(isOpen: boolean): void {
  writeBooleanStorage(CALC_PANEL_OPEN_STORAGE_KEY, Boolean(isOpen));
}

function coercePositiveInt(value: unknown): number | null {
  const n = Number(value);
  if (!Number.isFinite(n)) return null;
  const rounded = Math.round(n);
  return rounded > 0 ? rounded : null;
}

function normalizeCalcSuccessfulRun(raw: unknown): SuccessfulCalcRun | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const r = raw as Record<string, unknown>;
  const scoringMode = String(r.scoringMode || "").trim().toLowerCase() === "points" ? "points" : "roto";
  const teams = coercePositiveInt(r.teams);
  const horizon = coercePositiveInt(r.horizon);
  const startYear = coercePositiveInt(r.startYear);
  const playerCount = Math.max(0, Number.isFinite(Number(r.playerCount)) ? Math.round(Number(r.playerCount)) : 0);
  const completedAtRaw = String(r.completedAt || "").trim();
  const completedAtDate = completedAtRaw ? new Date(completedAtRaw) : null;
  const completedAt = completedAtDate && !Number.isNaN(completedAtDate.getTime())
    ? completedAtDate.toISOString()
    : new Date().toISOString();

  if (!teams || !horizon) return null;

  return {
    scoringMode,
    teams,
    horizon,
    startYear: startYear || null,
    playerCount,
    completedAt,
  };
}

export function readLastSuccessfulCalcRun(): SuccessfulCalcRun | null {
  const raw = safeReadStorage(CALC_LAST_SUCCESSFUL_RUN_STORAGE_KEY);
  if (!raw) return null;
  try {
    return normalizeCalcSuccessfulRun(JSON.parse(raw));
  } catch {
    return null;
  }
}

export function writeLastSuccessfulCalcRun(summary: unknown): void {
  const normalized = normalizeCalcSuccessfulRun(summary);
  if (!normalized) return;
  safeWriteStorage(CALC_LAST_SUCCESSFUL_RUN_STORAGE_KEY, JSON.stringify(normalized));
}

export function clearLastSuccessfulCalcRun(): void {
  try {
    window.localStorage.removeItem(CALC_LAST_SUCCESSFUL_RUN_STORAGE_KEY);
  } catch {
    // Ignore browsers/storage modes that disallow localStorage writes.
  }
}

export function normalizePlayerKey(value: unknown): string {
  const text = String(value || "").trim().toLowerCase();
  const normalized = text.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return normalized || "unknown-player";
}

export function calculationRowExplainKey(row: ProjectionRow | null | undefined): string {
  return String(row?.PlayerEntityKey || row?.PlayerKey || normalizePlayerKey(row?.Player)).trim();
}

export function projectionRowKey(row: ProjectionRow | null | undefined, fallbackIndex: number = 0): string {
  const entity = String(row?.PlayerEntityKey || row?.PlayerKey || "").trim();
  const player = String(row?.Player || "").trim();
  const team = String(row?.Team || "").trim();
  const year = String(row?.Year ?? "").trim();
  const side = String(row?.Type || "").trim();
  const stableKey = entity || `${player}|${team}|${year}|${side}`;
  return stableKey ? `${stableKey}|${fallbackIndex}` : `row-${fallbackIndex}`;
}


export function stablePlayerKeyFromRow(row: ProjectionRow | null | undefined): string {
  const explicitKey = String(row?.PlayerEntityKey || row?.PlayerKey || "").trim();
  if (explicitKey) return explicitKey;
  const playerKey = normalizePlayerKey(row?.Player);
  const teamKey = String(row?.Team || "").trim().toLowerCase();
  return teamKey ? `${playerKey}__${teamKey}` : playerKey;
}

export function playerWatchEntryFromRow(row: ProjectionRow | null | undefined): PlayerWatchEntry {
  return {
    key: stablePlayerKeyFromRow(row),
    player: String(row?.Player || "Unknown Player").trim() || "Unknown Player",
    team: String(row?.Team || "").trim(),
    pos: String(row?.Pos || "").trim(),
  };
}


function normalizeProjectionFilterPreset(rawPreset: unknown): ProjectionFilterPreset | null {
  if (!rawPreset || typeof rawPreset !== "object" || Array.isArray(rawPreset)) return null;
  const rp = rawPreset as Record<string, unknown>;
  const rawTab = String(rp.tab || "").trim().toLowerCase();
  const tab = rawTab === "bat" || rawTab === "pitch" ? rawTab : "all";
  const rawSortDir = String(rp.sortDir || "").trim().toLowerCase();
  const sortDir = rawSortDir === "asc" ? "asc" : "desc";
  const posFilters = Array.isArray(rp.posFilters)
    ? (rp.posFilters as unknown[])
      .map(value => String(value || "").trim())
      .filter(Boolean)
    : [];

  return {
    tab,
    search: String(rp.search || "").trim(),
    teamFilter: String(rp.teamFilter || "").trim(),
    yearFilter: String(rp.yearFilter || "").trim(),
    posFilters: Array.from(new Set(posFilters)),
    watchlistOnly: Boolean(rp.watchlistOnly),
    sortCol: String(rp.sortCol || "").trim(),
    sortDir,
  };
}

function normalizeProjectionFilterPresetBundle(rawBundle: unknown): ProjectionFilterPresetBundle {
  if (!rawBundle || typeof rawBundle !== "object" || Array.isArray(rawBundle)) {
    return { custom: null };
  }
  return {
    custom: normalizeProjectionFilterPreset((rawBundle as Record<string, unknown>).custom),
  };
}

export function readProjectionFilterPresets(): ProjectionFilterPresetBundle {
  const raw = safeReadStorage(PROJECTION_FILTER_PRESETS_STORAGE_KEY);
  if (!raw) return { custom: null };
  try {
    return normalizeProjectionFilterPresetBundle(JSON.parse(raw));
  } catch {
    return { custom: null };
  }
}

export function writeProjectionFilterPresets(rawBundle: unknown): void {
  const normalized = normalizeProjectionFilterPresetBundle(rawBundle);
  safeWriteStorage(PROJECTION_FILTER_PRESETS_STORAGE_KEY, JSON.stringify(normalized));
}

export function readHiddenColumnOverridesByTab(storageKey: string): Record<string, Record<string, boolean>> {
  const raw = safeReadStorage(storageKey);
  if (!raw) return normalizeHiddenColumnOverridesByTab(null);
  try {
    return normalizeHiddenColumnOverridesByTab(JSON.parse(raw));
  } catch {
    return normalizeHiddenColumnOverridesByTab(null);
  }
}

export function writeHiddenColumnOverridesByTab(storageKey: string, overridesByTab: unknown): void {
  safeWriteStorage(
    storageKey,
    JSON.stringify(normalizeHiddenColumnOverridesByTab(overridesByTab))
  );
}

function csvEscape(value: unknown): string {
  const text = String(value ?? "");
  if (text.includes('"') || text.includes(",") || text.includes("\n")) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export function buildWatchlistCsv(watchlist: Record<string, PlayerWatchEntry> | null | undefined): string {
  const rows = Object.values(watchlist || {})
    .filter((entry): entry is PlayerWatchEntry => entry != null && typeof entry === "object")
    .sort((a, b) => String(a.player || "").localeCompare(String(b.player || "")));
  const header = ["Player", "Team", "Pos", "PlayerKey"];
  const lines = [header.join(",")];
  rows.forEach(entry => {
    lines.push([
      csvEscape(entry.player || ""),
      csvEscape(entry.team || ""),
      csvEscape(entry.pos || ""),
      csvEscape(entry.key || ""),
    ].join(","));
  });
  return lines.join("\n");
}

export function mergeKnownCalculatorSettings(
  baseSettings: Record<string, unknown>,
  incomingSettings: Record<string, unknown> | null | undefined,
): Record<string, unknown> {
  const merged = { ...baseSettings };
  if (!incomingSettings || typeof incomingSettings !== "object") return merged;
  const normalizedIncoming = normalizeLegacyCalculatorSettings(incomingSettings);
  Object.keys(baseSettings).forEach(key => {
    if (Object.prototype.hasOwnProperty.call(normalizedIncoming, key)) {
      merged[key] = normalizedIncoming[key];
    }
  });
  // League mode removed — force common for legacy presets/URLs.
  merged.mode = "common";
  return merged;
}

export function encodeCalculatorSettings(settings: Record<string, unknown>): string {
  try {
    return window.btoa(encodeURIComponent(JSON.stringify(settings)));
  } catch {
    return "";
  }
}

/** Known calculator setting keys used for schema validation of decoded presets. */
const KNOWN_CALCULATOR_KEYS = new Set([
  "mode", "scoring_mode", "points_valuation_mode", "two_way", "sgp_denominator_mode",
  "sgp_winsor_low_pct", "sgp_winsor_high_pct", "sgp_epsilon_counting", "sgp_epsilon_ratio",
  "enable_playing_time_reliability", "enable_age_risk_adjustment",
  "enable_prospect_risk_adjustment", "enable_bench_stash_relief", "bench_negative_penalty",
  "enable_ir_stash_relief", "ir_negative_penalty",
  "enable_replacement_blend", "replacement_blend_alpha",
  "teams", "sims", "horizon", "discount",
  "hit_c", "hit_1b", "hit_2b", "hit_3b", "hit_ss", "hit_ci", "hit_mi", "hit_of", "hit_dh", "hit_ut",
  "pit_p", "pit_sp", "pit_rp", "bench", "minors", "ir", "keeper_limit",
  "ip_min", "ip_max", "start_year", "auction_budget",
  "weekly_starts_cap", "allow_same_day_starts_overflow", "weekly_acquisition_cap",
  "roto_hit_r", "roto_hit_rbi", "roto_hit_hr", "roto_hit_sb", "roto_hit_avg",
  "roto_hit_obp", "roto_hit_slg", "roto_hit_ops", "roto_hit_h", "roto_hit_bb",
  "roto_hit_2b", "roto_hit_tb",
  "roto_pit_w", "roto_pit_k", "roto_pit_sv", "roto_pit_era", "roto_pit_whip",
  "roto_pit_qs", "roto_pit_qa3", "roto_pit_svh",
  "pts_hit_1b", "pts_hit_2b", "pts_hit_3b", "pts_hit_hr", "pts_hit_r",
  "pts_hit_rbi", "pts_hit_sb", "pts_hit_bb", "pts_hit_hbp", "pts_hit_so",
  "pts_pit_ip", "pts_pit_w", "pts_pit_l", "pts_pit_k", "pts_pit_sv",
  "pts_pit_svh", "pts_pit_hld", "pts_pit_h", "pts_pit_er", "pts_pit_bb", "pts_pit_hbp",
]);

function normalizeLegacyCalculatorSettings(
  settings: Record<string, unknown> | null | undefined,
): Record<string, unknown> {
  const source = settings && typeof settings === "object" ? settings : {};
  const normalized = { ...source };
  const legacySvh = Number(normalized.pts_pit_svh);
  if (!Number.isFinite(legacySvh) || Object.prototype.hasOwnProperty.call(normalized, "pts_pit_hld")) {
    return normalized;
  }

  const currentSv = Number(normalized.pts_pit_sv);
  normalized.pts_pit_sv = (Number.isFinite(currentSv) ? currentSv : 0) + legacySvh;
  normalized.pts_pit_hld = legacySvh;
  delete normalized.pts_pit_svh;
  return normalized;
}

export function decodeCalculatorSettings(encoded: string | null | undefined): Record<string, unknown> | null {
  if (!encoded) return null;
  try {
    const raw = window.atob(encoded);
    const parsed = JSON.parse(decodeURIComponent(raw));
    if (!parsed || typeof parsed !== "object") return null;
    // Strip unknown keys to prevent stale/invalid settings from breaking the calculator.
    const validated: Record<string, unknown> = {};
    for (const key of Object.keys(parsed)) {
      if (KNOWN_CALCULATOR_KEYS.has(key)) {
        validated[key] = parsed[key];
      }
    }
    const normalized = normalizeLegacyCalculatorSettings(validated);
    return Object.keys(normalized).length > 0 ? normalized : null;
  } catch {
    return null;
  }
}
