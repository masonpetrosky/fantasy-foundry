import { useEffect, useState } from "react";
import { resolveTierLimits, Subscription, TierLimits } from "../premium";
import { resolveApiBase } from "../api_base";

const API = resolveApiBase();

interface AuthUser {
  email?: string;
}

export function usePremiumStatus(authUser: AuthUser | null | undefined): {
  subscription: Subscription | null;
  tierLimits: TierLimits;
  premiumLoading: boolean;
} {
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [premiumLoading, setPremiumLoading] = useState(false);

  useEffect(() => {
    const email = authUser?.email;
    if (!email) {
      setSubscription(null);
      return;
    }
    let cancelled = false;
    setPremiumLoading(true);
    fetch(`${API}/api/billing/subscription-status?email=${encodeURIComponent(email)}`)
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (!cancelled) setSubscription(data);
      })
      .catch(() => {
        if (!cancelled) setSubscription(null);
      })
      .finally(() => {
        if (!cancelled) setPremiumLoading(false);
      });
    return () => { cancelled = true; };
  }, [authUser?.email]);

  const tierLimits = resolveTierLimits(subscription);

  return { subscription, tierLimits, premiumLoading };
}
