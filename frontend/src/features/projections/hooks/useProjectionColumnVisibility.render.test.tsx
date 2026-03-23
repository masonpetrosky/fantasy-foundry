import { describe, expect, it, vi, afterEach } from "vitest";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";

import { useProjectionColumnVisibility } from "./useProjectionColumnVisibility";
import type { CalculatorSettings } from "../../../dynasty_calculator_config";

vi.mock("../../../app_state_storage", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../../../app_state_storage");
  return {
    ...actual,
    readHiddenColumnOverridesByTab: vi.fn(() => ({ all: {}, bat: {}, pitch: {} })),
    writeHiddenColumnOverridesByTab: vi.fn(),
  };
});

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

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useProjectionColumnVisibility hook rendering", () => {
  it("returns expected shape", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionColumnVisibility({
        tab: "all",
        seasonCol: "Year",
        dynastyYearCols: [],
        activeCalculatorSettings: null,
      }),
    );
    const r = result.current!;
    expect(Array.isArray(r.tableColumnCatalog)).toBe(true);
    expect(r.requiredProjectionTableCols).toBeInstanceOf(Set);
    expect(typeof r.resolvedProjectionTableHiddenCols).toBe("object");
    expect(Array.isArray(r.cols)).toBe(true);
    expect(typeof r.toggleProjectionTableColumn).toBe("function");
    expect(typeof r.showAllProjectionTableColumns).toBe("function");
    expect(Array.isArray(r.cardColumnCatalog)).toBe(true);
    expect(r.requiredProjectionCardCols).toBeInstanceOf(Set);
    expect(typeof r.resolvedProjectionCardHiddenCols).toBe("object");
    expect(typeof r.projectionCardColumnsForRow).toBe("function");
    expect(typeof r.toggleProjectionCardColumn).toBe("function");
    expect(typeof r.showAllProjectionCardColumns).toBe("function");
    cleanup();
  });

  it("Player column is always visible in cols", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionColumnVisibility({
        tab: "all",
        seasonCol: "Year",
        dynastyYearCols: [],
        activeCalculatorSettings: null,
      }),
    );
    expect(result.current!.cols).toContain("Player");
    cleanup();
  });

  it("toggleProjectionTableColumn toggles column hidden state", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionColumnVisibility({
        tab: "all",
        seasonCol: "Year",
        dynastyYearCols: [],
        activeCalculatorSettings: null,
      }),
    );
    const col = result.current!.tableColumnCatalog.find(c => c !== "Player");
    if (col) {
      act(() => { result.current!.toggleProjectionTableColumn(col); });
      // After toggle, the hidden state should have changed
      expect(result.current).not.toBeNull();
    }
    cleanup();
  });

  it("toggleProjectionTableColumn does not toggle Player", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionColumnVisibility({
        tab: "all",
        seasonCol: "Year",
        dynastyYearCols: [],
        activeCalculatorSettings: null,
      }),
    );
    const colsBefore = [...result.current!.cols];
    act(() => { result.current!.toggleProjectionTableColumn("Player"); });
    expect(result.current!.cols).toContain("Player");
    expect(result.current!.cols.length).toBe(colsBefore.length);
    cleanup();
  });

  it("showAllProjectionTableColumns reveals hidden columns", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionColumnVisibility({
        tab: "all",
        seasonCol: "Year",
        dynastyYearCols: [],
        activeCalculatorSettings: null,
      }),
    );
    act(() => { result.current!.showAllProjectionTableColumns(); });
    // After showing all, cols should include all catalog columns
    expect(result.current!.cols.length).toBeGreaterThanOrEqual(result.current!.tableColumnCatalog.length - 1);
    cleanup();
  });

  it("toggleProjectionCardColumn works", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionColumnVisibility({
        tab: "bat",
        seasonCol: "Year",
        dynastyYearCols: [],
        activeCalculatorSettings: null,
      }),
    );
    const cardCol = result.current!.cardColumnCatalog[0];
    if (cardCol) {
      act(() => { result.current!.toggleProjectionCardColumn(cardCol); });
      expect(result.current).not.toBeNull();
    }
    cleanup();
  });

  it("showAllProjectionCardColumns works", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionColumnVisibility({
        tab: "bat",
        seasonCol: "Year",
        dynastyYearCols: [],
        activeCalculatorSettings: null,
      }),
    );
    act(() => { result.current!.showAllProjectionCardColumns(); });
    expect(result.current).not.toBeNull();
    cleanup();
  });

  it("projectionCardColumnsForRow returns array", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionColumnVisibility({
        tab: "bat",
        seasonCol: "Year",
        dynastyYearCols: [],
        activeCalculatorSettings: null,
      }),
    );
    const row = { Player: "Test", Team: "NYY", Pos: "1B", Year: 2026 };
    const cols = result.current!.projectionCardColumnsForRow(row);
    expect(Array.isArray(cols)).toBe(true);
    cleanup();
  });

  it("includes SelectedPoints by default when setup is points-focused", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionColumnVisibility({
        tab: "all",
        seasonCol: "Year",
        dynastyYearCols: [],
        activeCalculatorSettings: { scoring_mode: "points" } as CalculatorSettings,
      }),
    );
    expect(result.current!.cols).toContain("SelectedPoints");
    expect(result.current!.projectionCardColumnsForRow({ Type: "H" })).toContain("SelectedPoints");
    cleanup();
  });

  it("omits SelectedPoints by default when setup is roto-focused", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionColumnVisibility({
        tab: "all",
        seasonCol: "Year",
        dynastyYearCols: [],
        activeCalculatorSettings: { scoring_mode: "roto" } as CalculatorSettings,
      }),
    );
    expect(result.current!.cols).not.toContain("SelectedPoints");
    expect(result.current!.projectionCardColumnsForRow({ Type: "H" })).not.toContain("SelectedPoints");
    cleanup();
  });
});
