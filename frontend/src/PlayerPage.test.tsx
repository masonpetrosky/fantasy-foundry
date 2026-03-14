import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";

vi.mock("react-router-dom", () => ({
  useParams: () => ({ slug: "mike-trout" }),
  Link: ({ to, children }: { to: string; children: React.ReactNode }) =>
    React.createElement("a", { href: to }, children),
}));
vi.mock("./api_base", () => ({
  resolveApiBase: () => "http://test-api",
}));
vi.mock("./hooks/useFocusOnMount", () => ({
  useFocusOnMount: () => React.createRef(),
}));

import { PlayerPage } from "./PlayerPage";

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

afterEach(() => {
  vi.restoreAllMocks();
});

describe("PlayerPage", () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("shows loading state initially", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    const { container, cleanup } = renderToContainer(<PlayerPage />);
    expect(container.textContent).toContain("Loading player data");
    cleanup();
  });

  it("renders breadcrumb navigation", () => {
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as unknown as typeof fetch;
    const { container, cleanup } = renderToContainer(<PlayerPage />);
    const breadcrumb = container.querySelector(".player-page-breadcrumb");
    expect(breadcrumb).not.toBeNull();
    expect(breadcrumb!.textContent).toContain("Home");
    cleanup();
  });

  it("renders player data after successful fetch", async () => {
    const mockData = {
      series: [
        { Player: "Mike Trout", Team: "LAA", Pos: "OF", Age: 34, Year: 2026, Type: "H", DynastyValue: 15.5, PA: 550, HR: 30, RBI: 85, SB: 5, AVG: ".280", OBP: ".380", OPS: ".900" },
        { Player: "Mike Trout", Team: "LAA", Pos: "OF", Age: 35, Year: 2027, Type: "H", DynastyValue: 12.0, PA: 500, HR: 25, RBI: 75, SB: 3, AVG: ".270", OBP: ".370", OPS: ".870" },
      ],
    };
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockData) } as Response),
    ) as unknown as typeof fetch;
    const { container, cleanup } = renderToContainer(<PlayerPage />);
    await act(async () => {
      await new Promise(r => setTimeout(r, 20));
    });
    expect(container.querySelector("h1")!.textContent).toBe("Mike Trout");
    expect(container.textContent).toContain("LAA");
    expect(container.textContent).toContain("OF");
    expect(container.textContent).toContain("Year-by-Year Projections");
    cleanup();
  });

  it("shows error state on failed fetch", async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 404 } as Response),
    ) as unknown as typeof fetch;
    const { container, cleanup } = renderToContainer(<PlayerPage />);
    await act(async () => {
      await new Promise(r => setTimeout(r, 20));
    });
    expect(container.textContent).toContain("Error");
    cleanup();
  });

  it("shows no data message when player not found", async () => {
    const mockData = { series: [] };
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockData) } as Response),
    ) as unknown as typeof fetch;
    const { container, cleanup } = renderToContainer(<PlayerPage />);
    await act(async () => {
      await new Promise(r => setTimeout(r, 20));
    });
    expect(container.textContent).toContain("No projection data found");
    cleanup();
  });

  it("renders dynasty value trajectory when enough data points", async () => {
    const mockData = {
      series: [
        { Player: "Mike Trout", Team: "LAA", Pos: "OF", Age: 34, Year: 2026, Type: "H", DynastyValue: 15.5 },
        { Player: "Mike Trout", Team: "LAA", Pos: "OF", Age: 35, Year: 2027, Type: "H", DynastyValue: 12.0 },
      ],
    };
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockData) } as Response),
    ) as unknown as typeof fetch;
    const { container, cleanup } = renderToContainer(<PlayerPage />);
    await act(async () => {
      await new Promise(r => setTimeout(r, 20));
    });
    expect(container.querySelector(".player-page-chart")).not.toBeNull();
    expect(container.textContent).toContain("Dynasty Value Trajectory");
    cleanup();
  });

  it("renders pitcher stats for pitcher type", async () => {
    const mockData = {
      series: [
        { Player: "Test Pitcher", Team: "NYY", Pos: "SP", Age: 28, Year: 2026, Type: "P", DynastyValue: 8.0, IP: 180, W: 12, K: 200, SV: 0, ERA: "3.50", WHIP: "1.15" },
        { Player: "Test Pitcher", Team: "NYY", Pos: "SP", Age: 29, Year: 2027, Type: "P", DynastyValue: 7.0, IP: 170, W: 10, K: 190, SV: 0, ERA: "3.80", WHIP: "1.20" },
      ],
    };
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockData) } as Response),
    ) as unknown as typeof fetch;
    const { container, cleanup } = renderToContainer(<PlayerPage />);
    await act(async () => {
      await new Promise(r => setTimeout(r, 20));
    });
    const thTexts = Array.from(container.querySelectorAll("th")).map(th => th.textContent);
    expect(thTexts).toContain("IP");
    expect(thTexts).toContain("ERA");
    expect(thTexts).toContain("WHIP");
    cleanup();
  });
});
