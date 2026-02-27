import { afterEach, describe, expect, it, vi } from "vitest";

import {
  MOBILE_BREAKPOINT_QUERY,
  readInitialMobileLayoutMode,
  resolveProjectionHorizontalAffordance,
} from "./useProjectionLayoutState";

function stubWindow({ savedLayout = "", matches = false } = {}) {
  const storage: Record<string, string> = {};
  if (savedLayout) storage["ff:proj-mobile-layout-mode:v2"] = savedLayout;
  vi.stubGlobal("window", {
    localStorage: {
      getItem: vi.fn((key: string) => (Object.prototype.hasOwnProperty.call(storage, key) ? storage[key] : null)),
      setItem: vi.fn(),
    },
    matchMedia: vi.fn((query: string) => ({
      media: query,
      matches,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })),
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("readInitialMobileLayoutMode", () => {
  it("returns saved layout mode when persisted", () => {
    stubWindow({ savedLayout: "table", matches: true });
    expect(readInitialMobileLayoutMode()).toBe("table");
  });

  it("uses viewport matchMedia fallback when no saved layout exists", () => {
    stubWindow({ matches: true });
    expect(readInitialMobileLayoutMode()).toBe("cards");

    stubWindow({ matches: false });
    expect(readInitialMobileLayoutMode()).toBe("table");
  });

  it("queries the expected mobile breakpoint", () => {
    stubWindow({ matches: false });
    readInitialMobileLayoutMode();
    expect(window.matchMedia).toHaveBeenCalledWith(MOBILE_BREAKPOINT_QUERY);
  });
});

describe("resolveProjectionHorizontalAffordance", () => {
  it("returns no affordance for non-mobile or missing element", () => {
    expect(resolveProjectionHorizontalAffordance(null, true)).toEqual({
      canScrollLeft: false,
      canScrollRight: false,
    });
    expect(resolveProjectionHorizontalAffordance({ scrollWidth: 1000, clientWidth: 400, scrollLeft: 10 } as HTMLElement, false)).toEqual({
      canScrollLeft: false,
      canScrollRight: false,
    });
  });

  it("returns left/right affordance based on scroll position", () => {
    const base = { scrollWidth: 1000, clientWidth: 400, scrollLeft: 0 } as HTMLElement;
    expect(resolveProjectionHorizontalAffordance(base, true)).toEqual({
      canScrollLeft: false,
      canScrollRight: true,
    });

    expect(resolveProjectionHorizontalAffordance({ ...base, scrollLeft: 200 } as HTMLElement, true)).toEqual({
      canScrollLeft: true,
      canScrollRight: true,
    });

    expect(resolveProjectionHorizontalAffordance({ ...base, scrollLeft: 600 } as HTMLElement, true)).toEqual({
      canScrollLeft: true,
      canScrollRight: false,
    });
  });
});
