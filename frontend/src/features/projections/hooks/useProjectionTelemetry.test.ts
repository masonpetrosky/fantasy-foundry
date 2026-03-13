import { describe, expect, it, vi } from "vitest";

vi.mock("../../../analytics", () => ({
  trackEvent: vi.fn(),
}));

import {
  buildProjectionEmptyStateMarker,
  buildProjectionRefreshMarker,
} from "./useProjectionTelemetry";

describe("buildProjectionEmptyStateMarker", () => {
  it("builds a stable marker from filter state", () => {
    const marker = buildProjectionEmptyStateMarker({
      tab: "bat",
      resolvedYearFilter: "2028",
      teamFilter: "SEA",
      watchlistOnly: true,
      search: "  Julio ",
      posFilters: ["OF", "DH"],
    });

    expect(marker).toBe("bat|2028|SEA|watchlist|Julio|OF,DH");
  });

  it("falls back to defaults when values are missing", () => {
    const marker = buildProjectionEmptyStateMarker({
      tab: "",
      resolvedYearFilter: "",
      teamFilter: "",
      watchlistOnly: false,
      search: "",
      posFilters: null,
    });

    expect(marker).toBe("|||all||");
  });

  it("trims whitespace from all string fields", () => {
    const marker = buildProjectionEmptyStateMarker({
      tab: "  all  ",
      resolvedYearFilter: " 2029 ",
      teamFilter: " NYY ",
      watchlistOnly: false,
      search: "  Judge  ",
      posFilters: ["OF"],
    });

    expect(marker).toBe("all|2029|NYY|all|Judge|OF");
  });

  it("handles null posFilters as empty string", () => {
    const marker = buildProjectionEmptyStateMarker({
      tab: "bat",
      resolvedYearFilter: "2029",
      teamFilter: "",
      watchlistOnly: false,
      search: "",
      posFilters: null,
    });
    expect(marker).toBe("bat|2029||all||");
  });

  it("handles empty posFilters array", () => {
    const marker = buildProjectionEmptyStateMarker({
      tab: "bat",
      resolvedYearFilter: "2029",
      teamFilter: "",
      watchlistOnly: false,
      search: "",
      posFilters: [],
    });
    expect(marker).toBe("bat|2029||all||");
  });
});

describe("buildProjectionRefreshMarker", () => {
  it("includes first-row identity and pagination context", () => {
    const marker = buildProjectionRefreshMarker({
      tab: "all",
      offset: 50,
      totalRows: 140,
      displayedPage: [
        { Player: "Julio Rodriguez", Team: "SEA", Year: 2029 },
        { Player: "Corbin Carroll", Team: "ARI", Year: 2029 },
      ],
    });

    expect(marker).toBe("all|50|2|140|Julio Rodriguez|SEA|2029");
  });

  it("changes when the first row changes", () => {
    const base = buildProjectionRefreshMarker({
      tab: "all",
      offset: 0,
      totalRows: 10,
      displayedPage: [{ Player: "Player A", Team: "SEA", Year: 2028 }],
    });
    const changed = buildProjectionRefreshMarker({
      tab: "all",
      offset: 0,
      totalRows: 10,
      displayedPage: [{ Player: "Player B", Team: "SEA", Year: 2028 }],
    });

    expect(changed).not.toBe(base);
  });

  it("handles empty displayedPage", () => {
    const marker = buildProjectionRefreshMarker({
      tab: "bat",
      offset: 0,
      totalRows: 0,
      displayedPage: [],
    });
    expect(marker).toBe("bat|0|0|0|||");
  });

  it("handles missing fields in first row", () => {
    const marker = buildProjectionRefreshMarker({
      tab: "pit",
      offset: 10,
      totalRows: 50,
      displayedPage: [{}],
    });
    expect(marker).toBe("pit|10|1|50|||");
  });

  it("handles non-array displayedPage gracefully", () => {
    const marker = buildProjectionRefreshMarker({
      tab: "all",
      offset: 0,
      totalRows: 0,
      displayedPage: null as unknown as [],
    });
    expect(marker).toBe("all|0|0|0|||");
  });

  it("uses first row only even with multiple rows", () => {
    const marker = buildProjectionRefreshMarker({
      tab: "all",
      offset: 0,
      totalRows: 100,
      displayedPage: [
        { Player: "First", Team: "AAA", Year: 2030 },
        { Player: "Second", Team: "BBB", Year: 2031 },
      ],
    });
    expect(marker).toContain("First");
    expect(marker).toContain("AAA");
    expect(marker).not.toContain("Second");
  });
});

describe("useProjectionTelemetry", () => {
  it("is exported as a function", async () => {
    const mod = await import("./useProjectionTelemetry");
    expect(typeof mod.useProjectionTelemetry).toBe("function");
  });
});
