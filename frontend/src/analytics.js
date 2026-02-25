const ANALYTICS_SESSION_ID_STORAGE_KEY = "ff:analytics-session-id:v1";
const ANALYTICS_BASE_CONTEXT = {
  is_signed_in: false,
  scoring_mode: "unknown",
  section: "unknown",
  data_version: "unknown",
};

let analyticsContext = { ...ANALYTICS_BASE_CONTEXT };

function normalizePropertyValue(value) {
  if (value == null) return null;
  if (typeof value === "string") return value.trim();
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "boolean") return value;
  return String(value);
}

function generateSessionId() {
  if (typeof window !== "undefined" && window.crypto?.getRandomValues) {
    const bytes = new Uint8Array(12);
    window.crypto.getRandomValues(bytes);
    const hex = Array.from(bytes).map(value => value.toString(16).padStart(2, "0")).join("");
    return `ffs-${hex}`;
  }
  const random = Math.random().toString(16).slice(2, 10);
  return `ffs-${Date.now().toString(16)}${random}`;
}

function resolveSessionId() {
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

export function setAnalyticsContext(nextValues = {}) {
  if (!nextValues || typeof nextValues !== "object" || Array.isArray(nextValues)) {
    return analyticsContext;
  }
  const merged = { ...analyticsContext };
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

export function resetAnalyticsContext() {
  analyticsContext = { ...ANALYTICS_BASE_CONTEXT };
}

export function buildAnalyticsPayload(name, properties = {}) {
  const eventName = String(name || "").trim();
  if (!eventName) return null;

  const resolvedProperties = {
    ...ANALYTICS_BASE_CONTEXT,
    ...analyticsContext,
    ...properties,
    session_id: resolveSessionId(),
  };
  const payloadProps = {};
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

export function trackEvent(name, properties = {}) {
  const payload = buildAnalyticsPayload(name, properties);
  if (!payload) return null;
  if (typeof window === "undefined") return payload;

  const eventData = {
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
