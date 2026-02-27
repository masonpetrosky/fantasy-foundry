import React from "react";

interface ProjectionEmptyStateActionsProps {
  clearAllFilters: () => void;
  clearFiltersDisabled: boolean;
  showTurnOffWatchlistAction: boolean;
  setWatchlistOnly: (value: boolean) => void;
  applyProjectionFilterPreset: (preset: string, source: string) => void;
  setSearch: (value: string) => void;
  showSwitchToCareerTotalsAction: boolean;
  setYearFilter: (value: string) => void;
  careerTotalsFilterValue: string;
}

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
}: ProjectionEmptyStateActionsProps): React.ReactElement {
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
