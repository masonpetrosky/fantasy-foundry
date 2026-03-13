import { describe, it, expect, beforeEach } from "vitest";

const React = await import("react");
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");

interface HookResult<T> {
  current: T | null;
}

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

describe("useTheme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("defaults to dark when localStorage empty", async () => {
    const { useTheme } = await import("./useTheme");
    const { result, cleanup } = renderHook(() => useTheme());
    expect(result.current!.theme).toBe("dark");
    cleanup();
  });

  it("reads stored theme from localStorage", async () => {
    localStorage.setItem("ff:theme", "light");
    // Re-import to pick up fresh localStorage state
    const mod = await import("./useTheme");
    const { result, cleanup } = renderHook(() => mod.useTheme());
    expect(result.current!.theme).toBe("light");
    cleanup();
  });

  it("toggleTheme switches from dark to light", async () => {
    const { useTheme } = await import("./useTheme");
    const { result, cleanup } = renderHook(() => useTheme());
    expect(result.current!.theme).toBe("dark");
    act(() => {
      result.current!.toggleTheme();
    });
    expect(result.current!.theme).toBe("light");
    cleanup();
  });

  it("toggleTheme switches from light to dark", async () => {
    localStorage.setItem("ff:theme", "light");
    const mod = await import("./useTheme");
    const { result, cleanup } = renderHook(() => mod.useTheme());
    expect(result.current!.theme).toBe("light");
    act(() => {
      result.current!.toggleTheme();
    });
    expect(result.current!.theme).toBe("dark");
    cleanup();
  });

  it("sets data-theme attribute on document", async () => {
    const { useTheme } = await import("./useTheme");
    const { result, cleanup } = renderHook(() => useTheme());
    // useEffect runs synchronously in act
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    act(() => {
      result.current!.toggleTheme();
    });
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    cleanup();
  });

  it("persists theme to localStorage on toggle", async () => {
    const { useTheme } = await import("./useTheme");
    const { result, cleanup } = renderHook(() => useTheme());
    act(() => {
      result.current!.toggleTheme();
    });
    expect(localStorage.getItem("ff:theme")).toBe("light");
    cleanup();
  });
});
