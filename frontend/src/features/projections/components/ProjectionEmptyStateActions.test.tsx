import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { ProjectionEmptyStateActions } from "./ProjectionEmptyStateActions";

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

const baseProps = {
  clearAllFilters: vi.fn(),
  clearFiltersDisabled: false,
  showTurnOffWatchlistAction: false,
  setWatchlistOnly: vi.fn(),
  applyProjectionFilterPreset: vi.fn(),
  setSearch: vi.fn(),
  showSwitchToCareerTotalsAction: false,
  setYearFilter: vi.fn(),
  careerTotalsFilterValue: "career",
};

describe("ProjectionEmptyStateActions", () => {
  it("is exported", () => {
    expect(ProjectionEmptyStateActions).toBeTruthy();
  });

  it("renders clear filters button", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionEmptyStateActions, baseProps)
    );
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBeGreaterThanOrEqual(3);
    expect(buttons[0].textContent).toBe("Clear Filters");
    cleanup();
  });

  it("calls clearAllFilters on click", () => {
    const clear = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionEmptyStateActions, { ...baseProps, clearAllFilters: clear })
    );
    const btn = container.querySelectorAll("button")[0] as HTMLButtonElement;
    act(() => { btn.click(); });
    expect(clear).toHaveBeenCalled();
    cleanup();
  });

  it("shows watchlist button when showTurnOffWatchlistAction is true", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionEmptyStateActions, { ...baseProps, showTurnOffWatchlistAction: true })
    );
    expect(container.textContent).toContain("Turn Off Watchlist View");
    cleanup();
  });

  it("calls setSearch with example on try example click", () => {
    const setSearch = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionEmptyStateActions, { ...baseProps, setSearch })
    );
    const tryBtn = Array.from(container.querySelectorAll("button")).find(
      b => b.textContent === "Try Example Search"
    ) as HTMLButtonElement;
    act(() => { tryBtn.click(); });
    expect(setSearch).toHaveBeenCalledWith("Rodriguez");
    cleanup();
  });

  it("shows career totals button when enabled", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionEmptyStateActions, { ...baseProps, showSwitchToCareerTotalsAction: true })
    );
    expect(container.textContent).toContain("Switch To Career Totals");
    cleanup();
  });

  it("disables clear button when clearFiltersDisabled", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionEmptyStateActions, { ...baseProps, clearFiltersDisabled: true })
    );
    const btn = container.querySelectorAll("button")[0] as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    cleanup();
  });
});
