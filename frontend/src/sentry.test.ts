import { describe, expect, it } from "vitest";
import { captureException } from "./sentry";

describe("sentry", () => {
  it("captureException no-ops when Sentry is not initialized", () => {
    expect(() => captureException(new Error("test"))).not.toThrow();
    expect(() => captureException(new Error("test"), { feature: "calc" })).not.toThrow();
  });
});
