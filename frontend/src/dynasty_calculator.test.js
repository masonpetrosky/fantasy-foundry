import { describe, expect, it } from "vitest";
import { buildQuickStartSettings } from "./dynasty_calculator.jsx";

const baseSettings = {
  scoring_mode: "roto",
  teams: 20,
  sims: 500,
  horizon: 10,
  discount: 0.9,
  bench: 10,
  minors: 7,
  ir: 4,
  ip_min: 300,
  ip_max: 1400,
  two_way: "max",
  start_year: 2027,
  recent_projections: 5,
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
      rotoSlotDefaults: { hit_of: 5, pit_p: 8 },
      rotoCategoryDefaults: { roto_hit_hr: true },
      pointsSlotDefaults: { hit_of: 3, pit_p: 2, pit_sp: 5, pit_rp: 2 },
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
    expect(settings.recent_projections).toBe(3);
    expect(settings.sims).toBe(300);
    expect(settings.start_year).toBe(2027);
    expect(settings.hit_of).toBe(3);
    expect(settings.pit_sp).toBe(5);
    expect(settings.pts_hit_hr).toBe(4);
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
      rotoSlotDefaults: { hit_of: 5, pit_p: 9 },
      rotoCategoryDefaults: { roto_hit_hr: true, roto_pit_k: true },
      pointsSlotDefaults: { hit_of: 3, pit_p: 2 },
      pointsScoringDefaults: { pts_hit_hr: 4 },
    });

    expect(settings.scoring_mode).toBe("roto");
    expect(settings.start_year).toBe(2026);
    expect(settings.hit_of).toBe(5);
    expect(settings.pit_p).toBe(9);
    expect(settings.roto_hit_hr).toBe(true);
    expect(settings.roto_pit_k).toBe(true);
  });
});
