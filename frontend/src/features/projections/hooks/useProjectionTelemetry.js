import { useEffect, useRef, useState } from "react";
import { trackEvent } from "../../../analytics.js";

export function buildProjectionEmptyStateMarker({
  tab,
  resolvedYearFilter,
  teamFilter,
  watchlistOnly,
  search,
  posFilters,
}) {
  return [
    String(tab || "").trim(),
    String(resolvedYearFilter || "").trim(),
    String(teamFilter || "").trim(),
    watchlistOnly ? "watchlist" : "all",
    String(search || "").trim(),
    Array.isArray(posFilters) ? posFilters.join(",") : "",
  ].join("|");
}

export function buildProjectionRefreshMarker({
  tab,
  offset,
  displayedPage,
  totalRows,
}) {
  const rows = Array.isArray(displayedPage) ? displayedPage : [];
  const firstRow = rows[0] || {};
  return [
    String(tab || "").trim(),
    Number(offset) || 0,
    rows.length,
    Number(totalRows) || 0,
    String(firstRow.Player || ""),
    String(firstRow.Team || ""),
    String(firstRow.Year || ""),
  ].join("|");
}

export function useProjectionTelemetry({
  loading,
  error,
  displayedPage,
  tab,
  resolvedYearFilter,
  teamFilter,
  watchlistOnly,
  search,
  posFilters,
  offset,
  totalRows,
}) {
  const emptyStateTrackedRef = useRef("");
  const lastRefreshMarkerRef = useRef("");
  const [lastRefreshedLabel, setLastRefreshedLabel] = useState("");
  const rows = Array.isArray(displayedPage) ? displayedPage : [];

  useEffect(() => {
    if (loading || error || rows.length > 0) return;

    const marker = buildProjectionEmptyStateMarker({
      tab,
      resolvedYearFilter,
      teamFilter,
      watchlistOnly,
      search,
      posFilters,
    });
    if (emptyStateTrackedRef.current === marker) return;

    emptyStateTrackedRef.current = marker;
    trackEvent("ff_projection_empty_state_seen", {
      tab,
      watchlist_only: Boolean(watchlistOnly),
      has_search: Boolean(String(search || "").trim()),
      has_team_filter: Boolean(String(teamFilter || "").trim()),
      has_pos_filters: Array.isArray(posFilters) && posFilters.length > 0,
      year_view: resolvedYearFilter,
    });
  }, [
    error,
    loading,
    posFilters,
    resolvedYearFilter,
    rows.length,
    search,
    tab,
    teamFilter,
    watchlistOnly,
  ]);

  useEffect(() => {
    if (loading || error || rows.length === 0) return;

    const marker = buildProjectionRefreshMarker({
      tab,
      offset,
      displayedPage: rows,
      totalRows,
    });
    if (lastRefreshMarkerRef.current === marker) return;

    lastRefreshMarkerRef.current = marker;
    setLastRefreshedLabel(
      new Date().toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
    );
  }, [error, loading, offset, rows, tab, totalRows]);

  return {
    lastRefreshedLabel,
  };
}
