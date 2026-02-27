import React from "react";
import { CalcTooltip } from "./dynasty_calculator_tooltip.jsx";
import { RotoCategoriesForm } from "./dynasty_calculator_sidebar_categories.jsx";
import { PointsScoringForm } from "./dynasty_calculator_sidebar_points.jsx";
import { StarterSlotsForm } from "./dynasty_calculator_sidebar_slots.jsx";

export function DynastyCalculatorSidebar({
  meta,
  presets,
  settings,
  state,
  actions,
}) {
  const {
    canSavePreset,
    hittersPerTeam,
    isPointsMode,
    lastRunTotal,
    loading,
    mainTableOverlayActive,
    pointRulesCount,
    presetName,
    presetStatus,
    presetStatusIsError,
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
    hasSuccessfulRun,
  } = state;
  const {
    applyQuickStartAndRun,
    applyScoringSetup,
    clearAppliedValues,
    copyShareLink,
    deletePreset,
    reapplySetupDefaults,
    resetPointsScoringDefaults,
    resetRotoCategoryDefaults,
    run,
    savePreset,
    selectPreset,
    setPresetName,
    update,
  } = actions;
  const runActionLabel = hasSuccessfulRun ? "Apply To Main Table" : "Run Dynasty Rankings";

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
        <p className="calc-note calc-note-links">
          Definitions:
          {" "}
          <CalcTooltip label="Projection Window">The year range included in valuation. Fantasy Foundry provides projections from 2026 through 2045.</CalcTooltip>
          {" · "}
          <CalcTooltip label="League Configuration">Your teams, roster slots, scoring categories, and innings rules. The calculator uses this setup to produce custom rankings.</CalcTooltip>
          {" · "}
          <CalcTooltip label="SGP">A way to convert raw stats into standings movement. One SGP estimates the amount of production needed to gain one place in a category.</CalcTooltip>
        </p>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="calc-teams-input">Teams</label>
            <input
              id="calc-teams-input"
              type="number"
              value={settings.teams}
              onChange={e => update("teams", e.target.value)}
              min="2"
              max="30"
            />
          </div>
          <div className="form-group">
            <label htmlFor="calc-start-year">Start Year</label>
            <select id="calc-start-year" value={settings.start_year} onChange={e => update("start_year", e.target.value)}>
              {meta.years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="calc-horizon">Horizon (yrs)</label>
            <input id="calc-horizon" type="number" value={settings.horizon} onChange={e => update("horizon", e.target.value)} min="1" max="20" />
          </div>
          <div className="form-group">
            <label htmlFor="calc-setup">Setup</label>
            <select
              id="calc-setup"
              value={settings.scoring_mode}
              onChange={e => applyScoringSetup(e.target.value)}
              disabled={settings.mode === "league"}
            >
              <option value="roto">Roto Focused</option>
              <option value="points">Points Focused</option>
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="calc-mode">
              Valuation Mode
              <span
                className="field-help"
                tabIndex={0}
                role="note"
                aria-label="Valuation mode help"
                title="Common: values players against a simulated average-starter pool. League: two-pass replacement-level valuation producing more realistic dynasty values."
              >
                ?
              </span>
            </label>
            <select
              id="calc-mode"
              value={settings.mode || "common"}
              onChange={e => {
                const newMode = e.target.value;
                update("mode", newMode);
                if (newMode === "league" && settings.scoring_mode !== "roto") {
                  applyScoringSetup("roto");
                }
              }}
            >
              <option value="common">Common</option>
              <option value="league">League</option>
            </select>
          </div>
        </div>
        <p className="calc-note">
          {settings.mode === "league"
            ? "League mode uses two-pass replacement-level valuation (roto only). Setup is locked to roto."
            : "Switching setup applies the recommended slot defaults for that format."}
        </p>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="calc-discount">
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
            <input id="calc-discount" type="number" value={settings.discount} onChange={e => update("discount", e.target.value)} min="0.5" max="1" step="0.01" />
          </div>
          <div className="form-group">
            <label htmlFor="calc-two-way">
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
            <select id="calc-two-way" value={settings.two_way} onChange={e => update("two_way", e.target.value)}>
              <option value="sum">Sum H + P</option>
              <option value="max">Best of H/P</option>
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="calc-sims">Simulations</label>
            <input
              id="calc-sims"
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
            <label htmlFor="calc-recent-projections">
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
            <input id="calc-recent-projections" type="number" value={settings.recent_projections} onChange={e => update("recent_projections", e.target.value)} min="1" max="10" />
          </div>
        </div>
        {isPointsMode && <p className="calc-note">Points mode ignores the simulations setting and scores directly from projected totals.</p>}

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="calc-ip-min">IP Min</label>
            <input
              id="calc-ip-min"
              type="number"
              value={settings.ip_min}
              onChange={e => update("ip_min", e.target.value)}
              min="0"
              step="100"
              disabled={isPointsMode}
            />
          </div>
          <div className="form-group">
            <label htmlFor="calc-ip-max">IP Max</label>
            <input
              id="calc-ip-max"
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
            <label htmlFor="calc-preset-name">Preset Name</label>
            <input
              id="calc-preset-name"
              type="text"
              value={presetName}
              placeholder="e.g. 12-team H2H Points"
              onChange={e => setPresetName(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>Preset Actions</label>
            <button type="button" className="calc-secondary-btn" onClick={savePreset} disabled={!canSavePreset}>
              Save / Update Preset
            </button>
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="calc-saved-presets">Saved Presets</label>
            <select
              id="calc-saved-presets"
              value={selectedPresetName}
              onChange={e => selectPreset(e.target.value)}
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
        {presetStatus && (
          <p
            className={`calc-preset-status ${presetStatusIsError ? "error" : ""}`.trim()}
            role={presetStatusIsError ? "alert" : "status"}
            aria-live="polite"
          >
            {presetStatus}
          </p>
        )}
        {selectedPresetName && (
          <div className="calc-inline-actions calc-inline-actions-single">
            <button type="button" className="calc-secondary-btn danger" onClick={() => deletePreset(selectedPresetName)}>
              Delete Selected Preset
            </button>
          </div>
        )}
      </div>

      <StarterSlotsForm settings={settings} update={update} />

      {!isPointsMode && (
        <RotoCategoriesForm
          settings={settings}
          update={update}
          selectedRotoHitCategoryCount={selectedRotoHitCategoryCount}
          selectedRotoPitchCategoryCount={selectedRotoPitchCategoryCount}
          resetRotoCategoryDefaults={resetRotoCategoryDefaults}
        />
      )}

      {isPointsMode && (
        <PointsScoringForm
          settings={settings}
          update={update}
          pointRulesCount={pointRulesCount}
          resetPointsScoringDefaults={resetPointsScoringDefaults}
        />
      )}

      <div className="calc-section">
        <p className="calc-section-title">Depth And Reset</p>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="calc-bench">Bench Slots</label>
            <input id="calc-bench" type="number" value={settings.bench} onChange={e => update("bench", e.target.value)} min="0" max="40" />
          </div>
          <div className="form-group">
            <label htmlFor="calc-minors">Minor Slots</label>
            <input id="calc-minors" type="number" value={settings.minors} onChange={e => update("minors", e.target.value)} min="0" max="60" />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="calc-ir">IR Slots</label>
            <input id="calc-ir" type="number" value={settings.ir} onChange={e => update("ir", e.target.value)} min="0" max="40" />
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
          {loading ? "Computing..." : runActionLabel}
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
