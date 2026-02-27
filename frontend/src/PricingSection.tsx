import React, { useState } from "react";
import { redirectToCheckout } from "./premium";
import { resolveApiBase } from "./api_base";
import { trackEvent } from "./analytics";
import type { Subscription } from "./premium";

const API: string = resolveApiBase();

const FREE_FEATURES: readonly string[] = [
  "5x5 Roto rankings",
  "300 simulations",
  "20-year projections",
];

const PRO_FEATURES: readonly string[] = [
  "Custom categories & points mode",
  "Up to 5,000 simulations",
  "CSV & XLSX export",
  "Trade Analyzer",
  "Cloud sync",
  "Priority support",
];

interface AuthUser {
  email?: string;
}

interface PricingSectionProps {
  authUser: AuthUser | null;
  subscription: Subscription | null;
}

export function PricingSection({ authUser, subscription }: PricingSectionProps): React.ReactElement {
  const [billing, setBilling] = useState<"monthly" | "annual">("monthly");
  const [loading, setLoading] = useState(false);

  const price = billing === "annual" ? "$29.99/yr" : "$4.99/mo";
  const savings = billing === "annual" ? "Save ~50%" : "";
  const isSubscribed = subscription?.status === "active";

  function handleUpgrade(): void {
    setLoading(true);
    trackEvent("ff_pricing_upgrade_click", { billing_period: billing });
    redirectToCheckout(API, {
      priceLookupKey: billing,
      userEmail: authUser?.email || "",
    }).catch(() => {
      setLoading(false);
    });
  }

  return (
    <section className="pricing-section" aria-labelledby="pricing-heading">
      <h2 id="pricing-heading">Pricing</h2>
      <div className="pricing-toggle" role="group" aria-label="Billing period">
        <button
          type="button"
          className={`pricing-toggle-btn ${billing === "monthly" ? "active" : ""}`.trim()}
          onClick={() => setBilling("monthly")}
        >
          Monthly
        </button>
        <button
          type="button"
          className={`pricing-toggle-btn ${billing === "annual" ? "active" : ""}`.trim()}
          onClick={() => setBilling("annual")}
        >
          Annual
        </button>
      </div>

      <div className="pricing-cards">
        <div className="pricing-card">
          <h3>Free</h3>
          <div className="pricing-price">$0</div>
          <ul className="pricing-features">
            {FREE_FEATURES.map(f => <li key={f}>{f}</li>)}
          </ul>
          <div className="pricing-card-action">
            {!isSubscribed && <span className="pricing-current">Current plan</span>}
          </div>
        </div>

        <div className="pricing-card pricing-card-pro">
          <h3>Pro</h3>
          <div className="pricing-price">
            {price}
            {savings && <span className="pricing-savings">{savings}</span>}
          </div>
          <ul className="pricing-features">
            {PRO_FEATURES.map(f => <li key={f}>{f}</li>)}
          </ul>
          <div className="pricing-card-action">
            {isSubscribed ? (
              <span className="pricing-current">Current plan</span>
            ) : (
              <button
                type="button"
                className="pricing-upgrade-btn"
                onClick={handleUpgrade}
                disabled={loading}
              >
                {loading ? "Redirecting..." : "Upgrade to Pro"}
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
