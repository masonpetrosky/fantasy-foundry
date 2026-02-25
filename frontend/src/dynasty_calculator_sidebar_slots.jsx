import React from "react";
import {
  HITTER_SLOT_FIELDS,
  PITCHER_SLOT_FIELDS,
  SLOT_INPUT_MIN,
  SLOT_INPUT_MAX,
} from "./dynasty_calculator_config.js";

const ALL_SLOT_FIELDS = [...HITTER_SLOT_FIELDS, ...PITCHER_SLOT_FIELDS];
const SLOT_PAIRS = [];
for (let i = 0; i < ALL_SLOT_FIELDS.length; i += 2) {
  SLOT_PAIRS.push([ALL_SLOT_FIELDS[i], ALL_SLOT_FIELDS[i + 1]].filter(Boolean));
}

export const StarterSlotsForm = React.memo(function StarterSlotsForm({ settings, update }) {
  return (
    <div className="calc-section">
      <p className="calc-section-title">Starter Slots Per Team</p>
      {SLOT_PAIRS.map(pair => (
        <div className="form-row" key={pair.map(f => f.key).join("-")}>
          {pair.map(field => (
            <div className="form-group" key={field.key}>
              <label>{field.label}</label>
              <input
                type="number"
                value={settings[field.key]}
                onChange={e => update(field.key, e.target.value)}
                min={SLOT_INPUT_MIN}
                max={SLOT_INPUT_MAX}
              />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
});
