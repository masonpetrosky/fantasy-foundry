import { useCallback, useEffect, useMemo, useState } from "react";
import {
  readProjectionFilterPresets,
  writeProjectionFilterPresets,
} from "../../../app_state_storage";
import type {
  ProjectionFilterPreset,
  ProjectionFilterPresetBundle,
} from "../../../app_state_storage";
import {
  CAREER_TOTALS_FILTER_VALUE,
  DEFAULT_PROJECTIONS_SORT_COL,
  DEFAULT_PROJECTIONS_SORT_DIR,
  DEFAULT_PROJECTIONS_TAB,
} from "../../../hooks/useProjectionsData";
import { trackEvent } from "../../../analytics";

export function defaultProjectionFilterPreset(
  tab: string = DEFAULT_PROJECTIONS_TAB,
  watchlistOnly = false,
): ProjectionFilterPreset {
  return {
    tab,
    search: "",
    teamFilter: "",
    yearFilter: CAREER_TOTALS_FILTER_VALUE,
    posFilters: [],
    watchlistOnly: Boolean(watchlistOnly),
    sortCol: DEFAULT_PROJECTIONS_SORT_COL,
    sortDir: DEFAULT_PROJECTIONS_SORT_DIR,
  };
}

export function projectionFilterPresetValuesForKey({
  presetKey,
  projectionFilterPresets,
}: {
  presetKey: string;
  projectionFilterPresets: ProjectionFilterPresetBundle;
}): ProjectionFilterPreset | null {
  const key = String(presetKey || "").trim().toLowerCase();
  if (!key) return null;
  if (key === "all") return defaultProjectionFilterPreset(DEFAULT_PROJECTIONS_TAB, false);
  if (key === "watchlist") return defaultProjectionFilterPreset(DEFAULT_PROJECTIONS_TAB, true);
  if (key === "hitters") return defaultProjectionFilterPreset("bat", false);
  if (key === "pitchers") return defaultProjectionFilterPreset("pitch", false);
  if (key === "custom") return projectionFilterPresets?.custom || null;
  return null;
}

export interface FilterState {
  tab: string;
  search: string;
  teamFilter: string;
  resolvedYearFilter: string;
  posFilters: string[];
  watchlistOnly: boolean;
  sortCol: string;
  sortDir: string;
}

export function matchesProjectionFilterPreset(
  filterState: FilterState,
  preset: ProjectionFilterPreset | null,
): boolean {
  if (!preset) return false;
  return (
    filterState.tab === (preset.tab || DEFAULT_PROJECTIONS_TAB)
    && filterState.search === (preset.search || "")
    && filterState.teamFilter === (preset.teamFilter || "")
    && filterState.resolvedYearFilter === (preset.yearFilter || CAREER_TOTALS_FILTER_VALUE)
    && filterState.watchlistOnly === Boolean(preset.watchlistOnly)
    && filterState.sortCol === (preset.sortCol || DEFAULT_PROJECTIONS_SORT_COL)
    && filterState.sortDir === (preset.sortDir || DEFAULT_PROJECTIONS_SORT_DIR)
    && JSON.stringify(filterState.posFilters) === JSON.stringify(Array.isArray(preset.posFilters) ? preset.posFilters : [])
  );
}

export function resolveActiveProjectionPresetKey(
  filterState: FilterState,
  projectionFilterPresets: ProjectionFilterPresetBundle,
): string {
  if (matchesProjectionFilterPreset(filterState, defaultProjectionFilterPreset(DEFAULT_PROJECTIONS_TAB, false))) {
    return "all";
  }
  if (matchesProjectionFilterPreset(filterState, defaultProjectionFilterPreset(DEFAULT_PROJECTIONS_TAB, true))) {
    return "watchlist";
  }
  if (matchesProjectionFilterPreset(filterState, defaultProjectionFilterPreset("bat", false))) {
    return "hitters";
  }
  if (matchesProjectionFilterPreset(filterState, defaultProjectionFilterPreset("pitch", false))) {
    return "pitchers";
  }
  if (projectionFilterPresets?.custom && matchesProjectionFilterPreset(filterState, projectionFilterPresets.custom)) {
    return "custom";
  }
  return "";
}

