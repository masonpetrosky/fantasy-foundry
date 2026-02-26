import { useCallback, useMemo, useState } from "react";

export function buildProjectionComparisonColumns({
  tab,
  seasonCol,
}) {
  if (tab === "bat") {
    return [seasonCol, "DynastyValue", "AB", "R", "HR", "RBI", "SB", "AVG"];
  }
  if (tab === "pitch") {
    return [seasonCol, "DynastyValue", "IP", "W", "K", "SV", "ERA", "WHIP"];
  }
  return [
    seasonCol,
    "DynastyValue",
    "AB",
    "R",
    "HR",
    "RBI",
    "SB",
    "IP",
    "W",
    "K",
    "SV",
    "ERA",
    "WHIP",
  ];
}

export function buildProjectionCompareShareHref({
  locationHref,
  compareRowsByKey,
}) {
  const keys = Object.keys(compareRowsByKey || {});
  if (keys.length === 0) return "";
  try {
    const url = new URL(String(locationHref || "").trim());
    url.searchParams.set("compare", keys.join(","));
    return url.toString();
  } catch {
    return "";
  }
}

export function useProjectionComparisonComposition({
  collections,
  tab,
  seasonCol,
}) {
  const [compareShareCopyNotice, setCompareShareCopyNotice] = useState("");
  const comparisonColumns = useMemo(
    () => buildProjectionComparisonColumns({ tab, seasonCol }),
    [tab, seasonCol]
  );

  const clearCompareShareCopyNotice = useCallback(() => {
    setCompareShareCopyNotice("");
  }, []);

  const copyCompareShareLink = useCallback(async () => {
    const href = buildProjectionCompareShareHref({
      locationHref: typeof window !== "undefined" ? window.location.href : "",
      compareRowsByKey: collections.compareRowsByKey,
    });
    if (!href) {
      setCompareShareCopyNotice("Add at least one player to comparison before copying a share link.");
      return;
    }

    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(href);
        setCompareShareCopyNotice("Copied comparison share link.");
        return;
      } catch {
        // Clipboard may be unavailable; fall back to prompt when possible.
      }
    }

    if (typeof window !== "undefined" && typeof window.prompt === "function") {
      window.prompt("Copy comparison share link:", href);
      setCompareShareCopyNotice("Unable to copy automatically; share link shown in prompt.");
      return;
    }
    setCompareShareCopyNotice("Unable to copy share link automatically in this browser.");
  }, [collections.compareRowsByKey]);

  return {
    compareRowsByKey: collections.compareRowsByKey,
    compareRows: collections.compareRows,
    compareRowsCount: collections.compareRows.length,
    maxComparePlayers: collections.maxComparePlayers,
    toggleCompareRow: collections.toggleCompareRow,
    removeCompareRow: collections.removeCompareRow,
    clearCompareRows: collections.clearCompareRows,
    comparisonColumns,
    copyCompareShareLink,
    compareShareCopyNotice,
    clearCompareShareCopyNotice,
    compareShareHydrating: collections.compareShareHydrating,
    compareShareNotice: collections.compareShareNotice,
    clearCompareShareNotice: collections.clearCompareShareNotice,
    workspaceHasComparisonActivity: collections.compareRows.length > 0,
  };
}
