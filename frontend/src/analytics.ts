export interface AnalyticsProperties {
  [key: string]: string | number | boolean | null;
}

export interface AnalyticsPayload {
  event: string;
  properties: AnalyticsProperties;
  timestamp: number;
}

export interface ActivationFunnel {
  window: {
    events_total: number;
    first_event_at_ms: number | null;
    last_event_at_ms: number | null;
  };
  quickstart: {
    impressions: number;
    clicks: number;
    runs_started: number;
    runs_succeeded: number;
    runs_failed: number;
    click_through_rate_pct: number | null;
    run_start_rate_pct: number | null;
    run_success_rate_pct: number | null;
    median_time_to_first_success_ms: number | null;
  };
}

interface AnalyticsDebugBridge {
  context: () => AnalyticsProperties;
  events: (limit?: number | null) => AnalyticsPayload[];
  clear: () => void;
  summary: (events?: AnalyticsPayload[] | null) => ActivationFunnel;
  exportCsv: (filename?: string) => boolean;
  toCsv: (events?: AnalyticsPayload[] | null) => string;
  track: (name: string, properties?: AnalyticsProperties) => AnalyticsPayload | null;
}

declare global {
  interface Window {
    dataLayer?: Record<string, unknown>[];
    ffAnalytics?: AnalyticsDebugBridge;
  }
}

if (typeof window !== "undefined") {
  window.dataLayer = window.dataLayer || [];
}

const ANALYTICS_SESSION_ID_STORAGE_KEY = "ff:analytics-session-id:v1";
const ANALYTICS_EVENT_BUFFER_STORAGE_KEY = "ff:analytics-events:v1";
const ANALYTICS_EVENT_BUFFER_MAX = 400;
const ANALYTICS_BASE_CONTEXT: AnalyticsProperties = {
  is_signed_in: false,
  scoring_mode: "unknown",
  section: "unknown",
  data_version: "unknown",
};

let analyticsContext: AnalyticsProperties = { ...ANALYTICS_BASE_CONTEXT };

function normalizePropertyValue(value: unknown): string | number | boolean | null {
  if (value == null) return null;
  if (typeof value === "string") return value.trim();
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "boolean") return value;
  return String(value);
}

function generateSessionId(): string {
  if (typeof window !== "undefined" && window.crypto?.getRandomValues) {
    const bytes = new Uint8Array(12);
    window.crypto.getRandomValues(bytes);
    const hex = Array.from(bytes).map(value => value.toString(16).padStart(2, "0")).join("");
    return `ffs-${hex}`;
  }
  const random = Math.random().toString(16).slice(2, 10);
  return `ffs-${Date.now().toString(16)}${random}`;
}

function resolveSessionId(): string {
  if (typeof window === "undefined") return "ffs-server";
  try {
    const existing = String(window.localStorage.getItem(ANALYTICS_SESSION_ID_STORAGE_KEY) || "").trim();
    if (existing) return existing;
    const generated = generateSessionId();
    window.localStorage.setItem(ANALYTICS_SESSION_ID_STORAGE_KEY, generated);
    return generated;
  } catch {
    return generateSessionId();
  }
}

function readEventBufferStorage(): Storage | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function readAnalyticsEventBufferRaw(): AnalyticsPayload[] {
  const storage = readEventBufferStorage();
  if (!storage) return [];
  try {
    const raw = String(storage.getItem(ANALYTICS_EVENT_BUFFER_STORAGE_KEY) || "").trim();
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((entry: unknown) => entry && typeof entry === "object")
      .map((entry: Record<string, unknown>) => ({
        event: String(entry.event || "").trim(),
        properties: entry.properties && typeof entry.properties === "object" ? entry.properties as AnalyticsProperties : {},
        timestamp: Number(entry.timestamp),
      }))
      .filter((entry: AnalyticsPayload) => entry.event && Number.isFinite(entry.timestamp));
  } catch {
    return [];
  }
}

function writeAnalyticsEventBufferRaw(entries: AnalyticsPayload[]): void {
  const storage = readEventBufferStorage();
  if (!storage) return;
  try {
    storage.setItem(ANALYTICS_EVENT_BUFFER_STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Ignore storage write failures in constrained browser modes.
  }
}

function appendAnalyticsEventBuffer(payload: AnalyticsPayload): void {
  const current = readAnalyticsEventBufferRaw();
  current.push({
    event: payload.event,
    properties: payload.properties,
    timestamp: payload.timestamp,
  });
  const trimmed = current.slice(-ANALYTICS_EVENT_BUFFER_MAX);
  writeAnalyticsEventBufferRaw(trimmed);
}

function median(values: number[]): number | null {
  const finite = values
    .map(value => Number(value))
    .filter(value => Number.isFinite(value));
  if (finite.length === 0) return null;
  const sorted = finite.slice().sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 1) return sorted[middle];
  return (sorted[middle - 1] + sorted[middle]) / 2;
}

