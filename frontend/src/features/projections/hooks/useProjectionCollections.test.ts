import { describe, expect, it } from "vitest";

import {
  buildProjectionCompareHydrationRequest,
  resolveCompareShareHydrationNotice,
  selectHydratedCompareRows,
} from "./useProjectionCollections";

describe("buildProjectionCompareHydrationRequest", () => {
  it("builds compare hydration request with dataset and calculator context", () => {
    const href = buildProjectionCompareHydrationRequest({
      apiBase: "https://example.com/",
      compareKeys: ["alpha", "beta"],
      tab: "pitch",
      careerTotalsView: false,
      resolvedYearFilter: "2028",
      calculatorJobId: "job-42",
    });

    const url = new URL(href);
    expect(url.pathname).toBe("/api/projections/compare");
    expect(url.searchParams.get("player_keys")).toBe("alpha,beta");
    expect(url.searchParams.get("dataset")).toBe("pitch");
    expect(url.searchParams.get("career_totals")).toBe("false");
    expect(url.searchParams.get("year")).toBe("2028");
    expect(url.searchParams.get("calculator_job_id")).toBe("job-42");
    expect(url.searchParams.get("include_dynasty")).toBe("true");
  });

  it("returns empty request for invalid inputs", () => {
    expect(buildProjectionCompareHydrationRequest({
      apiBase: "",
      compareKeys: ["alpha", "beta"],
      tab: "all",
      careerTotalsView: true,
      resolvedYearFilter: "__career_totals__",
      calculatorJobId: "",
    })).toBe("");
    expect(buildProjectionCompareHydrationRequest({
      apiBase: "https://example.com",
      compareKeys: ["alpha"],
      tab: "all",
      careerTotalsView: true,
      resolvedYearFilter: "__career_totals__",
      calculatorJobId: "",
    })).toBe("");
  });
});

describe("selectHydratedCompareRows", () => {
  it("prefers requested season rows when career totals are disabled", () => {
    const rowsByKey = selectHydratedCompareRows({
      rows: [
        { PlayerEntityKey: "alpha", Player: "Alpha", Year: 2027, DynastyValue: 12 },
        { PlayerEntityKey: "alpha", Player: "Alpha", Year: 2028, DynastyValue: 18 },
      ],
      requestedKeys: ["alpha"],
      careerTotalsView: false,
      resolvedYearFilter: "2027",
    });

    expect(rowsByKey.alpha).toMatchObject({
      PlayerEntityKey: "alpha",
      Year: 2027,
      DynastyValue: 12,
    });
  });

  it("falls back to latest year when the requested season is unavailable", () => {
    const rowsByKey = selectHydratedCompareRows({
      rows: [
        { PlayerEntityKey: "alpha", Player: "Alpha", Year: 2026, DynastyValue: 8 },
        { PlayerEntityKey: "alpha", Player: "Alpha", Year: 2028, DynastyValue: 15 },
      ],
      requestedKeys: ["alpha"],
      careerTotalsView: false,
      resolvedYearFilter: "2030",
    });

    expect(rowsByKey.alpha).toMatchObject({
      PlayerEntityKey: "alpha",
      Year: 2028,
    });
  });

  it("prefers career aggregate rows when career totals view is active", () => {
    const rowsByKey = selectHydratedCompareRows({
      rows: [
        { PlayerEntityKey: "beta", Player: "Beta", Year: 2028, DynastyValue: 10 },
        {
          PlayerEntityKey: "beta",
          Player: "Beta",
          Years: "2026-2028",
          YearStart: 2026,
          YearEnd: 2028,
          DynastyValue: 24,
        },
      ],
      requestedKeys: ["beta"],
      careerTotalsView: true,
      resolvedYearFilter: "__career_totals__",
    });

    expect(rowsByKey.beta).toMatchObject({
      PlayerEntityKey: "beta",
      Years: "2026-2028",
      DynastyValue: 24,
    });
  });
});

describe("resolveCompareShareHydrationNotice", () => {
  it("returns null when all requested compare keys are resolved", () => {
    expect(resolveCompareShareHydrationNotice({
      requestedKeys: ["alpha", "beta"],
      matchedKeys: ["beta", "alpha"],
    })).toBeNull();
  });

  it("returns warning notice when only a subset resolves", () => {
    const notice = resolveCompareShareHydrationNotice({
      requestedKeys: ["alpha", "beta", "gamma"],
      matchedKeys: ["alpha"],
    });

    expect(notice).toEqual({
      severity: "warning",
      message: "Loaded 1/3 shared comparison players. Missing: beta, gamma.",
    });
  });

  it("returns error notice with truncated missing preview when nothing resolves", () => {
    const notice = resolveCompareShareHydrationNotice({
      requestedKeys: ["alpha", "beta", "gamma", "delta"],
      matchedKeys: [],
    });

    expect(notice).toEqual({
      severity: "error",
      message: "Unable to load shared comparison players from link. Missing: alpha, beta, gamma (+1 more).",
    });
  });
});
