import { useCallback, useMemo, useState } from "react";
import { useProjectionExport } from "./useProjectionExport";
import type { ProjectionExportRequest } from "./useProjectionExport";

export interface BuildProjectionExportRequestInput {
  apiBase: string;
  tab: string;
  search: string;
  teamFilter: string;
  watchlistOnly: boolean;
  watchlistKeysFilter: string;
  careerTotalsView: boolean;
  resolvedYearFilter: string;
  posFilters: string[];
  selectedDynastyYears: string[];
  activeCalculatorJobId: string;
  sortCol: string;
  sortDir: string;
  cols: string[];
  format: string;
}

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
}: BuildProjectionExportRequestInput): ProjectionExportRequest {
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

export interface UseProjectionExportPipelineInput {
  apiBase: string;
  tab: string;
  search: string;
  teamFilter: string;
  watchlistOnly: boolean;
  watchlistKeysFilter: string;
  careerTotalsView: boolean;
  resolvedYearFilter: string;
  posFilters: string[];
  selectedDynastyYears: string[];
  activeCalculatorJobId: string;
  sortCol: string;
  sortDir: string;
  cols: string[];
}

export interface UseProjectionExportPipelineResult {
  exportError: string;
  exportingFormat: string;
  exportCurrentProjections: (format: string) => Promise<void>;
  clearExportError: () => void;
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
}: UseProjectionExportPipelineInput): UseProjectionExportPipelineResult {
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

  const exportCurrentProjections = useCallback(async (format: string) => {
    try {
      setExportingFormat(format);
      setExportError("");
      const request = buildProjectionExportRequest({
        ...exportRequestArgs,
        format,
      });
      await executeProjectionExport(request);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to export projections";
      setExportError(message);
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
