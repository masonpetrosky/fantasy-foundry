import { useCallback, useState } from "react";
import { stablePlayerKeyFromRow } from "../app_state_storage";

interface OverlayRow {
  [col: string]: unknown;
}

interface OverlaySummary {
  scoringMode: "roto" | "points";
  startYear: number;
  horizon: number;
  [key: string]: unknown;
}

function buildCalculatorOverlayMap(result: unknown): Record<string, OverlayRow> {
  const rows = Array.isArray((result as Record<string, unknown>)?.data)
    ? (result as Record<string, unknown>).data as Record<string, unknown>[]
    : [];
  const byPlayerKey: Record<string, OverlayRow> = {};

  rows.forEach(row => {
    const key = stablePlayerKeyFromRow(row);
    if (!key) return;

    const overlayRow: OverlayRow = {};
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

export function useCalculatorOverlay(dataVersion: string): {
  calculatorOverlayByPlayerKey: Record<string, OverlayRow>;
  calculatorOverlayActive: boolean;
  calculatorOverlayJobId: string;
  calculatorOverlayDataVersion: string;
  calculatorOverlaySummary: OverlaySummary | null;
  calculatorOverlayPlayerCount: number;
  applyCalculatorOverlay: (result: unknown, settings: Record<string, unknown>, runMeta: { jobId?: string }) => void;
  clearCalculatorOverlay: () => void;
} {
  const [calculatorOverlayByPlayerKey, setCalculatorOverlayByPlayerKey] = useState<Record<string, OverlayRow>>({});
  const [calculatorOverlayActive, setCalculatorOverlayActive] = useState(false);
  const [calculatorOverlayJobId, setCalculatorOverlayJobId] = useState("");
  const [calculatorOverlayDataVersion, setCalculatorOverlayDataVersion] = useState("");
  const [calculatorOverlaySummary, setCalculatorOverlaySummary] = useState<OverlaySummary | null>(null);

  const calculatorOverlayPlayerCount = Object.keys(calculatorOverlayByPlayerKey).length;

  const applyCalculatorOverlay = useCallback((result: unknown, settings: Record<string, unknown>, runMeta: { jobId?: string }) => {
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
