import { describe, expect, it, vi } from "vitest";

vi.mock("../../../app_state_storage", () => ({
  MAX_COMPARE_PLAYERS: 5,
  stablePlayerKeyFromRow: vi.fn((row: Record<string, unknown>) =>
    row?.mlbam_id ? `mlbam:${row.mlbam_id}` : row?.PlayerEntityKey ? String(row.PlayerEntityKey) : ""
  ),
}));

import {
  normalizeCompareKey,
  coerceRowYear,
  rowCompareIdentityKeys,
  pickPreferredCompareRow,
  profilePayloadRows,
  mergeCompareRowsWithCap,
  resolveCompareShareHydrationNotice,
  resolveProjectionDataset,
  buildProjectionCompareHydrationRequest,
  selectHydratedCompareRows,
} from "./projectionCollectionUtils";

describe("normalizeCompareKey", () => {
  it("trims and lowercases input", () => {
    expect(normalizeCompareKey("  FOO  ")).toBe("foo");
  });

  it("returns empty string for null/undefined", () => {
    expect(normalizeCompareKey(null)).toBe("");
    expect(normalizeCompareKey(undefined)).toBe("");
  });

  it("converts numbers to string", () => {
    expect(normalizeCompareKey(123)).toBe("123");
  });
});

describe("coerceRowYear", () => {
  it("returns number for valid year", () => {
    expect(coerceRowYear(2029)).toBe(2029);
    expect(coerceRowYear("2029")).toBe(2029);
  });

  it("returns null for null/undefined/empty", () => {
    expect(coerceRowYear(null)).toBeNull();
    expect(coerceRowYear(undefined)).toBeNull();
    expect(coerceRowYear("")).toBeNull();
  });

  it("returns null for non-finite values", () => {
    expect(coerceRowYear("abc")).toBeNull();
    expect(coerceRowYear(NaN)).toBeNull();
    expect(coerceRowYear(Infinity)).toBeNull();
  });

  it("rounds to nearest integer", () => {
    expect(coerceRowYear(2029.7)).toBe(2030);
  });
});

describe("rowCompareIdentityKeys", () => {
  it("returns set of normalized keys from row", () => {
    const row = { PlayerEntityKey: "entity:1", PlayerKey: "KEY:2", mlbam_id: "100" };
    const keys = rowCompareIdentityKeys(row);
    expect(keys.has("entity:1")).toBe(true);
    expect(keys.has("key:2")).toBe(true);
  });

  it("returns empty set for null/undefined", () => {
    expect(rowCompareIdentityKeys(null).size).toBe(0);
    expect(rowCompareIdentityKeys(undefined).size).toBe(0);
  });
});

describe("pickPreferredCompareRow", () => {
  it("returns null for empty/null rows", () => {
    expect(pickPreferredCompareRow(null, { careerTotalsView: false, resolvedYearFilter: "" })).toBeNull();
    expect(pickPreferredCompareRow([], { careerTotalsView: false, resolvedYearFilter: "" })).toBeNull();
  });

  it("returns first row when no filter criteria", () => {
    const rows = [{ Player: "A" }, { Player: "B" }];
    const result = pickPreferredCompareRow(rows, { careerTotalsView: false, resolvedYearFilter: "" });
    expect(result).not.toBeNull();
  });

  it("returns exact year match when year filter set", () => {
    const rows = [
      { Player: "A", Year: 2028 },
      { Player: "B", Year: 2029 },
    ];
    const result = pickPreferredCompareRow(rows, { careerTotalsView: false, resolvedYearFilter: "2029" });
    expect(result?.Player).toBe("B");
  });

  it("prefers career total rows in career totals view", () => {
    const rows = [
      { Player: "A", Year: 2029 },
      { Player: "B", Years: 10, YearStart: 2026, YearEnd: 2035 },
    ];
    const result = pickPreferredCompareRow(rows, { careerTotalsView: true, resolvedYearFilter: "" });
    expect(result?.Player).toBe("B");
  });

  it("returns latest year row when no filter matches", () => {
    const rows = [
      { Player: "A", Year: 2028 },
      { Player: "B", Year: 2030 },
      { Player: "C", Year: 2029 },
    ];
    const result = pickPreferredCompareRow(rows, { careerTotalsView: false, resolvedYearFilter: "2040" });
    expect(result?.Player).toBe("B");
  });
});

