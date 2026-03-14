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

  it("returns null subscription when authUser has no email", () => {
    const { result, cleanup } = renderHook(() => usePremiumStatus({}));
    expect(result.current!.subscription).toBeNull();
    cleanup();
  });

  it("returns tierLimits even when no auth user", () => {
    const { result, cleanup } = renderHook(() => usePremiumStatus(null));
    expect(result.current!.tierLimits).toBeDefined();
    expect(typeof result.current!.tierLimits.maxSims).toBe("number");
    cleanup();
  });

  it("fetches subscription status when authUser has email", async () => {
    const mockSubscription = { status: "active" };
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockSubscription) } as Response)
    ) as unknown as typeof fetch;

    const { result, cleanup } = renderHook(() => usePremiumStatus({ email: "test@example.com" }));

    await act(async () => {
      await new Promise(r => setTimeout(r, 10));
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/billing/subscription-status?email=test%40example.com")
    );
    expect(result.current!.subscription).toEqual(mockSubscription);
    expect(result.current!.premiumLoading).toBe(false);
    cleanup();
  });

  it("sets subscription to null on fetch error", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.reject(new Error("Network error"))
    ) as unknown as typeof fetch;

    const { result, cleanup } = renderHook(() => usePremiumStatus({ email: "test@example.com" }));

    await act(async () => {
      await new Promise(r => setTimeout(r, 10));
    });

    expect(result.current!.subscription).toBeNull();
    expect(result.current!.premiumLoading).toBe(false);
    cleanup();
  });

  it("sets subscription to null on non-ok response", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 404 } as Response)
    ) as unknown as typeof fetch;

    const { result, cleanup } = renderHook(() => usePremiumStatus({ email: "test@example.com" }));

    await act(async () => {
      await new Promise(r => setTimeout(r, 10));
    });

    expect(result.current!.subscription).toBeNull();
    cleanup();
  });
});
