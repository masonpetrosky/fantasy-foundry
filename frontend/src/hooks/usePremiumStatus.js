import { useEffect, useState } from "react";
import { resolveTierLimits } from "../premium";
import { resolveApiBase } from "../api_base";

const API = resolveApiBase();

export function usePremiumStatus(authUser) {
  const [subscription, setSubscription] = useState(null);
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
