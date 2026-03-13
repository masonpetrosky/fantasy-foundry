import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { MobileCalculatorSheet } from "./MobileCalculatorSheet";

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

describe("MobileCalculatorSheet", () => {
  const baseProps = {
    isOpen: false,
    onClose: vi.fn(),
    sheetRef: { current: null },
    dragHandleProps: {},
    children: React.createElement("div", null, "Sheet content"),
  };

  it("is exported", () => {
    expect(MobileCalculatorSheet).toBeTruthy();
  });

  it("renders nothing when closed", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MobileCalculatorSheet, baseProps)
    );
    expect(container.querySelector(".mobile-sheet")).toBeNull();
    cleanup();
  });

  it("renders sheet when open", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MobileCalculatorSheet, { ...baseProps, isOpen: true })
    );
    expect(container.querySelector(".mobile-sheet")).not.toBeNull();
    expect(container.textContent).toContain("Sheet content");
    cleanup();
  });

  it("renders backdrop when open", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MobileCalculatorSheet, { ...baseProps, isOpen: true })
    );
    expect(container.querySelector(".mobile-sheet-backdrop")).not.toBeNull();
    cleanup();
  });

  it("renders close button", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MobileCalculatorSheet, { ...baseProps, isOpen: true })
    );
    const closeBtn = container.querySelector(".mobile-sheet-close");
    expect(closeBtn).not.toBeNull();
    expect(closeBtn?.textContent).toBe("Close");
    cleanup();
  });

  it("calls onClose when close button clicked", () => {
    const onClose = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(MobileCalculatorSheet, { ...baseProps, isOpen: true, onClose })
    );
    const closeBtn = container.querySelector(".mobile-sheet-close") as HTMLButtonElement;
    act(() => { closeBtn.click(); });
    expect(onClose).toHaveBeenCalled();
    cleanup();
  });

  it("calls onClose when backdrop clicked", () => {
    const onClose = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(MobileCalculatorSheet, { ...baseProps, isOpen: true, onClose })
    );
    const backdrop = container.querySelector(".mobile-sheet-backdrop") as HTMLDivElement;
    act(() => { backdrop.click(); });
    expect(onClose).toHaveBeenCalled();
    cleanup();
  });

  it("renders with dialog role and aria-modal", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(MobileCalculatorSheet, { ...baseProps, isOpen: true })
    );
    const sheet = container.querySelector(".mobile-sheet");
    expect(sheet?.getAttribute("role")).toBe("dialog");
    expect(sheet?.getAttribute("aria-modal")).toBe("true");
    cleanup();
  });
});
