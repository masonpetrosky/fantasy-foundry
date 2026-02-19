import { describe, expect, it } from "vitest";
import {
  RANK_COMPARE_ACTIONS,
  WATCHLIST_ACTIONS,
  rankCompareReducer,
  watchlistReducer,
} from "./rank_state_reducers.js";

describe("watchlistReducer", () => {
  const row = { PlayerEntityKey: "p1", Player: "Test Player", Team: "NYM", Pos: "OF" };

  it("adds a watch entry when toggling a missing row", () => {
    const next = watchlistReducer({}, {
      type: WATCHLIST_ACTIONS.TOGGLE_ROW,
      row,
    });
    expect(next.p1).toEqual({
      key: "p1",
      player: "Test Player",
      team: "NYM",
      pos: "OF",
    });
  });

  it("removes a watch entry when toggling an existing row", () => {
    const current = {
      p1: { key: "p1", player: "Test Player", team: "NYM", pos: "OF" },
    };
    const next = watchlistReducer(current, {
      type: WATCHLIST_ACTIONS.TOGGLE_ROW,
      row,
    });
    expect(next).toEqual({});
  });

  it("clears all entries", () => {
    const current = {
      p1: { key: "p1", player: "Test Player", team: "NYM", pos: "OF" },
    };
    expect(watchlistReducer(current, { type: WATCHLIST_ACTIONS.CLEAR })).toEqual({});
  });
});

describe("rankCompareReducer", () => {
  const row1 = { PlayerEntityKey: "p1", Player: "One" };
  const row2 = { PlayerEntityKey: "p2", Player: "Two" };

  it("adds and removes rows via toggle", () => {
    const added = rankCompareReducer({}, {
      type: RANK_COMPARE_ACTIONS.TOGGLE_ROW,
      row: row1,
    });
    expect(added).toEqual({ p1: row1 });

    const removed = rankCompareReducer(added, {
      type: RANK_COMPARE_ACTIONS.TOGGLE_ROW,
      row: row1,
    });
    expect(removed).toEqual({});
  });

  it("enforces max players when adding", () => {
    const current = { p1: row1 };
    const next = rankCompareReducer(current, {
      type: RANK_COMPARE_ACTIONS.TOGGLE_ROW,
      row: row2,
      maxPlayers: 1,
    });
    expect(next).toBe(current);
  });

  it("removes a key explicitly", () => {
    const current = { p1: row1, p2: row2 };
    const next = rankCompareReducer(current, {
      type: RANK_COMPARE_ACTIONS.REMOVE_KEY,
      key: "p1",
    });
    expect(next).toEqual({ p2: row2 });
  });

  it("syncs rows by key and refreshes existing row payloads", () => {
    const current = {
      p1: { PlayerEntityKey: "p1", Player: "Old One" },
      p2: { PlayerEntityKey: "p2", Player: "Old Two" },
    };
    const next = rankCompareReducer(current, {
      type: RANK_COMPARE_ACTIONS.SYNC_ROWS,
      rows: [
        { PlayerEntityKey: "p1", Player: "New One" },
        { PlayerEntityKey: "p3", Player: "Three" },
      ],
    });
    expect(next).toEqual({
      p1: { PlayerEntityKey: "p1", Player: "New One" },
    });
  });
});
