export interface SlotField {
  key: string;
  label: string;
  defaultValue: number;
}

export interface PointsScoringField {
  key: string;
  label: string;
  group: "bat" | "pit";
  defaultValue: number;
}

export interface RotoCategoryField {
  key: string;
  label: string;
  statCol: string;
  defaultValue: boolean;
}

export interface PointsResultSummaryField {
  key: string;
  label: string;
  type: "number" | "slot";
}

export interface CalculatorSettings {
  [key: string]: unknown;
  mode: string;
  scoring_mode: string;
  teams: number;
  sims: number;
  horizon: number;
  discount: number;
  bench: number;
  minors: number;
  ir: number;
  ip_min: number;
  ip_max: string | number | null;
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

interface CalculatorGuardrails {
  default_hitter_slots?: Record<string, number>;
  default_pitcher_slots?: Record<string, number>;
  default_points_hitter_slots?: Record<string, number>;
  default_points_pitcher_slots?: Record<string, number>;
  default_points_scoring?: Record<string, number>;
  default_ir_slots?: number;
  default_minors_slots?: number;
  playable_by_year?: Record<string, { hitters?: number; pitchers?: number }>;
}

interface CalculatorMeta {
  calculator_guardrails?: CalculatorGuardrails;
  years?: number[];
}

// Shared dynasty calculator constants and payload/default builders.
export const CALC_SEARCH_DEBOUNCE_MS = 140;
export const SLOT_INPUT_MIN = 0;
export const SLOT_INPUT_MAX = 15;
export const HITTER_SLOT_FIELDS: SlotField[] = [
  { key: "hit_c", label: "C", defaultValue: 1 },
  { key: "hit_1b", label: "1B", defaultValue: 1 },
  { key: "hit_2b", label: "2B", defaultValue: 1 },
  { key: "hit_3b", label: "3B", defaultValue: 1 },
  { key: "hit_ss", label: "SS", defaultValue: 1 },
  { key: "hit_ci", label: "CI", defaultValue: 1 },
  { key: "hit_mi", label: "MI", defaultValue: 1 },
  { key: "hit_of", label: "OF", defaultValue: 5 },
  { key: "hit_ut", label: "UT", defaultValue: 1 },
];
export const PITCHER_SLOT_FIELDS: SlotField[] = [
  { key: "pit_p", label: "P", defaultValue: 9 },
  { key: "pit_sp", label: "SP", defaultValue: 0 },
  { key: "pit_rp", label: "RP", defaultValue: 0 },
];
const POINTS_SETUP_SLOT_DEFAULTS: Record<string, number> = {
  hit_c: 1,
  hit_1b: 1,
  hit_2b: 1,
  hit_3b: 1,
  hit_ss: 1,
  hit_ci: 0,
  hit_mi: 0,
  hit_of: 3,
  hit_ut: 1,
  pit_p: 2,
  pit_sp: 5,
  pit_rp: 2,
};
export const POINTS_SCORING_FIELDS: PointsScoringField[] = [
  { key: "pts_hit_1b", label: "1B", group: "bat", defaultValue: 1 },
  { key: "pts_hit_2b", label: "2B", group: "bat", defaultValue: 2 },
  { key: "pts_hit_3b", label: "3B", group: "bat", defaultValue: 3 },
  { key: "pts_hit_hr", label: "HR", group: "bat", defaultValue: 4 },
  { key: "pts_hit_r", label: "R", group: "bat", defaultValue: 1 },
  { key: "pts_hit_rbi", label: "RBI", group: "bat", defaultValue: 1 },
  { key: "pts_hit_sb", label: "SB", group: "bat", defaultValue: 1 },
  { key: "pts_hit_bb", label: "BB", group: "bat", defaultValue: 1 },
  { key: "pts_hit_so", label: "SO", group: "bat", defaultValue: -1 },
  { key: "pts_pit_ip", label: "IP", group: "pit", defaultValue: 3 },
  { key: "pts_pit_w", label: "W", group: "pit", defaultValue: 5 },
  { key: "pts_pit_l", label: "L", group: "pit", defaultValue: -5 },
  { key: "pts_pit_k", label: "K", group: "pit", defaultValue: 1 },
  { key: "pts_pit_sv", label: "SV", group: "pit", defaultValue: 5 },
  { key: "pts_pit_svh", label: "SVH", group: "pit", defaultValue: 0 },
  { key: "pts_pit_h", label: "H Allowed", group: "pit", defaultValue: -1 },
  { key: "pts_pit_er", label: "ER", group: "pit", defaultValue: -2 },
  { key: "pts_pit_bb", label: "BB Allowed", group: "pit", defaultValue: -1 },
];
export const POINTS_BATTING_FIELDS: PointsScoringField[] = POINTS_SCORING_FIELDS.filter(field => field.group === "bat");
export const POINTS_PITCHING_FIELDS: PointsScoringField[] = POINTS_SCORING_FIELDS.filter(field => field.group === "pit");
export const POINTS_RESULT_SUMMARY_FIELDS: PointsResultSummaryField[] = [
  { key: "HittingPoints", label: "Hitting Points", type: "number" },
  { key: "PitchingPoints", label: "Pitching Points", type: "number" },
  { key: "SelectedPoints", label: "Selected Points", type: "number" },
  { key: "HittingBestSlot", label: "Hitting Best Slot", type: "slot" },
  { key: "PitchingBestSlot", label: "Pitching Best Slot", type: "slot" },
  { key: "HittingValue", label: "Hitting Value", type: "number" },
  { key: "PitchingValue", label: "Pitching Value", type: "number" },
  { key: "HittingAssignmentSlot", label: "Hitting Assignment Slot", type: "slot" },
  { key: "PitchingAssignmentSlot", label: "Pitching Assignment Slot", type: "slot" },
  { key: "HittingAssignmentValue", label: "Hitting Assignment Value", type: "number" },
  { key: "PitchingAssignmentValue", label: "Pitching Assignment Value", type: "number" },
  { key: "KeepDropValue", label: "Keep/Drop Value", type: "number" },
];
export const POINTS_RESULT_SUMMARY_COLS: string[] = POINTS_RESULT_SUMMARY_FIELDS.map(field => field.key);
export const POINTS_RESULT_NUMERIC_COLS: Set<string> = new Set(
  POINTS_RESULT_SUMMARY_FIELDS.filter(field => field.type === "number").map(field => field.key)
);
export const POINTS_RESULT_SLOT_COLS: Set<string> = new Set(
  POINTS_RESULT_SUMMARY_FIELDS.filter(field => field.type === "slot").map(field => field.key)
);
export const POINTS_RESULT_COLUMN_LABELS: Record<string, string> = Object.fromEntries(
  POINTS_RESULT_SUMMARY_FIELDS.map(field => [field.key, field.label])
);
export const ROTO_HITTER_CATEGORY_FIELDS: RotoCategoryField[] = [
  { key: "roto_hit_r", label: "R", statCol: "R", defaultValue: true },
  { key: "roto_hit_rbi", label: "RBI", statCol: "RBI", defaultValue: true },
  { key: "roto_hit_hr", label: "HR", statCol: "HR", defaultValue: true },
  { key: "roto_hit_sb", label: "SB", statCol: "SB", defaultValue: true },
  { key: "roto_hit_avg", label: "AVG", statCol: "AVG", defaultValue: true },
  { key: "roto_hit_obp", label: "OBP", statCol: "OBP", defaultValue: false },
  { key: "roto_hit_slg", label: "SLG", statCol: "SLG", defaultValue: false },
  { key: "roto_hit_ops", label: "OPS", statCol: "OPS", defaultValue: false },
  { key: "roto_hit_h", label: "H", statCol: "H", defaultValue: false },
  { key: "roto_hit_bb", label: "BB", statCol: "BB", defaultValue: false },
  { key: "roto_hit_2b", label: "2B", statCol: "2B", defaultValue: false },
  { key: "roto_hit_tb", label: "TB", statCol: "TB", defaultValue: false },
];
export const ROTO_PITCHER_CATEGORY_FIELDS: RotoCategoryField[] = [
  { key: "roto_pit_w", label: "W", statCol: "W", defaultValue: true },
  { key: "roto_pit_k", label: "K", statCol: "K", defaultValue: true },
  { key: "roto_pit_sv", label: "SV", statCol: "SV", defaultValue: true },
  { key: "roto_pit_era", label: "ERA", statCol: "ERA", defaultValue: true },
  { key: "roto_pit_whip", label: "WHIP", statCol: "WHIP", defaultValue: true },
  { key: "roto_pit_qs", label: "QS", statCol: "QS", defaultValue: false },
  { key: "roto_pit_qa3", label: "QA3", statCol: "QA3", defaultValue: false },
  { key: "roto_pit_svh", label: "SVH", statCol: "SVH", defaultValue: false },
];
const ROTO_CATEGORY_FIELDS: RotoCategoryField[] = [...ROTO_HITTER_CATEGORY_FIELDS, ...ROTO_PITCHER_CATEGORY_FIELDS];
export const ROTO_RATE_STAT_COLS: Set<string> = new Set(["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"]);
export const ROTO_THREE_DECIMAL_RATE_COLS: Set<string> = new Set(["AVG", "OBP", "SLG", "OPS"]);
export const ROTO_COUNTING_STAT_COLS: Set<string> = new Set(["R", "RBI", "HR", "SB", "H", "BB", "2B", "TB", "W", "K", "SV", "QS", "QA3", "SVH"]);

export function coerceBooleanSetting(value: unknown, fallback: boolean = false): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "number" && Number.isFinite(value)) return value !== 0;
  const text = String(value ?? "").trim().toLowerCase();
  if (["1", "true", "yes", "y", "on"].includes(text)) return true;
  if (["0", "false", "no", "n", "off"].includes(text)) return false;
  return fallback;
}

