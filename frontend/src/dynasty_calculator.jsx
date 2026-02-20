import React, { useEffect, useMemo, useRef, useState } from "react";
import { cancelCalculationJob, runCalculationJob } from "./calculation_jobs.js";
import { DynastyCalculatorSidebar } from "./dynasty_calculator_sidebar.jsx";
import { normalizeCalculatorRunSettingsInput } from "./calculator_submit.js";
import {
  CALC_LINK_QUERY_PARAM,
  decodeCalculatorSettings,
  encodeCalculatorSettings,
  mergeKnownCalculatorSettings,
} from "./app_state_storage.js";
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
} from "./dynasty_calculator_config.js";

export function DynastyCalculator({
  apiBase,
  meta,
  presets,
  setPresets,
  onApplyToMainTable,
  onClearMainTableOverlay,
  mainTableOverlayActive,
}) {
  const API = String(apiBase || "").trim();
  const [settings, setSettings] = useState(() => buildDefaultCalculatorSettings(meta));
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");
  const [presetStatus, setPresetStatus] = useState("");
  const [presetName, setPresetName] = useState("");
  const [selectedPresetName, setSelectedPresetName] = useState("");
  const [lastRunTotal, setLastRunTotal] = useState(0);
  const calcRequestSeqRef = useRef(0);
  const calcAbortControllerRef = useRef(null);
  const calcActiveJobIdRef = useRef("");

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
    const params = new URLSearchParams(window.location.search);
    const encoded = String(params.get(CALC_LINK_QUERY_PARAM) || "").trim();
    if (!encoded) return;
    const parsed = decodeCalculatorSettings(encoded);
    if (!parsed) return;
    setSettings(current => mergeKnownCalculatorSettings(current, parsed));
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
  }, []);

  function update(key, val) {
    setSettings(current => ({ ...current, [key]: val }));
  }

  function applyScoringSetup(nextMode) {
    setSettings(curr => {
      const slotDefaults = nextMode === "points" ? pointsSlotDefaults : rotoSlotDefaults;
      return {
        ...curr,
        scoring_mode: nextMode,
        ...slotDefaults,
      };
    });
  }

  function resetPointsScoringDefaults() {
    setSettings(curr => ({ ...curr, ...pointsScoringDefaults }));
  }

  function resetRotoCategoryDefaults() {
    setSettings(curr => ({ ...curr, ...rotoCategoryDefaults }));
  }

  function reapplySetupDefaults() {
    setSettings(curr => (
      curr.scoring_mode === "points"
        ? { ...curr, ...pointsSlotDefaults, ...pointsScoringDefaults }
        : { ...curr, ...rotoSlotDefaults }
    ));
  }

  function buildQuickStartSettings(mode) {
    const availableStartYear = availableYears.length > 0
      ? availableYears[0]
      : Number(meta?.years?.[0] ?? 2026);
    const currentStartYear = Number(settings.start_year);
    const startYear = availableYears.includes(currentStartYear) ? currentStartYear : availableStartYear;
    const guardrails = meta?.calculator_guardrails || {};
    const defaultIr = Number(guardrails.default_ir_slots);
    const defaultMinors = Number(guardrails.default_minors_slots);
    const commonBase = {
      ...settings,
      teams: 12,
      horizon: 20,
      discount: 0.94,
      bench: 6,
      minors: Number.isInteger(defaultMinors) && defaultMinors >= 0 ? defaultMinors : 0,
      ir: Number.isInteger(defaultIr) && defaultIr >= 0 ? defaultIr : 0,
      ip_min: 0,
      ip_max: "",
      two_way: "sum",
      start_year: startYear,
      recent_projections: 3,
      sims: 300,
    };

    if (mode === "points") {
      return {
        ...commonBase,
        scoring_mode: "points",
        ...pointsSlotDefaults,
        ...pointsScoringDefaults,
      };
    }

    return {
      ...commonBase,
      scoring_mode: "roto",
      ...rotoSlotDefaults,
      ...rotoCategoryDefaults,
    };
  }

  function applyQuickStartAndRun(mode) {
    const nextSettings = buildQuickStartSettings(mode);
    setSettings(nextSettings);
    setStatus(`Applied quick start (${mode === "points" ? "12-team points" : "12-team 5x5 roto"}).`);
    run(nextSettings);
  }

  function savePreset() {
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

  function loadPreset(name) {
    const preset = presets[name];
    if (!preset || typeof preset !== "object") {
      setPresetStatus(`Error: Preset '${name}' was not found.`);
      return;
    }
    setSettings(current => mergeKnownCalculatorSettings(current, preset));
    setPresetName(name);
    setSelectedPresetName(name);
    setPresetStatus(`Loaded preset '${name}'.`);
  }

  function selectPreset(name) {
    const normalizedName = String(name || "").trim();
    setSelectedPresetName(normalizedName);
    if (!normalizedName) {
      setPresetStatus("");
      return;
    }
    loadPreset(normalizedName);
  }

  function deletePreset(name) {
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

  async function copyShareLink() {
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

  function clearAppliedValues() {
    if (typeof onClearMainTableOverlay === "function") {
      onClearMainTableOverlay();
    }
    setStatus("Cleared custom calculator values from the main table.");
  }

  function run(runSettings = settings) {
    const normalizedSettings = normalizeCalculatorRunSettingsInput(runSettings, settings);
    const payload = buildCalculatorPayload(normalizedSettings, availableYears, meta);
    if (payload.error || !payload.payload) {
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
    setLoading(true);
    setStatus("Submitting simulation job...");

    void runCalculationJob({
      apiBase: API,
      payload: payload.payload,
      controller,
      requestSeq,
      requestSeqRef: calcRequestSeqRef,
      activeJobIdRef: calcActiveJobIdRef,
      timeoutSeconds: Number(meta?.calculator_guardrails?.job_timeout_seconds),
      onStatus: nextStatus => setStatus(nextStatus),
      onCompleted: result => {
        const total = Number(result?.total);
        const resolvedTotal = Number.isFinite(total)
          ? total
          : Array.isArray(result?.data)
            ? result.data.length
            : 0;
        setLastRunTotal(resolvedTotal);
        if (typeof onApplyToMainTable === "function") {
          onApplyToMainTable(result, normalizedSettings);
        }
        setLoading(false);
        setStatus(`Done - applied ${resolvedTotal} ranked players to the main table.`);
      },
      onCancelled: () => {
        setLoading(false);
        setStatus("Calculation cancelled.");
      },
      onError: message => {
        setLoading(false);
        setStatus(`Error: ${message}`);
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
  const reservePerTeam = benchPerTeam + minorsPerTeam;
  const totalPlayersPerTeam = hittersPerTeam + pitchersPerTeam + reservePerTeam;
  const pointRulesCount = POINTS_SCORING_FIELDS.length;
  const statusIsError = Boolean(validationError) || String(status || "").startsWith("Error");
  const presetStatusIsError = String(presetStatus || "").startsWith("Error");
  const canSavePreset = String(presetName || "").trim().length > 0;

  const sidebarState = {
    canSavePreset,
    hittersPerTeam,
    isPointsMode,
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
    status,
    statusIsError,
    totalPlayersPerTeam,
    validationError,
    validationWarning,
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
  };

  return (
    <div className="fade-up fade-up-1">
      <DynastyCalculatorSidebar
        meta={meta}
        presets={presets}
        settings={settings}
        state={sidebarState}
        actions={sidebarActions}
      />
    </div>
  );
}
