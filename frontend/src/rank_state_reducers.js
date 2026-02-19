import { MAX_COMPARE_PLAYERS, playerWatchEntryFromRow, stablePlayerKeyFromRow } from "./app_state_storage.js";

export const WATCHLIST_ACTIONS = {
  CLEAR: "clear",
  TOGGLE_ROW: "toggle_row",
};

export const RANK_COMPARE_ACTIONS = {
  CLEAR: "clear",
  REMOVE_KEY: "remove_key",
  SYNC_ROWS: "sync_rows",
  TOGGLE_ROW: "toggle_row",
};

export function watchlistReducer(currentState, action) {
  const state = currentState && typeof currentState === "object" ? currentState : {};
  const type = String(action?.type || "");

  if (type === WATCHLIST_ACTIONS.CLEAR) {
    return {};
  }

  if (type === WATCHLIST_ACTIONS.TOGGLE_ROW) {
    const nextEntry = playerWatchEntryFromRow(action?.row);
    const key = String(nextEntry?.key || "").trim();
    if (!key) return state;
    if (state[key]) {
      const next = { ...state };
      delete next[key];
      return next;
    }
    return { ...state, [key]: nextEntry };
  }

  return state;
}

export function rankCompareReducer(currentState, action) {
  const state = currentState && typeof currentState === "object" ? currentState : {};
  const type = String(action?.type || "");

  if (type === RANK_COMPARE_ACTIONS.CLEAR) {
    return {};
  }

  if (type === RANK_COMPARE_ACTIONS.REMOVE_KEY) {
    const key = String(action?.key || "").trim();
    if (!key || !state[key]) return state;
    const next = { ...state };
    delete next[key];
    return next;
  }

  if (type === RANK_COMPARE_ACTIONS.TOGGLE_ROW) {
    const row = action?.row;
    const key = stablePlayerKeyFromRow(row);
    if (!key) return state;
    if (state[key]) {
      const next = { ...state };
      delete next[key];
      return next;
    }
    const maxPlayers = Number(action?.maxPlayers);
    const max = Number.isFinite(maxPlayers) && maxPlayers > 0 ? maxPlayers : MAX_COMPARE_PLAYERS;
    if (Object.keys(state).length >= max) return state;
    return { ...state, [key]: row };
  }

  if (type === RANK_COMPARE_ACTIONS.SYNC_ROWS) {
    const rows = Array.isArray(action?.rows) ? action.rows : [];
    const byKey = {};
    rows.forEach(row => {
      byKey[stablePlayerKeyFromRow(row)] = row;
    });
    const next = {};
    Object.keys(state).forEach(key => {
      if (byKey[key]) next[key] = byKey[key];
    });
    return next;
  }

  return state;
}
