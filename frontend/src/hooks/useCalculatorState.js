import { useCallback, useEffect, useRef, useState } from "react";
import { trackEvent } from "../analytics";
import {
  CALC_LINK_QUERY_PARAM,
  readCalculatorPanelOpenPreference,
  readCalculatorPresets,
  readLastSuccessfulCalcRun,
  writeCalculatorPanelOpenPreference,
  writeCalculatorPresets,
  writeLastSuccessfulCalcRun,
} from "../app_state_storage";

const ACTIVATION_SPRINT_ENABLED = String(import.meta.env.VITE_FF_ACTIVATION_SPRINT_V1 || "1").trim() !== "0";

/**
 * Extracts calculator-related state, refs, effects, and callbacks from App.
 * Accepts { section, setSection, meta } and returns everything the App JSX needs.
 */
export function useCalculatorState({ section, setSection, meta }) {
  const [calculatorPanelOpen, setCalculatorPanelOpen] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const hasSharedCalculatorState = Boolean(String(params.get(CALC_LINK_QUERY_PARAM) || "").trim());
    if (hasSharedCalculatorState) return true;
    const savedPanelOpenState = readCalculatorPanelOpenPreference();
    return typeof savedPanelOpenState === "boolean" ? savedPanelOpenState : true;
  });
  const [lastSuccessfulCalcRun, setLastSuccessfulCalcRun] = useState(() => readLastSuccessfulCalcRun());
  const [pendingMethodologyAnchor, setPendingMethodologyAnchor] = useState("");
  const [presets, setPresets] = useState(() => readCalculatorPresets());
  const [calculatorSettings, setCalculatorSettings] = useState(null);

  const calculatorSectionRef = useRef(null);
  const calculatorHeadingRef = useRef(null);
  const calculatorPanelOpenSourceRef = useRef("");
  const previousCalculatorPanelOpenRef = useRef(calculatorPanelOpen);

  const scrollToCalculator = useCallback(() => {
    if (!calculatorSectionRef.current) return;
    calculatorSectionRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const focusFirstCalculatorInput = useCallback(() => {
    const firstInput = document.getElementById("calc-teams-input");
    if (firstInput && typeof firstInput.focus === "function") {
      firstInput.focus({ preventScroll: true });
      return;
    }
    if (!calculatorHeadingRef.current || typeof calculatorHeadingRef.current.focus !== "function") return;
    calculatorHeadingRef.current.focus({ preventScroll: true });
  }, []);

  const openCalculatorPanel = useCallback((source = "app_action") => {
    calculatorPanelOpenSourceRef.current = String(source || "").trim() || "app_action";
    setSection("projections");
    setCalculatorPanelOpen(true);
  }, [setSection]);

  const handleCalculationSuccess = useCallback(summary => {
    const teams = Number(summary?.teams);
    const horizon = Number(summary?.horizon);
    if (!Number.isFinite(teams) || teams <= 0 || !Number.isFinite(horizon) || horizon <= 0) return;
    const nextSummary = {
      scoringMode: String(summary?.scoringMode || "").trim().toLowerCase() === "points" ? "points" : "roto",
      teams: Math.round(teams),
      horizon: Math.round(horizon),
      startYear: Number.isFinite(Number(summary?.startYear)) ? Math.round(Number(summary.startYear)) : null,
      playerCount: Number.isFinite(Number(summary?.playerCount)) ? Math.max(0, Math.round(Number(summary.playerCount))) : 0,
      completedAt: new Date().toISOString(),
    };
    setLastSuccessfulCalcRun(nextSummary);
    writeLastSuccessfulCalcRun(nextSummary);
  }, []);

  const openMethodologyGlossary = useCallback(anchorId => {
    const nextAnchor = String(anchorId || "").trim();
    if (!nextAnchor) return;
    setSection("methodology");
    setPendingMethodologyAnchor(nextAnchor);
  }, [setSection]);

  // Track panel open/close
  useEffect(() => {
    const wasOpen = previousCalculatorPanelOpenRef.current;
    if (!wasOpen && calculatorPanelOpen) {
      trackEvent("ff_calculator_panel_open", {
        source: calculatorPanelOpenSourceRef.current || "panel_toggle",
      });
      calculatorPanelOpenSourceRef.current = "";
    }
    previousCalculatorPanelOpenRef.current = calculatorPanelOpen;
  }, [calculatorPanelOpen]);

  // Preload calculator module
  useEffect(() => {
    if (!ACTIVATION_SPRINT_ENABLED) return;
    if (section !== "projections" || !meta) return;
    void import("../dynasty_calculator.jsx");
  }, [meta, section]);

  // Persist presets
  useEffect(() => {
    writeCalculatorPresets(presets);
  }, [presets]);

  // Persist panel open preference
  useEffect(() => {
    writeCalculatorPanelOpenPreference(calculatorPanelOpen);
  }, [calculatorPanelOpen]);

  // Methodology anchor scroll
  useEffect(() => {
    if (section !== "methodology" || !pendingMethodologyAnchor) return undefined;
    const raf = window.requestAnimationFrame(() => {
      const target = document.getElementById(pendingMethodologyAnchor);
      if (target && typeof target.scrollIntoView === "function") {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
      setPendingMethodologyAnchor("");
    });
    return () => window.cancelAnimationFrame(raf);
  }, [pendingMethodologyAnchor, section]);

  return {
    calculatorPanelOpen,
    setCalculatorPanelOpen,
    calculatorSettings,
    setCalculatorSettings,
    lastSuccessfulCalcRun,
    presets,
    setPresets,
    pendingMethodologyAnchor,
    calculatorSectionRef,
    calculatorHeadingRef,
    calculatorPanelOpenSourceRef,
    scrollToCalculator,
    focusFirstCalculatorInput,
    openCalculatorPanel,
    handleCalculationSuccess,
    openMethodologyGlossary,
  };
}
