import { describe, expect, it } from "vitest";
import { ErrorBoundary } from "./error_boundary.jsx";

describe("ErrorBoundary", () => {
  describe("getDerivedStateFromError", () => {
    it("returns error state from an Error instance", () => {
      const error = new Error("test crash");
      const state = ErrorBoundary.getDerivedStateFromError(error);
      expect(state).toEqual({ error });
    });

    it("returns error state from a non-Error value", () => {
      const state = ErrorBoundary.getDerivedStateFromError("string error");
      expect(state).toEqual({ error: "string error" });
    });

    it("returns error state from null", () => {
      const state = ErrorBoundary.getDerivedStateFromError(null);
      expect(state).toEqual({ error: null });
    });
  });
});
