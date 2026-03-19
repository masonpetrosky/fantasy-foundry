import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const React = await import("react");
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");

const mod = await import("./useProjectionDeltas");
const { useProjectionDeltas } = mod;
type DeltaMap = import("./useProjectionDeltas").DeltaMap;
type DeltaMover = import("./useProjectionDeltas").DeltaMover;
type ProjectionDeltasResponse = import("./useProjectionDeltas").ProjectionDeltasResponse;

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
    const _deltaMapCheck: DeltaMap = { "player:1": { composite_delta: 0.5 } };
    const _deltaMoverCheck: DeltaMover = {
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

  it("populates data after successful fetch", async () => {
    const mockResponse: ProjectionDeltasResponse = {
      risers: [{ key: "p1", player: "Player A", team: "NYY", pos: "1B", type: "hitter", deltas: { HR: 2 }, composite_delta: 1.5 }],
      fallers: [{ key: "p2", player: "Player B", team: "BOS", pos: "SP", type: "pitcher", deltas: { ERA: -0.5 }, composite_delta: -1.0 }],
      delta_map: { "p1": { composite_delta: 1.5 }, "p2": { composite_delta: -1.0 } },
      has_previous: true,
    };

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockResponse) } as Response)
    ) as unknown as typeof fetch;

    const { result, cleanup } = renderHook(() => useProjectionDeltas("http://test-api"));

    // Wait for the effect to resolve
    await act(async () => {
      await new Promise(r => setTimeout(r, 10));
    });

    expect(result.current!.loading).toBe(false);
    expect(result.current!.hasPrevious).toBe(true);
    expect(result.current!.risers).toHaveLength(1);
    expect(result.current!.risers[0].player).toBe("Player A");
    expect(result.current!.fallers).toHaveLength(1);
    expect(result.current!.deltaMap).toEqual(mockResponse.delta_map);
    cleanup();
  });

  it("handles fetch error gracefully", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.reject(new Error("Network error"))
    ) as unknown as typeof fetch;

    const { result, cleanup } = renderHook(() => useProjectionDeltas("http://test-api"));

    await act(async () => {
      await new Promise(r => setTimeout(r, 10));
    });

    expect(result.current!.loading).toBe(false);
    expect(result.current!.deltaMap).toEqual({});
    expect(result.current!.hasPrevious).toBe(false);
    expect(result.current!.risers).toEqual([]);
    expect(result.current!.fallers).toEqual([]);
    cleanup();
  });

  it("handles non-ok response gracefully", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 500 } as Response)
    ) as unknown as typeof fetch;

    const { result, cleanup } = renderHook(() => useProjectionDeltas("http://test-api"));

    await act(async () => {
      await new Promise(r => setTimeout(r, 10));
    });

    expect(result.current!.loading).toBe(false);
    expect(result.current!.deltaMap).toEqual({});
    cleanup();
  });

  it("calls fetch with correct URL", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    const { cleanup } = renderHook(() => useProjectionDeltas("http://my-api"));
    expect(globalThis.fetch).toHaveBeenCalledWith("http://my-api/api/projections/deltas");
    cleanup();
  });
});
