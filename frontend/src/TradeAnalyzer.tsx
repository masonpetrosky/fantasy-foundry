import React, { useCallback, useEffect, useMemo, useState } from "react";
import { fmt } from "./formatting_utils";
import { stablePlayerKeyFromRow } from "./app_state_storage";
import { trackEvent } from "./analytics";
import type { ProjectionRow } from "./app_state_storage";

const MAX_TRADE_PLAYERS = 6;

interface TradeParams {
  a: string[];
  b: string[];
}

function parseTradeParams(): TradeParams {
  if (typeof window === "undefined") return { a: [], b: [] };
  const params = new URLSearchParams(window.location.search);
  const a = (params.get("trade_a") || "").split(",").map(s => s.trim()).filter(Boolean);
  const b = (params.get("trade_b") || "").split(",").map(s => s.trim()).filter(Boolean);
  return { a, b };
}

function buildTradeUrl(sideA: ProjectionRow[], sideB: ProjectionRow[]): string {
  const base = `${window.location.origin}${window.location.pathname}`;
  const keysA = sideA.map(p => stablePlayerKeyFromRow(p)).join(",");
  const keysB = sideB.map(p => stablePlayerKeyFromRow(p)).join(",");
  const params = new URLSearchParams();
  if (keysA) params.set("trade_a", keysA);
  if (keysB) params.set("trade_b", keysB);
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

interface FairnessMeterProps {
  differential: number;
  totalValue: number;
}

function FairnessMeter({ differential, totalValue }: FairnessMeterProps): React.ReactElement {
  const ratio = totalValue > 0 ? Math.min(Math.abs(differential) / totalValue, 1) : 0;
  const pct = Math.round((1 - ratio) * 100);
  const label = pct >= 90 ? "Very Fair" : pct >= 70 ? "Fair" : pct >= 50 ? "Uneven" : "Lopsided";
  const color = pct >= 90 ? "var(--green)" : pct >= 70 ? "var(--accent)" : pct >= 50 ? "var(--text-secondary)" : "var(--red)";
  return (
    <div className="trade-fairness">
      <div className="trade-fairness-bar">
        <div className="trade-fairness-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="trade-fairness-label" style={{ color }}>{label} ({pct}%)</span>
    </div>
  );
}

interface TradeSideProps {
  label: string;
  players: ProjectionRow[];
  allPlayers: ProjectionRow[];
  searchTerm: string;
  onSearchChange: (value: string) => void;
  onAdd: (player: ProjectionRow) => void;
  onRemove: (key: string) => void;
}

function TradeSide({ label, players, allPlayers, searchTerm, onSearchChange, onAdd, onRemove }: TradeSideProps): React.ReactElement {
  const total = players.reduce((sum, p) => sum + (Number(p.DynastyValue) || 0), 0);
  const atLimit = players.length >= MAX_TRADE_PLAYERS;
  const filteredResults = useMemo(() => {
    if (!searchTerm || searchTerm.length < 2) return [];
    const term = searchTerm.toLowerCase();
    const addedKeys = new Set(players.map(p => stablePlayerKeyFromRow(p)));
    return allPlayers
      .filter(p => {
        const key = stablePlayerKeyFromRow(p);
        if (addedKeys.has(key)) return false;
        const name = String(p.Player || "").toLowerCase();
        return name.includes(term);
      })
      .slice(0, 8);
  }, [searchTerm, allPlayers, players]);

  return (
    <div className="trade-side">
      <h3>
        {label}
        <span className="trade-side-counter">{players.length}/{MAX_TRADE_PLAYERS}</span>
      </h3>
      {atLimit ? (
        <p className="trade-limit-notice">Player limit reached.</p>
      ) : (
        <div className="trade-search-wrap">
          <input
            type="text"
            placeholder="Search player to add..."
            value={searchTerm}
            onChange={e => onSearchChange(e.target.value)}
            className="trade-search-input"
          />
          {filteredResults.length > 0 && (
            <ul className="trade-search-results">
              {filteredResults.map(p => {
                const key = stablePlayerKeyFromRow(p);
                return (
                  <li key={key}>
                    <button type="button" onClick={() => onAdd(p)}>
                      <span className="trade-result-name">{p.Player}</span>
                      <span className="trade-result-meta">{p.Pos || "\u2014"} \u00b7 {fmt(p.DynastyValue, 2)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
      <div className="trade-players">
        {players.map(p => {
          const key = stablePlayerKeyFromRow(p);
          return (
            <div className="trade-player-card" key={key}>
              <div className="trade-player-info">
                <strong>{p.Player}</strong>
                <span>{(p.Team as string) || "\u2014"} \u00b7 {p.Pos || "\u2014"} \u00b7 Age {fmt(p.Age, 0)}</span>
              </div>
              <div className="trade-player-value">
                <span className={Number(p.DynastyValue) >= 0 ? "value-positive" : "value-negative"}>
                  {fmt(p.DynastyValue, 2)}
                </span>
                <button type="button" className="inline-btn" onClick={() => onRemove(key)}>Remove</button>
              </div>
            </div>
          );
        })}
        {players.length === 0 && <p className="trade-empty">No players added yet.</p>}
      </div>
      <div className="trade-side-total">
        <span>Total Dynasty Value</span>
        <strong className={total >= 0 ? "value-positive" : "value-negative"}>{fmt(total, 2)}</strong>
      </div>
    </div>
  );
}

interface TradeAnalyzerProps {
  calculatorResults: ProjectionRow[] | null;
  onClose?: (() => void) | null;
  onOpenCalculator?: () => void;
}

export function TradeAnalyzer({ calculatorResults, onClose, onOpenCalculator }: TradeAnalyzerProps): React.ReactElement {
  const allPlayers = useMemo(() => {
    if (!calculatorResults || !Array.isArray(calculatorResults)) return [];
    return calculatorResults.filter(r => r.Player && r.DynastyValue != null);
  }, [calculatorResults]);

  const [sideA, setSideA] = useState<ProjectionRow[]>([]);
  const [sideB, setSideB] = useState<ProjectionRow[]>([]);
  const [searchA, setSearchA] = useState("");
  const [searchB, setSearchB] = useState("");

  // Hydrate from URL params on mount
  useEffect(() => {
    if (allPlayers.length === 0) return;
    const { a, b } = parseTradeParams();
    if (a.length === 0 && b.length === 0) return;
    const playerByKey = new Map(allPlayers.map(p => [stablePlayerKeyFromRow(p), p]));
    setSideA(a.map(k => playerByKey.get(k)).filter((p): p is ProjectionRow => p != null).slice(0, MAX_TRADE_PLAYERS));
    setSideB(b.map(k => playerByKey.get(k)).filter((p): p is ProjectionRow => p != null).slice(0, MAX_TRADE_PLAYERS));
  }, [allPlayers]);

  const addToSide = useCallback((setter: React.Dispatch<React.SetStateAction<ProjectionRow[]>>, setSearch: React.Dispatch<React.SetStateAction<string>>) => (player: ProjectionRow): void => {
    setter(prev => [...prev, player]);
    setSearch("");
  }, []);

  const removeFromSide = useCallback((setter: React.Dispatch<React.SetStateAction<ProjectionRow[]>>) => (key: string): void => {
    setter(prev => prev.filter(p => stablePlayerKeyFromRow(p) !== key));
  }, []);

  const totalA = sideA.reduce((s, p) => s + (Number(p.DynastyValue) || 0), 0);
  const totalB = sideB.reduce((s, p) => s + (Number(p.DynastyValue) || 0), 0);
  const differential = totalA - totalB;
  const totalValue = Math.max(Math.abs(totalA) + Math.abs(totalB), 0.01);

  const usedKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const p of sideA) keys.add(stablePlayerKeyFromRow(p));
    for (const p of sideB) keys.add(stablePlayerKeyFromRow(p));
    return keys;
  }, [sideA, sideB]);

  const availablePlayers = useMemo(() => {
    return allPlayers.filter(p => !usedKeys.has(stablePlayerKeyFromRow(p)));
  }, [allPlayers, usedKeys]);

  const handleShareTrade = useCallback((): void => {
    const url = buildTradeUrl(sideA, sideB);
    if (navigator.clipboard) {
      navigator.clipboard.writeText(url).catch(() => {});
    }
    window.history.replaceState(null, "", url);
    trackEvent("ff_trade_share", { side_a_count: sideA.length, side_b_count: sideB.length });
  }, [sideA, sideB]);

  if (allPlayers.length === 0) {
    return (
      <div className="trade-analyzer">
        <div className="trade-analyzer-header">
          <h2>Trade Analyzer</h2>
          {onClose && <button type="button" className="inline-btn" onClick={onClose}>Close</button>}
        </div>
        <p className="trade-empty">
          Run the dynasty calculator first to generate player values for trade analysis.
          {onOpenCalculator && (
            <>{" "}<button type="button" className="inline-btn" onClick={onOpenCalculator}>Open Calculator</button></>
          )}
        </p>
      </div>
    );
  }

  return (
    <div className="trade-analyzer">
      <div className="trade-analyzer-header">
        <h2>Trade Analyzer</h2>
        <div className="trade-analyzer-actions">
          {(sideA.length > 0 || sideB.length > 0) && (
            <button type="button" className="inline-btn" onClick={handleShareTrade}>
              Share Trade
            </button>
          )}
          {onClose && <button type="button" className="inline-btn" onClick={onClose}>Close</button>}
        </div>
      </div>

      {(sideA.length > 0 || sideB.length > 0) && (
        <div className="trade-summary">
          <FairnessMeter differential={differential} totalValue={totalValue} />
          <div className="trade-differential">
            {Math.abs(differential) < 0.01
              ? "Perfectly even trade"
              : `Side A gets ${fmt(Math.abs(differential), 2)} more dynasty value`}
          </div>
        </div>
      )}

      <div className="trade-columns">
        <TradeSide
          label="Side A"
          players={sideA}
          allPlayers={availablePlayers}
          searchTerm={searchA}
          onSearchChange={setSearchA}
          onAdd={addToSide(setSideA, setSearchA)}
          onRemove={removeFromSide(setSideA)}
        />
        <TradeSide
          label="Side B"
          players={sideB}
          allPlayers={availablePlayers}
          searchTerm={searchB}
          onSearchChange={setSearchB}
          onAdd={addToSide(setSideB, setSearchB)}
          onRemove={removeFromSide(setSideB)}
        />
      </div>
    </div>
  );
}
