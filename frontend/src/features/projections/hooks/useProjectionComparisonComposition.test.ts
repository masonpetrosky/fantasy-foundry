import { describe, expect, it } from "vitest";

import {
  buildProjectionCompareShareHref,
  buildProjectionComparisonColumns,
} from "./useProjectionComparisonComposition";

describe("buildProjectionComparisonColumns", () => {
  it("returns hitter-focused columns for bat tab", () => {
    const cols = buildProjectionComparisonColumns({
      tab: "bat",
      seasonCol: "Year",
    });

    expect(cols).toEqual(["Year", "DynastyValue", "AB", "R", "HR", "RBI", "SB", "AVG"]);
  });

  it("returns pitcher-focused columns for pitch tab", () => {
    const cols = buildProjectionComparisonColumns({
      tab: "pitch",
      seasonCol: "Year",
    });

    expect(cols).toEqual(["Year", "DynastyValue", "IP", "W", "K", "SV", "ERA", "WHIP"]);
  });
});

describe("buildProjectionCompareShareHref", () => {
  it("builds a share URL with compare keys", () => {
    const href = buildProjectionCompareShareHref({
      locationHref: "https://example.com/app?tab=all",
      compareRowsByKey: {
        alpha: { Player: "Alpha" },
        beta: { Player: "Beta" },
      },
    });

    const url = new URL(href);
    expect(url.searchParams.get("compare")).toBe("alpha,beta");
    expect(url.searchParams.get("tab")).toBe("all");
  });

  it("returns empty href when no compare keys are available", () => {
    expect(buildProjectionCompareShareHref({
      locationHref: "https://example.com/app",
      compareRowsByKey: {},
    })).toBe("");
  });
});
