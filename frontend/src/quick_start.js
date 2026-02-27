import { trackEvent } from "./analytics";

export const QUICKSTART_CLICK_EVENT = "ff_quickstart_cta_click";
export const QUICKSTART_CLICK_ALIAS_EVENT = "quickstart_click";
export const QUICKSTART_IMPRESSION_EVENT = "ff_quickstart_impression";
export const QUICKSTART_IMPRESSION_ALIAS_EVENT = "quickstart_impression";
const QUICKSTART_ALIAS_EVENTS_ENABLED = String(
  import.meta.env?.VITE_FF_QUICKSTART_ALIAS_EVENTS_V1 ?? "1"
).trim() !== "0";

export function normalizeQuickStartMode(mode) {
  return mode === "points" ? "points" : "roto";
}

function buildQuickStartAnalyticsProps({
  mode,
  source,
  isFirstRun,
  section,
  dataVersion,
}) {
  const props = {
    source: String(source || "").trim() || "activation_strip",
    mode: normalizeQuickStartMode(mode),
    is_first_run: Boolean(isFirstRun),
  };
  const resolvedSection = String(section || "").trim();
  if (resolvedSection) {
    props.section = resolvedSection;
  }
  const resolvedDataVersion = String(dataVersion || "").trim();
  if (resolvedDataVersion) {
    props.data_version = resolvedDataVersion;
  }
  return props;
}

export function trackQuickStartClick({
  mode,
  source,
  isFirstRun = true,
  section = "",
  dataVersion = "",
  emitAliasEvents = QUICKSTART_ALIAS_EVENTS_ENABLED,
}) {
  const props = buildQuickStartAnalyticsProps({
    mode,
    source,
    isFirstRun,
    section,
    dataVersion,
  });
  trackEvent(QUICKSTART_CLICK_EVENT, props);
  if (emitAliasEvents) {
    trackEvent(QUICKSTART_CLICK_ALIAS_EVENT, props);
  }
  return props;
}

export function trackQuickStartImpression({
  source,
  mode = "roto",
  isFirstRun = true,
  section = "",
  dataVersion = "",
  emitAliasEvents = QUICKSTART_ALIAS_EVENTS_ENABLED,
}) {
  const props = buildQuickStartAnalyticsProps({
    mode,
    source,
    isFirstRun,
    section,
    dataVersion,
  });
  trackEvent(QUICKSTART_IMPRESSION_EVENT, props);
  if (emitAliasEvents) {
    trackEvent(QUICKSTART_IMPRESSION_ALIAS_EVENT, props);
  }
  return props;
}

export function runQuickStartFlow({
  mode,
  source = "activation_strip",
  isFirstRun = true,
  section = "",
  dataVersion = "",
  emitAliasEvents = QUICKSTART_ALIAS_EVENTS_ENABLED,
  openCalculatorPanel,
  setPendingQuickStartMode,
  scrollToCalculator,
  focusCalculator,
  scheduleFrame,
}) {
  const normalizedMode = normalizeQuickStartMode(mode);
  const resolvedSource = String(source || "").trim() || "activation_strip";
  trackQuickStartClick({
    mode: normalizedMode,
    source: resolvedSource,
    isFirstRun,
    section,
    dataVersion,
    emitAliasEvents,
  });
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
