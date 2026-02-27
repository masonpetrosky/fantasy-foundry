import React from "react";
import {
  POINTS_BATTING_FIELDS,
  POINTS_PITCHING_FIELDS,
} from "./dynasty_calculator_config";
import { CalcTooltip } from "./dynasty_calculator_tooltip.jsx";

export const PointsScoringForm = React.memo(function PointsScoringForm({
  settings,
  update,
  pointRulesCount,
  resetPointsScoringDefaults,
  tierLimits,
}) {
  const scoringLocked = tierLimits && !tierLimits.allowCustomCategories;
  return (
    <div className="calc-section">
      <p className="calc-section-title">Points Scoring Rules</p>
      <p className="calc-note">
        Edit category points below. Defaults align with a common H2H points format ({pointRulesCount} categories).
        {" "}
        <CalcTooltip label="Dynasty value context">A multi-year estimate of player worth that weighs present production, future seasons, and replacement context instead of only one season.</CalcTooltip>
      </p>
      {scoringLocked && (
        <p className="calc-note calc-pro-note">Custom scoring available with Pro</p>
      )}
      <p className="calc-subheading">Batting</p>
      <div className="form-row">
        {POINTS_BATTING_FIELDS.map(field => (
          <div className="form-group" key={field.key}>
            <label>{field.label}</label>
            <input
              type="number"
              step="0.1"
              value={settings[field.key]}
              onChange={e => update(field.key, e.target.value)}
              disabled={scoringLocked}
            />
          </div>
        ))}
      </div>

      <p className="calc-subheading">Pitching</p>
      <div className="form-row">
        {POINTS_PITCHING_FIELDS.map(field => (
          <div className="form-group" key={field.key}>
            <label>{field.label}</label>
            <input
              type="number"
              step="0.1"
              value={settings[field.key]}
              onChange={e => update(field.key, e.target.value)}
              disabled={scoringLocked}
            />
          </div>
        ))}
      </div>
      <button type="button" className="calc-secondary-btn" onClick={resetPointsScoringDefaults} disabled={scoringLocked}>
        Reset Recommended Points Scoring
      </button>
    </div>
  );
});
