import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

// Mock react-router-dom
vi.mock("react-router-dom", () => ({
  Link: ({ to, children, ...rest }: { to: string; children: React.ReactNode; style?: React.CSSProperties }) =>
    React.createElement("a", { href: to, ...rest }, children),
}));

// Mock api_base
vi.mock("./api_base", () => ({
  resolveApiBase: () => "http://localhost:8000",
}));

// Mock useProjectionDeltas hook
const mockUseProjectionDeltas = vi.fn();
vi.mock("./hooks/useProjectionDeltas", () => ({
  useProjectionDeltas: (...args: unknown[]) => mockUseProjectionDeltas(...args),
  DeltaMover: {},
}));

import { MoversPage } from "./MoversPage";

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

describe("MoversPage", () => {
  beforeEach(() => {
    mockUseProjectionDeltas.mockReturnValue({
      risers: [],
      fallers: [],
      hasPrevious: false,
      loading: false,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is exported as a function", () => {
    expect(typeof MoversPage).toBe("function");
  });

  it("renders loading state", () => {
    mockUseProjectionDeltas.mockReturnValue({
      risers: [],
      fallers: [],
      hasPrevious: false,
      loading: true,
    });
    const { container, cleanup } = renderToContainer(React.createElement(MoversPage));
    expect(container.textContent).toContain("Loading movers...");
    cleanup();
  });

  it("renders no previous data message when not loading and hasPrevious is false", () => {
    mockUseProjectionDeltas.mockReturnValue({
      risers: [],
      fallers: [],
      hasPrevious: false,
      loading: false,
    });
    const { container, cleanup } = renderToContainer(React.createElement(MoversPage));
    expect(container.textContent).toContain("No previous projection data available yet");
    cleanup();
  });

  it("renders risers and fallers tables when data is available", () => {
    mockUseProjectionDeltas.mockReturnValue({
      risers: [
        { key: "p1", player: "Player One", team: "NYY", pos: "SS", type: "bat", deltas: { HR: 2 }, composite_delta: 1.5 },
      ],
      fallers: [
        { key: "p2", player: "Player Two", team: "LAD", pos: "SP", type: "pitch", deltas: { ERA: -0.5 }, composite_delta: -1.2 },
      ],
      hasPrevious: true,
      loading: false,
    });
    const { container, cleanup } = renderToContainer(React.createElement(MoversPage));
    expect(container.textContent).toContain("Risers");
    expect(container.textContent).toContain("Fallers");
    expect(container.textContent).toContain("Player One");
    expect(container.textContent).toContain("Player Two");
    cleanup();
  });

  it("renders page title", () => {
    const { container, cleanup } = renderToContainer(React.createElement(MoversPage));
    expect(container.textContent).toContain("Biggest Movers");
    cleanup();
  });

  it("renders back to projections link", () => {
    const { container, cleanup } = renderToContainer(React.createElement(MoversPage));
    const link = container.querySelector('a[href="/"]');
    expect(link).not.toBeNull();
    expect(link?.textContent).toContain("Back to Projections");
    cleanup();
  });

  it("renders empty table messages when hasPrevious but no movers", () => {
    mockUseProjectionDeltas.mockReturnValue({
      risers: [],
      fallers: [],
      hasPrevious: true,
      loading: false,
    });
    const { container, cleanup } = renderToContainer(React.createElement(MoversPage));
    expect(container.textContent).toContain("No significant risers this week");
    expect(container.textContent).toContain("No significant fallers this week");
    cleanup();
  });

  it("sets document title", () => {
    const { cleanup } = renderToContainer(React.createElement(MoversPage));
    expect(document.title).toContain("Biggest Movers");
    cleanup();
  });
});
