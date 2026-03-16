import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { checkA11y } from "../../../test/a11y-helpers";
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

interface FlatOverrides {
  tab?: string;
  search?: string;
  resolvedYearFilter?: string;
  teamFilter?: string;
  posFilters?: string[];
  watchlistOnly?: boolean;
  watchlistCount?: number;
  totalRows?: number;
  loading?: boolean;
  searchIsDebouncing?: boolean;
  hasActiveFilters?: boolean;
  activeFilterChips?: string[];
  setSearch?: (v: string) => void;
  setTeamFilter?: (v: string) => void;
  setYearFilter?: (v: string) => void;
  setPosFilters?: (u: string[] | ((p: string[]) => string[])) => void;
  setWatchlistOnly?: (u: boolean | ((p: boolean) => boolean)) => void;
  clearAllFilters?: () => void;
  activeProjectionPresetKey?: string;
  projectionFilterPresets?: null;
  applyProjectionFilterPreset?: (k: string) => void;
  saveCustomProjectionPreset?: () => void;
  exportingFormat?: string;
  exportCurrentProjections?: (f: string) => void;
  tierLimits?: React.ComponentProps<typeof ProjectionFilterBar>["tierLimits"];
}

function defaultProps(overrides: FlatOverrides = {}): React.ComponentProps<typeof ProjectionFilterBar> {
  return {
    filterState: {
      tab: overrides.tab ?? "all",
      meta: { years: [2026, 2027, 2028], teams: ["SEA", "NYY", "LAD"], bat_positions: ["C", "1B", "OF"], pit_positions: ["SP", "RP"] },
      search: overrides.search ?? "",
      resolvedYearFilter: overrides.resolvedYearFilter ?? "__career_totals__",
      teamFilter: overrides.teamFilter ?? "",
      posFilters: overrides.posFilters ?? [],
      watchlistOnly: overrides.watchlistOnly ?? false,
      watchlistCount: overrides.watchlistCount ?? 5,
      totalRows: overrides.totalRows ?? 100,
      loading: overrides.loading ?? false,
      searchIsDebouncing: overrides.searchIsDebouncing ?? false,
      hasActiveFilters: overrides.hasActiveFilters ?? false,
      activeFilterChips: overrides.activeFilterChips ?? [],
    },
    filterActions: {
      setSearch: overrides.setSearch ?? vi.fn(),
      setTeamFilter: overrides.setTeamFilter ?? vi.fn(),
      setYearFilter: overrides.setYearFilter ?? vi.fn(),
      setPosFilters: overrides.setPosFilters ?? vi.fn(),
      setWatchlistOnly: overrides.setWatchlistOnly ?? vi.fn(),
      clearAllFilters: overrides.clearAllFilters ?? vi.fn(),
    },
    presetConfig: {
      activeProjectionPresetKey: overrides.activeProjectionPresetKey ?? "all",
      projectionFilterPresets: overrides.projectionFilterPresets ?? null,
      applyProjectionFilterPreset: overrides.applyProjectionFilterPreset ?? vi.fn(),
      saveCustomProjectionPreset: overrides.saveCustomProjectionPreset ?? vi.fn(),
    },
    columnConfig: {
      tableColumnCatalog: ["Player", "Team", "Age"],
      resolvedProjectionTableHiddenCols: {},
      requiredProjectionTableCols: new Set<string>(["Player"]),
      toggleProjectionTableColumn: vi.fn(),
      showAllProjectionTableColumns: vi.fn(),
      colLabels: { Player: "Player", Team: "Team", Age: "Age" },
    },
    exportConfig: {
      exportingFormat: overrides.exportingFormat ?? "",
      exportCurrentProjections: overrides.exportCurrentProjections ?? vi.fn(),
    },
    tierLimits: overrides.tierLimits ?? null,
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

  it("passes axe accessibility checks", async () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps())
    );
    await checkA11y(container);
    cleanup();
  });
});
