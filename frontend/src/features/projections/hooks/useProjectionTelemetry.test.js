import { describe, expect, it } from "vitest";

import {
  buildProjectionEmptyStateMarker,
  buildProjectionRefreshMarker,
} from "./useProjectionTelemetry.js";

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
});
