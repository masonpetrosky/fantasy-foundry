import { describe, expect, it } from "vitest";
import {
  PROJECTION_HITTER_CORE_STATS,
  PROJECTION_PITCHER_CORE_STATS,
  normalizeHiddenColumnOverridesByTab,
  projectionTableColumnCatalog,
  projectionTableColumnHiddenByDefault,
  resolveProjectionTableColumns,
  resolveProjectionCardColumns,
  resolveProjectionCardCoreColumnsForRow,
} from "./projections_view_config.js";

describe("projectionTable defaults", () => {
  it("orders all-tab columns with core stats first, then dynasty years, then other stats", () => {
    const cols = projectionTableColumnCatalog("all", "Year", ["Value_2026", "Value_2027"]);
    expect(cols.slice(0, 21)).toEqual([
      "Player",
      "Team",
      "Pos",
      "Age",
      "DynastyValue",
      "AB",
      "R",
      "HR",
      "RBI",
      "SB",
      "AVG",
      "OPS",
      "IP",
      "W",
      "K",
      "SV",
      "ERA",
      "WHIP",
      "QS",
      "Value_2026",
      "Value_2027",
    ]);
    expect(cols.indexOf("SVH")).toBeGreaterThan(cols.indexOf("ER"));
    expect(cols.indexOf("Value_2026")).toBeGreaterThan(cols.indexOf("QS"));
    expect(cols.indexOf("Value_2026")).toBeLessThan(cols.indexOf("OBP"));
  });

  it("places OPS and QS immediately after AVG and WHIP in tab-specific tables", () => {
    const batCols = projectionTableColumnCatalog("bat", "Year", ["Value_2026"]);
    const pitchCols = projectionTableColumnCatalog("pitch", "Year", ["Value_2026"]);
    expect(batCols[batCols.indexOf("AVG") + 1]).toBe("OPS");
    expect(pitchCols[pitchCols.indexOf("WHIP") + 1]).toBe("QS");
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
  it("uses hitter core stats plus rank/value by default for batters", () => {
    expect(resolveProjectionCardCoreColumnsForRow("bat", { Type: "H" })).toEqual(PROJECTION_HITTER_CORE_STATS);
    expect(resolveProjectionCardColumns("bat", "Year", ["Value_2026"], { Type: "H" }, {})).toEqual(
      [...PROJECTION_HITTER_CORE_STATS, "Rank", "DynastyValue"]
    );
  });

  it("uses pitcher core stats plus rank/value by default for pitchers", () => {
    expect(resolveProjectionCardCoreColumnsForRow("pitch", { Type: "P" })).toEqual(PROJECTION_PITCHER_CORE_STATS);
    expect(resolveProjectionCardColumns("pitch", "Year", ["Value_2026"], { Type: "P" }, {})).toEqual(
      [...PROJECTION_PITCHER_CORE_STATS, "Rank", "DynastyValue"]
    );
  });

  it("uses per-row relevant core stats plus rank/value on all-tab cards", () => {
    expect(resolveProjectionCardColumns("all", "Year", ["Value_2026"], { Type: "H" }, {})).toEqual(
      [...PROJECTION_HITTER_CORE_STATS, "Rank", "DynastyValue"]
    );
    expect(resolveProjectionCardColumns("all", "Year", ["Value_2026"], { Type: "P" }, {})).toEqual(
      [...PROJECTION_PITCHER_CORE_STATS, "Rank", "DynastyValue"]
    );
  });

  it("shows optional card fields when users enable them", () => {
    const cols = resolveProjectionCardColumns(
      "bat",
      "Year",
      ["Value_2026"],
      { Type: "H" },
      { Value_2026: false, Year: false }
    );
    expect(cols).toEqual([
      ...PROJECTION_HITTER_CORE_STATS,
      "Rank",
      "DynastyValue",
      "Value_2026",
      "Year",
    ]);
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
