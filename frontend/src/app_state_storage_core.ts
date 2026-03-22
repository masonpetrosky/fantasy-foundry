export interface PlayerWatchEntry {
  key: string;
  player: string;
  team: string;
  pos: string;
}

export interface CalculatorPreset {
  [key: string]: unknown;
}

export interface CloudPreferences {
  calculatorPresets: Record<string, CalculatorPreset>;
  playerWatchlist: Record<string, PlayerWatchEntry>;
}

export interface CloudPreferencesPayload {
  version: number;
  calculator_presets: Record<string, CalculatorPreset>;
  player_watchlist: Record<string, PlayerWatchEntry>;
}

export interface FantraxLeagueState {
  leagueId: string;
  selectedTeamId: string | null;
}

export const CALC_PRESETS_STORAGE_KEY = "ff:calc-presets:v1";
export const PLAYER_WATCHLIST_STORAGE_KEY = "ff:player-watchlist:v1";
export const FANTRAX_LEAGUE_STORAGE_KEY = "ff:fantrax-league:v1";
export const ONBOARDING_DISMISSED_STORAGE_KEY = "ff:onboarding-dismissed:v1";
export const FIRST_RUN_STATE_STORAGE_KEY = "ff:first-run-state:v1";
export const FIRST_RUN_SESSION_LANDING_TS_STORAGE_KEY = "ff:first-run-session-landing-ts:v1";
export const FIRST_RUN_SESSION_SUCCESS_STORAGE_KEY = "ff:first-run-session-success:v1";
export const FIRST_RUN_STATE_NEW = "new";
export const FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS = "dismissed_pre_success";
export const FIRST_RUN_STATE_COMPLETED = "completed";
export const CLOUD_SYNC_DEBOUNCE_MS = 900;
export const CLOUD_PREFERENCES_VERSION = 1;

export function safeReadStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function safeWriteStorage(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignore browsers/storage modes that disallow localStorage writes.
  }
}

