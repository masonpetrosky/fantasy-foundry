import { beforeEach, describe, expect, it, vi } from "vitest";

const { trackEventMock } = vi.hoisted(() => ({
  trackEventMock: vi.fn(),
}));

vi.mock("./analytics.js", () => ({
  trackEvent: trackEventMock,
}));

import { normalizeQuickStartMode, runQuickStartFlow } from "./quick_start.js";

describe("quick_start", () => {
  beforeEach(() => {
    trackEventMock.mockReset();
  });

  it("normalizes unknown quick start modes to roto", () => {
    expect(normalizeQuickStartMode("points")).toBe("points");
    expect(normalizeQuickStartMode("roto")).toBe("roto");
    expect(normalizeQuickStartMode("other")).toBe("roto");
  });

  it("tracks onboarding quick start click and runs the flow callbacks", () => {
    const openCalculatorPanel = vi.fn();
    const setPendingQuickStartMode = vi.fn();
    const scrollToCalculator = vi.fn();
    const focusCalculator = vi.fn();
    const scheduleFrame = vi.fn(callback => callback());

    const mode = runQuickStartFlow({
      mode: "points",
      source: "hero_cta",
      openCalculatorPanel,
      setPendingQuickStartMode,
      scrollToCalculator,
      focusCalculator,
      scheduleFrame,
    });

    expect(mode).toBe("points");
    expect(trackEventMock).toHaveBeenNthCalledWith(1, "ff_quickstart_cta_click", {
      source: "hero_cta",
      mode: "points",
    });
    expect(trackEventMock).toHaveBeenNthCalledWith(2, "ff_onboarding_cta_click", {
      source: "hero_cta",
      mode: "points",
    });
    expect(trackEventMock).toHaveBeenNthCalledWith(3, "quickstart_click", {
      source: "hero_cta",
      mode: "points",
    });
    expect(openCalculatorPanel).toHaveBeenCalledWith("hero_cta");
    expect(setPendingQuickStartMode).toHaveBeenCalledWith("points");
    expect(scheduleFrame).toHaveBeenCalledTimes(1);
    expect(scrollToCalculator).toHaveBeenCalledTimes(1);
    expect(focusCalculator).toHaveBeenCalledTimes(1);
  });
});
