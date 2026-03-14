import { describe, expect, it, vi, afterEach } from "vitest";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";

import { useProjectionFilterPresets } from "./useProjectionFilterPresets";
import type { UseProjectionFilterPresetsResult, FilterActions, FilterState } from "./useProjectionFilterPresets";

vi.mock("../../../app_state_storage", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../../../app_state_storage");
  return {
    ...actual,
    readProjectionFilterPresets: vi.fn(() => ({ custom: null })),
    writeProjectionFilterPresets: vi.fn(),
  };
});

vi.mock("../../../analytics", () => ({
  trackEvent: vi.fn(),
}));

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

function makeMockActions(): FilterActions {
  return {
    setSearch: vi.fn(),
    setTeamFilter: vi.fn(),
    setYearFilter: vi.fn(),
    setPosFilters: vi.fn(),
    setWatchlistOnly: vi.fn(),
    setSortCol: vi.fn(),
    setSortDir: vi.fn(),
    setOffset: vi.fn(),
    setTab: vi.fn(),
  };
}

function makeDefaultFilterState(): FilterState {
  return {
    tab: "all",
    search: "",
    teamFilter: "",
    resolvedYearFilter: "__career_totals__",
    posFilters: [],
    watchlistOnly: false,
    sortCol: "DynastyValue",
    sortDir: "desc",
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useProjectionFilterPresets hook rendering", () => {
  it("returns expected shape", () => {
    const actions = makeMockActions();
    const filterState = makeDefaultFilterState();
    const setShowPosMenu = vi.fn();
    const { result, cleanup } = renderHook(() =>
      useProjectionFilterPresets({ filterActions: actions, filterState, setShowPosMenu }),
    );
    const r = result.current!;
    expect(typeof r.projectionFilterPresets).toBe("object");
    expect(typeof r.applyProjectionFilterPreset).toBe("function");
    expect(typeof r.saveCustomProjectionPreset).toBe("function");
    expect(typeof r.activeProjectionPresetKey).toBe("string");
    expect(typeof r.clearAllFilters).toBe("function");
    cleanup();
  });

  it("activeProjectionPresetKey returns 'all' for default state", () => {
    const actions = makeMockActions();
    const filterState = makeDefaultFilterState();
    const setShowPosMenu = vi.fn();
    const { result, cleanup } = renderHook(() =>
      useProjectionFilterPresets({ filterActions: actions, filterState, setShowPosMenu }),
    );
    expect(result.current!.activeProjectionPresetKey).toBe("all");
    cleanup();
  });

  it("clearAllFilters calls all filter action setters", () => {
    const actions = makeMockActions();
    const filterState = makeDefaultFilterState();
    const setShowPosMenu = vi.fn();
    const { result, cleanup } = renderHook(() =>
      useProjectionFilterPresets({ filterActions: actions, filterState, setShowPosMenu }),
    );
    act(() => { result.current!.clearAllFilters(); });
    expect(actions.setSearch).toHaveBeenCalledWith("");
    expect(actions.setTeamFilter).toHaveBeenCalledWith("");
    expect(actions.setPosFilters).toHaveBeenCalledWith([]);
    expect(actions.setWatchlistOnly).toHaveBeenCalledWith(false);
    expect(actions.setOffset).toHaveBeenCalledWith(0);
    expect(setShowPosMenu).toHaveBeenCalledWith(false);
    cleanup();
  });

  it("applyProjectionFilterPreset applies hitters preset", () => {
    const actions = makeMockActions();
    const filterState = makeDefaultFilterState();
    const setShowPosMenu = vi.fn();
    const { result, cleanup } = renderHook(() =>
      useProjectionFilterPresets({ filterActions: actions, filterState, setShowPosMenu }),
    );
    act(() => { result.current!.applyProjectionFilterPreset("hitters"); });
    expect(actions.setTab).toHaveBeenCalledWith("bat");
    cleanup();
  });

  it("applyProjectionFilterPreset ignores empty key", () => {
    const actions = makeMockActions();
    const filterState = makeDefaultFilterState();
    const setShowPosMenu = vi.fn();
    const { result, cleanup } = renderHook(() =>
      useProjectionFilterPresets({ filterActions: actions, filterState, setShowPosMenu }),
    );
    act(() => { result.current!.applyProjectionFilterPreset(""); });
    expect(actions.setTab).not.toHaveBeenCalled();
    cleanup();
  });

  it("saveCustomProjectionPreset saves current filter state", () => {
    const actions = makeMockActions();
    const filterState = { ...makeDefaultFilterState(), search: "test", teamFilter: "NYY" };
    const setShowPosMenu = vi.fn();
    const { result, cleanup } = renderHook(() =>
      useProjectionFilterPresets({ filterActions: actions, filterState, setShowPosMenu }),
    );
    act(() => { result.current!.saveCustomProjectionPreset(); });
    // After saving, the custom preset should exist
    expect(result.current!.projectionFilterPresets.custom).not.toBeNull();
    cleanup();
  });
});
