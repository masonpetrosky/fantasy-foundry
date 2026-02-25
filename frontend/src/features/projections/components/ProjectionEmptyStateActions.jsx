import React from "react";

export const ProjectionEmptyStateActions = React.memo(function ProjectionEmptyStateActions({
  clearAllFilters,
  clearFiltersDisabled,
  showTurnOffWatchlistAction,
  setWatchlistOnly,
  applyProjectionFilterPreset,
  setSearch,
  showSwitchToCareerTotalsAction,
  setYearFilter,
  careerTotalsFilterValue,
}) {
  return (
    <div className="empty-state-actions">
      <button type="button" className="inline-btn" onClick={clearAllFilters} disabled={clearFiltersDisabled}>
        Clear Filters
      </button>
      {showTurnOffWatchlistAction && (
        <button type="button" className="inline-btn" onClick={() => setWatchlistOnly(false)}>
          Turn Off Watchlist View
        </button>
      )}
      <button type="button" className="inline-btn" onClick={() => applyProjectionFilterPreset("all", "empty_state")}>
        Reset To All Players
      </button>
      <button type="button" className="inline-btn" onClick={() => setSearch("Rodriguez")}>
        Try Example Search
      </button>
      {showSwitchToCareerTotalsAction && (
        <button type="button" className="inline-btn" onClick={() => setYearFilter(careerTotalsFilterValue)}>
          Switch To Career Totals
        </button>
      )}
    </div>
  );
});
