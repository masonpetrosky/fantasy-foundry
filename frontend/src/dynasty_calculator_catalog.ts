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
  type: "number" | "slot" | "boolean";
}

export interface CalculatorGuardrails {
  default_hitter_slots?: Record<string, number>;
  default_pitcher_slots?: Record<string, number>;
  default_points_hitter_slots?: Record<string, number>;
  default_points_pitcher_slots?: Record<string, number>;
  default_points_scoring?: Record<string, number>;
  default_ir_slots?: number;
  default_minors_slots?: number;
  playable_by_year?: Record<string, { hitters?: number; pitchers?: number }>;
}

export interface CalculatorMeta {
  calculator_guardrails?: CalculatorGuardrails;
  years?: number[];
}

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
  { key: "hit_dh", label: "DH", defaultValue: 0 },
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
  hit_dh: 0,
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
  { key: "pts_hit_hbp", label: "HBP", group: "bat", defaultValue: 0 },
  { key: "pts_hit_so", label: "SO", group: "bat", defaultValue: -1 },
  { key: "pts_pit_ip", label: "IP", group: "pit", defaultValue: 3 },
  { key: "pts_pit_w", label: "W", group: "pit", defaultValue: 5 },
  { key: "pts_pit_l", label: "L", group: "pit", defaultValue: -5 },
  { key: "pts_pit_k", label: "K", group: "pit", defaultValue: 1 },
  { key: "pts_pit_sv", label: "SV", group: "pit", defaultValue: 5 },
  { key: "pts_pit_hld", label: "Holds", group: "pit", defaultValue: 0 },
  { key: "pts_pit_h", label: "H Allowed", group: "pit", defaultValue: -1 },
  { key: "pts_pit_er", label: "ER", group: "pit", defaultValue: -2 },
  { key: "pts_pit_bb", label: "BB Allowed", group: "pit", defaultValue: -1 },
  { key: "pts_pit_hbp", label: "HB Allowed", group: "pit", defaultValue: 0 },
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
  { key: "KeepDropHoldValue", label: "Keep/Drop Hold Value", type: "number" },
  { key: "KeepDropKeep", label: "Keep/Drop Keep", type: "boolean" },
];

export const POINTS_RESULT_SUMMARY_COLS: string[] = POINTS_RESULT_SUMMARY_FIELDS.map(field => field.key);
export const POINTS_RESULT_NUMERIC_COLS: Set<string> = new Set(
  POINTS_RESULT_SUMMARY_FIELDS.filter(field => field.type === "number").map(field => field.key)
);
export const POINTS_RESULT_SLOT_COLS: Set<string> = new Set(
  POINTS_RESULT_SUMMARY_FIELDS.filter(field => field.type === "slot").map(field => field.key)
);
export const POINTS_RESULT_BOOLEAN_COLS: Set<string> = new Set(
  POINTS_RESULT_SUMMARY_FIELDS.filter(field => field.type === "boolean").map(field => field.key)
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

export const ROTO_CATEGORY_FIELDS: RotoCategoryField[] = [...ROTO_HITTER_CATEGORY_FIELDS, ...ROTO_PITCHER_CATEGORY_FIELDS];

export const ROTO_RATE_STAT_COLS: Set<string> = new Set(["AVG", "OBP", "SLG", "OPS", "ERA", "WHIP"]);
export const ROTO_THREE_DECIMAL_RATE_COLS: Set<string> = new Set(["AVG", "OBP", "SLG", "OPS"]);
export const ROTO_COUNTING_STAT_COLS: Set<string> = new Set(["R", "RBI", "HR", "SB", "H", "BB", "2B", "TB", "W", "K", "SV", "QS", "QA3", "SVH"]);

export const ROTO_STAT_DYNASTY_PREFIX = "StatDynasty_";

export function isRotoStatDynastyCol(col: string): boolean {
  return col.startsWith(ROTO_STAT_DYNASTY_PREFIX);
}

export function rotoStatDynastyLabel(col: string): string {
  return `SGP: ${col.slice(ROTO_STAT_DYNASTY_PREFIX.length)}`;
}

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
  const defaultHitSlots = guardrails.default_hitter_slots || {};
  const defaultPitchSlots = guardrails.default_pitcher_slots || {};
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
  const pointsHitDefaults = guardrails.default_points_hitter_slots || {};
  const pointsPitchDefaults = guardrails.default_points_pitcher_slots || {};
  const resolvedHitSlots = Object.fromEntries(
    HITTER_SLOT_FIELDS.map(slot => {
      const guardrailValue = Number(pointsHitDefaults[slot.label]);
      const fallbackValue = Number(POINTS_SETUP_SLOT_DEFAULTS[slot.key]);
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
      const fallbackValue = Number(POINTS_SETUP_SLOT_DEFAULTS[slot.key]);
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
  const provided = guardrails.default_points_scoring || {};
  return Object.fromEntries(
    POINTS_SCORING_FIELDS.map(field => {
      const value = Number(provided[field.key]);
      return [field.key, Number.isFinite(value) ? value : field.defaultValue];
    })
  );
}
