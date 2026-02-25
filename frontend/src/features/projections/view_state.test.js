import { describe, expect, it } from "vitest";

import {
  buildActiveFilterChips,
  buildOverlayStatusMeta,
  resolveProjectionEmptyStateModel,
  resolveProjectionSwipeHint,
  shortJobId,
} from "./view_state.js";

describe("shortJobId", () => {
  it("trims and shortens long ids", () => {
    expect(shortJobId(" job-abcdef123456 ")).toBe("job-abcd");
    expect(shortJobId("job-123", 16)).toBe("job-123");
  });
});

describe("buildActiveFilterChips", () => {
  it("returns only active filters", () => {
    const chips = buildActiveFilterChips({
      search: "  Julio ",
      teamFilter: "SEA",
      resolvedYearFilter: "2028",
      posFilters: ["OF", "DH"],
      watchlistOnly: true,
      careerTotalsFilterValue: "__career_totals__",
    });

    expect(chips).toEqual([
      "Player: Julio",
      "Team: SEA",
      "Year: 2028",
      "Pos: OF, DH",
      "Watchlist only",
    ]);
  });

  it("treats rest-of-career year as default", () => {
    const chips = buildActiveFilterChips({
      search: "",
      teamFilter: "",
      resolvedYearFilter: "__career_totals__",
      posFilters: [],
      watchlistOnly: false,
      careerTotalsFilterValue: "__career_totals__",
    });

    expect(chips).toEqual([]);
  });
});

describe("buildOverlayStatusMeta", () => {
  it("includes summary chips and source job id", () => {
    const result = buildOverlayStatusMeta({
      overlaySummaryParts: ["Points mode", "Start 2028"],
      overlayJobId: "job-abcdef123456",
      overlayAppliedDataVersion: "v1",
      resolvedDataVersion: "v1",
    });

    expect(result).toEqual({
      chips: ["Points mode", "Start 2028", "Job job-abcd"],
      isStale: false,
      sourceJobId: "job-abcd",
    });
  });

  it("marks stale when data version changes", () => {
    const result = buildOverlayStatusMeta({
      overlaySummaryParts: ["Roto mode"],
      overlayJobId: "job-1",
      overlayAppliedDataVersion: "old-build",
      resolvedDataVersion: "new-build",
    });

    expect(result.isStale).toBe(true);
    expect(result.chips).toContain("Stale");
  });
});

describe("resolveProjectionSwipeHint", () => {
  it("returns hidden hint state when no overflow is present", () => {
    expect(resolveProjectionSwipeHint({
      canScrollLeft: false,
      canScrollRight: false,
    })).toEqual({
      showSwipeHint: false,
      swipeHintText: "",
    });
  });

  it("returns direction-specific hint copy", () => {
    expect(resolveProjectionSwipeHint({
      canScrollLeft: false,
      canScrollRight: true,
    })).toEqual({
      showSwipeHint: true,
      swipeHintText: "Swipe left for more columns →",
    });
    expect(resolveProjectionSwipeHint({
      canScrollLeft: true,
      canScrollRight: true,
    })).toEqual({
      showSwipeHint: true,
      swipeHintText: "← Swipe both directions for more columns →",
    });
    expect(resolveProjectionSwipeHint({
      canScrollLeft: true,
      canScrollRight: false,
    })).toEqual({
      showSwipeHint: true,
      swipeHintText: "← Swipe right to return",
    });
  });
});

describe("resolveProjectionEmptyStateModel", () => {
  it("returns watchlist-specific messaging and actions", () => {
    const model = resolveProjectionEmptyStateModel({
      watchlistOnly: true,
      resolvedYearFilter: "2029",
      hasActiveFilters: true,
      careerTotalsFilterValue: "__career_totals__",
    });

    expect(model).toEqual({
      headline: "No watchlist players matched this view.",
      guidance: "Turn off Watchlist View or clear filters to expand results.",
      clearFiltersDisabled: false,
      showTurnOffWatchlistAction: true,
      showSwitchToCareerTotalsAction: true,
    });
  });

  it("returns default messaging for all-player career totals view", () => {
    const model = resolveProjectionEmptyStateModel({
      watchlistOnly: false,
      resolvedYearFilter: "__career_totals__",
      hasActiveFilters: false,
      careerTotalsFilterValue: "__career_totals__",
    });

    expect(model).toEqual({
      headline: "No projections matched these filters.",
      guidance: "Adjust or clear filters to expand results.",
      clearFiltersDisabled: true,
      showTurnOffWatchlistAction: false,
      showSwitchToCareerTotalsAction: false,
    });
  });
});
