import { describe, expect, it } from "vitest";
import { normalizeCalculatorRunSettingsInput } from "./calculator_submit";

describe("normalizeCalculatorRunSettingsInput", () => {
  it("falls back to current settings when called with a click event object", () => {
    const currentSettings = { hit_c: 1, teams: 12 };
    const clickEvent = {
      nativeEvent: {},
      preventDefault() {},
    };

    const resolved = normalizeCalculatorRunSettingsInput(clickEvent, currentSettings);
    expect(resolved).toBe(currentSettings);
  });

  it("uses explicit settings payloads unchanged", () => {
    const currentSettings = { hit_c: 1, teams: 12 };
    const nextSettings = { hit_c: 2, teams: 10 };

    const resolved = normalizeCalculatorRunSettingsInput(nextSettings, currentSettings);
    expect(resolved).toBe(nextSettings);
  });

  it("falls back to current settings for nullish input", () => {
    const currentSettings = { hit_c: 1, teams: 12 };

    expect(normalizeCalculatorRunSettingsInput(undefined, currentSettings)).toBe(currentSettings);
    expect(normalizeCalculatorRunSettingsInput(null, currentSettings)).toBe(currentSettings);
  });
});
