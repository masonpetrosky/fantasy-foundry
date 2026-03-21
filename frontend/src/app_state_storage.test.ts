import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildCloudPreferencesPayload,
  buildWatchlistCsv,
  calculationRowExplainKey,
  calculatorPresetsEqual,
  clearLastSuccessfulCalcRun,
  decodeCalculatorSettings,
  encodeCalculatorSettings,
  FIRST_RUN_STATE_COMPLETED,
  FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS,
  FIRST_RUN_STATE_NEW,
  formatAuthError,
  mergeCalculatorPresetsPreferLocal,
  mergeKnownCalculatorSettings,
  normalizeCloudPreferences,
  normalizePlayerKey,
  playerWatchEntryFromRow,
  projectionRowKey,
  readCalculatorPanelOpenPreference,
  readCalculatorPresets,
  readFirstRunState,
  readHiddenColumnOverridesByTab,
  readLastSuccessfulCalcRun,
  readOnboardingDismissed,
  readPlayerWatchlist,
  readProjectionFilterPresets,
  readSessionFirstRunLandingTimestamp,
  readSessionFirstRunSuccessRecorded,
  stablePlayerKeyFromRow,
  writeCalculatorPanelOpenPreference,
  writeCalculatorPresets,
  writeFirstRunState,
  writeHiddenColumnOverridesByTab,
  writeLastSuccessfulCalcRun,
  writeOnboardingDismissed,
  writePlayerWatchlist,
  writeProjectionFilterPresets,
  writeSessionFirstRunLandingTimestamp,
  writeSessionFirstRunSuccessRecorded,
} from "./app_state_storage";

