import { describe, expect, it } from "vitest";

import { buildSortedWatchlistEntries, useProjectionWatchlistComposition } from "./useProjectionWatchlistComposition";
import type { PlayerWatchEntry } from "../../../app_state_storage";

describe("buildSortedWatchlistEntries", () => {
  it("sorts watchlist entries alphabetically by player", () => {
    const sorted = buildSortedWatchlistEntries({
      b: { key: "b", player: "Zeta", team: "", pos: "" },
      a: { key: "a", player: "Alpha", team: "", pos: "" },
      c: { key: "c", player: "Bravo", team: "", pos: "" },
    });

    expect(sorted.map(entry => entry.player)).toEqual(["Alpha", "Bravo", "Zeta"]);
  });

  it("limits entries to the requested size and ignores malformed rows", () => {
    const watchlist: Record<string, PlayerWatchEntry | null> = {};
    for (let idx = 0; idx < 60; idx += 1) {
      const key = `player-${String(idx).padStart(2, "0")}`;
      watchlist[key] = { key, player: `Player ${String(idx).padStart(2, "0")}`, team: "", pos: "" };
    }
    watchlist.invalid = null;

    const sorted = buildSortedWatchlistEntries(watchlist as Record<string, PlayerWatchEntry>, 40);
    expect(sorted.length).toBe(40);
    expect(sorted[0].player).toBe("Player 00");
    expect(sorted[39].player).toBe("Player 39");
  });

  it("returns empty array for null/undefined watchlist", () => {
    expect(buildSortedWatchlistEntries(null)).toEqual([]);
    expect(buildSortedWatchlistEntries(undefined)).toEqual([]);
  });

  it("returns empty array for empty watchlist", () => {
    expect(buildSortedWatchlistEntries({})).toEqual([]);
  });

  it("uses default limit of 40", () => {
    const watchlist: Record<string, PlayerWatchEntry> = {};
    for (let i = 0; i < 50; i++) {
      watchlist[`p${i}`] = { key: `p${i}`, player: `Player ${i}`, team: "", pos: "" };
    }
    expect(buildSortedWatchlistEntries(watchlist).length).toBe(40);
  });
});

describe("useProjectionWatchlistComposition", () => {
  it("is exported as a function", () => {
    expect(typeof useProjectionWatchlistComposition).toBe("function");
  });
});