export function resolveRotoCategoryDefaults(): Record<string, boolean> {
  return Object.fromEntries(
    ROTO_CATEGORY_FIELDS.map(field => [field.key, field.defaultValue])
  );
}

export function resolveRotoSelectedStatColumns(settings: Record<string, unknown> | null | undefined): string[] {
  const source = settings && typeof settings === "object" ? settings : {};
  return ROTO_CATEGORY_FIELDS
    .filter(field => coerceBooleanSetting(source[field.key], field.defaultValue))
    .map(field => field.statCol);
}

export function resolveRotoSlotDefaults(meta: CalculatorMeta | null | undefined): Record<string, number> {
  const guardrails = meta?.calculator_guardrails || {};
  const defaultHitSlots = guardrails?.default_hitter_slots || {};
  const defaultPitchSlots = guardrails?.default_pitcher_slots || {};
  const resolvedHitSlots = Object.fromEntries(
    HITTER_SLOT_FIELDS.map(slot => {
      const value = Number(defaultHitSlots[slot.label]);
      return [slot.key, Number.isInteger(value) && value >= SLOT_INPUT_MIN ? value : slot.defaultValue];
    })
  );
  const resolvedPitchSlots = Object.fromEntries(
    PITCHER_SLOT_FIELDS.map(slot => {
      const value = Number(defaultPitchSlots[slot.label]);
      return [slot.key, Number.isInteger(value) && value >= SLOT_INPUT_MIN ? value : slot.defaultValue];
    })
  );
  return { ...resolvedHitSlots, ...resolvedPitchSlots };
}

