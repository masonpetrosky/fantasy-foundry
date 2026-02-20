export const PRIMARY_NAV_ITEMS = [
  { key: "projections", label: "Projections" },
  { key: "methodology", label: "Methodology" },
];

export const GLOSSARY_TERMS = [
  {
    term: "5x5 Roto",
    definition:
      "A scoring format that tracks five hitting and five pitching categories. The default here is R, RBI, HR, SB, AVG and W, K, SV, ERA, WHIP.",
  },
  {
    term: "Replacement Level",
    definition:
      "The baseline production expected from the last rosterable players in your league. Value is measured by how far a player clears that baseline.",
  },
  {
    term: "Category Impact",
    definition:
      "How much a player's projected stats move a category relative to league context, roster slots, and innings constraints.",
  },
  {
    term: "SGP (Standings Gain Points)",
    definition:
      "A way to convert raw stats into standings movement. One SGP estimates the amount of production needed to gain one place in a category.",
  },
  {
    term: "Dynasty Value",
    definition:
      "A multi-year estimate of player worth that weighs present production, future seasons, and risk instead of only one season.",
  },
  {
    term: "Positional Scarcity",
    definition:
      "Extra value assigned to players at positions where viable options are harder to find at replacement level.",
  },
  {
    term: "Surplus Value",
    definition:
      "The gap between a player's projected contribution and what the same roster spot would provide from replacement-level talent.",
  },
  {
    term: "Projection Window",
    definition:
      "The year range included in valuation. Fantasy Foundry provides projections from 2026 through 2045.",
  },
  {
    term: "Career Totals View",
    definition:
      "An aggregate view that rolls up projected output across all seasons in the projection window.",
  },
  {
    term: "Volatility",
    definition:
      "The uncertainty around a player's projection, often driven by role changes, health risk, and skill-variance categories.",
  },
  {
    term: "Playing-Time Risk",
    definition:
      "Risk that projected opportunities (PA, AB, or IP) are not reached due to performance, roster competition, or injuries.",
  },
  {
    term: "League Configuration",
    definition:
      "Your teams, roster slots, scoring categories, and innings rules. The calculator uses this setup to produce custom rankings.",
  },
];

export const METHODOLOGY_FAQS = [
  {
    question: "Do I need to use the default league setup?",
    answer:
      "No. Use the Dynasty Calculator section in Projections to customize teams, roster slots, categories, and scoring so values match your league.",
  },
  {
    question: "How should I interpret Dynasty Value?",
    answer:
      "Dynasty Value is a relative ranking score, not a dollar amount. Higher values indicate stronger long-term roster impact in your selected format.",
  },
  {
    question: "How are two-way players handled?",
    answer:
      "Two-way valuation follows your selected calculator option: sum hitting and pitching value, or keep the higher of the two sides.",
  },
  {
    question: "Why do rankings change when I edit league settings?",
    answer:
      "Value depends on scarcity and scoring context. Changing format, roster depth, or categories changes replacement level and category impact.",
  },
  {
    question: "Why might a player with strong stats rank lower than expected?",
    answer:
      "Multi-year value accounts for projection horizon, discounting, risk, and position/role context, not just one-season counting stats.",
  },
];
