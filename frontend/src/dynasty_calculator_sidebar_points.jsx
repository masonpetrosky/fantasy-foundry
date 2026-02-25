import React from "react";
import {
  POINTS_BATTING_FIELDS,
  POINTS_PITCHING_FIELDS,
} from "./dynasty_calculator_config.js";

export const PointsScoringForm = React.memo(function PointsScoringForm({
  settings,
  update,
  pointRulesCount,
  resetPointsScoringDefaults,
  jumpToGlossaryTerm,
}) {
  return (
    <div className="calc-section">
      <p className="calc-section-title">Points Scoring Rules</p>
      <p className="calc-note">
        Edit category points below. Defaults align with a common H2H points format ({pointRulesCount} categories).
        {" "}
        <button type="button" className="calc-method-link" onClick={() => jumpToGlossaryTerm("Dynasty Value")}>Dynasty value context</button>
      </p>
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
            />
          </div>
        ))}
      </div>
      <button type="button" className="calc-secondary-btn" onClick={resetPointsScoringDefaults}>
        Reset Recommended Points Scoring
      </button>
    </div>
  );
});
