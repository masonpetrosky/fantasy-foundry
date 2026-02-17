import React, { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { createRoot } from "react-dom/client";
import { ColumnChooserControl, ExplainabilityCard } from "./ui_components.jsx";
import { normalizeCalculatorRunSettingsInput } from "./calculator_submit.js";
import { parseDownloadFilename } from "./download_filename.js";
import { AUTH_SYNC_ENABLED, SUPABASE_PREFS_TABLE, loadSupabaseClient } from "./supabase_client.js";
import {
  PROJECTION_TABS,
  PROJECTION_HITTER_CORE_STATS,
  PROJECTION_PITCHER_CORE_STATS,
  uniqueColumnOrder,
  normalizeHiddenColumnOverridesByTab,
  projectionTableColumnCatalog,
  projectionCardColumnCatalog,
  projectionTableColumnHiddenByDefault,
} from "./projections_view_config.js";


// ---------------------------------------------------------------------------
// Config: API base URL (empty string = same origin)
// ---------------------------------------------------------------------------
function normalizeApiBase(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

function resolveApiBase() {
  const fromQuery = normalizeApiBase(new URLSearchParams(window.location.search).get("api"));
  if (fromQuery) return fromQuery;

  const fromGlobal = normalizeApiBase(window.API_BASE_URL || window.__API_BASE_URL__);
  if (fromGlobal) return fromGlobal;

  const { protocol, hostname, port } = window.location;
  if (protocol === "file:") return "http://localhost:8000";

  const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1";
  const localFrontendPorts = new Set(["3000", "4173", "5173"]);
  if (isLocalhost && localFrontendPorts.has(String(port || ""))) {
    return `${protocol}//${hostname}:8000`;
  }

  return "";
}

const API = resolveApiBase();
const BUILD_STORAGE_KEY = "ff:lastBuildId";
const BUILD_QUERY_PARAM = "build";
const CALC_PRESETS_STORAGE_KEY = "ff:calc-presets:v1";
const CALC_LINK_QUERY_PARAM = "calc";
const PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY = "ff:proj-mobile-layout-mode:v2";
const PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY = "ff:proj-table-hidden-cols:v1";
const PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY = "ff:proj-card-hidden-cols:v1";
const PLAYER_WATCHLIST_STORAGE_KEY = "ff:player-watchlist:v1";
const CLOUD_SYNC_DEBOUNCE_MS = 900;
const CLOUD_PREFERENCES_VERSION = 1;
const MAX_COMPARE_PLAYERS = 4;
const PRIMARY_NAV_ITEMS = [
  { key: "projections", label: "Projections" },
  { key: "calculator", label: "Dynasty Calculator" },
];
const INDEX_BUILD_ID = (() => {
  const metaEl = document.querySelector('meta[name="ff-build-id"]');
  const value = String(metaEl?.getAttribute("content") || "").trim();
  return value.startsWith("__APP_BUILD_") ? "" : value;
})();


// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------
function fmt(val, decimals = 1) {
  if (val == null || val === "" || isNaN(val)) return "—";
  return Number(val).toFixed(decimals);
}

function fmtInt(val, useGrouping = true) {
  if (val == null || val === "" || isNaN(val)) return "—";
  return Math.round(Number(val)).toLocaleString(undefined, { useGrouping });
}

function parsePosTokens(posValue) {
  return String(posValue || "")
    .toUpperCase()
    .split("/")
    .map(token => token.trim())
    .filter(Boolean);
}

function safeReadStorage(key) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeWriteStorage(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignore browsers/storage modes that disallow localStorage writes.
  }
}

function normalizePlayerKey(value) {
  const text = String(value || "").trim().toLowerCase();
  const normalized = text.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return normalized || "unknown-player";
}

function calculationRowExplainKey(row) {
  return String(row?.PlayerEntityKey || row?.PlayerKey || normalizePlayerKey(row?.Player)).trim();
}

function projectionRowKey(row, fallbackIndex = 0) {
  const entity = String(row?.PlayerEntityKey || row?.PlayerKey || "").trim();
  const player = String(row?.Player || "").trim();
  const team = String(row?.Team || "").trim();
  const year = String(row?.Year ?? "").trim();
  const side = String(row?.Type || "").trim();
  const stableKey = entity || `${player}|${team}|${year}|${side}`;
  return stableKey ? `${stableKey}|${fallbackIndex}` : `row-${fallbackIndex}`;
}

function downloadBlob(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  triggerBlobDownload(filename, blob);
}

function triggerBlobDownload(filename, blob) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
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

function readCalculatorPresets() {
  const raw = safeReadStorage(CALC_PRESETS_STORAGE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return normalizeCalculatorPresets(parsed);
  } catch {
    return {};
  }
}

function writeCalculatorPresets(presets) {
  safeWriteStorage(CALC_PRESETS_STORAGE_KEY, JSON.stringify(normalizeCalculatorPresets(presets)));
}

function stablePlayerKeyFromRow(row) {
  const explicitKey = String(row?.PlayerEntityKey || row?.PlayerKey || "").trim();
  if (explicitKey) return explicitKey;
  const playerKey = normalizePlayerKey(row?.Player);
  const teamKey = String(row?.Team || "").trim().toLowerCase();
  return teamKey ? `${playerKey}__${teamKey}` : playerKey;
}

function playerWatchEntryFromRow(row) {
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

function readPlayerWatchlist() {
  const raw = safeReadStorage(PLAYER_WATCHLIST_STORAGE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return normalizePlayerWatchlistEntries(parsed);
  } catch {
    return {};
  }
}

function writePlayerWatchlist(watchlist) {
  safeWriteStorage(PLAYER_WATCHLIST_STORAGE_KEY, JSON.stringify(normalizePlayerWatchlistEntries(watchlist)));
}

function readHiddenColumnOverridesByTab(storageKey) {
  const raw = safeReadStorage(storageKey);
  if (!raw) return normalizeHiddenColumnOverridesByTab(null);
  try {
    return normalizeHiddenColumnOverridesByTab(JSON.parse(raw));
  } catch {
    return normalizeHiddenColumnOverridesByTab(null);
  }
}

function writeHiddenColumnOverridesByTab(storageKey, overridesByTab) {
  safeWriteStorage(
    storageKey,
    JSON.stringify(normalizeHiddenColumnOverridesByTab(overridesByTab))
  );
}

function normalizeCloudPreferences(rawPreferences) {
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

function buildCloudPreferencesPayload({ calculatorPresets, playerWatchlist }) {
  return {
    version: CLOUD_PREFERENCES_VERSION,
    calculator_presets: normalizeCalculatorPresets(calculatorPresets),
    player_watchlist: normalizePlayerWatchlistEntries(playerWatchlist),
  };
}

function formatAuthError(error, fallbackMessage) {
  const message = String(error?.message || "").trim();
  return message || fallbackMessage;
}

function csvEscape(value) {
  const text = String(value ?? "");
  if (text.includes("\"") || text.includes(",") || text.includes("\n")) {
    return `"${text.replace(/"/g, "\"\"")}"`;
  }
  return text;
}

function buildWatchlistCsv(watchlist) {
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

function mergeKnownCalculatorSettings(baseSettings, incomingSettings) {
  const merged = { ...baseSettings };
  if (!incomingSettings || typeof incomingSettings !== "object") return merged;
  Object.keys(baseSettings).forEach(key => {
    if (Object.prototype.hasOwnProperty.call(incomingSettings, key)) {
      merged[key] = incomingSettings[key];
    }
  });
  return merged;
}

function encodeCalculatorSettings(settings) {
  try {
    return window.btoa(encodeURIComponent(JSON.stringify(settings)));
  } catch {
    return "";
  }
}

function decodeCalculatorSettings(encoded) {
  if (!encoded) return null;
  try {
    const raw = window.atob(encoded);
    const parsed = JSON.parse(decodeURIComponent(raw));
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

const DEFAULT_PROJECTIONS_TAB = "all";
const DEFAULT_PROJECTIONS_SORT_COL = "DynastyValue";
const DEFAULT_PROJECTIONS_SORT_DIR = "desc";
const CAREER_TOTALS_FILTER_VALUE = "__career_totals__";
const VERSION_POLL_INTERVAL_MS = 60000;
const PROJECTION_PAGE_CACHE_MAX = 80;
const PROJECTION_SEARCH_DEBOUNCE_MS = 220;
const PROJECTION_INITIAL_FETCH_DELAY_MS = 220;
const CALC_SEARCH_DEBOUNCE_MS = 140;
const SLOT_INPUT_MIN = 0;
const SLOT_INPUT_MAX = 15;
const HITTER_SLOT_FIELDS = [
  { key: "hit_c", label: "C", defaultValue: 1 },
  { key: "hit_1b", label: "1B", defaultValue: 1 },
  { key: "hit_2b", label: "2B", defaultValue: 1 },
  { key: "hit_3b", label: "3B", defaultValue: 1 },
  { key: "hit_ss", label: "SS", defaultValue: 1 },
  { key: "hit_ci", label: "CI", defaultValue: 1 },
  { key: "hit_mi", label: "MI", defaultValue: 1 },
  { key: "hit_of", label: "OF", defaultValue: 5 },
  { key: "hit_ut", label: "UT", defaultValue: 1 },
];
const PITCHER_SLOT_FIELDS = [
  { key: "pit_p", label: "P", defaultValue: 9 },
  { key: "pit_sp", label: "SP", defaultValue: 0 },
  { key: "pit_rp", label: "RP", defaultValue: 0 },
];
const POINTS_SETUP_SLOT_DEFAULTS = {
  hit_c: 1,
  hit_1b: 1,
  hit_2b: 1,
  hit_3b: 1,
  hit_ss: 1,
  hit_ci: 0,
  hit_mi: 0,
  hit_of: 3,
  hit_ut: 1,
  pit_p: 2,
  pit_sp: 5,
  pit_rp: 2,
};
const POINTS_SCORING_FIELDS = [
  { key: "pts_hit_1b", label: "1B", group: "bat", defaultValue: 1 },
  { key: "pts_hit_2b", label: "2B", group: "bat", defaultValue: 2 },
  { key: "pts_hit_3b", label: "3B", group: "bat", defaultValue: 3 },
  { key: "pts_hit_hr", label: "HR", group: "bat", defaultValue: 4 },
  { key: "pts_hit_r", label: "R", group: "bat", defaultValue: 1 },
  { key: "pts_hit_rbi", label: "RBI", group: "bat", defaultValue: 1 },
  { key: "pts_hit_sb", label: "SB", group: "bat", defaultValue: 1 },
  { key: "pts_hit_bb", label: "BB", group: "bat", defaultValue: 1 },
  { key: "pts_hit_so", label: "SO", group: "bat", defaultValue: -1 },
  { key: "pts_pit_ip", label: "IP", group: "pit", defaultValue: 3 },
  { key: "pts_pit_w", label: "W", group: "pit", defaultValue: 5 },
  { key: "pts_pit_l", label: "L", group: "pit", defaultValue: -5 },
  { key: "pts_pit_k", label: "K", group: "pit", defaultValue: 1 },
  { key: "pts_pit_sv", label: "SV", group: "pit", defaultValue: 5 },
  { key: "pts_pit_svh", label: "SVH", group: "pit", defaultValue: 0 },
  { key: "pts_pit_h", label: "H Allowed", group: "pit", defaultValue: -1 },
  { key: "pts_pit_er", label: "ER", group: "pit", defaultValue: -2 },
  { key: "pts_pit_bb", label: "BB Allowed", group: "pit", defaultValue: -1 },
];
const POINTS_BATTING_FIELDS = POINTS_SCORING_FIELDS.filter(field => field.group === "bat");
const POINTS_PITCHING_FIELDS = POINTS_SCORING_FIELDS.filter(field => field.group === "pit");

function resolveRotoSlotDefaults(meta) {
  const guardrails = meta?.calculator_guardrails || {};
  const defaultHitSlots = guardrails?.default_hitter_slots || {};
  const defaultPitchSlots = guardrails?.default_pitcher_slots || {};
  const resolvedHitSlots = Object.fromEntries(
    HITTER_SLOT_FIELDS.map(slot => {
      const value = Number(defaultHitSlots[slot.label]);
      return [slot.key, Number.isInteger(value) && value >= SLOT_INPUT_MIN ? value : slot.defaultValue];
    })
  );
  const resolvedPitchSlots = Object.fromEntries(
    PITCHER_SLOT_FIELDS.map(slot => {
      const value = Number(defaultPitchSlots[slot.label]);
      return [slot.key, Number.isInteger(value) && value >= SLOT_INPUT_MIN ? value : slot.defaultValue];
    })
  );
  return { ...resolvedHitSlots, ...resolvedPitchSlots };
}

function resolvePointsSlotDefaults(meta) {
  const guardrails = meta?.calculator_guardrails || {};
  const pointsHitDefaults = guardrails?.default_points_hitter_slots || {};
  const pointsPitchDefaults = guardrails?.default_points_pitcher_slots || {};
  const fallback = POINTS_SETUP_SLOT_DEFAULTS;
  const resolvedHitSlots = Object.fromEntries(
    HITTER_SLOT_FIELDS.map(slot => {
      const guardrailValue = Number(pointsHitDefaults[slot.label]);
      const fallbackValue = Number(fallback[slot.key]);
      return [
        slot.key,
        Number.isInteger(guardrailValue) && guardrailValue >= SLOT_INPUT_MIN
          ? guardrailValue
          : Number.isInteger(fallbackValue) && fallbackValue >= SLOT_INPUT_MIN
            ? fallbackValue
            : slot.defaultValue,
      ];
    })
  );
  const resolvedPitchSlots = Object.fromEntries(
    PITCHER_SLOT_FIELDS.map(slot => {
      const guardrailValue = Number(pointsPitchDefaults[slot.label]);
      const fallbackValue = Number(fallback[slot.key]);
      return [
        slot.key,
        Number.isInteger(guardrailValue) && guardrailValue >= SLOT_INPUT_MIN
          ? guardrailValue
          : Number.isInteger(fallbackValue) && fallbackValue >= SLOT_INPUT_MIN
            ? fallbackValue
            : slot.defaultValue,
      ];
    })
  );
  return { ...resolvedHitSlots, ...resolvedPitchSlots };
}

function resolvePointsScoringDefaults(meta) {
  const guardrails = meta?.calculator_guardrails || {};
  const provided = guardrails?.default_points_scoring || {};
  return Object.fromEntries(
    POINTS_SCORING_FIELDS.map(field => {
      const value = Number(provided[field.key]);
      return [field.key, Number.isFinite(value) ? value : field.defaultValue];
    })
  );
}

function buildDefaultCalculatorSettings(meta) {
  const guardrails = meta?.calculator_guardrails || {};
  const defaultIr = Number(guardrails?.default_ir_slots);
  const defaultMinors = Number(guardrails?.default_minors_slots);
  return {
    scoring_mode: "roto",
    teams: 12,
    sims: 300,
    horizon: 20,
    discount: 0.94,
    ...resolveRotoSlotDefaults(meta),
    bench: 6,
    minors: Number.isInteger(defaultMinors) && defaultMinors >= 0 ? defaultMinors : 0,
    ir: Number.isInteger(defaultIr) && defaultIr >= 0 ? defaultIr : 0,
    ip_min: 0,
    ip_max: "",
    two_way: "sum",
    start_year: Number(meta?.years?.[0] ?? 2026),
    recent_projections: 3,
    ...resolvePointsScoringDefaults(meta),
  };
}

function formatApiError(status, payload, rawText = "") {
  const detail = payload && payload.detail;
  if (typeof detail === "string" && detail.trim()) {
    return `Server error ${status}: ${detail}`;
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (first && typeof first.msg === "string") {
      return `Validation error (${status}): ${first.msg}`;
    }
  }
  const compactText = String(rawText || "").replace(/\s+/g, " ").trim();
  if (compactText && !compactText.startsWith("<")) {
    return `Server error ${status}: ${compactText.slice(0, 180)}`;
  }
  return `Server error: ${status}`;
}

async function readResponsePayload(response) {
  const rawText = await response.text();
  if (!rawText) return { payload: null, rawText: "" };
  try {
    return { payload: JSON.parse(rawText), rawText };
  } catch (_err) {
    return { payload: null, rawText };
  }
}

function sleepWithAbort(ms, signal) {
  return new Promise((resolve, reject) => {
    if (!signal) {
      window.setTimeout(resolve, ms);
      return;
    }
    if (signal.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }

    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);

    const onAbort = () => {
      window.clearTimeout(timer);
      signal.removeEventListener("abort", onAbort);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal.addEventListener("abort", onAbort);
  });
}

function useDebouncedValue(value, delayMs) {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => {
      window.clearTimeout(timer);
    };
  }, [value, delayMs]);

  return debounced;
}

function AccountPanel({
  authEnabled,
  authReady,
  authUser,
  authStatus,
  cloudStatus,
  onSignIn,
  onSignUp,
  onSignOut,
}) {
  const [mode, setMode] = useState("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const statusText = String(authUser ? cloudStatus : authStatus || "").trim();
  const statusLower = statusText.toLowerCase();
  const statusTone = statusLower.includes("error") || statusLower.includes("failed")
    ? "error"
    : statusLower.includes("saved") || statusLower.includes("loaded") || statusLower.includes("enabled") || statusLower.includes("signed in")
      ? "ok"
      : "";

  async function handleSubmit(event) {
    event.preventDefault();
    if (!authEnabled || !authReady || submitting) return;
    const normalizedEmail = String(email || "").trim();
    const normalizedPassword = String(password || "");
    if (!normalizedEmail || !normalizedPassword) return;

    setSubmitting(true);
    try {
      if (mode === "signup") {
        await onSignUp(normalizedEmail, normalizedPassword);
      } else {
        await onSignIn(normalizedEmail, normalizedPassword);
      }
      setPassword("");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSignOut() {
    if (submitting) return;
    setSubmitting(true);
    try {
      await onSignOut();
    } finally {
      setSubmitting(false);
    }
  }

  if (!authEnabled) {
    return (
      <section className="account-card" aria-live="polite">
        <div className="account-head">
          <h3>Account Sync</h3>
        </div>
        <p className="account-note">
          Account login is currently disabled for this deployment. Configure Supabase to enable saved cross-device settings.
        </p>
      </section>
    );
  }

  return (
    <section className="account-card" aria-live="polite">
      <div className="account-head">
        <h3>Account Sync</h3>
        {authUser && <span className="account-user">{authUser.email || "Signed in"}</span>}
      </div>

      {!authReady && (
        <p className="account-note">Checking existing session...</p>
      )}

      {authReady && !authUser && (
        <form className="account-form" onSubmit={handleSubmit}>
          <label className="account-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={event => setEmail(event.target.value)}
              placeholder="you@example.com"
              autoComplete="email"
              required
            />
          </label>
          <label className="account-field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={event => setPassword(event.target.value)}
              placeholder="At least 8 characters"
              autoComplete={mode === "signup" ? "new-password" : "current-password"}
              minLength={8}
              required
            />
          </label>
          <div className="account-actions">
            <button type="submit" className="inline-btn" disabled={submitting}>
              {submitting ? "Working..." : mode === "signup" ? "Create Account" : "Sign In"}
            </button>
            <button
              type="button"
              className="inline-btn"
              onClick={() => setMode(current => (current === "signup" ? "signin" : "signup"))}
              disabled={submitting}
            >
              {mode === "signup" ? "Use Existing Login" : "Create New Login"}
            </button>
          </div>
        </form>
      )}

      {authReady && authUser && (
        <div className="account-actions">
          <button type="button" className="inline-btn" onClick={handleSignOut} disabled={submitting}>
            {submitting ? "Signing Out..." : "Sign Out"}
          </button>
        </div>
      )}

      {statusText && (
        <p className={`account-status ${statusTone}`.trim()}>{statusText}</p>
      )}
    </section>
  );
}

function projectionCacheGet(cacheMapRef, cacheOrderRef, cacheKey) {
  const cached = cacheMapRef.current.get(cacheKey);
  if (!cached) return null;

  const idx = cacheOrderRef.current.indexOf(cacheKey);
  if (idx !== -1) {
    cacheOrderRef.current.splice(idx, 1);
  }
  cacheOrderRef.current.push(cacheKey);
  return cached;
}

function projectionCacheSet(cacheMapRef, cacheOrderRef, cacheKey, payload) {
  cacheMapRef.current.set(cacheKey, payload);

  const idx = cacheOrderRef.current.indexOf(cacheKey);
  if (idx !== -1) {
    cacheOrderRef.current.splice(idx, 1);
  }
  cacheOrderRef.current.push(cacheKey);

  while (cacheOrderRef.current.length > PROJECTION_PAGE_CACHE_MAX) {
    const oldest = cacheOrderRef.current.shift();
    if (oldest) {
      cacheMapRef.current.delete(oldest);
    }
  }
}

function buildCalculatorPayload(settings, availableYears, meta) {
  const scoringMode = String(settings.scoring_mode ?? "").trim().toLowerCase() || "roto";
  if (scoringMode !== "roto" && scoringMode !== "points") {
    return { error: "Scoring Mode must be either 'roto' or 'points'." };
  }

  const parsedSlots = {};
  for (const slot of [...HITTER_SLOT_FIELDS, ...PITCHER_SLOT_FIELDS]) {
    const value = Number(settings[slot.key]);
    if (!Number.isInteger(value) || value < SLOT_INPUT_MIN || value > SLOT_INPUT_MAX) {
      return { error: `${slot.label} slots must be an integer between ${SLOT_INPUT_MIN} and ${SLOT_INPUT_MAX}.` };
    }
    parsedSlots[slot.key] = value;
  }

  const hittersPerTeam = HITTER_SLOT_FIELDS.reduce((sum, slot) => sum + parsedSlots[slot.key], 0);
  if (hittersPerTeam <= 0) {
    return { error: "At least one hitter slot must be greater than 0." };
  }

  const pitchersPerTeam = PITCHER_SLOT_FIELDS.reduce((sum, slot) => sum + parsedSlots[slot.key], 0);
  if (pitchersPerTeam <= 0) {
    return { error: "At least one pitcher slot must be greater than 0." };
  }

  const teams = Number(settings.teams);
  if (!Number.isInteger(teams) || teams < 2 || teams > 30) {
    return { error: "Teams must be an integer between 2 and 30." };
  }

  const sims = Number(settings.sims);
  if (!Number.isInteger(sims) || sims < 1 || sims > 5000) {
    return { error: "Simulations must be an integer between 1 and 5000." };
  }

  const horizon = Number(settings.horizon);
  if (!Number.isInteger(horizon) || horizon < 1 || horizon > 20) {
    return { error: "Horizon must be an integer between 1 and 20." };
  }

  const discount = Number(settings.discount);
  if (!Number.isFinite(discount) || discount <= 0 || discount > 1) {
    return { error: "Discount must be a number greater than 0 and up to 1." };
  }

  const bench = Number(settings.bench);
  if (!Number.isInteger(bench) || bench < 0 || bench > 40) {
    return { error: "Bench slots must be an integer between 0 and 40." };
  }

  const minors = Number(settings.minors);
  if (!Number.isInteger(minors) || minors < 0 || minors > 60) {
    return { error: "Minor slots must be an integer between 0 and 60." };
  }

  const ir = Number(settings.ir);
  if (!Number.isInteger(ir) || ir < 0 || ir > 40) {
    return { error: "IR slots must be an integer between 0 and 40." };
  }

  const ipMin = Number(settings.ip_min);
  if (!Number.isFinite(ipMin) || ipMin < 0) {
    return { error: "IP Min must be a non-negative number." };
  }

  const ipMaxText = String(settings.ip_max ?? "").trim();
  let ipMax = null;
  if (ipMaxText && ipMaxText.toLowerCase() !== "none") {
    const parsedIpMax = Number(ipMaxText);
    if (!Number.isFinite(parsedIpMax) || parsedIpMax < 0) {
      return { error: "IP Max must be a non-negative number or 'none'." };
    }
    ipMax = parsedIpMax;
  }

  if (ipMax != null && ipMax < ipMin) {
    return { error: "IP Max must be greater than or equal to IP Min." };
  }

  const startYear = Number(settings.start_year);
  if (!Number.isInteger(startYear)) {
    return { error: "Start Year must be an integer." };
  }
  if (Array.isArray(availableYears) && availableYears.length > 0 && !availableYears.includes(startYear)) {
    return { error: "Start Year must match an available projection year." };
  }

  const recentProjections = Number(settings.recent_projections);
  if (!Number.isInteger(recentProjections) || recentProjections < 1 || recentProjections > 10) {
    return { error: "Recent Proj. must be an integer between 1 and 10." };
  }

  const twoWay = String(settings.two_way ?? "").trim().toLowerCase();
  if (twoWay !== "sum" && twoWay !== "max") {
    return { error: "Two-Way mode must be either 'sum' or 'max'." };
  }

  const parsedPointsScoring = {};
  for (const field of POINTS_SCORING_FIELDS) {
    const value = Number(settings[field.key]);
    if (!Number.isFinite(value) || value < -50 || value > 50) {
      return { error: `${field.label} points must be a number between -50 and 50.` };
    }
    parsedPointsScoring[field.key] = value;
  }
  if (scoringMode === "points") {
    const hasNonZeroRule = Object.values(parsedPointsScoring).some(value => Math.abs(value) > 1e-9);
    if (!hasNonZeroRule) {
      return { error: "Points scoring must include at least one non-zero scoring rule." };
    }
  }

  const payload = {
    ...settings,
    teams,
    sims,
    horizon,
    discount,
    ...parsedSlots,
    bench,
    minors,
    ir,
    scoring_mode: scoringMode,
    ip_min: ipMin,
    ip_max: ipMax,
    two_way: twoWay,
    start_year: startYear,
    recent_projections: recentProjections,
    ...parsedPointsScoring,
  };

  const guardrails = meta?.calculator_guardrails || {};
  const playableByYear = guardrails?.playable_by_year;
  if (playableByYear && typeof playableByYear === "object") {
    const pool = playableByYear[String(startYear)] || playableByYear[startYear];
    if (pool && typeof pool === "object") {
      const availableHitters = Number(pool.hitters);
      const availablePitchers = Number(pool.pitchers);
      const requiredHitters = teams * hittersPerTeam;
      const requiredPitchers = teams * pitchersPerTeam;
      const warnings = [];

      if (Number.isFinite(availableHitters) && requiredHitters > availableHitters) {
        warnings.push(
          `Roster likely unfillable for ${startYear}: requires ${requiredHitters} hitters but only ${availableHitters} have projected AB > 0.`
        );
      }
      if (Number.isFinite(availablePitchers) && requiredPitchers > availablePitchers) {
        warnings.push(
          `Roster likely unfillable for ${startYear}: requires ${requiredPitchers} pitchers but only ${availablePitchers} have projected IP > 0.`
        );
      }
      if (warnings.length > 0) {
        return { payload, warning: warnings.join(" ") };
      }
    }
  }

  return { payload };
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------
function App() {
  const [section, setSection] = useState("projections"); // projections | calculator
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState("");
  const [buildLabel, setBuildLabel] = useState("");
  const [dataVersion, setDataVersion] = useState("");
  const [presets, setPresets] = useState(() => readCalculatorPresets());
  const [watchlist, setWatchlist] = useState(() => readPlayerWatchlist());
  const [authReady, setAuthReady] = useState(!AUTH_SYNC_ENABLED);
  const [authUser, setAuthUser] = useState(null);
  const [authStatus, setAuthStatus] = useState("");
  const [cloudStatus, setCloudStatus] = useState("");
  const [cloudReadyForSave, setCloudReadyForSave] = useState(false);
  const presetsRef = useRef(presets);
  const watchlistRef = useRef(watchlist);
  const versionEtagRef = useRef("");

  useEffect(() => {
    presetsRef.current = presets;
  }, [presets]);

  useEffect(() => {
    watchlistRef.current = watchlist;
  }, [watchlist]);

  useEffect(() => {
    writeCalculatorPresets(presets);
  }, [presets]);

  useEffect(() => {
    writePlayerWatchlist(watchlist);
  }, [watchlist]);

  useEffect(() => {
    const controller = new AbortController();
    setMetaError("");
    fetch(`${API}/api/meta`, { signal: controller.signal })
      .then(r => {
        if (!r.ok) throw new Error(`Server returned ${r.status} while loading /api/meta`);
        return r.json();
      })
      .then(res => {
        setMeta(res);
      })
      .catch(err => {
        if (err?.name === "AbortError") return;
        setMetaError(err.message || "Failed to load metadata");
        console.error(err);
      });
    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    let timer = null;
    let activeController = null;

    const scheduleNextPoll = () => {
      if (cancelled) return;
      timer = window.setTimeout(runVersionCheck, VERSION_POLL_INTERVAL_MS);
    };

    const runVersionCheck = async () => {
      if (cancelled) return;
      if (activeController) activeController.abort();
      const controller = new AbortController();
      activeController = controller;
      const headers = { "Cache-Control": "no-cache" };
      if (versionEtagRef.current) {
        headers["If-None-Match"] = versionEtagRef.current;
      }

      try {
        const response = await fetch(`${API}/api/version`, {
          signal: controller.signal,
          cache: "no-store",
          headers,
        });
        if (response.status === 304) return;
        if (!response.ok) throw new Error(`Server returned ${response.status} while loading /api/version`);

        const etag = String(response.headers.get("etag") || "").trim();
        if (etag) {
          versionEtagRef.current = etag;
        }

        const res = await response.json();
        if (cancelled) return;

        const buildId = String(res?.build_id || "").trim();
        const resolvedDataVersion = String(res?.data_version || buildId || "").trim();
        if (resolvedDataVersion) {
          setDataVersion(resolvedDataVersion);
        }
        if (!buildId) return;

        setBuildLabel(buildId.slice(0, 12));

        const previousBuildId = safeReadStorage(BUILD_STORAGE_KEY);
        const url = new URL(window.location.href);
        const urlBuildId = String(url.searchParams.get(BUILD_QUERY_PARAM) || "").trim();

        // If the currently loaded HTML build is stale (or we previously saw a
        // different build), force one cache-busting navigation to the latest build.
        const pageIsStale = Boolean(INDEX_BUILD_ID && INDEX_BUILD_ID !== buildId);
        const seenBuildChange = Boolean(previousBuildId && previousBuildId !== buildId);
        if ((pageIsStale || seenBuildChange) && urlBuildId !== buildId) {
          url.searchParams.set(BUILD_QUERY_PARAM, buildId);
          window.location.replace(url.toString());
          return;
        }

        if (urlBuildId && urlBuildId !== buildId) {
          url.searchParams.set(BUILD_QUERY_PARAM, buildId);
          window.history.replaceState({}, "", url.toString());
        }

        safeWriteStorage(BUILD_STORAGE_KEY, buildId);
      } catch (err) {
        if (err?.name === "AbortError" || cancelled) return;
        console.warn("Version check failed:", err);
      } finally {
        if (activeController === controller) {
          activeController = null;
        }
        scheduleNextPoll();
      }
    };

    runVersionCheck();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
      if (activeController) {
        activeController.abort();
        activeController = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!AUTH_SYNC_ENABLED) return undefined;
    let mounted = true;
    let unsubscribe = null;

    const setupAuth = async () => {
      let client = null;
      try {
        client = await loadSupabaseClient();
      } catch (error) {
        if (!mounted) return;
        setAuthStatus(`Account setup error: ${formatAuthError(error, "Unable to initialize account sync.")}`);
        setAuthReady(true);
        return;
      }

      if (!mounted || !client) {
        if (mounted) setAuthReady(true);
        return;
      }

      const { data: authState } = client.auth.onAuthStateChange((_event, session) => {
        setAuthUser(session?.user || null);
        setCloudReadyForSave(false);
        if (!session?.user) {
          setCloudStatus("");
        }
      });
      unsubscribe = () => authState?.subscription?.unsubscribe();

      const { data, error } = await client.auth.getSession();
      if (!mounted) return;
      if (error) {
        setAuthStatus(`Account setup error: ${formatAuthError(error, "Unable to restore session.")}`);
      } else if (!data?.session) {
        setAuthStatus("Sign in to sync your presets and watchlist across devices.");
      }
      setAuthUser(data?.session?.user || null);
      setAuthReady(true);
    };

    setupAuth().catch(error => {
      if (!mounted) return;
      setAuthStatus(`Account setup error: ${formatAuthError(error, "Unable to initialize account sync.")}`);
      setAuthReady(true);
    });

    return () => {
      mounted = false;
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!AUTH_SYNC_ENABLED || !authReady) return undefined;
    if (!authUser?.id) {
      setCloudReadyForSave(false);
      return undefined;
    }

    let cancelled = false;
    setCloudStatus("Syncing account settings...");
    setCloudReadyForSave(false);

    const loadCloudPreferences = async () => {
      let client = null;
      try {
        client = await loadSupabaseClient();
      } catch (error) {
        if (cancelled) return;
        setCloudStatus(`Cloud sync error: ${formatAuthError(error, "Unable to initialize account settings.")}`);
        return;
      }
      if (!client || cancelled) return;

      const { data, error } = await client
        .from(SUPABASE_PREFS_TABLE)
        .select("preferences")
        .eq("user_id", authUser.id)
        .maybeSingle();

      if (cancelled) return;
      if (error) {
        setCloudStatus(`Cloud sync error: ${formatAuthError(error, "Unable to load account settings.")}`);
        return;
      }

      if (data?.preferences) {
        const normalized = normalizeCloudPreferences(data.preferences);
        setPresets(normalized.calculatorPresets);
        setWatchlist(normalized.playerWatchlist);
        setCloudStatus("Loaded saved account settings.");
        setCloudReadyForSave(true);
        return;
      }

      const seedPayload = buildCloudPreferencesPayload({
        calculatorPresets: presetsRef.current,
        playerWatchlist: watchlistRef.current,
      });

      const { error: upsertError } = await client
        .from(SUPABASE_PREFS_TABLE)
        .upsert(
          {
            user_id: authUser.id,
            preferences: seedPayload,
          },
          { onConflict: "user_id" }
        );

      if (cancelled) return;
      if (upsertError) {
        setCloudStatus(`Cloud sync error: ${formatAuthError(upsertError, "Unable to initialize account settings.")}`);
        return;
      }

      setCloudStatus("Cloud sync enabled.");
      setCloudReadyForSave(true);
    };

    loadCloudPreferences().catch(error => {
      if (cancelled) return;
      setCloudStatus(`Cloud sync error: ${formatAuthError(error, "Unexpected sync failure.")}`);
    });

    return () => {
      cancelled = true;
    };
  }, [authReady, authUser?.id]);

  useEffect(() => {
    if (!AUTH_SYNC_ENABLED || !authUser?.id || !cloudReadyForSave) return undefined;

    const timer = window.setTimeout(async () => {
      let client = null;
      try {
        client = await loadSupabaseClient();
      } catch (error) {
        setCloudStatus(`Cloud save error: ${formatAuthError(error, "Unable to initialize cloud sync.")}`);
        return;
      }
      if (!client) return;

      const payload = buildCloudPreferencesPayload({
        calculatorPresets: presets,
        playerWatchlist: watchlist,
      });
      const { error } = await client
        .from(SUPABASE_PREFS_TABLE)
        .upsert(
          {
            user_id: authUser.id,
            preferences: payload,
          },
          { onConflict: "user_id" }
        );
      if (error) {
        setCloudStatus(`Cloud save error: ${formatAuthError(error, "Unable to save settings.")}`);
        return;
      }
      setCloudStatus("Saved account settings.");
    }, CLOUD_SYNC_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
    };
  }, [authUser?.id, cloudReadyForSave, presets, watchlist]);

  const signIn = useCallback(async (email, password) => {
    if (!AUTH_SYNC_ENABLED) return;
    const normalizedEmail = String(email || "").trim();
    const normalizedPassword = String(password || "");
    if (!normalizedEmail || !normalizedPassword) {
      setAuthStatus("Sign in failed: email and password are required.");
      return;
    }
    setAuthStatus("");
    try {
      const client = await loadSupabaseClient();
      if (!client) return;
      const { error } = await client.auth.signInWithPassword({
        email: normalizedEmail,
        password: normalizedPassword,
      });
      if (error) {
        setAuthStatus(`Sign in failed: ${formatAuthError(error, "Invalid login.")}`);
        return;
      }
      setAuthStatus("Signed in.");
    } catch (error) {
      setAuthStatus(`Sign in failed: ${formatAuthError(error, "Unable to reach account service.")}`);
    }
  }, []);

  const signUp = useCallback(async (email, password) => {
    if (!AUTH_SYNC_ENABLED) return;
    const normalizedEmail = String(email || "").trim();
    const normalizedPassword = String(password || "");
    if (!normalizedEmail || !normalizedPassword) {
      setAuthStatus("Sign up failed: email and password are required.");
      return;
    }
    setAuthStatus("");
    try {
      const client = await loadSupabaseClient();
      if (!client) return;
      const { data, error } = await client.auth.signUp({
        email: normalizedEmail,
        password: normalizedPassword,
      });
      if (error) {
        setAuthStatus(`Sign up failed: ${formatAuthError(error, "Unable to create account.")}`);
        return;
      }
      if (data?.session) {
        setAuthStatus("Account created. You are signed in.");
        return;
      }
      setAuthStatus("Account created. Check your email to confirm your login.");
    } catch (error) {
      setAuthStatus(`Sign up failed: ${formatAuthError(error, "Unable to reach account service.")}`);
    }
  }, []);

  const signOut = useCallback(async () => {
    if (!AUTH_SYNC_ENABLED) return;
    try {
      const client = await loadSupabaseClient();
      if (!client) return;
      const { error } = await client.auth.signOut();
      if (error) {
        setAuthStatus(`Sign out failed: ${formatAuthError(error, "Unable to sign out.")}`);
        return;
      }
      setAuthStatus("Signed out.");
      setCloudStatus("");
    } catch (error) {
      setAuthStatus(`Sign out failed: ${formatAuthError(error, "Unable to reach account service.")}`);
    }
  }, []);

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <header>
        <div className="nav-inner">
          <a
            className="brand"
            href="#"
            onClick={event => {
              event.preventDefault();
              setSection("projections");
            }}
            aria-label="Fantasy Foundry home"
          >
            <span className="brand-mark" aria-hidden="true">
              <img src="/assets/favicon.svg" alt="" />
            </span>
            <span className="brand-text">
              <span className="brand-title">Fantasy Foundry</span>
              <span className="brand-tagline">Dynasty Baseball Intelligence</span>
            </span>
          </a>
          <nav className="primary-nav" aria-label="Primary">
            <div className="primary-nav-scroll">
              {PRIMARY_NAV_ITEMS.map(item => (
                <button
                  key={item.key}
                  type="button"
                  className={`primary-nav-btn ${section === item.key ? "active" : ""}`.trim()}
                  onClick={() => setSection(item.key)}
                  aria-pressed={section === item.key}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </nav>
        </div>
      </header>

      <main id="main-content">
        <div className="hero fade-up">
          <h1>The Only <em>20-Year</em><br/>Dynasty Baseball Projections</h1>
          <p>Comprehensive player projections from 2026 through 2045. Browse the data, configure your league settings, and generate personalized dynasty rankings.</p>
          {meta && (
            <div className="hero-stats fade-up fade-up-2">
              <div className="hero-stat">
                <div className="number">{meta.total_hitters}</div>
                <div className="label">Hitters</div>
              </div>
              <div className="hero-stat">
                <div className="number">{meta.total_pitchers}</div>
                <div className="label">Pitchers</div>
              </div>
              <div className="hero-stat">
                <div className="number">20</div>
                <div className="label">Seasons</div>
              </div>
            </div>
          )}
        </div>

        <div className="container">
          <AccountPanel
            authEnabled={AUTH_SYNC_ENABLED}
            authReady={authReady}
            authUser={authUser}
            authStatus={authStatus}
            cloudStatus={cloudStatus}
            onSignIn={signIn}
            onSignUp={signUp}
            onSignOut={signOut}
          />
          <div className="methodology-card" style={{ marginBottom: "20px" }}>
            <h2 style={{ marginBottom: "10px" }}>Default League Configuration</h2>
            <p>This site defaults to a 12-team, 5x5 roto setup for rankings.</p>
            <p>
              Hitting categories: <code>R</code>, <code>RBI</code>, <code>HR</code>, <code>SB</code>, <code>AVG</code>
              {" · "}
              Pitching categories: <code>W</code>, <code>K</code>, <code>SV</code>, <code>ERA</code>, <code>WHIP</code>.
            </p>
            <p>
              Roster defaults: 22 starters (13 hitters: <code>C, 1B, 2B, 3B, SS, CI, MI, 5 OF, UT</code>; 9 pitchers as <code>9 P</code>),
              plus 6 bench, 0 MiLB, and 0 IL slots.
            </p>
            <p className="methodology-note" style={{ marginBottom: 0 }}>
              Need custom rankings? Open the <strong>Dynasty Calculator</strong> tab and adjust league settings before you run values.
            </p>
            {meta?.projection_freshness && (
              <p className="methodology-note" style={{ marginBottom: 0, marginTop: 10 }}>
                Projection freshness: latest source date{" "}
                <code>{meta.projection_freshness.newest_projection_date || "unknown"}</code>
                {" · "}
                coverage {fmt(meta.projection_freshness.date_coverage_pct, 1)}%
              </p>
            )}
          </div>
          {metaError && (
            <p style={{marginBottom: "16px", color: "var(--red)"}}>
              Unable to load API data. Check that the backend is running and reachable. ({metaError})
            </p>
          )}
          {section === "projections" && meta && (
            <ProjectionsExplorer
              meta={meta}
              dataVersion={dataVersion}
              watchlist={watchlist}
              setWatchlist={setWatchlist}
            />
          )}
          {section === "calculator" && meta && (
            <DynastyCalculator
              meta={meta}
              presets={presets}
              setPresets={setPresets}
              watchlist={watchlist}
              setWatchlist={setWatchlist}
            />
          )}
        </div>

        <section id="methodology" className="methodology-section" aria-labelledby="methodology-heading">
          <div className="methodology-card">
            <h2 id="methodology-heading">Methodology</h2>
            <p>Player values are generated from projection inputs and league settings in three stages:</p>
            <ol>
              <li>
                For each player-year, duplicate rows are collapsed by averaging the most recent projections
                (up to the configured <code>recent_projections</code> count).
              </li>
              <li>
                Projections are translated into category-level impact using your scoring format, roster structure,
                and innings constraints.
              </li>
              <li>
                The backend runs simulation-based valuation to estimate multi-year dynasty value and produces ranked results.
              </li>
            </ol>
            <p className="methodology-note">
              Output is meant as directional guidance. Real outcomes depend on changing roles, health, and league context.
            </p>
          </div>
        </section>
      </main>

      <footer>
        Built for dynasty baseball enthusiasts &middot; Projections updated as-needed &middot;
        <a href="#methodology"> About the methodology</a>
        {buildLabel && <span className="build-id">Build {buildLabel}</span>}
      </footer>
    </>
  );
}


// ---------------------------------------------------------------------------
// Projections Explorer
// ---------------------------------------------------------------------------
function ProjectionsExplorer({ meta, dataVersion, watchlist, setWatchlist }) {
  const [tab, setTab] = useState(DEFAULT_PROJECTIONS_TAB); // all | bat | pitch
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, PROJECTION_SEARCH_DEBOUNCE_MS);
  const [isMobileViewport, setIsMobileViewport] = useState(() => (
    window.matchMedia("(max-width: 768px)").matches
  ));
  const [mobileLayoutMode, setMobileLayoutMode] = useState(() => {
    const saved = String(safeReadStorage(PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY) || "").trim().toLowerCase();
    if (saved === "cards" || saved === "table") return saved;
    return window.matchMedia("(max-width: 768px)").matches ? "cards" : "table";
  });
  const [projectionTableHiddenColsByTab, setProjectionTableHiddenColsByTab] = useState(() => (
    readHiddenColumnOverridesByTab(PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY)
  ));
  const [projectionCardHiddenColsByTab, setProjectionCardHiddenColsByTab] = useState(() => (
    readHiddenColumnOverridesByTab(PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY)
  ));
  const [watchlistOnly, setWatchlistOnly] = useState(false);
  const [compareRowsByKey, setCompareRowsByKey] = useState({});
  const [teamFilter, setTeamFilter] = useState("");
  const [yearFilter, setYearFilter] = useState(CAREER_TOTALS_FILTER_VALUE);
  const [posFilters, setPosFilters] = useState([]);
  const [showPosMenu, setShowPosMenu] = useState(false);
  const posMenuRef = useRef(null);
  const [data, setData] = useState([]);
  const [totalRows, setTotalRows] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [exportError, setExportError] = useState("");
  const [exportingFormat, setExportingFormat] = useState("");
  const [offset, setOffset] = useState(0);
  const [sortCol, setSortCol] = useState(DEFAULT_PROJECTIONS_SORT_COL);
  const [sortDir, setSortDir] = useState(DEFAULT_PROJECTIONS_SORT_DIR);
  const requestSeqRef = useRef(0);
  const abortControllerRef = useRef(null);
  const hasLoadedProjectionPageRef = useRef(false);
  const projectionCacheMapRef = useRef(new Map());
  const projectionCacheOrderRef = useRef([]);
  const projectionTableScrollRef = useRef(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);
  const limit = 100;
  const careerTotalsView = yearFilter === CAREER_TOTALS_FILTER_VALUE;
  const resolvedDataVersion = String(dataVersion || "").trim();
  const watchlistKeysFilter = useMemo(
    () => Object.keys(watchlist).sort().join(","),
    [watchlist]
  );
  const selectedDynastyYears = useMemo(() => {
    if (careerTotalsView) return (meta.years || []).map(String);
    if (yearFilter) return [String(yearFilter)];
    return (meta.years || []).map(String);
  }, [careerTotalsView, meta.years, yearFilter]);

  const updateProjectionHorizontalAffordance = useCallback(() => {
    const el = projectionTableScrollRef.current;
    if (!el || !isMobileViewport) {
      setCanScrollLeft(false);
      setCanScrollRight(false);
      return;
    }
    const maxLeft = Math.max(0, el.scrollWidth - el.clientWidth);
    setCanScrollLeft(el.scrollLeft > 2);
    setCanScrollRight(el.scrollLeft < maxLeft - 2);
  }, [isMobileViewport]);

  const handleProjectionTableScroll = useCallback(() => {
    updateProjectionHorizontalAffordance();
  }, [updateProjectionHorizontalAffordance]);

  const prefetchProjectionPage = useCallback(async (endpointTab, paramsWithoutOffset, nextOffset) => {
    if (nextOffset < 0) return;
    const nextParams = new URLSearchParams(paramsWithoutOffset);
    nextParams.set("offset", String(nextOffset));
    const nextCacheKey = `${resolvedDataVersion}:${endpointTab}?${nextParams.toString()}`;
    if (projectionCacheMapRef.current.has(nextCacheKey)) return;

    try {
      const response = await fetch(`${API}/api/projections/${endpointTab}?${nextParams}`, {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });
      if (!response.ok) return;
      const payload = await response.json();
      const pageRows = Array.isArray(payload.data) ? payload.data : [];
      const parsedTotal = Number(payload.total);
      const resolvedTotal = Number.isFinite(parsedTotal) && parsedTotal >= 0 ? parsedTotal : pageRows.length;
      const typeTag = endpointTab === "bat" ? "H" : endpointTab === "pitch" ? "P" : "";
      const rows = typeTag ? pageRows.map(row => ({ ...row, Type: typeTag })) : pageRows;
      projectionCacheSet(
        projectionCacheMapRef,
        projectionCacheOrderRef,
        nextCacheKey,
        { rows, total: resolvedTotal }
      );
    } catch {
      // Prefetch is best-effort only.
    }
  }, [resolvedDataVersion]);

  const fetchData = useCallback(async () => {
    const requestSeq = requestSeqRef.current + 1;
    requestSeqRef.current = requestSeq;
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const baseParams = new URLSearchParams();
    if (debouncedSearch) baseParams.set("player", debouncedSearch);
    if (teamFilter) baseParams.set("team", teamFilter);
    if (watchlistOnly) {
      if (!watchlistKeysFilter) {
        if (abortControllerRef.current === controller) {
          abortControllerRef.current = null;
        }
        hasLoadedProjectionPageRef.current = true;
        setLoading(false);
        setError("");
        setData([]);
        setTotalRows(0);
        return;
      }
      baseParams.set("player_keys", watchlistKeysFilter);
    }
    if (careerTotalsView) {
      baseParams.set("career_totals", "true");
    } else if (yearFilter) {
      baseParams.set("year", yearFilter);
    }
    if (posFilters.length > 0) baseParams.set("pos", posFilters.join(","));
    if (selectedDynastyYears.length > 0) baseParams.set("dynasty_years", selectedDynastyYears.join(","));
    baseParams.set("include_dynasty", "true");

    try {
      const endpointTab = tab === "all" ? "all" : tab;
      const paramsWithoutOffset = new URLSearchParams(baseParams);
      paramsWithoutOffset.set("limit", String(limit));
      paramsWithoutOffset.set("sort_col", sortCol);
      paramsWithoutOffset.set("sort_dir", sortDir);
      const params = new URLSearchParams(paramsWithoutOffset);
      params.set("offset", String(offset));
      const cacheKey = `${resolvedDataVersion}:${endpointTab}?${params.toString()}`;

      const cached = projectionCacheGet(projectionCacheMapRef, projectionCacheOrderRef, cacheKey);
      if (cached) {
        if (requestSeq !== requestSeqRef.current) return;
        hasLoadedProjectionPageRef.current = true;
        setError("");
        setData(Array.isArray(cached.rows) ? cached.rows : []);
        setTotalRows(Number.isFinite(cached.total) ? cached.total : 0);
        setLoading(false);
        if (cached.total > offset + limit) {
          prefetchProjectionPage(endpointTab, paramsWithoutOffset, offset + limit);
        }
        return;
      }

      setLoading(true);
      setError("");

      const response = await fetch(`${API}/api/projections/${endpointTab}?${params}`, {
        signal: controller.signal,
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });
      if (!response.ok) {
        throw new Error(`Server returned ${response.status} while loading projections`);
      }

      const payload = await response.json();
      if (requestSeq !== requestSeqRef.current || controller.signal.aborted) return;

      const pageRows = Array.isArray(payload.data) ? payload.data : [];
      const parsedTotal = Number(payload.total);
      const resolvedTotal = Number.isFinite(parsedTotal) && parsedTotal >= 0 ? parsedTotal : pageRows.length;
      const typeTag = endpointTab === "bat" ? "H" : endpointTab === "pitch" ? "P" : "";
      const rows = typeTag ? pageRows.map(row => ({ ...row, Type: typeTag })) : pageRows;

      if (requestSeq !== requestSeqRef.current || controller.signal.aborted) return;
      projectionCacheSet(
        projectionCacheMapRef,
        projectionCacheOrderRef,
        cacheKey,
        { rows, total: resolvedTotal }
      );
      hasLoadedProjectionPageRef.current = true;
      setData(rows);
      setTotalRows(resolvedTotal);
      setLoading(false);
      if (resolvedTotal > offset + limit) {
        prefetchProjectionPage(endpointTab, paramsWithoutOffset, offset + limit);
      }
    } catch (err) {
      if (requestSeq !== requestSeqRef.current) return;
      if (err?.name === "AbortError") return;
      setLoading(false);
      setError(err.message || "Failed to load projections");
    } finally {
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
      }
    }
  }, [
    tab,
    debouncedSearch,
    teamFilter,
    watchlistOnly,
    watchlistKeysFilter,
    yearFilter,
    posFilters,
    selectedDynastyYears,
    offset,
    sortCol,
    sortDir,
    limit,
    resolvedDataVersion,
    prefetchProjectionPage,
  ]);

  useEffect(() => {
    // Ensure first entry into this view always lands on the combined tab.
    setTab(DEFAULT_PROJECTIONS_TAB);
    setSortCol(DEFAULT_PROJECTIONS_SORT_COL);
    setSortDir(DEFAULT_PROJECTIONS_SORT_DIR);
    setOffset(0);
    setPosFilters([]);
    setShowPosMenu(false);
  }, []);

  useEffect(() => {
    const mediaQuery = window.matchMedia("(max-width: 768px)");
    const onViewportChange = event => {
      setIsMobileViewport(Boolean(event.matches));
    };

    setIsMobileViewport(mediaQuery.matches);
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", onViewportChange);
      return () => mediaQuery.removeEventListener("change", onViewportChange);
    }
    mediaQuery.addListener(onViewportChange);
    return () => mediaQuery.removeListener(onViewportChange);
  }, []);

  useEffect(() => {
    safeWriteStorage(PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY, mobileLayoutMode);
  }, [mobileLayoutMode]);

  useEffect(() => {
    writeHiddenColumnOverridesByTab(PROJECTION_TABLE_HIDDEN_COLS_STORAGE_KEY, projectionTableHiddenColsByTab);
  }, [projectionTableHiddenColsByTab]);

  useEffect(() => {
    writeHiddenColumnOverridesByTab(PROJECTION_CARD_HIDDEN_COLS_STORAGE_KEY, projectionCardHiddenColsByTab);
  }, [projectionCardHiddenColsByTab]);

  useEffect(() => {
    if (watchlistOnly && Object.keys(watchlist).length === 0) {
      setWatchlistOnly(false);
    }
  }, [watchlistOnly, watchlist]);

  useEffect(() => {
    const delayMs = hasLoadedProjectionPageRef.current ? 0 : PROJECTION_INITIAL_FETCH_DELAY_MS;
    const timer = window.setTimeout(fetchData, delayMs);
    return () => {
      window.clearTimeout(timer);
    };
  }, [fetchData]);

  useEffect(() => {
    return () => {
      requestSeqRef.current += 1;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      hasLoadedProjectionPageRef.current = false;
      projectionCacheMapRef.current.clear();
      projectionCacheOrderRef.current = [];
    };
  }, []);

  useEffect(() => {
    projectionCacheMapRef.current.clear();
    projectionCacheOrderRef.current = [];
    hasLoadedProjectionPageRef.current = false;
    setOffset(0);
  }, [resolvedDataVersion]);

  useEffect(() => {
    function handleOutsideClick(event) {
      if (posMenuRef.current && !posMenuRef.current.contains(event.target)) {
        setShowPosMenu(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  useEffect(() => {
    setOffset(0);
  }, [tab, search, teamFilter, watchlistOnly, watchlistKeysFilter, yearFilter, posFilters, sortCol, sortDir]);

  useEffect(() => {
    const availableYears = (meta.years || []).map(String);
    if (availableYears.length === 0) {
      if (yearFilter !== CAREER_TOTALS_FILTER_VALUE) setYearFilter(CAREER_TOTALS_FILTER_VALUE);
      return;
    }
    // Keep career/default and "all years year-by-year" as valid non-year modes.
    if (yearFilter === CAREER_TOTALS_FILTER_VALUE || yearFilter === "") {
      return;
    }
    if (!availableYears.includes(String(yearFilter))) {
      setYearFilter(CAREER_TOTALS_FILTER_VALUE);
    }
  }, [meta.years, yearFilter]);

  const positionOptions = useMemo(() => {
    const rawPositions = tab === "all"
      ? [...(meta.bat_positions || []), ...(meta.pit_positions || [])]
      : tab === "bat"
        ? (meta.bat_positions || [])
        : (meta.pit_positions || []);
    const uniq = new Set();
    rawPositions.forEach(pos => {
      parsePosTokens(pos).forEach(token => uniq.add(token));
    });
    if (tab === "bat") uniq.delete("SP");

    const order = ["C", "1B", "2B", "3B", "SS", "OF", "DH", "UT", "SP", "RP"];
    return Array.from(uniq).sort((a, b) => {
      const ai = order.indexOf(a);
      const bi = order.indexOf(b);
      if (ai !== -1 || bi !== -1) {
        if (ai === -1) return 1;
        if (bi === -1) return -1;
        return ai - bi;
      }
      return a.localeCompare(b);
    });
  }, [tab, meta.bat_positions, meta.pit_positions]);

  const page = data;
  const watchlistCount = Object.keys(watchlist).length;
  const compareRows = useMemo(
    () => Object.values(compareRowsByKey || {}).filter(Boolean),
    [compareRowsByKey]
  );

  function isRowWatched(row) {
    const key = stablePlayerKeyFromRow(row);
    return Boolean(watchlist[key]);
  }

  function toggleRowWatch(row) {
    const nextEntry = playerWatchEntryFromRow(row);
    setWatchlist(current => {
      const next = { ...current };
      if (next[nextEntry.key]) {
        delete next[nextEntry.key];
      } else {
        next[nextEntry.key] = nextEntry;
      }
      return next;
    });
  }

  function removeWatchlistEntry(key) {
    setWatchlist(current => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function clearWatchlist() {
    setWatchlist({});
  }

  function exportWatchlistCsv() {
    const csv = buildWatchlistCsv(watchlist);
    downloadBlob("player-watchlist.csv", csv, "text/csv;charset=utf-8");
  }

  function toggleCompareRow(row) {
    const key = stablePlayerKeyFromRow(row);
    setCompareRowsByKey(current => {
      if (current[key]) {
        const next = { ...current };
        delete next[key];
        return next;
      }
      if (Object.keys(current).length >= MAX_COMPARE_PLAYERS) return current;
      return { ...current, [key]: row };
    });
  }

  function clearCompareRows() {
    setCompareRowsByKey({});
  }

  function removeCompareRow(key) {
    setCompareRowsByKey(current => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function handleSort(col) {
    if (sortCol === col) {
      setSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setSortCol(col);
      setSortDir(col === "Player" || col === "Team" || col === "Pos" || col === "Type" || col === "Year" || col === "Years" ? "asc" : "desc");
    }
  }

  async function exportCurrentProjections(format) {
    const endpointTab = tab === "all" ? "all" : tab;
    const params = new URLSearchParams();
    if (search) params.set("player", search);
    if (teamFilter) params.set("team", teamFilter);
    if (watchlistOnly && watchlistKeysFilter) params.set("player_keys", watchlistKeysFilter);
    if (careerTotalsView) {
      params.set("career_totals", "true");
    } else if (yearFilter) {
      params.set("year", yearFilter);
    }
    if (posFilters.length > 0) params.set("pos", posFilters.join(","));
    if (selectedDynastyYears.length > 0) params.set("dynasty_years", selectedDynastyYears.join(","));
    params.set("include_dynasty", "true");
    params.set("sort_col", sortCol);
    params.set("sort_dir", sortDir);
    params.set("format", format);
    const href = `${API}/api/projections/export/${endpointTab}?${params.toString()}`;

    try {
      setExportingFormat(format);
      setExportError("");
      const response = await fetch(href, {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });
      if (!response.ok) {
        const parsed = await readResponsePayload(response);
        throw new Error(formatApiError(response.status, parsed.payload, parsed.rawText));
      }
      const blob = await response.blob();
      const fallback = `projections-${endpointTab}.${format}`;
      const filename = parseDownloadFilename(response.headers.get("content-disposition"), fallback);
      triggerBlobDownload(filename, blob);
    } catch (err) {
      setExportError(err?.message || "Failed to export projections");
    } finally {
      setExportingFormat("");
    }
  }

  const seasonCol = careerTotalsView ? "Years" : "Year";
  const dynastyYearCols = selectedDynastyYears.map(year => `Value_${year}`);
  const tableColumnCatalog = useMemo(
    () => projectionTableColumnCatalog(tab, seasonCol, dynastyYearCols),
    [tab, seasonCol, dynastyYearCols]
  );
  const activeProjectionTableHiddenCols = projectionTableHiddenColsByTab[tab] || {};
  const requiredProjectionTableCols = useMemo(() => new Set(["Player"]), []);
  const isProjectionTableColHidden = useCallback((col, hiddenOverrides = activeProjectionTableHiddenCols) => {
    if (Object.prototype.hasOwnProperty.call(hiddenOverrides, col)) {
      return Boolean(hiddenOverrides[col]);
    }
    return projectionTableColumnHiddenByDefault(tab, col);
  }, [tab, activeProjectionTableHiddenCols]);
  const resolvedProjectionTableHiddenCols = useMemo(() => {
    const hidden = {};
    tableColumnCatalog.forEach(col => {
      if (isProjectionTableColHidden(col)) hidden[col] = true;
    });
    return hidden;
  }, [tableColumnCatalog, isProjectionTableColHidden]);
  const cols = useMemo(
    () => tableColumnCatalog.filter(col => !isProjectionTableColHidden(col)),
    [tableColumnCatalog, isProjectionTableColHidden]
  );

  const cardColumnCatalog = useMemo(
    () => projectionCardColumnCatalog(tab, seasonCol, dynastyYearCols),
    [tab, seasonCol, dynastyYearCols]
  );
  const projectionCardCoreUnionCols = useMemo(() => (
    tab === "bat"
      ? [...PROJECTION_HITTER_CORE_STATS]
      : tab === "pitch"
        ? [...PROJECTION_PITCHER_CORE_STATS]
        : [...PROJECTION_HITTER_CORE_STATS, ...PROJECTION_PITCHER_CORE_STATS]
  ), [tab]);
  const projectionCardCoreUnionSet = useMemo(
    () => new Set(projectionCardCoreUnionCols),
    [projectionCardCoreUnionCols]
  );
  const activeProjectionCardHiddenCols = projectionCardHiddenColsByTab[tab] || {};
  const isProjectionCardOptionalColHidden = useCallback((col, hiddenOverrides = activeProjectionCardHiddenCols) => {
    if (projectionCardCoreUnionSet.has(col)) return false;
    if (Object.prototype.hasOwnProperty.call(hiddenOverrides, col)) {
      return Boolean(hiddenOverrides[col]);
    }
    return true;
  }, [activeProjectionCardHiddenCols, projectionCardCoreUnionSet]);
  const cardOptionalCols = useMemo(
    () => cardColumnCatalog.filter(col => !projectionCardCoreUnionSet.has(col)),
    [cardColumnCatalog, projectionCardCoreUnionSet]
  );
  const visibleCardOptionalCols = useMemo(
    () => cardOptionalCols.filter(col => !isProjectionCardOptionalColHidden(col)),
    [cardOptionalCols, isProjectionCardOptionalColHidden]
  );
  const requiredProjectionCardCols = useMemo(
    () => new Set(projectionCardCoreUnionCols),
    [projectionCardCoreUnionCols]
  );
  const resolvedProjectionCardHiddenCols = useMemo(() => {
    const hidden = {};
    cardColumnCatalog.forEach(col => {
      if (isProjectionCardOptionalColHidden(col)) hidden[col] = true;
    });
    return hidden;
  }, [cardColumnCatalog, isProjectionCardOptionalColHidden]);
  const projectionCardCoreColumnsForRow = useCallback(row => {
    if (tab === "bat") return PROJECTION_HITTER_CORE_STATS;
    if (tab === "pitch") return PROJECTION_PITCHER_CORE_STATS;
    const side = String(row?.Type || "").trim().toUpperCase();
    if (side === "P") return PROJECTION_PITCHER_CORE_STATS;
    if (side === "H") return PROJECTION_HITTER_CORE_STATS;
    return [...PROJECTION_HITTER_CORE_STATS, ...PROJECTION_PITCHER_CORE_STATS];
  }, [tab]);
  const projectionCardColumnsForRow = useCallback(row => (
    uniqueColumnOrder([
      ...projectionCardCoreColumnsForRow(row),
      ...visibleCardOptionalCols,
    ])
  ), [projectionCardCoreColumnsForRow, visibleCardOptionalCols]);

  function setProjectionTableColumnHidden(col, hidden) {
    setProjectionTableHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      const defaultHidden = projectionTableColumnHiddenByDefault(tab, col);
      if (hidden === defaultHidden) {
        delete nextTab[col];
      } else {
        nextTab[col] = hidden;
      }
      next[tab] = nextTab;
      return next;
    });
  }

  function toggleProjectionTableColumn(col) {
    if (requiredProjectionTableCols.has(col)) return;
    const currentlyHidden = isProjectionTableColHidden(col);
    setProjectionTableColumnHidden(col, !currentlyHidden);
  }

  function showAllProjectionTableColumns() {
    setProjectionTableHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      tableColumnCatalog.forEach(col => {
        if (requiredProjectionTableCols.has(col)) return;
        nextTab[col] = false;
      });
      next[tab] = nextTab;
      return next;
    });
  }

  function setProjectionCardOptionalColumnHidden(col, hidden) {
    if (projectionCardCoreUnionSet.has(col)) return;
    setProjectionCardHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      if (hidden) {
        delete nextTab[col];
      } else {
        nextTab[col] = false;
      }
      next[tab] = nextTab;
      return next;
    });
  }

  function toggleProjectionCardColumn(col) {
    if (requiredProjectionCardCols.has(col)) return;
    const currentlyHidden = isProjectionCardOptionalColHidden(col);
    setProjectionCardOptionalColumnHidden(col, !currentlyHidden);
  }

  function showAllProjectionCardColumns() {
    setProjectionCardHiddenColsByTab(current => {
      const next = normalizeHiddenColumnOverridesByTab(current);
      const nextTab = { ...(next[tab] || {}) };
      cardOptionalCols.forEach(col => {
        nextTab[col] = false;
      });
      next[tab] = nextTab;
      return next;
    });
  }

  const colLabels = useMemo(() => {
    const labels = {
      Type: "Side",
      ProjectionsUsed: "Proj Count",
      OldestProjectionDate: "Oldest Proj Date",
      DynastyValue: "Dynasty Value",
      Years: "Years",
      PitH: "P H",
      PitHR: "P HR",
      PitBB: "P BB",
    };
    dynastyYearCols.forEach(col => {
      labels[col] = `${col.replace("Value_", "")} Dyn Value`;
    });
    return labels;
  }, [dynastyYearCols]);
  const threeDecimalCols = new Set(["AVG", "OBP", "OPS"]);
  const twoDecimalCols = new Set(["ERA", "WHIP"]);
  const wholeNumberCols = new Set([
    "AB",
    "R",
    "HR",
    "RBI",
    "SB",
    "IP",
    "W",
    "K",
    "SVH",
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
    "SV",
    "PitH",
    "PitHR",
    "ER",
  ]);
  const intCols = new Set(["Year", "Years", "Age", "ProjectionsUsed"]);
  const posFilterLabel = posFilters.length === 0
    ? "All Positions"
    : posFilters.length <= 2
      ? posFilters.join(", ")
      : `${posFilters.length} Positions`;
  const displayedPage = page;
  const showCards = mobileLayoutMode === "cards";
  const showInitialLoadSkeleton = loading && displayedPage.length === 0;
  const showInlineRefreshError = Boolean(error) && displayedPage.length > 0;
  const searchIsDebouncing = search !== debouncedSearch;
  const freshness = meta?.projection_freshness || {};
  const freshnessLatestDate = String(freshness.newest_projection_date || "").trim();
  const freshnessDatedRows = Number(freshness.rows_with_projection_date);
  const freshnessCoveragePct = Number(freshness.date_coverage_pct);
  const dataVersionShort = resolvedDataVersion ? resolvedDataVersion.slice(0, 8) : "";
  const showMobileSwipeHint = !showCards && isMobileViewport && (canScrollLeft || canScrollRight);
  const swipeHintText = !canScrollLeft && canScrollRight
    ? "Swipe left for more columns →"
    : canScrollLeft && canScrollRight
      ? "← Swipe both directions for more columns →"
      : "← Swipe right to return";
  const comparisonColumns = tab === "bat"
    ? [seasonCol, "DynastyValue", "AB", "R", "HR", "RBI", "SB", "AVG"]
    : tab === "pitch"
      ? [seasonCol, "DynastyValue", "IP", "W", "K", "SV", "ERA", "WHIP"]
      : [seasonCol, "DynastyValue", "AB", "R", "HR", "RBI", "SB", "IP", "W", "K", "SV", "ERA", "WHIP"];

  function togglePosFilter(pos) {
    setPosFilters(curr => (
      curr.includes(pos) ? curr.filter(p => p !== pos) : [...curr, pos]
    ));
  }

  useEffect(() => {
    const onResize = () => updateProjectionHorizontalAffordance();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [updateProjectionHorizontalAffordance]);

  useEffect(() => {
    const raf = window.requestAnimationFrame(() => updateProjectionHorizontalAffordance());
    return () => window.cancelAnimationFrame(raf);
  }, [updateProjectionHorizontalAffordance, cols.length, displayedPage.length, loading, totalRows, tab, offset, mobileLayoutMode]);

  useEffect(() => {
    if (!isMobileViewport) return;
    if (mobileLayoutMode === "cards") {
      setCanScrollLeft(false);
      setCanScrollRight(false);
      return;
    }
    const el = projectionTableScrollRef.current;
    if (!el) return;
    el.scrollLeft = 0;
    updateProjectionHorizontalAffordance();
  }, [tab, mobileLayoutMode, isMobileViewport, updateProjectionHorizontalAffordance]);

  return (
    <div className="fade-up fade-up-1">
      <div className="section-tabs">
        <button className={`section-tab ${tab==="all"?"active":""}`} onClick={() => {setTab(DEFAULT_PROJECTIONS_TAB); setSortCol(DEFAULT_PROJECTIONS_SORT_COL); setSortDir(DEFAULT_PROJECTIONS_SORT_DIR); setOffset(0); setPosFilters([]); setShowPosMenu(false);}} aria-pressed={tab==="all"}>All</button>
        <button className={`section-tab ${tab==="bat"?"active":""}`} onClick={() => {setTab("bat"); setSortCol(DEFAULT_PROJECTIONS_SORT_COL); setSortDir(DEFAULT_PROJECTIONS_SORT_DIR); setOffset(0); setPosFilters([]); setShowPosMenu(false);}} aria-pressed={tab==="bat"}>Hitters</button>
        <button className={`section-tab ${tab==="pitch"?"active":""}`} onClick={() => {setTab("pitch"); setSortCol(DEFAULT_PROJECTIONS_SORT_COL); setSortDir(DEFAULT_PROJECTIONS_SORT_DIR); setOffset(0); setPosFilters([]); setShowPosMenu(false);}} aria-pressed={tab==="pitch"}>Pitchers</button>
      </div>

      <div className="filter-bar">
        <label className="sr-only" htmlFor="projections-search">Search player name</label>
        <input
          id="projections-search"
          type="text"
          placeholder="Search player name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <label className="sr-only" htmlFor="projections-year-filter">Projection year view</label>
        <select id="projections-year-filter" value={yearFilter} onChange={e => setYearFilter(e.target.value)}>
          <option value={CAREER_TOTALS_FILTER_VALUE}>Rest of Career Totals</option>
          <option value="">All Years (Year-by-year)</option>
          {meta.years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
        <label className="sr-only" htmlFor="projections-team-filter">Team filter</label>
        <select id="projections-team-filter" value={teamFilter} onChange={e => setTeamFilter(e.target.value)}>
          <option value="">All Teams</option>
          {meta.teams.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <div className="multi-select" ref={posMenuRef}>
          <button
            type="button"
            className={`multi-select-trigger ${showPosMenu ? "open" : ""}`}
            onClick={() => setShowPosMenu(open => !open)}
            aria-haspopup="listbox"
            aria-expanded={showPosMenu}
            aria-controls="projections-position-menu"
            aria-label="Filter positions"
          >
            <span className="multi-select-label">
              <span>{posFilterLabel}</span>
              <span className="multi-select-chevron">{showPosMenu ? "▲" : "▼"}</span>
            </span>
          </button>
          {showPosMenu && (
            <div id="projections-position-menu" className="multi-select-menu" role="listbox" aria-multiselectable="true">
              <button
                type="button"
                className="multi-select-clear"
                onClick={() => setPosFilters([])}
                disabled={posFilters.length === 0}
              >
                Clear position filters
              </button>
              {positionOptions.map(pos => (
                <label key={pos} className="multi-select-option">
                  <input
                    type="checkbox"
                    checked={posFilters.includes(pos)}
                    onChange={() => togglePosFilter(pos)}
                  />
                  <span>{pos}</span>
                </label>
              ))}
            </div>
          )}
        </div>
        {ColumnChooserControl && (
          <ColumnChooserControl
            buttonLabel="Table Columns"
            columns={tableColumnCatalog}
            hiddenCols={resolvedProjectionTableHiddenCols}
            requiredCols={requiredProjectionTableCols}
            onToggleColumn={toggleProjectionTableColumn}
            onShowAllColumns={showAllProjectionTableColumns}
            columnLabels={colLabels}
          />
        )}
        <span className={`result-count ${loading || searchIsDebouncing ? "loading" : ""}`.trim()} aria-live="polite" aria-atomic="true">
          {watchlistOnly ? `${totalRows.toLocaleString()} watchlist rows` : `${totalRows.toLocaleString()} rows`}
          {searchIsDebouncing ? " · typing..." : loading ? " · refreshing..." : ""}
        </span>
        <button
          type="button"
          className={`inline-btn ${watchlistOnly ? "open" : ""}`.trim()}
          onClick={() => setWatchlistOnly(value => !value)}
          disabled={watchlistCount === 0}
        >
          {watchlistOnly ? "All Players View" : "Watchlist View"}
        </button>
        <button
          type="button"
          className="inline-btn"
          onClick={() => exportCurrentProjections("csv")}
          disabled={Boolean(exportingFormat)}
        >
          {exportingFormat === "csv" ? "Exporting CSV..." : "Export CSV"}
        </button>
        <button
          type="button"
          className="inline-btn"
          onClick={() => exportCurrentProjections("xlsx")}
          disabled={Boolean(exportingFormat)}
        >
          {exportingFormat === "xlsx" ? "Exporting XLSX..." : "Export XLSX"}
        </button>
      </div>
      {exportError && (
        <div className="table-refresh-message error" role="status" aria-live="polite">
          Export failed. {exportError}
        </div>
      )}
      <div className="collection-toolbar" role="group" aria-label="Watchlist and comparison actions">
        <span className="collection-toolbar-label">Watchlist: {watchlistCount}</span>
        <span className="collection-toolbar-label">View: {watchlistOnly ? "Watchlist" : "All Players"}</span>
        <button type="button" className="inline-btn" onClick={exportWatchlistCsv} disabled={watchlistCount === 0}>
          Export Watchlist CSV
        </button>
        <button type="button" className="inline-btn" onClick={clearWatchlist} disabled={watchlistCount === 0}>
          Clear Watchlist
        </button>
        <span className="collection-toolbar-label">Compare: {compareRows.length}/{MAX_COMPARE_PLAYERS}</span>
        <button type="button" className="inline-btn" onClick={clearCompareRows} disabled={compareRows.length === 0}>
          Clear Compare
        </button>
      </div>
      {compareRows.length > 0 && (
        <div className="comparison-panel" role="region" aria-label="Player comparison">
          <div className="comparison-header">
            <strong>Player Comparison</strong>
            <span>{compareRows.length}/{MAX_COMPARE_PLAYERS} selected</span>
          </div>
          <div className="comparison-grid">
            {compareRows.map(row => {
              const compareKey = stablePlayerKeyFromRow(row);
              return (
                <article className="comparison-card" key={compareKey}>
                  <div className="comparison-card-head">
                    <h4>{row.Player || "Player"}</h4>
                    <button type="button" className="inline-btn" onClick={() => removeCompareRow(compareKey)}>Remove</button>
                  </div>
                  <p>{row.Team || "—"} · {row.Pos || "—"}</p>
                  <dl>
                    {comparisonColumns.map(col => (
                      <React.Fragment key={`${compareKey}-${col}`}>
                        <dt>{colLabels[col] || col}</dt>
                        <dd>
                          {(col === "DynastyValue" || col.startsWith("Value_"))
                            ? fmt(row[col], 2)
                            : twoDecimalCols.has(col)
                              ? fmt(row[col], 2)
                              : threeDecimalCols.has(col)
                                ? fmt(row[col], 3)
                                : wholeNumberCols.has(col)
                                  ? fmtInt(row[col], true)
                                  : intCols.has(col)
                                ? fmtInt(row[col], col !== "Year")
                                : (typeof row[col] === "number" ? fmt(row[col]) : (row[col] ?? "—"))}
                        </dd>
                      </React.Fragment>
                    ))}
                  </dl>
                </article>
              );
            })}
          </div>
        </div>
      )}
      {watchlistCount > 0 && (
        <div className="watchlist-panel" role="region" aria-label="Saved watchlist">
          <div className="watchlist-panel-head">
            <strong>Saved Watchlist</strong>
            <span>{watchlistCount} players</span>
          </div>
          <div className="watchlist-chip-grid">
            {Object.values(watchlist)
              .sort((a, b) => String(a.player || "").localeCompare(String(b.player || "")))
              .slice(0, 40)
              .map(entry => (
                <div key={entry.key} className="watchlist-chip">
                  <span>{entry.player}</span>
                  <small>{entry.team || "—"} · {entry.pos || "—"}</small>
                  <button type="button" onClick={() => removeWatchlistEntry(entry.key)} aria-label={`Remove ${entry.player}`}>
                    ×
                  </button>
                </div>
              ))}
          </div>
          {watchlistCount > 40 && <p className="calc-note">Showing first 40 watchlist entries.</p>}
        </div>
      )}
      <div className="data-freshness-banner" role="note">
        Data freshness:{" "}
        {freshnessLatestDate ? `latest source date ${freshnessLatestDate}` : "projection dates unavailable"}
        {Number.isFinite(freshnessDatedRows) && freshnessDatedRows > 0 ? ` · ${freshnessDatedRows.toLocaleString()} dated rows` : ""}
        {Number.isFinite(freshnessCoveragePct) ? ` (${freshnessCoveragePct.toFixed(1)}% coverage)` : ""}
        {dataVersionShort ? ` · Data v${dataVersionShort}` : ""}
        {watchlistOnly ? " · Watchlist query active" : ""}
      </div>
      <div style={{marginBottom: "12px", color: "var(--text-muted)", fontSize: "0.82rem"}}>
        Dynasty Value already combines hitting and pitching contributions for two-way players.
      </div>
      <div className="projection-layout-controls" role="group" aria-label="Projection layout controls">
          <div className="projection-layout-row">
            <span className="label">Layout</span>
            <div className="projection-view-toggle">
              <button
                type="button"
                className={`projection-view-btn ${mobileLayoutMode === "cards" ? "active" : ""}`.trim()}
                onClick={() => setMobileLayoutMode("cards")}
                aria-pressed={mobileLayoutMode === "cards"}
              >
                Cards
              </button>
              <button
                type="button"
                className={`projection-view-btn ${mobileLayoutMode === "table" ? "active" : ""}`.trim()}
                onClick={() => setMobileLayoutMode("table")}
                aria-pressed={mobileLayoutMode === "table"}
              >
                Table
              </button>
            </div>
          </div>
          {mobileLayoutMode === "cards" && ColumnChooserControl && (
            <div className="projection-layout-row">
              <span className="label">Cards</span>
              <ColumnChooserControl
                buttonLabel="Card Stats"
                columns={cardColumnCatalog}
                hiddenCols={resolvedProjectionCardHiddenCols}
                requiredCols={requiredProjectionCardCols}
                onToggleColumn={toggleProjectionCardColumn}
                onShowAllColumns={showAllProjectionCardColumns}
                columnLabels={colLabels}
              />
            </div>
          )}
      </div>
      {showCards && (
        <div className="projection-card-list">
          {showInitialLoadSkeleton ? (
            Array.from({ length: 8 }).map((_, idx) => (
              <div className="projection-card" key={`loading-card-${idx}`}>
                <div className="loading-shimmer" style={{ width: "60%", margin: 0 }} />
                <div className="loading-shimmer" style={{ width: "90%", marginTop: 10 }} />
              </div>
            ))
          ) : error && displayedPage.length === 0 ? (
            <div className="projection-card-empty">Unable to load projections. {error}</div>
          ) : displayedPage.length === 0 ? (
            <div className="projection-card-empty">No results found for this page.</div>
          ) : (
            displayedPage.map((row, idx) => {
              const rowWatch = isRowWatched(row);
              const compareKey = stablePlayerKeyFromRow(row);
              const isCompared = Boolean(compareRowsByKey[compareKey]);
              const cardCols = projectionCardColumnsForRow(row);
              return (
                <article className="projection-card" key={projectionRowKey(row, offset + idx)}>
                  <div className="projection-card-head">
                    <h4>{row.Player || "Player"}</h4>
                    <div className="projection-card-actions">
                      <button
                        type="button"
                        className={`inline-btn ${rowWatch ? "open" : ""}`.trim()}
                        onClick={() => toggleRowWatch(row)}
                      >
                        {rowWatch ? "Tracked" : "Track"}
                      </button>
                      <button
                        type="button"
                        className={`inline-btn ${isCompared ? "open" : ""}`.trim()}
                        onClick={() => toggleCompareRow(row)}
                        disabled={!isCompared && compareRows.length >= MAX_COMPARE_PLAYERS}
                      >
                        {isCompared ? "Compared" : "Compare"}
                      </button>
                    </div>
                  </div>
                  <p className="projection-card-meta">{row.Team || "—"} · {row.Pos || "—"}</p>
                  <dl>
                    {cardCols.map(col => (
                      <div className="projection-card-stat" key={`${projectionRowKey(row, offset + idx)}-${col}`}>
                        <dt>{colLabels[col] || col}</dt>
                        <dd>
                          {(col === "DynastyValue" || col.startsWith("Value_"))
                            ? fmt(row[col], 2)
                            : twoDecimalCols.has(col)
                              ? fmt(row[col], 2)
                              : threeDecimalCols.has(col)
                                ? fmt(row[col], 3)
                                : wholeNumberCols.has(col)
                                  ? fmtInt(row[col], true)
                                  : intCols.has(col)
                                ? fmtInt(row[col], col !== "Year")
                                : (typeof row[col] === "number" ? fmt(row[col]) : (row[col] ?? "—"))}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </article>
              );
            })
          )}
        </div>
      )}
      {showMobileSwipeHint && (
        <div className="table-swipe-hint" role="note">
          {swipeHintText}
        </div>
      )}
      {showInlineRefreshError && (
        <div className="table-refresh-message error" role="status" aria-live="polite">
          Refresh failed. Showing last loaded page. {error}
        </div>
      )}
      {loading && displayedPage.length > 0 && !showInlineRefreshError && (
        <div className="table-refresh-message" role="status" aria-live="polite">
          Refreshing results...
        </div>
      )}

      {(!showCards || totalRows > limit) && (
      <div className="table-wrapper">
        {!showCards && (
          <div className="table-scroll" ref={projectionTableScrollRef} onScroll={handleProjectionTableScroll}>
            <table className="projections-table">
              <thead>
                <tr>
                  <th scope="col" className="index-col" style={{width:40}}>#</th>
                  {cols.map(c => (
                    <th
                      key={c}
                      scope="col"
                      className={`${sortCol === c ? "sorted" : ""}${c === "Player" ? " player-col" : ""}`.trim()}
                      onClick={() => handleSort(c)}
                      onKeyDown={event => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          handleSort(c);
                        }
                      }}
                      tabIndex={0}
                      aria-sort={sortCol === c ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                    >
                      {colLabels[c] || c}
                      {sortCol === c && <span className="sort-arrow">{sortDir === "asc" ? "▲" : "▼"}</span>}
                    </th>
                  ))}
                  <th scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {showInitialLoadSkeleton ? (
                  Array.from({length: 15}).map((_,i) => (
                    <tr key={i}>
                      <td className="index-col"><div className="loading-shimmer" style={{width: 24}}/></td>
                      {cols.map((c,j) => <td key={j}><div className="loading-shimmer" style={{width: c==="Player"?120:50}}/></td>)}
                      <td><div className="loading-shimmer" style={{width: 90}}/></td>
                    </tr>
                  ))
                ) : error && displayedPage.length === 0 ? (
                  <tr>
                    <td colSpan={cols.length + 2} style={{textAlign:"center",padding:"40px",color:"var(--red)"}}>
                      Unable to load projections. {error}
                    </td>
                  </tr>
                ) : displayedPage.length === 0 ? (
                  <tr><td colSpan={cols.length + 2} style={{textAlign:"center",padding:"40px",color:"var(--text-muted)"}}>No results found</td></tr>
                ) : (
                  displayedPage.map((row, i) => {
                    const rowWatch = isRowWatched(row);
                    const compareKey = stablePlayerKeyFromRow(row);
                    const isCompared = Boolean(compareRowsByKey[compareKey]);
                    return (
                      <tr key={projectionRowKey(row, offset + i)}>
                        <td className="num index-col" style={{color:"var(--text-muted)"}}>{offset + i + 1}</td>
                        {cols.map(c => {
                          const val = row[c];
                          if (c === "Player") return <td key={c} className="player-name">{val}</td>;
                          if (c === "Pos") return <td key={c} className="pos">{val}</td>;
                          if (c === "Team") return <td key={c} className="team">{val}</td>;
                          if (c === "DynastyValue" || c.startsWith("Value_")) {
                            if ((val == null || val === "") && c === "DynastyValue" && row.DynastyMatchStatus === "no_unique_match") {
                              return <td key={c} className="num" style={{color:"var(--text-muted)"}}>No unique match</td>;
                            }
                            const n = Number(val);
                            const cls = n > 0 ? "value-positive" : n < 0 ? "value-negative" : "";
                            return <td key={c} className={`num ${cls}`}>{fmt(val, 2)}</td>;
                          }
                          if (twoDecimalCols.has(c)) return <td key={c} className="num">{fmt(val, 2)}</td>;
                          if (threeDecimalCols.has(c)) return <td key={c} className="num">{fmt(val, 3)}</td>;
                          if (wholeNumberCols.has(c)) return <td key={c} className="num">{fmtInt(val, true)}</td>;
                          if (intCols.has(c)) return <td key={c} className="num">{fmtInt(val, c !== "Year")}</td>;
                          if (typeof val === "number") return <td key={c} className="num">{fmt(val)}</td>;
                          return <td key={c}>{val ?? "—"}</td>;
                        })}
                        <td className="row-actions-cell">
                          <button
                            type="button"
                            className={`inline-btn ${rowWatch ? "open" : ""}`.trim()}
                            onClick={() => toggleRowWatch(row)}
                          >
                            {rowWatch ? "Tracked" : "Track"}
                          </button>
                          <button
                            type="button"
                            className={`inline-btn ${isCompared ? "open" : ""}`.trim()}
                            onClick={() => toggleCompareRow(row)}
                            disabled={!isCompared && compareRows.length >= MAX_COMPARE_PLAYERS}
                          >
                            {isCompared ? "Compared" : "Compare"}
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
        {totalRows > limit && (
          <div className="pagination">
            <button disabled={offset === 0 || loading} onClick={() => setOffset(Math.max(0, offset - limit))}>← Previous</button>
            <span className="page-info">
              {totalRows === 0 ? 0 : offset + 1}–{Math.min(offset + limit, totalRows)} of {totalRows}
            </span>
            <button disabled={offset + limit >= totalRows || loading} onClick={() => setOffset(offset + limit)}>Next →</button>
          </div>
        )}
      </div>
      )}
    </div>
  );
}


// ---------------------------------------------------------------------------
// Dynasty Value Calculator
// ---------------------------------------------------------------------------
function DynastyCalculator({ meta, presets, setPresets, watchlist, setWatchlist }) {
  const [settings, setSettings] = useState(() => buildDefaultCalculatorSettings(meta));
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [sortCol, setSortCol] = useState("DynastyValue");
  const [sortDir, setSortDir] = useState("desc");
  const [searchInput, setSearchInput] = useState("");
  const debouncedRankSearch = useDebouncedValue(searchInput, CALC_SEARCH_DEBOUNCE_MS);
  const [posFilter, setPosFilter] = useState("");
  const [presetName, setPresetName] = useState("");
  const [selectedPresetName, setSelectedPresetName] = useState("");
  const [selectedExplainKey, setSelectedExplainKey] = useState("");
  const [selectedExplainYear, setSelectedExplainYear] = useState("");
  const [hiddenRankCols, setHiddenRankCols] = useState({});
  const [pinRankKeyColumns, setPinRankKeyColumns] = useState(true);
  const [rankWatchlistOnly, setRankWatchlistOnly] = useState(false);
  const [rankCompareRowsByKey, setRankCompareRowsByKey] = useState({});
  const calcRequestSeqRef = useRef(0);
  const calcAbortControllerRef = useRef(null);
  const calcActiveJobIdRef = useRef("");
  const rankTableScrollRef = useRef(null);
  const rankScrollRafRef = useRef(0);
  const rankScrollPendingTopRef = useRef(0);
  const [rankScrollTop, setRankScrollTop] = useState(0);
  const [rankViewportHeight, setRankViewportHeight] = useState(480);
  const availableYears = useMemo(
    () => (meta.years || []).map(Number).filter(Number.isFinite),
    [meta.years]
  );
  const rotoSlotDefaults = useMemo(() => resolveRotoSlotDefaults(meta), [meta]);
  const pointsSlotDefaults = useMemo(() => resolvePointsSlotDefaults(meta), [meta]);
  const pointsScoringDefaults = useMemo(() => resolvePointsScoringDefaults(meta), [meta]);
  const validationResult = useMemo(
    () => buildCalculatorPayload(settings, availableYears, meta),
    [settings, availableYears, meta]
  );
  const validationError = validationResult.error || "";
  const validationWarning = validationResult.warning || "";

  useEffect(() => {
    if (availableYears.length === 0) return;
    const currentYear = Number(settings.start_year);
    if (!availableYears.includes(currentYear)) {
      setSettings(prev => ({ ...prev, start_year: availableYears[0] }));
    }
  }, [availableYears, settings.start_year]);

  useEffect(() => {
    if (rankWatchlistOnly && Object.keys(watchlist).length === 0) {
      setRankWatchlistOnly(false);
    }
  }, [rankWatchlistOnly, watchlist]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const encoded = String(params.get(CALC_LINK_QUERY_PARAM) || "").trim();
    if (!encoded) return;
    const parsed = decodeCalculatorSettings(encoded);
    if (!parsed) return;
    setSettings(current => mergeKnownCalculatorSettings(current, parsed));
    setStatus("Loaded calculator settings from share link.");
  }, []);

  useEffect(() => {
    return () => {
      calcRequestSeqRef.current += 1;
      const activeJobId = String(calcActiveJobIdRef.current || "").trim();
      if (activeJobId) {
        void cancelCalculationJob(activeJobId);
        calcActiveJobIdRef.current = "";
      }
      if (calcAbortControllerRef.current) {
        calcAbortControllerRef.current.abort();
        calcAbortControllerRef.current = null;
      }
      if (rankScrollRafRef.current) {
        window.cancelAnimationFrame(rankScrollRafRef.current);
        rankScrollRafRef.current = 0;
      }
    };
  }, []);

  async function cancelCalculationJob(jobId) {
    const normalizedJobId = String(jobId || "").trim();
    if (!normalizedJobId) return;
    try {
      await fetch(`${API}/api/calculate/jobs/${encodeURIComponent(normalizedJobId)}`, {
        method: "DELETE",
      });
    } catch {
      // Best-effort cancel path; ignore network errors.
    }
  }

  function update(key, val) {
    setSettings(s => ({ ...s, [key]: val }));
  }

  function applyScoringSetup(nextMode) {
    setSettings(curr => {
      const slotDefaults = nextMode === "points" ? pointsSlotDefaults : rotoSlotDefaults;
      return {
        ...curr,
        scoring_mode: nextMode,
        ...slotDefaults,
      };
    });
  }

  function resetPointsScoringDefaults() {
    setSettings(curr => ({ ...curr, ...pointsScoringDefaults }));
  }

  function reapplySetupDefaults() {
    setSettings(curr => (
      curr.scoring_mode === "points"
        ? { ...curr, ...pointsSlotDefaults, ...pointsScoringDefaults }
        : { ...curr, ...rotoSlotDefaults }
    ));
  }

  function buildQuickStartSettings(mode) {
    const availableStartYear = availableYears.length > 0
      ? availableYears[0]
      : Number(meta?.years?.[0] ?? 2026);
    const currentStartYear = Number(settings.start_year);
    const startYear = availableYears.includes(currentStartYear) ? currentStartYear : availableStartYear;
    const guardrails = meta?.calculator_guardrails || {};
    const defaultIr = Number(guardrails.default_ir_slots);
    const defaultMinors = Number(guardrails.default_minors_slots);
    const commonBase = {
      ...settings,
      teams: 12,
      horizon: 20,
      discount: 0.94,
      bench: 6,
      minors: Number.isInteger(defaultMinors) && defaultMinors >= 0 ? defaultMinors : 0,
      ir: Number.isInteger(defaultIr) && defaultIr >= 0 ? defaultIr : 0,
      ip_min: 0,
      ip_max: "",
      two_way: "sum",
      start_year: startYear,
      recent_projections: 3,
      sims: 300,
    };

    if (mode === "points") {
      return {
        ...commonBase,
        scoring_mode: "points",
        ...pointsSlotDefaults,
        ...pointsScoringDefaults,
      };
    }

    return {
      ...commonBase,
      scoring_mode: "roto",
      ...rotoSlotDefaults,
    };
  }

  function applyQuickStartAndRun(mode) {
    const nextSettings = buildQuickStartSettings(mode);
    setSettings(nextSettings);
    setSortCol("DynastyValue");
    setSortDir("desc");
    setStatus(`Applied quick start (${mode === "points" ? "12-team points" : "12-team 5x5 roto"}).`);
    run(nextSettings);
  }

  function savePreset() {
    const name = String(presetName || "").trim();
    if (!name) {
      setStatus("Error: Enter a preset name before saving.");
      return;
    }
    setPresets(current => ({ ...current, [name]: settings }));
    setStatus(`Saved preset '${name}'.`);
  }

  function loadPreset(name) {
    const preset = presets[name];
    if (!preset || typeof preset !== "object") {
      setStatus(`Error: Preset '${name}' was not found.`);
      return;
    }
    setSettings(current => mergeKnownCalculatorSettings(current, preset));
    setPresetName(name);
    setSelectedPresetName(name);
    setStatus(`Loaded preset '${name}'.`);
  }

  function deletePreset(name) {
    setPresets(current => {
      const next = { ...current };
      delete next[name];
      return next;
    });
    setSelectedPresetName(current => (current === name ? "" : current));
    setStatus(`Deleted preset '${name}'.`);
  }

  async function copyShareLink() {
    const encoded = encodeCalculatorSettings(settings);
    if (!encoded) {
      setStatus("Error: Unable to encode settings for sharing.");
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set(CALC_LINK_QUERY_PARAM, encoded);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(url.toString());
      } else {
        throw new Error("Clipboard API unavailable");
      }
      setStatus("Copied share link to clipboard.");
      window.history.replaceState({}, "", url.toString());
    } catch {
      window.prompt("Copy calculator link:", url.toString());
      setStatus("Share link is ready.");
    }
  }

  async function exportRankings(format) {
    const payload = buildCalculatorPayload(settings, availableYears, meta);
    if (payload.error || !payload.payload) {
      setStatus(`Error: ${payload.error || "Invalid settings"}`);
      return;
    }

    try {
      setStatus("Preparing export...");
      const response = await fetch(`${API}/api/calculate/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload.payload,
          format,
          include_explanations: format === "xlsx",
        }),
      });
      if (!response.ok) {
        const parsed = await readResponsePayload(response);
        throw new Error(formatApiError(response.status, parsed.payload, parsed.rawText));
      }
      const blob = await response.blob();
      const fallback = `dynasty-rankings.${format}`;
      const filename = parseDownloadFilename(response.headers.get("content-disposition"), fallback);
      triggerBlobDownload(filename, blob);
      setStatus(`Exported ${filename}`);
    } catch (err) {
      setStatus(`Error: ${err.message || "Failed to export rankings"}`);
    }
  }

  function run(runSettings = settings) {
    const normalizedSettings = normalizeCalculatorRunSettingsInput(runSettings, settings);
    const payload = buildCalculatorPayload(normalizedSettings, availableYears, meta);
    if (payload.error || !payload.payload) {
      setStatus(`Error: ${payload.error || "Invalid settings"}`);
      return;
    }

    const requestSeq = calcRequestSeqRef.current + 1;
    calcRequestSeqRef.current = requestSeq;
    const previousJobId = String(calcActiveJobIdRef.current || "").trim();
    if (previousJobId) {
      void cancelCalculationJob(previousJobId);
      calcActiveJobIdRef.current = "";
    }
    if (calcAbortControllerRef.current) {
      calcAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    calcAbortControllerRef.current = controller;
    setLoading(true);
    setStatus("Submitting simulation job...");
    const body = payload.payload;
    const runningStatusLabel = body.scoring_mode === "points"
      ? "Running points valuation..."
      : "Running Monte Carlo simulations...";

    (async () => {
      let jobId = "";
      try {
        const createResp = await fetch(`${API}/api/calculate/jobs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
        const createParsed = await readResponsePayload(createResp);
        if (!createResp.ok) {
          throw new Error(formatApiError(createResp.status, createParsed.payload, createParsed.rawText));
        }
        const initialJobPayload = createParsed.payload && typeof createParsed.payload === "object"
          ? createParsed.payload
          : {};

        jobId = String(createParsed.payload?.job_id || "").trim();
        if (!jobId) {
          throw new Error("Server did not return a calculation job id.");
        }
        calcActiveJobIdRef.current = jobId;

        const timeoutSeconds = Number(meta?.calculator_guardrails?.job_timeout_seconds);
        const maxWaitMs = Number.isFinite(timeoutSeconds) && timeoutSeconds > 0
          ? timeoutSeconds * 1000
          : 10 * 60 * 1000;
        const deadline = Date.now() + maxWaitMs;

        while (true) {
          if (requestSeq !== calcRequestSeqRef.current || controller.signal.aborted) {
            if (jobId) {
              void cancelCalculationJob(jobId);
              if (calcActiveJobIdRef.current === jobId) {
                calcActiveJobIdRef.current = "";
              }
            }
            return;
          }
          if (Date.now() > deadline) {
            throw new Error("Calculation timed out before completion.");
          }

          const elapsedSecondsFromIso = isoText => {
            const parsedMs = Date.parse(String(isoText || ""));
            if (!Number.isFinite(parsedMs)) return null;
            return Math.max(0, Math.round((Date.now() - parsedMs) / 1000));
          };

          const statusResp = await fetch(`${API}/api/calculate/jobs/${encodeURIComponent(jobId)}`, {
            signal: controller.signal,
          });
          const statusParsed = await readResponsePayload(statusResp);
          if (!statusResp.ok) {
            throw new Error(formatApiError(statusResp.status, statusParsed.payload, statusParsed.rawText));
          }

          const jobStatus = String(statusParsed.payload?.status || "").toLowerCase();
          if (jobStatus === "queued") {
            const queuePosition = Number(statusParsed.payload?.queue_position);
            const queuedJobs = Number(statusParsed.payload?.queued_jobs);
            const queueLabel = Number.isFinite(queuePosition) && queuePosition > 0
              ? `queue ${queuePosition}${Number.isFinite(queuedJobs) && queuedJobs > 0 ? `/${queuedJobs}` : ""}`
              : "queued";
            const queueElapsed = elapsedSecondsFromIso(
              statusParsed.payload?.created_at || initialJobPayload.created_at
            );
            setStatus(
              `${runningStatusLabel} (${queueLabel}${queueElapsed != null ? ` · ${queueElapsed}s` : ""})`
            );
            await sleepWithAbort(1200, controller.signal);
            continue;
          }
          if (jobStatus === "running") {
            const runningElapsed = elapsedSecondsFromIso(
              statusParsed.payload?.started_at ||
              statusParsed.payload?.created_at ||
              initialJobPayload.created_at
            );
            setStatus(
              `${runningStatusLabel}${runningElapsed != null ? ` (${runningElapsed}s elapsed)` : ""}`
            );
            await sleepWithAbort(1200, controller.signal);
            continue;
          }
          if (jobStatus === "completed") {
            const result = statusParsed.payload?.result;
            if (!result || !Array.isArray(result.data)) {
              throw new Error("Calculation completed without a usable result payload.");
            }
            if (requestSeq !== calcRequestSeqRef.current || controller.signal.aborted) return;
            if (calcActiveJobIdRef.current === jobId) {
              calcActiveJobIdRef.current = "";
            }
            setResults(result);
            setLoading(false);
            setStatus(`Done - ${result.total} players ranked`);
            return;
          }
          if (jobStatus === "cancelled" || jobStatus === "canceled") {
            if (calcActiveJobIdRef.current === jobId) {
              calcActiveJobIdRef.current = "";
            }
            setLoading(false);
            setStatus("Calculation cancelled.");
            return;
          }
          if (jobStatus === "failed") {
            const error = statusParsed.payload?.error;
            const detail = typeof error?.detail === "string" ? error.detail : "";
            const errorStatus = Number(error?.status_code);
            if (calcActiveJobIdRef.current === jobId) {
              calcActiveJobIdRef.current = "";
            }
            if (detail && Number.isFinite(errorStatus)) {
              throw new Error(formatApiError(errorStatus, { detail }));
            }
            if (detail) {
              throw new Error(detail);
            }
            throw new Error("Calculation job failed.");
          }

          throw new Error("Unexpected calculation job status.");
        }
      } catch (err) {
        if (jobId) {
          void cancelCalculationJob(jobId);
          if (calcActiveJobIdRef.current === jobId) {
            calcActiveJobIdRef.current = "";
          }
        }
        if (requestSeq !== calcRequestSeqRef.current) return;
        if (err?.name === "AbortError") return;
        setLoading(false);
        setStatus(`Error: ${err.message}`);
      } finally {
        if (calcAbortControllerRef.current === controller) {
          calcAbortControllerRef.current = null;
        }
      }
    })();
  }

  const sortedAll = useMemo(() => {
    if (!results) return [];
    const source = Array.isArray(results.data) ? results.data : [];
    if (!sortCol) return source;
    return [...source].sort((a, b) => {
      let av = a[sortCol], bv = b[sortCol];
      if (sortCol === "Player" || sortCol === "Team" || sortCol === "Pos") {
        const avText = String(av ?? "").trim();
        const bvText = String(bv ?? "").trim();
        if (!avText && !bvText) return 0;
        if (!avText) return 1;
        if (!bvText) return -1;
        return sortDir === "asc" ? avText.localeCompare(bvText) : bvText.localeCompare(avText);
      }
      const avNum = Number(av);
      const bvNum = Number(bv);
      const safeAv = Number.isFinite(avNum) ? avNum : -Infinity;
      const safeBv = Number.isFinite(bvNum) ? bvNum : -Infinity;
      return sortDir === "asc" ? safeAv - safeBv : safeBv - safeAv;
    });
  }, [results, sortCol, sortDir]);

  function isRowWatched(row) {
    const key = stablePlayerKeyFromRow(row);
    return Boolean(watchlist[key]);
  }

  const rankedFiltered = useMemo(() => {
    const q = debouncedRankSearch.trim().toLowerCase();
    const posNeedle = posFilter.trim().toUpperCase();
    return sortedAll
      .map((row, idx) => ({ row, rank: idx + 1 }))
      .filter(({ row }) => {
        if (q && !(row.Player || "").toLowerCase().includes(q)) return false;
        if (posNeedle && !(row.Pos || "").toUpperCase().includes(posNeedle)) return false;
        if (rankWatchlistOnly && !isRowWatched(row)) return false;
        return true;
      });
  }, [sortedAll, debouncedRankSearch, posFilter, rankWatchlistOnly, watchlist]);

  function handleSort(col) {
    if (sortCol === col) setSortDir(d => d === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir(col === "Player" || col === "Team" || col === "Pos" ? "asc" : "desc"); }
  }

  function toggleRankColumn(col) {
    if (requiredRankCols.has(col)) return;
    setHiddenRankCols(current => {
      const next = { ...current };
      if (next[col]) delete next[col];
      else next[col] = true;
      return next;
    });
  }

  function showAllRankColumns() {
    setHiddenRankCols({});
  }

  function clearRankFilters() {
    setSearchInput("");
    setPosFilter("");
    setRankWatchlistOnly(false);
  }

  function toggleRowWatch(row) {
    const nextEntry = playerWatchEntryFromRow(row);
    setWatchlist(current => {
      const next = { ...current };
      if (next[nextEntry.key]) {
        delete next[nextEntry.key];
      } else {
        next[nextEntry.key] = nextEntry;
      }
      return next;
    });
  }

  function clearWatchlist() {
    setWatchlist({});
  }

  function exportWatchlistCsv() {
    const csv = buildWatchlistCsv(watchlist);
    downloadBlob("player-watchlist.csv", csv, "text/csv;charset=utf-8");
  }

  function toggleRankCompareRow(row) {
    const key = stablePlayerKeyFromRow(row);
    setRankCompareRowsByKey(current => {
      if (current[key]) {
        const next = { ...current };
        delete next[key];
        return next;
      }
      if (Object.keys(current).length >= MAX_COMPARE_PLAYERS) return current;
      return { ...current, [key]: row };
    });
  }

  function removeRankCompareRow(key) {
    setRankCompareRowsByKey(current => {
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }

  function clearRankCompareRows() {
    setRankCompareRowsByKey({});
  }

  // Determine columns to show
  const baseCols = ["Player", "DynastyValue", "Age", "Team", "Pos"];
  const yearCols = results
    ? Object.keys(results.data[0] || {})
      .filter(c => c.startsWith("Value_"))
      .sort((a, b) => {
        const av = Number(a.replace("Value_", ""));
        const bv = Number(b.replace("Value_", ""));
        if (Number.isFinite(av) && Number.isFinite(bv)) return av - bv;
        return a.localeCompare(b);
      })
    : [];
  const displayCols = [...baseCols, ...yearCols];
  const isPointsMode = settings.scoring_mode === "points";
  const requiredRankCols = useMemo(() => new Set(["Player", "DynastyValue"]), []);
  const visibleRankCols = useMemo(
    () => displayCols.filter(col => !hiddenRankCols[col]),
    [displayCols, hiddenRankCols]
  );
  const virtualRowHeight = 38;
  const virtualOverscan = 8;
  const totalRankRows = rankedFiltered.length;
  const virtualStartIndex = Math.max(0, Math.floor(rankScrollTop / virtualRowHeight) - virtualOverscan);
  const virtualVisibleCount = Math.ceil(rankViewportHeight / virtualRowHeight) + virtualOverscan * 2;
  const virtualEndIndex = Math.min(totalRankRows, virtualStartIndex + virtualVisibleCount);
  const virtualRows = rankedFiltered.slice(virtualStartIndex, virtualEndIndex);
  const virtualTopPad = virtualStartIndex * virtualRowHeight;
  const virtualBottomPad = Math.max(0, (totalRankRows - virtualEndIndex) * virtualRowHeight);
  const explanationMap = useMemo(() => (
    results && results.explanations && typeof results.explanations === "object"
      ? results.explanations
      : {}
  ), [results]);
  const activeExplanation = useMemo(() => {
    if (!selectedExplainKey) return null;
    return explanationMap[selectedExplainKey] || null;
  }, [explanationMap, selectedExplainKey]);
  const hittersPerTeam = useMemo(() => HITTER_SLOT_FIELDS.reduce((sum, slot) => {
    const value = Number(settings[slot.key]);
    return sum + (Number.isFinite(value) ? value : 0);
  }, 0), [settings]);
  const pitchersPerTeam = useMemo(() => PITCHER_SLOT_FIELDS.reduce((sum, slot) => {
    const value = Number(settings[slot.key]);
    return sum + (Number.isFinite(value) ? value : 0);
  }, 0), [settings]);
  const benchPerTeam = Number.isFinite(Number(settings.bench)) ? Number(settings.bench) : 0;
  const minorsPerTeam = Number.isFinite(Number(settings.minors)) ? Number(settings.minors) : 0;
  const reservePerTeam = benchPerTeam + minorsPerTeam;
  const totalPlayersPerTeam = hittersPerTeam + pitchersPerTeam + reservePerTeam;
  const pointRulesCount = POINTS_SCORING_FIELDS.length;
  const watchlistCount = Object.keys(watchlist).length;
  const rankCompareRows = useMemo(
    () => Object.values(rankCompareRowsByKey || {}).filter(Boolean),
    [rankCompareRowsByKey]
  );
  const compareYearCols = yearCols.slice(0, 6);
  const hasRankFilters = Boolean(searchInput.trim() || posFilter.trim() || rankWatchlistOnly);
  const rankSearchIsDebouncing = searchInput !== debouncedRankSearch;
  const statusIsError = Boolean(validationError) || String(status || "").startsWith("Error");

  const handleRankScroll = useCallback(event => {
    rankScrollPendingTopRef.current = event.currentTarget.scrollTop;
    if (rankScrollRafRef.current) return;
    rankScrollRafRef.current = window.requestAnimationFrame(() => {
      rankScrollRafRef.current = 0;
      setRankScrollTop(rankScrollPendingTopRef.current);
    });
  }, []);

  useEffect(() => {
    if (!results || !Array.isArray(results.data) || results.data.length === 0) {
      setSelectedExplainKey("");
      setSelectedExplainYear("");
      return;
    }
    const firstKey = calculationRowExplainKey(results.data[0]);
    setSelectedExplainKey(current => (current && explanationMap[current] ? current : firstKey));
  }, [results, explanationMap]);

  useEffect(() => {
    setSelectedExplainYear("");
  }, [selectedExplainKey]);

  useEffect(() => {
    setRankCompareRowsByKey(current => {
      const byKey = {};
      sortedAll.forEach(row => {
        byKey[stablePlayerKeyFromRow(row)] = row;
      });
      const next = {};
      Object.keys(current).forEach(key => {
        if (byKey[key]) next[key] = byKey[key];
      });
      return next;
    });
  }, [sortedAll]);

  useEffect(() => {
    setHiddenRankCols(current => {
      const next = {};
      displayCols.forEach(col => {
        if (current[col] && !requiredRankCols.has(col)) next[col] = true;
      });
      return next;
    });
  }, [displayCols, requiredRankCols]);

  useEffect(() => {
    const tableEl = rankTableScrollRef.current;
    if (!tableEl) return;
    const measure = () => setRankViewportHeight(Math.max(240, tableEl.clientHeight || 480));
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [results]);

  useEffect(() => {
    const tableEl = rankTableScrollRef.current;
    if (tableEl) tableEl.scrollTop = 0;
    rankScrollPendingTopRef.current = 0;
    setRankScrollTop(0);
  }, [debouncedRankSearch, posFilter, rankWatchlistOnly, sortCol, sortDir, results, visibleRankCols.length]);

  return (
    <div className="fade-up fade-up-1">
      <div className="calc-layout">
        <div className="calc-sidebar">
          <div className="calc-sidebar-header">
            <h3>League Settings</h3>
            <p className="calc-sidebar-intro">Configure format, roster depth, and scoring. Then generate rankings.</p>
          </div>

          <div className="calc-summary-grid">
            <div className="calc-summary-chip">
              <span>Setup</span>
              <strong>{isPointsMode ? "Points Focused" : "Roto Focused"}</strong>
            </div>
            <div className="calc-summary-chip">
              <span>Teams</span>
              <strong>{settings.teams}</strong>
            </div>
            <div className="calc-summary-chip">
              <span>Per-Team Starters</span>
              <strong>{hittersPerTeam} H / {pitchersPerTeam} P</strong>
            </div>
            <div className="calc-summary-chip">
              <span>Total Keeper Depth</span>
              <strong>{totalPlayersPerTeam} slots</strong>
            </div>
          </div>

          <div className="calc-section">
            <p className="calc-section-title">Quick Start</p>
            <p className="calc-note">Apply common league settings and run immediately.</p>
            <div className="calc-inline-actions">
              <button
                type="button"
                className="calc-secondary-btn"
                onClick={() => applyQuickStartAndRun("roto")}
                disabled={loading}
              >
                Run 12-Team 5x5 Roto
              </button>
              <button
                type="button"
                className="calc-secondary-btn"
                onClick={() => applyQuickStartAndRun("points")}
                disabled={loading}
              >
                Run 12-Team Points
              </button>
            </div>
          </div>

          <div className="calc-section">
            <p className="calc-section-title">Format</p>

            <div className="form-row">
              <div className="form-group">
                <label>Teams</label>
                <input type="number" value={settings.teams} onChange={e => update("teams", e.target.value)} min="2" max="30" />
              </div>
              <div className="form-group">
                <label>Start Year</label>
                <select value={settings.start_year} onChange={e => update("start_year", e.target.value)}>
                  {meta.years.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Horizon (yrs)</label>
                <input type="number" value={settings.horizon} onChange={e => update("horizon", e.target.value)} min="1" max="20" />
              </div>
              <div className="form-group">
                <label>
                  Discount
                  <span
                    className="field-help"
                    tabIndex={0}
                    role="note"
                    aria-label="Discount help"
                    title="Applies a yearly value multiplier. Example: 0.94 means each future season is worth 94% of the previous season."
                  >
                    ?
                  </span>
                </label>
                <input type="number" value={settings.discount} onChange={e => update("discount", e.target.value)} min="0.5" max="1" step="0.01" />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>Setup</label>
                <select
                  value={settings.scoring_mode}
                  onChange={e => applyScoringSetup(e.target.value)}
                >
                  <option value="roto">Roto Focused</option>
                  <option value="points">Points Focused</option>
                </select>
              </div>
              <div className="form-group">
                <label>
                  Two-Way Value
                  <span
                    className="field-help"
                    tabIndex={0}
                    role="note"
                    aria-label="Two-Way Value help"
                    title="Sum H + P combines both sides for two-way players. Best of H/P keeps whichever side grades higher."
                  >
                    ?
                  </span>
                </label>
                <select value={settings.two_way} onChange={e => update("two_way", e.target.value)}>
                  <option value="sum">Sum H + P</option>
                  <option value="max">Best of H/P</option>
                </select>
              </div>
            </div>
            <p className="calc-note">Switching setup applies the recommended slot defaults for that format.</p>

            <div className="form-row">
              <div className="form-group">
                <label>Simulations</label>
                <input
                  type="number"
                  value={settings.sims}
                  onChange={e => update("sims", e.target.value)}
                  min="50"
                  max="1000"
                  step="50"
                  disabled={isPointsMode}
                />
              </div>
              <div className="form-group">
                <label>
                  Recent Proj.
                  <span
                    className="field-help"
                    tabIndex={0}
                    role="note"
                    aria-label="Recent projections help"
                    title="Number of newest projection sets averaged per player-year (1-10). Higher values smooth volatility."
                  >
                    ?
                  </span>
                </label>
                <input type="number" value={settings.recent_projections} onChange={e => update("recent_projections", e.target.value)} min="1" max="10" />
              </div>
            </div>
            {isPointsMode && <p className="calc-note">Points mode ignores the simulations setting and scores directly from projected totals.</p>}

            <div className="form-row">
              <div className="form-group">
                <label>IP Min</label>
                <input
                  type="number"
                  value={settings.ip_min}
                  onChange={e => update("ip_min", e.target.value)}
                  min="0"
                  step="100"
                  disabled={isPointsMode}
                />
              </div>
              <div className="form-group">
                <label>IP Max</label>
                <input
                  type="text"
                  value={settings.ip_max}
                  onChange={e => update("ip_max", e.target.value)}
                  placeholder="none"
                  disabled={isPointsMode}
                />
              </div>
            </div>
            {isPointsMode && <p className="calc-note">IP min/max constraints only apply in roto mode.</p>}
          </div>

          <div className="calc-section">
            <p className="calc-section-title">Presets And Sharing</p>
            <div className="form-row">
              <div className="form-group">
                <label>Preset Name</label>
                <input
                  type="text"
                  value={presetName}
                  placeholder="e.g. 12-team H2H Points"
                  onChange={e => setPresetName(e.target.value)}
                />
              </div>
              <div className="form-group">
                <label>Preset Actions</label>
                <button type="button" className="calc-secondary-btn" onClick={savePreset}>
                  Save / Update Preset
                </button>
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label>Saved Presets</label>
                <select
                  value={selectedPresetName}
                  onChange={e => setSelectedPresetName(e.target.value)}
                >
                  <option value="">Select Preset</option>
                  {Object.keys(presets).sort((a, b) => a.localeCompare(b)).map(name => (
                    <option key={name} value={name}>{name}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label>Share</label>
                <button type="button" className="calc-secondary-btn" onClick={copyShareLink}>
                  Copy Share Link
                </button>
              </div>
            </div>
            {selectedPresetName && (
              <div className="calc-inline-actions">
                <button type="button" className="calc-secondary-btn" onClick={() => loadPreset(selectedPresetName)}>
                  Load Selected Preset
                </button>
                <button type="button" className="calc-secondary-btn danger" onClick={() => deletePreset(selectedPresetName)}>
                  Delete Selected Preset
                </button>
              </div>
            )}
          </div>

          <div className="calc-section">
            <p className="calc-section-title">Starter Slots Per Team</p>

            <div className="form-row">
              <div className="form-group">
                <label>C</label>
                <input type="number" value={settings.hit_c} onChange={e => update("hit_c", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
              <div className="form-group">
                <label>1B</label>
                <input type="number" value={settings.hit_1b} onChange={e => update("hit_1b", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>2B</label>
                <input type="number" value={settings.hit_2b} onChange={e => update("hit_2b", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
              <div className="form-group">
                <label>3B</label>
                <input type="number" value={settings.hit_3b} onChange={e => update("hit_3b", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>SS</label>
                <input type="number" value={settings.hit_ss} onChange={e => update("hit_ss", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
              <div className="form-group">
                <label>CI</label>
                <input type="number" value={settings.hit_ci} onChange={e => update("hit_ci", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>MI</label>
                <input type="number" value={settings.hit_mi} onChange={e => update("hit_mi", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
              <div className="form-group">
                <label>OF</label>
                <input type="number" value={settings.hit_of} onChange={e => update("hit_of", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>UT</label>
                <input type="number" value={settings.hit_ut} onChange={e => update("hit_ut", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
              <div className="form-group">
                <label>P</label>
                <input type="number" value={settings.pit_p} onChange={e => update("pit_p", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>SP</label>
                <input type="number" value={settings.pit_sp} onChange={e => update("pit_sp", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
              <div className="form-group">
                <label>RP</label>
                <input type="number" value={settings.pit_rp} onChange={e => update("pit_rp", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
              </div>
            </div>
          </div>

          {isPointsMode && (
            <div className="calc-section">
              <p className="calc-section-title">Points Scoring Rules</p>
              <p className="calc-note">Edit category points below. Defaults align with a common H2H points format ({pointRulesCount} categories).</p>
              <p className="calc-subheading">Batting</p>
              <div className="form-row">
                {POINTS_BATTING_FIELDS.map(field => (
                  <div className="form-group" key={field.key}>
                    <label>{field.label}</label>
                    <input
                      type="number"
                      step="0.1"
                      value={settings[field.key]}
                      onChange={e => update(field.key, e.target.value)}
                    />
                  </div>
                ))}
              </div>

              <p className="calc-subheading">Pitching</p>
              <div className="form-row">
                {POINTS_PITCHING_FIELDS.map(field => (
                  <div className="form-group" key={field.key}>
                    <label>{field.label}</label>
                    <input
                      type="number"
                      step="0.1"
                      value={settings[field.key]}
                      onChange={e => update(field.key, e.target.value)}
                    />
                  </div>
                ))}
              </div>
              <button type="button" className="calc-secondary-btn" onClick={resetPointsScoringDefaults}>
                Reset Recommended Points Scoring
              </button>
            </div>
          )}

          <div className="calc-section">
            <p className="calc-section-title">Depth And Reset</p>
            <div className="form-row">
              <div className="form-group">
                <label>Bench Slots</label>
                <input type="number" value={settings.bench} onChange={e => update("bench", e.target.value)} min="0" max="40" />
              </div>
              <div className="form-group">
                <label>Minor Slots</label>
                <input type="number" value={settings.minors} onChange={e => update("minors", e.target.value)} min="0" max="60" />
              </div>
            </div>

            <div className="form-row">
              <div className="form-group">
                <label>IR Slots</label>
                <input type="number" value={settings.ir} onChange={e => update("ir", e.target.value)} min="0" max="40" />
              </div>
              <div className="form-group">
                <label>Setup Actions</label>
                <button type="button" className="calc-secondary-btn" onClick={reapplySetupDefaults}>
                  {isPointsMode ? "Reset Points + Slot Defaults" : "Reapply Roto Slot Defaults"}
                </button>
              </div>
            </div>
            <p className="calc-note">Reserve depth per team: {reservePerTeam} (bench + minors).</p>
          </div>

          <div className="calc-section">
            <button className="calc-btn" onClick={() => run()} disabled={loading || Boolean(validationError)}>
              {loading ? "Computing..." : "Generate Rankings"}
            </button>
            <div
              className={`calc-status ${loading ? "running" : statusIsError ? "error" : ""}`}
              role={statusIsError ? "alert" : "status"}
              aria-live="polite"
            >
              {loading
                ? status
                : validationError
                  ? `Fix settings: ${validationError}`
                  : status || (validationWarning ? `Warning: ${validationWarning}` : "")}
            </div>
          </div>
        </div>

        <div>
          {results ? (
            <>
              <div className="filter-bar calc-results-toolbar">
                <label className="sr-only" htmlFor="calculator-rank-search">Search ranked players</label>
                <input
                  id="calculator-rank-search"
                  type="text"
                  placeholder="Search ranked players…"
                  value={searchInput}
                  onChange={e => setSearchInput(e.target.value)}
                />
                <label className="sr-only" htmlFor="calculator-rank-pos-filter">Position filter</label>
                <select id="calculator-rank-pos-filter" value={posFilter} onChange={e => setPosFilter(e.target.value)}>
                  <option value="">All Positions</option>
                  {["C","1B","2B","3B","SS","OF","SP","RP"].map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <span className={`result-count ${rankSearchIsDebouncing ? "loading" : ""}`.trim()} aria-live="polite" aria-atomic="true">
                  {rankedFiltered.length.toLocaleString()} / {sortedAll.length.toLocaleString()} players
                  {rankSearchIsDebouncing ? " · filtering..." : ""}
                </span>
                <button type="button" className="inline-btn" onClick={clearRankFilters} disabled={!hasRankFilters}>
                  Reset Filters
                </button>
                <button
                  type="button"
                  className={`inline-btn ${rankWatchlistOnly ? "open" : ""}`.trim()}
                  onClick={() => setRankWatchlistOnly(value => !value)}
                  disabled={watchlistCount === 0}
                >
                  {rankWatchlistOnly ? "All Ranked Players" : "Watchlist Only"}
                </button>
                {ColumnChooserControl && (
                  <ColumnChooserControl
                    columns={displayCols}
                    hiddenCols={hiddenRankCols}
                    requiredCols={requiredRankCols}
                    onToggleColumn={toggleRankColumn}
                    onShowAllColumns={showAllRankColumns}
                  />
                )}
                <button type="button" className="inline-btn" onClick={() => setPinRankKeyColumns(v => !v)}>
                  {pinRankKeyColumns ? "Unpin Key Columns" : "Pin Key Columns"}
                </button>
                <button type="button" className="inline-btn" onClick={exportWatchlistCsv} disabled={watchlistCount === 0}>
                  Export Watchlist CSV
                </button>
                <button type="button" className="inline-btn" onClick={clearWatchlist} disabled={watchlistCount === 0}>
                  Clear Watchlist
                </button>
                <button type="button" className="inline-btn" onClick={clearRankCompareRows} disabled={rankCompareRows.length === 0}>
                  Clear Compare
                </button>
                <button type="button" className="inline-btn" onClick={() => exportRankings("csv")}>Export CSV</button>
                <button type="button" className="inline-btn" onClick={() => exportRankings("xlsx")}>Export XLSX</button>
              </div>
              {rankCompareRows.length > 0 && (
                <div className="comparison-panel" role="region" aria-label="Ranked player comparison">
                  <div className="comparison-header">
                    <strong>Ranked Player Comparison</strong>
                    <span>{rankCompareRows.length}/{MAX_COMPARE_PLAYERS} selected</span>
                  </div>
                  <div className="comparison-grid">
                    {rankCompareRows.map(row => {
                      const key = stablePlayerKeyFromRow(row);
                      return (
                        <article className="comparison-card" key={`rank-compare-${key}`}>
                          <div className="comparison-card-head">
                            <h4>{row.Player || "Player"}</h4>
                            <button type="button" className="inline-btn" onClick={() => removeRankCompareRow(key)}>Remove</button>
                          </div>
                          <p>{row.Team || "—"} · {row.Pos || "—"} · Age {fmt(row.Age, 0)}</p>
                          <dl>
                            <dt>Dynasty Value</dt>
                            <dd>{fmt(row.DynastyValue, 2)}</dd>
                            {compareYearCols.map(col => (
                              <React.Fragment key={`${key}-${col}`}>
                                <dt>{col.replace("Value_", "")}</dt>
                                <dd>{fmt(row[col], 2)}</dd>
                              </React.Fragment>
                            ))}
                          </dl>
                        </article>
                      );
                    })}
                  </div>
                </div>
              )}
              <p className="calc-results-hint">Click or press Enter on a row to inspect its value breakdown.</p>
              <div className="table-wrapper">
                <div
                  className="table-scroll"
                  ref={rankTableScrollRef}
                  onScroll={handleRankScroll}
                >
                  <table className="rankings-table">
                    <thead>
                      <tr>
                        <th scope="col" style={{width:40}} className={pinRankKeyColumns ? "rank-pin-rank" : ""}>#</th>
                        {visibleRankCols.map(c => (
                          <th
                            key={c}
                            scope="col"
                            className={[
                              sortCol === c ? "sorted" : "",
                              c === "Player" ? "player-col" : "",
                              pinRankKeyColumns && c === "Player" ? "rank-pin-player" : "",
                              pinRankKeyColumns && c === "DynastyValue" ? "rank-pin-value" : "",
                            ].join(" ").trim()}
                            onClick={() => handleSort(c)}
                            onKeyDown={event => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                handleSort(c);
                              }
                            }}
                            tabIndex={0}
                            aria-sort={sortCol === c ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
                          >
                            {c.replace("Value_", "")}
                            {sortCol === c && <span className="sort-arrow">{sortDir === "asc" ? "▲" : "▼"}</span>}
                          </th>
                        ))}
                        <th scope="col">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {virtualTopPad > 0 && (
                        <tr aria-hidden="true">
                          <td colSpan={visibleRankCols.length + 2} style={{height: virtualTopPad, padding: 0, border: "none"}} />
                        </tr>
                      )}
                      {virtualRows.map(({ row, rank }, i) => {
                        const explainKey = calculationRowExplainKey(row);
                        const isSelected = selectedExplainKey === explainKey;
                        const watchKey = stablePlayerKeyFromRow(row);
                        const isWatched = Boolean(watchlist[watchKey]);
                        const isCompared = Boolean(rankCompareRowsByKey[watchKey]);
                        return (
                          <tr
                            key={virtualStartIndex + i}
                            className={`clickable-row ${isSelected ? "rank-row-selected" : ""}`.trim()}
                            onClick={() => setSelectedExplainKey(explainKey)}
                            onKeyDown={event => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                setSelectedExplainKey(explainKey);
                              }
                            }}
                            aria-selected={isSelected}
                            tabIndex={0}
                          >
                            <td className={`num ${pinRankKeyColumns ? "rank-pin-rank" : ""}`.trim()} style={{color:"var(--text-muted)"}}>{rank}</td>
                            {visibleRankCols.map(c => {
                              const val = row[c];
                              const pinClass = pinRankKeyColumns && c === "Player"
                                ? "rank-pin-player"
                                : pinRankKeyColumns && c === "DynastyValue"
                                  ? "rank-pin-value"
                                  : "";
                              if (c === "Player") return <td key={c} className={`player-name ${pinClass}`.trim()}>{val}</td>;
                              if (c === "Pos") return <td key={c} className={`pos ${pinClass}`.trim()}>{val}</td>;
                              if (c === "Team") return <td key={c} className={`team ${pinClass}`.trim()}>{val}</td>;
                              if (c === "DynastyValue" || c.startsWith("Value_")) {
                                const n = Number(val);
                                const cls = n > 0 ? "value-positive" : n < 0 ? "value-negative" : "";
                                return <td key={c} className={`num ${cls} ${pinClass}`.trim()}>{fmt(val, 2)}</td>;
                              }
                              if (typeof val === "number") return <td key={c} className={`num ${pinClass}`.trim()}>{fmt(val, Number.isInteger(val) ? 0 : 1)}</td>;
                              return <td key={c} className={pinClass}>{val ?? "—"}</td>;
                            })}
                            <td className="row-actions-cell">
                              <button
                                type="button"
                                className={`inline-btn ${isWatched ? "open" : ""}`.trim()}
                                onClick={event => {
                                  event.stopPropagation();
                                  toggleRowWatch(row);
                                }}
                              >
                                {isWatched ? "Tracked" : "Track"}
                              </button>
                              <button
                                type="button"
                                className={`inline-btn ${isCompared ? "open" : ""}`.trim()}
                                disabled={!isCompared && rankCompareRows.length >= MAX_COMPARE_PLAYERS}
                                onClick={event => {
                                  event.stopPropagation();
                                  toggleRankCompareRow(row);
                                }}
                              >
                                {isCompared ? "Compared" : "Compare"}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                      {virtualBottomPad > 0 && (
                        <tr aria-hidden="true">
                          <td colSpan={visibleRankCols.length + 2} style={{height: virtualBottomPad, padding: 0, border: "none"}} />
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
              {ExplainabilityCard && (
                <ExplainabilityCard
                  explanation={activeExplanation}
                  selectedYear={selectedExplainYear}
                  onSelectedYearChange={setSelectedExplainYear}
                  fmt={fmt}
                />
              )}
            </>
          ) : (
            <div className="calc-empty-state">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 6v6l4 2"/>
              </svg>
              <p>Configure your league settings and click <strong>Generate Rankings</strong></p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


// ---------------------------------------------------------------------------
// Mount
// ---------------------------------------------------------------------------
createRoot(document.getElementById("root")).render(<App />);
