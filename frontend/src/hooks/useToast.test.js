import { describe, it, expect } from "vitest";

describe("useToast", () => {
  it("module exports useToast function", async () => {
    const mod = await import("./useToast.js");
    expect(typeof mod.useToast).toBe("function");
  });
});
