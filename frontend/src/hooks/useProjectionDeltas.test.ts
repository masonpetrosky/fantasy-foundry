import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const React = await import("react");
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");

const mod = await import("./useProjectionDeltas");
const { useProjectionDeltas } = mod;

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

describe("useProjectionDeltas", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("exports useProjectionDeltas function", () => {
    expect(typeof useProjectionDeltas).toBe("function");
  });

  it("exported types can be imported (DeltaMap, DeltaMover interfaces)", () => {
    // TypeScript compile-time check: if these types didn't exist, the import would fail
    const _deltaMapCheck: mod.DeltaMap = { "player:1": { composite_delta: 0.5 } };
    const _deltaMoverCheck: mod.DeltaMover = {
      key: "k", player: "p", team: "t", pos: "OF", type: "hitter",
      deltas: { HR: 1 }, composite_delta: 0.5,
    };
    expect(_deltaMapCheck).toBeDefined();
    expect(_deltaMoverCheck).toBeDefined();
  });

  it("returns initial loading state", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    const { result, cleanup } = renderHook(() => useProjectionDeltas("http://test-api"));
    expect(result.current!.loading).toBe(true);
    cleanup();
  });

  it("returns empty defaults when no data", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    const { result, cleanup } = renderHook(() => useProjectionDeltas("http://test-api"));
    expect(result.current!.deltaMap).toEqual({});
    expect(result.current!.hasPrevious).toBe(false);
    expect(result.current!.risers).toEqual([]);
    expect(result.current!.fallers).toEqual([]);
    cleanup();
  });
});
