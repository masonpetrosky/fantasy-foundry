import { afterEach, describe, expect, it, vi } from "vitest";
import {
  buildAnalyticsPayload,
  resetAnalyticsContext,
  setAnalyticsContext,
  trackEvent,
} from "./analytics.js";

describe("analytics", () => {
  const originalWindow = globalThis.window;

  afterEach(() => {
    resetAnalyticsContext();
    if (typeof originalWindow === "undefined") {
      delete globalThis.window;
    } else {
      globalThis.window = originalWindow;
    }
  });

  it("builds payloads with normalized properties", () => {
    const payload = buildAnalyticsPayload("quickstart_click", {
      source: " onboarding_strip ",
      mode: "roto",
      ignored: "",
      attempts: 2,
      enabled: true,
    });

    expect(payload?.event).toBe("quickstart_click");
    expect(payload?.properties).toMatchObject({
      source: "onboarding_strip",
      mode: "roto",
      attempts: 2,
      enabled: true,
      is_signed_in: false,
      scoring_mode: "unknown",
      section: "unknown",
      data_version: "unknown",
    });
    expect(payload?.properties.session_id).toMatch(/^ffs-/);
    expect(typeof payload?.timestamp).toBe("number");
  });

  it("publishes events to dataLayer and CustomEvent listeners in browser contexts", () => {
    const dataLayer = [];
    const dispatchEvent = vi.fn();
    class MockCustomEvent {
      constructor(name, options) {
        this.name = name;
        this.detail = options?.detail;
      }
    }

    globalThis.window = {
      dataLayer,
      dispatchEvent,
      CustomEvent: MockCustomEvent,
    };

    setAnalyticsContext({
      section: "projections",
      scoring_mode: "points",
      is_signed_in: true,
      data_version: "v-test",
    });
    const payload = trackEvent("export_click", { format: "csv", tab: "all" });

    expect(payload?.event).toBe("export_click");
    expect(dataLayer).toHaveLength(1);
    expect(dataLayer[0]).toMatchObject({
      event: "export_click",
      format: "csv",
      tab: "all",
      section: "projections",
      scoring_mode: "points",
      is_signed_in: true,
      data_version: "v-test",
    });
    expect(dataLayer[0].session_id).toMatch(/^ffs-/);
    expect(dispatchEvent).toHaveBeenCalledTimes(1);
    expect(dispatchEvent.mock.calls[0][0].name).toBe("ff:analytics");
    expect(dispatchEvent.mock.calls[0][0].detail.event).toBe("export_click");
  });
});
