import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { ProjectionOverlayBanner } from "./ProjectionOverlayBanner";

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

const baseProps = {
  hasCalculatorOverlay: false,
  resolvedCalculatorOverlayPlayerCount: 0,
  overlayStatusMeta: { isStale: false, chips: [] as string[] },
  showOverlayWhy: false,
  setShowOverlayWhy: vi.fn(),
  onClearCalculatorOverlay: null,
};

describe("ProjectionOverlayBanner", () => {
  it("is exported", () => {
    expect(ProjectionOverlayBanner).toBeTruthy();
  });

  it("renders nothing when no overlay", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionOverlayBanner, baseProps)
    );
    expect(container.querySelector(".projections-overlay-message")).toBeNull();
    cleanup();
  });

  it("renders banner when overlay is active", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionOverlayBanner, {
        ...baseProps,
        hasCalculatorOverlay: true,
        resolvedCalculatorOverlayPlayerCount: 150,
      })
    );
    expect(container.querySelector(".projections-overlay-message")).not.toBeNull();
    expect(container.textContent).toContain("150");
    cleanup();
  });

  it("shows chips when overlay summary parts present", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionOverlayBanner, {
        ...baseProps,
        hasCalculatorOverlay: true,
        resolvedCalculatorOverlayPlayerCount: 10,
        overlayStatusMeta: { isStale: false, chips: ["Roto mode", "10-year horizon"] },
      })
    );
    expect(container.textContent).toContain("Roto mode");
    expect(container.textContent).toContain("10-year horizon");
    cleanup();
  });

  it("shows stale warning when overlay is stale", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionOverlayBanner, {
        ...baseProps,
        hasCalculatorOverlay: true,
        resolvedCalculatorOverlayPlayerCount: 10,
        overlayStatusMeta: { isStale: true, chips: [] },
      })
    );
    expect(container.querySelector(".warning")).not.toBeNull();
    expect(container.textContent).toContain("older projections build");
    cleanup();
  });

  it("toggles why explanation on button click", () => {
    const setShowOverlayWhy = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionOverlayBanner, {
        ...baseProps,
        hasCalculatorOverlay: true,
        resolvedCalculatorOverlayPlayerCount: 10,
        setShowOverlayWhy,
      })
    );
    const whyBtn = container.querySelector(".overlay-why-btn") as HTMLButtonElement;
    act(() => { whyBtn.click(); });
    expect(setShowOverlayWhy).toHaveBeenCalled();
    cleanup();
  });

  it("renders clear button when handler provided", () => {
    const onClear = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionOverlayBanner, {
        ...baseProps,
        hasCalculatorOverlay: true,
        resolvedCalculatorOverlayPlayerCount: 10,
        onClearCalculatorOverlay: onClear,
      })
    );
    const clearBtn = Array.from(container.querySelectorAll("button")).find(
      b => b.textContent === "Clear applied values"
    );
    expect(clearBtn).not.toBeUndefined();
    act(() => { clearBtn!.click(); });
    expect(onClear).toHaveBeenCalled();
    cleanup();
  });
});
