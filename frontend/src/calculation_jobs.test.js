import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./request_helpers.js", async () => {
  const actual = await vi.importActual("./request_helpers.js");
  return {
    ...actual,
    sleepWithAbort: vi.fn(async () => {}),
  };
});

import { cancelCalculationJob, runCalculationJob } from "./calculation_jobs.js";

function jsonResponse(payload, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    text: async () => JSON.stringify(payload),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("runCalculationJob", () => {
  it("submits and polls jobs on same-origin API when apiBase is empty", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ job_id: "job-1", created_at: "2026-01-01T00:00:00Z" }, { status: 202 }))
      .mockResolvedValueOnce(jsonResponse({ status: "completed", result: { data: [], total: 0 } }));
    vi.stubGlobal("fetch", fetchMock);

    const onStatus = vi.fn();
    const onCompleted = vi.fn();
    const onCancelled = vi.fn();
    const onError = vi.fn();
    await runCalculationJob({
      apiBase: "",
      payload: { scoring_mode: "roto" },
      controller: new AbortController(),
      requestSeq: 1,
      requestSeqRef: { current: 1 },
      activeJobIdRef: { current: "" },
      timeoutSeconds: 60,
      onStatus,
      onCompleted,
      onCancelled,
      onError,
    });

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/calculate/jobs",
      expect.objectContaining({ method: "POST" })
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/calculate/jobs/job-1",
      expect.any(Object)
    );
    expect(onCompleted).toHaveBeenCalledWith(expect.objectContaining({ total: 0 }));
    expect(onCancelled).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it("continues polling same-origin status endpoint through running state", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ job_id: "job-2", created_at: "2026-01-01T00:00:00Z" }, { status: 202 }))
      .mockResolvedValueOnce(jsonResponse({ status: "running", started_at: "2026-01-01T00:00:10Z" }))
      .mockResolvedValueOnce(jsonResponse({ status: "completed", result: { data: [], total: 3 } }));
    vi.stubGlobal("fetch", fetchMock);

    const onStatus = vi.fn();
    const onCompleted = vi.fn();
    await runCalculationJob({
      apiBase: "",
      payload: { scoring_mode: "roto" },
      controller: new AbortController(),
      requestSeq: 1,
      requestSeqRef: { current: 1 },
      activeJobIdRef: { current: "" },
      timeoutSeconds: 60,
      onStatus,
      onCompleted,
      onCancelled: vi.fn(),
      onError: vi.fn(),
    });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      "/api/calculate/jobs/job-2",
      expect.any(Object)
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      "/api/calculate/jobs/job-2",
      expect.any(Object)
    );
    expect(onStatus).toHaveBeenCalledWith(expect.stringContaining("Running Monte Carlo simulations"));
    expect(onCompleted).toHaveBeenCalledWith(expect.objectContaining({ total: 3 }));
  });

  it("uses points-specific status messaging for points jobs", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ job_id: "job-points", created_at: "2026-01-01T00:00:00Z" }, { status: 202 }))
      .mockResolvedValueOnce(jsonResponse({ status: "running", started_at: "2026-01-01T00:00:10Z" }))
      .mockResolvedValueOnce(jsonResponse({ status: "completed", result: { data: [], total: 2 } }));
    vi.stubGlobal("fetch", fetchMock);

    const onStatus = vi.fn();
    const onCompleted = vi.fn();
    await runCalculationJob({
      apiBase: "",
      payload: { scoring_mode: "points" },
      controller: new AbortController(),
      requestSeq: 1,
      requestSeqRef: { current: 1 },
      activeJobIdRef: { current: "" },
      timeoutSeconds: 60,
      onStatus,
      onCompleted,
      onCancelled: vi.fn(),
      onError: vi.fn(),
    });

    expect(onStatus).toHaveBeenCalledWith(expect.stringContaining("Running points valuation"));
    expect(onCompleted).toHaveBeenCalledWith(expect.objectContaining({ total: 2 }));
  });

  it("rejects missing payloads before making requests", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const onError = vi.fn();

    await runCalculationJob({
      apiBase: "",
      payload: null,
      controller: new AbortController(),
      requestSeq: 1,
      requestSeqRef: { current: 1 },
      activeJobIdRef: { current: "" },
      timeoutSeconds: 60,
      onStatus: vi.fn(),
      onCompleted: vi.fn(),
      onCancelled: vi.fn(),
      onError,
    });

    expect(onError).toHaveBeenCalledWith("Invalid calculation request.");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("cancelCalculationJob", () => {
  it("uses same-origin API path when apiBase is empty", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    await cancelCalculationJob("", "job-3");

    expect(fetchMock).toHaveBeenCalledWith("/api/calculate/jobs/job-3", { method: "DELETE" });
  });
});
