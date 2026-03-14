import React from "react";

export interface HeroSectionProps {
  meta: Record<string, unknown> | null;
  subscriptionActive: boolean;
  projectionSeasons: number;
  scrollToCalculator: () => void;
  setSection: (section: string) => void;
}

export const HeroSection = React.memo(function HeroSection({
  meta,
  subscriptionActive,
  projectionSeasons,
  scrollToCalculator,
  setSection,
}: HeroSectionProps): React.ReactElement {
  return (
    <>
      <div className="hero fade-up">
        <h1>The Only <em>20-Year</em><br />Dynasty Baseball Projections</h1>
        <p>Comprehensive player projections from 2026 through 2045. Browse the data, configure your league settings, and generate personalized dynasty rankings.</p>
        <div className="hero-actions fade-up fade-up-2">
          {!subscriptionActive && (
            <button className="hero-cta hero-cta-primary" onClick={scrollToCalculator}>
              Get Started Free
            </button>
          )}
          <button className="hero-cta hero-cta-secondary" onClick={() => setSection("methodology")}>
            See Methodology
          </button>
        </div>
        {meta && (
          <>
            <div className="hero-stats fade-up fade-up-2">
              <div className="hero-stat">
                <div className="number">{String(meta.total_hitters)}</div>
                <div className="label">Hitters</div>
              </div>
              <div className="hero-stat">
                <div className="number">{String(meta.total_pitchers)}</div>
                <div className="label">Pitchers</div>
              </div>
              <div className="hero-stat">
                <div className="number">{projectionSeasons}</div>
                <div className="label">Seasons</div>
              </div>
            </div>
            <div className="hero-proof fade-up fade-up-2">
              <span>Updated for the 2026 season</span>
            </div>
          </>
        )}
      </div>

      <section className="how-it-works fade-up" aria-labelledby="how-it-works-heading">
        <h2 id="how-it-works-heading" className="sr-only">How It Works</h2>
        <div className="how-it-works-steps">
          <div className="how-it-works-step">
            <div className="how-it-works-number">1</div>
            <h3>Browse Projections</h3>
            <p>Explore 20 years of MLB projections for hundreds of hitters and pitchers.</p>
          </div>
          <div className="how-it-works-step">
            <div className="how-it-works-number">2</div>
            <h3>Configure Your League</h3>
            <p>Set your roster slots, scoring categories, and league size to match your format.</p>
          </div>
          <div className="how-it-works-step">
            <div className="how-it-works-number">3</div>
            <h3>Generate Rankings</h3>
            <p>Run Monte Carlo simulations to produce custom dynasty values for every player.</p>
          </div>
        </div>
      </section>
    </>
  );
});