describe("profilePayloadRows", () => {
  it("returns empty array for non-object", () => {
    expect(profilePayloadRows(null, { careerTotalsView: false })).toEqual([]);
    expect(profilePayloadRows("str", { careerTotalsView: false })).toEqual([]);
  });

  it("returns series for non-career view", () => {
    const payload = { series: [{ Player: "A" }], data: [{ Player: "B" }] };
    expect(profilePayloadRows(payload, { careerTotalsView: false })).toEqual([{ Player: "A" }]);
  });

  it("returns career_totals for career view", () => {
    const payload = { career_totals: [{ Player: "A" }], series: [{ Player: "B" }] };
    expect(profilePayloadRows(payload, { careerTotalsView: true })).toEqual([{ Player: "A" }]);
  });

  it("falls back to data array", () => {
    const payload = { data: [{ Player: "C" }] };
    expect(profilePayloadRows(payload, { careerTotalsView: false })).toEqual([{ Player: "C" }]);
  });
});

describe("mergeCompareRowsWithCap", () => {
  it("adds rows up to cap", () => {
    const result = mergeCompareRowsWithCap(null, [
      { mlbam_id: "1", Player: "A" },
      { mlbam_id: "2", Player: "B" },
    ]);
    expect(Object.keys(result).length).toBe(2);
  });

  it("replaces existing rows", () => {
    const current = { "mlbam:1": { mlbam_id: "1", Player: "Old" } };
    const result = mergeCompareRowsWithCap(current, [
      { mlbam_id: "1", Player: "New" },
    ]);
    expect(Object.values(result)[0].Player).toBe("New");
  });

  it("skips null rows", () => {
    const result = mergeCompareRowsWithCap(null, [null, undefined]);
    expect(Object.keys(result).length).toBe(0);
  });
});

describe("resolveCompareShareHydrationNotice", () => {
  it("returns null when no requested keys", () => {
    expect(resolveCompareShareHydrationNotice({ requestedKeys: [], matchedKeys: [] })).toBeNull();
  });

  it("returns null when all keys matched", () => {
    expect(resolveCompareShareHydrationNotice({
      requestedKeys: ["a", "b"],
      matchedKeys: ["a", "b"],
    })).toBeNull();
  });

  it("returns warning when some keys missing", () => {
    const result = resolveCompareShareHydrationNotice({
      requestedKeys: ["a", "b", "c"],
      matchedKeys: ["a"],
    });
    expect(result?.severity).toBe("warning");
    expect(result?.message).toContain("1/3");
  });

  it("returns error when all keys missing", () => {
    const result = resolveCompareShareHydrationNotice({
      requestedKeys: ["a", "b"],
      matchedKeys: [],
    });
    expect(result?.severity).toBe("error");
    expect(result?.message).toContain("Unable to load");
  });
});

describe("resolveProjectionDataset", () => {
  it("returns bat for bat tab", () => {
    expect(resolveProjectionDataset("bat")).toBe("bat");
  });

  it("returns pitch for pitch tab", () => {
    expect(resolveProjectionDataset("pitch")).toBe("pitch");
  });

  it("returns all for anything else", () => {
    expect(resolveProjectionDataset("all")).toBe("all");
    expect(resolveProjectionDataset("unknown")).toBe("all");
  });
});

describe("buildProjectionCompareHydrationRequest", () => {
  it("returns empty string when less than 2 keys", () => {
    expect(buildProjectionCompareHydrationRequest({
      apiBase: "http://localhost",
      compareKeys: ["a"],
      tab: "all",
      careerTotalsView: false,
      resolvedYearFilter: "",
      calculatorJobId: "",
    })).toBe("");
  });

  it("builds URL with player keys", () => {
    const url = buildProjectionCompareHydrationRequest({
      apiBase: "http://localhost",
      compareKeys: ["a", "b"],
      tab: "bat",
      careerTotalsView: false,
      resolvedYearFilter: "2029",
      calculatorJobId: "",
    });
    expect(url).toContain("/api/projections/compare");
    expect(url).toContain("player_keys=a%2Cb");
    expect(url).toContain("dataset=bat");
    expect(url).toContain("year=2029");
  });

  it("includes calculator_job_id when provided", () => {
    const url = buildProjectionCompareHydrationRequest({
      apiBase: "http://localhost",
      compareKeys: ["a", "b"],
      tab: "all",
      careerTotalsView: false,
      resolvedYearFilter: "",
      calculatorJobId: "job-123",
    });
    expect(url).toContain("calculator_job_id=job-123");
  });
});

describe("selectHydratedCompareRows", () => {
  it("returns empty object for empty rows", () => {
    expect(selectHydratedCompareRows({
      rows: [],
      requestedKeys: ["a"],
      careerTotalsView: false,
      resolvedYearFilter: "",
    })).toEqual({});
  });

  it("returns empty object for empty requestedKeys", () => {
    expect(selectHydratedCompareRows({
      rows: [{ Player: "A", PlayerEntityKey: "a" }],
      requestedKeys: [],
      careerTotalsView: false,
      resolvedYearFilter: "",
    })).toEqual({});
  });
});
