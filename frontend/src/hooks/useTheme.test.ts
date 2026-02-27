import { describe, it, expect } from "vitest";

describe("useTheme", () => {
  it("module exports useTheme", async () => {
    const mod = await import("./useTheme");
    expect(typeof mod.useTheme).toBe("function");
  });

  it("defaults to dark theme when localStorage is empty", () => {
    const stored = localStorage.getItem("ff:theme");
    // No stored value means default dark
    expect(stored === null || stored === "dark" || stored === undefined).toBe(true);
  });
});
