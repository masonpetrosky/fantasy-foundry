import { afterEach, describe, expect, it, vi } from "vitest";
import {
  calculatorPresetsEqual,
  mergeCalculatorPresetsPreferLocal,
  readLastSuccessfulCalcRun,
  readCalculatorPanelOpenPreference,
  readOnboardingDismissed,
  readProjectionFilterPresets,
  writeLastSuccessfulCalcRun,
  writeCalculatorPanelOpenPreference,
  writeOnboardingDismissed,
  writeProjectionFilterPresets,
} from "./app_state_storage.js";

function withStorage(initialValues = {}) {
  const store = { ...initialValues };
  vi.stubGlobal("window", {
    localStorage: {
      getItem: vi.fn(key => (Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null)),
      setItem: vi.fn((key, value) => {
        store[key] = String(value);
      }),
      removeItem: vi.fn(key => {
        delete store[key];
      }),
    },
  });
  return store;
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
    const store = withStorage({ "ff:calc-panel-open:v1": "0" });
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
    const store = withStorage();
    writeOnboardingDismissed(true);
    expect(store["ff:onboarding-dismissed:v1"]).toBe("1");
    expect(readOnboardingDismissed()).toBe(true);

    writeOnboardingDismissed(false);
    expect(store["ff:onboarding-dismissed:v1"]).toBe("0");
    expect(readOnboardingDismissed()).toBe(false);
  });
});

describe("last successful calculator run storage", () => {
  it("round-trips a normalized run summary", () => {
    const store = withStorage();
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
    const store = withStorage();
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
