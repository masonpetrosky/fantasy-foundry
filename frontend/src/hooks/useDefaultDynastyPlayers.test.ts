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

const { useDefaultDynastyPlayers } = await import("./useDefaultDynastyPlayers");

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

describe("useDefaultDynastyPlayers", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("returns empty array initially", () => {
    globalThis.fetch = vi.fn(() =>
      new Promise(() => {})
    ) as unknown as typeof fetch;

    const { result, cleanup } = renderHook(() => useDefaultDynastyPlayers("http://localhost"));
    expect(result.current).toEqual([]);
    cleanup();
  });

  it("calls fetch with correct URL and params", () => {
    globalThis.fetch = vi.fn(() =>
      new Promise(() => {})
    ) as unknown as typeof fetch;

    const { cleanup } = renderHook(() => useDefaultDynastyPlayers("http://localhost:8000"));

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const callUrl = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(callUrl).toContain("http://localhost:8000/api/projections/all?");
    expect(callUrl).toContain("include_dynasty=true");
    expect(callUrl).toContain("career_totals=true");
    expect(callUrl).toContain("sort_col=DynastyValue");
    expect(callUrl).toContain("sort_dir=desc");
    expect(callUrl).toContain("limit=2000");
    cleanup();
  });

  it("returns data rows on successful fetch", async () => {
    const mockRows = [
      { PlayerEntityKey: "player1", Player: "Test Player", DynastyValue: 10 },
      { PlayerEntityKey: "player2", Player: "Test Player 2", DynastyValue: 5 },
    ];

    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: mockRows }),
      })
    ) as unknown as typeof fetch;

    let result: HookResult<ReturnType<typeof useDefaultDynastyPlayers>>;
    let cleanup: () => void;

    await act(async () => {
      const rendered = renderHook(() => useDefaultDynastyPlayers("http://localhost"));
      result = rendered.result;
      cleanup = rendered.cleanup;
    });

    // Wait for promises to resolve
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result!.current).toEqual(mockRows);
    cleanup!();
  });

  it("returns empty array on fetch error", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: false,
        status: 500,
      })
    ) as unknown as typeof fetch;

    let result: HookResult<ReturnType<typeof useDefaultDynastyPlayers>>;
    let cleanup: () => void;

    await act(async () => {
      const rendered = renderHook(() => useDefaultDynastyPlayers("http://localhost"));
      result = rendered.result;
      cleanup = rendered.cleanup;
    });

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result!.current).toEqual([]);
    cleanup!();
  });

  it("returns empty array when response data is not an array", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ data: "not-an-array" }),
      })
    ) as unknown as typeof fetch;

    let result: HookResult<ReturnType<typeof useDefaultDynastyPlayers>>;
    let cleanup: () => void;

    await act(async () => {
      const rendered = renderHook(() => useDefaultDynastyPlayers("http://localhost"));
      result = rendered.result;
      cleanup = rendered.cleanup;
    });

    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    expect(result!.current).toEqual([]);
    cleanup!();
  });
});
