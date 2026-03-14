import { describe, expect, it, vi } from "vitest";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";

vi.mock("../../../analytics", () => ({
  trackEvent: vi.fn(),
}));

import {
  buildProjectionEmptyStateMarker,
  buildProjectionRefreshMarker,
  useProjectionTelemetry,
} from "./useProjectionTelemetry";
import type { UseProjectionTelemetryInput } from "./useProjectionTelemetry";

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

  it("produces distinct markers for different watchlist states", () => {
    const base = {
      tab: "all",
      resolvedYearFilter: "2028",
      teamFilter: "",
      search: "",
      posFilters: [] as string[],
    };
    const watchlistMarker = buildProjectionEmptyStateMarker({ ...base, watchlistOnly: true });
    const allMarker = buildProjectionEmptyStateMarker({ ...base, watchlistOnly: false });
    expect(watchlistMarker).not.toBe(allMarker);
    expect(watchlistMarker).toContain("watchlist");
    expect(allMarker).toContain("all");
  });

  it("handles multiple posFilters", () => {
    const marker = buildProjectionEmptyStateMarker({
      tab: "all",
      resolvedYearFilter: "2028",
      teamFilter: "",
      watchlistOnly: false,
      search: "",
      posFilters: ["C", "1B", "SS"],
    });
    expect(marker).toContain("C,1B,SS");
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

  it("changes when offset changes", () => {
    const page = [{ Player: "A", Team: "SEA", Year: 2028 }];
    const m1 = buildProjectionRefreshMarker({ tab: "all", offset: 0, totalRows: 100, displayedPage: page });
    const m2 = buildProjectionRefreshMarker({ tab: "all", offset: 25, totalRows: 100, displayedPage: page });
    expect(m1).not.toBe(m2);
  });

  it("changes when totalRows changes", () => {
    const page = [{ Player: "A", Team: "SEA", Year: 2028 }];
    const m1 = buildProjectionRefreshMarker({ tab: "all", offset: 0, totalRows: 100, displayedPage: page });
    const m2 = buildProjectionRefreshMarker({ tab: "all", offset: 0, totalRows: 200, displayedPage: page });
    expect(m1).not.toBe(m2);
  });

  it("changes when tab changes", () => {
    const page = [{ Player: "A", Team: "SEA", Year: 2028 }];
    const m1 = buildProjectionRefreshMarker({ tab: "all", offset: 0, totalRows: 100, displayedPage: page });
    const m2 = buildProjectionRefreshMarker({ tab: "bat", offset: 0, totalRows: 100, displayedPage: page });
    expect(m1).not.toBe(m2);
  });
});

describe("useProjectionTelemetry", () => {
  interface HookResult<T> { current: T | null }
  function renderHook<T>(hookFn: () => T): { result: HookResult<T>; cleanup: () => void } {
    const result: HookResult<T> = { current: null };
    function TestComponent(): null { result.current = hookFn(); return null; }
    const container = document.createElement("div");
    document.body.appendChild(container);
    let root: ReturnType<typeof createRoot>;
    act(() => { root = createRoot(container); root.render(React.createElement(TestComponent)); });
    return {
      result,
      cleanup: () => { act(() => root.unmount()); document.body.removeChild(container); },
    };
  }

  function defaultInput(overrides: Partial<UseProjectionTelemetryInput> = {}): UseProjectionTelemetryInput {
    return {
      loading: false,
      error: null,
      displayedPage: [],
      tab: "all",
      resolvedYearFilter: "__career_totals__",
      teamFilter: "",
      watchlistOnly: false,
      search: "",
      posFilters: [],
      offset: 0,
      totalRows: 0,
      ...overrides,
    };
  }

  it("is exported as a function", () => {
    expect(typeof useProjectionTelemetry).toBe("function");
  });

  it("returns empty lastRefreshedLabel initially when no rows", () => {
    const { result, cleanup } = renderHook(() => useProjectionTelemetry(defaultInput()));
    expect(result.current!.lastRefreshedLabel).toBe("");
    cleanup();
  });

  it("returns lastRefreshedLabel when rows are present", () => {
    const { result, cleanup } = renderHook(() => useProjectionTelemetry(defaultInput({
      displayedPage: [{ Player: "Test", Team: "SEA", Year: 2028 }],
      totalRows: 1,
    })));
    expect(result.current!.lastRefreshedLabel).not.toBe("");
    cleanup();
  });

  it("returns empty lastRefreshedLabel when loading", () => {
    const { result, cleanup } = renderHook(() => useProjectionTelemetry(defaultInput({
      loading: true,
      displayedPage: [{ Player: "Test" }],
      totalRows: 1,
    })));
    expect(result.current!.lastRefreshedLabel).toBe("");
    cleanup();
  });

  it("returns empty lastRefreshedLabel when error is present", () => {
    const { result, cleanup } = renderHook(() => useProjectionTelemetry(defaultInput({
      error: new Error("test"),
      displayedPage: [{ Player: "Test" }],
      totalRows: 1,
    })));
    expect(result.current!.lastRefreshedLabel).toBe("");
    cleanup();
  });
});
