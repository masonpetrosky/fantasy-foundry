import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";
import { MethodologySection } from "./methodology_section";

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

describe("MethodologySection", () => {
  it("is exported as a function", () => {
    expect(typeof MethodologySection).toBe("function");
  });

  it("renders methodology heading", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MethodologySection)
    );
    expect(container.querySelector("#methodology-heading")).not.toBeNull();
    expect(container.textContent).toContain("Methodology");
    cleanup();
  });

  it("renders with accessible section", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MethodologySection)
    );
    const section = container.querySelector('[aria-labelledby="methodology-heading"]');
    expect(section).not.toBeNull();
    cleanup();
  });
});
