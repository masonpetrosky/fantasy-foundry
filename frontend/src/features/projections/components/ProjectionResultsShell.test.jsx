import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ProjectionResultsShell } from "./ProjectionResultsShell.jsx";

function buildProps(overrides = {}) {
  return {
    showCards: true,
    displayedPage: [],
    showInitialLoadSkeleton: false,
    error: "",
    retryFetch: vi.fn(),
    emptyStateHeadline: "No projections matched these filters.",
    emptyStateGuidance: "Adjust or clear filters to expand results.",
    emptyStateActions: <div className="actions-stub">Actions</div>,
    cardRowsMarkup: [],
    showMobileSwipeHint: false,
    swipeHintText: "",
    showInlineRefreshError: false,
    loading: false,
    cols: ["Player"],
    colLabels: {},
    sortCol: "Player",
    sortDir: "asc",
    onSort: vi.fn(),
    projectionTableScrollRef: { current: null },
    onTableScroll: vi.fn(),
    tableRowsMarkup: [],
    totalRows: 0,
    limit: 50,
    offset: 0,
    setOffset: vi.fn(),
    ...overrides,
  };
}

describe("ProjectionResultsShell", () => {
  it("renders card-view empty state when no rows are present", () => {
    const html = renderToStaticMarkup(
      <ProjectionResultsShell {...buildProps({ showCards: true })} />
    );

    expect(html).toContain("No projections matched these filters.");
    expect(html).toContain("Adjust or clear filters to expand results.");
    expect(html).toContain("Actions");
    expect(html).not.toContain("<table");
  });

  it("renders table empty state when table view is active", () => {
    const html = renderToStaticMarkup(
      <ProjectionResultsShell {...buildProps({ showCards: false })} />
    );

    expect(html).toContain("<table");
    expect(html).toContain("No projections matched these filters.");
    expect(html).toContain("Actions");
  });
});
