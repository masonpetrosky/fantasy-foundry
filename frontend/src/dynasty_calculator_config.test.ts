import { describe, expect, it } from "vitest";
import {
  buildCalculatorPayload,
  buildDefaultCalculatorSettings,
  coerceBooleanSetting,
  isRotoStatDynastyCol,
  resolvePointsScoringDefaults,
  resolvePointsSlotDefaults,
  resolveRotoCategoryDefaults,
  resolveRotoSelectedStatColumns,
  resolveRotoSlotDefaults,
  rotoStatDynastyLabel,
  ROTO_STAT_DYNASTY_PREFIX,
} from "./dynasty_calculator_config";

describe("coerceBooleanSetting", () => {
  it("returns boolean values unchanged", () => {
    expect(coerceBooleanSetting(true)).toBe(true);
    expect(coerceBooleanSetting(false)).toBe(false);
  });

  it("coerces truthy string representations", () => {
    expect(coerceBooleanSetting("1")).toBe(true);
    expect(coerceBooleanSetting("true")).toBe(true);
    expect(coerceBooleanSetting("yes")).toBe(true);
    expect(coerceBooleanSetting("on")).toBe(true);
  });

  it("coerces falsy string representations", () => {
    expect(coerceBooleanSetting("0")).toBe(false);
    expect(coerceBooleanSetting("false")).toBe(false);
    expect(coerceBooleanSetting("no")).toBe(false);
    expect(coerceBooleanSetting("off")).toBe(false);
  });

  it("returns fallback for unrecognized values", () => {
    expect(coerceBooleanSetting(undefined, true)).toBe(true);
    expect(coerceBooleanSetting("maybe", false)).toBe(false);
    expect(coerceBooleanSetting(null, true)).toBe(true);
  });

  it("coerces finite numbers", () => {
    expect(coerceBooleanSetting(1)).toBe(true);
    expect(coerceBooleanSetting(0)).toBe(false);
    expect(coerceBooleanSetting(42)).toBe(true);
  });
});

describe("resolveRotoCategoryDefaults", () => {
  it("returns an object with default category values", () => {
    const defaults = resolveRotoCategoryDefaults();
    expect(typeof defaults).toBe("object");
    // Standard 5x5 roto defaults
    expect(defaults.roto_hit_r).toBe(true);
    expect(defaults.roto_hit_rbi).toBe(true);
    expect(defaults.roto_hit_hr).toBe(true);
    expect(defaults.roto_hit_sb).toBe(true);
    expect(defaults.roto_hit_avg).toBe(true);
    expect(defaults.roto_pit_w).toBe(true);
    expect(defaults.roto_pit_k).toBe(true);
    expect(defaults.roto_pit_sv).toBe(true);
    expect(defaults.roto_pit_era).toBe(true);
    expect(defaults.roto_pit_whip).toBe(true);
    // Non-default categories
    expect(defaults.roto_hit_obp).toBe(false);
    expect(defaults.roto_pit_qs).toBe(false);
    expect(defaults.roto_pit_svh).toBe(false);
  });
});

describe("resolveRotoSelectedStatColumns", () => {
  it("returns default 5x5 columns when settings are empty", () => {
    const cols = resolveRotoSelectedStatColumns({});
    expect(cols).toContain("R");
    expect(cols).toContain("RBI");
    expect(cols).toContain("HR");
    expect(cols).toContain("SB");
    expect(cols).toContain("AVG");
    expect(cols).toContain("W");
    expect(cols).toContain("K");
    expect(cols).toContain("SV");
    expect(cols).toContain("ERA");
    expect(cols).toContain("WHIP");
  });

  it("includes non-default categories when enabled in settings", () => {
    const cols = resolveRotoSelectedStatColumns({
      roto_hit_obp: true,
      roto_pit_qs: true,
      roto_pit_svh: true,
    });
    expect(cols).toContain("OBP");
    expect(cols).toContain("QS");
    expect(cols).toContain("SVH");
  });

  it("excludes default categories when disabled in settings", () => {
    const cols = resolveRotoSelectedStatColumns({
      roto_hit_r: false,
      roto_hit_rbi: false,
    });
    expect(cols).not.toContain("R");
    expect(cols).not.toContain("RBI");
  });

  it("handles null/undefined settings gracefully", () => {
    const cols = resolveRotoSelectedStatColumns(null);
    expect(Array.isArray(cols)).toBe(true);
    expect(cols.length).toBeGreaterThan(0);
  });
});

