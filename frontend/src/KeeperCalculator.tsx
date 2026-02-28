import React, { useCallback, useMemo, useState } from "react";
import { fmt } from "./formatting_utils";
import { stablePlayerKeyFromRow } from "./app_state_storage";
import type { ProjectionRow } from "./app_state_storage";

const STORAGE_KEY = "ff_keeper_roster";
const MAX_KEEPERS = 40;

interface KeeperEntry {
  playerKey: string;
  playerName: string;
  team: string;
  pos: string;
  cost: number;
}

interface KeeperRow extends KeeperEntry {
  dynastyValue: number;
  surplus: number;
}

function loadKeeperRoster(): KeeperEntry[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (e: unknown): e is KeeperEntry =>
        typeof e === "object" && e !== null && "playerKey" in e && "cost" in e,
    );
  } catch {
    return [];
  }
}

function saveKeeperRoster(entries: KeeperEntry[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // localStorage full or unavailable
  }
}

interface KeeperCalculatorProps {
  calculatorResults: ProjectionRow[];
  onClose: () => void;
}

export function KeeperCalculator({
  calculatorResults,
  onClose,
}: KeeperCalculatorProps): React.ReactElement {
  const [entries, setEntries] = useState<KeeperEntry[]>(loadKeeperRoster);
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearch, setShowSearch] = useState(false);

  const playerLookup = useMemo(() => {
    const map = new Map<string, ProjectionRow>();
    for (const row of calculatorResults) {
      const key = stablePlayerKeyFromRow(row);
      if (key) map.set(key, row);
    }
    return map;
  }, [calculatorResults]);

  const searchResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return [];
    const entryKeys = new Set(entries.map(e => e.playerKey));
    return calculatorResults
      .filter(row => {
        const name = String(row.Player || "").toLowerCase();
        const key = stablePlayerKeyFromRow(row);
        return name.includes(q) && !entryKeys.has(key);
      })
      .sort((a, b) => Number(b.DynastyValue || 0) - Number(a.DynastyValue || 0))
      .slice(0, 8);
  }, [calculatorResults, searchQuery, entries]);

  const addPlayer = useCallback(
    (row: ProjectionRow) => {
      const key = stablePlayerKeyFromRow(row);
      setEntries(prev => {
        if (prev.length >= MAX_KEEPERS) return prev;
        if (prev.some(e => e.playerKey === key)) return prev;
        const next = [
          ...prev,
          {
            playerKey: key,
            playerName: String(row.Player || ""),
            team: String(row.Team || ""),
            pos: String(row.Pos || ""),
            cost: 0,
          },
        ];
        saveKeeperRoster(next);
        return next;
      });
      setSearchQuery("");
      setShowSearch(false);
    },
    [],
  );

  const removePlayer = useCallback((playerKey: string) => {
    setEntries(prev => {
      const next = prev.filter(e => e.playerKey !== playerKey);
      saveKeeperRoster(next);
      return next;
    });
  }, []);

  const updateCost = useCallback((playerKey: string, cost: number) => {
    setEntries(prev => {
      const next = prev.map(e =>
        e.playerKey === playerKey ? { ...e, cost } : e,
      );
      saveKeeperRoster(next);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => {
    setEntries([]);
    saveKeeperRoster([]);
  }, []);

  const keeperRows: KeeperRow[] = useMemo(() => {
    return entries
      .map(entry => {
        const row = playerLookup.get(entry.playerKey);
        const dynastyValue = Number(row?.DynastyValue || 0);
        const surplus = dynastyValue - entry.cost;
        return { ...entry, dynastyValue, surplus };
      })
      .sort((a, b) => b.surplus - a.surplus);
  }, [entries, playerLookup]);

  const hasResults = calculatorResults.length > 0;

  return (
    <div className="keeper-calculator">
      <div className="keeper-header">
        <h3>Keeper Calculator</h3>
        <button type="button" className="inline-btn" onClick={onClose}>
          Close
        </button>
      </div>

      {!hasResults && (
        <p className="keeper-note">
          Run the dynasty calculator first to populate dynasty values, then add
          your keepers here.
        </p>
      )}

      {hasResults && (
        <>
          <p className="keeper-note">
            Add keeper-eligible players and their cost (round or dollar amount).
            Surplus = Dynasty Value &minus; Cost. Keep players with the highest
            surplus.
          </p>

          <div className="keeper-add-row">
            {!showSearch && (
              <button
                type="button"
                className="calc-secondary-btn"
                onClick={() => setShowSearch(true)}
                disabled={entries.length >= MAX_KEEPERS}
              >
                + Add Player
              </button>
            )}
            {showSearch && (
              <div className="keeper-search-wrap">
                <input
                  type="text"
                  className="keeper-search-input"
                  placeholder="Search player name..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  autoFocus
                />
                <button
                  type="button"
                  className="inline-btn"
                  onClick={() => {
                    setShowSearch(false);
                    setSearchQuery("");
                  }}
                >
                  Cancel
                </button>
                {searchResults.length > 0 && (
                  <ul className="keeper-search-results">
                    {searchResults.map(row => {
                      const key = stablePlayerKeyFromRow(row);
                      return (
                        <li key={key}>
                          <button
                            type="button"
                            className="keeper-search-result-btn"
                            onClick={() => addPlayer(row)}
                          >
                            <span className="keeper-result-name">
                              {String(row.Player || "")}
                            </span>
                            <span className="keeper-result-meta">
                              {String(row.Team || "")} · {String(row.Pos || "")}
                              {" · DV: "}
                              {fmt(row.DynastyValue, 2)}
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
                {searchQuery.trim() && searchResults.length === 0 && (
                  <p className="keeper-no-results">No matching players found.</p>
                )}
              </div>
            )}
            {entries.length > 0 && (
              <button
                type="button"
                className="inline-btn"
                onClick={clearAll}
              >
                Clear All
              </button>
            )}
          </div>

          {keeperRows.length > 0 && (
            <div className="keeper-table-wrap">
              <table className="keeper-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    <th>Team</th>
                    <th>Pos</th>
                    <th className="num">Dynasty Value</th>
                    <th className="num">Cost</th>
                    <th className="num">Surplus</th>
                    <th className="num">Keep?</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {keeperRows.map(row => {
                    const recommendation =
                      row.surplus > 0
                        ? "Keep"
                        : row.surplus === 0
                          ? "Neutral"
                          : "Cut";
                    const recClass =
                      row.surplus > 0
                        ? "value-positive"
                        : row.surplus < 0
                          ? "value-negative"
                          : "";
                    const surplusClass =
                      row.surplus > 0
                        ? "value-positive"
                        : row.surplus < 0
                          ? "value-negative"
                          : "";
                    return (
                      <tr key={row.playerKey}>
                        <td className="player-name">{row.playerName}</td>
                        <td className="team">{row.team}</td>
                        <td className="pos">{row.pos}</td>
                        <td className="num">{fmt(row.dynastyValue, 2)}</td>
                        <td className="num">
                          <input
                            type="number"
                            className="keeper-cost-input"
                            value={row.cost || ""}
                            onChange={e => {
                              const val = e.target.value;
                              updateCost(
                                row.playerKey,
                                val === "" ? 0 : Number(val),
                              );
                            }}
                            min="0"
                            placeholder="0"
                          />
                        </td>
                        <td className={`num ${surplusClass}`}>
                          {fmt(row.surplus, 2)}
                        </td>
                        <td className={`num ${recClass}`}>{recommendation}</td>
                        <td>
                          <button
                            type="button"
                            className="inline-btn"
                            onClick={() => removePlayer(row.playerKey)}
                            aria-label={`Remove ${row.playerName}`}
                          >
                            &times;
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {keeperRows.length === 0 && (
            <p className="keeper-empty">
              No keepers added yet. Use the search above to add players.
            </p>
          )}
        </>
      )}
    </div>
  );
}
