import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { ProjectionSectionTabs } from "./ProjectionSectionTabs";

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

describe("ProjectionSectionTabs", () => {
  it("is exported", () => {
    expect(ProjectionSectionTabs).toBeTruthy();
  });

  it("renders three tab buttons", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionSectionTabs, { tab: "all", onSelectTab: vi.fn() })
    );
    const buttons = container.querySelectorAll("button");
    expect(buttons.length).toBe(3);
    expect(buttons[0].textContent).toBe("All");
    expect(buttons[1].textContent).toBe("Hitters");
    expect(buttons[2].textContent).toBe("Pitchers");
    cleanup();
  });

  it("marks active tab with active class", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionSectionTabs, { tab: "bat", onSelectTab: vi.fn() })
    );
    const buttons = container.querySelectorAll("button");
    expect(buttons[1].classList.contains("active")).toBe(true);
    expect(buttons[0].classList.contains("active")).toBe(false);
    cleanup();
  });

  it("calls onSelectTab when tab is clicked", () => {
    const onSelectTab = vi.fn();
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionSectionTabs, { tab: "all", onSelectTab })
    );
    const buttons = container.querySelectorAll("button");
    act(() => { buttons[2].click(); });
    expect(onSelectTab).toHaveBeenCalledWith("pitch");
    cleanup();
  });

  it("sets aria-pressed on active tab", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionSectionTabs, { tab: "pitch", onSelectTab: vi.fn() })
    );
    const buttons = container.querySelectorAll("button");
    expect(buttons[2].getAttribute("aria-pressed")).toBe("true");
    expect(buttons[0].getAttribute("aria-pressed")).toBe("false");
    cleanup();
  });
});
