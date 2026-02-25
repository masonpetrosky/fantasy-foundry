import { describe, expect, it } from "vitest";

import { buildProjectionExportRequest } from "./useProjectionExportPipeline.js";

describe("buildProjectionExportRequest", () => {
  it("assembles year-based export params with optional filters", () => {
    const request = buildProjectionExportRequest({
      apiBase: "https://example.com",
      tab: "bat",
      search: "julio",
      teamFilter: "SEA",
      watchlistOnly: true,
      watchlistKeysFilter: "julio-rodriguez",
      careerTotalsView: false,
      resolvedYearFilter: "2028",
      posFilters: ["OF", "DH"],
      selectedDynastyYears: ["2028", "2029"],
      activeCalculatorJobId: "job-123",
      sortCol: "DynastyValue",
      sortDir: "desc",
      cols: ["Player", "DynastyValue"],
      format: "csv",
    });

    const url = new URL(request.href);
    expect(request.endpointTab).toBe("bat");
    expect(request.yearView).toBe("2028");
    expect(request.hasCalculatorOverlay).toBe(true);
    expect(url.pathname).toBe("/api/projections/export/bat");
    expect(url.searchParams.get("player")).toBe("julio");
    expect(url.searchParams.get("team")).toBe("SEA");
    expect(url.searchParams.get("player_keys")).toBe("julio-rodriguez");
    expect(url.searchParams.get("year")).toBe("2028");
    expect(url.searchParams.get("career_totals")).toBeNull();
    expect(url.searchParams.get("pos")).toBe("OF,DH");
    expect(url.searchParams.get("dynasty_years")).toBe("2028,2029");
    expect(url.searchParams.get("calculator_job_id")).toBe("job-123");
    expect(url.searchParams.get("sort_col")).toBe("DynastyValue");
    expect(url.searchParams.get("sort_dir")).toBe("desc");
    expect(url.searchParams.get("columns")).toBe("Player,DynastyValue");
    expect(url.searchParams.get("format")).toBe("csv");
  });

  it("assembles career-totals export params and omits absent optional values", () => {
    const request = buildProjectionExportRequest({
      apiBase: "https://example.com",
      tab: "all",
      search: "",
      teamFilter: "",
      watchlistOnly: false,
      watchlistKeysFilter: "",
      careerTotalsView: true,
      resolvedYearFilter: "__career_totals__",
      posFilters: [],
      selectedDynastyYears: [],
      activeCalculatorJobId: "",
      sortCol: "Player",
      sortDir: "asc",
      cols: [],
      format: "xlsx",
    });

    const url = new URL(request.href);
    expect(request.endpointTab).toBe("all");
    expect(request.yearView).toBe("career_totals");
    expect(request.hasCalculatorOverlay).toBe(false);
    expect(url.pathname).toBe("/api/projections/export/all");
    expect(url.searchParams.get("career_totals")).toBe("true");
    expect(url.searchParams.get("year")).toBeNull();
    expect(url.searchParams.get("player")).toBeNull();
    expect(url.searchParams.get("team")).toBeNull();
    expect(url.searchParams.get("player_keys")).toBeNull();
    expect(url.searchParams.get("dynasty_years")).toBeNull();
    expect(url.searchParams.get("calculator_job_id")).toBeNull();
    expect(url.searchParams.get("columns")).toBeNull();
    expect(url.searchParams.get("include_dynasty")).toBe("true");
    expect(url.searchParams.get("format")).toBe("xlsx");
  });
});
