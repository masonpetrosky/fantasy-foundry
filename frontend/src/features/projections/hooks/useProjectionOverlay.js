import { useCallback, useEffect, useMemo, useState } from "react";
import { buildOverlayStatusMeta } from "../view_state";
import { stablePlayerKeyFromRow } from "../../../app_state_storage";

export function useProjectionOverlay({
  calculatorOverlayByPlayerKey,
  calculatorOverlayActive,
  calculatorOverlayJobId,
  calculatorOverlayDataVersion,
  calculatorOverlayPlayerCount,
  calculatorOverlaySummary,
  dataVersion,
}) {
  const [showOverlayWhy, setShowOverlayWhy] = useState(false);

  const resolvedCalculatorOverlayByPlayerKey = useMemo(() => (
    calculatorOverlayByPlayerKey && typeof calculatorOverlayByPlayerKey === "object" && !Array.isArray(calculatorOverlayByPlayerKey)
      ? calculatorOverlayByPlayerKey
      : {}
  ), [calculatorOverlayByPlayerKey]);

  const resolvedCalculatorOverlayPlayerCount = useMemo(
    () => Number.isFinite(Number(calculatorOverlayPlayerCount))
      ? Math.max(0, Number(calculatorOverlayPlayerCount))
      : Object.keys(resolvedCalculatorOverlayByPlayerKey).length,
    [calculatorOverlayPlayerCount, resolvedCalculatorOverlayByPlayerKey]
  );

  const hasCalculatorOverlay = Boolean(calculatorOverlayActive) && resolvedCalculatorOverlayPlayerCount > 0;

  const overlayScoringMode = String(calculatorOverlaySummary?.scoringMode || "").trim().toLowerCase();
  const overlayStartYear = Number(calculatorOverlaySummary?.startYear);
  const overlayHorizon = Number(calculatorOverlaySummary?.horizon);

  const overlaySummaryParts = useMemo(() => {
    const parts = [];
    if (overlayScoringMode === "points") {
      parts.push("Points mode");
    } else if (overlayScoringMode === "roto") {
      parts.push("Roto mode");
    }
    if (Number.isFinite(overlayStartYear) && overlayStartYear > 0) {
      parts.push(`Start ${overlayStartYear}`);
    }
    if (Number.isFinite(overlayHorizon) && overlayHorizon > 0) {
      parts.push(`${overlayHorizon}-year horizon`);
    }
    return parts;
  }, [overlayHorizon, overlayScoringMode, overlayStartYear]);

  const overlayStatusMeta = useMemo(() => buildOverlayStatusMeta({
    overlaySummaryParts,
    overlayJobId: calculatorOverlayJobId,
    overlayAppliedDataVersion: calculatorOverlayDataVersion,
    resolvedDataVersion: dataVersion,
  }), [calculatorOverlayDataVersion, calculatorOverlayJobId, dataVersion, overlaySummaryParts]);

  const applyCalculatorOverlayToRows = useCallback(rows => {
    if (!Array.isArray(rows) || rows.length === 0) return [];
    if (!hasCalculatorOverlay) return rows;
    return rows.map(row => {
      const key = stablePlayerKeyFromRow(row);
      const overlay = resolvedCalculatorOverlayByPlayerKey[key];
      if (!overlay || typeof overlay !== "object") return row;
      return { ...row, ...overlay, DynastyMatchStatus: "matched" };
    });
  }, [hasCalculatorOverlay, resolvedCalculatorOverlayByPlayerKey]);

  useEffect(() => {
    if (!hasCalculatorOverlay) {
      setShowOverlayWhy(false);
    }
  }, [hasCalculatorOverlay]);

  return {
    hasCalculatorOverlay,
    resolvedCalculatorOverlayPlayerCount,
    overlayStatusMeta,
    showOverlayWhy,
    setShowOverlayWhy,
    applyCalculatorOverlayToRows,
  };
}
