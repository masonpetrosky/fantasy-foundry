import React from "react";
import { GLOSSARY_TERMS, METHODOLOGY_FAQS, glossaryTermAnchorId } from "./app_content";

export function MethodologySection(): React.ReactElement {
  return (
    <section className="methodology-stack" aria-labelledby="methodology-heading">
      <article className="methodology-card" aria-labelledby="methodology-heading">
        <h2 id="methodology-heading">Methodology</h2>
        <p>
          Dynasty values are deterministic from the projection file plus your calculator settings.
          Reusing the same inputs produces the same output.
        </p>
        <p><strong>Pipeline:</strong></p>
        <ol>
          <li>
            Import Bat/Pitch projections, normalize columns, and collapse duplicate player-year rows by
            averaging entries from the most recent projection date.
          </li>
          <li>
            Build valuation years from <code>start_year</code> and <code>horizon</code>, then compute
            per-year player value relative to slot eligibility and league replacement baselines.
          </li>
          <li>
            Aggregate yearly values into <code>RawDynastyValue</code> with discounting, then center at
            the replacement roster cutoff to produce <code>DynastyValue</code>. In very deep leagues where
            the normal cutoff collapses to raw value 0, the calculator applies a forced-roster fallback to
            separate the fringe, and can add a small minors-slot scarcity cost when zero-value MiLB stashes
            still tie at the cutoff.
          </li>
        </ol>
        <p><strong>Core equations:</strong></p>
        <ul>
          <li>
            <code>valuation_years = [start_year .. start_year + horizon - 1] intersect projection_years</code>
          </li>
          <li>
            <code>discount_factor(y) = discount ** (y - start_year)</code>
          </li>
          <li>
            <code>DynastyValue = RawDynastyValue - CenteringBaselineValue</code>
          </li>
          <li>
            Deep-roster fallback:
            {" "}
            <code>CenteringScore = RawDynastyValue</code> for positive raw values, otherwise
            {" "}
            <code>ForcedRosterValue = v_0 + discount ** gap * keep_or_drop(v_1...)</code>.
          </li>
          <li>
            Residual MiLB stash pricing:
            {" "}
            zero-value minor-eligible fringe players can receive a small negative slot-cost score based on
            ETA and projected future volume so the deep-league cutoff does not remain pinned at 0.
          </li>
        </ul>
        <p><strong>Roto mode (SGP) math:</strong></p>
        <ul>
          <li>
            SGP denominators come from Monte Carlo simulations of team standings:
            {" "}
            <code>SGP_denom(cat) = mean_adjacent_rank_gap(simulated_team_category_totals)</code>.
          </li>
          <li>
            For each eligible slot, value is the category delta vs replacement:
            {" "}
            <code>Value_y = sum(delta_cat / SGP_denom(cat))</code> (ERA/WHIP deltas are sign-reversed).
          </li>
          <li>
            Pitching totals apply innings rules before category deltas: <code>ip_max</code> is a hard cap on
            credited innings and <code>ip_min</code> can force qualification penalties.
          </li>
          <li>
            Multi-year value uses keep/drop optimization with stash rules:
            {" "}
            <code>F[i] = max(0, v_i + discount ** gap * F[i+1])</code>.
          </li>
          <li>
            Optional predictive controls (advanced settings) can switch SGP denominators to robust winsorized gaps,
            apply playing-time reliability scaling, age-risk adjustment, and blended replacement baselines.
            The shipped default also uses an internal softened depth blend for broad shared slots like <code>OF</code> and <code>P</code>.
          </li>
        </ul>
        <p><strong>Points mode math:</strong></p>
        <ul>
          <li>
            Hitting and pitching points are weighted sums:
            {" "}
            <code>hitter_points = sum(stat * pts_hit_*)</code>,
            {" "}
            <code>pitcher_points = sum(stat * pts_pit_*)</code>.
          </li>
          <li>
            Slot value is replacement-relative with start-year anchored baselines:
            {" "}
            <code>slot_value = player_points - replacement_points_for_slot</code>.
          </li>
          <li>
            Per-year points use a slot-constrained assignment so players compete for finite roster capacity.
          </li>
          <li>
            Season-total points mode uses in-season roster depth for replacement, and an optional
            {" "}
            <code>keeper_limit</code> can anchor the dynasty cutoff to shallow keeper pools instead of full roster depth.
          </li>
          <li>
            Weekly H2H points mode is a calibrated valuation path, not a day-by-day schedule simulator.
            It raises pitcher replacement baselines when weekly starts caps and acquisition caps make streamer production fungible.
          </li>
          <li>
            Final-day starts overflow can be modeled explicitly in weekly H2H mode, increasing the effective starts cap by a small calibrated amount.
          </li>
          <li>
            Two-way handling uses your setting: <code>sum</code> adds both sides, <code>max</code> keeps the higher side.
          </li>
          <li>
            Multi-year value uses keep/drop optimization:
            {" "}
            <code>F[i] = max(0, Value_i + discount ** gap * F[i+1])</code>.
          </li>
          <li>
            Points mode is deterministic and does not use Monte Carlo simulation. When set, <code>ip_max</code>
            applies as a hard annual innings budget; <code>ip_min</code> is not used in points mode.
          </li>
        </ul>
        <p className="methodology-note" style={{ marginBottom: 0 }}>
          Final values come directly from the valuation pipeline after projection averaging and league settings.
          Use the <strong>Dynasty Calculator</strong> section in Projections to run your exact league settings.
          {" "}
          Site baseline rankings default to 12-team 5x5 roto with 22 starters, 6 bench, 0 MiLB, 0 IL, a 20-year horizon,
          <code>two_way=sum</code>, prospect risk adjustment enabled, replacement blending on at <code>alpha=0.40</code>,
          and an internal OF/P replacement-depth blend at <code>alpha=0.33</code>.
          The default list is model-derived and
          benchmark-reviewed against external consensus to surface missing assumptions, but consensus is not used
          directly as a ranking input.
        </p>
      </article>

      <article className="methodology-card glossary-card" aria-labelledby="glossary-heading">
        <h2 id="glossary-heading" style={{ marginBottom: "10px" }}>Glossary</h2>
        <p className="glossary-intro">
          Quick definitions for terms used in projections, league settings, and dynasty valuation.
        </p>
        <dl className="glossary-list">
          {GLOSSARY_TERMS.map(entry => (
            <div key={entry.term} className="glossary-item">
              <dt id={glossaryTermAnchorId(entry.term)} tabIndex={-1}>{entry.term}</dt>
              <dd>{entry.definition}</dd>
            </div>
          ))}
        </dl>
      </article>

      <article className="methodology-card faq-card" aria-labelledby="faq-heading">
        <h2 id="faq-heading">FAQs</h2>
        <dl className="faq-list">
          {METHODOLOGY_FAQS.map(entry => (
            <div key={entry.question} className="faq-item">
              <dt>{entry.question}</dt>
              <dd>{entry.answer}</dd>
            </div>
          ))}
        </dl>
      </article>
    </section>
  );
}
