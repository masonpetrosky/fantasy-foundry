import React, { useEffect, useState } from "react";
import { glossaryTermAnchorId } from "./app_content.js";
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
    openMethodologyGlossary,
  } = actions;
  const [showAdvancedSettings, setShowAdvancedSettings] = useState(Boolean(hasSuccessfulRun));

  useEffect(() => {
    if (!hasSuccessfulRun) return;
    setShowAdvancedSettings(true);
  }, [hasSuccessfulRun]);

  function jumpToGlossaryTerm(term) {
    if (typeof openMethodologyGlossary !== "function") return;
    openMethodologyGlossary(glossaryTermAnchorId(term));
  }

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
          <button type="button" className="calc-method-link" onClick={() => jumpToGlossaryTerm("Projection Window")}>Projection Window</button>
          {" · "}
          <button type="button" className="calc-method-link" onClick={() => jumpToGlossaryTerm("League Configuration")}>League Configuration</button>
          {" · "}
          <button type="button" className="calc-method-link" onClick={() => jumpToGlossaryTerm("SGP (Standings Gain Points)")}>SGP</button>
        </p>

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
            <button type="button" className="calc-secondary-btn" onClick={savePreset} disabled={!canSavePreset}>
              Save / Update Preset
            </button>
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>Saved Presets</label>
            <select
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

      <div className="calc-section">
        <p className="calc-section-title">Advanced Settings</p>
        <p className="calc-note">
          Starter slots, scoring categories, and bench/minors depth.
          {!hasSuccessfulRun && " Run quick start first for a baseline before adjusting these values."}
        </p>
        <button
          type="button"
          className="calc-secondary-btn"
          onClick={() => setShowAdvancedSettings(current => !current)}
        >
          {showAdvancedSettings ? "Hide Advanced Settings" : "Show Advanced Settings"}
        </button>
      </div>

      {showAdvancedSettings && (
        <>
          <StarterSlotsForm settings={settings} update={update} />

          {!isPointsMode && (
            <RotoCategoriesForm
              settings={settings}
              update={update}
              selectedRotoHitCategoryCount={selectedRotoHitCategoryCount}
              selectedRotoPitchCategoryCount={selectedRotoPitchCategoryCount}
              resetRotoCategoryDefaults={resetRotoCategoryDefaults}
              jumpToGlossaryTerm={jumpToGlossaryTerm}
            />
          )}

          {isPointsMode && (
            <PointsScoringForm
              settings={settings}
              update={update}
              pointRulesCount={pointRulesCount}
              resetPointsScoringDefaults={resetPointsScoringDefaults}
              jumpToGlossaryTerm={jumpToGlossaryTerm}
            />
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
        </>
      )}

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
