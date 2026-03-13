import { describe, expect, it } from "vitest";

describe("projections_explorer", () => {
  it("re-exports ProjectionsExplorer", async () => {
    const mod = await import("./projections_explorer");
    expect(mod.ProjectionsExplorer).toBeTruthy();
  });
});
