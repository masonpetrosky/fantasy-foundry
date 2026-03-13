import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("../view_state", () => ({
  buildOverlayStatusMeta: vi.fn(() => ({ stale: false, summary: "" })),
}));
vi.mock("../../../app_state_storage", () => ({
  stablePlayerKeyFromRow: vi.fn((row: Record<string, unknown>) => row?.mlbam_id ? `mlbam:${row.mlbam_id}` : ""),
}));

import type { UseProjectionOverlayInput } from "./useProjectionOverlay";

function makeInput(overrides: Partial<UseProjectionOverlayInput> = {}): UseProjectionOverlayInput {
  return {
    calculatorOverlayByPlayerKey: null,
    calculatorOverlayActive: false,
    calculatorOverlayJobId: "",
    calculatorOverlayDataVersion: null,
    calculatorOverlayPlayerCount: null,
    calculatorOverlaySummary: null,
    dataVersion: null,
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

describe("useProjectionOverlay", () => {
  it("returns hasCalculatorOverlay false when inactive", async () => {
    const { useProjectionOverlay } = await import("./useProjectionOverlay");
    const { renderHook } = await setupRenderHook();
    const input = makeInput({ calculatorOverlayActive: false });
    const { result, cleanup } = renderHook(() => useProjectionOverlay(input));
    expect(result.current!.hasCalculatorOverlay).toBe(false);
    cleanup();
  });

  it("returns hasCalculatorOverlay true when active with player data", async () => {
    const { useProjectionOverlay } = await import("./useProjectionOverlay");
    const { renderHook } = await setupRenderHook();
    const input = makeInput({
      calculatorOverlayActive: true,
      calculatorOverlayByPlayerKey: { "mlbam:123": { mlbam_id: 123 } as never },
      calculatorOverlayPlayerCount: 1,
    });
    const { result, cleanup } = renderHook(() => useProjectionOverlay(input));
    expect(result.current!.hasCalculatorOverlay).toBe(true);
    cleanup();
  });

  it("resolvedCalculatorOverlayPlayerCount counts overlay keys", async () => {
    const { useProjectionOverlay } = await import("./useProjectionOverlay");
    const { renderHook } = await setupRenderHook();
    const input = makeInput({
      calculatorOverlayActive: true,
      calculatorOverlayPlayerCount: undefined,
      calculatorOverlayByPlayerKey: {
        "mlbam:1": {} as never,
        "mlbam:2": {} as never,
        "mlbam:3": {} as never,
      },
    });
    const { result, cleanup } = renderHook(() => useProjectionOverlay(input));
    expect(result.current!.resolvedCalculatorOverlayPlayerCount).toBe(3);
    cleanup();
  });

  it("applyCalculatorOverlayToRows returns empty array for empty input", async () => {
    const { useProjectionOverlay } = await import("./useProjectionOverlay");
    const { renderHook } = await setupRenderHook();
    const input = makeInput();
    const { result, cleanup } = renderHook(() => useProjectionOverlay(input));
    expect(result.current!.applyCalculatorOverlayToRows([])).toEqual([]);
    cleanup();
  });

  it("applyCalculatorOverlayToRows merges overlay data when active", async () => {
    const { useProjectionOverlay } = await import("./useProjectionOverlay");
    const { renderHook } = await setupRenderHook();
    const overlayData = { dynasty_value: 42 };
    const input = makeInput({
      calculatorOverlayActive: true,
      calculatorOverlayByPlayerKey: { "mlbam:100": overlayData as never },
      calculatorOverlayPlayerCount: 1,
    });
    const { result, cleanup } = renderHook(() => useProjectionOverlay(input));
    const rows = [{ mlbam_id: 100, Name: "Test Player" }] as never[];
    const merged = result.current!.applyCalculatorOverlayToRows(rows);
    expect(merged).toHaveLength(1);
    expect(merged[0]).toMatchObject({ mlbam_id: 100, dynasty_value: 42, DynastyMatchStatus: "matched" });
    cleanup();
  });

  it("showOverlayWhy defaults to false", async () => {
    const { useProjectionOverlay } = await import("./useProjectionOverlay");
    const { renderHook } = await setupRenderHook();
    const input = makeInput();
    const { result, cleanup } = renderHook(() => useProjectionOverlay(input));
    expect(result.current!.showOverlayWhy).toBe(false);
    cleanup();
  });
});
