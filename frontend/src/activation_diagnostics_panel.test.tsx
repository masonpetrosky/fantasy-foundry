import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

import {
  ActivationDiagnosticsPanel,
  buildActivationCheckpointReadoutCommand,
  buildActivationReadoutCommand,
  resolveActivationDatePreset,
  resolveActivationDiagnosticsPanelEnabled,
} from "./activation_diagnostics_panel";

function renderToContainer(element: React.ReactElement): { container: HTMLDivElement; cleanup: () => void } {
  const container = document.createElement("div");
  document.body.appendChild(container);
  let root: ReturnType<typeof createRoot>;
  act(() => {
    root = createRoot(container);
    root.render(element);
  });
  return {
    container,
    cleanup: () => {
      act(() => root.unmount());
      document.body.removeChild(container);
    },
  };
}

let previousActEnvironmentFlag: unknown;

beforeAll(() => {
  previousActEnvironmentFlag = globalThis.IS_REACT_ACT_ENVIRONMENT;
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
});

afterAll(() => {
  (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = previousActEnvironmentFlag;
});

describe("resolveActivationDiagnosticsPanelEnabled", () => {
  it("enables diagnostics when env flag is enabled", () => {
    expect(resolveActivationDiagnosticsPanelEnabled({
      envEnabled: true,
      locationSearch: "",
    })).toBe(true);
  });

  it("enables diagnostics when query param requests activation debug", () => {
    expect(resolveActivationDiagnosticsPanelEnabled({
      envEnabled: false,
      locationSearch: "?activation_debug=1",
    })).toBe(true);
    expect(resolveActivationDiagnosticsPanelEnabled({
      envEnabled: false,
      locationSearch: "?activation_debug=true",
    })).toBe(true);
  });

  it("keeps diagnostics disabled by default", () => {
    expect(resolveActivationDiagnosticsPanelEnabled({
      envEnabled: false,
      locationSearch: "",
    })).toBe(false);
  });
});

describe("buildActivationReadoutCommand", () => {
  it("builds an executable rollout readout command with defaults", () => {
    const command = buildActivationReadoutCommand({
      reportDate: "2026-02-25",
    });
    expect(command).toContain("scripts/run_activation_readout.sh");
    expect(command).toContain("--current 'tmp/activation_current.csv'");
    expect(command).toContain("--baseline 'tmp/activation_baseline.csv'");
    expect(command).toContain("--date '2026-02-25'");
    expect(command).toContain("--owner 'Analytics Team'");
  });

  it("shell-quotes values that include spaces or single quotes", () => {
    const command = buildActivationReadoutCommand({
      currentPath: "tmp/current export.csv",
      baselinePath: "tmp/base.csv",
      reportDate: "2026-02-25",
      owner: "Owner's Team",
    });
    expect(command).toContain("--current 'tmp/current export.csv'");
    expect(command).toContain("--owner 'Owner'\"'\"'s Team'");
  });
});

describe("buildActivationCheckpointReadoutCommand", () => {
  it("builds the checkpoint rollout command with sensible defaults", () => {
    const command = buildActivationCheckpointReadoutCommand({
      date24h: "2026-02-26",
    });
    expect(command).toContain("scripts/run_activation_readout_checkpoints.sh");
    expect(command).toContain("--current-24h 'tmp/activation_current_24h.csv'");
    expect(command).toContain("--baseline-24h 'tmp/activation_baseline_24h.csv'");
    expect(command).toContain("--date-24h '2026-02-26'");
    expect(command).toContain("--date-48h '2026-02-27'");
    expect(command).toContain("--owner 'Analytics Team'");
  });

  it("supports explicit paths, dates, and shell-quoted owner names", () => {
    const command = buildActivationCheckpointReadoutCommand({
      current24hPath: "tmp/current 24h.csv",
      baseline24hPath: "tmp/baseline 24h.csv",
      current48hPath: "tmp/current 48h.csv",
      baseline48hPath: "tmp/baseline 48h.csv",
      date24h: "2026-02-26",
      date48h: "2026-02-27",
      owner: "Owner's Team",
    });
    expect(command).toContain("--current-24h 'tmp/current 24h.csv'");
    expect(command).toContain("--baseline-48h 'tmp/baseline 48h.csv'");
    expect(command).toContain("--date-48h '2026-02-27'");
    expect(command).toContain("--owner 'Owner'\"'\"'s Team'");
  });
});

describe("resolveActivationDatePreset", () => {
  it("resolves explicit anchor date and offset into readout + checkpoint dates", () => {
    const dates = resolveActivationDatePreset({
      anchorDate: "2026-02-25",
      offsetDays: 1,
    });
    expect(dates).toEqual({
      readoutDate: "2026-02-26",
      date24h: "2026-02-26",
      date48h: "2026-02-27",
    });
  });

  it("falls back to a valid ISO date trio when anchor date is invalid", () => {
    const dates = resolveActivationDatePreset({
      anchorDate: "not-a-date",
      offsetDays: 0,
    });
    expect(dates.readoutDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(dates.date24h).toBe(dates.readoutDate);
    expect(dates.date48h).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe("ActivationDiagnosticsPanel", () => {
  it("opens command center, applies date preset, and closes on Escape", async () => {
    const fetchOpsSnapshot = vi.fn(async () => null);
    const { container, cleanup } = renderToContainer(
      <ActivationDiagnosticsPanel
        section="projections"
        dataVersion="v-test"
        readEvents={() => []}
        summarize={() => ({ window: { events_total: 0, first_event_at_ms: null, last_event_at_ms: null }, quickstart: { impressions: 0, clicks: 0, runs_started: 0, runs_succeeded: 0, runs_failed: 0, click_through_rate_pct: null, run_start_rate_pct: null, run_success_rate_pct: null, median_time_to_first_success_ms: null } })}
        clearEvents={vi.fn()}
        exportCsv={vi.fn(() => true)}
        fetchOpsSnapshot={fetchOpsSnapshot}
        opsRefreshIntervalMs={0}
      />
    );
    await act(async () => {
      await Promise.resolve();
    });

    const commandCenterButton = Array.from(container.querySelectorAll("button")).find(
      button => button.textContent?.trim() === "Command Center"
    );
    expect(commandCenterButton).toBeTruthy();
    act(() => {
      commandCenterButton!.click();
    });
    expect(container.querySelector('[role="dialog"][aria-label="Activation command center"]')).toBeTruthy();

    const tomorrowButton = Array.from(container.querySelectorAll("button")).find(
      button => button.textContent?.trim() === "Use Tomorrow"
    );
    expect(tomorrowButton).toBeTruthy();
    act(() => {
      tomorrowButton!.click();
    });
    expect(container.textContent).toContain("Applied date preset (tomorrow).");

    act(() => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(container.querySelector('[role="dialog"][aria-label="Activation command center"]')).toBeNull();

    cleanup();
  });

  it("shows fallback status and prompt when clipboard copy is unavailable", async () => {
    const fetchOpsSnapshot = vi.fn(async () => null);
    const promptSpy = vi.spyOn(window, "prompt").mockReturnValue("");
    const originalClipboard = navigator.clipboard;
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: undefined,
    });
    let cleanup: (() => void) | null = null;
    try {
      const rendered = renderToContainer(
        <ActivationDiagnosticsPanel
          section="projections"
          dataVersion="v-test"
          readEvents={() => []}
          summarize={() => ({ window: { events_total: 0, first_event_at_ms: null, last_event_at_ms: null }, quickstart: { impressions: 0, clicks: 0, runs_started: 0, runs_succeeded: 0, runs_failed: 0, click_through_rate_pct: null, run_start_rate_pct: null, run_success_rate_pct: null, median_time_to_first_success_ms: null } })}
          clearEvents={vi.fn()}
          exportCsv={vi.fn(() => true)}
          fetchOpsSnapshot={fetchOpsSnapshot}
          opsRefreshIntervalMs={0}
        />
      );
      const { container } = rendered;
      cleanup = rendered.cleanup;
      await act(async () => {
        await Promise.resolve();
      });

      const commandCenterButton = Array.from(container.querySelectorAll("button")).find(
        button => button.textContent?.trim() === "Command Center"
      );
      act(() => {
        commandCenterButton!.click();
      });

      const copyCheckpointButton = Array.from(container.querySelectorAll("button")).find(
        button => button.textContent?.trim() === "Copy Checkpoint Cmd"
      );
      expect(copyCheckpointButton).toBeTruthy();
      await act(async () => {
        copyCheckpointButton!.click();
        await Promise.resolve();
      });

      expect(promptSpy).toHaveBeenCalledTimes(1);
      const copiedCommand = String(promptSpy.mock.calls[0][1] || "");
      expect(copiedCommand).toContain("--owner 'Analytics Team'");
      expect(container.textContent).toContain("Unable to copy automatically; checkpoint command shown in prompt.");

    } finally {
      cleanup?.();
      promptSpy.mockRestore();
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: originalClipboard,
      });
    }
  });

  it("renders runtime queue telemetry from ops snapshot", async () => {
    const fetchOpsSnapshot = vi.fn(async () => ({
      timestamp: "2026-02-26T12:00:00Z",
      queues: {
        job_pressure: {
          utilization_ratio: 0.625,
          active_jobs: 5,
          capacity_total: 8,
          queued_oldest_age_seconds: 240,
          alerts: {
            queue_wait_exceeds_request_timeout: true,
            runtime_exceeds_request_timeout: false,
          },
        },
        rate_limit_activity: {
          totals: {
            blocked: 7,
          },
        },
      },
    }));

    const { container, cleanup } = renderToContainer(
      <ActivationDiagnosticsPanel
        section="projections"
        dataVersion="v-test"
        readEvents={() => []}
        summarize={() => ({ window: { events_total: 0, first_event_at_ms: null, last_event_at_ms: null }, quickstart: { impressions: 0, clicks: 0, runs_started: 0, runs_succeeded: 0, runs_failed: 0, click_through_rate_pct: null, run_start_rate_pct: null, run_success_rate_pct: null, median_time_to_first_success_ms: null } })}
        clearEvents={vi.fn()}
        exportCsv={vi.fn(() => true)}
        fetchOpsSnapshot={fetchOpsSnapshot}
        opsRefreshIntervalMs={0}
      />
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(fetchOpsSnapshot).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("Runtime");
    expect(container.textContent).toContain("62.5%");
    expect(container.textContent).toContain("5 / 8");
    expect(container.textContent).toContain("7");
    expect(container.textContent).toContain("Queue alert: request timeout threshold exceeded for queued or running jobs.");

    cleanup();
  });

  it("refreshes ops snapshot automatically on the configured interval", async () => {
    vi.useFakeTimers();
    const fetchOpsSnapshot = vi.fn(async () => ({
      queues: {},
    }));
    const { cleanup } = renderToContainer(
      <ActivationDiagnosticsPanel
        section="projections"
        dataVersion="v-test"
        readEvents={() => []}
        summarize={() => ({ window: { events_total: 0, first_event_at_ms: null, last_event_at_ms: null }, quickstart: { impressions: 0, clicks: 0, runs_started: 0, runs_succeeded: 0, runs_failed: 0, click_through_rate_pct: null, run_start_rate_pct: null, run_success_rate_pct: null, median_time_to_first_success_ms: null } })}
        clearEvents={vi.fn()}
        exportCsv={vi.fn(() => true)}
        fetchOpsSnapshot={fetchOpsSnapshot}
        opsRefreshIntervalMs={10000}
      />
    );

    try {
      await act(async () => {
        await Promise.resolve();
      });
      expect(fetchOpsSnapshot).toHaveBeenCalledTimes(1);

      await act(async () => {
        vi.advanceTimersByTime(10000);
        await Promise.resolve();
      });
      expect(fetchOpsSnapshot).toHaveBeenCalledTimes(2);
    } finally {
      cleanup();
      vi.useRealTimers();
    }
  });
});
