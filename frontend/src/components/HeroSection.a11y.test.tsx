import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, it, vi } from "vitest";
import { checkA11y } from "../test/a11y-helpers";
import { HeroSection } from "./HeroSection";

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

function defaultProps(): React.ComponentProps<typeof HeroSection> {
  return {
    meta: { total_hitters: 500, total_pitchers: 300 },
    subscriptionActive: false,
    projectionSeasons: 20,
    scrollToCalculator: vi.fn(),
    setSection: vi.fn(),
  };
}

describe("HeroSection a11y", () => {
  it("passes axe checks in default state", async () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(HeroSection, defaultProps()),
    );
    await checkA11y(container);
    cleanup();
  });

  it("passes axe checks with active subscription", async () => {
    const props = defaultProps();
    props.subscriptionActive = true;
    const { container, cleanup } = renderToContainer(
      React.createElement(HeroSection, props),
    );
    await checkA11y(container);
    cleanup();
  });

  it("passes axe checks without meta data", async () => {
    const props = defaultProps();
    props.meta = null;
    const { container, cleanup } = renderToContainer(
      React.createElement(HeroSection, props),
    );
    await checkA11y(container);
    cleanup();
  });
});
