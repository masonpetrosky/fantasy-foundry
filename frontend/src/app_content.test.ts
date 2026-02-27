import { describe, expect, it } from "vitest";
import { glossaryTermAnchorId } from "./app_content";

describe("glossaryTermAnchorId", () => {
  it("slugifies a normal term", () => {
    expect(glossaryTermAnchorId("5x5 Roto")).toBe("glossary-term-5x5-roto");
  });

  it("strips leading/trailing hyphens", () => {
    expect(glossaryTermAnchorId("  --Hello World--  ")).toBe("glossary-term-hello-world");
  });

  it("falls back for empty input", () => {
    expect(glossaryTermAnchorId("")).toBe("glossary-term-term");
    expect(glossaryTermAnchorId(null)).toBe("glossary-term-term");
  });
});
