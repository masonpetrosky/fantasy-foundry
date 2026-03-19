import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";
import { CalcTooltip } from "./dynasty_calculator_tooltip";

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

describe("CalcTooltip", () => {
  function renderTooltip(): { container: HTMLDivElement; cleanup: () => void } {
    return renderToContainer(<CalcTooltip label="Help">Tooltip content</CalcTooltip>);
  }

  it("is exported as a function", () => {
    expect(typeof CalcTooltip).toBe("function");
  });

  it("renders the label", () => {
    const { container, cleanup } = renderTooltip();
    expect(container.textContent).toContain("Help");
    cleanup();
  });

  it("does not show tooltip content initially", () => {
    const { container, cleanup } = renderTooltip();
    expect(container.querySelector('[role="tooltip"]')).toBeNull();
    cleanup();
  });

  it("shows tooltip content when button is clicked", () => {
    const { container, cleanup } = renderTooltip();
    const button = container.querySelector("button") as HTMLButtonElement;
    act(() => { button.click(); });
    expect(container.querySelector('[role="tooltip"]')).not.toBeNull();
    expect(container.textContent).toContain("Tooltip content");
    cleanup();
  });

  it("toggles tooltip on repeated clicks", () => {
    const { container, cleanup } = renderTooltip();
    const button = container.querySelector("button") as HTMLButtonElement;
    act(() => { button.click(); });
    expect(container.querySelector('[role="tooltip"]')).not.toBeNull();
    act(() => { button.click(); });
    expect(container.querySelector('[role="tooltip"]')).toBeNull();
    cleanup();
  });

  it("sets aria-expanded on button", () => {
    const { container, cleanup } = renderTooltip();
    const button = container.querySelector("button") as HTMLButtonElement;
    expect(button.getAttribute("aria-expanded")).toBe("false");
    act(() => { button.click(); });
    expect(button.getAttribute("aria-expanded")).toBe("true");
    cleanup();
  });

  it("closes on Escape key", () => {
    const { container, cleanup } = renderTooltip();
    const button = container.querySelector("button") as HTMLButtonElement;
    act(() => { button.click(); });
    expect(container.querySelector('[role="tooltip"]')).not.toBeNull();
    act(() => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });
    expect(container.querySelector('[role="tooltip"]')).toBeNull();
    cleanup();
  });
});
