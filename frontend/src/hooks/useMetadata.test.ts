import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../analytics", () => ({ trackEvent: vi.fn() }));

const React = await import("react");
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");

const { useMetadata } = await import("./useMetadata");

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

describe("useMetadata", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("returns initial loading state", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    const { result, cleanup } = renderHook(() => useMetadata("http://test-api"));
    expect(result.current!.metaLoading).toBe(true);
    expect(result.current!.meta).toBeNull();
    expect(result.current!.metaError).toBe("");
    cleanup();
  });

  it("sets meta on successful fetch", async () => {
    const mockMeta = { version: "1.0", players: 500 };
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockMeta) } as Response)
    );
    let result: HookResult<ReturnType<typeof useMetadata>>;
    let cleanup: () => void;

    await act(async () => {
      const rendered = renderHook(() => useMetadata("http://test-api"));
      result = rendered.result;
      cleanup = rendered.cleanup;
    });

    // Allow microtasks to flush
    await act(async () => {});

    expect(result!.current!.meta).toEqual(mockMeta);
    expect(result!.current!.metaLoading).toBe(false);
    cleanup!();
  });

  it("sets metaError on failed fetch", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 500 } as Response)
    );
    let result: HookResult<ReturnType<typeof useMetadata>>;
    let cleanup: () => void;

    await act(async () => {
      const rendered = renderHook(() => useMetadata("http://test-api"));
      result = rendered.result;
      cleanup = rendered.cleanup;
    });

    await act(async () => {});

    expect(result!.current!.metaError).toContain("500");
    expect(result!.current!.metaLoading).toBe(false);
    cleanup!();
  });

  it("retryMetaLoad is a function", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    const { result, cleanup } = renderHook(() => useMetadata("http://test-api"));
    expect(typeof result.current!.retryMetaLoad).toBe("function");
    cleanup();
  });
});
