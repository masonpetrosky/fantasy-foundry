import { afterEach, describe, expect, it, vi } from "vitest";
import { resolveApiBase } from "./api_base";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubLocation(overrides: Partial<Location> = {}) {
  vi.stubGlobal("window", {
    ...window,
    location: { ...window.location, ...overrides },
  });
}

describe("resolveApiBase", () => {
  it("returns empty string for production origin", () => {
    stubLocation({ protocol: "https:", hostname: "fantasy-foundry.com", port: "", search: "" });
    expect(resolveApiBase()).toBe("");
  });

  it("returns localhost:8000 for local dev port", () => {
    stubLocation({ protocol: "http:", hostname: "localhost", port: "5173", search: "" });
    expect(resolveApiBase()).toBe("http://localhost:8000");
  });

  it("reads api query param when present", () => {
    stubLocation({ search: "?api=https://custom.api.com/" });
    expect(resolveApiBase()).toBe("https://custom.api.com");
  });
});
