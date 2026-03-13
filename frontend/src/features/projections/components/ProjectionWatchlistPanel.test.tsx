import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { ProjectionWatchlistPanel } from "./ProjectionWatchlistPanel";

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

describe("ProjectionWatchlistPanel", () => {
  it("is exported", () => {
    expect(ProjectionWatchlistPanel).toBeTruthy();
  });

  it("renders nothing when watchlistCount is 0", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionWatchlistPanel, {
        watchlistCount: 0,
        watchlist: {},
        removeWatchlistEntry: vi.fn(),
      })
    );
    expect(container.querySelector(".watchlist-panel")).toBeNull();
    cleanup();
  });

  it("renders watchlist entries", () => {
    const entries = [
      { key: "mlbam:1", player: "Player A", team: "SEA", pos: "OF" },
      { key: "mlbam:2", player: "Player B", team: "NYY", pos: "1B" },
    ];
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionWatchlistPanel, {
        watchlistCount: 2,
        watchlist: {},
        watchlistEntries: entries,
        removeWatchlistEntry: vi.fn(),
      })
    );
    expect(container.querySelector(".watchlist-panel")).not.toBeNull();
    expect(container.textContent).toContain("Player A");
    expect(container.textContent).toContain("Player B");
    expect(container.textContent).toContain("2 players");
    cleanup();
  });

  it("calls removeWatchlistEntry when remove button clicked", () => {
    const remove = vi.fn();
    const entries = [{ key: "mlbam:1", player: "Player A", team: "SEA", pos: "OF" }];
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionWatchlistPanel, {
        watchlistCount: 1,
        watchlist: {},
        watchlistEntries: entries,
        removeWatchlistEntry: remove,
      })
    );
    const removeBtn = container.querySelector('[aria-label="Remove Player A"]') as HTMLButtonElement;
    act(() => { removeBtn.click(); });
    expect(remove).toHaveBeenCalledWith("mlbam:1");
    cleanup();
  });

  it("has accessible region role", () => {
    const entries = [{ key: "mlbam:1", player: "Player A" }];
    const { container, cleanup } = renderToContainer(
      React.createElement(ProjectionWatchlistPanel, {
        watchlistCount: 1,
        watchlist: {},
        watchlistEntries: entries,
        removeWatchlistEntry: vi.fn(),
      })
    );
    const panel = container.querySelector('[role="region"]');
    expect(panel).not.toBeNull();
    expect(panel?.getAttribute("aria-label")).toBe("Saved watchlist");
    cleanup();
  });
});