export function resolvePointsSlotDefaults(meta: CalculatorMeta | null | undefined): Record<string, number> {
  const guardrails = meta?.calculator_guardrails || {};
  const pointsHitDefaults = guardrails?.default_points_hitter_slots || {};
  const pointsPitchDefaults = guardrails?.default_points_pitcher_slots || {};
  const fallback = POINTS_SETUP_SLOT_DEFAULTS;
  const resolvedHitSlots = Object.fromEntries(
    HITTER_SLOT_FIELDS.map(slot => {
      const guardrailValue = Number(pointsHitDefaults[slot.label]);
      const fallbackValue = Number(fallback[slot.key]);
      return [
        slot.key,
        Number.isInteger(guardrailValue) && guardrailValue >= SLOT_INPUT_MIN
          ? guardrailValue
          : Number.isInteger(fallbackValue) && fallbackValue >= SLOT_INPUT_MIN
            ? fallbackValue
            : slot.defaultValue,
      ];
    })
  );
  const resolvedPitchSlots = Object.fromEntries(
    PITCHER_SLOT_FIELDS.map(slot => {
      const guardrailValue = Number(pointsPitchDefaults[slot.label]);
      const fallbackValue = Number(fallback[slot.key]);
      return [
        slot.key,
        Number.isInteger(guardrailValue) && guardrailValue >= SLOT_INPUT_MIN
          ? guardrailValue
          : Number.isInteger(fallbackValue) && fallbackValue >= SLOT_INPUT_MIN
            ? fallbackValue
            : slot.defaultValue,
      ];
    })
  );
  return { ...resolvedHitSlots, ...resolvedPitchSlots };
}

export function resolvePointsScoringDefaults(meta: CalculatorMeta | null | undefined): Record<string, number> {
  const guardrails = meta?.calculator_guardrails || {};
  const provided = guardrails?.default_points_scoring || {};
  return Object.fromEntries(
    POINTS_SCORING_FIELDS.map(field => {
      const value = Number(provided[field.key]);
      return [field.key, Number.isFinite(value) ? value : field.defaultValue];
    })
  );
}

export function buildDefaultCalculatorSettings(meta: CalculatorMeta | null | undefined): CalculatorSettings {
  const guardrails = meta?.calculator_guardrails || {};
  const defaultIr = Number(guardrails?.default_ir_slots);
  const defaultMinors = Number(guardrails?.default_minors_slots);
  return {
    mode: "common",
    scoring_mode: "roto",
    teams: 12,
    sims: 300,
    horizon: 20,
    discount: 0.94,
    ...resolveRotoSlotDefaults(meta),
    bench: 6,
    minors: Number.isInteger(defaultMinors) && defaultMinors >= 0 ? defaultMinors : 0,
    ir: Number.isInteger(defaultIr) && defaultIr >= 0 ? defaultIr : 0,
    ip_min: 0,
    ip_max: "",
    two_way: "sum",
    sgp_denominator_mode: "classic",
    sgp_winsor_low_pct: 0.1,
    sgp_winsor_high_pct: 0.9,
    sgp_epsilon_counting: 0.15,
    sgp_epsilon_ratio: 0.0015,
    enable_playing_time_reliability: false,
    enable_age_risk_adjustment: false,
    enable_replacement_blend: false,
    replacement_blend_alpha: 0.7,
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

  const pitchersPerTeam = PITCHER_SLOT_FIELDS.reduce((sum, slot) => sum + parsedSlots[slot.key], 0);
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
  const enableReplacementBlend = coerceBooleanSetting(settings.enable_replacement_blend, false);
  const replacementBlendAlpha = Number(settings.replacement_blend_alpha);
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
    ...settings,
    mode,
    teams,
    sims,
    horizon,
    discount,
    ...parsedSlots,
    bench,
    minors,
    ir,
    scoring_mode: scoringMode,
    ip_min: ipMin,
    ip_max: ipMax,
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
