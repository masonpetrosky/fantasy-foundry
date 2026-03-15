import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, it, vi } from "vitest";
import { checkA11y } from "../../../test/a11y-helpers";
import { ProjectionStatusMessages } from "./ProjectionStatusMessages";

function renderToContainer(element: React.ReactElement): { container: HTMLDivElement; cleanup: () => void } {
  const container = document.createElement("div");
  document.body.appendChild(container);
  let root: ReturnType<typeof createRoot>;
  act(() => {
    root = createRoot(container);
    root.render(element);
  });
  return {
    container,
    cleanup: () => {
      act(() => root.unmount());
      document.body.removeChild(container);
    },
  };
}

function defaultProps(overrides: Partial<React.ComponentProps<typeof ProjectionStatusMessages>> = {}) {
  return {
    pageResetNotice: "",
    clearPageResetNotice: vi.fn(),
    exportError: "",
    clearExportError: vi.fn(),
    compareShareCopyNotice: "",
    clearCompareShareCopyNotice: null,
    compareShareHydrating: false,
    compareShareNotice: null,
    clearCompareShareNotice: null,
    lastRefreshedLabel: "",
    ...overrides,
  };
}

describe("ProjectionStatusMessages a11y", () => {
  it("passes axe checks when empty", async () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionStatusMessages, defaultProps()),
    );
    await checkA11y(container);
    cleanup();
  });

  it("passes axe checks with an export error", async () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(
        ProjectionStatusMessages,
        defaultProps({ exportError: "Export failed" }),
      ),
    );
    await checkA11y(container);
    cleanup();
  });

  it("passes axe checks with a page reset notice", async () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(
        ProjectionStatusMessages,
        defaultProps({ pageResetNotice: "Page was reset" }),
      ),
    );
    await checkA11y(container);
    cleanup();
  });
});
