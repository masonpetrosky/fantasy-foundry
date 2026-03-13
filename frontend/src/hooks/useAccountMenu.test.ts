import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../accessibility_components", () => ({
  useMenuInteractions: vi.fn(),
}));

const React = await import("react");
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");

const { useAccountMenu } = await import("./useAccountMenu");

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

describe("useAccountMenu", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns initial closed state", () => {
    const { result, cleanup } = renderHook(() => useAccountMenu({ section: "projections" }));
    expect(result.current!.accountMenuOpen).toBe(false);
    cleanup();
  });

  it("returns expected shape (accountMenuOpen, setAccountMenuOpen, refs)", () => {
    const { result, cleanup } = renderHook(() => useAccountMenu({ section: "projections" }));
    expect(result.current).toHaveProperty("accountMenuOpen");
    expect(result.current).toHaveProperty("setAccountMenuOpen");
    expect(result.current).toHaveProperty("accountMenuRef");
    expect(result.current).toHaveProperty("accountTriggerRef");
    expect(typeof result.current!.setAccountMenuOpen).toBe("function");
    cleanup();
  });

  it("accountMenuOpen defaults to false", () => {
    const { result, cleanup } = renderHook(() => useAccountMenu({ section: "methodology" }));
    expect(result.current!.accountMenuOpen).toBe(false);
    cleanup();
  });
});
