import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";

vi.mock("../../../app_state_storage", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../../../app_state_storage");
  return {
    ...actual,
    safeReadStorage: vi.fn(() => null),
    safeWriteStorage: vi.fn(),
    PROJECTION_MOBILE_LAYOUT_MODE_STORAGE_KEY: "ff:proj-mobile-layout-mode:v2",
  };
});

interface HookResult<T> { current: T | null }

function stubMatchMedia(matches = false) {
  window.matchMedia = vi.fn().mockReturnValue({
    matches,
    media: "",
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
  }) as unknown as typeof window.matchMedia;
}

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

beforeEach(() => {
  stubMatchMedia(false);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useProjectionLayoutState hook rendering", () => {
  it("returns expected shape", async () => {
    const { useProjectionLayoutState } = await import("./useProjectionLayoutState");
    const { result, cleanup } = renderHook(() => useProjectionLayoutState());
    const r = result.current!;
    expect(typeof r.isMobileViewport).toBe("boolean");
    expect(typeof r.mobileLayoutMode).toBe("string");
    expect(typeof r.setMobileLayoutMode).toBe("function");
    expect(r.projectionTableScrollRef).toBeDefined();
    expect(typeof r.canScrollLeft).toBe("boolean");
    expect(typeof r.canScrollRight).toBe("boolean");
    expect(typeof r.updateProjectionHorizontalAffordance).toBe("function");
    expect(typeof r.handleProjectionTableScroll).toBe("function");
    cleanup();
  });

  it("setMobileLayoutMode changes mode", async () => {
    const { useProjectionLayoutState } = await import("./useProjectionLayoutState");
    const { result, cleanup } = renderHook(() => useProjectionLayoutState());
    act(() => { result.current!.setMobileLayoutMode("cards"); });
    expect(result.current!.mobileLayoutMode).toBe("cards");
    act(() => { result.current!.setMobileLayoutMode("table"); });
    expect(result.current!.mobileLayoutMode).toBe("table");
    cleanup();
  });

  it("updateProjectionHorizontalAffordance runs without error", async () => {
    const { useProjectionLayoutState } = await import("./useProjectionLayoutState");
    const { result, cleanup } = renderHook(() => useProjectionLayoutState());
    act(() => { result.current!.updateProjectionHorizontalAffordance(); });
    expect(result.current!.canScrollLeft).toBe(false);
    expect(result.current!.canScrollRight).toBe(false);
    cleanup();
  });

  it("handleProjectionTableScroll runs without error", async () => {
    const { useProjectionLayoutState } = await import("./useProjectionLayoutState");
    const { result, cleanup } = renderHook(() => useProjectionLayoutState());
    act(() => { result.current!.handleProjectionTableScroll(); });
    expect(result.current).not.toBeNull();
    cleanup();
  });
});
