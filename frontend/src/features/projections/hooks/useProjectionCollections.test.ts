import { describe, expect, it, vi, afterEach } from "vitest";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";

import {
  buildProjectionCompareHydrationRequest,
  coerceRowYear,
  mergeCompareRowsWithCap,
  normalizeCompareKey,
  pickPreferredCompareRow,
  profilePayloadRows,
  resolveCompareShareHydrationNotice,
  resolveProjectionDataset,
  rowCompareIdentityKeys,
  selectHydratedCompareRows,
} from "./projectionCollectionUtils";
import { useProjectionCollections } from "./useProjectionCollections";
import type { UseProjectionCollectionsResult } from "./useProjectionCollections";

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

  it("returns null for empty requestedKeys", () => {
    expect(resolveCompareShareHydrationNotice({
      requestedKeys: [],
      matchedKeys: [],
    })).toBeNull();
  });
});

describe("normalizeCompareKey", () => {
  it("trims and lowercases a string", () => {
    expect(normalizeCompareKey("  Alpha  ")).toBe("alpha");
  });

  it("returns empty string for falsy input", () => {
    expect(normalizeCompareKey(null)).toBe("");
    expect(normalizeCompareKey(undefined)).toBe("");
    expect(normalizeCompareKey("")).toBe("");
  });
});

describe("coerceRowYear", () => {
  it("returns rounded number for valid numeric input", () => {
    expect(coerceRowYear(2027)).toBe(2027);
    expect(coerceRowYear(2027.6)).toBe(2028);
    expect(coerceRowYear("2026")).toBe(2026);
  });

  it("returns null for null/undefined/empty", () => {
    expect(coerceRowYear(null)).toBeNull();
    expect(coerceRowYear(undefined)).toBeNull();
    expect(coerceRowYear("")).toBeNull();
  });

  it("returns null for non-finite values", () => {
    expect(coerceRowYear(NaN)).toBeNull();
    expect(coerceRowYear(Infinity)).toBeNull();
    expect(coerceRowYear("abc")).toBeNull();
  });
});

describe("rowCompareIdentityKeys", () => {
  it("collects entity key, player key, and stable key", () => {
    const keys = rowCompareIdentityKeys({
      PlayerEntityKey: "entity1",
      PlayerKey: "playerkey1",
      Player: "Test",
    });
    expect(keys.size).toBeGreaterThanOrEqual(1);
    expect(keys.has("entity1")).toBe(true);
    expect(keys.has("playerkey1")).toBe(true);
  });

  it("returns a set for null/undefined input", () => {
    const nullKeys = rowCompareIdentityKeys(null);
    expect(nullKeys).toBeInstanceOf(Set);
    const undefinedKeys = rowCompareIdentityKeys(undefined);
    expect(undefinedKeys).toBeInstanceOf(Set);
  });
});

describe("pickPreferredCompareRow", () => {
  it("returns null for empty/null arrays", () => {
    expect(pickPreferredCompareRow(null, { careerTotalsView: false, resolvedYearFilter: "2027" })).toBeNull();
    expect(pickPreferredCompareRow([], { careerTotalsView: false, resolvedYearFilter: "2027" })).toBeNull();
  });

  it("returns career row when careerTotalsView is true", () => {
    const rows = [
      { Player: "A", Year: 2027 },
      { Player: "A", Years: "2026-2028", YearStart: 2026, YearEnd: 2028 },
    ];
    const result = pickPreferredCompareRow(rows, { careerTotalsView: true, resolvedYearFilter: "__career_totals__" });
    expect(result).toMatchObject({ Years: "2026-2028" });
  });

  it("falls back to first row when no career rows exist and careerTotalsView is true", () => {
    const rows = [{ Player: "A", Year: 2027 }];
    const result = pickPreferredCompareRow(rows, { careerTotalsView: true, resolvedYearFilter: "__career_totals__" });
    expect(result).toMatchObject({ Year: 2027 });
  });

  it("returns exact year match when available", () => {
    const rows = [
      { Player: "A", Year: 2026 },
      { Player: "A", Year: 2027 },
    ];
    const result = pickPreferredCompareRow(rows, { careerTotalsView: false, resolvedYearFilter: "2026" });
    expect(result).toMatchObject({ Year: 2026 });
  });

  it("returns latest year when no exact match", () => {
    const rows = [
      { Player: "A", Year: 2026 },
      { Player: "A", Year: 2029 },
    ];
    const result = pickPreferredCompareRow(rows, { careerTotalsView: false, resolvedYearFilter: "2030" });
    expect(result).toMatchObject({ Year: 2029 });
  });

  it("returns first row when no year data and no career view", () => {
    const rows = [{ Player: "A" }];
    const result = pickPreferredCompareRow(rows, { careerTotalsView: false, resolvedYearFilter: "" });
    expect(result).toMatchObject({ Player: "A" });
  });
});