export function safeReadSessionStorage(key: string): string | null {
  try {
    if (!window.sessionStorage) return null;
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export function safeWriteSessionStorage(key: string, value: string): void {
  try {
    if (!window.sessionStorage) return;
    window.sessionStorage.setItem(key, value);
  } catch {
    // Ignore browsers/storage modes that disallow sessionStorage writes.
  }
}

export function readBooleanStorage(key: string): boolean | null {
  const raw = String(safeReadStorage(key) || "").trim().toLowerCase();
  if (!raw) return null;
  if (raw === "1" || raw === "true") return true;
  if (raw === "0" || raw === "false") return false;
  return null;
}

export function writeBooleanStorage(key: string, value: boolean): void {
  safeWriteStorage(key, value ? "1" : "0");
}

function writeSessionBooleanStorage(key: string, value: boolean): void {
  safeWriteSessionStorage(key, value ? "1" : "0");
}

function readSessionBooleanStorage(key: string): boolean | null {
  const raw = String(safeReadSessionStorage(key) || "").trim().toLowerCase();
  if (!raw) return null;
  if (raw === "1" || raw === "true") return true;
  if (raw === "0" || raw === "false") return false;
  return null;
}

function normalizeFirstRunState(value: unknown): string {
  const raw = String(value || "").trim().toLowerCase();
  if (raw === FIRST_RUN_STATE_NEW) return FIRST_RUN_STATE_NEW;
  if (raw === FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS) return FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS;
  if (raw === FIRST_RUN_STATE_COMPLETED) return FIRST_RUN_STATE_COMPLETED;
  return "";
}

export function readFirstRunState(): string {
  const storedState = normalizeFirstRunState(safeReadStorage(FIRST_RUN_STATE_STORAGE_KEY));
  if (storedState) return storedState;
  const migratedDismissed = readBooleanStorage(ONBOARDING_DISMISSED_STORAGE_KEY) === true;
  return migratedDismissed ? FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS : FIRST_RUN_STATE_NEW;
}

export function writeFirstRunState(nextState: string): string {
  const normalizedState = normalizeFirstRunState(nextState) || FIRST_RUN_STATE_NEW;
  safeWriteStorage(FIRST_RUN_STATE_STORAGE_KEY, normalizedState);
  writeBooleanStorage(
    ONBOARDING_DISMISSED_STORAGE_KEY,
    normalizedState === FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS
  );
  return normalizedState;
}

export function readSessionFirstRunLandingTimestamp(): number | null {
  const raw = String(safeReadSessionStorage(FIRST_RUN_SESSION_LANDING_TS_STORAGE_KEY) || "").trim();
  if (!raw) return null;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) return null;
  return Math.round(value);
}

export function writeSessionFirstRunLandingTimestamp(timestampMs: number): void {
  const value = Number(timestampMs);
  if (!Number.isFinite(value) || value <= 0) return;
  safeWriteSessionStorage(FIRST_RUN_SESSION_LANDING_TS_STORAGE_KEY, String(Math.round(value)));
}

export function readSessionFirstRunSuccessRecorded(): boolean {
  return readSessionBooleanStorage(FIRST_RUN_SESSION_SUCCESS_STORAGE_KEY) === true;
}

export function writeSessionFirstRunSuccessRecorded(recorded: boolean): void {
  writeSessionBooleanStorage(FIRST_RUN_SESSION_SUCCESS_STORAGE_KEY, Boolean(recorded));
}

export function readOnboardingDismissed(): boolean {
  const explicit = readBooleanStorage(ONBOARDING_DISMISSED_STORAGE_KEY);
  if (explicit != null) return explicit === true;
  return readFirstRunState() === FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS;
}

export function writeOnboardingDismissed(dismissed: boolean): void {
  const isDismissed = Boolean(dismissed);
  writeBooleanStorage(ONBOARDING_DISMISSED_STORAGE_KEY, isDismissed);
  const currentFirstRunState = readFirstRunState();
  if (isDismissed) {
    writeFirstRunState(FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS);
    return;
  }
  if (currentFirstRunState !== FIRST_RUN_STATE_COMPLETED) {
    writeFirstRunState(FIRST_RUN_STATE_NEW);
  }
}

export function normalizeCalculatorPresets(presets: unknown): Record<string, CalculatorPreset> {
  if (!presets || typeof presets !== "object" || Array.isArray(presets)) return {};
  const sanitized: Record<string, CalculatorPreset> = {};
  Object.entries(presets as Record<string, unknown>).forEach(([rawName, rawPreset]) => {
    const name = String(rawName || "").trim();
    if (!name) return;
    if (!rawPreset || typeof rawPreset !== "object" || Array.isArray(rawPreset)) return;
    sanitized[name] = { ...(rawPreset as CalculatorPreset) };
  });
  return sanitized;
}

export function readCalculatorPresets(): Record<string, CalculatorPreset> {
  const raw = safeReadStorage(CALC_PRESETS_STORAGE_KEY);
  if (!raw) return {};
  try {
    return normalizeCalculatorPresets(JSON.parse(raw));
  } catch {
    return {};
  }
}

export function writeCalculatorPresets(presets: unknown): void {
  safeWriteStorage(CALC_PRESETS_STORAGE_KEY, JSON.stringify(normalizeCalculatorPresets(presets)));
}

function stableSerialize(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(entry => stableSerialize(entry)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    const entries = Object.keys(value as Record<string, unknown>)
      .sort((a, b) => a.localeCompare(b))
      .map(key => `${JSON.stringify(key)}:${stableSerialize((value as Record<string, unknown>)[key])}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value);
}

export function calculatorPresetsEqual(left: unknown, right: unknown): boolean {
  const normalizedLeft = normalizeCalculatorPresets(left);
  const normalizedRight = normalizeCalculatorPresets(right);
  const leftKeys = Object.keys(normalizedLeft).sort((a, b) => a.localeCompare(b));
  const rightKeys = Object.keys(normalizedRight).sort((a, b) => a.localeCompare(b));
  if (leftKeys.length !== rightKeys.length) return false;
  for (let i = 0; i < leftKeys.length; i += 1) {
    const leftKey = leftKeys[i];
    const rightKey = rightKeys[i];
    if (leftKey !== rightKey) return false;
    if (stableSerialize(normalizedLeft[leftKey]) !== stableSerialize(normalizedRight[rightKey])) return false;
  }
  return true;
}

export function mergeCalculatorPresetsPreferLocal(
  localPresets: unknown,
  cloudPresets: unknown,
): Record<string, CalculatorPreset> {
  const normalizedLocal = normalizeCalculatorPresets(localPresets);
  const normalizedCloud = normalizeCalculatorPresets(cloudPresets);
  return {
    ...normalizedCloud,
    ...normalizedLocal,
  };
}

export function normalizePlayerWatchlistEntries(rawEntries: unknown): Record<string, PlayerWatchEntry> {
  if (!rawEntries || typeof rawEntries !== "object" || Array.isArray(rawEntries)) return {};
  const entries: Record<string, PlayerWatchEntry> = {};
  Object.entries(rawEntries as Record<string, unknown>).forEach(([rawKey, value]) => {
    const key = String(rawKey || "").trim();
    if (!key) return;
    if (!value || typeof value !== "object") return;
    const v = value as Record<string, unknown>;
    entries[key] = {
      key,
      player: String(v.player || "").trim() || "Unknown Player",
      team: String(v.team || "").trim(),
      pos: String(v.pos || "").trim(),
    };
  });
  return entries;
}

export function readPlayerWatchlist(): Record<string, PlayerWatchEntry> {
  const raw = safeReadStorage(PLAYER_WATCHLIST_STORAGE_KEY);
  if (!raw) return {};
  try {
    return normalizePlayerWatchlistEntries(JSON.parse(raw));
  } catch {
    return {};
  }
}

export function writePlayerWatchlist(watchlist: unknown): void {
  safeWriteStorage(PLAYER_WATCHLIST_STORAGE_KEY, JSON.stringify(normalizePlayerWatchlistEntries(watchlist)));
}

export function normalizeCloudPreferences(rawPreferences: unknown): CloudPreferences {
  if (!rawPreferences || typeof rawPreferences !== "object" || Array.isArray(rawPreferences)) {
    return {
      calculatorPresets: {},
      playerWatchlist: {},
    };
  }
  const rp = rawPreferences as Record<string, unknown>;
  return {
    calculatorPresets: normalizeCalculatorPresets(rp.calculator_presets),
    playerWatchlist: normalizePlayerWatchlistEntries(rp.player_watchlist),
  };
}

export function buildCloudPreferencesPayload({
  calculatorPresets,
  playerWatchlist,
}: CloudPreferences): CloudPreferencesPayload {
  return {
    version: CLOUD_PREFERENCES_VERSION,
    calculator_presets: normalizeCalculatorPresets(calculatorPresets),
    player_watchlist: normalizePlayerWatchlistEntries(playerWatchlist),
  };
}

export function formatAuthError(error: { message?: string } | null | undefined, fallbackMessage: string): string {
  const message = String(error?.message || "").trim();
  return message || fallbackMessage;
}

export function readFantraxLeague(): FantraxLeagueState | null {
  const raw = safeReadStorage(FANTRAX_LEAGUE_STORAGE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const leagueId = String(parsed.leagueId || "").trim();
    if (!leagueId) return null;
    const selectedTeamId = parsed.selectedTeamId ? String(parsed.selectedTeamId).trim() : null;
    return { leagueId, selectedTeamId };
  } catch {
    return null;
  }
}

export function writeFantraxLeague(state: FantraxLeagueState | null): void {
  if (!state) {
    try {
      window.localStorage.removeItem(FANTRAX_LEAGUE_STORAGE_KEY);
    } catch {
      // Ignore browsers/storage modes that disallow localStorage writes.
    }
    return;
  }
  safeWriteStorage(FANTRAX_LEAGUE_STORAGE_KEY, JSON.stringify({
    leagueId: state.leagueId,
    selectedTeamId: state.selectedTeamId,
  }));
}
