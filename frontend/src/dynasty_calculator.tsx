import React, { useEffect, useMemo, useRef, useState } from "react";
import { cancelCalculationJob, runCalculationJob } from "./calculation_jobs";
import { DynastyCalculatorSidebar } from "./dynasty_calculator_sidebar";
import { trackEvent } from "./analytics";
import { normalizeCalculatorRunSettingsInput } from "./calculator_submit";
import { trackQuickStartClick } from "./quick_start";
import {
  CALC_LINK_QUERY_PARAM,
  decodeCalculatorSettings,
  encodeCalculatorSettings,
  mergeKnownCalculatorSettings,
  readSessionFirstRunLandingTimestamp,
  readSessionFirstRunSuccessRecorded,
  writeSessionFirstRunSuccessRecorded,
} from "./app_state_storage";
import {
  HITTER_SLOT_FIELDS,
  POINTS_SCORING_FIELDS,
  PITCHER_SLOT_FIELDS,
  ROTO_HITTER_CATEGORY_FIELDS,
  ROTO_PITCHER_CATEGORY_FIELDS,
  buildCalculatorPayload,
  buildDefaultCalculatorSettings,
  coerceBooleanSetting,
  resolvePointsScoringDefaults,
  resolvePointsSlotDefaults,
  resolveRotoCategoryDefaults,
  resolveRotoSlotDefaults,
} from "./dynasty_calculator_config";
import type { CalculatorSettings } from "./dynasty_calculator_config";
import type { CalculatorPreset } from "./app_state_storage";
import type { TierLimits } from "./premium";
import type { UseFantraxLeagueResult } from "./hooks/useFantraxLeague";
import { useCalculatorOverlayContext } from "./contexts/CalculatorOverlayContext";

