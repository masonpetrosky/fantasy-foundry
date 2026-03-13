import { describe, expect, it, beforeEach } from "vitest";
import { captureException, initSentry } from "./sentry";

describe("sentry", () => {
  describe("initSentry", () => {
    it("is exported and is a function", () => {
      expect(typeof initSentry).toBe("function");
    });

    it("does not crash when VITE_SENTRY_DSN is not set", () => {
      expect(() => initSentry()).not.toThrow();
    });

    it("returns undefined", () => {
      const result = initSentry();
      expect(result).toBeUndefined();
    });

    it("can be called multiple times without crashing", () => {
      expect(() => {
        initSentry();
        initSentry();
        initSentry();
      }).not.toThrow();
    });
  });

  describe("captureException", () => {
    it("is exported and is a function", () => {
      expect(typeof captureException).toBe("function");
    });

    it("no-ops when Sentry is not initialized", () => {
      expect(() => captureException(new Error("test"))).not.toThrow();
      expect(() => captureException(new Error("test"), { feature: "calc" })).not.toThrow();
    });

    it("handles various error types gracefully", () => {
      expect(() => captureException("string error")).not.toThrow();
      expect(() => captureException(null)).not.toThrow();
      expect(() => captureException(undefined)).not.toThrow();
      expect(() => captureException(42)).not.toThrow();
      expect(() => captureException({ custom: "object" })).not.toThrow();
    });

    it("accepts optional context parameter", () => {
      expect(() => captureException(new Error("err"), undefined)).not.toThrow();
      expect(() => captureException(new Error("err"), { key: "value", nested: { a: 1 } })).not.toThrow();
    });

    it("accepts context with empty object", () => {
      expect(() => captureException(new Error("err"), {})).not.toThrow();
    });

    it("works with Error subclasses", () => {
      expect(() => captureException(new TypeError("type err"))).not.toThrow();
      expect(() => captureException(new RangeError("range err"))).not.toThrow();
    });
  });

  describe("initSentry with DSN set", () => {
    const origEnv = import.meta.env.VITE_SENTRY_DSN_FRONTEND;

    beforeEach(() => {
      // reset after each test
      import.meta.env.VITE_SENTRY_DSN_FRONTEND = origEnv;
    });

    it("attempts dynamic import when DSN is provided", async () => {
      import.meta.env.VITE_SENTRY_DSN_FRONTEND = "https://fake@sentry.io/123";
      // initSentry triggers a dynamic import("@sentry/react") which will fail
      // in test env but should not throw synchronously
      expect(() => initSentry()).not.toThrow();
    });

    it("does not crash when DSN is whitespace-only", () => {
      import.meta.env.VITE_SENTRY_DSN_FRONTEND = "   ";
      expect(() => initSentry()).not.toThrow();
    });
  });
});
