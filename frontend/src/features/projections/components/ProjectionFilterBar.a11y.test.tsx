import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, it, vi } from "vitest";
import { checkA11y } from "../../../test/a11y-helpers";
import { ProjectionFilterBar } from "./ProjectionFilterBar";

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

function defaultProps(): React.ComponentProps<typeof ProjectionFilterBar> {
  return {
    filterState: {
      tab: "all",
      meta: { years: [2026, 2027], teams: ["NYY", "BOS"], bat_positions: ["C", "1B"], pit_positions: ["SP", "RP"] },
      search: "",
      resolvedYearFilter: "__career_totals__",
      teamFilter: "",
      posFilters: [],
      watchlistOnly: false,
      watchlistCount: 0,
      totalRows: 100,
      loading: false,
      searchIsDebouncing: false,
      hasActiveFilters: false,
      activeFilterChips: [],
    },
    filterActions: {
      setSearch: vi.fn(),
      setTeamFilter: vi.fn(),
      setYearFilter: vi.fn(),
      setPosFilters: vi.fn(),
      setWatchlistOnly: vi.fn(),
      clearAllFilters: vi.fn(),
    },
    presetConfig: {
      activeProjectionPresetKey: "all",
      projectionFilterPresets: null,
      applyProjectionFilterPreset: vi.fn(),
      saveCustomProjectionPreset: vi.fn(),
    },
    columnConfig: {
      tableColumnCatalog: ["Player", "Team", "Pos", "HR", "RBI"],
      resolvedProjectionTableHiddenCols: {},
      requiredProjectionTableCols: new Set(["Player"]),
      toggleProjectionTableColumn: vi.fn(),
      showAllProjectionTableColumns: vi.fn(),
      colLabels: {},
    },
    exportConfig: {
      exportingFormat: "",
      exportCurrentProjections: vi.fn(),
    },
    tierLimits: null,
  };
}

describe("ProjectionFilterBar a11y", () => {
  it("passes axe checks in default state", async () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, defaultProps()),
    );
    await checkA11y(container);
    cleanup();
  });

  it("passes axe checks with active filters", async () => {
    const props = defaultProps();
    props.filterState.hasActiveFilters = true;
    props.filterState.activeFilterChips = ["Team: NYY", "Pos: C"];
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, props),
    );
    await checkA11y(container);
    cleanup();
  });

  it("passes axe checks while loading", async () => {
    const props = defaultProps();
    props.filterState.loading = true;
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionFilterBar, props),
    );
    await checkA11y(container);
    cleanup();
  });
});
