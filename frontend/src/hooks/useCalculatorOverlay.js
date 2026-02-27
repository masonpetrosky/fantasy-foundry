import { useCallback, useState } from "react";
import { stablePlayerKeyFromRow } from "../app_state_storage";

function buildCalculatorOverlayMap(result) {
  const rows = Array.isArray(result?.data) ? result.data : [];
  const byPlayerKey = {};

  rows.forEach(row => {
    const key = stablePlayerKeyFromRow(row);
    if (!key) return;

    const overlayRow = {};
    if (row?.DynastyValue != null && row?.DynastyValue !== "") {
      overlayRow.DynastyValue = row.DynastyValue;
    }
    Object.keys(row || {}).forEach(col => {
      if (!col.startsWith("Value_")) return;
      const value = row[col];
      if (value == null || value === "") return;
      overlayRow[col] = value;
    });
    if (Object.keys(overlayRow).length === 0) return;
    byPlayerKey[key] = overlayRow;
  });

  return byPlayerKey;
}

export function useCalculatorOverlay(dataVersion) {
  const [calculatorOverlayByPlayerKey, setCalculatorOverlayByPlayerKey] = useState({});
  const [calculatorOverlayActive, setCalculatorOverlayActive] = useState(false);
  const [calculatorOverlayJobId, setCalculatorOverlayJobId] = useState("");
  const [calculatorOverlayDataVersion, setCalculatorOverlayDataVersion] = useState("");
  const [calculatorOverlaySummary, setCalculatorOverlaySummary] = useState(null);

  const calculatorOverlayPlayerCount = Object.keys(calculatorOverlayByPlayerKey).length;

  const applyCalculatorOverlay = useCallback((result, settings, runMeta) => {
    const nextOverlay = buildCalculatorOverlayMap(result);
    const hasOverlay = Object.keys(nextOverlay).length > 0;
    const nextJobId = hasOverlay ? String(runMeta?.jobId || "").trim() : "";
    const nextDataVersion = hasOverlay ? String(dataVersion || "").trim() : "";
    setCalculatorOverlayByPlayerKey(nextOverlay);
    setCalculatorOverlayActive(hasOverlay);
    setCalculatorOverlayJobId(nextJobId);
    setCalculatorOverlayDataVersion(nextDataVersion);
    setCalculatorOverlaySummary(hasOverlay ? {
      scoringMode: String(settings?.scoring_mode || "").trim().toLowerCase() === "points" ? "points" : "roto",
      startYear: Number(settings?.start_year),
      horizon: Number(settings?.horizon),
    } : null);
  }, [dataVersion]);

  const clearCalculatorOverlay = useCallback(() => {
    setCalculatorOverlayByPlayerKey({});
    setCalculatorOverlayActive(false);
    setCalculatorOverlayJobId("");
    setCalculatorOverlayDataVersion("");
    setCalculatorOverlaySummary(null);
  }, []);

  return {
    calculatorOverlayByPlayerKey,
    calculatorOverlayActive,
    calculatorOverlayJobId,
    calculatorOverlayDataVersion,
    calculatorOverlaySummary,
    calculatorOverlayPlayerCount,
    applyCalculatorOverlay,
    clearCalculatorOverlay,
  };
}
