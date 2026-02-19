import { normalizeHiddenColumnOverridesByTab } from "./projections_view_config.js";

export const BUILD_STORAGE_KEY = "ff:lastBuildId";
export const BUILD_QUERY_PARAM = "build";
export const CALC_PRESETS_STORAGE_KEY = "ff:calc-presets:v1";
export const CALC_LINK_QUERY_PARAM = "calc";
export const PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY = "ff:proj-mobile-layout-mode:v2";
export const PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY = "ff:proj-table-hidden-cols:v1";
export const PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY = "ff:proj-card-hidden-cols:v1";
export const PLAYER_WATCHLIST_STORAGE_KEY = "ff:player-watchlist:v1";
export const CLOUD_SYNC_DEBOUNCE_MS = 900;
export const CLOUD_PREFERENCES_VERSION = 1;
export const MAX_COMPARE_PLAYERS = 4;

export function safeReadStorage(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function safeWriteStorage(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignore browsers/storage modes that disallow localStorage writes.
  }
}

export function normalizePlayerKey(value) {
  const text = String(value || "").trim().toLowerCase();
  const normalized = text.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return normalized || "unknown-player";
}

export function calculationRowExplainKey(row) {
  return String(row?.PlayerEntityKey || row?.PlayerKey || normalizePlayerKey(row?.Player)).trim();
}

export function projectionRowKey(row, fallbackIndex = 0) {
  const entity = String(row?.PlayerEntityKey || row?.PlayerKey || "").trim();
  const player = String(row?.Player || "").trim();
  const team = String(row?.Team || "").trim();
  const year = String(row?.Year ?? "").trim();
  const side = String(row?.Type || "").trim();
  const stableKey = entity || `${player}|${team}|${year}|${side}`;
  return stableKey ? `${stableKey}|${fallbackIndex}` : `row-${fallbackIndex}`;
}

function normalizeCalculatorPresets(presets) {
  if (!presets || typeof presets !== "object" || Array.isArray(presets)) return {};
  const sanitized = {};
  Object.entries(presets).forEach(([rawName, rawPreset]) => {
    const name = String(rawName || "").trim();
    if (!name) return;
    if (!rawPreset || typeof rawPreset !== "object" || Array.isArray(rawPreset)) return;
    sanitized[name] = { ...rawPreset };
  });
  return sanitized;
}

export function readCalculatorPresets() {
  const raw = safeReadStorage(CALC_PRESETS_STORAGE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return normalizeCalculatorPresets(parsed);
  } catch {
    return {};
  }
}

export function writeCalculatorPresets(presets) {
  safeWriteStorage(CALC_PRESETS_STORAGE_KEY, JSON.stringify(normalizeCalculatorPresets(presets)));
}

export function stablePlayerKeyFromRow(row) {
  const explicitKey = String(row?.PlayerEntityKey || row?.PlayerKey || "").trim();
  if (explicitKey) return explicitKey;
  const playerKey = normalizePlayerKey(row?.Player);
  const teamKey = String(row?.Team || "").trim().toLowerCase();
  return teamKey ? `${playerKey}__${teamKey}` : playerKey;
}

export function playerWatchEntryFromRow(row) {
  return {
    key: stablePlayerKeyFromRow(row),
    player: String(row?.Player || "Unknown Player").trim() || "Unknown Player",
    team: String(row?.Team || "").trim(),
    pos: String(row?.Pos || "").trim(),
  };
}

function normalizePlayerWatchlistEntries(rawEntries) {
  if (!rawEntries || typeof rawEntries !== "object" || Array.isArray(rawEntries)) return {};
  const entries = {};
  Object.entries(rawEntries).forEach(([rawKey, value]) => {
    const key = String(rawKey || "").trim();
    if (!key) return;
    if (!value || typeof value !== "object") return;
    entries[key] = {
      key,
      player: String(value.player || "").trim() || "Unknown Player",
      team: String(value.team || "").trim(),
      pos: String(value.pos || "").trim(),
    };
  });
  return entries;
}

export function readPlayerWatchlist() {
  const raw = safeReadStorage(PLAYER_WATCHLIST_STORAGE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return normalizePlayerWatchlistEntries(parsed);
  } catch {
    return {};
  }
}

export function writePlayerWatchlist(watchlist) {
  safeWriteStorage(PLAYER_WATCHLIST_STORAGE_KEY, JSON.stringify(normalizePlayerWatchlistEntries(watchlist)));
}

export function readHiddenColumnOverridesByTab(storageKey) {
  const raw = safeReadStorage(storageKey);
  if (!raw) return normalizeHiddenColumnOverridesByTab(null);
  try {
    return normalizeHiddenColumnOverridesByTab(JSON.parse(raw));
  } catch {
    return normalizeHiddenColumnOverridesByTab(null);
  }
}

export function writeHiddenColumnOverridesByTab(storageKey, overridesByTab) {
  safeWriteStorage(
    storageKey,
    JSON.stringify(normalizeHiddenColumnOverridesByTab(overridesByTab))
  );
}

export function normalizeCloudPreferences(rawPreferences) {
  if (!rawPreferences || typeof rawPreferences !== "object" || Array.isArray(rawPreferences)) {
    return {
      calculatorPresets: {},
      playerWatchlist: {},
    };
  }
  return {
    calculatorPresets: normalizeCalculatorPresets(rawPreferences.calculator_presets),
    playerWatchlist: normalizePlayerWatchlistEntries(rawPreferences.player_watchlist),
  };
}

export function buildCloudPreferencesPayload({ calculatorPresets, playerWatchlist }) {
  return {
    version: CLOUD_PREFERENCES_VERSION,
    calculator_presets: normalizeCalculatorPresets(calculatorPresets),
    player_watchlist: normalizePlayerWatchlistEntries(playerWatchlist),
  };
}

export function formatAuthError(error, fallbackMessage) {
  const message = String(error?.message || "").trim();
  return message || fallbackMessage;
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (text.includes('"') || text.includes(",") || text.includes("\n")) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export function buildWatchlistCsv(watchlist) {
  const rows = Object.values(watchlist || {})
    .filter(entry => entry && typeof entry === "object")
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

export function mergeKnownCalculatorSettings(baseSettings, incomingSettings) {
  const merged = { ...baseSettings };
  if (!incomingSettings || typeof incomingSettings !== "object") return merged;
  Object.keys(baseSettings).forEach(key => {
    if (Object.prototype.hasOwnProperty.call(incomingSettings, key)) {
      merged[key] = incomingSettings[key];
    }
  });
  return merged;
}

export function encodeCalculatorSettings(settings) {
  try {
    return window.btoa(encodeURIComponent(JSON.stringify(settings)));
  } catch {
    return "";
  }
}

export function decodeCalculatorSettings(encoded) {
  if (!encoded) return null;
  try {
    const raw = window.atob(encoded);
    const parsed = JSON.parse(decodeURIComponent(raw));
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}
