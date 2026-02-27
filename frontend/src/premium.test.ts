import { describe, it, expect } from "vitest";
import {
  FREE_TIER_LIMITS,
  PREMIUM_TIER_LIMITS,
  resolveTierLimits,
  canUseFeature,
} from "./premium";

describe("premium", () => {
  describe("FREE_TIER_LIMITS", () => {
    it("caps sims at 300", () => {
      expect(FREE_TIER_LIMITS.maxSims).toBe(300);
    });

    it("disallows export", () => {
      expect(FREE_TIER_LIMITS.allowExport).toBe(false);
    });

    it("disallows points mode", () => {
      expect(FREE_TIER_LIMITS.allowPointsMode).toBe(false);
    });

    it("disallows trade analyzer", () => {
      expect(FREE_TIER_LIMITS.allowTradeAnalyzer).toBe(false);
    });
  });

  describe("PREMIUM_TIER_LIMITS", () => {
    it("allows 5000 sims", () => {
      expect(PREMIUM_TIER_LIMITS.maxSims).toBe(5000);
    });

    it("allows export", () => {
      expect(PREMIUM_TIER_LIMITS.allowExport).toBe(true);
    });

    it("allows all features", () => {
      expect(PREMIUM_TIER_LIMITS.allowPointsMode).toBe(true);
      expect(PREMIUM_TIER_LIMITS.allowTradeAnalyzer).toBe(true);
      expect(PREMIUM_TIER_LIMITS.allowCustomCategories).toBe(true);
      expect(PREMIUM_TIER_LIMITS.allowCloudSync).toBe(true);
    });
  });

  describe("resolveTierLimits", () => {
    it("returns premium limits when enforcement is off (default)", () => {
      // VITE_FF_PREMIUM_ENABLED is not set, so enforcement is off
      const limits = resolveTierLimits(null);
      expect(limits.maxSims).toBe(5000);
      expect(limits.allowExport).toBe(true);
    });

    it("returns premium limits for active subscription", () => {
      const limits = resolveTierLimits({ status: "active" });
      expect(limits).toEqual(PREMIUM_TIER_LIMITS);
    });
  });

  describe("canUseFeature", () => {
    it("returns true when tierLimits is null", () => {
      expect(canUseFeature(null, "allowExport")).toBe(true);
    });

    it("returns false for disabled feature in free tier", () => {
      expect(canUseFeature(FREE_TIER_LIMITS, "allowExport")).toBe(false);
    });

    it("returns true for enabled feature in premium tier", () => {
      expect(canUseFeature(PREMIUM_TIER_LIMITS, "allowExport")).toBe(true);
    });
  });
});
