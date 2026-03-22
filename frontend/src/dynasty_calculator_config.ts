export {
  CALC_SEARCH_DEBOUNCE_MS,
  HITTER_SLOT_FIELDS,
  PITCHER_SLOT_FIELDS,
  POINTS_BATTING_FIELDS,
  POINTS_PITCHING_FIELDS,
  POINTS_RESULT_BOOLEAN_COLS,
  POINTS_RESULT_COLUMN_LABELS,
  POINTS_RESULT_NUMERIC_COLS,
  POINTS_RESULT_SLOT_COLS,
  POINTS_RESULT_SUMMARY_COLS,
  POINTS_RESULT_SUMMARY_FIELDS,
  POINTS_SCORING_FIELDS,
  ROTO_COUNTING_STAT_COLS,
  ROTO_HITTER_CATEGORY_FIELDS,
  ROTO_PITCHER_CATEGORY_FIELDS,
  ROTO_RATE_STAT_COLS,
  ROTO_STAT_DYNASTY_PREFIX,
  ROTO_THREE_DECIMAL_RATE_COLS,
  SLOT_INPUT_MAX,
  SLOT_INPUT_MIN,
  coerceBooleanSetting,
  isRotoStatDynastyCol,
  resolvePointsScoringDefaults,
  resolvePointsSlotDefaults,
  resolveRotoCategoryDefaults,
  resolveRotoSelectedStatColumns,
  resolveRotoSlotDefaults,
  rotoStatDynastyLabel,
} from "./dynasty_calculator_catalog";
import {
  HITTER_SLOT_FIELDS,
  PITCHER_SLOT_FIELDS,
  POINTS_SCORING_FIELDS,
  ROTO_CATEGORY_FIELDS,
  ROTO_HITTER_CATEGORY_FIELDS,
  ROTO_PITCHER_CATEGORY_FIELDS,
  SLOT_INPUT_MAX,
  SLOT_INPUT_MIN,
  coerceBooleanSetting,
  resolvePointsScoringDefaults,
  resolveRotoCategoryDefaults,
  resolveRotoSlotDefaults,
  type CalculatorMeta,
} from "./dynasty_calculator_catalog";
export type {
  CalculatorGuardrails,
  CalculatorMeta,
  PointsResultSummaryField,
  PointsScoringField,
  RotoCategoryField,
  SlotField,
} from "./dynasty_calculator_catalog";

export interface CalculatorSettings {
  [key: string]: unknown;
  mode: string;
  scoring_mode: string;
  points_valuation_mode: string;
  teams: number;
  sims: number;
  horizon: number;
  discount: number;
  bench: number;
  minors: number;
  ir: number;
  keeper_limit: number | null;
  ip_min: number;
  ip_max: string | number | null;
  weekly_starts_cap: number | null;
  allow_same_day_starts_overflow: boolean;
  weekly_acquisition_cap: number | null;
  two_way: string;
  sgp_denominator_mode: string;
  sgp_winsor_low_pct: number;
  sgp_winsor_high_pct: number;
  sgp_epsilon_counting: number;
  sgp_epsilon_ratio: number;
  enable_playing_time_reliability: boolean;
  enable_age_risk_adjustment: boolean;
  enable_replacement_blend: boolean;
  replacement_blend_alpha: number;
  start_year: number;
  auction_budget: number | null;
}

export interface PayloadResult {
  payload?: Record<string, unknown>;
  error?: string;
  warning?: string;
}

function parseOptionalIntegerSetting(
  value: unknown,
  options: {
    min: number;
    max: number;
    label: string;
    treatZeroAsBlank?: boolean;
  },
): { value: number | null; error?: string } {
  const {
    min,
    max,
    label,
    treatZeroAsBlank = false,
  } = options;
  const text = String(value ?? "").trim();
  if (!text || text.toLowerCase() === "none") {
    return { value: null };
  }
  const parsed = Number(text);
  if (treatZeroAsBlank && parsed === 0) {
    return { value: null };
  }
  if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
    return { value: null, error: `${label} must be an integer between ${min} and ${max}, or blank.` };
  }
  return { value: parsed };
}

