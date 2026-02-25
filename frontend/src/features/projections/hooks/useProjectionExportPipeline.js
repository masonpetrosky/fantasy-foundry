import { useCallback, useMemo, useState } from "react";
import { useProjectionExport } from "./useProjectionExport.js";

export function buildProjectionExportRequest({
  apiBase,
  tab,
  search,
  teamFilter,
  watchlistOnly,
  watchlistKeysFilter,
  careerTotalsView,
  resolvedYearFilter,
  posFilters,
  selectedDynastyYears,
  activeCalculatorJobId,
  sortCol,
  sortDir,
  cols,
  format,
}) {
  const endpointTab = tab === "all" ? "all" : tab;
  const params = new URLSearchParams();
  if (search) params.set("player", search);
  if (teamFilter) params.set("team", teamFilter);
  if (watchlistOnly && watchlistKeysFilter) params.set("player_keys", watchlistKeysFilter);
  if (careerTotalsView) {
    params.set("career_totals", "true");
  } else {
    params.set("year", resolvedYearFilter);
  }
  if (posFilters.length > 0) params.set("pos", posFilters.join(","));
  if (selectedDynastyYears.length > 0) params.set("dynasty_years", selectedDynastyYears.join(","));
  params.set("include_dynasty", "true");
  if (activeCalculatorJobId) params.set("calculator_job_id", activeCalculatorJobId);
  params.set("sort_col", sortCol);
  params.set("sort_dir", sortDir);
  if (cols.length > 0) params.set("columns", cols.join(","));
  params.set("format", format);

  return {
    endpointTab,
    href: `${String(apiBase || "").trim()}/api/projections/export/${endpointTab}?${params.toString()}`,
    format,
    watchlistOnly: Boolean(watchlistOnly),
    yearView: careerTotalsView ? "career_totals" : String(resolvedYearFilter || "").trim(),
    hasCalculatorOverlay: Boolean(activeCalculatorJobId),
  };
}

export function useProjectionExportPipeline({
  apiBase,
  tab,
  search,
  teamFilter,
  watchlistOnly,
  watchlistKeysFilter,
  careerTotalsView,
  resolvedYearFilter,
  posFilters,
  selectedDynastyYears,
  activeCalculatorJobId,
  sortCol,
  sortDir,
  cols,
}) {
  const { executeProjectionExport } = useProjectionExport();
  const [exportError, setExportError] = useState("");
  const [exportingFormat, setExportingFormat] = useState("");

  const exportRequestArgs = useMemo(() => ({
    apiBase,
    tab,
    search,
    teamFilter,
    watchlistOnly,
    watchlistKeysFilter,
    careerTotalsView,
    resolvedYearFilter,
    posFilters,
    selectedDynastyYears,
    activeCalculatorJobId,
    sortCol,
    sortDir,
    cols,
  }), [
    activeCalculatorJobId,
    apiBase,
    careerTotalsView,
    cols,
    posFilters,
    resolvedYearFilter,
    search,
    selectedDynastyYears,
    sortCol,
    sortDir,
    tab,
    teamFilter,
    watchlistKeysFilter,
    watchlistOnly,
  ]);

  const exportCurrentProjections = useCallback(async format => {
    try {
      setExportingFormat(format);
      setExportError("");
      const request = buildProjectionExportRequest({
        ...exportRequestArgs,
        format,
      });
      await executeProjectionExport(request);
    } catch (err) {
      setExportError(err?.message || "Failed to export projections");
    } finally {
      setExportingFormat("");
    }
  }, [executeProjectionExport, exportRequestArgs]);

  return {
    exportError,
    exportingFormat,
    exportCurrentProjections,
    clearExportError: () => setExportError(""),
  };
}
