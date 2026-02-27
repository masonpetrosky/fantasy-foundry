/**
 * Billing redirect URL parameter utilities.
 *
 * After Stripe Checkout, the user lands back with ?billing=success or ?billing=cancel.
 * These helpers parse that param and clean it from the URL.
 */

const BILLING_PARAM = "billing";

export type BillingRedirectStatus = "success" | "cancel" | null;

/**
 * Parse the ?billing= query param from the current URL.
 * Returns "success", "cancel", or null.
 */
export function parseBillingRedirectParam(search: string | null | undefined): BillingRedirectStatus {
  const raw = new URLSearchParams(search || "").get(BILLING_PARAM);
  const normalized = String(raw || "").trim().toLowerCase();
  if (normalized === "success") return "success";
  if (normalized === "cancel") return "cancel";
  return null;
}

/**
 * Remove the ?billing= param from the URL without triggering navigation.
 */
export function cleanBillingParam(): void {
  const url = new URL(window.location.href);
  if (!url.searchParams.has(BILLING_PARAM)) return;
  url.searchParams.delete(BILLING_PARAM);
  window.history.replaceState({}, "", url.toString());
}
