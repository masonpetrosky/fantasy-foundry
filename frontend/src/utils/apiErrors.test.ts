import { describe, it, expect } from "vitest";
import { extractApiErrorMessage } from "./apiErrors";

describe("extractApiErrorMessage", () => {
  it("returns default message for null", () => {
    expect(extractApiErrorMessage(null)).toBe("Something went wrong. Please try again.");
  });

  it("returns default message for undefined", () => {
    expect(extractApiErrorMessage(undefined)).toBe("Something went wrong. Please try again.");
  });

  it("extracts message from direct backend envelope", () => {
    expect(extractApiErrorMessage({ message: "Rate limit exceeded" })).toBe("Rate limit exceeded");
  });

  it("trims whitespace from message", () => {
    expect(extractApiErrorMessage({ message: "  spaced  " })).toBe("spaced");
  });

  it("ignores empty message string", () => {
    expect(extractApiErrorMessage({ message: "   " })).toBe("Something went wrong. Please try again.");
  });

  it("extracts message from axios-style nested response", () => {
    const error = {
      response: {
        data: {
          message: "Server error occurred",
        },
      },
    };
    expect(extractApiErrorMessage(error)).toBe("Server error occurred");
  });

  it("extracts message from Error instance", () => {
    expect(extractApiErrorMessage(new Error("Network failure"))).toBe("Network failure");
  });

  it("extracts message from plain string", () => {
    expect(extractApiErrorMessage("Something broke")).toBe("Something broke");
  });

  it("trims string errors", () => {
    expect(extractApiErrorMessage("  trimmed error  ")).toBe("trimmed error");
  });

  it("returns default for empty string", () => {
    expect(extractApiErrorMessage("   ")).toBe("Something went wrong. Please try again.");
  });

  it("returns default for object without message", () => {
    expect(extractApiErrorMessage({ code: 500 })).toBe("Something went wrong. Please try again.");
  });

  it("returns default for empty object", () => {
    expect(extractApiErrorMessage({})).toBe("Something went wrong. Please try again.");
  });

  it("prefers direct message over nested response", () => {
    const error = {
      message: "Direct message",
      response: { data: { message: "Nested message" } },
    };
    expect(extractApiErrorMessage(error)).toBe("Direct message");
  });

  it("falls through to response.data.message when direct message missing", () => {
    const error = {
      response: {
        data: {
          message: "Nested only",
        },
      },
    };
    expect(extractApiErrorMessage(error)).toBe("Nested only");
  });

  it("returns default when response.data has no message", () => {
    const error = {
      response: {
        data: { code: 422 },
      },
    };
    expect(extractApiErrorMessage(error)).toBe("Something went wrong. Please try again.");
  });

  it("returns default when response is not an object", () => {
    const error = { response: "not-an-object" };
    expect(extractApiErrorMessage(error)).toBe("Something went wrong. Please try again.");
  });

  it("handles non-string message property", () => {
    expect(extractApiErrorMessage({ message: 42 })).toBe("Something went wrong. Please try again.");
  });

  it("returns default for number input", () => {
    expect(extractApiErrorMessage(0)).toBe("Something went wrong. Please try again.");
  });

  it("returns default for boolean input", () => {
    expect(extractApiErrorMessage(false)).toBe("Something went wrong. Please try again.");
  });
});
