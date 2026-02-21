import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import process from "node:process";
import { describe, expect, it } from "vitest";

function readIndexHtml() {
  return readFileSync(resolve(process.cwd(), "index.html"), "utf-8");
}

describe("frontend index shell metadata", () => {
  it("includes canonical and robots tags", () => {
    const html = readIndexHtml();
    expect(html).toContain('<link rel="canonical" href="https://fantasy-foundry.com/">');
    expect(html).toContain('<meta name="robots" content="index, follow, max-image-preview:large">');
  });

  it("includes WebSite and SoftwareApplication JSON-LD schemas", () => {
    const html = readIndexHtml();
    const schemaMatches = [...html.matchAll(/<script type="application\/ld\+json">\s*([\s\S]*?)\s*<\/script>/g)];
    const schemas = schemaMatches.map(match => JSON.parse(match[1]));
    const schemaTypes = schemas.map(schema => schema["@type"]);

    expect(schemaTypes).toContain("WebSite");
    expect(schemaTypes).toContain("SoftwareApplication");
  });
});