describe("profilePayloadRows", () => {
  it("returns career_totals when careerTotalsView is true and available", () => {
    const payload = { career_totals: [{ Player: "A" }], series: [{ Player: "B" }] };
    expect(profilePayloadRows(payload, { careerTotalsView: true })).toEqual([{ Player: "A" }]);
  });

  it("returns series when careerTotalsView is false", () => {
    const payload = { career_totals: [{ Player: "A" }], series: [{ Player: "B" }] };
    expect(profilePayloadRows(payload, { careerTotalsView: false })).toEqual([{ Player: "B" }]);
  });

  it("falls back to data array", () => {
    const payload = { data: [{ Player: "C" }] };
    expect(profilePayloadRows(payload, { careerTotalsView: false })).toEqual([{ Player: "C" }]);
    expect(profilePayloadRows(payload, { careerTotalsView: true })).toEqual([{ Player: "C" }]);
  });

  it("returns empty for non-object input", () => {
    expect(profilePayloadRows(null, { careerTotalsView: false })).toEqual([]);
    expect(profilePayloadRows("str", { careerTotalsView: false })).toEqual([]);
  });
});

describe("mergeCompareRowsWithCap", () => {
  it("merges new rows into existing", () => {
    const current = { alpha: { PlayerEntityKey: "alpha", Player: "Alpha" } };
    const result = mergeCompareRowsWithCap(current, [{ PlayerEntityKey: "beta", Player: "Beta" }]);
    expect(result.alpha).toBeTruthy();
    expect(result.beta).toBeTruthy();
  });

  it("updates existing key", () => {
    const current = { alpha: { PlayerEntityKey: "alpha", Player: "Old" } };
    const result = mergeCompareRowsWithCap(current, [{ PlayerEntityKey: "alpha", Player: "New" }]);
    expect(result.alpha.Player).toBe("New");
  });

  it("handles null current", () => {
    const result = mergeCompareRowsWithCap(null, [{ PlayerEntityKey: "a", Player: "A" }]);
    expect(Object.keys(result).length).toBe(1);
  });

  it("skips null/invalid rows", () => {
    const result = mergeCompareRowsWithCap({}, [null, undefined, "not-a-row" as unknown]);
    expect(Object.keys(result).length).toBe(0);
  });
});

describe("resolveProjectionDataset", () => {
  it("returns bat for bat tab", () => {
    expect(resolveProjectionDataset("bat")).toBe("bat");
  });

  it("returns pitch for pitch tab", () => {
    expect(resolveProjectionDataset("pitch")).toBe("pitch");
  });

  it("returns all for other tabs", () => {
    expect(resolveProjectionDataset("all")).toBe("all");
    expect(resolveProjectionDataset("unknown")).toBe("all");
    expect(resolveProjectionDataset("")).toBe("all");
  });
});

describe("useProjectionCollections hook", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  function renderHook<T>(hookFn: () => T): { result: { current: T | null }; cleanup: () => void } {
    const result: { current: T | null } = { current: null };
    function TestComponent(): null {
      result.current = hookFn();
      return null;
    }
    const container = document.createElement("div");
    document.body.appendChild(container);
    let root: ReturnType<typeof createRoot>;
    act(() => {
      root = createRoot(container);
      root.render(React.createElement(TestComponent));
    });
    return {
      result,
      cleanup: () => {
        act(() => root.unmount());
        document.body.removeChild(container);
      },
    };
  }

  it("returns expected shape from hook", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionCollections({
        watchlist: {},
        setWatchlist: vi.fn(),
        data: [],
        apiBase: "http://test",
        tab: "all",
        careerTotalsView: false,
        resolvedYearFilter: "",
        calculatorJobId: "",
      }),
    );
    expect(result.current).not.toBeNull();
    expect(result.current!.watchlistCount).toBe(0);
    expect(result.current!.compareRows).toEqual([]);
    expect(result.current!.compareShareHydrating).toBe(false);
    expect(result.current!.maxComparePlayers).toBeGreaterThan(0);
    expect(typeof result.current!.isRowWatched).toBe("function");
    expect(typeof result.current!.toggleRowWatch).toBe("function");
    expect(typeof result.current!.clearWatchlist).toBe("function");
    expect(typeof result.current!.toggleCompareRow).toBe("function");
    expect(typeof result.current!.clearCompareRows).toBe("function");
    expect(typeof result.current!.removeCompareRow).toBe("function");
    expect(typeof result.current!.removeWatchlistEntry).toBe("function");
    expect(typeof result.current!.exportWatchlistCsv).toBe("function");
    expect(typeof result.current!.quickAddRow).toBe("function");
    expect(typeof result.current!.clearCompareShareNotice).toBe("function");
    cleanup();
  });

  it("isRowWatched returns false for unwatched row", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionCollections({
        watchlist: {},
        setWatchlist: vi.fn(),
        data: [],
        apiBase: "http://test",
        tab: "all",
        careerTotalsView: false,
        resolvedYearFilter: "",
        calculatorJobId: "",
      }),
    );
    const row = { Player: "Test", Team: "NYY", Pos: "1B", Year: 2026 };
    expect(result.current!.isRowWatched(row)).toBe(false);
    cleanup();
  });
});
