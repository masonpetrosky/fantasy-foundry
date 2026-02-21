import { useCallback, useState } from "react";
import { trackEvent } from "../../../analytics.js";
import { parseDownloadFilename } from "../../../download_filename.js";
import { triggerBlobDownload } from "../../../download_helpers.js";
import { formatApiError, readResponsePayload } from "../../../request_helpers.js";

export function useProjectionExport({
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
  const [exportError, setExportError] = useState("");
  const [exportingFormat, setExportingFormat] = useState("");

  const exportCurrentProjections = useCallback(async format => {
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
    const href = `${String(apiBase || "").trim()}/api/projections/export/${endpointTab}?${params.toString()}`;

    try {
      setExportingFormat(format);
      setExportError("");
      trackEvent("export_click", {
        format,
        tab: endpointTab,
        watchlistOnly,
        yearView: careerTotalsView ? "career_totals" : resolvedYearFilter,
        hasCalculatorOverlay: Boolean(activeCalculatorJobId),
      });
      const response = await fetch(href, {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });
      if (!response.ok) {
        const parsed = await readResponsePayload(response);
        throw new Error(formatApiError(response.status, parsed.payload, parsed.rawText));
      }
      const blob = await response.blob();
      const fallback = `projections-${endpointTab}.${format}`;
      const filename = parseDownloadFilename(response.headers.get("content-disposition"), fallback);
      triggerBlobDownload(filename, blob);
    } catch (err) {
      setExportError(err?.message || "Failed to export projections");
    } finally {
      setExportingFormat("");
    }
  }, [
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

  return {
    exportError,
    exportingFormat,
    exportCurrentProjections,
    clearExportError: () => setExportError(""),
  };
}
