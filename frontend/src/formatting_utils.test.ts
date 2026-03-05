import { describe, it, expect } from "vitest";
import {
  fmt,
  fmtInt,
  fmtSigned,
  formatCellValue,
  parsePosTokens,
  formatIsoDateLabel,
  resolveProjectionWindow,
  THREE_DECIMAL_COLS,
  TWO_DECIMAL_COLS,
  WHOLE_NUMBER_COLS,
  INT_COLS,
} from "./formatting_utils";

describe("fmt", () => {
  it("returns em dash for null", () => {
    expect(fmt(null)).toBe("\u2014");
  });
  it("returns em dash for empty string", () => {
    expect(fmt("")).toBe("\u2014");
  });
  it("returns em dash for NaN", () => {
    expect(fmt(NaN)).toBe("\u2014");
  });
  it("formats number with default 1 decimal", () => {
    expect(fmt(3.456)).toBe("3.5");
  });
  it("formats number with specified decimals", () => {
    expect(fmt(3.456, 2)).toBe("3.46");
  });
  it("formats zero", () => {
    expect(fmt(0, 2)).toBe("0.00");
  });
});

describe("fmtInt", () => {
  it("returns em dash for null", () => {
    expect(fmtInt(null)).toBe("\u2014");
  });
  it("rounds and formats integer", () => {
    const result = fmtInt(1234);
    expect(result).toContain("1");
    expect(result).toContain("234");
  });
  it("rounds float to nearest integer", () => {
    const result = fmtInt(3.7, false);
    expect(result).toBe("4");
  });
});

describe("fmtSigned", () => {
  it("prefixes positive values with +", () => {
    expect(fmtSigned(5.678)).toBe("+5.68");
  });
  it("prefixes negative values with minus sign", () => {
    expect(fmtSigned(-3.1)).toBe("\u22123.10");
  });
  it("shows zero without prefix", () => {
    expect(fmtSigned(0)).toBe("0.00");
  });
  it("returns em dash for null", () => {
    expect(fmtSigned(null)).toBe("\u2014");
  });
});

describe("formatCellValue", () => {
  it("formats DynastyValue with signed prefix", () => {
    expect(formatCellValue("DynastyValue", 5.678)).toBe("+5.68");
  });
  it("formats negative DynastyValue with minus sign", () => {
    expect(formatCellValue("DynastyValue", -2.5)).toBe("\u22122.50");
  });
  it("formats Value_ columns with signed prefix", () => {
    expect(formatCellValue("Value_2026", 3.1)).toBe("+3.10");
  });
  it("formats AVG with 3 decimals", () => {
    expect(formatCellValue("AVG", 0.289)).toBe("0.289");
  });
  it("formats ERA with 2 decimals", () => {
    expect(formatCellValue("ERA", 3.456)).toBe("3.46");
  });
  it("formats HR as whole number", () => {
    const result = formatCellValue("HR", 30);
    expect(result).toContain("30");
  });
  it("returns em dash for null value", () => {
    expect(formatCellValue("Player", null)).toBe("\u2014");
  });
  it("returns string values as-is", () => {
    expect(formatCellValue("Player", "Mike Trout")).toBe("Mike Trout");
  });
});

describe("parsePosTokens", () => {
  it("splits slash-separated positions", () => {
    expect(parsePosTokens("SS/2B")).toEqual(["SS", "2B"]);
  });
  it("uppercases tokens", () => {
    expect(parsePosTokens("sp/rp")).toEqual(["SP", "RP"]);
  });
  it("handles single position", () => {
    expect(parsePosTokens("C")).toEqual(["C"]);
  });
  it("returns empty array for null", () => {
    expect(parsePosTokens(null)).toEqual([]);
  });
  it("returns empty array for empty string", () => {
    expect(parsePosTokens("")).toEqual([]);
  });
  it("trims whitespace around tokens", () => {
    expect(parsePosTokens(" 1B / OF ")).toEqual(["1B", "OF"]);
  });
});

describe("formatIsoDateLabel", () => {
  it("formats ISO date string", () => {
    const result = formatIsoDateLabel("2026-02-15T12:00:00Z");
    expect(result).toContain("Feb");
    expect(result).toContain("2026");
  });
  it("returns Unknown for empty value", () => {
    expect(formatIsoDateLabel("")).toBe("Unknown");
  });
  it("returns Unknown for null", () => {
    expect(formatIsoDateLabel(null)).toBe("Unknown");
  });
  it("returns raw text for invalid date", () => {
    expect(formatIsoDateLabel("not-a-date")).toBe("not-a-date");
  });
});

describe("resolveProjectionWindow", () => {
  it("resolves from explicit meta start/end", () => {
    const result = resolveProjectionWindow({
      projection_window_start: 2026,
      projection_window_end: 2045,
    });
    expect(result).toEqual({ start: 2026, end: 2045, seasons: 20 });
  });
  it("resolves from years array when no explicit window", () => {
    const result = resolveProjectionWindow({
      years: [2026, 2027, 2028],
    });
    expect(result).toEqual({ start: 2026, end: 2028, seasons: 3 });
  });
  it("returns nulls for empty meta", () => {
    const result = resolveProjectionWindow({});
    expect(result).toEqual({ start: null, end: null, seasons: null });
  });
  it("returns nulls for null meta", () => {
    const result = resolveProjectionWindow(null);
    expect(result).toEqual({ start: null, end: null, seasons: null });
  });
});

describe("column set constants", () => {
  it("THREE_DECIMAL_COLS includes AVG", () => {
    expect(THREE_DECIMAL_COLS.has("AVG")).toBe(true);
  });
  it("TWO_DECIMAL_COLS includes ERA", () => {
    expect(TWO_DECIMAL_COLS.has("ERA")).toBe(true);
  });
  it("WHOLE_NUMBER_COLS includes HR", () => {
    expect(WHOLE_NUMBER_COLS.has("HR")).toBe(true);
  });
  it("INT_COLS includes Year", () => {
    expect(INT_COLS.has("Year")).toBe(true);
  });
});