interface CalculatorMeta {
  years?: number[];
  calculator_guardrails?: {
    default_ir_slots?: number;
    default_minors_slots?: number;
    job_timeout_seconds?: number;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

interface QuickStartInput {
  mode: string;
  settings: CalculatorSettings;
  availableYears: number[];
  meta: CalculatorMeta;
  rotoSlotDefaults: Record<string, unknown>;
  rotoCategoryDefaults: Record<string, unknown>;
  pointsSlotDefaults: Record<string, unknown>;
  pointsScoringDefaults: Record<string, unknown>;
}

export function buildQuickStartSettings({
  mode,
  settings,
  availableYears,
  meta,
  rotoSlotDefaults,
  rotoCategoryDefaults,
  pointsSlotDefaults,
  pointsScoringDefaults,
}: QuickStartInput): CalculatorSettings {
  const availableStartYear = availableYears.length > 0
    ? availableYears[0]
    : Number(meta?.years?.[0] ?? 2026);
  const currentStartYear = Number(settings.start_year);
  const startYear = availableYears.includes(currentStartYear) ? currentStartYear : availableStartYear;
  const guardrails = meta?.calculator_guardrails || {};
  const defaultIr = Number(guardrails.default_ir_slots);
  const defaultMinors = Number(guardrails.default_minors_slots);
  const commonBase: CalculatorSettings = {
    ...settings,
    teams: 12,
    horizon: 20,
    discount: 0.94,
    bench: 6,
    minors: Number.isInteger(defaultMinors) && defaultMinors >= 0 ? defaultMinors : 0,
    ir: Number.isInteger(defaultIr) && defaultIr >= 0 ? defaultIr : 0,
    keeper_limit: null,
    ip_min: 0,
    ip_max: "",
    points_valuation_mode: "season_total",
    weekly_starts_cap: null,
    allow_same_day_starts_overflow: false,
    weekly_acquisition_cap: null,
    two_way: "sum",
    sgp_denominator_mode: "classic",
    sgp_winsor_low_pct: 0.1,
    sgp_winsor_high_pct: 0.9,
    sgp_epsilon_counting: 0.15,
    sgp_epsilon_ratio: 0.0015,
    enable_playing_time_reliability: false,
    enable_age_risk_adjustment: false,
    enable_prospect_risk_adjustment: false,
    enable_bench_stash_relief: false,
    bench_negative_penalty: 0.55,
    enable_ir_stash_relief: false,
    ir_negative_penalty: 0.2,
    enable_replacement_blend: false,
    replacement_blend_alpha: 0.7,
    start_year: startYear,
    sims: 300,
  };

  if (mode === "points") {
    return {
      ...commonBase,
      scoring_mode: "points",
      ...pointsSlotDefaults,
      ...pointsScoringDefaults,
    } as CalculatorSettings;
  }

  if (mode === "deep") {
    return {
      ...commonBase,
      scoring_mode: "roto",
      hit_c: 2,
      hit_1b: 1,
      hit_2b: 1,
      hit_3b: 1,
      hit_ss: 1,
      hit_ci: 1,
      hit_mi: 1,
      hit_of: 5,
      hit_ut: 2,
      pit_p: 3,
      pit_sp: 3,
      pit_rp: 3,
      bench: 14,
      minors: 20,
      ir: 8,
      ip_min: 1000,
      ip_max: 1500,
      roto_hit_r: true,
      roto_hit_rbi: true,
      roto_hit_hr: true,
      roto_hit_sb: true,
      roto_hit_avg: true,
      roto_hit_obp: false,
      roto_hit_slg: false,
      roto_hit_ops: true,
      roto_hit_h: false,
      roto_hit_bb: false,
      roto_hit_2b: false,
      roto_hit_tb: false,
      roto_pit_w: true,
      roto_pit_k: true,
      roto_pit_sv: false,
      roto_pit_era: true,
      roto_pit_whip: true,
      roto_pit_qs: false,
      roto_pit_qa3: true,
      roto_pit_svh: true,
      enable_prospect_risk_adjustment: true,
      enable_bench_stash_relief: true,
      bench_negative_penalty: 0.55,
      enable_ir_stash_relief: true,
      ir_negative_penalty: 0.2,
    } as CalculatorSettings;
  }

  return {
    ...commonBase,
    scoring_mode: "roto",
    ...rotoSlotDefaults,
    ...rotoCategoryDefaults,
  } as CalculatorSettings;
}

interface RunContext {
  source?: string;
  quickStartMode?: string;
  quickStartSource?: string;
}

interface QuickStartRunOptions {
  source?: string;
  trackClick?: boolean;
}

interface CalculationResult {
  total?: number;
  data?: unknown[];
  diagnostics?: {
    CenteringMode?: string;
    ForcedRosterFallbackApplied?: boolean;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

interface RunMeta {
  jobId?: string;
  [key: string]: unknown;
}

function buildCalculationNotice(result: CalculationResult): string {
  const diagnostics = result?.diagnostics;
  if (!diagnostics || typeof diagnostics !== "object") {
    return "";
  }
  const centeringMode = String(diagnostics.CenteringMode || "").trim().toLowerCase();
  const fallbackApplied = diagnostics.ForcedRosterFallbackApplied === true;
  if (!fallbackApplied && centeringMode !== "forced_roster" && centeringMode !== "forced_roster_minor_cost") {
    return "";
  }
  if (centeringMode === "forced_roster_minor_cost") {
    return "Deep-roster fallback applied: fringe players are ranked by forced-roster holding cost, with zero-value MiLB stashes priced by minor-slot scarcity because the normal cutoff landed at raw dynasty value 0.";
  }
  return "Deep-roster fallback applied: fringe players are ranked by forced-roster holding cost because the normal cutoff landed at raw dynasty value 0.";
}

interface CalculationSuccessInfo {
  scoringMode: string;
  startYear: number;
  horizon: number;
  teams: number;
  playerCount: number;
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

  useEffect(() => {
    if (typeof onRegisterQuickStartRunner !== "function") return undefined;
    onRegisterQuickStartRunner((mode: string) => {
      if (typeof quickStartRunRef.current === "function") {
        quickStartRunRef.current(mode);
      }
    });
    return () => {
      onRegisterQuickStartRunner(null);
    };
  }, [onRegisterQuickStartRunner]);

  function savePreset(): void {
    const name = String(presetName || "").trim();
    if (!name) {
      setPresetStatus("Error: Enter a preset name before saving.");
      return;
    }
    const existingPreset = presets[name];
    const isUpdate = Boolean(existingPreset && typeof existingPreset === "object");
    setPresets(current => ({ ...current, [name]: settings }));
    setPresetName(name);
    setSelectedPresetName(name);
    setPresetStatus(`${isUpdate ? "Updated" : "Saved new"} preset '${name}'.`);
  }

  function loadPreset(name: string): void {
    const preset = presets[name];
    if (!preset || typeof preset !== "object") {
      setPresetStatus(`Error: Preset '${name}' was not found.`);
      return;
    }
    setSettings(current => mergeKnownCalculatorSettings(current, preset as Record<string, unknown>) as CalculatorSettings);
    setPresetName(name);
    setSelectedPresetName(name);
    setPresetStatus(`Loaded preset '${name}'.`);
  }

  function selectPreset(name: string): void {
    const normalizedName = String(name || "").trim();
    setSelectedPresetName(normalizedName);
    if (!normalizedName) {
      setPresetStatus("");
      return;
    }
    loadPreset(normalizedName);
  }

  function deletePreset(name: string): void {
    const normalizedName = String(name || "").trim();
    if (!normalizedName) return;
    if (!window.confirm(`Delete preset '${normalizedName}'?`)) {
      return;
    }
    setPresets(current => {
      const next = { ...current };
      delete next[normalizedName];
      return next;
    });
    setPresetName(current => (current === normalizedName ? "" : current));
    setSelectedPresetName(current => (current === normalizedName ? "" : current));
    setPresetStatus(`Deleted preset '${normalizedName}'.`);
  }

  async function copyShareLink(): Promise<void> {
    const encoded = encodeCalculatorSettings(settings);
    if (!encoded) {
      setStatus("Error: Unable to encode settings for sharing.");
      return;
    }
    const url = new URL(window.location.href);
    url.searchParams.set(CALC_LINK_QUERY_PARAM, encoded);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(url.toString());
      } else {
        throw new Error("Clipboard API unavailable");
      }
      setStatus("Copied share link to clipboard.");
      window.history.replaceState({}, "", url.toString());
    } catch {
      window.prompt("Copy calculator link:", url.toString());
      setStatus("Share link is ready.");
    }
  }

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

  const isPointsMode = settings.scoring_mode === "points";
  const selectedRotoHitCategoryCount = ROTO_HITTER_CATEGORY_FIELDS.filter(
    field => coerceBooleanSetting(settings[field.key], field.defaultValue)
  ).length;
  const selectedRotoPitchCategoryCount = ROTO_PITCHER_CATEGORY_FIELDS.filter(
    field => coerceBooleanSetting(settings[field.key], field.defaultValue)
  ).length;
  const hittersPerTeam = useMemo(() => HITTER_SLOT_FIELDS.reduce((sum, slot) => {
    const value = Number(settings[slot.key]);
    return sum + (Number.isFinite(value) ? value : 0);
  }, 0), [settings]);
  const pitchersPerTeam = useMemo(() => PITCHER_SLOT_FIELDS.reduce((sum, slot) => {
    const value = Number(settings[slot.key]);
    return sum + (Number.isFinite(value) ? value : 0);
  }, 0), [settings]);
  const benchPerTeam = Number.isFinite(Number(settings.bench)) ? Number(settings.bench) : 0;
  const minorsPerTeam = Number.isFinite(Number(settings.minors)) ? Number(settings.minors) : 0;
  const irPerTeam = Number.isFinite(Number(settings.ir)) ? Number(settings.ir) : 0;
  const reservePerTeam = benchPerTeam + minorsPerTeam + irPerTeam;
  const totalPlayersPerTeam = hittersPerTeam + pitchersPerTeam + reservePerTeam;
  const keeperLimitRaw = Number(settings.keeper_limit);
  const keeperLimit = Number.isInteger(keeperLimitRaw) && keeperLimitRaw > 0 ? keeperLimitRaw : null;
  const pointRulesCount = POINTS_SCORING_FIELDS.length;
  const statusIsError = Boolean(validationError) || String(status || "").startsWith("Error");
  const presetStatusIsError = String(presetStatus || "").startsWith("Error");
  const canSavePreset = String(presetName || "").trim().length > 0;

  const sidebarState = {
    canSavePreset,
    hittersPerTeam,
    isPointsMode,
    keeperLimit,
    lastRunTotal,
    loading,
    mainTableOverlayActive: Boolean(mainTableOverlayActive),
    pointRulesCount,
    presetName,
    presetStatus,
    presetStatusIsError,
    pitchersPerTeam,
    reservePerTeam,
    selectedPresetName,
    selectedRotoHitCategoryCount,
    selectedRotoPitchCategoryCount,
    calculationNotice,
    status,
    statusIsError,
    totalPlayersPerTeam,
    validationError,
    validationWarning,
    hasSuccessfulRun: Boolean(hasSuccessfulRun) || firstSuccessTrackedRef.current,
    tierLimits: tierLimits ?? null,
  };

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
      />
    </div>
  );
}
