import { describe, it, expect, vi, afterEach } from "vitest";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import type { UseAccountSyncReturn } from "./useAccountSync";

// AUTH_SYNC_ENABLED will be false in test because supabase env vars are not set
const { useAccountSync } = await import("./useAccountSync");

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

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useAccountSync", () => {
  it("exports useAccountSync function", () => {
    expect(typeof useAccountSync).toBe("function");
  });

  it("returns expected shape when auth sync is disabled", () => {
    const setPresets = vi.fn();
    const setWatchlist = vi.fn();
    const { result, cleanup } = renderHook(() =>
      useAccountSync({
        presets: {},
        setPresets,
        watchlist: {},
        setWatchlist,
      }),
    );
    expect(result.current!.authReady).toBe(true);
    expect(result.current!.authUser).toBeNull();
    expect(result.current!.authStatus).toBe("");
    expect(result.current!.cloudStatus).toBe("");
    expect(typeof result.current!.signIn).toBe("function");
    expect(typeof result.current!.signUp).toBe("function");
    expect(typeof result.current!.signOut).toBe("function");
    cleanup();
  });

  it("signIn is a no-op function when auth disabled", async () => {
    const { result, cleanup } = renderHook(() =>
      useAccountSync({
        presets: {},
        setPresets: vi.fn(),
        watchlist: {},
        setWatchlist: vi.fn(),
      }),
    );
    // Should not throw
    await act(async () => {
      await result.current!.signIn("test@test.com", "password");
    });
    cleanup();
  });

  it("signUp is a no-op function when auth disabled", async () => {
    const { result, cleanup } = renderHook(() =>
      useAccountSync({
        presets: {},
        setPresets: vi.fn(),
        watchlist: {},
        setWatchlist: vi.fn(),
      }),
    );
    await act(async () => {
      await result.current!.signUp("test@test.com", "password");
    });
    cleanup();
  });

  it("signOut is a no-op function when auth disabled", async () => {
    const { result, cleanup } = renderHook(() =>
      useAccountSync({
        presets: {},
        setPresets: vi.fn(),
        watchlist: {},
        setWatchlist: vi.fn(),
      }),
    );
    await act(async () => {
      await result.current!.signOut();
    });
    cleanup();
  });
});
