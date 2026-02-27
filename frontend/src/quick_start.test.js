import { beforeEach, describe, expect, it, vi } from "vitest";

const { trackEventMock } = vi.hoisted(() => ({
  trackEventMock: vi.fn(),
}));

vi.mock("./analytics", () => ({
  trackEvent: trackEventMock,
}));

import {
  normalizeQuickStartMode,
  runQuickStartFlow,
  trackQuickStartClick,
  trackQuickStartImpression,
} from "./quick_start.js";

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
      section: "projections",
      dataVersion: "v-main",
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
      is_first_run: true,
      section: "projections",
      data_version: "v-main",
    });
    expect(trackEventMock).toHaveBeenNthCalledWith(2, "quickstart_click", {
      source: "hero_cta",
      mode: "points",
      is_first_run: true,
      section: "projections",
      data_version: "v-main",
    });
    expect(openCalculatorPanel).toHaveBeenCalledWith("hero_cta");
    expect(setPendingQuickStartMode).toHaveBeenCalledWith("points");
    expect(scheduleFrame).toHaveBeenCalledTimes(1);
    expect(scrollToCalculator).toHaveBeenCalledTimes(1);
    expect(focusCalculator).toHaveBeenCalledTimes(1);
  });

  it("can emit canonical click event without aliases", () => {
    trackQuickStartClick({
      mode: "roto",
      source: "activation_strip",
      isFirstRun: false,
      section: "projections",
      dataVersion: "v-test",
      emitAliasEvents: false,
    });

    expect(trackEventMock).toHaveBeenCalledTimes(1);
    expect(trackEventMock).toHaveBeenCalledWith("ff_quickstart_cta_click", {
      source: "activation_strip",
      mode: "roto",
      is_first_run: false,
      section: "projections",
      data_version: "v-test",
    });
  });

  it("tracks quick start impressions with canonical + alias events", () => {
    trackQuickStartImpression({
      source: "activation_strip",
      mode: "roto",
      isFirstRun: true,
      section: "projections",
      dataVersion: "v-42",
      emitAliasEvents: true,
    });

    expect(trackEventMock).toHaveBeenNthCalledWith(1, "ff_quickstart_impression", {
      source: "activation_strip",
      mode: "roto",
      is_first_run: true,
      section: "projections",
      data_version: "v-42",
    });
    expect(trackEventMock).toHaveBeenNthCalledWith(2, "quickstart_impression", {
      source: "activation_strip",
      mode: "roto",
      is_first_run: true,
      section: "projections",
      data_version: "v-42",
    });
  });
});