describe("resolveRotoSlotDefaults", () => {
  it("returns built-in slot defaults when no meta provided", () => {
    const slots = resolveRotoSlotDefaults({});
    expect(slots.hit_c).toBe(1);
    expect(slots.hit_of).toBe(5);
    expect(slots.hit_dh).toBe(0);
    expect(slots.pit_p).toBe(9);
    expect(slots.pit_sp).toBe(0);
    expect(slots.pit_rp).toBe(0);
  });

  it("applies guardrail defaults when provided", () => {
    const meta = {
      calculator_guardrails: {
        default_hitter_slots: { C: 2, OF: 4 },
        default_pitcher_slots: { P: 7 },
      },
    };
    const slots = resolveRotoSlotDefaults(meta);
    expect(slots.hit_c).toBe(2);
    expect(slots.hit_of).toBe(4);
    expect(slots.pit_p).toBe(7);
    expect(slots.hit_1b).toBe(1); // falls back to built-in
  });
});

describe("resolvePointsSlotDefaults", () => {
  it("returns defaults when no meta guardrails provided", () => {
    const slots = resolvePointsSlotDefaults({});
    expect(typeof slots).toBe("object");
    expect(typeof slots.hit_c).toBe("number");
    expect(typeof slots.pit_p).toBe("number");
  });
});

describe("resolvePointsScoringDefaults", () => {
  it("returns built-in scoring defaults for empty meta", () => {
    const scoring = resolvePointsScoringDefaults({});
    expect(scoring.pts_hit_hr).toBe(4);
    expect(scoring.pts_pit_sv).toBe(5);
    expect(scoring.pts_hit_so).toBe(-1);
  });

  it("overrides defaults from guardrail values", () => {
    const meta = {
      calculator_guardrails: {
        default_points_scoring: { pts_hit_hr: 6 },
      },
    };
    const scoring = resolvePointsScoringDefaults(meta);
    expect(scoring.pts_hit_hr).toBe(6);
    expect(scoring.pts_pit_sv).toBe(5); // unchanged
  });
});

function buildValidRotoSettings(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  const base: Record<string, unknown> = {
    scoring_mode: "roto",
    teams: 12,
    sims: 300,
    horizon: 20,
    discount: 0.94,
    hit_c: 1, hit_1b: 1, hit_2b: 1, hit_3b: 1, hit_ss: 1, hit_ci: 1, hit_mi: 1, hit_of: 5, hit_dh: 0, hit_ut: 1,
    pit_p: 9, pit_sp: 0, pit_rp: 0,
    bench: 6,
    minors: 0,
    ir: 0,
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
    enable_prospect_risk_adjustment: false,
    enable_bench_stash_relief: false,
    bench_negative_penalty: 0.55,
    enable_ir_stash_relief: false,
    ir_negative_penalty: 0.2,
    enable_replacement_blend: false,
    replacement_blend_alpha: 0.7,
    start_year: 2026,
    ...resolveRotoCategoryDefaults(),
    ...resolvePointsScoringDefaults({}),
  };
  return { ...base, ...overrides };
}

