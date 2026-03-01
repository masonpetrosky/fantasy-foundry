import { describe, it, expect } from "vitest";
import { useMobileNavMenu } from "./useMobileNavMenu";

describe("useMobileNavMenu", () => {
  it("exports a function", () => {
    expect(typeof useMobileNavMenu).toBe("function");
  });
});
