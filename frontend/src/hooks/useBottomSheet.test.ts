import { afterEach, describe, expect, it, vi } from "vitest";

import { prefersReducedMotion } from "./useBottomSheet";

function stubMatchMedia(matches = false): void {
  vi.stubGlobal("window", {
    ...window,
    matchMedia: vi.fn(() => ({ matches })),
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("prefersReducedMotion", () => {
  it("returns false when no preference set", () => {
    stubMatchMedia(false);
    expect(prefersReducedMotion()).toBe(false);
  });

  it("returns true when reduce motion is preferred", () => {
    stubMatchMedia(true);
    expect(prefersReducedMotion()).toBe(true);
  });

  it("queries the correct media query", () => {
    stubMatchMedia(false);
    prefersReducedMotion();
    expect(window.matchMedia).toHaveBeenCalledWith("(prefers-reduced-motion: reduce)");
  });
});

describe("useBottomSheet", () => {
  async function setupRenderHook() {
    const React = await import("react");
    const { createRoot } = await import("react-dom/client");
    const { act } = await import("react");

    interface HookResult<T> { current: T | null; }

    function renderHook<T>(hookFn: () => T): { result: HookResult<T>; cleanup: () => void; rerender: () => void } {
      const result: HookResult<T> = { current: null };
      function TestComponent(): null { result.current = hookFn(); return null; }
      const container = document.createElement("div");
      document.body.appendChild(container);
      let root: ReturnType<typeof createRoot>;
      act(() => { root = createRoot(container); root.render(React.createElement(TestComponent)); });
      return {
        result,
        cleanup: () => { act(() => root.unmount()); document.body.removeChild(container); },
        rerender: () => { act(() => { root.render(React.createElement(TestComponent)); }); },
      };
    }

    return { renderHook, act };
  }

  it("returns initial isOpen as false", async () => {
    const { useBottomSheet } = await import("./useBottomSheet");
    const { renderHook } = await setupRenderHook();
    const { result, cleanup } = renderHook(() => useBottomSheet());
    expect(result.current!.isOpen).toBe(false);
    cleanup();
  });

  it("open() sets isOpen to true", async () => {
    const { useBottomSheet } = await import("./useBottomSheet");
    const { renderHook, act } = await setupRenderHook();
    const { result, cleanup } = renderHook(() => useBottomSheet());
    act(() => { result.current!.open(); });
    expect(result.current!.isOpen).toBe(true);
    cleanup();
  });

  it("close() sets isOpen back to false", async () => {
    const { useBottomSheet } = await import("./useBottomSheet");
    const { renderHook, act } = await setupRenderHook();
    const { result, cleanup } = renderHook(() => useBottomSheet());
    act(() => { result.current!.open(); });
    expect(result.current!.isOpen).toBe(true);
    act(() => { result.current!.close(); });
    expect(result.current!.isOpen).toBe(false);
    cleanup();
  });

  it("sheetStyle is undefined when not dragging", async () => {
    const { useBottomSheet } = await import("./useBottomSheet");
    const { renderHook } = await setupRenderHook();
    const { result, cleanup } = renderHook(() => useBottomSheet());
    expect(result.current!.sheetStyle).toBeUndefined();
    cleanup();
  });

  it("dragHandleProps has onTouchStart, onTouchMove, onTouchEnd functions", async () => {
    const { useBottomSheet } = await import("./useBottomSheet");
    const { renderHook } = await setupRenderHook();
    const { result, cleanup } = renderHook(() => useBottomSheet());
    const { dragHandleProps } = result.current!;
    expect(typeof dragHandleProps.onTouchStart).toBe("function");
    expect(typeof dragHandleProps.onTouchMove).toBe("function");
    expect(typeof dragHandleProps.onTouchEnd).toBe("function");
    cleanup();
  });
});
