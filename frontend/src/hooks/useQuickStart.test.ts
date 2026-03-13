import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("../analytics", () => ({ trackEvent: vi.fn() }));
vi.mock("../quick_start", () => ({
  runQuickStartFlow: vi.fn(),
  trackQuickStartImpression: vi.fn(),
}));
vi.mock("../app_state_storage", () => ({
  FIRST_RUN_STATE_COMPLETED: "completed",
  FIRST_RUN_STATE_DISMISSED_PRE_SUCCESS: "dismissed_pre_success",
  FIRST_RUN_STATE_NEW: "new",
  readFirstRunState: vi.fn(() => "new"),
  writeFirstRunState: vi.fn(),
}));

import type { UseQuickStartInput } from "./useQuickStart";

function makeInput(overrides: Partial<UseQuickStartInput> = {}): UseQuickStartInput {
  return {
    meta: null,
    section: "projections",
    dataVersion: "v1",
    calculatorPanelOpen: false,
    lastSuccessfulCalcRun: null,
    openCalculatorPanel: vi.fn(),
    scrollToCalculator: vi.fn(),
    focusCalculatorHeading: vi.fn(),
    ...overrides,
  };
}

async function setupRenderHook() {
  const React = await import("react");
  const { createRoot } = await import("react-dom/client");
  const { act } = await import("react");

  interface HookResult<T> { current: T | null; }

  function renderHook<T>(hookFn: () => T): { result: HookResult<T>; cleanup: () => void } {
    const result: HookResult<T> = { current: null };
    function TestComponent(): null { result.current = hookFn(); return null; }
    const container = document.createElement("div");
    document.body.appendChild(container);
    let root: ReturnType<typeof createRoot>;
    act(() => { root = createRoot(container); root.render(React.createElement(TestComponent)); });
    return { result, cleanup: () => { act(() => root.unmount()); document.body.removeChild(container); } };
  }

  return { renderHook, act };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("useQuickStart", () => {
  it("exports useQuickStart function", async () => {
    const mod = await import("./useQuickStart");
    expect(typeof mod.useQuickStart).toBe("function");
  });

  it("returns expected shape", async () => {
    const { useQuickStart } = await import("./useQuickStart");
    const { renderHook } = await setupRenderHook();
    const input = makeInput({ meta: { foo: "bar" } });
    const { result, cleanup } = renderHook(() => useQuickStart(input));
    const value = result.current!;
    expect(value).toHaveProperty("firstRunState");
    expect(value).toHaveProperty("showQuickStartOnboarding");
    expect(value).toHaveProperty("showQuickStartReminder");
    expect(value).toHaveProperty("requestQuickStartRun");
    expect(value).toHaveProperty("dismissQuickStartOnboarding");
    expect(value).toHaveProperty("reopenQuickStartOnboarding");
    expect(value).toHaveProperty("handleRegisterQuickStartRunner");
    expect(typeof value.requestQuickStartRun).toBe("function");
    expect(typeof value.dismissQuickStartOnboarding).toBe("function");
    expect(typeof value.reopenQuickStartOnboarding).toBe("function");
    expect(typeof value.handleRegisterQuickStartRunner).toBe("function");
    cleanup();
  });

  it("showQuickStartOnboarding is true when section is projections, meta exists, no successful run", async () => {
    const { useQuickStart } = await import("./useQuickStart");
    const { renderHook } = await setupRenderHook();
    const input = makeInput({
      section: "projections",
      meta: { foo: "bar" },
      lastSuccessfulCalcRun: null,
    });
    const { result, cleanup } = renderHook(() => useQuickStart(input));
    expect(result.current!.showQuickStartOnboarding).toBe(true);
    cleanup();
  });

  it("showQuickStartOnboarding is false when section is not projections", async () => {
    const { useQuickStart } = await import("./useQuickStart");
    const { renderHook } = await setupRenderHook();
    const input = makeInput({
      section: "calculator",
      meta: { foo: "bar" },
      lastSuccessfulCalcRun: null,
    });
    const { result, cleanup } = renderHook(() => useQuickStart(input));
    expect(result.current!.showQuickStartOnboarding).toBe(false);
    cleanup();
  });
});