export function buildDefaultCalculatorSettings(meta: CalculatorMeta | null | undefined): CalculatorSettings {
  const guardrails = meta?.calculator_guardrails || {};
  const defaultIr = Number(guardrails?.default_ir_slots);
  const defaultMinors = Number(guardrails?.default_minors_slots);
  return {
    mode: "common",
    scoring_mode: "roto",
    points_valuation_mode: "season_total",
    teams: 12,
    sims: 300,
    horizon: 20,
    discount: 0.94,
    ...resolveRotoSlotDefaults(meta),
    bench: 6,
    minors: Number.isInteger(defaultMinors) && defaultMinors >= 0 ? defaultMinors : 0,
    ir: Number.isInteger(defaultIr) && defaultIr >= 0 ? defaultIr : 0,
    keeper_limit: null,
    ip_min: 0,
    ip_max: "",
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
    start_year: Number(meta?.years?.[0] ?? 2026),
    auction_budget: null,
    ...resolveRotoCategoryDefaults(),
    ...resolvePointsScoringDefaults(meta),
  };
}
export function buildCalculatorPayload(settings: Record<string, unknown>, availableYears: number[] | null | undefined, meta: CalculatorMeta | null | undefined): PayloadResult {
  // League mode removed — always use common.
  const mode = "common";

  const scoringMode = String(settings.scoring_mode ?? "").trim().toLowerCase() || "roto";
  if (scoringMode !== "roto" && scoringMode !== "points") {
    return { error: "Scoring Mode must be either 'roto' or 'points'." };
  }
  const pointsValuationMode = String(settings.points_valuation_mode ?? "").trim().toLowerCase() || "season_total";
  if (pointsValuationMode !== "season_total" && pointsValuationMode !== "weekly_h2h" && pointsValuationMode !== "daily_h2h") {
    return { error: "Points valuation mode must be 'season_total', 'weekly_h2h', or 'daily_h2h'." };
  }

  const parsedSlots: Record<string, number> = {};
  for (const slot of [...HITTER_SLOT_FIELDS, ...PITCHER_SLOT_FIELDS]) {
    const value = Number(settings[slot.key]);
    if (!Number.isInteger(value) || value < SLOT_INPUT_MIN || value > SLOT_INPUT_MAX) {
      return { error: `${slot.label} slots must be an integer between ${SLOT_INPUT_MIN} and ${SLOT_INPUT_MAX}.` };
    }
    parsedSlots[slot.key] = value;
  }

  const hittersPerTeam = HITTER_SLOT_FIELDS.reduce((sum, slot) => sum + parsedSlots[slot.key], 0);
  if (hittersPerTeam <= 0) {
    return { error: "At least one hitter slot must be greater than 0." };
  }

  const pitchersPerTeam = PITCHER_SLOT_FIELDS.reduce(
    (sum: number, slot) => sum + parsedSlots[slot.key],
    0
  );
  if (pitchersPerTeam <= 0) {
    return { error: "At least one pitcher slot must be greater than 0." };
  }

  const teams = Number(settings.teams);
  if (!Number.isInteger(teams) || teams < 2 || teams > 30) {
    return { error: "Teams must be an integer between 2 and 30." };
  }

  const sims = Number(settings.sims);
  if (!Number.isInteger(sims) || sims < 1 || sims > 5000) {
    return { error: "Simulations must be an integer between 1 and 5000." };
  }

  const horizon = Number(settings.horizon);
  if (!Number.isInteger(horizon) || horizon < 1 || horizon > 20) {
    return { error: "Horizon must be an integer between 1 and 20." };
  }

  const discount = Number(settings.discount);
  if (!Number.isFinite(discount) || discount <= 0 || discount > 1) {
    return { error: "Discount must be a number greater than 0 and up to 1." };
  }

  const bench = Number(settings.bench);
  if (!Number.isInteger(bench) || bench < 0 || bench > 40) {
    return { error: "Bench slots must be an integer between 0 and 40." };
  }

  const minors = Number(settings.minors);
  if (!Number.isInteger(minors) || minors < 0 || minors > 60) {
    return { error: "Minor slots must be an integer between 0 and 60." };
  }

  const ir = Number(settings.ir);
  if (!Number.isInteger(ir) || ir < 0 || ir > 40) {
    return { error: "IR slots must be an integer between 0 and 40." };
  }
  const keeperLimitResult = parseOptionalIntegerSetting(settings.keeper_limit, {
    min: 1,
    max: 60,
    label: "Keeper limit",
    treatZeroAsBlank: true,
  });
  if (keeperLimitResult.error) {
    return { error: keeperLimitResult.error };
  }
  const weeklyStartsCapResult = parseOptionalIntegerSetting(settings.weekly_starts_cap, {
    min: 1,
    max: 40,
    label: "Weekly starts cap",
    treatZeroAsBlank: true,
  });
  if (weeklyStartsCapResult.error) {
    return { error: weeklyStartsCapResult.error };
  }
  const weeklyAcquisitionCapResult = parseOptionalIntegerSetting(settings.weekly_acquisition_cap, {
    min: 0,
    max: 40,
    label: "Weekly acquisition cap",
  });
  if (weeklyAcquisitionCapResult.error) {
    return { error: weeklyAcquisitionCapResult.error };
  }

  const ipMin = Number(settings.ip_min);
  if (!Number.isFinite(ipMin) || ipMin < 0) {
    return { error: "IP Min must be a non-negative number." };
  }

  const ipMaxText = String(settings.ip_max ?? "").trim();
  let ipMax: number | null = null;
  if (ipMaxText && ipMaxText.toLowerCase() !== "none") {
    const parsedIpMax = Number(ipMaxText);
    if (!Number.isFinite(parsedIpMax) || parsedIpMax < 0) {
      return { error: "IP Max must be a non-negative number or 'none'." };
    }
    ipMax = parsedIpMax;
  }

  if (ipMax != null && ipMax < ipMin) {
    return { error: "IP Max must be greater than or equal to IP Min." };
  }

  const startYear = Number(settings.start_year);
  if (!Number.isInteger(startYear)) {
    return { error: "Start Year must be an integer." };
  }
  if (Array.isArray(availableYears) && availableYears.length > 0 && !availableYears.includes(startYear)) {
    return { error: "Start Year must match an available projection year." };
  }

  const twoWay = String(settings.two_way ?? "").trim().toLowerCase();
  if (twoWay !== "sum" && twoWay !== "max") {
    return { error: "Two-Way mode must be either 'sum' or 'max'." };
  }
  const sgpDenominatorMode = String(settings.sgp_denominator_mode ?? "").trim().toLowerCase() || "classic";
  if (sgpDenominatorMode !== "classic" && sgpDenominatorMode !== "robust") {
    return { error: "SGP denominator mode must be either 'classic' or 'robust'." };
  }
  const sgpWinsorLowPct = Number(settings.sgp_winsor_low_pct);
  if (!Number.isFinite(sgpWinsorLowPct) || sgpWinsorLowPct < 0 || sgpWinsorLowPct > 1) {
    return { error: "SGP winsor low percentile must be a number between 0 and 1." };
  }
  const sgpWinsorHighPct = Number(settings.sgp_winsor_high_pct);
  if (!Number.isFinite(sgpWinsorHighPct) || sgpWinsorHighPct < 0 || sgpWinsorHighPct > 1) {
    return { error: "SGP winsor high percentile must be a number between 0 and 1." };
  }
  if (sgpWinsorLowPct >= sgpWinsorHighPct) {
    return { error: "SGP winsor low percentile must be less than the high percentile." };
  }
  const sgpEpsilonCounting = Number(settings.sgp_epsilon_counting);
  if (!Number.isFinite(sgpEpsilonCounting) || sgpEpsilonCounting < 0) {
    return { error: "SGP counting epsilon must be a non-negative number." };
  }
  const sgpEpsilonRatio = Number(settings.sgp_epsilon_ratio);
  if (!Number.isFinite(sgpEpsilonRatio) || sgpEpsilonRatio < 0) {
    return { error: "SGP ratio epsilon must be a non-negative number." };
  }
  const enablePlayingTimeReliability = coerceBooleanSetting(settings.enable_playing_time_reliability, false);
  const enableAgeRiskAdjustment = coerceBooleanSetting(settings.enable_age_risk_adjustment, false);
  const enableReplacementBlend = coerceBooleanSetting(settings.enable_replacement_blend, true);
  const replacementBlendAlpha = Number(settings.replacement_blend_alpha ?? 0.4);
  if (!Number.isFinite(replacementBlendAlpha) || replacementBlendAlpha < 0 || replacementBlendAlpha > 1) {
    return { error: "Replacement blend alpha must be a number between 0 and 1." };
  }

  const parsedRotoCategories: Record<string, boolean> = {};
  for (const field of ROTO_CATEGORY_FIELDS) {
    parsedRotoCategories[field.key] = coerceBooleanSetting(settings[field.key], field.defaultValue);
  }
  if (scoringMode === "roto") {
    const selectedHitCategories = ROTO_HITTER_CATEGORY_FIELDS.filter(field => parsedRotoCategories[field.key]).length;
    const selectedPitchCategories = ROTO_PITCHER_CATEGORY_FIELDS.filter(field => parsedRotoCategories[field.key]).length;
    if (selectedHitCategories <= 0) {
      return { error: "Roto scoring must include at least one hitting category." };
    }
    if (selectedPitchCategories <= 0) {
      return { error: "Roto scoring must include at least one pitching category." };
    }
  }

  let auctionBudget: number | null = null;
  const auctionBudgetText = String(settings.auction_budget ?? "").trim();
  if (auctionBudgetText && auctionBudgetText !== "0") {
    const parsedAuctionBudget = Number(auctionBudgetText);
    if (!Number.isFinite(parsedAuctionBudget) || parsedAuctionBudget < 1 || parsedAuctionBudget > 9999) {
      return { error: "Auction budget must be a number between 1 and 9999." };
    }
    auctionBudget = Math.round(parsedAuctionBudget);
  }

  const parsedPointsScoring: Record<string, number> = {};
  for (const field of POINTS_SCORING_FIELDS) {
    const value = Number(settings[field.key]);
    if (!Number.isFinite(value) || value < -50 || value > 50) {
      return { error: `${field.label} points must be a number between -50 and 50.` };
    }
    parsedPointsScoring[field.key] = value;
  }
  if (scoringMode === "points") {
    const hasNonZeroRule = Object.values(parsedPointsScoring).some(value => Math.abs(value) > 1e-9);
    if (!hasNonZeroRule) {
      return { error: "Points scoring must include at least one non-zero scoring rule." };
    }
  }

  const payload: Record<string, unknown> = {
    mode,
    teams,
    sims,
    horizon,
    discount,
    ...parsedSlots,
    bench,
    minors,
    ir,
    keeper_limit: keeperLimitResult.value,
    scoring_mode: scoringMode,
    points_valuation_mode: pointsValuationMode,
    ip_min: ipMin,
    ip_max: ipMax,
    weekly_starts_cap: weeklyStartsCapResult.value,
    allow_same_day_starts_overflow: coerceBooleanSetting(settings.allow_same_day_starts_overflow, false),
    weekly_acquisition_cap: weeklyAcquisitionCapResult.value,
    two_way: twoWay,
    sgp_denominator_mode: sgpDenominatorMode,
    sgp_winsor_low_pct: sgpWinsorLowPct,
    sgp_winsor_high_pct: sgpWinsorHighPct,
    sgp_epsilon_counting: sgpEpsilonCounting,
    sgp_epsilon_ratio: sgpEpsilonRatio,
    enable_playing_time_reliability: enablePlayingTimeReliability,
    enable_age_risk_adjustment: enableAgeRiskAdjustment,
    enable_replacement_blend: enableReplacementBlend,
    replacement_blend_alpha: replacementBlendAlpha,
    start_year: startYear,
    auction_budget: auctionBudget,
    ...parsedRotoCategories,
    ...parsedPointsScoring,
  };

  const guardrails = meta?.calculator_guardrails || {};
  const playableByYear = guardrails?.playable_by_year;
  if (playableByYear && typeof playableByYear === "object") {
    const pool = playableByYear[String(startYear)];
    if (pool && typeof pool === "object") {
      const availableHitters = Number(pool.hitters);
      const availablePitchers = Number(pool.pitchers);
      const requiredHitters = teams * hittersPerTeam;
      const requiredPitchers = teams * pitchersPerTeam;
      const warnings: string[] = [];

      if (Number.isFinite(availableHitters) && requiredHitters > availableHitters) {
        warnings.push(
          `Roster likely unfillable for ${startYear}: requires ${requiredHitters} hitters but only ${availableHitters} have projected AB > 0.`
        );
      }
      if (Number.isFinite(availablePitchers) && requiredPitchers > availablePitchers) {
        warnings.push(
          `Roster likely unfillable for ${startYear}: requires ${requiredPitchers} pitchers but only ${availablePitchers} have projected IP > 0.`
        );
      }
      if (warnings.length > 0) {
        return { payload, warning: warnings.join(" ") };
      }
    }
  }

  return { payload };
}
