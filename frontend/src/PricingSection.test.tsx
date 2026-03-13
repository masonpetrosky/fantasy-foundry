import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";

vi.mock("./premium", () => ({
  redirectToCheckout: vi.fn(() => Promise.resolve()),
}));
vi.mock("./analytics", () => ({
  trackEvent: vi.fn(),
}));

import { PricingSection } from "./PricingSection";

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

describe("PricingSection", () => {
  it("is exported", () => {
    expect(PricingSection).toBeTruthy();
  });

  it("renders pricing heading", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PricingSection, { authUser: null, subscription: null })
    );
    expect(container.querySelector("#pricing-heading")?.textContent).toBe("Pricing");
    cleanup();
  });

  it("renders Free and Pro cards", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PricingSection, { authUser: null, subscription: null })
    );
    const headings = Array.from(container.querySelectorAll("h3")).map(h => h.textContent);
    expect(headings).toContain("Free");
    expect(headings).toContain("Pro");
    cleanup();
  });

  it("shows upgrade button when not subscribed", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PricingSection, { authUser: null, subscription: null })
    );
    const btn = container.querySelector(".pricing-upgrade-btn") as HTMLButtonElement;
    expect(btn).not.toBeNull();
    expect(btn.textContent).toBe("Upgrade to Pro");
    cleanup();
  });

  it("shows current plan when subscribed", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PricingSection, {
        authUser: { email: "test@test.com" },
        subscription: { status: "active" },
      })
    );
    const currentLabels = Array.from(container.querySelectorAll(".pricing-current"));
    expect(currentLabels.length).toBeGreaterThan(0);
    cleanup();
  });

  it("toggles billing period", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PricingSection, { authUser: null, subscription: null })
    );
    const annualBtn = Array.from(container.querySelectorAll(".pricing-toggle-btn")).find(
      b => b.textContent === "Annual"
    ) as HTMLButtonElement;
    act(() => { annualBtn.click(); });
    expect(annualBtn.classList.contains("active")).toBe(true);
    expect(container.textContent).toContain("$29.99/yr");
    expect(container.textContent).toContain("Save ~50%");
    cleanup();
  });

  it("renders free tier features", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PricingSection, { authUser: null, subscription: null })
    );
    expect(container.textContent).toContain("5x5 Roto rankings");
    expect(container.textContent).toContain("300 simulations");
    cleanup();
  });

  it("renders pro tier features", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(PricingSection, { authUser: null, subscription: null })
    );
    expect(container.textContent).toContain("CSV & XLSX export");
    expect(container.textContent).toContain("Trade Analyzer");
    cleanup();
  });
});
