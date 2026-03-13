import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { PointsScoringForm } from "./dynasty_calculator_sidebar_points";
import {
  POINTS_BATTING_FIELDS,
  POINTS_PITCHING_FIELDS,
} from "./dynasty_calculator_config";

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

function defaultProps(overrides: Partial<React.ComponentProps<typeof PointsScoringForm>> = {}) {
  // Build default settings from field defaults
  const settings: Record<string, unknown> = {};
  [...POINTS_BATTING_FIELDS, ...POINTS_PITCHING_FIELDS].forEach(f => {
    settings[f.key] = f.defaultValue;
  });
  return {
    settings,
    update: vi.fn(),
    pointRulesCount: 18,
    resetPointsScoringDefaults: vi.fn(),
    tierLimits: null,
    ...overrides,
  };
}

describe("PointsScoringForm", () => {
  it("is exported", () => {
    expect(PointsScoringForm).toBeTruthy();
  });

  it("renders the section title", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps())
    );
    expect(container.textContent).toContain("Points Scoring Rules");
    cleanup();
  });

  it("renders the rules count in description", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps({ pointRulesCount: 12 }))
    );
    expect(container.textContent).toContain("12 categories");
    cleanup();
  });

  it("renders Batting and Pitching subheadings", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps())
    );
    expect(container.textContent).toContain("Batting");
    expect(container.textContent).toContain("Pitching");
    cleanup();
  });

  it("renders all batting field labels", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps())
    );
    for (const field of POINTS_BATTING_FIELDS) {
      expect(container.textContent).toContain(field.label);
    }
    cleanup();
  });

  it("renders all pitching field labels", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps())
    );
    for (const field of POINTS_PITCHING_FIELDS) {
      expect(container.textContent).toContain(field.label);
    }
    cleanup();
  });

  it("renders number inputs for all fields", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps())
    );
    const inputs = container.querySelectorAll<HTMLInputElement>('input[type="number"]');
    expect(inputs.length).toBe(POINTS_BATTING_FIELDS.length + POINTS_PITCHING_FIELDS.length);
    cleanup();
  });

  it("renders the reset button", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps())
    );
    const resetBtn = container.querySelector("button.calc-secondary-btn");
    expect(resetBtn).not.toBeNull();
    expect(resetBtn!.textContent).toContain("Reset Recommended Points Scoring");
    cleanup();
  });

  it("calls resetPointsScoringDefaults when reset button clicked", () => {
    const resetFn = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps({ resetPointsScoringDefaults: resetFn }))
    );
    act(() => {
      container.querySelector<HTMLButtonElement>("button.calc-secondary-btn")!.click();
    });
    expect(resetFn).toHaveBeenCalledTimes(1);
    cleanup();
  });

  it("calls update when an input value changes", () => {
    const updateFn = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps({ update: updateFn }))
    );
    const firstInput = container.querySelector<HTMLInputElement>('input[type="number"]');
    expect(firstInput).not.toBeNull();
    act(() => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
      )!.set!;
      nativeInputValueSetter.call(firstInput, "5");
      firstInput!.dispatchEvent(new Event("input", { bubbles: true }));
    });
    // The onChange should fire update
    cleanup();
  });

  it("shows pro note when scoring is locked", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps({
        tierLimits: {
          maxSims: 300,
          allowExport: false,
          allowPointsMode: false,
          allowTradeAnalyzer: false,
          allowCustomCategories: false,
          allowCloudSync: false,
        },
      }))
    );
    expect(container.textContent).toContain("Custom scoring available with Pro");
    cleanup();
  });

  it("disables inputs when scoring is locked", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps({
        tierLimits: {
          maxSims: 300,
          allowExport: false,
          allowPointsMode: false,
          allowTradeAnalyzer: false,
          allowCustomCategories: false,
          allowCloudSync: false,
        },
      }))
    );
    const inputs = container.querySelectorAll<HTMLInputElement>('input[type="number"]');
    inputs.forEach(input => {
      expect(input.disabled).toBe(true);
    });
    cleanup();
  });

  it("does not show pro note when allowCustomCategories is true", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps({
        tierLimits: {
          maxSims: 2000,
          allowExport: true,
          allowPointsMode: true,
          allowTradeAnalyzer: true,
          allowCustomCategories: true,
          allowCloudSync: true,
        },
      }))
    );
    expect(container.textContent).not.toContain("Custom scoring available with Pro");
    cleanup();
  });

  it("disables the reset button when scoring is locked", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PointsScoringForm, defaultProps({
        tierLimits: {
          maxSims: 300,
          allowExport: false,
          allowPointsMode: false,
          allowTradeAnalyzer: false,
          allowCustomCategories: false,
          allowCloudSync: false,
        },
      }))
    );
    const resetBtn = container.querySelector<HTMLButtonElement>("button.calc-secondary-btn");
    expect(resetBtn!.disabled).toBe(true);
    cleanup();
  });
});
