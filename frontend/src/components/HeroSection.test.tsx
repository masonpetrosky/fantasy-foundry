import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi, afterEach } from "vitest";

import { HeroSection, HeroSectionProps } from "./HeroSection";

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

function makeProps(overrides: Partial<HeroSectionProps> = {}): HeroSectionProps {
  return {
    meta: null,
    subscriptionActive: false,
    projectionSeasons: 20,
    scrollToCalculator: vi.fn(),
    setSection: vi.fn(),
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("HeroSection", () => {
  it("renders hero heading", () => {
    const { container, cleanup } = renderToContainer(<HeroSection {...makeProps()} />);
    const h1 = container.querySelector("h1");
    expect(h1).not.toBeNull();
    expect(h1!.textContent).toContain("20-Year");
    expect(h1!.textContent).toContain("Dynasty Baseball Projections");
    cleanup();
  });

  it("renders description text", () => {
    const { container, cleanup } = renderToContainer(<HeroSection {...makeProps()} />);
    expect(container.textContent).toContain("Comprehensive player projections");
    cleanup();
  });

  it("renders Get Started Free button when not subscribed", () => {
    const scrollToCalculator = vi.fn();
    const { container, cleanup } = renderToContainer(
      <HeroSection {...makeProps({ subscriptionActive: false, scrollToCalculator })} />
    );
    const ctaBtn = container.querySelector(".hero-cta-primary") as HTMLButtonElement;
    expect(ctaBtn).not.toBeNull();
    expect(ctaBtn.textContent).toBe("Get Started Free");
    act(() => { ctaBtn.click(); });
    expect(scrollToCalculator).toHaveBeenCalled();
    cleanup();
  });

  it("hides Get Started Free button when subscribed", () => {
    const { container, cleanup } = renderToContainer(
      <HeroSection {...makeProps({ subscriptionActive: true })} />
    );
    expect(container.querySelector(".hero-cta-primary")).toBeNull();
    cleanup();
  });

  it("renders See Methodology button that calls setSection", () => {
    const setSection = vi.fn();
    const { container, cleanup } = renderToContainer(
      <HeroSection {...makeProps({ setSection })} />
    );
    const btn = container.querySelector(".hero-cta-secondary") as HTMLButtonElement;
    expect(btn.textContent).toBe("See Methodology");
    act(() => { btn.click(); });
    expect(setSection).toHaveBeenCalledWith("methodology");
    cleanup();
  });

  it("renders hero stats when meta is provided", () => {
    const { container, cleanup } = renderToContainer(
      <HeroSection {...makeProps({
        meta: { total_hitters: 500, total_pitchers: 300 },
        projectionSeasons: 20,
      })} />
    );
    expect(container.textContent).toContain("500");
    expect(container.textContent).toContain("Hitters");
    expect(container.textContent).toContain("300");
    expect(container.textContent).toContain("Pitchers");
    expect(container.textContent).toContain("20");
    expect(container.textContent).toContain("Seasons");
    cleanup();
  });

  it("does not render hero stats when meta is null", () => {
    const { container, cleanup } = renderToContainer(
      <HeroSection {...makeProps({ meta: null })} />
    );
    expect(container.querySelector(".hero-stats")).toBeNull();
    cleanup();
  });

  it("renders how it works section", () => {
    const { container, cleanup } = renderToContainer(<HeroSection {...makeProps()} />);
    expect(container.querySelector(".how-it-works")).not.toBeNull();
    expect(container.textContent).toContain("Browse Projections");
    expect(container.textContent).toContain("Configure Your League");
    expect(container.textContent).toContain("Generate Rankings");
    cleanup();
  });

  it("renders hero proof section when meta is present", () => {
    const { container, cleanup } = renderToContainer(
      <HeroSection {...makeProps({ meta: { total_hitters: 1, total_pitchers: 1 } })} />
    );
    expect(container.textContent).toContain("Updated for the 2026 season");
    cleanup();
  });
});
