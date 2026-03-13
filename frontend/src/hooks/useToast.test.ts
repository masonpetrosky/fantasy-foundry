import { describe, it, expect, vi, beforeEach } from "vitest";

const React = await import("react");
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");

const { useToast } = await import("./useToast");

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

describe("useToast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("returns initial empty toasts array", () => {
    const { result, cleanup } = renderHook(() => useToast());
    expect(result.current!.toasts).toEqual([]);
    cleanup();
  });

  it("addToast adds a toast with correct message and default type info", () => {
    const { result, cleanup } = renderHook(() => useToast());
    act(() => {
      result.current!.addToast("Hello");
    });
    expect(result.current!.toasts).toHaveLength(1);
    expect(result.current!.toasts[0].message).toBe("Hello");
    expect(result.current!.toasts[0].type).toBe("info");
    cleanup();
  });

  it("addToast with type error sets correct type", () => {
    const { result, cleanup } = renderHook(() => useToast());
    act(() => {
      result.current!.addToast("Oops", { type: "error" });
    });
    expect(result.current!.toasts[0].type).toBe("error");
    cleanup();
  });

  it("dismissToast removes the toast", () => {
    const { result, cleanup } = renderHook(() => useToast());
    let id: number;
    act(() => {
      id = result.current!.addToast("Remove me", { duration: 0 });
    });
    expect(result.current!.toasts).toHaveLength(1);
    act(() => {
      result.current!.dismissToast(id!);
    });
    expect(result.current!.toasts).toHaveLength(0);
    cleanup();
  });

  it("addToast returns a numeric id", () => {
    const { result, cleanup } = renderHook(() => useToast());
    let id: number;
    act(() => {
      id = result.current!.addToast("test");
    });
    expect(typeof id!).toBe("number");
    cleanup();
  });

  it("multiple addToast calls accumulate toasts", () => {
    const { result, cleanup } = renderHook(() => useToast());
    act(() => {
      result.current!.addToast("one", { duration: 0 });
      result.current!.addToast("two", { duration: 0 });
      result.current!.addToast("three", { duration: 0 });
    });
    expect(result.current!.toasts).toHaveLength(3);
    cleanup();
  });
});
