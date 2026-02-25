export const DEFAULT_FILTER_SUMMARY_FALLBACK = "None";

export function shortJobId(jobId, maxLength = 8) {
  const value = String(jobId || "").trim();
  if (!value) return "";
  if (value.length <= maxLength) return value;
  return value.slice(0, maxLength);
}

export function buildActiveFilterChips({
  search,
  teamFilter,
  resolvedYearFilter,
  posFilters,
  watchlistOnly,
  careerTotalsFilterValue,
}) {
  const chips = [];
  const searchValue = String(search || "").trim();
  const teamValue = String(teamFilter || "").trim();
  const yearValue = String(resolvedYearFilter || "").trim();
  const positionValues = Array.isArray(posFilters) ? posFilters : [];

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

export function resolveProjectionSwipeHint({
  canScrollLeft,
  canScrollRight,
}) {
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
      swipeHintText: "Swipe left for more columns →",
    };
  }
  if (canScrollLeft && canScrollRight) {
    return {
      showSwipeHint: true,
      swipeHintText: "← Swipe both directions for more columns →",
    };
  }
  return {
    showSwipeHint: true,
    swipeHintText: "← Swipe right to return",
  };
}

export function resolveProjectionEmptyStateModel({
  watchlistOnly,
  resolvedYearFilter,
  hasActiveFilters,
  careerTotalsFilterValue,
}) {
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

export function buildOverlayStatusMeta({
  overlaySummaryParts,
  overlayJobId,
  overlayAppliedDataVersion,
  resolvedDataVersion,
}) {
  const chips = [];
  const summaryParts = Array.isArray(overlaySummaryParts) ? overlaySummaryParts : [];
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
