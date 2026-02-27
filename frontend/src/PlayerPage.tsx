import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { resolveApiBase } from "./api_base";
import { formatCellValue } from "./formatting_utils";

const API: string = resolveApiBase();

const KEY_STAT_COLS_BAT: readonly string[] = ["Year", "Team", "Pos", "PA", "HR", "RBI", "SB", "AVG", "OBP", "OPS", "DynastyValue"];
const KEY_STAT_COLS_PIT: readonly string[] = ["Year", "Team", "Pos", "IP", "W", "K", "SV", "ERA", "WHIP", "DynastyValue"];

interface PlayerRow {
  [key: string]: unknown;
  Player?: string;
  Team?: string;
  Pos?: string;
  Age?: number | string;
  Year?: number | string;
  Type?: string;
  DynastyValue?: number | string;
}

interface SparkLineProps {
  rows: PlayerRow[];
  col: string;
}

function SparkLine({ rows, col }: SparkLineProps): React.ReactElement | null {
  const values = rows.map(r => Number(r[col] ?? 0)).filter(v => !isNaN(v));
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 320;
  const H = 80;
  const pad = 4;
  const points = values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (W - pad * 2);
      const y = pad + (H - pad * 2) - ((v - min) / range) * (H - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="sparkline player-page-sparkline" aria-hidden="true">
      <polyline points={points} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

function parseRows(payload: unknown): PlayerRow[] {
  if (!payload || typeof payload !== "object") return [];
  const obj = payload as Record<string, unknown>;
  if (Array.isArray(obj.series)) return obj.series as PlayerRow[];
  if (Array.isArray(obj.data)) return obj.data as PlayerRow[];
  return [];
}

export function PlayerPage(): React.ReactElement {
  const { slug } = useParams<{ slug: string }>();
  const [data, setData] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    setError(null);
    const controller = new AbortController();
    const url = `${API}/api/projections/profile/${encodeURIComponent(slug)}?dataset=all`;
    fetch(url, { signal: controller.signal })
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((json: unknown) => {
        setData(json);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : String(err));
        setLoading(false);
      });
    return () => controller.abort();
  }, [slug]);

  const rows = parseRows(data);
  const playerName = rows.length > 0
    ? (rows[0].Player || slug)
    : ((data as Record<string, unknown>)?.matched_players as string[] | undefined)?.[0] || slug || "Player";
  const team = rows[0]?.Team || "";
  const pos = rows[0]?.Pos || "";
  const age = rows[0]?.Age;
  const isPitcher = rows.some(r => r.Type === "P") && !rows.some(r => r.Type !== "P");
  const primaryCols = isPitcher ? KEY_STAT_COLS_PIT : KEY_STAT_COLS_BAT;
  const dynastyRows = rows.filter(r => r.DynastyValue != null);

  // Dynamic document title
  useEffect(() => {
    if (playerName && playerName !== slug) {
      document.title = `${playerName} Dynasty Value & Projections | Fantasy Foundry`;
    }
    return () => {
      document.title = "Fantasy Foundry | 20-Year Dynasty Baseball Projections";
    };
  }, [playerName, slug]);

  return (
    <div className="player-page">
      <div className="container">
        <nav className="player-page-breadcrumb" aria-label="Breadcrumb">
          <Link to="/">Home</Link>
          <span aria-hidden="true"> / </span>
          <span>{playerName}</span>
        </nav>

        {loading && <p className="player-profile-status">Loading player data...</p>}
        {error && <p className="player-profile-status player-profile-error">Error: {error}</p>}
        {!loading && !error && rows.length === 0 && (
          <p className="player-profile-status">No projection data found for this player.</p>
        )}

        {!loading && !error && rows.length > 0 && (
          <>
            <header className="player-page-header">
              <h1>{playerName}</h1>
              <p className="player-page-meta">
                {team && <span>{team}</span>}
                {pos && <><span className="player-page-sep"> · </span><span>{pos}</span></>}
                {age != null && <><span className="player-page-sep"> · </span><span>Age {Math.round(Number(age))}</span></>}
              </p>
            </header>

            {dynastyRows.length >= 2 && (
              <section className="player-page-chart" aria-label="Dynasty value trajectory">
                <h2>Dynasty Value Trajectory</h2>
                <SparkLine rows={dynastyRows} col="DynastyValue" />
              </section>
            )}

            <section className="player-page-projections">
              <h2>Year-by-Year Projections</h2>
              <div className="player-profile-table-wrap">
                <table className="player-profile-table">
                  <thead>
                    <tr>
                      {primaryCols.map(col => (
                        <th key={col} className={col === "Year" || col === "Team" || col === "Pos" ? "" : "num"}>
                          {col === "DynastyValue" ? "Dyn Value" : col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, idx) => (
                      <tr key={r.Year ?? idx}>
                        {primaryCols.map(col => (
                          <td key={col} className={col === "Year" || col === "Team" || col === "Pos" ? "" : "num"}>
                            {formatCellValue(col, r[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