function ratioPercent(numerator: number, denominator: number): number | null {
  const n = Number(numerator);
  const d = Number(denominator);
  if (!Number.isFinite(n) || !Number.isFinite(d) || d <= 0) return null;
  return Number(((n / d) * 100).toFixed(1));
}

function csvCell(value: unknown): string {
  if (value == null) return "";
  const text = String(value);
  const escaped = text.replace(/"/g, "\"\"");
  return /[",\n]/.test(escaped) ? `"${escaped}"` : escaped;
}

export function setAnalyticsContext(nextValues: Record<string, unknown> = {}): AnalyticsProperties {
  if (!nextValues || typeof nextValues !== "object" || Array.isArray(nextValues)) {
    return analyticsContext;
  }
  const merged: AnalyticsProperties = { ...analyticsContext };
  Object.entries(nextValues).forEach(([key, value]) => {
    const normalized = normalizePropertyValue(value);
    if (normalized === null || normalized === "") {
      delete merged[key];
      return;
    }
    merged[key] = normalized;
  });
  analyticsContext = merged;
  return analyticsContext;
}

export function resetAnalyticsContext(): void {
  analyticsContext = { ...ANALYTICS_BASE_CONTEXT };
}

export function readAnalyticsEventBuffer(limit: number | null = null): AnalyticsPayload[] {
  const events = readAnalyticsEventBufferRaw();
  const resolvedLimit = Number(limit);
  if (Number.isFinite(resolvedLimit) && resolvedLimit > 0) {
    return events.slice(-Math.round(resolvedLimit));
  }
  return events;
}

export function clearAnalyticsEventBuffer(): void {
  writeAnalyticsEventBufferRaw([]);
}

export function summarizeActivationFunnel(events: AnalyticsPayload[] = readAnalyticsEventBufferRaw()): ActivationFunnel {
  const normalized = Array.isArray(events) ? events : [];
  const countByEvent: Record<string, number> = {};
  normalized.forEach(entry => {
    const eventName = String(entry?.event || "").trim();
    if (!eventName) return;
    countByEvent[eventName] = (countByEvent[eventName] || 0) + 1;
  });

  const quickstartRunStarts = normalized.filter(entry => (
    entry?.event === "calculator_run_start"
    && String((entry?.properties as Record<string, unknown>)?.source || "").trim() === "quickstart"
  ));
  const quickstartSuccesses = normalized.filter(entry => (
    entry?.event === "ff_calculation_success"
    && String((entry?.properties as Record<string, unknown>)?.source || "").trim() === "quickstart"
  ));
  const quickstartErrors = normalized.filter(entry => (
    entry?.event === "ff_calculation_error"
    && String((entry?.properties as Record<string, unknown>)?.source || "").trim() === "quickstart"
  ));
  const firstSuccessDurations = quickstartSuccesses
    .map(entry => Number((entry?.properties as Record<string, unknown>)?.time_to_first_success_ms))
    .filter(value => Number.isFinite(value) && value >= 0);

  const firstEventTs = normalized.length > 0 ? Number(normalized[0]?.timestamp) : null;
  const lastEventTs = normalized.length > 0 ? Number(normalized[normalized.length - 1]?.timestamp) : null;

  const impressions = countByEvent.ff_quickstart_impression || 0;
  const clicks = countByEvent.ff_quickstart_cta_click || 0;
  const runsStarted = quickstartRunStarts.length;
  const runsSucceeded = quickstartSuccesses.length;

  return {
    window: {
      events_total: normalized.length,
      first_event_at_ms: Number.isFinite(firstEventTs) ? firstEventTs : null,
      last_event_at_ms: Number.isFinite(lastEventTs) ? lastEventTs : null,
    },
    quickstart: {
      impressions,
      clicks,
      runs_started: runsStarted,
      runs_succeeded: runsSucceeded,
      runs_failed: quickstartErrors.length,
      click_through_rate_pct: ratioPercent(clicks, impressions),
      run_start_rate_pct: ratioPercent(runsStarted, clicks),
      run_success_rate_pct: ratioPercent(runsSucceeded, runsStarted),
      median_time_to_first_success_ms: median(firstSuccessDurations),
    },
  };
}

export function analyticsEventsToCsv(events: AnalyticsPayload[] = readAnalyticsEventBufferRaw()): string {
  const rows = Array.isArray(events) ? events : [];
  const header = [
    "timestamp_ms",
    "timestamp",
    "event",
    "session_id",
    "source",
    "mode",
    "is_first_run",
    "section",
    "data_version",
    "scoring_mode",
    "start_year",
    "horizon",
    "teams",
    "player_count",
    "time_to_first_success_ms",
    "quickstart_mode",
    "quickstart_source",
    "error_message",
    "job_id",
  ];
  const lines = [header.join(",")];
  rows.forEach(entry => {
    const props = entry?.properties && typeof entry.properties === "object" ? entry.properties as Record<string, unknown> : {};
    const timestampMs = Number(entry?.timestamp);
    const timestampIso = Number.isFinite(timestampMs) ? new Date(timestampMs).toISOString() : "";
    const line = [
      Number.isFinite(timestampMs) ? timestampMs : "",
      timestampIso,
      entry?.event ?? "",
      props.session_id ?? "",
      props.source ?? "",
      props.mode ?? "",
      props.is_first_run ?? "",
      props.section ?? "",
      props.data_version ?? "",
      props.scoring_mode ?? props.scoringMode ?? "",
      props.start_year ?? props.startYear ?? "",
      props.horizon ?? "",
      props.teams ?? "",
      props.player_count ?? props.playerCount ?? "",
      props.time_to_first_success_ms ?? "",
      props.quickstart_mode ?? props.quickStartMode ?? "",
      props.quickstart_source ?? props.quickStartSource ?? "",
      props.error_message ?? "",
      props.job_id ?? props.jobId ?? "",
    ];
    lines.push(line.map(csvCell).join(","));
  });
  return `${lines.join("\n")}\n`;
}

export function downloadAnalyticsEventCsv(filename: string = "ff-analytics-events.csv"): boolean {
  if (typeof window === "undefined" || typeof document === "undefined") return false;
  const csv = analyticsEventsToCsv(readAnalyticsEventBufferRaw());
  try {
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const href = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = href;
    link.download = String(filename || "ff-analytics-events.csv").trim() || "ff-analytics-events.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(href);
    return true;
  } catch {
    return false;
  }
}

export function installAnalyticsDebugBridge(): boolean {
  if (typeof window === "undefined") return false;
  const bridge: AnalyticsDebugBridge = {
    context: () => ({ ...analyticsContext }),
    events: (limit: number | null = null) => readAnalyticsEventBuffer(limit),
    clear: () => clearAnalyticsEventBuffer(),
    summary: (events: AnalyticsPayload[] | null = null) => summarizeActivationFunnel(events || readAnalyticsEventBufferRaw()),
    exportCsv: (filename: string = "ff-analytics-events.csv") => downloadAnalyticsEventCsv(filename),
    toCsv: (events: AnalyticsPayload[] | null = null) => analyticsEventsToCsv(events || readAnalyticsEventBufferRaw()),
    track: (name: string, properties: AnalyticsProperties = {}) => trackEvent(name, properties),
  };
  try {
    window.ffAnalytics = bridge;
  } catch {
    return false;
  }
  return true;
}

export function buildAnalyticsPayload(name: string, properties: Record<string, unknown> = {}): AnalyticsPayload | null {
  const eventName = String(name || "").trim();
  if (!eventName) return null;

  const resolvedProperties: Record<string, unknown> = {
    ...ANALYTICS_BASE_CONTEXT,
    ...analyticsContext,
    ...properties,
    session_id: resolveSessionId(),
  };
  const payloadProps: AnalyticsProperties = {};
  Object.entries(resolvedProperties || {}).forEach(([key, value]) => {
    const normalized = normalizePropertyValue(value);
    if (normalized === null || normalized === "") return;
    payloadProps[key] = normalized;
  });

  return {
    event: eventName,
    properties: payloadProps,
    timestamp: Date.now(),
  };
}

export function trackEvent(name: string, properties: Record<string, unknown> = {}): AnalyticsPayload | null {
  const payload = buildAnalyticsPayload(name, properties);
  if (!payload) return null;
  if (typeof window === "undefined") return payload;
  appendAnalyticsEventBuffer(payload);

  const eventData: Record<string, unknown> = {
    event: payload.event,
    ...payload.properties,
  };
  if (Array.isArray(window.dataLayer)) {
    window.dataLayer.push(eventData);
  }

  if (typeof window.dispatchEvent === "function" && typeof window.CustomEvent === "function") {
    window.dispatchEvent(new window.CustomEvent("ff:analytics", { detail: payload }));
  }

  return payload;
}
