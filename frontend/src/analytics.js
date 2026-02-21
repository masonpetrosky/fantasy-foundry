function normalizePropertyValue(value) {
  if (value == null) return null;
  if (typeof value === "string") return value.trim();
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value === "boolean") return value;
  return String(value);
}

export function buildAnalyticsPayload(name, properties = {}) {
  const eventName = String(name || "").trim();
  if (!eventName) return null;

  const payloadProps = {};
  Object.entries(properties || {}).forEach(([key, value]) => {
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
