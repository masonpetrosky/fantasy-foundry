import React from "react";
import {
  POINTS_BATTING_FIELDS,
  POINTS_PITCHING_FIELDS,
  ROTO_HITTER_CATEGORY_FIELDS,
  ROTO_PITCHER_CATEGORY_FIELDS,
  SLOT_INPUT_MAX,
  SLOT_INPUT_MIN,
  coerceBooleanSetting,
} from "./dynasty_calculator_config.js";

export function DynastyCalculatorSidebar({
  meta,
  presets,
  settings,
  state,
  actions,
}) {
  const {
    hittersPerTeam,
    isPointsMode,
    lastRunTotal,
    loading,
    mainTableOverlayActive,
    pointRulesCount,
    presetName,
    pitchersPerTeam,
    reservePerTeam,
    selectedPresetName,
    selectedRotoHitCategoryCount,
    selectedRotoPitchCategoryCount,
    status,
    statusIsError,
    totalPlayersPerTeam,
    validationError,
    validationWarning,
  } = state;
  const {
    applyQuickStartAndRun,
    applyScoringSetup,
    clearAppliedValues,
    copyShareLink,
    deletePreset,
    loadPreset,
    reapplySetupDefaults,
    resetPointsScoringDefaults,
    resetRotoCategoryDefaults,
    run,
    savePreset,
    setPresetName,
    setSelectedPresetName,
    update,
  } = actions;

  return (
    <div className="calc-sidebar">
      <div className="calc-sidebar-header">
        <h3>League Settings</h3>
        <p className="calc-sidebar-intro">Configure format, roster depth, and scoring. Then apply custom dynasty values to the main projections table.</p>
      </div>

      <div className="calc-summary-grid">
        <div className="calc-summary-chip">
          <span>Setup</span>
          <strong>{isPointsMode ? "Points Focused" : "Roto Focused"}</strong>
        </div>
        <div className="calc-summary-chip">
          <span>Teams</span>
          <strong>{settings.teams}</strong>
        </div>
        <div className="calc-summary-chip">
          <span>Per-Team Starters</span>
          <strong>{hittersPerTeam} H / {pitchersPerTeam} P</strong>
        </div>
        <div className="calc-summary-chip">
          <span>Total Keeper Depth</span>
          <strong>{totalPlayersPerTeam} slots</strong>
        </div>
      </div>

      <div className="calc-section">
        <p className="calc-section-title">Quick Start</p>
        <p className="calc-note">Apply common league settings and run immediately.</p>
        <div className="calc-inline-actions">
          <button
            type="button"
            className="calc-secondary-btn"
            onClick={() => applyQuickStartAndRun("roto")}
            disabled={loading}
          >
            Run 12-Team 5x5 Roto
          </button>
          <button
            type="button"
            className="calc-secondary-btn"
            onClick={() => applyQuickStartAndRun("points")}
            disabled={loading}
          >
            Run 12-Team Points
          </button>
        </div>
      </div>

      <div className="calc-section">
        <p className="calc-section-title">Format</p>

        <div className="form-row">
          <div className="form-group">
            <label>Teams</label>
            <input type="number" value={settings.teams} onChange={e => update("teams", e.target.value)} min="2" max="30" />
          </div>
          <div className="form-group">
            <label>Start Year</label>
            <select value={settings.start_year} onChange={e => update("start_year", e.target.value)}>
              {meta.years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Horizon (yrs)</label>
            <input type="number" value={settings.horizon} onChange={e => update("horizon", e.target.value)} min="1" max="20" />
          </div>
          <div className="form-group">
            <label>
              Discount
              <span
                className="field-help"
                tabIndex={0}
                role="note"
                aria-label="Discount help"
                title="Applies a yearly value multiplier. Example: 0.94 means each future season is worth 94% of the previous season."
              >
                ?
              </span>
            </label>
            <input type="number" value={settings.discount} onChange={e => update("discount", e.target.value)} min="0.5" max="1" step="0.01" />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Setup</label>
            <select
              value={settings.scoring_mode}
              onChange={e => applyScoringSetup(e.target.value)}
            >
              <option value="roto">Roto Focused</option>
              <option value="points">Points Focused</option>
            </select>
          </div>
          <div className="form-group">
            <label>
              Two-Way Value
              <span
                className="field-help"
                tabIndex={0}
                role="note"
                aria-label="Two-Way Value help"
                title="Sum H + P combines both sides for two-way players. Best of H/P keeps whichever side grades higher."
              >
                ?
              </span>
            </label>
            <select value={settings.two_way} onChange={e => update("two_way", e.target.value)}>
              <option value="sum">Sum H + P</option>
              <option value="max">Best of H/P</option>
            </select>
          </div>
        </div>
        <p className="calc-note">Switching setup applies the recommended slot defaults for that format.</p>

        <div className="form-row">
          <div className="form-group">
            <label>Simulations</label>
            <input
              type="number"
              value={settings.sims}
              onChange={e => update("sims", e.target.value)}
              min="50"
              max="1000"
              step="50"
              disabled={isPointsMode}
            />
          </div>
          <div className="form-group">
            <label>
              Recent Proj.
              <span
                className="field-help"
                tabIndex={0}
                role="note"
                aria-label="Recent projections help"
                title="Number of newest projection sets averaged per player-year (1-10). Higher values smooth volatility."
              >
                ?
              </span>
            </label>
            <input type="number" value={settings.recent_projections} onChange={e => update("recent_projections", e.target.value)} min="1" max="10" />
          </div>
        </div>
        {isPointsMode && <p className="calc-note">Points mode ignores the simulations setting and scores directly from projected totals.</p>}

        <div className="form-row">
          <div className="form-group">
            <label>IP Min</label>
            <input
              type="number"
              value={settings.ip_min}
              onChange={e => update("ip_min", e.target.value)}
              min="0"
              step="100"
              disabled={isPointsMode}
            />
          </div>
          <div className="form-group">
            <label>IP Max</label>
            <input
              type="text"
              value={settings.ip_max}
              onChange={e => update("ip_max", e.target.value)}
              placeholder="none"
              disabled={isPointsMode}
            />
          </div>
        </div>
        {isPointsMode && <p className="calc-note">IP min/max constraints only apply in roto mode.</p>}
      </div>

      <div className="calc-section">
        <p className="calc-section-title">Presets And Sharing</p>
        <div className="form-row">
          <div className="form-group">
            <label>Preset Name</label>
            <input
              type="text"
              value={presetName}
              placeholder="e.g. 12-team H2H Points"
              onChange={e => setPresetName(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Preset Actions</label>
            <button type="button" className="calc-secondary-btn" onClick={savePreset}>
              Save / Update Preset
            </button>
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>Saved Presets</label>
            <select
              value={selectedPresetName}
              onChange={e => setSelectedPresetName(e.target.value)}
            >
              <option value="">Select Preset</option>
              {Object.keys(presets).sort((a, b) => a.localeCompare(b)).map(name => (
                <option key={name} value={name}>{name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Share</label>
            <button type="button" className="calc-secondary-btn" onClick={copyShareLink}>
              Copy Share Link
            </button>
          </div>
        </div>
        {selectedPresetName && (
          <div className="calc-inline-actions">
            <button type="button" className="calc-secondary-btn" onClick={() => loadPreset(selectedPresetName)}>
              Load Selected Preset
            </button>
            <button type="button" className="calc-secondary-btn danger" onClick={() => deletePreset(selectedPresetName)}>
              Delete Selected Preset
            </button>
          </div>
        )}
      </div>

      <div className="calc-section">
        <p className="calc-section-title">Starter Slots Per Team</p>

        <div className="form-row">
          <div className="form-group">
            <label>C</label>
            <input type="number" value={settings.hit_c} onChange={e => update("hit_c", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
          <div className="form-group">
            <label>1B</label>
            <input type="number" value={settings.hit_1b} onChange={e => update("hit_1b", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>2B</label>
            <input type="number" value={settings.hit_2b} onChange={e => update("hit_2b", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
          <div className="form-group">
            <label>3B</label>
            <input type="number" value={settings.hit_3b} onChange={e => update("hit_3b", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>SS</label>
            <input type="number" value={settings.hit_ss} onChange={e => update("hit_ss", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
          <div className="form-group">
            <label>CI</label>
            <input type="number" value={settings.hit_ci} onChange={e => update("hit_ci", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>MI</label>
            <input type="number" value={settings.hit_mi} onChange={e => update("hit_mi", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
          <div className="form-group">
            <label>OF</label>
            <input type="number" value={settings.hit_of} onChange={e => update("hit_of", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>UT</label>
            <input type="number" value={settings.hit_ut} onChange={e => update("hit_ut", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
          <div className="form-group">
            <label>P</label>
            <input type="number" value={settings.pit_p} onChange={e => update("pit_p", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>SP</label>
            <input type="number" value={settings.pit_sp} onChange={e => update("pit_sp", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
          <div className="form-group">
            <label>RP</label>
            <input type="number" value={settings.pit_rp} onChange={e => update("pit_rp", e.target.value)} min={SLOT_INPUT_MIN} max={SLOT_INPUT_MAX} />
          </div>
        </div>
      </div>

      {!isPointsMode && (
        <div className="calc-section">
          <p className="calc-section-title">Roto Categories</p>
          <p className="calc-note">
            Choose which categories count toward value in roto mode ({selectedRotoHitCategoryCount} hitting, {selectedRotoPitchCategoryCount} pitching).
          </p>

          <p className="calc-subheading">Hitting</p>
          <div className="calc-checkbox-grid">
            {ROTO_HITTER_CATEGORY_FIELDS.map(field => (
              <label className="calc-checkbox-option" key={field.key}>
                <input
                  type="checkbox"
                  checked={coerceBooleanSetting(settings[field.key], field.defaultValue)}
                  onChange={e => update(field.key, e.target.checked)}
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
                />
                <span>{field.label}</span>
              </label>
            ))}
          </div>
          <button type="button" className="calc-secondary-btn" onClick={resetRotoCategoryDefaults}>
            Reset 5x5 Categories
          </button>
        </div>
      )}

      {isPointsMode && (
        <div className="calc-section">
          <p className="calc-section-title">Points Scoring Rules</p>
          <p className="calc-note">Edit category points below. Defaults align with a common H2H points format ({pointRulesCount} categories).</p>
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
      )}

      <div className="calc-section">
        <p className="calc-section-title">Depth And Reset</p>
        <div className="form-row">
          <div className="form-group">
            <label>Bench Slots</label>
            <input type="number" value={settings.bench} onChange={e => update("bench", e.target.value)} min="0" max="40" />
          </div>
          <div className="form-group">
            <label>Minor Slots</label>
            <input type="number" value={settings.minors} onChange={e => update("minors", e.target.value)} min="0" max="60" />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>IR Slots</label>
            <input type="number" value={settings.ir} onChange={e => update("ir", e.target.value)} min="0" max="40" />
          </div>
          <div className="form-group">
            <label>Setup Actions</label>
            <button type="button" className="calc-secondary-btn" onClick={reapplySetupDefaults}>
              {isPointsMode ? "Reset Points + Slot Defaults" : "Reapply Roto Slot Defaults"}
            </button>
          </div>
        </div>
        <p className="calc-note">Reserve depth per team: {reservePerTeam} (bench + minors).</p>
      </div>

      <div className="calc-section">
        <p className="calc-section-title">Main Table Sync</p>
        <p className="calc-note">
          {mainTableOverlayActive
            ? `Custom calculator values are active in the main table${lastRunTotal > 0 ? ` (${lastRunTotal.toLocaleString()} players from your latest run).` : "."}`
            : "Run the calculator to apply your custom dynasty values directly in the main projections table."}
        </p>
        <button
          type="button"
          className="calc-secondary-btn"
          onClick={clearAppliedValues}
          disabled={!mainTableOverlayActive}
        >
          Clear Applied Values
        </button>
      </div>

      <div className="calc-section">
        <button className="calc-btn" onClick={() => run()} disabled={loading || Boolean(validationError)}>
          {loading ? "Computing..." : "Apply To Main Table"}
        </button>
        <div
          className={`calc-status ${loading ? "running" : statusIsError ? "error" : ""}`}
          role={statusIsError ? "alert" : "status"}
          aria-live="polite"
        >
          {loading
            ? status
            : validationError
              ? `Fix settings: ${validationError}`
              : status || (validationWarning ? `Warning: ${validationWarning}` : "")}
        </div>
      </div>
    </div>
  );
}