function withStorage(initialValues: Record<string, string> = {}) {
  const store: Record<string, string> = { ...initialValues };
  const sessionStore: Record<string, string> = {};
  vi.stubGlobal("window", {
    localStorage: {
      getItem: vi.fn((key: string) => (Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null)),
      setItem: vi.fn((key: string, value: string) => {
        store[key] = String(value);
      }),
      removeItem: vi.fn((key: string) => {
        delete store[key];
      }),
    },
    sessionStorage: {
      getItem: vi.fn((key: string) => (Object.prototype.hasOwnProperty.call(sessionStore, key) ? sessionStore[key] : null)),
      setItem: vi.fn((key: string, value: string) => {
        sessionStore[key] = String(value);
      }),
      removeItem: vi.fn((key: string) => {
        delete sessionStore[key];
      }),
    },
  });
  return { store, sessionStore };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("mergeCalculatorPresetsPreferLocal", () => {
  it("combines cloud and local presets by name", () => {
    const merged = mergeCalculatorPresetsPreferLocal(
      {
        "Local Keeper": { teams: 16, scoring_mode: "roto" },
      },
      {
        "Cloud Points": { teams: 12, scoring_mode: "points" },
      }
    );

    expect(Object.keys(merged).sort((a, b) => a.localeCompare(b))).toEqual([
      "Cloud Points",
      "Local Keeper",
    ]);
  });

  it("prefers local values when preset names collide", () => {
    const merged = mergeCalculatorPresetsPreferLocal(
      {
        "My League": { teams: 15, discount: 0.9 },
      },
      {
        "My League": { teams: 10, discount: 0.95 },
      }
    );

    expect(merged["My League"]).toEqual({ teams: 15, discount: 0.9 });
  });
});

describe("calculatorPresetsEqual", () => {
  it("returns true for equivalent preset objects", () => {
    expect(calculatorPresetsEqual(
      {
        Alpha: { teams: 12, scoring_mode: "roto" },
      },
      {
        Alpha: { teams: 12, scoring_mode: "roto" },
      }
    )).toBe(true);
  });

  it("returns false when names or values differ", () => {
    expect(calculatorPresetsEqual(
      {
        Alpha: { teams: 12, scoring_mode: "roto" },
      },
      {
        Beta: { teams: 12, scoring_mode: "roto" },
      }
    )).toBe(false);

    expect(calculatorPresetsEqual(
      {
        Alpha: { teams: 12, scoring_mode: "roto" },
      },
      {
        Alpha: { teams: 10, scoring_mode: "roto" },
      }
    )).toBe(false);
  });
});

describe("calculator panel storage", () => {
  it("returns null when no panel preference exists", () => {
    withStorage();
    expect(readCalculatorPanelOpenPreference()).toBeNull();
  });

  it("reads and writes panel open preference", () => {
    const { store } = withStorage({ "ff:calc-panel-open:v1": "0" });
    expect(readCalculatorPanelOpenPreference()).toBe(false);

    writeCalculatorPanelOpenPreference(true);
    expect(store["ff:calc-panel-open:v1"]).toBe("1");
    expect(readCalculatorPanelOpenPreference()).toBe(true);
  });
});

describe("onboarding dismissal storage", () => {
  it("defaults to not dismissed", () => {
    withStorage();
    expect(readOnboardingDismissed()).toBe(false);
  });

  it("persists dismissed state as boolean", () => {
    const { store } = withStorage();
    writeOnboardingDismissed(true);
    expect(store["ff:onboarding-dismissed:v1"]).toBe("1");
    expect(readOnboardingDismissed()).toBe(true);

    writeOnboardingDismissed(false);
    expect(store["ff:onboarding-dismissed:v1"]).toBe("0");
    expect(readOnboardingDismissed()).toBe(false);
  });
});

describe("first-run state storage", () => {
  it("defaults to new and migrates from legacy onboarding dismissal", () => {
    withStorage();
    expect(readFirstRunState()).toBe(FIRST_RUN_STATE_NEW);

    withStorage({ "ff:onboarding-dismissed:v1": "1" });
    expect(readFirstRunState()).toBe(FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS);
  });

  it("persists first-run state values", () => {
    const { store } = withStorage();
    writeFirstRunState(FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS);
    expect(store["ff:first-run-state:v1"]).toBe(FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS);
    expect(store["ff:onboarding-dismissed:v1"]).toBe("1");

    writeFirstRunState(FIRST_RUN_STATE_NEW);
    expect(store["ff:first-run-state:v1"]).toBe(FIRST_RUN_STATE_NEW);
    expect(store["ff:onboarding-dismissed:v1"]).toBe("0");
  });
});

describe("session first-run metrics storage", () => {
  it("stores and reads landing timestamp and first-success flag", () => {
    const { sessionStore } = withStorage();
    writeSessionFirstRunLandingTimestamp(1700001234567);
    writeSessionFirstRunSuccessRecorded(true);

    expect(readSessionFirstRunLandingTimestamp()).toBe(1700001234567);
    expect(readSessionFirstRunSuccessRecorded()).toBe(true);
    expect(sessionStore["ff:first-run-session-landing-ts:v1"]).toBe("1700001234567");
    expect(sessionStore["ff:first-run-session-success:v1"]).toBe("1");
  });
});

describe("last successful calculator run storage", () => {
  it("round-trips a normalized run summary", () => {
    const { store } = withStorage();
    writeLastSuccessfulCalcRun({
      scoringMode: "points",
      teams: "12",
      horizon: "15",
      startYear: "2027",
      playerCount: 381,
      completedAt: "2026-02-25T10:00:00Z",
    });

    expect(store["ff:last-successful-calc-run:v1"]).toBeTruthy();
    expect(readLastSuccessfulCalcRun()).toEqual({
      scoringMode: "points",
      teams: 12,
      horizon: 15,
      startYear: 2027,
      playerCount: 381,
      completedAt: "2026-02-25T10:00:00.000Z",
    });
  });

  it("returns null for invalid payloads", () => {
    withStorage({ "ff:last-successful-calc-run:v1": "{\"teams\":0}" });
    expect(readLastSuccessfulCalcRun()).toBeNull();
  });
});

describe("projection filter preset storage", () => {
  it("stores and loads one normalized custom preset", () => {
    const { store } = withStorage();
    writeProjectionFilterPresets({
      custom: {
        tab: "bat",
        search: "  julio ",
        teamFilter: "SEA",
        yearFilter: "2028",
        posFilters: ["OF", "OF", "DH", ""],
        watchlistOnly: true,
        sortCol: "DynastyValue",
        sortDir: "asc",
      },
    });

    expect(store["ff:proj-filter-presets:v1"]).toBeTruthy();
    expect(readProjectionFilterPresets()).toEqual({
      custom: {
        tab: "bat",
        search: "julio",
        teamFilter: "SEA",
        yearFilter: "2028",
        posFilters: ["OF", "DH"],
        watchlistOnly: true,
        sortCol: "DynastyValue",
        sortDir: "asc",
      },
    });
  });

  it("falls back to null custom preset on malformed storage", () => {
    withStorage({ "ff:proj-filter-presets:v1": "{bad json" });
    expect(readProjectionFilterPresets()).toEqual({ custom: null });
  });
});

describe("clearLastSuccessfulCalcRun", () => {
  it("removes the stored run from localStorage", () => {
    const { store } = withStorage({ "ff:last-successful-calc-run:v1": "{}" });
    clearLastSuccessfulCalcRun();
    expect(Object.prototype.hasOwnProperty.call(store, "ff:last-successful-calc-run:v1")).toBe(false);
  });
});

describe("normalizePlayerKey", () => {
  it("lowercases and strips non-alphanumeric chars to hyphens", () => {
    expect(normalizePlayerKey("Juan Soto")).toBe("juan-soto");
    expect(normalizePlayerKey("Mike Trout")).toBe("mike-trout");
    expect(normalizePlayerKey("  A.J. Pollock  ")).toBe("a-j-pollock");
  });

  it("returns 'unknown-player' for blank input", () => {
    expect(normalizePlayerKey("")).toBe("unknown-player");
    expect(normalizePlayerKey(null)).toBe("unknown-player");
  });
});

describe("calculationRowExplainKey", () => {
  it("prefers PlayerEntityKey, then PlayerKey, then normalizes Player", () => {
    expect(calculationRowExplainKey({ PlayerEntityKey: "soto-ek" })).toBe("soto-ek");
    expect(calculationRowExplainKey({ PlayerKey: "soto-pk" })).toBe("soto-pk");
    expect(calculationRowExplainKey({ Player: "Juan Soto" })).toBe("juan-soto");
  });
});

describe("projectionRowKey", () => {
  it("builds key from entity key when present", () => {
    const row = { PlayerEntityKey: "soto-ek", Year: 2027 };
    const key = projectionRowKey(row, 0);
    expect(key).toContain("soto-ek");
  });

  it("builds composite key when no entity key", () => {
    const row = { Player: "Juan Soto", Team: "NYY", Year: "2027", Type: "H" };
    const key = projectionRowKey(row, 5);
    expect(key).toContain("Juan Soto");
    expect(key).toContain("NYY");
    expect(key).toContain("5");
  });

  it("appends fallback index to pipe-separated composite key for empty rows", () => {
    const key = projectionRowKey({}, 3);
    expect(key).toContain("3");
    expect(key).not.toContain("undefined");
  });
});

describe("stablePlayerKeyFromRow", () => {
  it("uses PlayerEntityKey when available", () => {
    expect(stablePlayerKeyFromRow({ PlayerEntityKey: "ek-1" })).toBe("ek-1");
  });

  it("falls back to PlayerKey, then normalizes Player+Team", () => {
    expect(stablePlayerKeyFromRow({ PlayerKey: "pk-1" })).toBe("pk-1");
    expect(stablePlayerKeyFromRow({ Player: "Juan Soto", Team: "NYY" })).toBe("juan-soto__nyy");
    expect(stablePlayerKeyFromRow({ Player: "Juan Soto" })).toBe("juan-soto");
  });
});

describe("playerWatchEntryFromRow", () => {
  it("builds a normalized watch entry from a row", () => {
    const row = { PlayerEntityKey: "soto-ek", Player: "Juan Soto", Team: "NYY", Pos: "OF" };
    const entry = playerWatchEntryFromRow(row);
    expect(entry.key).toBe("soto-ek");
    expect(entry.player).toBe("Juan Soto");
    expect(entry.team).toBe("NYY");
    expect(entry.pos).toBe("OF");
  });

  it("defaults player to Unknown Player when blank", () => {
    const entry = playerWatchEntryFromRow({});
    expect(entry.player).toBe("Unknown Player");
  });
});

describe("calculator preset storage", () => {
  it("reads empty presets when storage is empty", () => {
    withStorage();
    expect(readCalculatorPresets()).toEqual({});
  });

  it("round-trips a preset object", () => {
    const { store } = withStorage();
    const presets = { "My League": { teams: 14, scoring_mode: "roto" } };
    writeCalculatorPresets(presets);
    expect(store["ff:calc-presets:v1"]).toBeTruthy();
    const loaded = readCalculatorPresets();
    expect(loaded["My League"]).toEqual({ teams: 14, scoring_mode: "roto" });
  });

  it("returns empty object on malformed storage", () => {
    withStorage({ "ff:calc-presets:v1": "{{invalid" });
    expect(readCalculatorPresets()).toEqual({});
  });
});

describe("player watchlist storage", () => {
  it("reads empty watchlist when storage is empty", () => {
    withStorage();
    expect(readPlayerWatchlist()).toEqual({});
  });

  it("round-trips a watchlist object", () => {
    const { store } = withStorage();
    const watchlist = {
      "juan-soto": { key: "juan-soto", player: "Juan Soto", team: "NYY", pos: "OF" },
    };
    writePlayerWatchlist(watchlist);
    expect(store["ff:player-watchlist:v1"]).toBeTruthy();
    const loaded = readPlayerWatchlist();
    expect(loaded["juan-soto"].player).toBe("Juan Soto");
  });

  it("returns empty on malformed storage", () => {
    withStorage({ "ff:player-watchlist:v1": "{bad}" });
    expect(readPlayerWatchlist()).toEqual({});
  });
});

describe("hidden column overrides storage", () => {
  it("returns normalized defaults when nothing stored", () => {
    withStorage();
    const overrides = readHiddenColumnOverridesByTab("ff:proj-table-hidden-cols:v1");
    expect(typeof overrides).toBe("object");
  });

  it("round-trips hidden column data", () => {
    const { store } = withStorage();
    writeHiddenColumnOverridesByTab("ff:proj-table-hidden-cols:v1", { all: ["ERA", "WHIP"] });
    expect(store["ff:proj-table-hidden-cols:v1"]).toBeTruthy();
    const loaded = readHiddenColumnOverridesByTab("ff:proj-table-hidden-cols:v1");
    expect(typeof loaded).toBe("object");
  });
});

describe("normalizeCloudPreferences", () => {
  it("returns empty defaults for null/non-object input", () => {
    expect(normalizeCloudPreferences(null)).toEqual({ calculatorPresets: {}, playerWatchlist: {} });
    expect(normalizeCloudPreferences([])).toEqual({ calculatorPresets: {}, playerWatchlist: {} });
  });

  it("normalizes cloud preferences from raw API response", () => {
    const raw = {
      calculator_presets: { "League": { teams: 12 } },
      player_watchlist: {
        "soto": { key: "soto", player: "Juan Soto", team: "NYY", pos: "OF" },
      },
    };
    const prefs = normalizeCloudPreferences(raw);
    expect(prefs.calculatorPresets["League"]).toBeDefined();
    expect(prefs.playerWatchlist["soto"]).toBeDefined();
  });
});

describe("buildCloudPreferencesPayload", () => {
  it("builds a versioned payload for cloud sync", () => {
    const payload = buildCloudPreferencesPayload({ calculatorPresets: {}, playerWatchlist: {} });
    expect(typeof payload.version).toBe("number");
    expect(payload.calculator_presets).toBeDefined();
    expect(payload.player_watchlist).toBeDefined();
  });
});

describe("formatAuthError", () => {
  it("returns error message when present", () => {
    expect(formatAuthError({ message: "Invalid email" }, "Unknown error")).toBe("Invalid email");
  });

  it("returns fallback when no message", () => {
    expect(formatAuthError({}, "Fallback")).toBe("Fallback");
    expect(formatAuthError(null, "Fallback")).toBe("Fallback");
  });
});

describe("buildWatchlistCsv", () => {
  it("produces a CSV with header and rows sorted by player name", () => {
    const watchlist = {
      "b": { key: "b", player: "Zach Miller", team: "CHC", pos: "C" },
      "a": { key: "a", player: "Aaron Judge", team: "NYY", pos: "OF" },
    };
    const csv = buildWatchlistCsv(watchlist);
    const lines = csv.split("\n");
    expect(lines[0]).toBe("Player,Team,Pos,PlayerKey");
    expect(lines[1]).toContain("Aaron Judge");
    expect(lines[2]).toContain("Zach Miller");
  });

  it("escapes commas and quotes in player names", () => {
    const watchlist = {
      "k": { key: "k", player: 'Smith, Jr. "The Kid"', team: "LAD", pos: "OF" },
    };
    const csv = buildWatchlistCsv(watchlist);
    expect(csv).toContain('"Smith, Jr. ""The Kid"""');
  });

  it("returns just the header for an empty watchlist", () => {
    const csv = buildWatchlistCsv({});
    expect(csv).toBe("Player,Team,Pos,PlayerKey");
  });
});

describe("mergeKnownCalculatorSettings", () => {
  it("only merges keys that exist in baseSettings", () => {
    const base = { teams: 12, horizon: 20 };
    const incoming = { teams: 14, unknown_key: "ignored", horizon: 15 };
    const merged = mergeKnownCalculatorSettings(base, incoming);
    expect(merged.teams).toBe(14);
    expect(merged.horizon).toBe(15);
    expect(merged.unknown_key).toBeUndefined();
  });

  it("returns base unchanged when incoming is null", () => {
    const base = { teams: 12 };
    const merged = mergeKnownCalculatorSettings(base, null);
    expect(merged.teams).toBe(12);
  });

  it("forces mode to common for legacy league presets", () => {
    const base = { mode: "common", teams: 12 };
    const incoming = { mode: "league", teams: 14 };
    const merged = mergeKnownCalculatorSettings(base, incoming);
    expect(merged.mode).toBe("common");
    expect(merged.teams).toBe(14);
  });

  it("retains new slot defaults when older settings omit hit_dh", () => {
    const base = { hit_dh: 0, teams: 12 };
    const incoming = { teams: 14 };
    const merged = mergeKnownCalculatorSettings(base, incoming);
    expect(merged.hit_dh).toBe(0);
    expect(merged.teams).toBe(14);
  });
});

describe("encodeCalculatorSettings / decodeCalculatorSettings", () => {
  it("round-trips settings through encode/decode", () => {
    vi.stubGlobal("window", {
      btoa: (s: string) => globalThis.btoa(s),
      atob: (s: string) => globalThis.atob(s),
    });

    const settings = { teams: 12, horizon: 20, scoring_mode: "roto" };
    const encoded = encodeCalculatorSettings(settings);
    expect(typeof encoded).toBe("string");
    expect(encoded.length).toBeGreaterThan(0);

    const decoded = decodeCalculatorSettings(encoded);
    expect(decoded).toEqual(settings);
  });

  it("returns null for empty or invalid encoded strings", () => {
    vi.stubGlobal("window", {
      atob: () => { throw new Error("invalid"); },
    });
    expect(decodeCalculatorSettings("")).toBeNull();
    expect(decodeCalculatorSettings("!!!invalid!!!")).toBeNull();
  });

  it("returns empty string from encodeCalculatorSettings on failure", () => {
    vi.stubGlobal("window", {
      btoa: () => { throw new Error("fail"); },
    });
    expect(encodeCalculatorSettings({ x: 1 })).toBe("");
  });

  it("round-trips hit_dh for calculator share links", () => {
    vi.stubGlobal("window", {
      btoa: (s: string) => globalThis.btoa(s),
      atob: (s: string) => globalThis.atob(s),
    });

    const settings = { teams: 12, hit_dh: 2, scoring_mode: "roto" };
    const encoded = encodeCalculatorSettings(settings);
    expect(decodeCalculatorSettings(encoded)).toEqual(settings);
  });
});

describe("writeFirstRunState completed state", () => {
  it("persists FIRST_RUN_STATE_COMPLETED without setting dismissed flag", () => {
    const { store } = withStorage();
    writeFirstRunState(FIRST_RUN_STATE_COMPLETED);
    expect(store["ff:first-run-state:v1"]).toBe(FIRST_RUN_STATE_COMPLETED);
    expect(store["ff:onboarding-dismissed:v1"]).toBe("0");
  });
});
