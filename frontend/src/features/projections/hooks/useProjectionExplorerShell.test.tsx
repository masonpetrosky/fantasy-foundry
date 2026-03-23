import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useProjectionExplorerShell } from "./useProjectionExplorerShell";

interface HookResult<T> { current: T | null }

function renderHook<T>(hookFn: () => T): { result: HookResult<T>; cleanup: () => void } {
  const result: HookResult<T> = { current: null };
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

function renderProjectionExplorerShell(isPointsFocused: boolean) {
  return renderHook(() => useProjectionExplorerShell({
    isPointsFocused,
    search: "",
    teamFilter: "",
    resolvedYearFilter: "__career_totals__",
    posFilters: [],
    watchlistOnly: false,
    sortCol: "DynastyValue",
    sortDir: "desc",
    tab: "all",
    selectedDynastyYears: ["2026"],
    tableColumnCatalog: ["Player", "DynastyValue", "SelectedPoints"],
    canScrollLeft: false,
    canScrollRight: false,
    showCards: false,
    isMobileViewport: false,
    mobileLayoutMode: "table",
    colsLength: 3,
    displayedPageLength: 25,
    loading: false,
    totalRows: 25,
    offset: 0,
    projectionTableScrollRef: { current: document.createElement("div") },
    updateProjectionHorizontalAffordance: vi.fn(),
    setTab: vi.fn(),
    setSortCol: vi.fn(),
    setSortDir: vi.fn(),
    setOffset: vi.fn(),
    setPosFilters: vi.fn(),
  }));
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useProjectionExplorerShell", () => {
  it("labels SelectedPoints as Points in points-focused mode", () => {
    const { result, cleanup } = renderProjectionExplorerShell(true);
    expect(result.current?.colLabels.SelectedPoints).toBe("Points");
    cleanup();
  });

  it("keeps the Selected Points label outside points-focused mode", () => {
    const { result, cleanup } = renderProjectionExplorerShell(false);
    expect(result.current?.colLabels.SelectedPoints).toBe("Selected Points");
    cleanup();
  });
});
