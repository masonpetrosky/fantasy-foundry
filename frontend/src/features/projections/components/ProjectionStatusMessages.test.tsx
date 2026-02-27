import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { ProjectionStatusMessages } from "./ProjectionStatusMessages";

describe("ProjectionStatusMessages", () => {
  it("renders nothing when no status sources are present", () => {
    const html = renderToStaticMarkup(
      <ProjectionStatusMessages
        pageResetNotice=""
        clearPageResetNotice={vi.fn()}
        exportError=""
        clearExportError={vi.fn()}
        compareShareCopyNotice=""
        clearCompareShareCopyNotice={vi.fn()}
        compareShareHydrating={false}
        compareShareNotice={null}
        clearCompareShareNotice={vi.fn()}
        lastRefreshedLabel=""
      />
    );

    expect(html).toBe("");
  });

  it("renders compare share hydration progress and warning notice", () => {
    const html = renderToStaticMarkup(
      <ProjectionStatusMessages
        pageResetNotice=""
        clearPageResetNotice={vi.fn()}
        exportError=""
        clearExportError={vi.fn()}
        compareShareCopyNotice=""
        clearCompareShareCopyNotice={vi.fn()}
        compareShareHydrating={true}
        compareShareNotice={{
          severity: "warning",
          message: "Loaded 1/2 shared comparison players. Missing: beta.",
        }}
        clearCompareShareNotice={vi.fn()}
        lastRefreshedLabel=""
      />
    );

    expect(html).toContain("Loading shared comparison players from link...");
    expect(html).toContain("Loaded 1/2 shared comparison players. Missing: beta.");
    expect(html).toContain("table-refresh-message warning");
    expect(html).toContain("Dismiss");
  });

  it("renders compare share hydration error as alert banner", () => {
    const html = renderToStaticMarkup(
      <ProjectionStatusMessages
        pageResetNotice=""
        clearPageResetNotice={vi.fn()}
        exportError=""
        clearExportError={vi.fn()}
        compareShareCopyNotice=""
        clearCompareShareCopyNotice={vi.fn()}
        compareShareHydrating={false}
        compareShareNotice={{
          severity: "error",
          message: "Unable to load shared comparison players from link.",
        }}
        clearCompareShareNotice={vi.fn()}
        lastRefreshedLabel=""
      />
    );

    expect(html).toContain("table-refresh-message error");
    expect(html).toContain("Unable to load shared comparison players from link.");
  });

  it("renders copy share-link status notice with dismiss action", () => {
    const html = renderToStaticMarkup(
      <ProjectionStatusMessages
        pageResetNotice=""
        clearPageResetNotice={vi.fn()}
        exportError=""
        clearExportError={vi.fn()}
        compareShareCopyNotice="Copied comparison share link."
        clearCompareShareCopyNotice={vi.fn()}
        compareShareHydrating={false}
        compareShareNotice={null}
        clearCompareShareNotice={vi.fn()}
        lastRefreshedLabel=""
      />
    );

    expect(html).toContain("Copied comparison share link.");
    expect(html).toContain("Dismiss");
  });
});
