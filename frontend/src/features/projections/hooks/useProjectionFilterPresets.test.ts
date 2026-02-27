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

describe("matchesProjectionFilterPreset", () => {
  it("matches filter state against preset values", () => {
    expect(matchesProjectionFilterPreset(defaultState, defaultProjectionFilterPreset("all", false))).toBe(true);
    expect(matchesProjectionFilterPreset(
      { ...defaultState, teamFilter: "SEA" },
      defaultProjectionFilterPreset("all", false)
    )).toBe(false);
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
