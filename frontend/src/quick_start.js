import { trackEvent } from "./analytics.js";

export function normalizeQuickStartMode(mode) {
  return mode === "points" ? "points" : "roto";
}

export function runQuickStartFlow({
  mode,
  source = "activation_strip",
  openCalculatorPanel,
  setPendingQuickStartMode,
  scrollToCalculator,
  focusCalculator,
  scheduleFrame,
}) {
  const normalizedMode = normalizeQuickStartMode(mode);
  const resolvedSource = String(source || "").trim() || "activation_strip";
  trackEvent("ff_quickstart_cta_click", { source: resolvedSource, mode: normalizedMode });
  trackEvent("ff_onboarding_cta_click", { source: resolvedSource, mode: normalizedMode });
  trackEvent("quickstart_click", { source: resolvedSource, mode: normalizedMode });
  if (typeof openCalculatorPanel === "function") {
    openCalculatorPanel(resolvedSource);
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
