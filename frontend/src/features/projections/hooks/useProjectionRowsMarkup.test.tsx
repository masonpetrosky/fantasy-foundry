import { describe, expect, it } from "vitest";
import { useProjectionRowsMarkup } from "./useProjectionRowsMarkup";

describe("useProjectionRowsMarkup", () => {
  it("is exported as a function", () => {
    expect(typeof useProjectionRowsMarkup).toBe("function");
  });
});
