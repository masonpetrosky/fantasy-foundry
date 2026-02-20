import { describe, expect, it } from "vitest";
import {
  buildProjectionCacheKey,
  buildProjectionQueryParams,
} from "./useProjectionsData.js";

describe("buildProjectionQueryParams", () => {
  it("builds year-based projection params with optional filters", () => {
    const { baseParams, shouldReturnEmptyWatchlist } = buildProjectionQueryParams({
      debouncedSearch: "soto",
      teamFilter: "NYY",
      watchlistOnly: true,
      watchlistKeysFilter: "juan-soto",
      careerTotalsView: false,
      resolvedYearFilter: "2028",
      posFilters: ["OF", "DH"],
      selectedDynastyYears: ["2028"],
    });

    expect(shouldReturnEmptyWatchlist).toBe(false);
    expect(baseParams.get("player")).toBe("soto");
    expect(baseParams.get("team")).toBe("NYY");
    expect(baseParams.get("player_keys")).toBe("juan-soto");
    expect(baseParams.get("year")).toBe("2028");
    expect(baseParams.get("pos")).toBe("OF,DH");
    expect(baseParams.get("dynasty_years")).toBe("2028");
    expect(baseParams.get("include_dynasty")).toBe("true");
  });

  it("returns empty-watchlist short-circuit flag and career totals params", () => {
    const { baseParams, shouldReturnEmptyWatchlist } = buildProjectionQueryParams({
      debouncedSearch: "",
      teamFilter: "",
      watchlistOnly: true,
      watchlistKeysFilter: "",
      careerTotalsView: true,
      resolvedYearFilter: "__career_totals__",
      posFilters: [],
      selectedDynastyYears: ["2026", "2027"],
    });

    expect(shouldReturnEmptyWatchlist).toBe(true);
    expect(baseParams.get("career_totals")).toBe("true");
    expect(baseParams.get("year")).toBeNull();
    expect(baseParams.get("dynasty_years")).toBe("2026,2027");
    expect(baseParams.get("include_dynasty")).toBe("true");
  });
});

describe("buildProjectionCacheKey", () => {
  it("generates stable cache keys by data version + endpoint + params", () => {
    const params = new URLSearchParams();
    params.set("limit", "100");
    params.set("offset", "0");

    const key = buildProjectionCacheKey("data-v42", "all", params);
    expect(key).toBe("data-v42:all?limit=100&offset=0");
  });
});
