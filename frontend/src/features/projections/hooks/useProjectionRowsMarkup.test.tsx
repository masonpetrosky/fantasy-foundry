import React from "react";
import { describe, expect, it, vi } from "vitest";
import { createRoot } from "react-dom/client";
import { act } from "react";
import { useProjectionRowsMarkup } from "./useProjectionRowsMarkup";
import type { UseProjectionRowsMarkupInput } from "./useProjectionRowsMarkup";
import type { ProjectionRow } from "../../../app_state_storage";

vi.mock("../../../dynasty_calculator_config", () => ({
  isRotoStatDynastyCol: vi.fn((col: string) => col.startsWith("Roto_")),
}));

function makeRow(overrides: Partial<ProjectionRow> = {}): ProjectionRow {
  return {
    PlayerEntityKey: "player1",
    Player: "Test Player",
    Team: "SEA",
    Pos: "OF",
    Year: 2027,
    HR: 30,
    AVG: 0.295,
    ERA: 3.45,
    DynastyValue: 5.2,
    ...overrides,
  };
}

function defaultInput(overrides: Partial<UseProjectionRowsMarkupInput> = {}): UseProjectionRowsMarkupInput {
  return {
    showCards: false,
    displayedPage: [],
    offset: 0,
    cols: ["Player", "Team", "Pos", "HR", "AVG"],
    colLabels: { Player: "Player", Team: "Team", Pos: "Pos", HR: "HR", AVG: "AVG" },
    projectionCardColumnsForRow: () => ["HR", "AVG"],
    isRowWatched: () => false,
    compareRowsByKey: {},
    compareRowsCount: 0,
    maxComparePlayers: 4,
    toggleRowWatch: vi.fn(),
    toggleCompareRow: vi.fn(),
    quickAddRow: vi.fn(),
    onViewProfile: null,
    ...overrides,
  };
}

interface HookResult<T> { current: T | null }

function renderHook<T>(hookFn: () => T): { result: HookResult<T>; cleanup: () => void } {
  const result: HookResult<T> = { current: null };
  function TestComponent(): null { result.current = hookFn(); return null; }
  const container = document.createElement("div");
  document.body.appendChild(container);
  let root: ReturnType<typeof createRoot>;
  act(() => { root = createRoot(container); root.render(React.createElement(TestComponent)); });
  return {
    result,
    cleanup: () => { act(() => root.unmount()); document.body.removeChild(container); },
  };
}

