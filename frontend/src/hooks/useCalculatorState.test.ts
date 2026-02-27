import { describe, expect, it, vi, beforeEach } from "vitest";

// Mock app_state_storage before importing the hook
vi.mock("../app_state_storage", () => ({
  CALC_LINK_QUERY_PARAM: "calc",
  readCalculatorPanelOpenPreference: vi.fn(() => null),
  readCalculatorPresets: vi.fn(() => ({})),
  readLastSuccessfulCalcRun: vi.fn(() => null),
  writeCalculatorPanelOpenPreference: vi.fn(),
  writeCalculatorPresets: vi.fn(),
  writeLastSuccessfulCalcRun: vi.fn(),
}));

vi.mock("../analytics", () => ({
  trackEvent: vi.fn(),
}));

// Must import after mocks are set up
const { useCalculatorState } = await import("./useCalculatorState");

// Minimal renderHook implementation using React
const React = await import("react");
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");

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

describe("useCalculatorState", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns initial state with panel open by default", () => {
    const setSection = vi.fn();
    const { result, cleanup } = renderHook(() =>
      useCalculatorState({ section: "projections", setSection, meta: null })
    );

    expect(result.current!.calculatorPanelOpen).toBe(true);
    expect(result.current!.lastSuccessfulCalcRun).toBe(null);
    expect(result.current!.calculatorSettings).toBe(null);
    expect(typeof result.current!.scrollToCalculator).toBe("function");
    expect(typeof result.current!.openCalculatorPanel).toBe("function");
    expect(typeof result.current!.handleCalculationSuccess).toBe("function");
    cleanup();
  });

  it("openCalculatorPanel sets panel open and calls setSection", () => {
    const setSection = vi.fn();
    const { result, cleanup } = renderHook(() =>
      useCalculatorState({ section: "methodology", setSection, meta: null })
    );

    act(() => {
      result.current!.openCalculatorPanel("test_source");
    });

    expect(setSection).toHaveBeenCalledWith("projections");
    expect(result.current!.calculatorPanelOpen).toBe(true);
    cleanup();
  });
});
