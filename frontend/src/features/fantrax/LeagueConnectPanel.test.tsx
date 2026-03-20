import React from "react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { LeagueConnectPanel } from "./LeagueConnectPanel";
import type { UseFantraxLeagueResult } from "../../hooks/useFantraxLeague";

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

function baseFanTrax(overrides: Partial<UseFantraxLeagueResult> = {}): UseFantraxLeagueResult {
  return {
    leagueId: "",
    leagueData: null,
    loading: false,
    error: null,
    selectedTeamId: null,
    rosterPlayerKeys: new Set<string>(),
    suggestedSettings: null,
    connectLeague: vi.fn(),
    selectTeam: vi.fn(),
    disconnect: vi.fn(),
    applyLeagueSettings: vi.fn(),
    ...overrides,
  };
}

describe("LeagueConnectPanel", () => {
  it("is exported", () => {
    expect(LeagueConnectPanel).toBeTruthy();
  });

  it("renders section title", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(LeagueConnectPanel, { fantrax: baseFanTrax() , onApplySettings: vi.fn() })
    );
    expect(container.textContent).toContain("Fantrax League");
    cleanup();
  });

  it("starts expanded when no leagueId", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(LeagueConnectPanel, { fantrax: baseFanTrax() , onApplySettings: vi.fn() })
    );
    expect(container.textContent).toContain("Paste your Fantrax League ID");
    cleanup();
  });

  it("collapses when toggle button is clicked", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(LeagueConnectPanel, { fantrax: baseFanTrax() , onApplySettings: vi.fn() })
    );
    const toggleBtn = container.querySelector(".fantrax-toggle-btn") as HTMLButtonElement;
    act(() => { toggleBtn.click(); });
    expect(container.textContent).not.toContain("Paste your Fantrax League ID");
    cleanup();
  });

  it("disables connect button when input is empty", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(LeagueConnectPanel, { fantrax: baseFanTrax() , onApplySettings: vi.fn() })
    );
    const connectBtn = container.querySelector(".fantrax-connect-btn") as HTMLButtonElement;
    expect(connectBtn.disabled).toBe(true);
    cleanup();
  });

  it("shows error message when present", () => {
    const { container, cleanup } = renderToContainer(
      React.createElement(LeagueConnectPanel, {
        fantrax: baseFanTrax({ error: "Network error" }),
        onApplySettings: vi.fn(),
      })
    );
    expect(container.textContent).toContain("Network error");
    cleanup();
  });

  it("renders connected state with league data", () => {
    const fantrax = baseFanTrax({
      leagueId: "abc123",
      // UseFantraxLeagueResult.leagueData is typed as FantraxLeagueData | null (not exported)
      // Structural typing matches when all required fields are present
      leagueData: {
        league_id: "abc123",
        league_name: "Test League",
        team_count: 12,
        scoring_type: "roto",
        scoring_categories: [] as string[],
        roster_positions: [] as string[],
        teams: [
          { team_id: "t1", team_name: "Team A", player_count: 25 },
          { team_id: "t2", team_name: "Team B", player_count: 22 },
        ],
      },
    });
    const { container, cleanup } = renderToContainer(
      React.createElement(LeagueConnectPanel, { fantrax, onApplySettings: vi.fn() })
    );
    // Initially collapsed since leagueId is set
    const toggleBtn = container.querySelector(".fantrax-toggle-btn") as HTMLButtonElement;
    act(() => { toggleBtn.click(); });
    expect(container.textContent).toContain("Test League");
    expect(container.textContent).toContain("12 teams");
    expect(container.textContent).toContain("Roto");
    cleanup();
  });

  it("renders import warnings when suggested settings include them", () => {
    const fantrax = baseFanTrax({
      leagueId: "abc123",
      leagueData: {
        league_id: "abc123",
        league_name: "Test League",
        team_count: 12,
        scoring_type: "points",
        scoring_categories: [] as string[],
        roster_positions: [] as string[],
        teams: [{ team_id: "t1", team_name: "Team A", player_count: 25 }],
      },
      suggestedSettings: {
        teams: 12,
        scoring_mode: "points",
        roto_categories: {},
        roster_slots: {},
        points_scoring: {},
        bench: 10,
        minors: 0,
        ir: 4,
        keeper_limit: 7,
        points_valuation_mode: "weekly_h2h",
        weekly_starts_cap: 12,
        allow_same_day_starts_overflow: true,
        weekly_acquisition_cap: 7,
        import_warnings: ["Review final-day starts overflow manually."],
      },
    });
    const { container, cleanup } = renderToContainer(
      React.createElement(LeagueConnectPanel, { fantrax, onApplySettings: vi.fn() })
    );
    const toggleBtn = container.querySelector(".fantrax-toggle-btn") as HTMLButtonElement;
    act(() => { toggleBtn.click(); });
    expect(container.textContent).toContain("Import warnings:");
    expect(container.textContent).toContain("Review final-day starts overflow manually.");
    cleanup();
  });

  it("shows calibrated weekly points guidance for Fantrax points imports", () => {
    const fantrax = baseFanTrax({
      leagueId: "abc123",
      leagueData: {
        league_id: "abc123",
        league_name: "Test League",
        team_count: 12,
        scoring_type: "points",
        scoring_categories: [] as string[],
        roster_positions: [] as string[],
        teams: [{ team_id: "t1", team_name: "Team A", player_count: 25 }],
      },
      suggestedSettings: {
        teams: 12,
        scoring_mode: "points",
        roto_categories: {},
        roster_slots: {},
        points_scoring: {},
        bench: 10,
        minors: 0,
        ir: 4,
        keeper_limit: 7,
        points_valuation_mode: "weekly_h2h",
        weekly_starts_cap: 12,
        allow_same_day_starts_overflow: true,
        weekly_acquisition_cap: 7,
        import_warnings: [],
      },
    });
    const { container, cleanup } = renderToContainer(
      React.createElement(LeagueConnectPanel, { fantrax, onApplySettings: vi.fn() })
    );
    const toggleBtn = container.querySelector(".fantrax-toggle-btn") as HTMLButtonElement;
    act(() => { toggleBtn.click(); });
    expect(container.textContent).toContain("Weekly H2H points uses a calibrated valuation model");
    expect(container.textContent).toContain("Review imported weekly caps and acquisition rules");
    cleanup();
  });
});
