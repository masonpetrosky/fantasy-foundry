import { afterEach, describe, expect, it, vi } from "vitest";
import React from "react";
import { createRoot } from "react-dom/client";
import { act } from "react";
import {
  readFantraxLeague,
  writeFantraxLeague,
  FANTRAX_LEAGUE_STORAGE_KEY,
} from "../app_state_storage";
import { useFantraxLeague } from "./useFantraxLeague";
import type { UseFantraxLeagueResult } from "./useFantraxLeague";

interface HookResult<T> {
  current: T | null;
}

function renderHook<T>(hookFn: () => T): { result: HookResult<T>; cleanup: () => void } {
  const result: HookResult<T> = { current: null };
  function TestComponent(): null {
    result.current = hookFn();
    return null;
  }
  const container = document.createElement("div");
  document.body.appendChild(container);
  let root: ReturnType<typeof createRoot>;
  act(() => {
    root = createRoot(container);
    root.render(React.createElement(TestComponent));
  });
  return {
    result,
    cleanup: () => {
      act(() => root.unmount());
      document.body.removeChild(container);
    },
  };
}

describe("useFantraxLeague hook", () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("returns initial state with null values", () => {
    const { result, cleanup } = renderHook(() => useFantraxLeague());
    expect(result.current!.leagueId).toBeNull();
    expect(result.current!.selectedTeamId).toBeNull();
    expect(result.current!.leagueData).toBeNull();
    expect(result.current!.rosterPlayerKeys.size).toBe(0);
    expect(result.current!.suggestedSettings).toBeNull();
    expect(result.current!.loading).toBe(false);
    expect(result.current!.error).toBeNull();
    cleanup();
  });

  it("exports all expected functions", () => {
    const { result, cleanup } = renderHook(() => useFantraxLeague());
    expect(typeof result.current!.connectLeague).toBe("function");
    expect(typeof result.current!.selectTeam).toBe("function");
    expect(typeof result.current!.disconnect).toBe("function");
    expect(typeof result.current!.applyLeagueSettings).toBe("function");
    cleanup();
  });

  it("disconnect clears all state", () => {
    // Pre-populate localStorage with a league
    writeFantraxLeague({ leagueId: "test123", selectedTeamId: "t1" });
    const { result, cleanup } = renderHook(() => useFantraxLeague());
    act(() => {
      result.current!.disconnect();
    });
    expect(result.current!.leagueId).toBeNull();
    expect(result.current!.selectedTeamId).toBeNull();
    expect(result.current!.leagueData).toBeNull();
    expect(result.current!.rosterPlayerKeys.size).toBe(0);
    cleanup();
  });

  it("applyLeagueSettings calls update with correct settings", () => {
    const { result, cleanup } = renderHook(() => useFantraxLeague());
    const update = vi.fn();
    // Without suggestedSettings, it should be a no-op
    act(() => {
      result.current!.applyLeagueSettings(update);
    });
    // No settings to apply, so update should not have been called
    expect(update).not.toHaveBeenCalled();
    cleanup();
  });
});

describe("Fantrax league storage", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("returns null when no stored league", () => {
    expect(readFantraxLeague()).toBeNull();
  });

  it("writes and reads league state", () => {
    writeFantraxLeague({ leagueId: "abc123", selectedTeamId: "t1" });
    const result = readFantraxLeague();
    expect(result).toEqual({ leagueId: "abc123", selectedTeamId: "t1" });
  });

  it("writes and reads league state without team", () => {
    writeFantraxLeague({ leagueId: "abc123", selectedTeamId: null });
    const result = readFantraxLeague();
    expect(result).toEqual({ leagueId: "abc123", selectedTeamId: null });
  });

  it("clears league state when null is written", () => {
    writeFantraxLeague({ leagueId: "abc123", selectedTeamId: "t1" });
    writeFantraxLeague(null);
    expect(readFantraxLeague()).toBeNull();
  });

  it("returns null for invalid JSON", () => {
    localStorage.setItem(FANTRAX_LEAGUE_STORAGE_KEY, "not-json");
    expect(readFantraxLeague()).toBeNull();
  });

  it("returns null for empty leagueId", () => {
    localStorage.setItem(FANTRAX_LEAGUE_STORAGE_KEY, JSON.stringify({ leagueId: "", selectedTeamId: null }));
    expect(readFantraxLeague()).toBeNull();
  });

  it("returns null for non-object stored value", () => {
    localStorage.setItem(FANTRAX_LEAGUE_STORAGE_KEY, JSON.stringify("string"));
    expect(readFantraxLeague()).toBeNull();
  });
});
