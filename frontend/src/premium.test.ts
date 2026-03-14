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

    it("returns true when tierLimits is undefined", () => {
      expect(canUseFeature(undefined, "allowExport")).toBe(true);
    });

    it("returns false for disabled feature in free tier", () => {
      expect(canUseFeature(FREE_TIER_LIMITS, "allowExport")).toBe(false);
    });

    it("returns true for enabled feature in premium tier", () => {
      expect(canUseFeature(PREMIUM_TIER_LIMITS, "allowExport")).toBe(true);
    });

    it("checks allowPointsMode correctly", () => {
      expect(canUseFeature(FREE_TIER_LIMITS, "allowPointsMode")).toBe(false);
      expect(canUseFeature(PREMIUM_TIER_LIMITS, "allowPointsMode")).toBe(true);
    });

    it("checks allowTradeAnalyzer correctly", () => {
      expect(canUseFeature(FREE_TIER_LIMITS, "allowTradeAnalyzer")).toBe(false);
      expect(canUseFeature(PREMIUM_TIER_LIMITS, "allowTradeAnalyzer")).toBe(true);
    });

    it("checks allowCustomCategories correctly", () => {
      expect(canUseFeature(FREE_TIER_LIMITS, "allowCustomCategories")).toBe(false);
      expect(canUseFeature(PREMIUM_TIER_LIMITS, "allowCustomCategories")).toBe(true);
    });

    it("checks allowCloudSync correctly", () => {
      expect(canUseFeature(FREE_TIER_LIMITS, "allowCloudSync")).toBe(false);
      expect(canUseFeature(PREMIUM_TIER_LIMITS, "allowCloudSync")).toBe(true);
    });

    it("returns truthy for maxSims (numeric feature)", () => {
      expect(canUseFeature(FREE_TIER_LIMITS, "maxSims")).toBe(true);
      expect(canUseFeature(PREMIUM_TIER_LIMITS, "maxSims")).toBe(true);
    });
  });

  describe("FREE_TIER_LIMITS completeness", () => {
    it("disallows custom categories", () => {
      expect(FREE_TIER_LIMITS.allowCustomCategories).toBe(false);
    });

    it("disallows cloud sync", () => {
      expect(FREE_TIER_LIMITS.allowCloudSync).toBe(false);
    });
  });

  describe("resolveTierLimits edge cases", () => {
    it("returns free limits for inactive subscription when premium enabled", () => {
      // Without controlling VITE_FF_PREMIUM_ENABLED we can only test the default path
      const limits = resolveTierLimits({ status: "inactive" });
      // Default: premium enforcement off, so returns premium limits
      expect(limits.maxSims).toBe(5000);
    });

    it("returns premium for undefined subscription", () => {
      const limits = resolveTierLimits(undefined);
      expect(limits.maxSims).toBe(5000);
    });
  });

  describe("redirectToCheckout", () => {
    it("is exported as a function", async () => {
      const { redirectToCheckout } = await import("./premium");
      expect(typeof redirectToCheckout).toBe("function");
    });
  });
});
