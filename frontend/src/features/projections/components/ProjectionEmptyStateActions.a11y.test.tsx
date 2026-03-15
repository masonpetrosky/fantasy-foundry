import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, it, vi } from "vitest";
import { checkA11y } from "../../../test/a11y-helpers";
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

function defaultProps(overrides: Partial<React.ComponentProps<typeof ProjectionEmptyStateActions>> = {}) {
  return {
    clearAllFilters: vi.fn(),
    clearFiltersDisabled: false,
    showTurnOffWatchlistAction: false,
    setWatchlistOnly: vi.fn(),
    applyProjectionFilterPreset: vi.fn(),
    setSearch: vi.fn(),
    showSwitchToCareerTotalsAction: false,
    setYearFilter: vi.fn(),
    careerTotalsFilterValue: "__career_totals__",
    ...overrides,
  };
}

describe("ProjectionEmptyStateActions a11y", () => {
  it("passes axe checks in default state", async () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionEmptyStateActions, defaultProps()),
    );
    await checkA11y(container);
    cleanup();
  });

  it("passes axe checks with watchlist action visible", async () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(
        ProjectionEmptyStateActions,
        defaultProps({ showTurnOffWatchlistAction: true }),
      ),
    );
    await checkA11y(container);
    cleanup();
  });
});
