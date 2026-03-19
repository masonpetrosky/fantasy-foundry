import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import type { ComponentProps } from "react";
import { describe, expect, it, vi, afterEach } from "vitest";

vi.mock("./ui_components", () => ({
  ColumnChooserControl: () => React.createElement("div", { "data-testid": "column-chooser" }),
  ExplainabilityCard: () => React.createElement("div", { "data-testid": "explainability-card" }),
}));
vi.mock("./formatting_utils", () => ({
  fmt: (v: unknown, d?: number) => {
    if (v == null) return "";
    return Number(v).toFixed(d ?? 0);
  },
}));

import { DynastyCalculatorResults } from "./dynasty_calculator_results";

type ResultsState = ComponentProps<typeof DynastyCalculatorResults>["state"];
type ResultsActions = ComponentProps<typeof DynastyCalculatorResults>["actions"];
type ResultsRefs = ComponentProps<typeof DynastyCalculatorResults>["refs"];

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

function makeDefaultActions(): ResultsActions {
  return {
    clearRankCompareRows: vi.fn(),
    clearRankFilters: vi.fn(),
    clearWatchlist: vi.fn(),
    exportRankings: vi.fn(),
    exportWatchlistCsv: vi.fn(),
    handleSort: vi.fn(),
    removeRankCompareRow: vi.fn(),
    setPinRankKeyColumns: vi.fn(),
    setPosFilter: vi.fn(),
    setRankWatchlistOnly: vi.fn(),
    setSearchInput: vi.fn(),
    setSelectedExplainKey: vi.fn(),
    setSelectedExplainYear: vi.fn(),
    showAllRankColumns: vi.fn(),
    toggleRankColumn: vi.fn(),
    toggleRankCompareRow: vi.fn(),
    toggleRowWatch: vi.fn(),
  };
}

function makeDefaultState(): ResultsState {
  return {
    activeExplanation: null,
    compareYearCols: [],
    columnLabels: {},
    displayCols: ["Player", "Team", "Pos", "DynastyValue"],
    hasRankFilters: false,
    hiddenRankCols: {},
    pinRankKeyColumns: true,
    posFilter: "",
    rankCompareRows: [],
    rankCompareRowsByKey: {},
    rankedFiltered: [],
    rankSearchIsDebouncing: false,
    rankWatchlistOnly: false,
    searchInput: "",
    selectedExplainKey: "",
    selectedExplainYear: "",
    sortCol: "DynastyValue",
    sortDir: "desc" as const,
    sortedAll: [],
    virtualBottomPad: 0,
    virtualRows: [],
    virtualStartIndex: 0,
    virtualTopPad: 0,
    visibleRankCols: ["Player", "Team", "Pos", "DynastyValue"],
    watchlist: {},
    watchlistCount: 0,
    requiredRankCols: new Set<string>(),
    tierLimits: null,
  };
}

function makeDefaultRefs(): ResultsRefs {
  return {
    handleRankScroll: vi.fn(),
    rankTableScrollRef: React.createRef<HTMLDivElement>(),
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("DynastyCalculatorResults", () => {
  it("renders empty state when no results", () => {
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorResults
        results={null}
        state={makeDefaultState()}
        refs={makeDefaultRefs()}
        actions={makeDefaultActions()}
      />
    );
    expect(container.querySelector(".calc-empty-state")).not.toBeNull();
    expect(container.textContent).toContain("Configure your league settings");
    expect(container.textContent).toContain("Generate Rankings");
    cleanup();
  });

  it("renders results table when results are provided", () => {
    const state = makeDefaultState();
    state.virtualRows = [
      { row: { Player: "Mike Trout", Team: "LAA", Pos: "OF", DynastyValue: 15.5 }, rank: 1 },
      { row: { Player: "Shohei Ohtani", Team: "LAD", Pos: "DH", DynastyValue: 14.2 }, rank: 2 },
    ];
    state.rankedFiltered = state.virtualRows;
    state.sortedAll = state.virtualRows;
    state.displayCols = ["Player", "Team", "Pos", "DynastyValue"];

    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorResults
        results={{ data: [1, 2] }}
        state={state}
        refs={makeDefaultRefs()}
        actions={makeDefaultActions()}
      />
    );
    expect(container.querySelector(".calc-empty-state")).toBeNull();
    cleanup();
  });

  it("renders search input for filtering", () => {
    const state = makeDefaultState();
    state.rankedFiltered = [{ row: { Player: "Test" }, rank: 1 }];

    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorResults
        results={{ data: [1] }}
        state={state}
        refs={makeDefaultRefs()}
        actions={makeDefaultActions()}
      />
    );
    const searchInput = container.querySelector("[type='text']") as HTMLInputElement;
    expect(searchInput).not.toBeNull();
    cleanup();
  });

  it("renders position filter buttons", () => {
    const state = makeDefaultState();
    const { container, cleanup } = renderToContainer(
      <DynastyCalculatorResults
        results={{ data: [1] }}
        state={state}
        refs={makeDefaultRefs()}
        actions={makeDefaultActions()}
      />
    );
    const text = container.textContent || "";
    expect(text).toContain("All");
    cleanup();
  });
});
