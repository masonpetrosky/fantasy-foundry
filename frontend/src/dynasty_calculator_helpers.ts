import {
  HITTER_SLOT_FIELDS,
  POINTS_SCORING_FIELDS,
  PITCHER_SLOT_FIELDS,
  ROTO_HITTER_CATEGORY_FIELDS,
  ROTO_PITCHER_CATEGORY_FIELDS,
  coerceBooleanSetting,
  type CalculatorSettings,
} from "./dynasty_calculator_config";
import type { TierLimits } from "./premium";

export interface CalculatorMeta {
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
    enable_replacement_blend: true,
    replacement_blend_alpha: 0.4,
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
      hit_dh: 0,
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
    } as CalculatorSettings;
  }

  return {
    ...commonBase,
    scoring_mode: "roto",
    ...rotoSlotDefaults,
    ...rotoCategoryDefaults,
  } as CalculatorSettings;
}

export interface CalculationResult {
  total?: number;
  data?: unknown[];
  diagnostics?: {
    CenteringMode?: string;
    ForcedRosterFallbackApplied?: boolean;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export function buildCalculationNotice(result: CalculationResult): string {
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

export interface DynastyCalculatorSidebarState {
  calculationNotice: string;
  canSavePreset: boolean;
  hittersPerTeam: number;
  isPointsMode: boolean;
  keeperLimit: number | null;
  lastRunTotal: number;
  loading: boolean;
  mainTableOverlayActive: boolean;
  pointRulesCount: number;
  presetName: string;
  presetStatus: string;
  presetStatusIsError: boolean;
  pitchersPerTeam: number;
  reservePerTeam: number;
  selectedPresetName: string;
  selectedRotoHitCategoryCount: number;
  selectedRotoPitchCategoryCount: number;
  status: string;
  statusIsError: boolean;
  totalPlayersPerTeam: number;
  validationError: string;
  validationWarning: string;
  hasSuccessfulRun: boolean;
  tierLimits: TierLimits | null;
}

interface BuildDynastyCalculatorSidebarStateInput {
  settings: CalculatorSettings;
  loading: boolean;
  status: string;
  presetStatus: string;
  presetName: string;
  selectedPresetName: string;
  lastRunTotal: number;
  calculationNotice: string;
  hasSuccessfulRun: boolean;
  firstSuccessTracked: boolean;
  mainTableOverlayActive: boolean;
  validationError: string;
  validationWarning: string;
  tierLimits?: TierLimits | null;
}

function sumSlots(settings: CalculatorSettings, fields: ReadonlyArray<{ key: string }>): number {
  return fields.reduce((sum, slot) => {
    const value = Number(settings[slot.key]);
    return sum + (Number.isFinite(value) ? value : 0);
  }, 0);
}

export function buildDynastyCalculatorSidebarState({
  settings,
  loading,
  status,
  presetStatus,
  presetName,
  selectedPresetName,
  lastRunTotal,
  calculationNotice,
  hasSuccessfulRun,
  firstSuccessTracked,
  mainTableOverlayActive,
  validationError,
  validationWarning,
  tierLimits,
}: BuildDynastyCalculatorSidebarStateInput): DynastyCalculatorSidebarState {
  const isPointsMode = settings.scoring_mode === "points";
  const selectedRotoHitCategoryCount = ROTO_HITTER_CATEGORY_FIELDS.filter(
    field => coerceBooleanSetting(settings[field.key], field.defaultValue)
  ).length;
  const selectedRotoPitchCategoryCount = ROTO_PITCHER_CATEGORY_FIELDS.filter(
    field => coerceBooleanSetting(settings[field.key], field.defaultValue)
  ).length;
  const hittersPerTeam = sumSlots(settings, HITTER_SLOT_FIELDS);
  const pitchersPerTeam = sumSlots(settings, PITCHER_SLOT_FIELDS);
  const benchPerTeam = Number.isFinite(Number(settings.bench)) ? Number(settings.bench) : 0;
  const minorsPerTeam = Number.isFinite(Number(settings.minors)) ? Number(settings.minors) : 0;
  const irPerTeam = Number.isFinite(Number(settings.ir)) ? Number(settings.ir) : 0;
  const reservePerTeam = benchPerTeam + minorsPerTeam + irPerTeam;
  const totalPlayersPerTeam = hittersPerTeam + pitchersPerTeam + reservePerTeam;
  const keeperLimitRaw = Number(settings.keeper_limit);
  const keeperLimit = Number.isInteger(keeperLimitRaw) && keeperLimitRaw > 0 ? keeperLimitRaw : null;

  return {
    calculationNotice,
    canSavePreset: String(presetName || "").trim().length > 0,
    hittersPerTeam,
    isPointsMode,
    keeperLimit,
    lastRunTotal,
    loading,
    mainTableOverlayActive: Boolean(mainTableOverlayActive),
    pointRulesCount: POINTS_SCORING_FIELDS.length,
    presetName,
    presetStatus,
    presetStatusIsError: String(presetStatus || "").startsWith("Error"),
    pitchersPerTeam,
    reservePerTeam,
    selectedPresetName,
    selectedRotoHitCategoryCount,
    selectedRotoPitchCategoryCount,
    status,
    statusIsError: Boolean(validationError) || String(status || "").startsWith("Error"),
    totalPlayersPerTeam,
    validationError,
    validationWarning,
    hasSuccessfulRun: Boolean(hasSuccessfulRun) || firstSuccessTracked,
    tierLimits: tierLimits ?? null,
  };
}
