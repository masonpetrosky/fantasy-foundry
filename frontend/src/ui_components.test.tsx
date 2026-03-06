import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { ExplainabilityCard } from "./ui_components";
import { fmt } from "./formatting_utils";

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

afterEach(() => {
  vi.restoreAllMocks();
});

let previousActEnvironmentFlag: unknown;

beforeAll(() => {
  previousActEnvironmentFlag = (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT;
  (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
});

afterAll(() => {
  (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = previousActEnvironmentFlag;
});

describe("ExplainabilityCard roto stat contributions", () => {
  it("renders stat dynasty contributions for roto mode", () => {
    const explanation = {
      player: "Test Player",
      team: "AAA",
      pos: "1B",
      mode: "roto",
      dynasty_value: 10.0,
      raw_dynasty_value: 12.0,
      per_year: [
        { year: 2026, year_value: 5.0, discount_factor: 1.0, discounted_contribution: 5.0 },
        { year: 2027, year_value: 3.0, discount_factor: 0.94, discounted_contribution: 2.82 },
      ],
      stat_dynasty_contributions: { R: 3.5, HR: 4.0, AVG: 2.5 },
    };

    const { container, cleanup } = renderToContainer(
      <ExplainabilityCard explanation={explanation} selectedYear="" onSelectedYearChange={() => {}} fmt={fmt} />
    );

    const text = container.textContent || "";
    expect(text).toContain("Per-Stat Dynasty Contributions");
    expect(text).toContain("R");
    expect(text).toContain("HR");
    expect(text).toContain("AVG");
    cleanup();
  });

  it("does not render stat contributions for points mode", () => {
    const explanation = {
      player: "Test Player",
      team: "AAA",
      pos: "1B",
      mode: "points",
      dynasty_value: 10.0,
      raw_dynasty_value: 12.0,
      per_year: [
        { year: 2026, year_value: 5.0, discount_factor: 1.0, discounted_contribution: 5.0 },
      ],
      stat_dynasty_contributions: { R: 3.5 },
    };

    const { container, cleanup } = renderToContainer(
      <ExplainabilityCard explanation={explanation} selectedYear="" onSelectedYearChange={() => {}} fmt={fmt} />
    );

    const text = container.textContent || "";
    expect(text).not.toContain("Per-Stat Dynasty Contributions");
    cleanup();
  });

  it("does not render stat contributions when absent", () => {
    const explanation = {
      player: "Test Player",
      mode: "roto",
      dynasty_value: 5.0,
      raw_dynasty_value: 6.0,
      per_year: [
        { year: 2026, year_value: 5.0, discount_factor: 1.0, discounted_contribution: 5.0 },
      ],
    };

    const { container, cleanup } = renderToContainer(
      <ExplainabilityCard explanation={explanation} selectedYear="" onSelectedYearChange={() => {}} fmt={fmt} />
    );

    const text = container.textContent || "";
    expect(text).not.toContain("Per-Stat Dynasty Contributions");
    cleanup();
  });
});
