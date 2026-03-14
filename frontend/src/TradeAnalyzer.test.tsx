import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi, afterEach } from "vitest";

vi.mock("./analytics", () => ({
  trackEvent: vi.fn(),
}));

import { TradeAnalyzer } from "./TradeAnalyzer";
import type { ProjectionRow } from "./app_state_storage";

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

function makePlayers(count: number): ProjectionRow[] {
  return Array.from({ length: count }, (_, i) => ({
    Player: `Player ${i + 1}`,
    Team: "NYY",
    Pos: "1B",
    Age: 25 + i,
    DynastyValue: 10 - i,
    Type: "hitter",
  }));
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TradeAnalyzer", () => {
  it("renders Trade Analyzer heading", () => {
    const players = makePlayers(5);
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={players} />
    );
    expect(container.querySelector("h2")!.textContent).toBe("Trade Analyzer");
    cleanup();
  });

  it("shows loading message when no calculator results", () => {
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={null} />
    );
    expect(container.textContent).toContain("Loading player dynasty values");
    cleanup();
  });

  it("shows loading message when calculator results is empty array", () => {
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={[]} />
    );
    expect(container.textContent).toContain("Loading player dynasty values");
    cleanup();
  });

  it("renders close button when onClose provided", () => {
    const onClose = vi.fn();
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={makePlayers(3)} onClose={onClose} />
    );
    const closeBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Close");
    expect(closeBtn).toBeDefined();
    act(() => { closeBtn!.click(); });
    expect(onClose).toHaveBeenCalled();
    cleanup();
  });

  it("renders close button in loading state when onClose provided", () => {
    const onClose = vi.fn();
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={null} onClose={onClose} />
    );
    const closeBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Close");
    expect(closeBtn).toBeDefined();
    cleanup();
  });

  it("renders Open Calculator button when onOpenCalculator provided and no results", () => {
    const onOpenCalculator = vi.fn();
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={null} onOpenCalculator={onOpenCalculator} />
    );
    const calcBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Open Calculator");
    expect(calcBtn).toBeDefined();
    act(() => { calcBtn!.click(); });
    expect(onOpenCalculator).toHaveBeenCalled();
    cleanup();
  });

  it("renders two trade sides with labels", () => {
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={makePlayers(5)} />
    );
    const headings = Array.from(container.querySelectorAll("h3")).map(h => h.textContent);
    expect(headings.some(h => h?.includes("Side A"))).toBe(true);
    expect(headings.some(h => h?.includes("Side B"))).toBe(true);
    cleanup();
  });

  it("renders search inputs for adding players", () => {
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={makePlayers(5)} />
    );
    const inputs = container.querySelectorAll(".trade-search-input");
    expect(inputs.length).toBe(2);
    cleanup();
  });

  it("shows empty state text initially", () => {
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={makePlayers(5)} />
    );
    const emptyTexts = container.querySelectorAll(".trade-empty");
    expect(emptyTexts.length).toBe(2);
    expect(emptyTexts[0].textContent).toBe("No players added yet.");
    cleanup();
  });

  it("shows search results when typing in search input", () => {
    const players = makePlayers(5);
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={players} />
    );
    const input = container.querySelector(".trade-search-input") as HTMLInputElement;
    act(() => {
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype, "value"
      )!.set!;
      nativeInputValueSetter.call(input, "Player");
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    // Search results should appear for matching players
    cleanup();
  });

  it("displays total dynasty value for each side", () => {
    const { container, cleanup } = renderToContainer(
      <TradeAnalyzer calculatorResults={makePlayers(5)} />
    );
    const totals = container.querySelectorAll(".trade-side-total");
    expect(totals.length).toBe(2);
    expect(totals[0].textContent).toContain("Total Dynasty Value");
    cleanup();
  });
});