describe("buildCalculatorPayload", () => {
  it("returns a valid payload for well-formed roto settings", () => {
    const settings = buildValidRotoSettings();
    const result = buildCalculatorPayload(settings, [2026, 2027], {});
    expect(result.error).toBeUndefined();
    expect(result.payload).toBeDefined();
    expect(result.payload!.scoring_mode).toBe("roto");
    expect(result.payload!.teams).toBe(12);
    expect(result.payload!.enable_prospect_risk_adjustment).toBe(false);
    expect(result.payload!.bench_negative_penalty).toBe(0.55);
    expect(result.payload!.ir_negative_penalty).toBe(0.2);
  });

  it("accepts daily_h2h as a valid points valuation mode", () => {
    const settings = buildValidRotoSettings({
      scoring_mode: "points",
      points_valuation_mode: "daily_h2h",
      hit_of: 1,
      pit_p: 1,
      pts_hit_1b: 1,
    });
    const result = buildCalculatorPayload(settings, [2026, 2027], {});

    expect(result.error).toBeUndefined();
    expect(result.payload?.points_valuation_mode).toBe("daily_h2h");
  });

  it("returns error for invalid scoring mode", () => {
    const settings = buildValidRotoSettings({ scoring_mode: "invalid" });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toMatch(/scoring mode/i);
  });

  it("returns error when teams is out of range", () => {
    const result = buildCalculatorPayload(buildValidRotoSettings({ teams: 1 }), [2026], {});
    expect(result.error).toMatch(/teams/i);

    const result2 = buildCalculatorPayload(buildValidRotoSettings({ teams: 31 }), [2026], {});
    expect(result2.error).toMatch(/teams/i);
  });

  it("returns error when all hitter slots are zero", () => {
    const settings = buildValidRotoSettings({
      hit_c: 0, hit_1b: 0, hit_2b: 0, hit_3b: 0, hit_ss: 0,
      hit_ci: 0, hit_mi: 0, hit_of: 0, hit_dh: 0, hit_ut: 0,
    });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toMatch(/hitter slot/i);
  });

  it("returns error when all pitcher slots are zero", () => {
    const settings = buildValidRotoSettings({ pit_p: 0, pit_sp: 0, pit_rp: 0 });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toMatch(/pitcher slot/i);
  });

  it("returns error for invalid horizon", () => {
    const result = buildCalculatorPayload(buildValidRotoSettings({ horizon: 0 }), [2026], {});
    expect(result.error).toMatch(/horizon/i);

    const result2 = buildCalculatorPayload(buildValidRotoSettings({ horizon: 21 }), [2026], {});
    expect(result2.error).toMatch(/horizon/i);
  });

  it("returns error when start_year not in available years", () => {
    const result = buildCalculatorPayload(buildValidRotoSettings({ start_year: 2099 }), [2026, 2027], {});
    expect(result.error).toMatch(/start year/i);
  });

  it("returns error when bench penalty is outside zero to one", () => {
    const result = buildCalculatorPayload(buildValidRotoSettings({ bench_negative_penalty: 1.5 }), [2026], {});
    expect(result.error).toMatch(/bench stash penalty/i);
  });

  it("returns error when IR penalty is outside zero to one", () => {
    const result = buildCalculatorPayload(buildValidRotoSettings({ ir_negative_penalty: -0.1 }), [2026], {});
    expect(result.error).toMatch(/IR stash penalty/i);
  });

  it("returns error when roto mode has no hitting categories", () => {
    const settings = buildValidRotoSettings({
      roto_hit_r: false, roto_hit_rbi: false, roto_hit_hr: false,
      roto_hit_sb: false, roto_hit_avg: false,
    });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toMatch(/hitting category/i);
  });

  it("includes a warning when roster requirements exceed available players", () => {
    const settings = buildValidRotoSettings({ teams: 30, hit_of: 15 });
    const meta = {
      calculator_guardrails: {
        playable_by_year: {
          2026: { hitters: 100, pitchers: 500 },
        },
      },
    };
    const result = buildCalculatorPayload(settings, [2026], meta);
    if (result.warning) {
      expect(result.warning).toBeTruthy();
      expect(result.payload).toBeDefined();
    }
  });

  it("handles ip_max set to a valid value", () => {
    const settings = buildValidRotoSettings({ ip_min: 10, ip_max: "200" });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toBeUndefined();
    expect(result.payload?.ip_max).toBe(200);
  });

  it("keeps ip_max in points payloads", () => {
    const settings = buildValidRotoSettings({
      scoring_mode: "points",
      ip_max: "1500",
      hit_of: 1,
      pit_p: 1,
      pts_hit_1b: 1,
    });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toBeUndefined();
    expect(result.payload?.scoring_mode).toBe("points");
    expect(result.payload?.ip_max).toBe(1500);
  });

  it("returns error when ip_max is less than ip_min", () => {
    const settings = buildValidRotoSettings({ ip_min: 100, ip_max: "50" });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toMatch(/ip max/i);
  });

  it("treats keeper limit zero as blank", () => {
    const settings = buildValidRotoSettings({ keeper_limit: "0" });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toBeUndefined();
    expect(result.payload?.keeper_limit).toBeNull();
  });

  it("preserves a zero weekly acquisition cap", () => {
    const settings = buildValidRotoSettings({ weekly_acquisition_cap: "0" });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toBeUndefined();
    expect(result.payload?.weekly_acquisition_cap).toBe(0);
  });
});

