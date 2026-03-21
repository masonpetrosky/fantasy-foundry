import { describe, expect, it } from "vitest";
import { buildQuickStartSettings } from "./dynasty_calculator";

const baseSettings = {
  scoring_mode: "roto",
  mode: "common",
  points_valuation_mode: "season_total",
  teams: 20,
  sims: 500,
  horizon: 10,
  discount: 0.9,
  bench: 10,
  minors: 7,
  ir: 4,
  keeper_limit: null as number | null,
  ip_min: 300,
  ip_max: 1400 as string | number,
  weekly_starts_cap: null as number | null,
  allow_same_day_starts_overflow: false,
  weekly_acquisition_cap: null as number | null,
  two_way: "max",
  start_year: 2027,
  hit_dh: 0,
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
  auction_budget: null,
};

describe("buildQuickStartSettings", () => {
  it("builds points quick start with points defaults and normalized common settings", () => {
    const settings = buildQuickStartSettings({
      mode: "points",
      settings: baseSettings,
      availableYears: [2026, 2027],
      meta: {
        years: [2026, 2027],
        calculator_guardrails: {
          default_ir_slots: 2,
          default_minors_slots: 3,
        },
      },
      rotoSlotDefaults: { hit_of: 5, hit_dh: 0, pit_p: 8 },
      rotoCategoryDefaults: { roto_hit_hr: true },
      pointsSlotDefaults: { hit_of: 3, hit_dh: 0, pit_p: 2, pit_sp: 5, pit_rp: 2 },
      pointsScoringDefaults: { pts_hit_hr: 4, pts_pit_w: 5 },
    });

    expect(settings.scoring_mode).toBe("points");
    expect(settings.teams).toBe(12);
    expect(settings.horizon).toBe(20);
    expect(settings.discount).toBe(0.94);
    expect(settings.bench).toBe(6);
    expect(settings.minors).toBe(3);
    expect(settings.ir).toBe(2);
    expect(settings.ip_min).toBe(0);
    expect(settings.ip_max).toBe("");
    expect(settings.two_way).toBe("sum");
    expect(settings.sgp_denominator_mode).toBe("classic");
    expect(settings.sgp_winsor_low_pct).toBe(0.1);
    expect(settings.sgp_winsor_high_pct).toBe(0.9);
    expect(settings.enable_playing_time_reliability).toBe(false);
    expect(settings.enable_age_risk_adjustment).toBe(false);
    expect(settings.enable_prospect_risk_adjustment).toBe(false);
    expect(settings.enable_bench_stash_relief).toBe(false);
    expect(settings.bench_negative_penalty).toBe(0.55);
    expect(settings.enable_ir_stash_relief).toBe(false);
    expect(settings.ir_negative_penalty).toBe(0.2);
    expect(settings.enable_replacement_blend).toBe(false);
    expect(settings.replacement_blend_alpha).toBe(0.7);
    expect(settings.sims).toBe(300);
    expect(settings.start_year).toBe(2027);
    expect(settings["hit_of"]).toBe(3);
    expect(settings["hit_dh"]).toBe(0);
    expect(settings["pit_sp"]).toBe(5);
    expect(settings["pts_hit_hr"]).toBe(4);
  });

  it("falls back to first available year for roto quick start when current year is invalid", () => {
    const settings = buildQuickStartSettings({
      mode: "roto",
      settings: {
        ...baseSettings,
        start_year: 2035,
      },
      availableYears: [2026, 2027],
      meta: {
        years: [2026, 2027],
      },
      rotoSlotDefaults: { hit_of: 5, hit_dh: 0, pit_p: 9 },
      rotoCategoryDefaults: { roto_hit_hr: true, roto_pit_k: true },
      pointsSlotDefaults: { hit_of: 3, hit_dh: 0, pit_p: 2 },
      pointsScoringDefaults: { pts_hit_hr: 4 },
    });

    expect(settings.scoring_mode).toBe("roto");
    expect(settings.start_year).toBe(2026);
    expect(settings["hit_of"]).toBe(5);
    expect(settings["hit_dh"]).toBe(0);
    expect(settings["pit_p"]).toBe(9);
    expect(settings["roto_hit_hr"]).toBe(true);
    expect(settings["roto_pit_k"]).toBe(true);
  });

  it("builds deep dynasty quick start with exact league settings and realism flags", () => {
    const settings = buildQuickStartSettings({
      mode: "deep",
      settings: baseSettings,
      availableYears: [2026, 2027],
      meta: {
        years: [2026, 2027],
      },
      rotoSlotDefaults: { hit_of: 5, hit_dh: 0, pit_p: 9 },
      rotoCategoryDefaults: { roto_hit_hr: true, roto_pit_k: true },
      pointsSlotDefaults: { hit_of: 3, hit_dh: 0, pit_p: 2 },
      pointsScoringDefaults: { pts_hit_hr: 4 },
    });

    expect(settings.scoring_mode).toBe("roto");
    expect(settings.teams).toBe(12);
    expect(settings["hit_c"]).toBe(2);
    expect(settings["hit_dh"]).toBe(0);
    expect(settings["hit_ut"]).toBe(2);
    expect(settings["pit_p"]).toBe(3);
    expect(settings.bench).toBe(14);
    expect(settings.minors).toBe(20);
    expect(settings.ir).toBe(8);
    expect(settings.ip_min).toBe(1000);
    expect(settings.ip_max).toBe(1500);
    expect(settings.roto_hit_ops).toBe(true);
    expect(settings.roto_pit_qa3).toBe(true);
    expect(settings.roto_pit_svh).toBe(true);
    expect(settings.enable_prospect_risk_adjustment).toBe(true);
    expect(settings.enable_bench_stash_relief).toBe(true);
    expect(settings.enable_ir_stash_relief).toBe(true);
  });
});
