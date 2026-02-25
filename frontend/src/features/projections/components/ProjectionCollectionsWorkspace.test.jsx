import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ProjectionCollectionsWorkspace } from "./ProjectionCollectionsWorkspace.jsx";

function buildProps(overrides = {}) {
  return {
    showCollectionsWorkspace: true,
    watchlistCount: 0,
    watchlistOnly: false,
    watchlist: {},
    watchlistEntries: [],
    clearWatchlist: vi.fn(),
    exportWatchlistCsv: vi.fn(),
    removeWatchlistEntry: vi.fn(),
    compareRowsCount: 0,
    maxComparePlayers: 4,
    clearCompareRows: vi.fn(),
    compareRows: [],
    comparisonColumns: ["Year", "DynastyValue"],
    removeCompareRow: vi.fn(),
    colLabels: {},
    formatCellValue: value => String(value ?? ""),
    ...overrides,
  };
}

describe("ProjectionCollectionsWorkspace", () => {
  it("shows the workspace hint when collections are unavailable", () => {
    const html = renderToStaticMarkup(
      <ProjectionCollectionsWorkspace {...buildProps({ showCollectionsWorkspace: false })} />
    );

    expect(html).toContain("Run dynasty rankings first to unlock your watchlist and comparison workspace.");
  });

  it("renders toolbar counts and disabled actions when lists are empty", () => {
    const html = renderToStaticMarkup(
      <ProjectionCollectionsWorkspace {...buildProps()} />
    );

    expect(html).toContain("Watchlist: 0");
    expect(html).toContain("View: All Players");
    expect(html).toContain("Compare: 0/4");
    expect(html).toContain("Export Watchlist CSV");
    expect(html).toContain("Clear Watchlist");
    expect(html).toContain("Clear Compare");
    expect(html).toContain("disabled=\"\"");
  });
});
