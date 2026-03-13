import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("../api_base", () => ({ resolveApiBase: () => "http://test-api" }));
vi.mock("../premium", async () => {
  const actual = await vi.importActual("../premium");
  return {
    ...actual,
    resolveTierLimits: vi.fn((sub: unknown) => sub ? { maxSims: 5000 } : (actual as Record<string, unknown>).FREE_TIER_LIMITS),
  };
});

const React = await import("react");
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");

const { usePremiumStatus } = await import("./usePremiumStatus");

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

describe("usePremiumStatus", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("returns null subscription when authUser is null", () => {
    const { result, cleanup } = renderHook(() => usePremiumStatus(null));
    expect(result.current!.subscription).toBeNull();
    cleanup();
  });

  it("returns initial loading false when no authUser", () => {
    const { result, cleanup } = renderHook(() => usePremiumStatus(null));
    expect(result.current!.premiumLoading).toBe(false);
    cleanup();
  });

  it("exports usePremiumStatus function", () => {
    expect(typeof usePremiumStatus).toBe("function");
  });
});
