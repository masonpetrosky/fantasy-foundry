import { describe, expect, it } from "vitest";

import { buildProjectionComparisonColumns } from "./useProjectionComparisonComposition.js";

describe("buildProjectionComparisonColumns", () => {
  it("returns hitter comparison columns for bat tab", () => {
    expect(buildProjectionComparisonColumns({
      tab: "bat",
      seasonCol: "Year",
    })).toEqual(["Year", "DynastyValue", "AB", "R", "HR", "RBI", "SB", "AVG"]);
  });

  it("returns pitcher comparison columns for pitch tab", () => {
    expect(buildProjectionComparisonColumns({
      tab: "pitch",
      seasonCol: "Year",
    })).toEqual(["Year", "DynastyValue", "IP", "W", "K", "SV", "ERA", "WHIP"]);
  });

  it("returns mixed comparison columns for all tab", () => {
    expect(buildProjectionComparisonColumns({
      tab: "all",
      seasonCol: "Years",
    })).toEqual([
      "Years",
      "DynastyValue",
      "AB",
      "R",
      "HR",
      "RBI",
      "SB",
      "IP",
      "W",
      "K",
      "SV",
      "ERA",
      "WHIP",
    ]);
  });
});
