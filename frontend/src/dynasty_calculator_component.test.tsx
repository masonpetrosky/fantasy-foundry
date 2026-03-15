import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockRunCalculationJob = vi.fn(() => Promise.resolve());
const mockCancelCalculationJob = vi.fn(() => Promise.resolve());
vi.mock("./calculation_jobs", () => ({
  runCalculationJob: (...args: unknown[]) => mockRunCalculationJob(...args),
  cancelCalculationJob: (...args: unknown[]) => mockCancelCalculationJob(...args),
}));

vi.mock("./analytics", () => ({
  trackEvent: vi.fn(),
}));

vi.mock("./quick_start", () => ({
  trackQuickStartClick: vi.fn(),
}));

vi.mock("./app_state_storage", () => ({
  CALC_LINK_QUERY_PARAM: "calc_link",
  decodeCalculatorSettings: vi.fn(() => null),
  encodeCalculatorSettings: vi.fn(() => "encoded"),
  mergeKnownCalculatorSettings: vi.fn(
    (current: Record<string, unknown>, incoming: Record<string, unknown>) => ({ ...current, ...incoming }),
  ),
  readSessionFirstRunLandingTimestamp: vi.fn(() => null),
  readSessionFirstRunSuccessRecorded: vi.fn(() => false),
  writeSessionFirstRunSuccessRecorded: vi.fn(),
}));

const mockApplyOverlay = vi.fn();
const mockClearOverlay = vi.fn();
vi.mock("./contexts/CalculatorOverlayContext", () => ({
  useCalculatorOverlayContext: () => ({
    applyCalculatorOverlay: mockApplyOverlay,
    clearCalculatorOverlay: mockClearOverlay,
    calculatorOverlayActive: false,
    calculatorResultRows: [],
  }),
}));

// Capture sidebar props so we can invoke actions in tests
let capturedSidebarProps: Record<string, unknown> | null = null;
vi.mock("./dynasty_calculator_sidebar", () => ({
  DynastyCalculatorSidebar: (props: Record<string, unknown>) => {
    capturedSidebarProps = props;
    return React.createElement("div", { "data-testid": "sidebar" });
  },
}));

import { DynastyCalculator } from "./dynasty_calculator";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function renderToContainer(element: React.ReactElement): { container: HTMLDivElement; cleanup: () => void } {
  const container = document.createElement("div");
  document.body.appendChild(container);
  let root: ReturnType<typeof createRoot>;
  act(() => {
    root = createRoot(container);
    root.render(element);
  });
  return {
    container,
    cleanup: () => {
      act(() => root.unmount());
      document.body.removeChild(container);
    },
  };
}

function makeDefaultProps() {
  return {
    apiBase: "http://localhost:8000",
    meta: { years: [2026, 2027, 2028] },
    presets: {} as Record<string, Record<string, unknown>>,
    setPresets: vi.fn(),
    hasSuccessfulRun: false,
    onCalculationSuccess: vi.fn(),
    onSettingsChange: vi.fn(),
    onRegisterQuickStartRunner: vi.fn(),
    onOpenMethodologyGlossary: vi.fn(),
    tierLimits: null,
    fantrax: null,
  };
}

function getSidebarActions(): Record<string, (...args: unknown[]) => unknown> {
  return (capturedSidebarProps as Record<string, unknown>)?.actions as Record<string, (...args: unknown[]) => unknown>;
}

