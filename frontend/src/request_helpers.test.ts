import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { formatApiError, readResponsePayload, sleepWithAbort, useDebouncedValue } from "./request_helpers";

describe("formatApiError", () => {
  it("returns detail string when present", () => {
    expect(formatApiError(500, { detail: "Internal error" })).toBe(
      "Server error 500: Internal error"
    );
  });

  it("includes request id when present", () => {
    expect(formatApiError(500, { detail: "Internal error", request_id: "req-123" })).toBe(
      "Server error 500: Internal error (request id: req-123)"
    );
  });

  it("returns validation error for array detail", () => {
    const payload = { detail: [{ msg: "field required" }] };
    expect(formatApiError(422, payload)).toBe(
      "Validation error (422): field required"
    );
  });

  it("returns raw text when payload has no detail", () => {
    expect(formatApiError(500, {}, "Something broke")).toBe(
      "Server error 500: Something broke"
    );
  });

  it("returns status-only message as fallback", () => {
    expect(formatApiError(500, null)).toBe("Server error: 500");
  });

  it("ignores HTML raw text", () => {
    expect(formatApiError(502, null, "<html>Bad Gateway</html>")).toBe(
      "Server error: 502"
    );
  });

  it("ignores empty detail string", () => {
    expect(formatApiError(400, { detail: "  " })).toBe("Server error: 400");
  });
});

describe("readResponsePayload", () => {
  it("parses JSON response", async () => {
    const response = { text: () => Promise.resolve('{"ok":true}') };
    const { payload, rawText } = await readResponsePayload(response);
    expect(payload).toEqual({ ok: true });
    expect(rawText).toBe('{"ok":true}');
  });

  it("returns null payload for non-JSON", async () => {
    const response = { text: () => Promise.resolve("not json") };
    const { payload, rawText } = await readResponsePayload(response);
    expect(payload).toBeNull();
    expect(rawText).toBe("not json");
  });

  it("handles empty response body", async () => {
    const response = { text: () => Promise.resolve("") };
    const { payload, rawText } = await readResponsePayload(response);
    expect(payload).toBeNull();
    expect(rawText).toBe("");
  });
});

describe("sleepWithAbort", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("resolves after delay with no signal", async () => {
    const p = sleepWithAbort(100);
    vi.advanceTimersByTime(100);
    await expect(p).resolves.toBeUndefined();
  });

  it("rejects immediately if signal already aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    await expect(sleepWithAbort(100, controller.signal)).rejects.toThrow(
      "Aborted"
    );
  });

  it("rejects when signal aborts during sleep", async () => {
    const controller = new AbortController();
    const p = sleepWithAbort(1000, controller.signal);
    controller.abort();
    await expect(p).rejects.toThrow("Aborted");
  });
});

describe("useDebouncedValue", () => {
  it("is exported as a function", () => {
    expect(typeof useDebouncedValue).toBe("function");
  });

  it("returns initial value immediately", async () => {
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

    const { result, cleanup } = renderHook(() => useDebouncedValue("hello", 300));
    expect(result.current).toBe("hello");
    cleanup();
  });
});
