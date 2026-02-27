import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { PlayerProfile } from "./PlayerProfile";

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

async function flushEffects(): Promise<void> {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

let previousActEnvironmentFlag: unknown;

beforeAll(() => {
  previousActEnvironmentFlag = (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT;
  (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true;
});

afterAll(() => {
  (globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = previousActEnvironmentFlag;
});

describe("PlayerProfile", () => {
  it("requests projection profile endpoint with calculator context and renders series rows", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        series: [
          { PlayerEntityKey: "alpha", Player: "Alpha", Team: "SEA", Pos: "OF", Year: 2027, PA: 610, HR: 29, RBI: 86, SB: 22, AVG: 0.279, OBP: 0.35, OPS: 0.84, DynastyValue: 56.1 },
          { PlayerEntityKey: "alpha", Player: "Alpha", Team: "SEA", Pos: "OF", Year: 2028, PA: 622, HR: 31, RBI: 91, SB: 20, AVG: 0.284, OBP: 0.357, OPS: 0.851, DynastyValue: 60.3 },
        ],
        career_totals: [],
      }),
    } as Response);

    const { container, cleanup } = renderToContainer(
      <PlayerProfile
        row={{ PlayerEntityKey: "alpha", Player: "Alpha", Team: "SEA", Pos: "OF", Type: "H" }}
        tab="bat"
        apiBase="https://example.com/"
        calculatorJobId="job-7"
        onClose={vi.fn()}
      />
    );

    await flushEffects();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const requestedUrl = new URL(String(fetchSpy.mock.calls[0][0]));
    expect(requestedUrl.pathname).toBe("/api/projections/profile/alpha");
    expect(requestedUrl.searchParams.get("dataset")).toBe("bat");
    expect(requestedUrl.searchParams.get("calculator_job_id")).toBe("job-7");
    expect(container.textContent).toContain("Dynasty Value trajectory");
    expect(container.textContent).toContain("2027");
    expect(container.textContent).toContain("2028");

    cleanup();
  });
});
