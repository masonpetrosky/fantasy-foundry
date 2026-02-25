import { describe, expect, it } from "vitest";

import { buildSortedWatchlistEntries } from "./useProjectionWatchlistComposition.js";

describe("buildSortedWatchlistEntries", () => {
  it("sorts watchlist entries alphabetically by player", () => {
    const sorted = buildSortedWatchlistEntries({
      b: { key: "b", player: "Zeta" },
      a: { key: "a", player: "Alpha" },
      c: { key: "c", player: "Bravo" },
    });

    expect(sorted.map(entry => entry.player)).toEqual(["Alpha", "Bravo", "Zeta"]);
  });

  it("limits entries to the requested size and ignores malformed rows", () => {
    const watchlist = {};
    for (let idx = 0; idx < 60; idx += 1) {
      const key = `player-${String(idx).padStart(2, "0")}`;
      watchlist[key] = { key, player: `Player ${String(idx).padStart(2, "0")}` };
    }
    watchlist.invalid = null;

    const sorted = buildSortedWatchlistEntries(watchlist, 40);
    expect(sorted.length).toBe(40);
    expect(sorted[0].player).toBe("Player 00");
    expect(sorted[39].player).toBe("Player 39");
  });
});