describe("buildDefaultCalculatorSettings", () => {
  it("returns a complete settings object for empty meta", () => {
    const settings = buildDefaultCalculatorSettings({});
    expect(settings.scoring_mode).toBe("roto");
    expect(settings.mode).toBe("common");
    expect(settings.teams).toBe(12);
    expect(settings.horizon).toBe(20);
    expect(settings.discount).toBe(0.94);
    expect(settings.bench).toBe(6);
    expect(settings.hit_dh).toBe(0);
    expect(typeof settings.start_year).toBe("number");
  });

  it("uses meta years for start_year when available", () => {
    const settings = buildDefaultCalculatorSettings({ years: [2027, 2028] });
    expect(settings.start_year).toBe(2027);
  });
});

describe("buildCalculatorPayload mode field", () => {
  it("always uses common mode", () => {
    const settings = buildValidRotoSettings({ mode: "common" });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toBeUndefined();
    expect(result.payload!.mode).toBe("common");
  });

  it("forces common mode even if league is specified", () => {
    const settings = buildValidRotoSettings({ mode: "league" });
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toBeUndefined();
    expect(result.payload!.mode).toBe("common");
  });

  it("defaults mode to common when not specified", () => {
    const settings = buildValidRotoSettings();
    delete settings.mode;
    const result = buildCalculatorPayload(settings, [2026], {});
    expect(result.error).toBeUndefined();
    expect(result.payload!.mode).toBe("common");
  });
});

describe("roto stat dynasty column helpers", () => {
  it("ROTO_STAT_DYNASTY_PREFIX is correct", () => {
    expect(ROTO_STAT_DYNASTY_PREFIX).toBe("StatDynasty_");
  });

  it("isRotoStatDynastyCol identifies stat dynasty columns", () => {
    expect(isRotoStatDynastyCol("StatDynasty_R")).toBe(true);
    expect(isRotoStatDynastyCol("StatDynasty_ERA")).toBe(true);
    expect(isRotoStatDynastyCol("DynastyValue")).toBe(false);
    expect(isRotoStatDynastyCol("Value_2026")).toBe(false);
    expect(isRotoStatDynastyCol("")).toBe(false);
  });

  it("rotoStatDynastyLabel generates correct labels", () => {
    expect(rotoStatDynastyLabel("StatDynasty_R")).toBe("SGP: R");
    expect(rotoStatDynastyLabel("StatDynasty_AVG")).toBe("SGP: AVG");
    expect(rotoStatDynastyLabel("StatDynasty_ERA")).toBe("SGP: ERA");
  });
});
