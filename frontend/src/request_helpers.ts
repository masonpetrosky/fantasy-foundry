import { useEffect, useState } from "react";

interface ApiErrorPayload {
  detail?: string | Array<{ msg?: string }>;
  request_id?: string;
}

function appendRequestId(message: string, payload: ApiErrorPayload | null): string {
  const requestId = String(payload?.request_id || "").trim();
  if (!requestId) {
    return message;
  }
  return `${message} (request id: ${requestId})`;
}

export function formatApiError(status: number, payload: ApiErrorPayload | null, rawText = ""): string {
  const detail = payload && payload.detail;
  if (typeof detail === "string" && detail.trim()) {
    return appendRequestId(`Server error ${status}: ${detail}`, payload);
  }
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (first && typeof first.msg === "string") {
      return appendRequestId(`Validation error (${status}): ${first.msg}`, payload);
    }
  }
  const compactText = String(rawText || "").replace(/\s+/g, " ").trim();
  if (compactText && !compactText.startsWith("<")) {
    return appendRequestId(`Server error ${status}: ${compactText.slice(0, 180)}`, payload);
  }
  return appendRequestId(`Server error: ${status}`, payload);
}

interface ResponseLike {
  text: () => Promise<string>;
}

interface ResponsePayloadResult {
  payload: unknown;
  rawText: string;
}

export async function readResponsePayload(response: ResponseLike): Promise<ResponsePayloadResult> {
  const rawText = await response.text();
  if (!rawText) return { payload: null, rawText: "" };
  try {
    return { payload: JSON.parse(rawText), rawText };
  } catch {
    return { payload: null, rawText };
  }
}

export function sleepWithAbort(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!signal) {
      window.setTimeout(resolve, ms);
      return;
    }
    if (signal.aborted) {
      reject(new DOMException("Aborted", "AbortError"));
      return;
    }

    const timer = window.setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);

    const onAbort = (): void => {
      window.clearTimeout(timer);
      signal.removeEventListener("abort", onAbort);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal.addEventListener("abort", onAbort);
  });
}

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delayMs);
    return () => {
      window.clearTimeout(timer);
    };
  }, [value, delayMs]);

  return debounced;
}
