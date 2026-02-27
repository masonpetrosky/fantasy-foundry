import React from "react";
import {
  ROTO_HITTER_CATEGORY_FIELDS,
  ROTO_PITCHER_CATEGORY_FIELDS,
  coerceBooleanSetting,
} from "./dynasty_calculator_config.js";
import { CalcTooltip } from "./dynasty_calculator_tooltip.jsx";

export const RotoCategoriesForm = React.memo(function RotoCategoriesForm({
  settings,
  update,
  selectedRotoHitCategoryCount,
  selectedRotoPitchCategoryCount,
  resetRotoCategoryDefaults,
  tierLimits,
}) {
  const categoriesLocked = tierLimits && !tierLimits.allowCustomCategories;
  return (
    <div className="calc-section">
      <p className="calc-section-title">Roto Categories</p>
      <p className="calc-note">
        Choose which categories count toward value in roto mode ({selectedRotoHitCategoryCount} hitting, {selectedRotoPitchCategoryCount} pitching).
        {" "}
        <CalcTooltip label="How category impact works">How much a player&#39;s projected stats move a category relative to league context, roster slots, and innings constraints.</CalcTooltip>
      </p>
      {categoriesLocked && (
        <p className="calc-note calc-pro-note">Custom categories available with Pro</p>
      )}

      <p className="calc-subheading">Hitting</p>
      <div className="calc-checkbox-grid">
        {ROTO_HITTER_CATEGORY_FIELDS.map(field => (
          <label className="calc-checkbox-option" key={field.key}>
            <input
              type="checkbox"
              checked={coerceBooleanSetting(settings[field.key], field.defaultValue)}
              onChange={e => update(field.key, e.target.checked)}
              disabled={categoriesLocked}
            />
            <span>{field.label}</span>
          </label>
        ))}
      </div>

      <p className="calc-subheading">Pitching</p>
      <div className="calc-checkbox-grid">
        {ROTO_PITCHER_CATEGORY_FIELDS.map(field => (
          <label className="calc-checkbox-option" key={field.key}>
            <input
              type="checkbox"
              checked={coerceBooleanSetting(settings[field.key], field.defaultValue)}
              onChange={e => update(field.key, e.target.checked)}
              disabled={categoriesLocked}
            />
            <span>{field.label}</span>
          </label>
        ))}
      </div>
      <button type="button" className="calc-secondary-btn" onClick={resetRotoCategoryDefaults} disabled={categoriesLocked}>
        Reset 5x5 Categories
      </button>
    </div>
  );
});
