import { useMemo } from "react";

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

export function useProjectionComparisonComposition({
  collections,
  tab,
  seasonCol,
}) {
  const comparisonColumns = useMemo(
    () => buildProjectionComparisonColumns({ tab, seasonCol }),
    [tab, seasonCol]
  );

  return {
    compareRowsByKey: collections.compareRowsByKey,
    compareRows: collections.compareRows,
    compareRowsCount: collections.compareRows.length,
    maxComparePlayers: collections.maxComparePlayers,
    toggleCompareRow: collections.toggleCompareRow,
    removeCompareRow: collections.removeCompareRow,
    clearCompareRows: collections.clearCompareRows,
    comparisonColumns,
    workspaceHasComparisonActivity: collections.compareRows.length > 0,
  };
}
