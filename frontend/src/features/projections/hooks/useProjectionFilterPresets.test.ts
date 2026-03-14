import { describe, expect, it } from "vitest";

import {
  defaultProjectionFilterPreset,
  matchesProjectionFilterPreset,
  projectionFilterPresetValuesForKey,
  resolveActiveProjectionPresetKey,
} from "./useProjectionFilterPresets";
import type { FilterState } from "./useProjectionFilterPresets";

const defaultState: FilterState = {
  tab: "all",
  search: "",
  teamFilter: "",
  resolvedYearFilter: "__career_totals__",
  posFilters: [],
  watchlistOnly: false,
  sortCol: "DynastyValue",
  sortDir: "desc",
};

describe("projectionFilterPresetValuesForKey", () => {
  it("returns built-in presets and custom preset values", () => {
    expect(projectionFilterPresetValuesForKey({
      presetKey: "all",
      projectionFilterPresets: { custom: null },
    })).toEqual(defaultProjectionFilterPreset("all", false));

    expect(projectionFilterPresetValuesForKey({
      presetKey: "watchlist",
      projectionFilterPresets: { custom: null },
    })).toEqual(defaultProjectionFilterPreset("all", true));

    expect(projectionFilterPresetValuesForKey({
      presetKey: "custom",
      projectionFilterPresets: {
        custom: { ...defaultProjectionFilterPreset("bat", false), search: "julio" },
      },
    })).toEqual({ ...defaultProjectionFilterPreset("bat", false), search: "julio" });
  });

  it("returns null for unknown keys", () => {
    expect(projectionFilterPresetValuesForKey({
      presetKey: "unknown",
      projectionFilterPresets: { custom: null },
    })).toBeNull();
  });
});

describe("defaultProjectionFilterPreset", () => {
  it("returns default preset for given tab", () => {
    const preset = defaultProjectionFilterPreset("bat");
    expect(preset.tab).toBe("bat");
    expect(preset.search).toBe("");
    expect(preset.yearFilter).toBe("__career_totals__");
    expect(preset.posFilters).toEqual([]);
    expect(preset.watchlistOnly).toBe(false);
  });

  it("returns default tab when no argument", () => {
    const preset = defaultProjectionFilterPreset();
    expect(preset.tab).toBe("all");
  });

  it("returns watchlistOnly true when specified", () => {
    expect(defaultProjectionFilterPreset("all", true).watchlistOnly).toBe(true);
  });

  it("has correct sort defaults", () => {
    const preset = defaultProjectionFilterPreset();
    expect(preset.sortCol).toBe("DynastyValue");
    expect(preset.sortDir).toBe("desc");
  });
});

describe("projectionFilterPresetValuesForKey extended", () => {
  it("returns hitters preset", () => {
    expect(projectionFilterPresetValuesForKey({
      presetKey: "hitters",
      projectionFilterPresets: { custom: null },
    })).toEqual(defaultProjectionFilterPreset("bat", false));
  });

  it("returns pitchers preset", () => {
    expect(projectionFilterPresetValuesForKey({
      presetKey: "pitchers",
      projectionFilterPresets: { custom: null },
    })).toEqual(defaultProjectionFilterPreset("pitch", false));
  });

  it("returns null for empty string key", () => {
    expect(projectionFilterPresetValuesForKey({
      presetKey: "",
      projectionFilterPresets: { custom: null },
    })).toBeNull();
  });

  it("returns null when custom key but no custom preset saved", () => {
    expect(projectionFilterPresetValuesForKey({
      presetKey: "custom",
      projectionFilterPresets: { custom: null },
    })).toBeNull();
  });

  it("is case-insensitive", () => {
    expect(projectionFilterPresetValuesForKey({
      presetKey: "ALL",
      projectionFilterPresets: { custom: null },
    })).toEqual(defaultProjectionFilterPreset("all", false));
  });
});

describe("matchesProjectionFilterPreset", () => {
  it("matches filter state against preset values", () => {
    expect(matchesProjectionFilterPreset(defaultState, defaultProjectionFilterPreset("all", false))).toBe(true);
    expect(matchesProjectionFilterPreset(
      { ...defaultState, teamFilter: "SEA" },
      defaultProjectionFilterPreset("all", false)
    )).toBe(false);
  });

  it("returns false when preset is null", () => {
    expect(matchesProjectionFilterPreset(defaultState, null)).toBe(false);
  });

  it("returns false when search differs", () => {
    expect(matchesProjectionFilterPreset(
      { ...defaultState, search: "julio" },
      defaultProjectionFilterPreset("all", false)
    )).toBe(false);
  });

  it("returns false when yearFilter differs", () => {
    expect(matchesProjectionFilterPreset(
      { ...defaultState, resolvedYearFilter: "2028" },
      defaultProjectionFilterPreset("all", false)
    )).toBe(false);
  });

  it("returns false when watchlistOnly differs", () => {
    expect(matchesProjectionFilterPreset(
      { ...defaultState, watchlistOnly: true },
      defaultProjectionFilterPreset("all", false)
    )).toBe(false);
  });

  it("returns false when sortCol differs", () => {
    expect(matchesProjectionFilterPreset(
      { ...defaultState, sortCol: "HR" },
      defaultProjectionFilterPreset("all", false)
    )).toBe(false);
  });

  it("returns false when sortDir differs", () => {
    expect(matchesProjectionFilterPreset(
      { ...defaultState, sortDir: "asc" },
      defaultProjectionFilterPreset("all", false)
    )).toBe(false);
  });

  it("returns false when posFilters differ", () => {
    expect(matchesProjectionFilterPreset(
      { ...defaultState, posFilters: ["OF"] },
      defaultProjectionFilterPreset("all", false)
    )).toBe(false);
  });

  it("returns false when tab differs", () => {
    expect(matchesProjectionFilterPreset(
      { ...defaultState, tab: "bat" },
      defaultProjectionFilterPreset("all", false)
    )).toBe(false);
  });

  it("matches watchlist preset", () => {
    expect(matchesProjectionFilterPreset(
      { ...defaultState, watchlistOnly: true },
      defaultProjectionFilterPreset("all", true)
    )).toBe(true);
  });
});

describe("resolveActiveProjectionPresetKey", () => {
  it("resolves built-in active preset key", () => {
    expect(resolveActiveProjectionPresetKey(defaultState, { custom: null })).toBe("all");
    expect(resolveActiveProjectionPresetKey(
      { ...defaultState, tab: "pitch" },
      { custom: null }
    )).toBe("pitchers");
  });

  it("resolves custom active preset key when custom values match", () => {
    const custom = {
      ...defaultProjectionFilterPreset("bat", false),
      search: "julio",
      teamFilter: "SEA",
    };
    expect(resolveActiveProjectionPresetKey(
      {
        ...defaultState,
        tab: "bat",
        search: "julio",
        teamFilter: "SEA",
      },
      { custom }
    )).toBe("custom");
  });
});
