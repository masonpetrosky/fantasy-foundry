// eslint-disable-next-line no-control-regex
const CONTROL_CHARS_RE = /[\u0000-\u001f\u007f]/g;
const FORBIDDEN_FILENAME_CHARS_RE = /[\\/:*?"<>|]/g;

function _sanitizeFilenamePart(value: unknown): string {
  return String(value || "")
    .replace(CONTROL_CHARS_RE, "")
    .replace(FORBIDDEN_FILENAME_CHARS_RE, "_")
    .replace(/\s+/g, " ")
    .trim();
}

function _fallbackFilename(fallbackName: unknown): string {
  const fallback = _sanitizeFilenamePart(fallbackName) || "download";
  if (fallback === "." || fallback === "..") return "download";
  return fallback;
}

function _decodeExtendedFilenameToken(rawValue: unknown): string {
  let token = String(rawValue || "").trim();
  if (!token) return "";
  if (token.startsWith('"') && token.endsWith('"') && token.length >= 2) {
    token = token.slice(1, -1);
  }

  // RFC 5987 form: charset'language'percent-encoded-value
  const tickIdx = token.indexOf("'");
  const secondTickIdx = tickIdx < 0 ? -1 : token.indexOf("'", tickIdx + 1);
  const encoded = secondTickIdx >= 0 ? token.slice(secondTickIdx + 1) : token;
  try {
    return decodeURIComponent(encoded);
  } catch {
    return encoded;
  }
}

function _extractFilenameFromDisposition(disposition: unknown): string {
  const text = String(disposition || "");
  if (!text) return "";

  // Prefer RFC 5987 filename* when both are present.
  const filenameStarMatch = text.match(/filename\*\s*=\s*(?:"([^"]*)"|([^;]+))/i);
  if (filenameStarMatch) {
    const token = filenameStarMatch[1] || filenameStarMatch[2] || "";
    const decoded = _decodeExtendedFilenameToken(token);
    if (decoded) return decoded;
  }

  const filenameMatch = text.match(/filename\s*=\s*(?:"((?:\\.|[^"])*)"|([^;]+))/i);
  if (!filenameMatch) return "";
  const quoted = filenameMatch[1];
  const unquoted = filenameMatch[2];
  if (quoted != null) {
    return quoted.replace(/\\(.)/g, "$1").trim();
  }
  return String(unquoted || "").trim();
}

export function parseDownloadFilename(disposition: unknown, fallbackName: unknown): string {
  const fallback = _fallbackFilename(fallbackName);
  const extracted = _extractFilenameFromDisposition(disposition);
  const sanitized = _sanitizeFilenamePart(extracted);
  if (!sanitized || sanitized === "." || sanitized === "..") return fallback;
  return sanitized.slice(0, 180);
}
