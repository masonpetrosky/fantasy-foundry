/**
 * Extract a user-friendly error message from an API error response.
 *
 * The backend returns a structured JSON envelope with a `message` field
 * (see backend/api/error_handlers.py).  This helper walks common error
 * shapes so callers don't have to stringify raw objects.
 */
export function extractApiErrorMessage(error: unknown): string {
  if (error == null) return "Something went wrong. Please try again.";

  // Fetch Response-style errors (response.json() already parsed)
  if (typeof error === "object") {
    const obj = error as Record<string, unknown>;

    // Direct backend envelope: { message: "..." }
    if (typeof obj.message === "string" && obj.message.trim()) {
      return obj.message.trim();
    }

    // Wrapped in a response property (e.g. axios-style)
    if (obj.response && typeof obj.response === "object") {
      const resp = obj.response as Record<string, unknown>;
      if (resp.data && typeof resp.data === "object") {
        const data = resp.data as Record<string, unknown>;
        if (typeof data.message === "string" && data.message.trim()) {
          return data.message.trim();
        }
      }
    }

    // Error instance
    if (error instanceof Error && error.message.trim()) {
      return error.message.trim();
    }
  }

  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }

  return "Something went wrong. Please try again.";
}
