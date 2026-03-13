import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../app_state_storage", () => ({
  stablePlayerKeyFromRow: vi.fn((row: Record<string, unknown>) =>
    row?.mlbam_id ? `mlbam:${row.mlbam_id}` : ""
  ),
}));

const React = await import("react");
const { createRoot } = await import("react-dom/client");
const { act } = await import("react");

const { useCalculatorOverlay } = await import("./useCalculatorOverlay");

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

describe("useCalculatorOverlay", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns initial state with empty overlay", () => {
    const { result, cleanup } = renderHook(() => useCalculatorOverlay("v1"));
    expect(result.current!.calculatorOverlayByPlayerKey).toEqual({});
    expect(result.current!.calculatorOverlayActive).toBe(false);
    expect(result.current!.calculatorOverlayJobId).toBe("");
    expect(result.current!.calculatorOverlaySummary).toBeNull();
    expect(result.current!.calculatorOverlayPlayerCount).toBe(0);
    expect(result.current!.calculatorResultRows).toEqual([]);
    cleanup();
  });

  it("applyCalculatorOverlay with valid result data sets overlay active", () => {
    const { result, cleanup } = renderHook(() => useCalculatorOverlay("v1"));
    const mockResult = {
      data: [
        { mlbam_id: "123", DynastyValue: 42, Value_HR: 5 },
      ],
    };
    act(() => {
      result.current!.applyCalculatorOverlay(mockResult, { scoring_mode: "roto", start_year: 2026, horizon: 20 }, { jobId: "job1" });
    });
    expect(result.current!.calculatorOverlayActive).toBe(true);
    expect(result.current!.calculatorOverlayJobId).toBe("job1");
    expect(result.current!.calculatorOverlayPlayerCount).toBe(1);
    cleanup();
  });

  it("applyCalculatorOverlay extracts DynastyValue and Value_*/StatDynasty_* columns", () => {
    const { result, cleanup } = renderHook(() => useCalculatorOverlay("v1"));
    const mockResult = {
      data: [
        {
          mlbam_id: "456",
          DynastyValue: 100,
          Value_HR: 10,
          StatDynasty_AVG: 0.3,
          Name: "Player A",
          Team: "NYY",
        },
      ],
    };
    act(() => {
      result.current!.applyCalculatorOverlay(mockResult, { scoring_mode: "roto" }, { jobId: "j2" });
    });
    const overlay = result.current!.calculatorOverlayByPlayerKey["mlbam:456"];
    expect(overlay).toBeDefined();
    expect(overlay.DynastyValue).toBe(100);
    expect(overlay.Value_HR).toBe(10);
    expect(overlay.StatDynasty_AVG).toBe(0.3);
    // Non-overlay columns should not be present
    expect(overlay.Name).toBeUndefined();
    expect(overlay.Team).toBeUndefined();
    cleanup();
  });

  it("clearCalculatorOverlay resets all state", () => {
    const { result, cleanup } = renderHook(() => useCalculatorOverlay("v1"));
    act(() => {
      result.current!.applyCalculatorOverlay(
        { data: [{ mlbam_id: "1", DynastyValue: 5 }] },
        { scoring_mode: "roto", start_year: 2026, horizon: 20 },
        { jobId: "j3" }
      );
    });
    expect(result.current!.calculatorOverlayActive).toBe(true);
    act(() => {
      result.current!.clearCalculatorOverlay();
    });
    expect(result.current!.calculatorOverlayActive).toBe(false);
    expect(result.current!.calculatorOverlayByPlayerKey).toEqual({});
    expect(result.current!.calculatorOverlaySummary).toBeNull();
    expect(result.current!.calculatorResultRows).toEqual([]);
    cleanup();
  });

  it("applyCalculatorOverlay with empty data keeps overlay inactive", () => {
    const { result, cleanup } = renderHook(() => useCalculatorOverlay("v1"));
    act(() => {
      result.current!.applyCalculatorOverlay({ data: [] }, { scoring_mode: "roto" }, { jobId: "j4" });
    });
    expect(result.current!.calculatorOverlayActive).toBe(false);
    cleanup();
  });

  it("applyCalculatorOverlay sets summary with scoring mode, start year, horizon", () => {
    const { result, cleanup } = renderHook(() => useCalculatorOverlay("v1"));
    act(() => {
      result.current!.applyCalculatorOverlay(
        { data: [{ mlbam_id: "7", DynastyValue: 50 }] },
        { scoring_mode: "points", start_year: 2027, horizon: 10 },
        { jobId: "j5" }
      );
    });
    expect(result.current!.calculatorOverlaySummary).toEqual({
      scoringMode: "points",
      startYear: 2027,
      horizon: 10,
    });
    cleanup();
  });
});
