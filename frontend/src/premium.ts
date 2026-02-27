/**
 * Premium tier feature gates.
 *
 * Free tier: 5x5 roto, 300 sims, no export, no trade analyzer.
 * Premium:   custom categories, 2000+ sims, export, trade analyzer, points mode, cloud sync.
 */

export interface TierLimits {
  maxSims: number;
  allowExport: boolean;
  allowPointsMode: boolean;
  allowTradeAnalyzer: boolean;
  allowCustomCategories: boolean;
  allowCloudSync: boolean;
}

export interface Subscription {
  status: string;
}

export const FREE_TIER_LIMITS: TierLimits = {
  maxSims: 300,
  allowExport: false,
  allowPointsMode: false,
  allowTradeAnalyzer: false,
  allowCustomCategories: false,
  allowCloudSync: false,
};

export const PREMIUM_TIER_LIMITS: TierLimits = {
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
export function resolveTierLimits(subscription: Subscription | null | undefined): TierLimits {
  const premiumEnabled = String(import.meta.env.VITE_FF_PREMIUM_ENABLED || "0").trim() === "1";
  if (!premiumEnabled) return PREMIUM_TIER_LIMITS;
  if (subscription?.status === "active") return PREMIUM_TIER_LIMITS;
  return FREE_TIER_LIMITS;
}

/**
 * Check if the user can perform a gated action.
 */
export function canUseFeature(tierLimits: TierLimits | null | undefined, feature: keyof TierLimits): boolean {
  if (!tierLimits) return true;
  return Boolean(tierLimits[feature]);
}

/**
 * Redirect the user to Stripe Checkout for a subscription.
 */
export async function redirectToCheckout(
  apiBase: string,
  { priceLookupKey, userEmail }: { priceLookupKey: string; userEmail?: string },
): Promise<void> {
  const resp = await fetch(`${apiBase}/api/billing/create-checkout-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      price_lookup_key: priceLookupKey,
      success_url: `${window.location.origin}/?billing=success`,
      cancel_url: `${window.location.origin}/?billing=cancel`,
      user_email: userEmail || "",
    }),
  });
  if (!resp.ok) throw new Error("Failed to create checkout session.");
  const data = await resp.json();
  if (data.checkout_url) {
    window.location.href = data.checkout_url;
  }
}
