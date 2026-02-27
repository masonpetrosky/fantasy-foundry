import { trackEvent } from "./analytics";

export const QUICKSTART_CLICK_EVENT = "ff_quickstart_cta_click";
export const QUICKSTART_CLICK_ALIAS_EVENT = "quickstart_click";
export const QUICKSTART_IMPRESSION_EVENT = "ff_quickstart_impression";
export const QUICKSTART_IMPRESSION_ALIAS_EVENT = "quickstart_impression";
const QUICKSTART_ALIAS_EVENTS_ENABLED = String(
  import.meta.env?.VITE_FF_QUICKSTART_ALIAS_EVENTS_V1 ?? "1"
).trim() !== "0";

export type QuickStartMode = "roto" | "points";

export function normalizeQuickStartMode(mode: unknown): QuickStartMode {
  return mode === "points" ? "points" : "roto";
}

interface QuickStartAnalyticsInput {
  mode: unknown;
  source: unknown;
  isFirstRun: boolean;
  section?: string;
  dataVersion?: string;
}

function buildQuickStartAnalyticsProps({
  mode,
  source,
  isFirstRun,
  section,
  dataVersion,
}: QuickStartAnalyticsInput): Record<string, string | boolean> {
  const props: Record<string, string | boolean> = {
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

export interface TrackQuickStartInput {
  mode?: unknown;
  source: unknown;
  isFirstRun?: boolean;
  section?: string;
  dataVersion?: string;
  emitAliasEvents?: boolean;
}

export function trackQuickStartClick({
  mode,
  source,
  isFirstRun = true,
  section = "",
  dataVersion = "",
  emitAliasEvents = QUICKSTART_ALIAS_EVENTS_ENABLED,
}: TrackQuickStartInput): Record<string, string | boolean> {
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
}: TrackQuickStartInput): Record<string, string | boolean> {
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

export interface RunQuickStartFlowInput extends TrackQuickStartInput {
  openCalculatorPanel?: (source: string) => void;
  setPendingQuickStartMode?: (mode: QuickStartMode) => void;
  scrollToCalculator?: () => void;
  focusCalculator?: () => void;
  scheduleFrame?: (callback: () => void) => void;
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
}: RunQuickStartFlowInput): QuickStartMode {
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
    : (callback: () => void) => callback();
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
