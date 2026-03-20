import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";

import { KeeperCalculator } from "./KeeperCalculator";
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
    Player: `Player ${String.fromCharCode(65 + i)}`,
    Team: "NYY",
    Pos: "1B",
    Age: 25 + i,
    DynastyValue: 10 - i,
    Type: "hitter",
  }));
}

beforeEach(() => {
  localStorage.removeItem("ff_keeper_roster");
});

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.removeItem("ff_keeper_roster");
});

describe("KeeperCalculator", () => {
  it("renders heading and close button", () => {
    const onClose = vi.fn();
    const { container, cleanup } = renderToContainer(
      <KeeperCalculator calculatorResults={makePlayers(5)} onClose={onClose} />
    );
    expect(container.querySelector("h3")!.textContent).toBe("Keeper Calculator");
    const closeBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Close")!;
    act(() => { closeBtn.click(); });
    expect(onClose).toHaveBeenCalled();
    cleanup();
  });

  it("shows loading message when no calculator results", () => {
    const { container, cleanup } = renderToContainer(
      <KeeperCalculator calculatorResults={[]} onClose={vi.fn()} />
    );
    expect(container.textContent).toContain("Loading player dynasty values");
    cleanup();
  });

  it("shows Open Calculator button when onOpenCalculator provided and no results", () => {
    const onOpenCalculator = vi.fn();
    const { container, cleanup } = renderToContainer(
      <KeeperCalculator calculatorResults={[]} onClose={vi.fn()} onOpenCalculator={onOpenCalculator} />
    );
    const btn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "Open Calculator")!;
    expect(btn).toBeDefined();
    act(() => { btn.click(); });
    expect(onOpenCalculator).toHaveBeenCalled();
    cleanup();
  });

  it("renders Add Player button when results available", () => {
    const { container, cleanup } = renderToContainer(
      <KeeperCalculator calculatorResults={makePlayers(3)} onClose={vi.fn()} />
    );
    const addBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "+ Add Player");
    expect(addBtn).toBeDefined();
    cleanup();
  });

  it("shows empty state message initially", () => {
    const { container, cleanup } = renderToContainer(
      <KeeperCalculator calculatorResults={makePlayers(3)} onClose={vi.fn()} />
    );
    expect(container.textContent).toContain("No keepers added yet");
    cleanup();
  });

  it("shows search input when Add Player is clicked", () => {
    const { container, cleanup } = renderToContainer(
      <KeeperCalculator calculatorResults={makePlayers(3)} onClose={vi.fn()} />
    );
    const addBtn = Array.from(container.querySelectorAll("button")).find(b => b.textContent === "+ Add Player")!;
    act(() => { addBtn.click(); });
    expect(container.querySelector(".keeper-search-input")).not.toBeNull();
    cleanup();
  });

  it("renders explanation note text", () => {
    const { container, cleanup } = renderToContainer(
      <KeeperCalculator calculatorResults={makePlayers(3)} onClose={vi.fn()} />
    );
    expect(container.textContent).toContain("Add keeper-eligible players");
    expect(container.textContent).toContain("Surplus");
    cleanup();
  });

  it("shows keeper-limit recommendation text when a limit is provided", () => {
    const { container, cleanup } = renderToContainer(
      <KeeperCalculator calculatorResults={makePlayers(5)} onClose={vi.fn()} keeperLimit={2} />
    );
    expect(container.textContent).toContain("Top 2 positive-surplus players are marked as keeps.");
    cleanup();
  });
});
