import { describe, expect, it, vi, beforeEach } from "vitest";

vi.mock("../../../analytics", () => ({ trackEvent: vi.fn() }));
vi.mock("../../../download_filename", () => ({ parseDownloadFilename: vi.fn(() => "test.csv") }));
vi.mock("../../../download_helpers", () => ({ triggerBlobDownload: vi.fn() }));
vi.mock("../../../request_helpers", () => ({
  formatApiError: vi.fn(() => "Error occurred"),
  readResponsePayload: vi.fn(() => Promise.resolve({ payload: null, rawText: "" })),
}));

beforeEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
});

describe("useProjectionExport", () => {
  it("exports executeProjectionExportRequest function", async () => {
    const mod = await import("./useProjectionExport");
    expect(typeof mod.executeProjectionExportRequest).toBe("function");
  });

  it("exports useProjectionExport function", async () => {
    const mod = await import("./useProjectionExport");
    expect(typeof mod.useProjectionExport).toBe("function");
  });

  it("executeProjectionExportRequest calls fetch with correct URL", async () => {
    const { executeProjectionExportRequest } = await import("./useProjectionExport");
    const mockBlob = new Blob(["data"], { type: "text/csv" });
    const mockResponse = {
      ok: true,
      blob: vi.fn(() => Promise.resolve(mockBlob)),
      headers: new Headers({ "content-disposition": 'attachment; filename="test.csv"' }),
    };
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(mockResponse)));

    await executeProjectionExportRequest({
      endpointTab: "hitters",
      href: "/api/projections/export?tab=hitters",
      format: "csv",
      watchlistOnly: false,
      yearView: "2026",
      hasCalculatorOverlay: false,
    });

    expect(fetch).toHaveBeenCalledWith("/api/projections/export?tab=hitters", expect.objectContaining({
      cache: "no-store",
    }));

    vi.unstubAllGlobals();
  });

  it("executeProjectionExportRequest throws on non-ok response", async () => {
    const { executeProjectionExportRequest } = await import("./useProjectionExport");
    const mockResponse = {
      ok: false,
      status: 500,
      headers: new Headers(),
      blob: vi.fn(),
    };
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(mockResponse)));

    await expect(executeProjectionExportRequest({
      endpointTab: "hitters",
      href: "/api/projections/export",
      format: "csv",
      watchlistOnly: false,
      yearView: "2026",
      hasCalculatorOverlay: false,
    })).rejects.toThrow("Error occurred");

    vi.unstubAllGlobals();
  });

  it("useProjectionExport returns executeProjectionExport function", async () => {
    const { useProjectionExport } = await import("./useProjectionExport");
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

    const { result, cleanup } = renderHook(() => useProjectionExport());
    expect(typeof result.current!.executeProjectionExport).toBe("function");
    cleanup();
  });
});
