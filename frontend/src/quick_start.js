import { trackEvent } from "./analytics.js";

export function normalizeQuickStartMode(mode) {
  return mode === "points" ? "points" : "roto";
}

export function runQuickStartFlow({
  mode,
  onboardingDismissed,
  markOnboardingDismissed,
  openCalculatorPanel,
  setPendingQuickStartMode,
  scrollToCalculator,
  focusCalculator,
  scheduleFrame,
}) {
  const normalizedMode = normalizeQuickStartMode(mode);
  trackEvent("ff_onboarding_cta_click", { source: "onboarding_strip", mode: normalizedMode });
  trackEvent("quickstart_click", { source: "onboarding_strip", mode: normalizedMode });

  if (!onboardingDismissed && typeof markOnboardingDismissed === "function") {
    markOnboardingDismissed();
  }
  if (typeof openCalculatorPanel === "function") {
    openCalculatorPanel();
  }
  if (typeof setPendingQuickStartMode === "function") {
    setPendingQuickStartMode(normalizedMode);
  }

  const schedule = typeof scheduleFrame === "function"
    ? scheduleFrame
    : callback => callback();
  schedule(() => {
    if (typeof scrollToCalculator === "function") {
      scrollToCalculator();
    }
    if (typeof focusCalculator === "function") {
      focusCalculator();
    }
  });

  return normalizedMode;
}
