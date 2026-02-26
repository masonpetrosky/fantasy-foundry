/**
 * Premium tier feature gates.
 *
 * Free tier: 5x5 roto, 300 sims, no export, no trade analyzer.
 * Premium:   custom categories, 2000+ sims, export, trade analyzer, points mode, cloud sync.
 */

export const FREE_TIER_LIMITS = {
  maxSims: 300,
  allowExport: false,
  allowPointsMode: false,
  allowTradeAnalyzer: false,
  allowCustomCategories: false,
  allowCloudSync: false,
};

export const PREMIUM_TIER_LIMITS = {
  maxSims: 5000,
  allowExport: true,
  allowPointsMode: true,
  allowTradeAnalyzer: true,
  allowCustomCategories: true,
  allowCloudSync: true,
};

/**
 * Resolve tier limits for the current user.
 * When premium enforcement is off (default), all features are enabled.
 */
export function resolveTierLimits(subscription) {
  const premiumEnabled = String(import.meta.env.VITE_FF_PREMIUM_ENABLED || "0").trim() === "1";
  if (!premiumEnabled) return PREMIUM_TIER_LIMITS;
  if (subscription?.status === "active") return PREMIUM_TIER_LIMITS;
  return FREE_TIER_LIMITS;
}

/**
 * Check if the user can perform a gated action.
 */
export function canUseFeature(tierLimits, feature) {
  if (!tierLimits) return true;
  return Boolean(tierLimits[feature]);
}
