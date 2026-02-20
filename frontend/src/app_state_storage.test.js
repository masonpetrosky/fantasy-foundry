import { describe, expect, it } from "vitest";
import {
  calculatorPresetsEqual,
  mergeCalculatorPresetsPreferLocal,
} from "./app_state_storage.js";

describe("mergeCalculatorPresetsPreferLocal", () => {
  it("combines cloud and local presets by name", () => {
    const merged = mergeCalculatorPresetsPreferLocal(
      {
        "Local Keeper": { teams: 16, scoring_mode: "roto" },
      },
      {
        "Cloud Points": { teams: 12, scoring_mode: "points" },
      }
    );

    expect(Object.keys(merged).sort((a, b) => a.localeCompare(b))).toEqual([
      "Cloud Points",
      "Local Keeper",
    ]);
  });

  it("prefers local values when preset names collide", () => {
    const merged = mergeCalculatorPresetsPreferLocal(
      {
        "My League": { teams: 15, discount: 0.9 },
      },
      {
        "My League": { teams: 10, discount: 0.95 },
      }
    );

    expect(merged["My League"]).toEqual({ teams: 15, discount: 0.9 });
  });
});

describe("calculatorPresetsEqual", () => {
  it("returns true for equivalent preset objects", () => {
    expect(calculatorPresetsEqual(
      {
        Alpha: { teams: 12, scoring_mode: "roto" },
      },
      {
        Alpha: { teams: 12, scoring_mode: "roto" },
      }
    )).toBe(true);
  });

  it("returns false when names or values differ", () => {
    expect(calculatorPresetsEqual(
      {
        Alpha: { teams: 12, scoring_mode: "roto" },
      },
      {
        Beta: { teams: 12, scoring_mode: "roto" },
      }
    )).toBe(false);

    expect(calculatorPresetsEqual(
      {
        Alpha: { teams: 12, scoring_mode: "roto" },
      },
      {
        Alpha: { teams: 10, scoring_mode: "roto" },
      }
    )).toBe(false);
  });
});
