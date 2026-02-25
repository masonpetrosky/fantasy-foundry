import React, { useEffect, useRef, useState } from "react";
import { formatCellValue } from "../../../formatting_utils.js";

const KEY_STAT_COLS_BAT = ["Year", "Team", "Pos", "PA", "HR", "RBI", "SB", "AVG", "OBP", "OPS", "DynastyValue"];
const KEY_STAT_COLS_PIT = ["Year", "Team", "Pos", "IP", "W", "K", "SV", "ERA", "WHIP", "DynastyValue"];

function SparkLine({ rows, col }) {
  const values = rows.map(r => Number(r[col] ?? 0)).filter(v => !isNaN(v));
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 200;
  const H = 44;
  const pad = 3;
  const points = values
    .map((v, i) => {
      const x = pad + (i / (values.length - 1)) * (W - pad * 2);
      const y = pad + (H - pad * 2) - ((v - min) / range) * (H - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      width={W}
      height={H}
      className="sparkline"
      aria-hidden="true"
    >
      <polyline
        points={points}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function PlayerProfile({ row, tab, apiBase, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const dialogRef = useRef(null);

  const playerKey = String(row?.PlayerEntityKey || row?.PlayerKey || "").trim();
  const playerName = String(row?.Player || "Player").trim();
  const isPitcherRow = row?.Type === "P";

  useEffect(() => {
    if (!playerKey) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    const dataset = tab === "bat" ? "bat" : tab === "pitch" ? "pitch" : "all";
    const url = `${apiBase}/api/projections/player/${encodeURIComponent(playerKey)}?dataset=${dataset}`;
    fetch(url)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(json => {
        setData(json.data || []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [apiBase, playerKey, tab]);

  useEffect(() => {
    const handler = e => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    dialogRef.current?.focus();
  }, []);

  const rows = data || [];
  const batRows = rows.filter(r => r.Type !== "P");
  const pitRows = rows.filter(r => r.Type === "P");
  const primaryRows = isPitcherRow
    ? (pitRows.length ? pitRows : rows)
    : (batRows.length ? batRows : rows);
  const primaryCols = isPitcherRow ? KEY_STAT_COLS_PIT : KEY_STAT_COLS_BAT;
  const dynastyRows = primaryRows.filter(r => r.DynastyValue != null);

  return (
    <div className="player-profile-backdrop" onClick={onClose}>
      <div
        className="player-profile-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={`Player profile: ${playerName}`}
        tabIndex={-1}
        ref={dialogRef}
        onClick={e => e.stopPropagation()}
      >
        <div className="player-profile-header">
          <div>
            <h2 className="player-profile-name">{playerName}</h2>
            <p className="player-profile-meta">
              {row.Team || "—"} · {row.Pos || "—"}
            </p>
          </div>
          <button
            type="button"
            className="inline-btn"
            onClick={onClose}
            aria-label="Close player profile"
          >
            Close
          </button>
        </div>

        {loading && <p className="player-profile-status">Loading…</p>}
        {error && (
          <p className="player-profile-status player-profile-error">
            Error: {error}
          </p>
        )}
        {!loading && !error && primaryRows.length === 0 && (
          <p className="player-profile-status">No year-by-year data available.</p>
        )}

        {!loading && !error && primaryRows.length > 0 && (
          <>
            {dynastyRows.length >= 2 && (
              <div className="player-profile-chart">
                <SparkLine rows={dynastyRows} col="DynastyValue" />
                <span className="player-profile-chart-label">Dynasty Value trajectory</span>
              </div>
            )}
            <div className="player-profile-table-wrap">
              <table className="player-profile-table">
                <thead>
                  <tr>
                    {primaryCols.map(col => (
                      <th
                        key={col}
                        className={col === "Year" || col === "Team" || col === "Pos" ? "" : "num"}
                      >
                        {col === "DynastyValue" ? "Dyn Value" : col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {primaryRows.map((r, idx) => (
                    <tr key={r.Year ?? idx}>
                      {primaryCols.map(col => (
                        <td
                          key={col}
                          className={col === "Year" || col === "Team" || col === "Pos" ? "" : "num"}
                        >
                          {formatCellValue(col, r[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
