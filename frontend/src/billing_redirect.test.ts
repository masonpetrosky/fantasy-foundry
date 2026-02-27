import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { parseBillingRedirectParam, cleanBillingParam } from "./billing_redirect";

describe("parseBillingRedirectParam", () => {
  it("returns 'success' for ?billing=success", () => {
    expect(parseBillingRedirectParam("?billing=success")).toBe("success");
  });

  it("returns 'cancel' for ?billing=cancel", () => {
    expect(parseBillingRedirectParam("?billing=cancel")).toBe("cancel");
  });

  it("is case-insensitive", () => {
    expect(parseBillingRedirectParam("?billing=SUCCESS")).toBe("success");
    expect(parseBillingRedirectParam("?billing=Cancel")).toBe("cancel");
  });

  it("trims whitespace", () => {
    expect(parseBillingRedirectParam("?billing= success ")).toBe("success");
  });

  it("returns null for missing param", () => {
    expect(parseBillingRedirectParam("")).toBeNull();
    expect(parseBillingRedirectParam("?foo=bar")).toBeNull();
  });

  it("returns null for unrecognized values", () => {
    expect(parseBillingRedirectParam("?billing=pending")).toBeNull();
    expect(parseBillingRedirectParam("?billing=")).toBeNull();
  });

  it("handles null/undefined search gracefully", () => {
    expect(parseBillingRedirectParam(null)).toBeNull();
    expect(parseBillingRedirectParam(undefined)).toBeNull();
  });
});

describe("cleanBillingParam", () => {
  let originalLocation: string;
  let replaceStateSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    originalLocation = window.location.href;
    replaceStateSpy = vi.spyOn(window.history, "replaceState");
  });

  afterEach(() => {
    replaceStateSpy.mockRestore();
    // Reset location to avoid test pollution
    window.history.replaceState({}, "", originalLocation);
  });

  it("removes billing param from the URL", () => {
    window.history.replaceState({}, "", "/?billing=success");
    cleanBillingParam();
    expect(replaceStateSpy).toHaveBeenCalled();
    const calledUrl = replaceStateSpy.mock.calls[replaceStateSpy.mock.calls.length - 1]?.[2];
    expect(calledUrl).not.toContain("billing=");
  });

  it("does nothing when billing param is absent", () => {
    window.history.replaceState({}, "", "/");
    replaceStateSpy.mockClear();
    cleanBillingParam();
    expect(replaceStateSpy).not.toHaveBeenCalled();
  });

  it("preserves other query params", () => {
    window.history.replaceState({}, "", "/?foo=bar&billing=cancel&baz=1");
    cleanBillingParam();
    const calledUrl = replaceStateSpy.mock.calls[replaceStateSpy.mock.calls.length - 1]?.[2];
    expect(calledUrl).toContain("foo=bar");
    expect(calledUrl).toContain("baz=1");
    expect(calledUrl).not.toContain("billing=");
  });
});
