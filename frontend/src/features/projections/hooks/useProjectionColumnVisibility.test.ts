import { describe, expect, it } from "vitest";

import {
  buildHiddenColumnOverridesByTab,
  buildShowAllColumnsOverridesByTab,
  resolveProjectionCardColumnHidden,
  resolveProjectionTableColumnHidden,
} from "./useProjectionColumnVisibility";

describe("projection table hidden overrides", () => {
  it("falls back to table defaults when no override exists", () => {
    expect(resolveProjectionTableColumnHidden("all", "Years", {})).toBe(true);
    expect(resolveProjectionTableColumnHidden("all", "Player", {})).toBe(false);
  });

  it("persists only non-default overrides", () => {
    const byTab = buildHiddenColumnOverridesByTab({
      currentByTab: { all: { Years: false }, bat: {}, pitch: {} },
      tab: "all",
      col: "Years",
      hidden: true,
      defaultHidden: true,
    });
    expect(byTab.all.Years).toBeUndefined();

    const nextByTab = buildHiddenColumnOverridesByTab({
      currentByTab: byTab,
      tab: "all",
      col: "Player",
      hidden: true,
      defaultHidden: false,
    });
    expect(nextByTab.all.Player).toBe(true);
  });

  it("show all clears visibility for optional columns and keeps required columns untouched", () => {
    const nextByTab = buildShowAllColumnsOverridesByTab({
      currentByTab: { all: { Years: true }, bat: {}, pitch: {} },
      tab: "all",
      columns: ["Player", "Years", "DynastyValue"],
      requiredCols: new Set(["Player"]),
    });
    expect(nextByTab.all.Player).toBeUndefined();
    expect(nextByTab.all.Years).toBe(false);
    expect(nextByTab.all.DynastyValue).toBe(false);
  });
});

describe("projection card hidden overrides", () => {
  it("uses explicit overrides before default visibility set", () => {
    const visibleDefaults = new Set(["DynastyValue"]);
    expect(resolveProjectionCardColumnHidden("Rank", { Rank: false }, visibleDefaults)).toBe(false);
    expect(resolveProjectionCardColumnHidden("Rank", { Rank: true }, visibleDefaults)).toBe(true);
  });
});
