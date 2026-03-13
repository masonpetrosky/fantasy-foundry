import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../app_state_storage", () => ({
  BUILD_QUERY_PARAM: "build",
  BUILD_STORAGE_KEY: "ff:build",
  safeReadStorage: vi.fn(() => null),
  safeWriteStorage: vi.fn(),
}));

const React = await import("react");
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");

const { useVersionPolling } = await import("./useVersionPolling");

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

describe("useVersionPolling", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    globalThis.fetch = originalFetch;
  });

  it("exports useVersionPolling function", () => {
    expect(typeof useVersionPolling).toBe("function");
  });

  it("returns initial empty buildLabel and dataVersion", () => {
    globalThis.fetch = vi.fn(() =>
      new Promise(() => {})
    ) as unknown as typeof fetch;

    const { result, cleanup } = renderHook(() => useVersionPolling("http://localhost"));
    expect(result.current).toEqual({ buildLabel: "", dataVersion: "" });
    cleanup();
  });

  it("calls fetch with /api/version URL", () => {
    globalThis.fetch = vi.fn(() =>
      new Promise(() => {})
    ) as unknown as typeof fetch;

    const { cleanup } = renderHook(() => useVersionPolling("http://localhost:8000"));

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const callUrl = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(callUrl).toBe("http://localhost:8000/api/version");
    cleanup();
  });

  it("updates buildLabel and dataVersion on successful response", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers({ etag: '"abc123"' }),
        json: () => Promise.resolve({ build_id: "abcdef123456789", data_version: "v2" }),
      })
    ) as unknown as typeof fetch;

    let result: HookResult<ReturnType<typeof useVersionPolling>>;
    let cleanup: () => void;

    await act(async () => {
      const rendered = renderHook(() => useVersionPolling("http://localhost"));
      result = rendered.result;
      cleanup = rendered.cleanup;
    });

    // Flush microtasks by advancing fake timers minimally
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result!.current!.buildLabel).toBe("abcdef123456");
    expect(result!.current!.dataVersion).toBe("v2");
    cleanup!();
  });

  it("handles 304 response without updating state", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 304,
        headers: new Headers(),
      })
    ) as unknown as typeof fetch;

    let result: HookResult<ReturnType<typeof useVersionPolling>>;
    let cleanup: () => void;

    await act(async () => {
      const rendered = renderHook(() => useVersionPolling("http://localhost"));
      result = rendered.result;
      cleanup = rendered.cleanup;
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(result!.current!.buildLabel).toBe("");
    expect(result!.current!.dataVersion).toBe("");
    cleanup!();
  });
});