describe("useProjectionRowsMarkup", () => {
  it("is exported as a function", () => {
    expect(typeof useProjectionRowsMarkup).toBe("function");
  });

  it("returns empty arrays when displayedPage is empty", () => {
    const { result, cleanup } = renderHook(() => useProjectionRowsMarkup(defaultInput()));
    expect(result.current!.cardRowsMarkup).toEqual([]);
    expect(result.current!.tableRowsMarkup).toEqual([]);
    cleanup();
  });

  it("returns empty cardRowsMarkup when showCards is false", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [makeRow()],
      }))
    );
    expect(result.current!.cardRowsMarkup).toEqual([]);
    expect(result.current!.tableRowsMarkup.length).toBe(1);
    cleanup();
  });

  it("returns empty tableRowsMarkup when showCards is true", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: true,
        displayedPage: [makeRow()],
      }))
    );
    expect(result.current!.tableRowsMarkup).toEqual([]);
    expect(result.current!.cardRowsMarkup.length).toBe(1);
    cleanup();
  });

  it("generates table rows with correct number of rows", () => {
    const rows = [makeRow(), makeRow({ PlayerEntityKey: "player2", Player: "Player 2" })];
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: rows,
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(2);
    cleanup();
  });

  it("generates card rows with correct number", () => {
    const rows = [makeRow(), makeRow({ PlayerEntityKey: "player2", Player: "Player 2" })];
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: true,
        displayedPage: rows,
      }))
    );
    expect(result.current!.cardRowsMarkup.length).toBe(2);
    cleanup();
  });

  it("renders table rows with various column types", () => {
    const row = makeRow({
      AuctionDollars: 25,
      ProjectionDelta: 1.5,
      DynastyValue: 5.2,
      Value_2028: -3.1,
      Roto_HR: 2.5,
      ERA: 3.45,
      AVG: 0.295,
      HR: 30,
      Rank: 5,
      Year: 2027,
    });
    const cols = [
      "Player", "Team", "Pos",
      "AuctionDollars", "ProjectionDelta", "DynastyValue",
      "Value_2028", "Roto_HR", "ERA", "AVG", "HR", "Rank", "Year",
    ];
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [row],
        cols,
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(1);
    cleanup();
  });

  it("handles null AuctionDollars", () => {
    const row = makeRow({ AuctionDollars: null });
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [row],
        cols: ["AuctionDollars"],
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(1);
    cleanup();
  });

  it("handles ProjectionDelta zero and null and negative", () => {
    const row1 = makeRow({ ProjectionDelta: 0 });
    const row2 = makeRow({ ProjectionDelta: null, PlayerEntityKey: "p2" });
    const row3 = makeRow({ ProjectionDelta: -2.5, PlayerEntityKey: "p3" });
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [row1, row2, row3],
        cols: ["ProjectionDelta"],
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(3);
    cleanup();
  });

  it("handles DynastyValue with no_unique_match status", () => {
    const row = makeRow({ DynastyValue: null, DynastyMatchStatus: "no_unique_match" });
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [row],
        cols: ["DynastyValue"],
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(1);
    cleanup();
  });

  it("handles negative and zero DynastyValue", () => {
    const row1 = makeRow({ DynastyValue: -3.5 });
    const row2 = makeRow({ DynastyValue: 0, PlayerEntityKey: "p2" });
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [row1, row2],
        cols: ["DynastyValue"],
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(2);
    cleanup();
  });

  it("handles unknown column type with number and null values", () => {
    const row1 = makeRow({ CustomStat: 42.5 });
    const row2 = makeRow({ CustomStat: null, PlayerEntityKey: "p2" });
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [row1, row2],
        cols: ["CustomStat"],
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(2);
    cleanup();
  });

  it("renders cards with profile button when onViewProfile is set", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: true,
        displayedPage: [makeRow()],
        onViewProfile: vi.fn(),
      }))
    );
    expect(result.current!.cardRowsMarkup.length).toBe(1);
    cleanup();
  });

  it("handles watched and compared rows in card and table views", () => {
    const row = makeRow();
    const key = row.PlayerEntityKey || "player1";
    const { result: cardResult, cleanup: cardCleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: true,
        displayedPage: [row],
        isRowWatched: () => true,
        compareRowsByKey: { [key]: row },
        compareRowsCount: 1,
      }))
    );
    expect(cardResult.current!.cardRowsMarkup.length).toBe(1);
    cardCleanup();

    const { result: tableResult, cleanup: tableCleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [row],
        isRowWatched: () => true,
        compareRowsByKey: { [key]: row },
        compareRowsCount: 1,
        onViewProfile: vi.fn(),
      }))
    );
    expect(tableResult.current!.tableRowsMarkup.length).toBe(1);
    tableCleanup();
  });

  it("uses offset for row numbering", () => {
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [makeRow()],
        offset: 50,
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(1);
    cleanup();
  });

  it("handles Roto dynasty col with various values", () => {
    const row1 = makeRow({ Roto_HR: -1.5 });
    const row2 = makeRow({ Roto_HR: 0, PlayerEntityKey: "p2" });
    const row3 = makeRow({ Roto_HR: null, PlayerEntityKey: "p3" });
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [row1, row2, row3],
        cols: ["Roto_HR"],
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(3);
    cleanup();
  });

  it("handles Value_ col with NaN", () => {
    const row = makeRow({ Value_2028: "not-a-number" });
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [row],
        cols: ["Value_2028"],
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(1);
    cleanup();
  });

  it("handles card without Player name", () => {
    const row = makeRow({ Player: undefined });
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: true,
        displayedPage: [row],
      }))
    );
    expect(result.current!.cardRowsMarkup.length).toBe(1);
    cleanup();
  });

  it("handles empty AuctionDollars string", () => {
    const row = makeRow({ AuctionDollars: "" });
    const { result, cleanup } = renderHook(() =>
      useProjectionRowsMarkup(defaultInput({
        showCards: false,
        displayedPage: [row],
        cols: ["AuctionDollars"],
      }))
    );
    expect(result.current!.tableRowsMarkup.length).toBe(1);
    cleanup();
  });
});
