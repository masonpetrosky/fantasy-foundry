export const DEFAULT_FILTER_SUMMARY_FALLBACK = "None";

export function shortJobId(jobId: unknown, maxLength = 8): string {
  const value = String(jobId || "").trim();
  if (!value) return "";
  if (value.length <= maxLength) return value;
  return value.slice(0, maxLength);
}

export interface ActiveFilterChipsInput {
  search: unknown;
  teamFilter: unknown;
  resolvedYearFilter: unknown;
  posFilters: unknown;
  watchlistOnly: unknown;
  careerTotalsFilterValue: unknown;
}

export function buildActiveFilterChips({
  search,
  teamFilter,
  resolvedYearFilter,
  posFilters,
  watchlistOnly,
  careerTotalsFilterValue,
}: ActiveFilterChipsInput): string[] {
  const chips: string[] = [];
  const searchValue = String(search || "").trim();
  const teamValue = String(teamFilter || "").trim();
  const yearValue = String(resolvedYearFilter || "").trim();
  const positionValues = Array.isArray(posFilters) ? posFilters as string[] : [];

  if (searchValue) chips.push(`Player: ${searchValue}`);
  if (teamValue) chips.push(`Team: ${teamValue}`);
  if (yearValue && yearValue !== String(careerTotalsFilterValue || "")) {
    chips.push(`Year: ${yearValue}`);
  }
  if (positionValues.length > 0) {
    chips.push(`Pos: ${positionValues.join(", ")}`);
  }
  if (watchlistOnly) {
    chips.push("Watchlist only");
  }

  return chips;
}

export interface SwipeHintInput {
  canScrollLeft: boolean;
  canScrollRight: boolean;
}

export interface SwipeHintResult {
  showSwipeHint: boolean;
  swipeHintText: string;
}

export function resolveProjectionSwipeHint({
  canScrollLeft,
  canScrollRight,
}: SwipeHintInput): SwipeHintResult {
  const hasHorizontalOverflow = Boolean(canScrollLeft) || Boolean(canScrollRight);
  if (!hasHorizontalOverflow) {
    return {
      showSwipeHint: false,
      swipeHintText: "",
    };
  }
  if (!canScrollLeft && canScrollRight) {
    return {
      showSwipeHint: true,
      swipeHintText: "Swipe left for more columns \u2192",
    };
  }
  if (canScrollLeft && canScrollRight) {
    return {
      showSwipeHint: true,
      swipeHintText: "\u2190 Swipe both directions for more columns \u2192",
    };
  }
  return {
    showSwipeHint: true,
    swipeHintText: "\u2190 Swipe right to return",
  };
}

export interface EmptyStateInput {
  watchlistOnly: unknown;
  resolvedYearFilter: unknown;
  hasActiveFilters: unknown;
  careerTotalsFilterValue: unknown;
}

export interface EmptyStateModel {
  headline: string;
  guidance: string;
  clearFiltersDisabled: boolean;
  showTurnOffWatchlistAction: boolean;
  showSwitchToCareerTotalsAction: boolean;
}

export function resolveProjectionEmptyStateModel({
  watchlistOnly,
  resolvedYearFilter,
  hasActiveFilters,
  careerTotalsFilterValue,
}: EmptyStateInput): EmptyStateModel {
  const isWatchlistOnly = Boolean(watchlistOnly);
  const inCareerTotalsView = String(resolvedYearFilter || "").trim()
    === String(careerTotalsFilterValue || "").trim();

  return {
    headline: isWatchlistOnly
      ? "No watchlist players matched this view."
      : "No projections matched these filters.",
    guidance: isWatchlistOnly
      ? "Turn off Watchlist View or clear filters to expand results."
      : "Adjust or clear filters to expand results.",
    clearFiltersDisabled: !hasActiveFilters,
    showTurnOffWatchlistAction: isWatchlistOnly,
    showSwitchToCareerTotalsAction: !inCareerTotalsView,
  };
}

export interface OverlayStatusInput {
  overlaySummaryParts: unknown;
  overlayJobId: unknown;
  overlayAppliedDataVersion: unknown;
  resolvedDataVersion: unknown;
}

export interface OverlayStatusMeta {
  chips: string[];
  isStale: boolean;
  sourceJobId: string;
}

export function buildOverlayStatusMeta({
  overlaySummaryParts,
  overlayJobId,
  overlayAppliedDataVersion,
  resolvedDataVersion,
}: OverlayStatusInput): OverlayStatusMeta {
  const chips: string[] = [];
  const summaryParts = Array.isArray(overlaySummaryParts) ? overlaySummaryParts as unknown[] : [];
  const sourceJobId = shortJobId(overlayJobId);
  const sourceDataVersion = String(overlayAppliedDataVersion || "").trim();
  const currentDataVersion = String(resolvedDataVersion || "").trim();

  summaryParts.forEach(part => {
    const value = String(part || "").trim();
    if (value) chips.push(value);
  });

  if (sourceJobId) chips.push(`Job ${sourceJobId}`);

  const isStale = Boolean(sourceDataVersion && currentDataVersion && sourceDataVersion !== currentDataVersion);
  if (isStale) chips.push("Stale");

  return {
    chips,
    isStale,
    sourceJobId,
  };
}
