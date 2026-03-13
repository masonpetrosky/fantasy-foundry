import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { RotoCategoriesForm } from "./dynasty_calculator_sidebar_categories";
import {
  ROTO_HITTER_CATEGORY_FIELDS,
  ROTO_PITCHER_CATEGORY_FIELDS,
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

function defaultProps(overrides: Partial<React.ComponentProps<typeof RotoCategoriesForm>> = {}) {
  return {
    settings: {} as Record<string, unknown>,
    update: vi.fn(),
    selectedRotoHitCategoryCount: 5,
    selectedRotoPitchCategoryCount: 5,
    resetRotoCategoryDefaults: vi.fn(),
    tierLimits: null,
    ...overrides,
  };
}

describe("RotoCategoriesForm", () => {
  it("is exported", () => {
    expect(RotoCategoriesForm).toBeTruthy();
  });

  it("renders the section title", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps())
    );
    expect(container.textContent).toContain("Roto Categories");
    cleanup();
  });

  it("renders category counts in the description", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps({
        selectedRotoHitCategoryCount: 3,
        selectedRotoPitchCategoryCount: 4,
      }))
    );
    expect(container.textContent).toContain("3 hitting");
    expect(container.textContent).toContain("4 pitching");
    cleanup();
  });

  it("renders hitting and pitching subheadings", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps())
    );
    expect(container.textContent).toContain("Hitting");
    expect(container.textContent).toContain("Pitching");
    cleanup();
  });

  it("renders all hitter category checkboxes", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps())
    );
    for (const field of ROTO_HITTER_CATEGORY_FIELDS) {
      expect(container.textContent).toContain(field.label);
    }
    cleanup();
  });

  it("renders all pitcher category checkboxes", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps())
    );
    for (const field of ROTO_PITCHER_CATEGORY_FIELDS) {
      expect(container.textContent).toContain(field.label);
    }
    cleanup();
  });

  it("renders the reset button", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps())
    );
    const resetBtn = container.querySelector("button.calc-secondary-btn");
    expect(resetBtn).not.toBeNull();
    expect(resetBtn!.textContent).toContain("Reset 5x5 Categories");
    cleanup();
  });

  it("calls resetRotoCategoryDefaults when reset button clicked", () => {
    const resetFn = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps({ resetRotoCategoryDefaults: resetFn }))
    );
    act(() => {
      container.querySelector<HTMLButtonElement>("button.calc-secondary-btn")!.click();
    });
    expect(resetFn).toHaveBeenCalledTimes(1);
    cleanup();
  });

  it("calls update when a checkbox is toggled", () => {
    const updateFn = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps({ update: updateFn }))
    );
    const firstCheckbox = container.querySelector<HTMLInputElement>("input[type=checkbox]");
    expect(firstCheckbox).not.toBeNull();
    act(() => {
      firstCheckbox!.click();
    });
    expect(updateFn).toHaveBeenCalled();
    cleanup();
  });

  it("shows pro note when categories are locked", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps({
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
    expect(container.textContent).toContain("Custom categories available with Pro");
    cleanup();
  });

  it("disables checkboxes when categories are locked", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps({
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
    const checkboxes = container.querySelectorAll<HTMLInputElement>("input[type=checkbox]");
    expect(checkboxes.length).toBeGreaterThan(0);
    checkboxes.forEach(cb => {
      expect(cb.disabled).toBe(true);
    });
    cleanup();
  });

  it("does not show pro note when allowCustomCategories is true", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps({
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
    expect(container.textContent).not.toContain("Custom categories available with Pro");
    cleanup();
  });

  it("checkboxes reflect settings values", () => {
    const settings: Record<string, unknown> = {
      roto_hit_r: false,
      roto_hit_rbi: true,
    };
    const { container, cleanup } = renderToContainer(
      React.createElement(RotoCategoriesForm, defaultProps({ settings }))
    );
    const checkboxes = container.querySelectorAll<HTMLInputElement>("input[type=checkbox]");
    // First checkbox is roto_hit_r, should be unchecked (false overrides default true)
    expect(checkboxes[0].checked).toBe(false);
    // Second checkbox is roto_hit_rbi, should be checked
    expect(checkboxes[1].checked).toBe(true);
    cleanup();
  });
});
