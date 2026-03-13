import { afterEach, describe, expect, it } from "vitest";
import {
  readFantraxLeague,
  writeFantraxLeague,
  FANTRAX_LEAGUE_STORAGE_KEY,
} from "../app_state_storage";

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
