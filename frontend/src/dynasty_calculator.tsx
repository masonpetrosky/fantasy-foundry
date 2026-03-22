import React, { useEffect, useMemo, useRef, useState } from "react";
import { cancelCalculationJob, runCalculationJob } from "./calculation_jobs";
import { DynastyCalculatorSidebar } from "./dynasty_calculator_sidebar";
import { trackEvent } from "./analytics";
import { normalizeCalculatorRunSettingsInput } from "./calculator_submit";
import { trackQuickStartClick } from "./quick_start";
import {
  buildCalculationNotice,
  buildDynastyCalculatorSidebarState,
  buildQuickStartSettings,
  type CalculationResult,
  type CalculatorMeta,
} from "./dynasty_calculator_helpers";
import {
  CALC_LINK_QUERY_PARAM,
  decodeCalculatorSettings,
  mergeKnownCalculatorSettings,
  readSessionFirstRunLandingTimestamp,
  readSessionFirstRunSuccessRecorded,
  writeSessionFirstRunSuccessRecorded,
} from "./app_state_storage";
import {
  buildCalculatorPayload,
  buildDefaultCalculatorSettings,
  resolvePointsScoringDefaults,
  resolvePointsSlotDefaults,
  resolveRotoCategoryDefaults,
  resolveRotoSlotDefaults,
} from "./dynasty_calculator_config";
import type { CalculatorSettings } from "./dynasty_calculator_config";
import type { CalculatorPreset } from "./app_state_storage";
import type { TierLimits } from "./premium";
import type { UseFantraxLeagueResult } from "./hooks/useFantraxLeague";
import { useDynastyCalculatorControls } from "./hooks/useDynastyCalculatorControls";
import { useCalculatorOverlayContext } from "./contexts/CalculatorOverlayContext";

export { buildQuickStartSettings } from "./dynasty_calculator_helpers";

interface RunContext {
  source?: string;
  quickStartMode?: string;
  quickStartSource?: string;
}

interface QuickStartRunOptions {
  source?: string;
  trackClick?: boolean;
}

interface RunMeta {
  jobId?: string;
  [key: string]: unknown;
}

interface CalculationSuccessInfo {
  scoringMode: string;
  startYear: number;
  horizon: number;
  teams: number;
  playerCount: number;
}

export interface DynastyCalculatorActionBridge {
  copyShareLink: () => Promise<void>;
  focusPresetNameInput: () => void;
}

interface DynastyCalculatorProps {
  apiBase: string;
  meta: CalculatorMeta;
  presets: Record<string, CalculatorPreset>;
  setPresets: React.Dispatch<React.SetStateAction<Record<string, CalculatorPreset>>>;
  hasSuccessfulRun: boolean;
  onCalculationSuccess?: (info: CalculationSuccessInfo) => void;
  onSettingsChange?: (settings: CalculatorSettings) => void;
  onRegisterQuickStartRunner?: (runner: ((mode: string) => void) | null) => void;
  onRegisterActionBridge?: (bridge: DynastyCalculatorActionBridge | null) => void;
  onOpenMethodologyGlossary?: (anchorId?: string) => void;
  tierLimits?: TierLimits | null;
  fantrax?: UseFantraxLeagueResult | null;
}

