import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import { resolveApiBase } from "./api_base";
import { useProjectionDeltas, DeltaMover } from "./hooks/useProjectionDeltas";

const API: string = resolveApiBase();

function DeltaArrow({ value }: { value: number }): React.ReactElement {
  if (value > 0) return <span className="value-positive">{"\u2191"} +{value.toFixed(2)}</span>;
  if (value < 0) return <span className="value-negative">{"\u2193"} {value.toFixed(2)}</span>;
  return <span>{"\u2014"}</span>;
}

function MoverRow({ mover }: { mover: DeltaMover }): React.ReactElement {
  return (
    <tr>
      <td className="player-name">
        <Link to={`/player/${mover.key}`}>{mover.player}</Link>
      </td>
      <td className="team">{mover.team}</td>
      <td className="pos">{mover.pos}</td>
      <td className="num">{mover.type}</td>
      <td className="num">
        <DeltaArrow value={mover.composite_delta} />
      </td>
      <td className="num" style={{ fontSize: "0.85em", color: "var(--text-muted)" }}>
        {Object.entries(mover.deltas)
          .filter(([, v]) => v !== 0)
          .map(([stat, v]) => `${stat}: ${v > 0 ? "+" : ""}${Number(v).toFixed(stat.length <= 3 && Math.abs(v) > 1 ? 1 : 3)}`)
          .join(", ")}
      </td>
    </tr>
  );
}

function MoverTable({ title, movers, emptyText }: { title: string; movers: DeltaMover[]; emptyText: string }): React.ReactElement {
  return (
    <section style={{ marginBottom: "2rem" }}>
      <h2>{title}</h2>
      {movers.length === 0 ? (
        <p style={{ color: "var(--text-muted)" }}>{emptyText}</p>
      ) : (
        <div className="projection-table-wrap" style={{ overflow: "auto" }}>
          <table className="projection-table">
            <thead>
              <tr>
                <th>Player</th>
                <th>Team</th>
                <th>Pos</th>
                <th>Type</th>
                <th>Change</th>
                <th>Stat Deltas</th>
              </tr>
            </thead>
            <tbody>
              {movers.map((m) => (
                <MoverRow key={m.key} mover={m} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export function MoversPage(): React.ReactElement {
  const { risers, fallers, hasPrevious, loading } = useProjectionDeltas(API);

  useEffect(() => {
    document.title = "This Week's Biggest Movers | Fantasy Foundry";
  }, []);

  return (
    <div className="player-page" style={{ maxWidth: 960, margin: "0 auto", padding: "1.5rem" }}>
      <nav style={{ marginBottom: "1rem" }}>
        <Link to="/" style={{ color: "var(--accent)" }}>{"\u2190"} Back to Projections</Link>
      </nav>
      <h1>This Week{"\u2019"}s Biggest Movers</h1>
      <p style={{ color: "var(--text-muted)", marginBottom: "1.5rem" }}>
        Week-over-week projection changes across all dynasty players. Updated with each projection refresh.
      </p>
      {loading ? (
        <p>Loading movers...</p>
      ) : !hasPrevious ? (
        <p style={{ color: "var(--text-muted)" }}>
          No previous projection data available yet. Movers will appear after the next projection update.
        </p>
      ) : (
        <>
          <MoverTable title="Risers" movers={risers} emptyText="No significant risers this week." />
          <MoverTable title="Fallers" movers={fallers} emptyText="No significant fallers this week." />
        </>
      )}
    </div>
  );
}
