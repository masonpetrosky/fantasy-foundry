declare global {
  interface Window {
    API_BASE_URL?: string;
    __API_BASE_URL__?: string;
  }
}

function normalizeApiBase(value: string | null | undefined): string {
  return String(value || "").trim().replace(/\/+$/, "");
}

export function resolveApiBase(): string {
  const fromQuery = normalizeApiBase(new URLSearchParams(window.location.search).get("api"));
  if (fromQuery) return fromQuery;

  const fromGlobal = normalizeApiBase(window.API_BASE_URL || window.__API_BASE_URL__);
  if (fromGlobal) return fromGlobal;

  const { protocol, hostname, port } = window.location;
  if (protocol === "file:") return "http://localhost:8000";

  const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1";
  const localFrontendPorts = new Set(["3000", "4173", "5173"]);
  if (isLocalhost && localFrontendPorts.has(String(port || ""))) {
    return `${protocol}//${hostname}:8000`;
  }

  return "";
}
