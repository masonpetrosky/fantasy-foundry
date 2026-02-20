import { describe, expect, it } from "vitest";
import {
  PROJECTION_HITTER_CORE_STATS,
  PROJECTION_PITCHER_CORE_STATS,
  normalizeHiddenColumnOverridesByTab,
  projectionCardDefaultVisibleColumns,
  projectionTableColumnCatalog,
  projectionTableColumnHiddenByDefault,
  resolveProjectionCardColumns,
  resolveProjectionCardCoreColumnsForRow,
  resolveProjectionPriorityStats,
  resolveProjectionTableColumns,
} from "./projections_view_config.js";

describe("projectionTable defaults", () => {
  it("includes QA3 in pitcher table catalogs", () => {
    const pitchCols = projectionTableColumnCatalog("pitch", "Year", ["Value_2026"]);
    const allCols = projectionTableColumnCatalog("all", "Year", ["Value_2026"]);
    expect(pitchCols).toContain("QA3");
    expect(allCols).toContain("QA3");
  });

  it("uses points settings to move selected stats into early columns", () => {
    const settings = {
      scoring_mode: "points",
      pts_hit_hr: 4,
      pts_pit_k: 1,
      pts_pit_bb: -1,
    };
    const cols = projectionTableColumnCatalog("all", "Year", ["Value_2026", "Value_2027"], settings);
    expect(cols.slice(0, 12)).toEqual([
      "Player",
      "Team",
      "Pos",
      "Age",
      "DynastyValue",
      "AB",
      "HR",
      "IP",
      "K",
      "PitBB",
      "Value_2026",
      "Value_2027",
    ]);
  });

  it("hides Years and Side by default, but supports explicit user overrides", () => {
    expect(projectionTableColumnHiddenByDefault("all", "Years")).toBe(true);
    expect(projectionTableColumnHiddenByDefault("all", "Type")).toBe(true);

    const defaultCols = resolveProjectionTableColumns("all", "Years", ["Value_2026"], {});
    expect(defaultCols).not.toContain("Years");
    expect(defaultCols).not.toContain("Type");

    const customizedCols = resolveProjectionTableColumns(
      "all",
      "Years",
      ["Value_2026"],
      { Years: false, Type: false, OBP: true }
    );
    expect(customizedCols).toContain("Years");
    expect(customizedCols).toContain("Type");
    expect(customizedCols).not.toContain("OBP");
  });
});

describe("projectionCard defaults", () => {
  it("uses contextual AB/IP force by row side", () => {
    expect(resolveProjectionCardCoreColumnsForRow("bat", { Type: "H" })).toContain("AB");
    expect(resolveProjectionCardCoreColumnsForRow("pitch", { Type: "P" })).toContain("IP");
    expect(resolveProjectionCardCoreColumnsForRow("all", { Type: "H" })).toContain("AB");
    expect(resolveProjectionCardCoreColumnsForRow("all", { Type: "P" })).toContain("IP");
  });

  it("uses row-specific points metrics by default for all-tab cards", () => {
    const settings = {
      scoring_mode: "points",
      pts_hit_hr: 4,
      pts_pit_k: 1,
      pts_pit_bb: -1,
    };
    expect(resolveProjectionCardColumns("all", "Year", ["Value_2026"], { Type: "H" }, {}, settings)).toEqual([
      "AB",
      "HR",
      "Rank",
      "DynastyValue",
    ]);
    expect(resolveProjectionCardColumns("all", "Year", ["Value_2026"], { Type: "P" }, {}, settings)).toEqual([
      "IP",
      "K",
      "PitBB",
      "Rank",
      "DynastyValue",
    ]);
  });

  it("groups mixed all-tab card defaults as AB, hitting stats, then IP, then pitching stats", () => {
    const settings = {
      scoring_mode: "points",
      pts_hit_hr: 4,
      pts_pit_k: 1,
      pts_pit_bb: -1,
    };
    expect(resolveProjectionCardColumns("all", "Year", ["Value_2026"], { Type: "BOTH" }, {}, settings)).toEqual([
      "AB",
      "HR",
      "IP",
      "K",
      "PitBB",
      "Rank",
      "DynastyValue",
    ]);
  });

  it("lets user overrides hide default card stats", () => {
    const settings = {
      scoring_mode: "points",
      pts_hit_hr: 4,
    };
    const cols = resolveProjectionCardColumns(
      "bat",
      "Year",
      ["Value_2026"],
      { Type: "H" },
      { AB: true, HR: true, Value_2026: false },
      settings
    );
    expect(cols).toEqual(["Rank", "DynastyValue", "Value_2026"]);
  });

  it("exposes default visible card columns by side", () => {
    const defaultsForHitters = projectionCardDefaultVisibleColumns("all", { Type: "H" });
    const defaultsForPitchers = projectionCardDefaultVisibleColumns("all", { Type: "P" });
    expect(defaultsForHitters).toContain("AB");
    expect(defaultsForPitchers).toContain("IP");
    expect(defaultsForHitters).toContain("Rank");
    expect(defaultsForPitchers).toContain("DynastyValue");
  });
});

describe("priority stat resolution", () => {
  it("falls back to legacy core stats when no calculator settings are available", () => {
    expect(resolveProjectionPriorityStats("bat", null, null)).toEqual(PROJECTION_HITTER_CORE_STATS);
    expect(resolveProjectionPriorityStats("pitch", null, null)).toEqual(PROJECTION_PITCHER_CORE_STATS);
  });

  it("keeps mixed all-tab priority grouped by hitting before pitching", () => {
    const settings = {
      scoring_mode: "points",
      pts_hit_hr: 4,
      pts_pit_k: 1,
      pts_pit_bb: -1,
    };
    expect(resolveProjectionPriorityStats("all", null, settings)).toEqual([
      "AB",
      "HR",
      "IP",
      "K",
      "PitBB",
    ]);
  });

  it("separates AB and IP in mixed all-tab fallback ordering", () => {
    const stats = resolveProjectionPriorityStats("all", null, null);
    expect(stats.indexOf("AB")).toBe(0);
    expect(stats.indexOf("IP")).toBeGreaterThan(stats.indexOf("OPS"));
    expect(stats.indexOf("W")).toBeGreaterThan(stats.indexOf("IP"));
  });
});

describe("normalizeHiddenColumnOverridesByTab", () => {
  it("returns all tabs and coerces values to booleans", () => {
    const normalized = normalizeHiddenColumnOverridesByTab({
      bat: { AVG: 0, HR: 1 },
      extra: { ignored: true },
    });
    expect(normalized).toEqual({
      all: {},
      bat: { AVG: false, HR: true },
      pitch: {},
    });
  });
});
