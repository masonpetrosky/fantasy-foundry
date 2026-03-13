import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { ProjectionFilterBar } from "./ProjectionFilterBar";

vi.mock("../../../ui_components", () => ({
  ColumnChooserControl: null,
}));

vi.mock("../../../formatting_utils", () => ({
  parsePosTokens: (pos: string) => [pos],
}));

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

function defaultProps(overrides: Partial<React.ComponentProps<typeof ProjectionFilterBar>> = {}) {
  return {
    tab: "all",
    meta: { years: [2026, 2027, 2028], teams: ["SEA", "NYY", "LAD"], bat_positions: ["C", "1B", "OF"], pit_positions: ["SP", "RP"] },
    search: "",
    resolvedYearFilter: "__career_totals__",
    teamFilter: "",
    posFilters: [] as string[],
    watchlistOnly: false,
    watchlistCount: 5,
    totalRows: 100,
    loading: false,
    searchIsDebouncing: false,
    setSearch: vi.fn(),
    setTeamFilter: vi.fn(),
    setYearFilter: vi.fn(),
    setPosFilters: vi.fn(),
    setWatchlistOnly: vi.fn(),
    activeProjectionPresetKey: "all",
    projectionFilterPresets: null,
    applyProjectionFilterPreset: vi.fn(),
    saveCustomProjectionPreset: vi.fn(),
    clearAllFilters: vi.fn(),
    hasActiveFilters: false,
    activeFilterChips: [] as string[],
    tableColumnCatalog: ["Player", "Team", "Age"],
    resolvedProjectionTableHiddenCols: {},
    requiredProjectionTableCols: new Set<string>(["Player"]),
    toggleProjectionTableColumn: vi.fn(),
    showAllProjectionTableColumns: vi.fn(),
    colLabels: { Player: "Player", Team: "Team", Age: "Age" },
    exportingFormat: "",
    exportCurrentProjections: vi.fn(),
    tierLimits: null,
    ...overrides,
  };
}

describe("ProjectionFilterBar", () => {
  it("is exported", () => {
    expect(ProjectionFilterBar).toBeTruthy();
  });

  it("renders without crashing", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps())
    );
    expect(container.textContent).toBeDefined();
    cleanup();
  });

  it("renders preset buttons", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps())
    );
    expect(container.textContent).toContain("Presets");
    expect(container.textContent).toContain("All");
    expect(container.textContent).toContain("My Watchlist");
    expect(container.textContent).toContain("Hitters");
    expect(container.textContent).toContain("Pitchers");
    expect(container.textContent).toContain("Custom");
    cleanup();
  });

  it("renders search input", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps())
    );
    const searchInput = container.querySelector("#projections-search");
    expect(searchInput).not.toBeNull();
    cleanup();
  });

  it("renders year filter dropdown", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps())
    );
    const yearSelect = container.querySelector("#projections-year-filter");
    expect(yearSelect).not.toBeNull();
    cleanup();
  });

  it("renders team filter dropdown with teams", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps())
    );
    const teamSelect = container.querySelector("#projections-team-filter") as HTMLSelectElement;
    expect(teamSelect).not.toBeNull();
    expect(teamSelect.options.length).toBeGreaterThan(1); // "All Teams" + actual teams
    cleanup();
  });

  it("renders row count", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({ totalRows: 250 }))
    );
    expect(container.textContent).toContain("250 rows");
    cleanup();
  });

  it("shows watchlist rows when watchlistOnly", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({ watchlistOnly: true, totalRows: 10 }))
    );
    expect(container.textContent).toContain("10 watchlist rows");
    cleanup();
  });

  it("shows loading indicator when searchIsDebouncing", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({ searchIsDebouncing: true }))
    );
    expect(container.textContent).toContain("typing...");
    cleanup();
  });

  it("shows refreshing indicator when loading", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({ loading: true }))
    );
    expect(container.textContent).toContain("refreshing...");
    cleanup();
  });

  it("renders Export CSV and Export XLSX buttons", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps())
    );
    expect(container.textContent).toContain("Export CSV");
    expect(container.textContent).toContain("Export XLSX");
    cleanup();
  });

  it("shows Export CSV (Pro) when export not allowed", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({
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
    expect(container.textContent).toContain("Export CSV (Pro)");
    expect(container.textContent).toContain("Export XLSX (Pro)");
    cleanup();
  });

  it("calls setSearch when search input changes", () => {
    const setSearch = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({ setSearch }))
    );
    const input = container.querySelector("#projections-search") as HTMLInputElement;
    act(() => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
      )!.set!;
      nativeInputValueSetter.call(input, "test");
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(setSearch).toHaveBeenCalled();
    cleanup();
  });

  it("calls applyProjectionFilterPreset when preset button clicked", () => {
    const applyPreset = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({ applyProjectionFilterPreset: applyPreset }))
    );
    // Find the Hitters button and click it
    const buttons = Array.from(container.querySelectorAll("button"));
    const hittersBtn = buttons.find(b => b.textContent === "Hitters");
    expect(hittersBtn).toBeDefined();
    act(() => {
      hittersBtn!.click();
    });
    expect(applyPreset).toHaveBeenCalledWith("hitters");
    cleanup();
  });

  it("renders Clear All Filters button", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps())
    );
    expect(container.textContent).toContain("Clear All Filters");
    cleanup();
  });

  it("renders active filter chips", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({
        hasActiveFilters: true,
        activeFilterChips: ["Team: SEA", "Year: 2028"],
      }))
    );
    expect(container.textContent).toContain("Team: SEA");
    expect(container.textContent).toContain("Year: 2028");
    cleanup();
  });

  it("renders No active filters when none", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({ hasActiveFilters: false }))
    );
    expect(container.textContent).toContain("No active filters");
    cleanup();
  });

  it("disables watchlist button when watchlistCount is 0", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({ watchlistCount: 0 }))
    );
    const buttons = Array.from(container.querySelectorAll("button"));
    const watchlistBtn = buttons.find(b => b.textContent === "My Watchlist");
    expect(watchlistBtn).toBeDefined();
    expect(watchlistBtn!.disabled).toBe(true);
    cleanup();
  });

  it("shows exporting state for CSV", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps({ exportingFormat: "csv" }))
    );
    expect(container.textContent).toContain("Exporting CSV...");
    cleanup();
  });
});
