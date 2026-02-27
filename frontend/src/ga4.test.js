import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("initGA4", () => {
  let originalCreateElement;
  let appendedScripts;

  beforeEach(() => {
    appendedScripts = [];
    originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag) => {
      const el = originalCreateElement(tag);
      if (tag === "script") appendedScripts.push(el);
      return el;
    });
    vi.spyOn(document.head, "appendChild").mockImplementation(() => {});
    window.dataLayer = undefined;
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  it("injects gtag script when measurement ID is set", async () => {
    vi.stubEnv("VITE_GA4_MEASUREMENT_ID", "G-TEST12345");
    const { initGA4 } = await import("./ga4.js");
    initGA4();
    expect(appendedScripts.length).toBe(1);
    expect(appendedScripts[0].src).toContain("gtag/js?id=G-TEST12345");
    expect(appendedScripts[0].async).toBe(true);
    expect(Array.isArray(window.dataLayer)).toBe(true);
    expect(window.dataLayer.length).toBeGreaterThan(0);
  });

  it("does nothing when measurement ID is empty", async () => {
    vi.stubEnv("VITE_GA4_MEASUREMENT_ID", "");
    const { initGA4 } = await import("./ga4.js");
    initGA4();
    expect(appendedScripts.length).toBe(0);
  });

  it("does nothing when measurement ID is not set", async () => {
    vi.stubEnv("VITE_GA4_MEASUREMENT_ID", "");
    const { initGA4 } = await import("./ga4.js");
    initGA4();
    expect(document.head.appendChild).not.toHaveBeenCalled();
  });
});
