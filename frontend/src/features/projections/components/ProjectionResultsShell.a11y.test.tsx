import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, it, vi } from "vitest";
import { checkA11y } from "../../../test/a11y-helpers";
import { ProjectionResultsShell } from "./ProjectionResultsShell";

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

function defaultProps(): React.ComponentProps<typeof ProjectionResultsShell> {
  return {
    showCards: false,
    displayedPage: [],
    showInitialLoadSkeleton: false,
    error: "",
    retryFetch: vi.fn(),
    emptyStateHeadline: "No results found",
    emptyStateGuidance: "Try adjusting your filters",
    emptyStateActions: React.createElement("button", { type: "button" }, "Clear Filters"),
    cardRowsMarkup: null,
    showMobileSwipeHint: false,
    swipeHintText: "",
    showInlineRefreshError: false,
    loading: false,
    cols: ["Player", "Team", "HR"],
    colLabels: { Player: "Player", Team: "Team", HR: "Home Runs" },
    sortCol: "Player",
    sortDir: "asc",
    onSort: vi.fn(),
    projectionTableScrollRef: { current: null },
    onTableScroll: vi.fn(),
    tableRowsMarkup: null,
    totalRows: 0,
    limit: 50,
    offset: 0,
    setOffset: vi.fn(),
  };
}

describe("ProjectionResultsShell a11y", () => {
  it("passes axe checks with empty state", async () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionResultsShell, defaultProps()),
    );
    await checkA11y(container);
    cleanup();
  });

  it("passes axe checks in loading state", async () => {
    const props = defaultProps();
    props.showInitialLoadSkeleton = true;
    props.loading = true;
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionResultsShell, props),
    );
    await checkA11y(container);
    cleanup();
  });

  it("passes axe checks with error state", async () => {
    const props = defaultProps();
    props.error = "Failed to load projections";
    props.showInlineRefreshError = true;
    props.displayedPage = [{ Player: "Test", Team: "NYY", HR: 30 }];
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionResultsShell, props),
    );
    await checkA11y(container);
    cleanup();
  });
});
