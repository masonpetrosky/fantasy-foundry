import { describe, expect, it } from "vitest";

import {
  buildProjectionCompareShareHref,
  buildProjectionComparisonColumns,
  useProjectionComparisonComposition,
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

  it("returns empty href when compareRowsByKey is null", () => {
    expect(buildProjectionCompareShareHref({
      locationHref: "https://example.com",
      compareRowsByKey: null,
    })).toBe("");
  });

  it("returns empty string for invalid URL", () => {
    expect(buildProjectionCompareShareHref({
      locationHref: "",
      compareRowsByKey: { a: { Player: "A" } },
    })).toBe("");
  });
});

describe("buildProjectionComparisonColumns - all tab", () => {
  it("returns combined columns for all tab", () => {
    const cols = buildProjectionComparisonColumns({ tab: "all", seasonCol: "Year" });
    expect(cols.includes("AB")).toBe(true);
    expect(cols.includes("IP")).toBe(true);
    expect(cols.includes("DynastyValue")).toBe(true);
  });
});

describe("useProjectionComparisonComposition", () => {
  it("is exported as a function", () => {
    expect(typeof useProjectionComparisonComposition).toBe("function");
  });
});