function getSidebarState(): Record<string, unknown> {
  return (capturedSidebarProps as Record<string, unknown>)?.state as Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DynastyCalculator component", () => {
  let cleanup: () => void;

  beforeEach(() => {
    capturedSidebarProps = null;
    mockRunCalculationJob.mockReset();
    mockCancelCalculationJob.mockReset();
    mockApplyOverlay.mockReset();
    mockClearOverlay.mockReset();
    mockRunCalculationJob.mockReturnValue(Promise.resolve());
    mockCancelCalculationJob.mockReturnValue(Promise.resolve());
  });

  afterEach(() => {
    if (cleanup) cleanup();
  });

  it("renders the sidebar with default state", () => {
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));
    expect(capturedSidebarProps).not.toBeNull();
    const state = getSidebarState();
    expect(state.loading).toBe(false);
    expect(state.isPointsMode).toBe(false);
    expect(state.statusIsError).toBe(false);
  });

  it("calls onSettingsChange when settings update", () => {
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));
    const actions = getSidebarActions();
    act(() => {
      actions.update("teams", 14);
    });
    expect(props.onSettingsChange).toHaveBeenCalled();
    const lastCall = props.onSettingsChange.mock.calls[props.onSettingsChange.mock.calls.length - 1][0];
    expect(lastCall.teams).toBe(14);
  });

  it("switches scoring mode via applyScoringSetup", () => {
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));
    act(() => {
      getSidebarActions().applyScoringSetup("points");
    });
    const state = getSidebarState();
    expect(state.isPointsMode).toBe(true);
  });

  it("saves preset when name is set via sidebar state", () => {
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));

    // Set preset name first
    act(() => {
      getSidebarActions().setPresetName("My Preset");
    });
    // After re-render, the sidebar state should have the name
    expect(getSidebarState().presetName).toBe("My Preset");
    expect(getSidebarState().canSavePreset).toBe(true);

    // Now save — must use fresh actions reference after re-render
    act(() => {
      getSidebarActions().savePreset();
    });
    expect(props.setPresets).toHaveBeenCalled();
    const state = getSidebarState();
    expect(state.presetStatus).toContain("preset");
  });

  it("reports error when saving preset with empty name", () => {
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));
    act(() => {
      getSidebarActions().savePreset();
    });
    const state = getSidebarState();
    expect(state.presetStatus).toContain("Error");
  });

  it("deletes a preset after confirm", () => {
    const props = makeDefaultProps();
    props.presets = { TestPreset: { teams: 10 } };
    vi.spyOn(window, "confirm").mockReturnValue(true);
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));
    act(() => {
      getSidebarActions().deletePreset("TestPreset");
    });
    expect(props.setPresets).toHaveBeenCalled();
    vi.restoreAllMocks();
  });

  it("triggers run and transitions loading state", async () => {
    let resolveJob: () => void;
    mockRunCalculationJob.mockImplementation(() => new Promise<void>(r => { resolveJob = r; }));
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));

    act(() => {
      getSidebarActions().run();
    });
    expect(getSidebarState().loading).toBe(true);
    expect(getSidebarState().status).toBe("Submitting simulation...");

    // Simulate completion via the onCompleted callback
    const jobCallArgs = mockRunCalculationJob.mock.calls[0][0] as Record<string, unknown>;
    const onCompleted = jobCallArgs.onCompleted as (result: Record<string, unknown>, meta?: Record<string, unknown>) => void;
    act(() => {
      onCompleted({ total: 250, data: [] }, { jobId: "job-1" });
    });
    await act(async () => { resolveJob!(); });

    expect(getSidebarState().loading).toBe(false);
    expect(getSidebarState().status).toContain("250 players");
    expect(props.onCalculationSuccess).toHaveBeenCalled();
    expect(mockApplyOverlay).toHaveBeenCalled();
  });

  it("shows error status on run failure", async () => {
    mockRunCalculationJob.mockImplementation(() => Promise.resolve());
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));

    act(() => {
      getSidebarActions().run();
    });

    const jobCallArgs = mockRunCalculationJob.mock.calls[0][0] as Record<string, unknown>;
    const onError = jobCallArgs.onError as (message: string) => void;
    act(() => {
      onError("Timeout exceeded");
    });
    expect(getSidebarState().loading).toBe(false);
    expect(getSidebarState().status).toContain("Timeout exceeded");
    expect(getSidebarState().statusIsError).toBe(true);
  });

  it("aborts controller on unmount when a run is active", () => {
    mockRunCalculationJob.mockImplementation(() => new Promise<void>(() => {}));
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));

    act(() => {
      getSidebarActions().run();
    });
    expect(getSidebarState().loading).toBe(true);

    // Simulate the job having set an active job id via the onStatus callback
    const jobCallArgs = mockRunCalculationJob.mock.calls[0][0] as Record<string, unknown>;
    const activeJobIdRef = jobCallArgs.activeJobIdRef as { current: string };
    activeJobIdRef.current = "test-job-123";

    // Unmount should trigger cleanup
    cleanup();
    // @ts-expect-error cleanup already called
    cleanup = undefined;
    expect(mockCancelCalculationJob).toHaveBeenCalledWith(
      "http://localhost:8000",
      "test-job-123",
    );
  });

  it("applies quick start and triggers run", () => {
    mockRunCalculationJob.mockImplementation(() => Promise.resolve());
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));

    act(() => {
      getSidebarActions().applyQuickStartAndRun("roto");
    });
    expect(mockRunCalculationJob).toHaveBeenCalled();
    // run() overwrites status to "Submitting simulation...", so check that the run was triggered
    expect(getSidebarState().loading).toBe(true);
  });

  it("registers quick start runner callback", () => {
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));
    expect(props.onRegisterQuickStartRunner).toHaveBeenCalled();
    const registeredRunner = props.onRegisterQuickStartRunner.mock.calls[0][0];
    expect(typeof registeredRunner).toBe("function");
  });

  it("clears overlay when clearAppliedValues is called", () => {
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));
    act(() => {
      getSidebarActions().clearAppliedValues();
    });
    expect(mockClearOverlay).toHaveBeenCalled();
  });

  it("enforces tier sims limit", () => {
    const props = makeDefaultProps();
    props.tierLimits = { maxSims: 100, allowPointsMode: true, allowTradeAnalyzer: true } as Record<string, unknown>;
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));
    // Default sims is 300 via buildDefaultCalculatorSettings; tier caps it to 100
    const lastSettingsCall = props.onSettingsChange.mock.calls[props.onSettingsChange.mock.calls.length - 1];
    if (lastSettingsCall) {
      expect(lastSettingsCall[0].sims).toBeLessThanOrEqual(100);
    }
  });

  it("forces roto mode when points mode is disallowed by tier", () => {
    const props = makeDefaultProps();
    props.tierLimits = { maxSims: 1000, allowPointsMode: false, allowTradeAnalyzer: false } as Record<string, unknown>;
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));

    // Try switching to points - should be forced back to roto
    act(() => {
      getSidebarActions().applyScoringSetup("points");
    });
    // The tier limit effect should force it back to roto
    act(() => {});
    expect(getSidebarState().isPointsMode).toBe(false);
  });

  it("handles cancelled calculation", () => {
    mockRunCalculationJob.mockImplementation(() => Promise.resolve());
    const props = makeDefaultProps();
    ({ cleanup } = renderToContainer(React.createElement(DynastyCalculator, props)));

    act(() => {
      getSidebarActions().run();
    });
    const jobCallArgs = mockRunCalculationJob.mock.calls[0][0] as Record<string, unknown>;
    const onCancelled = jobCallArgs.onCancelled as () => void;
    act(() => {
      onCancelled();
    });
    expect(getSidebarState().loading).toBe(false);
    expect(getSidebarState().status).toBe("Calculation cancelled.");
  });
});