export interface FilterActions {
  setSearch: (value: string) => void;
  setTeamFilter: (value: string) => void;
  setYearFilter: (value: string) => void;
  setPosFilters: (value: string[]) => void;
  setWatchlistOnly: (value: boolean) => void;
  setSortCol: (value: string) => void;
  setSortDir: (value: string) => void;
  setOffset: (value: number) => void;
  setTab: (value: string) => void;
}

export interface UseProjectionFilterPresetsInput {
  filterActions: FilterActions;
  filterState: FilterState;
  setShowPosMenu: (value: boolean) => void;
}

export interface UseProjectionFilterPresetsResult {
  projectionFilterPresets: ProjectionFilterPresetBundle;
  applyProjectionFilterPreset: (presetKey: string, source?: string) => void;
  saveCustomProjectionPreset: () => void;
  activeProjectionPresetKey: string;
  clearAllFilters: () => void;
}

export function useProjectionFilterPresets({
  filterActions,
  filterState,
  setShowPosMenu,
}: UseProjectionFilterPresetsInput): UseProjectionFilterPresetsResult {
  const [projectionFilterPresets, setProjectionFilterPresets] = useState<ProjectionFilterPresetBundle>(() => readProjectionFilterPresets());

  const clearAllFilters = useCallback(() => {
    filterActions.setSearch("");
    filterActions.setTeamFilter("");
    filterActions.setYearFilter(CAREER_TOTALS_FILTER_VALUE);
    filterActions.setPosFilters([]);
    filterActions.setWatchlistOnly(false);
    filterActions.setSortCol(DEFAULT_PROJECTIONS_SORT_COL);
    filterActions.setSortDir(DEFAULT_PROJECTIONS_SORT_DIR);
    setShowPosMenu(false);
    filterActions.setOffset(0);
  }, [filterActions, setShowPosMenu]);

  const applyProjectionFilterPreset = useCallback((presetKey: string, source = "toolbar") => {
    const key = String(presetKey || "").trim().toLowerCase();
    if (!key) return;

    const applyPresetValues = (values: ProjectionFilterPreset) => {
      filterActions.setTab(values.tab || DEFAULT_PROJECTIONS_TAB);
      filterActions.setSearch(values.search || "");
      filterActions.setTeamFilter(values.teamFilter || "");
      filterActions.setYearFilter(values.yearFilter || CAREER_TOTALS_FILTER_VALUE);
      filterActions.setPosFilters(Array.isArray(values.posFilters) ? values.posFilters : []);
      filterActions.setWatchlistOnly(Boolean(values.watchlistOnly));
      filterActions.setSortCol(values.sortCol || DEFAULT_PROJECTIONS_SORT_COL);
      filterActions.setSortDir(values.sortDir || DEFAULT_PROJECTIONS_SORT_DIR);
      setShowPosMenu(false);
      filterActions.setOffset(0);
    };

    const presetValues = projectionFilterPresetValuesForKey({
      presetKey: key,
      projectionFilterPresets,
    });
    if (!presetValues) {
      return;
    }
    applyPresetValues(presetValues);

    trackEvent("ff_projection_filter_preset_apply", {
      preset: key,
      source,
      watchlist_only: key === "watchlist",
    });
  }, [filterActions, projectionFilterPresets, setShowPosMenu]);

  const saveCustomProjectionPreset = useCallback(() => {
    const customPreset: ProjectionFilterPreset = {
      tab: filterState.tab,
      search: filterState.search,
      teamFilter: filterState.teamFilter,
      yearFilter: filterState.resolvedYearFilter,
      posFilters: filterState.posFilters,
      watchlistOnly: filterState.watchlistOnly,
      sortCol: filterState.sortCol,
      sortDir: filterState.sortDir,
    };
    setProjectionFilterPresets({ custom: customPreset });
    trackEvent("ff_projection_filter_preset_apply", {
      preset: "custom_save",
      source: "toolbar",
      watchlist_only: filterState.watchlistOnly,
    });
  }, [filterState]);

  const activeProjectionPresetKey = useMemo(() => {
    return resolveActiveProjectionPresetKey(filterState, projectionFilterPresets);
  }, [filterState, projectionFilterPresets]);

  useEffect(() => {
    writeProjectionFilterPresets(projectionFilterPresets);
  }, [projectionFilterPresets]);

  return {
    projectionFilterPresets,
    applyProjectionFilterPreset,
    saveCustomProjectionPreset,
    activeProjectionPresetKey,
    clearAllFilters,
  };
}
