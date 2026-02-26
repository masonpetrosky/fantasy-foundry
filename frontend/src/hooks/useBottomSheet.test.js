import { afterEach, describe, expect, it, vi } from "vitest";

import { prefersReducedMotion } from "./useBottomSheet.js";

function stubMatchMedia(matches = false) {
  vi.stubGlobal("window", {
    ...window,
    matchMedia: vi.fn(() => ({ matches })),
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("prefersReducedMotion", () => {
  it("returns false when no preference set", () => {
    stubMatchMedia(false);
    expect(prefersReducedMotion()).toBe(false);
  });

  it("returns true when reduce motion is preferred", () => {
    stubMatchMedia(true);
    expect(prefersReducedMotion()).toBe(true);
  });

  it("queries the correct media query", () => {
    stubMatchMedia(false);
    prefersReducedMotion();
    expect(window.matchMedia).toHaveBeenCalledWith("(prefers-reduced-motion: reduce)");
  });
});