export function DynastyCalculator({
  apiBase,
  meta,
  presets,
  setPresets,
  hasSuccessfulRun,
  onCalculationSuccess,
  onSettingsChange,
  onRegisterQuickStartRunner,
  onRegisterActionBridge,
  onOpenMethodologyGlossary,
  tierLimits,
  fantrax,
}: DynastyCalculatorProps): React.ReactElement {
  const {
    applyCalculatorOverlay: onApplyToMainTable,
    clearCalculatorOverlay: onClearMainTableOverlay,
    calculatorOverlayActive: mainTableOverlayActive,
  } = useCalculatorOverlayContext();
  const API = String(apiBase || "").trim();
  const [settings, setSettings] = useState<CalculatorSettings>(() => buildDefaultCalculatorSettings(meta));
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [presetStatus, setPresetStatus] = useState("");
  const [presetName, setPresetName] = useState("");
  const [selectedPresetName, setSelectedPresetName] = useState("");
  const [lastRunTotal, setLastRunTotal] = useState(0);
  const [calculationNotice, setCalculationNotice] = useState("");
  const calcRequestSeqRef = useRef(0);
  const calcAbortControllerRef = useRef<AbortController | null>(null);
  const calcActiveJobIdRef = useRef("");
  const quickStartRunRef = useRef<((mode: string) => void) | null>(null);
  const firstSuccessTrackedRef = useRef(Boolean(hasSuccessfulRun));
  const presetNameInputRef = useRef<HTMLInputElement | null>(null);

  const availableYears = useMemo(
    () => (meta.years || []).map(Number).filter(Number.isFinite),
    [meta.years]
  );
  const rotoSlotDefaults = useMemo(() => resolveRotoSlotDefaults(meta), [meta]);
  const rotoCategoryDefaults = useMemo(() => resolveRotoCategoryDefaults(), []);
  const pointsSlotDefaults = useMemo(() => resolvePointsSlotDefaults(meta), [meta]);
  const pointsScoringDefaults = useMemo(() => resolvePointsScoringDefaults(meta), [meta]);
  const validationResult = useMemo(
    () => buildCalculatorPayload(settings, availableYears, meta),
    [settings, availableYears, meta]
  );
  const validationError = validationResult.error || "";
  const validationWarning = validationResult.warning || "";

  useEffect(() => {
    if (availableYears.length === 0) return;
    const currentYear = Number(settings.start_year);
    if (!availableYears.includes(currentYear)) {
      setSettings(prev => ({ ...prev, start_year: availableYears[0] }));
    }
  }, [availableYears, settings.start_year]);

  useEffect(() => {
    if (!hasSuccessfulRun) return;
    firstSuccessTrackedRef.current = true;
  }, [hasSuccessfulRun]);

  useEffect(() => {
    const maxSims = tierLimits?.maxSims;
    if (!maxSims || !Number.isFinite(maxSims)) return;
    const current = Number(settings.sims);
    if (Number.isFinite(current) && current > maxSims) {
      setSettings(prev => ({ ...prev, sims: maxSims }));
    }
  }, [tierLimits?.maxSims, settings.sims]);

  useEffect(() => {
    if (tierLimits?.allowPointsMode === false && settings.scoring_mode === "points") {
      applyScoringSetup("roto");
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- applyScoringSetup is stable, only guard on tier/mode changes
  }, [tierLimits?.allowPointsMode, settings.scoring_mode]);

  useEffect(() => {
    if (typeof onSettingsChange !== "function") return;
    onSettingsChange(settings);
  }, [onSettingsChange, settings]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const encoded = String(params.get(CALC_LINK_QUERY_PARAM) || "").trim();
    if (!encoded) return;
    const parsed = decodeCalculatorSettings(encoded);
    if (!parsed) return;
    setSettings(current => mergeKnownCalculatorSettings(current, parsed) as CalculatorSettings);
    setStatus("Loaded calculator settings from share link.");
  }, []);

  useEffect(() => {
    return () => {
      calcRequestSeqRef.current += 1;
      const activeJobId = String(calcActiveJobIdRef.current || "").trim();
      if (activeJobId) {
        void cancelCalculationJob(API, activeJobId);
        calcActiveJobIdRef.current = "";
      }
      if (calcAbortControllerRef.current) {
        calcAbortControllerRef.current.abort();
        calcAbortControllerRef.current = null;
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- cleanup-only effect, API is stable module-level const
  }, []);

  function update(key: string, val: unknown): void {
    setSettings(current => ({ ...current, [key]: val }));
  }

  function applyScoringSetup(nextMode: string): void {
    setSettings(curr => {
      const slotDefaults = nextMode === "points" ? pointsSlotDefaults : rotoSlotDefaults;
      return {
        ...curr,
        scoring_mode: nextMode,
        ...slotDefaults,
      };
    });
  }

  function resetPointsScoringDefaults(): void {
    setSettings(curr => ({ ...curr, ...pointsScoringDefaults }));
  }

  function resetRotoCategoryDefaults(): void {
    setSettings(curr => ({ ...curr, ...rotoCategoryDefaults }));
  }

  function reapplySetupDefaults(): void {
    setSettings(curr => (
      curr.scoring_mode === "points"
        ? { ...curr, ...pointsSlotDefaults, ...pointsScoringDefaults }
        : { ...curr, ...rotoSlotDefaults }
    ));
  }

  function applyQuickStartAndRun(mode: string, options: QuickStartRunOptions = {}): void {
    const normalizedMode = mode === "points" ? "points" : mode === "deep" ? "deep" : "roto";
    const source = String(options.source || "calculator_sidebar").trim() || "calculator_sidebar";
    const shouldTrackQuickStartClick = options.trackClick !== false;
    if (shouldTrackQuickStartClick) {
      trackQuickStartClick({
        mode: normalizedMode === "deep" ? "roto" : normalizedMode,
        source,
        isFirstRun: !firstSuccessTrackedRef.current,
        section: "projections",
      });
    }
    const nextSettings = buildQuickStartSettings({
      mode: normalizedMode,
      settings,
      availableYears,
      meta,
      rotoSlotDefaults,
      rotoCategoryDefaults,
      pointsSlotDefaults,
      pointsScoringDefaults,
    });
    setSettings(nextSettings);
    const quickStartLabel = normalizedMode === "points"
      ? "12-team points"
      : normalizedMode === "deep"
        ? "12-team deep dynasty roto"
        : "12-team 5x5 roto";
    setStatus(`Applied quick start (${quickStartLabel}).`);
    run(nextSettings, {
      source: "quickstart",
      quickStartMode: normalizedMode,
      quickStartSource: source,
    });
  }
  quickStartRunRef.current = (mode: string) => applyQuickStartAndRun(mode, {
    source: "activation_strip",
    trackClick: false,
  });
  const {
    savePreset,
    selectPreset,
    deletePreset,
    copyShareLink,
  } = useDynastyCalculatorControls({
    settings,
    setSettings,
    presets,
    setPresets,
    presetName,
    setPresetName,
    setSelectedPresetName,
    setPresetStatus,
    setStatus,
    presetNameInputRef,
    quickStartRunRef,
    onRegisterQuickStartRunner,
    onRegisterActionBridge,
  });

  function clearAppliedValues(): void {
    if (typeof onClearMainTableOverlay === "function") {
      onClearMainTableOverlay();
    }
    setStatus("Cleared custom calculator values from the main table.");
  }

  function run(runSettings: unknown = settings, runContext: RunContext = {}): void {
    const normalizedSettings = normalizeCalculatorRunSettingsInput(runSettings, settings);
    const payload = buildCalculatorPayload(normalizedSettings, availableYears, meta);
    if (payload.error || !payload.payload) {
      setCalculationNotice("");
      setStatus(`Error: ${payload.error || "Invalid settings"}`);
      return;
    }

    const requestSeq = calcRequestSeqRef.current + 1;
    calcRequestSeqRef.current = requestSeq;
    const previousJobId = String(calcActiveJobIdRef.current || "").trim();
    if (previousJobId) {
      void cancelCalculationJob(API, previousJobId);
      calcActiveJobIdRef.current = "";
    }
    if (calcAbortControllerRef.current) {
      calcAbortControllerRef.current.abort();
    }

    const controller = new AbortController();
    calcAbortControllerRef.current = controller;
    setCalculationNotice("");
    trackEvent("calculator_run_start", {
      source: String(runContext.source || "manual").trim() || "manual",
      quickStartMode: runContext.quickStartMode || "",
      quickStartSource: runContext.quickStartSource || "",
      scoringMode: String(normalizedSettings.scoring_mode || "").trim() || "roto",
      startYear: Number(normalizedSettings.start_year),
      horizon: Number(normalizedSettings.horizon),
    });
    trackEvent("ff_calculation_submit", {
      source: String(runContext.source || "manual").trim() || "manual",
      scoring_mode: String(normalizedSettings.scoring_mode || "").trim() || "roto",
      start_year: Number(normalizedSettings.start_year),
      horizon: Number(normalizedSettings.horizon),
      teams: Number(normalizedSettings.teams),
      quickstart_mode: runContext.quickStartMode || "",
      quickstart_source: runContext.quickStartSource || "",
    });
    setLoading(true);
    setStatus("Submitting simulation...");

    void runCalculationJob({
      apiBase: API,
      payload: payload.payload,
      controller,
      requestSeq,
      requestSeqRef: calcRequestSeqRef,
      activeJobIdRef: calcActiveJobIdRef,
      timeoutSeconds: Number(meta?.calculator_guardrails?.job_timeout_seconds),
      onStatus: (nextStatus: string) => setStatus(nextStatus),
      onCompleted: (result: CalculationResult, runMeta: RunMeta | undefined) => {
        const total = Number(result?.total);
        const resolvedTotal = Number.isFinite(total)
          ? total
          : Array.isArray(result?.data)
            ? result.data.length
            : 0;
        const sessionHadSuccess = readSessionFirstRunSuccessRecorded();
        const sessionLandingTs = readSessionFirstRunLandingTimestamp();
        const resolvedTimeToFirstSuccess = !sessionHadSuccess && Number.isFinite(sessionLandingTs)
          ? Math.max(0, Date.now() - Number(sessionLandingTs))
          : null;
        if (!sessionHadSuccess) {
          writeSessionFirstRunSuccessRecorded(true);
        }
        const firstSuccessfulRun = !firstSuccessTrackedRef.current;
        setLastRunTotal(resolvedTotal);
        setCalculationNotice(buildCalculationNotice(result));
        if (typeof onCalculationSuccess === "function") {
          onCalculationSuccess({
            scoringMode: String(normalizedSettings.scoring_mode || "").trim().toLowerCase() === "points" ? "points" : "roto",
            startYear: Number(normalizedSettings.start_year),
            horizon: Number(normalizedSettings.horizon),
            teams: Number(normalizedSettings.teams),
            playerCount: resolvedTotal,
          });
        }
        if (typeof onApplyToMainTable === "function") {
          onApplyToMainTable(result, normalizedSettings, runMeta ?? {});
        }
        if (firstSuccessfulRun) {
          firstSuccessTrackedRef.current = true;
          trackEvent("ff_calculator_first_success", {
            source: String(runContext.source || "manual").trim() || "manual",
            scoring_mode: String(normalizedSettings.scoring_mode || "").trim() || "roto",
            start_year: Number(normalizedSettings.start_year),
            horizon: Number(normalizedSettings.horizon),
            teams: Number(normalizedSettings.teams),
            player_count: resolvedTotal,
          });
        }
        trackEvent("ff_calculation_success", {
          source: String(runContext.source || "manual").trim() || "manual",
          scoring_mode: String(normalizedSettings.scoring_mode || "").trim() || "roto",
          start_year: Number(normalizedSettings.start_year),
          horizon: Number(normalizedSettings.horizon),
          teams: Number(normalizedSettings.teams),
          player_count: resolvedTotal,
          job_id: runMeta?.jobId || "",
          is_first_run: firstSuccessfulRun,
          time_to_first_success_ms: resolvedTimeToFirstSuccess,
          quickstart_mode: runContext.quickStartMode || "",
          quickstart_source: runContext.quickStartSource || "",
        });
        trackEvent("calculator_run_success", {
          source: String(runContext.source || "manual").trim() || "manual",
          quickStartMode: runContext.quickStartMode || "",
          quickStartSource: runContext.quickStartSource || "",
          scoringMode: String(normalizedSettings.scoring_mode || "").trim() || "roto",
          startYear: Number(normalizedSettings.start_year),
          horizon: Number(normalizedSettings.horizon),
          jobId: runMeta?.jobId || "",
          playerCount: resolvedTotal,
        });
        setLoading(false);
        setStatus(`Applied ${resolvedTotal} players to the table.`);
      },
      onCancelled: () => {
        setLoading(false);
        setCalculationNotice("");
        setStatus("Calculation cancelled.");
      },
      onError: (message: string) => {
        setLoading(false);
        setCalculationNotice("");
        setStatus(`Error: ${message}`);
        trackEvent("ff_calculation_error", {
          source: String(runContext.source || "manual").trim() || "manual",
          scoring_mode: String(normalizedSettings.scoring_mode || "").trim() || "roto",
          start_year: Number(normalizedSettings.start_year),
          horizon: Number(normalizedSettings.horizon),
          teams: Number(normalizedSettings.teams),
          error_message: String(message || "").trim() || "Calculation failed",
          quickstart_mode: runContext.quickStartMode || "",
          quickstart_source: runContext.quickStartSource || "",
        });
      },
    }).finally(() => {
      if (calcAbortControllerRef.current === controller) {
        calcAbortControllerRef.current = null;
      }
    });
  }

  const sidebarState = buildDynastyCalculatorSidebarState({
    settings,
    loading,
    status,
    presetStatus,
    presetName,
    selectedPresetName,
    lastRunTotal,
    calculationNotice,
    hasSuccessfulRun,
    firstSuccessTracked: firstSuccessTrackedRef.current,
    mainTableOverlayActive,
    validationError,
    validationWarning,
    tierLimits,
  });

  const sidebarActions = {
    applyQuickStartAndRun,
    applyScoringSetup,
    clearAppliedValues,
    copyShareLink,
    deletePreset,
    reapplySetupDefaults,
    resetPointsScoringDefaults,
    resetRotoCategoryDefaults,
    run,
    savePreset,
    selectPreset,
    setPresetName,
    update,
    openMethodologyGlossary: onOpenMethodologyGlossary,
  };

  return (
    <div className="fade-up fade-up-1">
      <DynastyCalculatorSidebar
        meta={meta as { years: number[]; [key: string]: unknown }}
        presets={presets}
        settings={settings}
        state={sidebarState}
        actions={sidebarActions}
        fantrax={fantrax || null}
        presetNameInputRef={presetNameInputRef}
      />
    </div>
  );
}
