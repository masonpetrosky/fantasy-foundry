import { afterEach, describe, expect, it, vi } from "vitest";
import {
  analyticsEventsToCsv,
  buildAnalyticsPayload,
  clearAnalyticsEventBuffer,
  downloadAnalyticsEventCsv,
  installAnalyticsDebugBridge,
  readAnalyticsEventBuffer,
  resetAnalyticsContext,
  setAnalyticsContext,
  summarizeActivationFunnel,
  trackEvent,
} from "./analytics";

describe("analytics", () => {
  const originalWindow = globalThis.window;
  const originalDocument = globalThis.document;
  const originalUrl = globalThis.URL;

  afterEach(() => {
    resetAnalyticsContext();
    if (typeof originalWindow === "undefined") {
      delete (globalThis as Record<string, unknown>).window;
    } else {
      globalThis.window = originalWindow;
    }
    if (typeof originalDocument === "undefined") {
      delete (globalThis as Record<string, unknown>).document;
    } else {
      globalThis.document = originalDocument;
    }
    if (typeof originalUrl === "undefined") {
      delete (globalThis as Record<string, unknown>).URL;
    } else {
      globalThis.URL = originalUrl;
    }
  });

  function createMemoryStorage(initial: Record<string, string> = {}) {
    const store: Record<string, string> = { ...initial };
    return {
      getItem: (key: string) => (Object.prototype.hasOwnProperty.call(store, key) ? store[key] : null),
      setItem: (key: string, value: string) => {
        store[key] = String(value);
      },
      removeItem: (key: string) => {
        delete store[key];
      },
      __store: store,
    };
  }

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
    const localStorage = createMemoryStorage();
    const dataLayer: Record<string, unknown>[] = [];
    const dispatchEvent = vi.fn();
    class MockCustomEvent {
      name: string;
      detail: unknown;
      constructor(name: string, options?: { detail?: unknown }) {
        this.name = name;
        this.detail = options?.detail;
      }
    }

    (globalThis as Record<string, unknown>).window = {
      localStorage,
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
    expect((dispatchEvent.mock.calls[0][0] as MockCustomEvent).name).toBe("ff:analytics");
    expect((dispatchEvent.mock.calls[0][0] as MockCustomEvent).detail).toHaveProperty("event", "export_click");
    expect(readAnalyticsEventBuffer()).toHaveLength(1);
    clearAnalyticsEventBuffer();
    expect(readAnalyticsEventBuffer()).toHaveLength(0);
  });

  it("summarizes quick-start funnel metrics from buffered events", () => {
    const localStorage = createMemoryStorage();
    (globalThis as Record<string, unknown>).window = {
      localStorage,
      dataLayer: [],
      dispatchEvent: vi.fn(),
      CustomEvent: class MockCustomEvent {
        name: string;
        detail: unknown;
        constructor(name: string, options?: { detail?: unknown }) {
          this.name = name;
          this.detail = options?.detail;
        }
      },
    };

    trackEvent("ff_quickstart_impression", { source: "activation_strip" });
    trackEvent("ff_quickstart_cta_click", { source: "activation_strip" });
    trackEvent("calculator_run_start", { source: "quickstart" });
    trackEvent("ff_calculation_success", {
      source: "quickstart",
      time_to_first_success_ms: 8200,
    });
    trackEvent("ff_calculation_error", { source: "quickstart" });

    const summary = summarizeActivationFunnel();
    expect(summary.quickstart).toMatchObject({
      impressions: 1,
      clicks: 1,
      runs_started: 1,
      runs_succeeded: 1,
      runs_failed: 1,
      click_through_rate_pct: 100,
      run_start_rate_pct: 100,
      run_success_rate_pct: 100,
      median_time_to_first_success_ms: 8200,
    });
    expect(summary.window.events_total).toBe(5);
  });

  it("installs a browser debug bridge for event diagnostics", () => {
    const localStorage = createMemoryStorage();
    const createObjectURL = vi.fn(() => "blob:test");
    const revokeObjectURL = vi.fn();
    const click = vi.fn();
    const appendChild = vi.fn();
    const removeChild = vi.fn();

    globalThis.URL = {
      createObjectURL,
      revokeObjectURL,
    } as unknown as typeof URL;
    (globalThis as Record<string, unknown>).document = {
      body: { appendChild, removeChild },
      createElement: vi.fn(() => ({ click })),
    };
    (globalThis as Record<string, unknown>).window = {
      localStorage,
      dataLayer: [],
      dispatchEvent: vi.fn(),
      CustomEvent: class MockCustomEvent {
        name: string;
        detail: unknown;
        constructor(name: string, options?: { detail?: unknown }) {
          this.name = name;
          this.detail = options?.detail;
        }
      },
    };

    expect(installAnalyticsDebugBridge()).toBe(true);
    const w = globalThis.window as Window & { ffAnalytics?: Record<string, (...args: unknown[]) => unknown> };
    expect(typeof w.ffAnalytics?.summary).toBe("function");
    expect(typeof w.ffAnalytics?.exportCsv).toBe("function");
    trackEvent("ff_quickstart_impression", { source: "activation_strip" });
    const events = w.ffAnalytics!.events();
    expect(events).toHaveLength(1);
    expect(downloadAnalyticsEventCsv("out.csv")).toBe(true);
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledTimes(1);

    const csv = analyticsEventsToCsv(events as never);
    expect(csv).toContain("timestamp_ms,timestamp,event,session_id,source");
    expect(csv).toContain("ff_quickstart_impression");

    w.ffAnalytics!.clear();
    expect(w.ffAnalytics!.events()).toHaveLength(0);
  });
});
