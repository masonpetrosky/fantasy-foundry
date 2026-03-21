import React, { useState, useCallback } from "react";
import type { UseFantraxLeagueResult } from "../../hooks/useFantraxLeague";

interface LeagueConnectPanelProps {
  fantrax: UseFantraxLeagueResult;
  onApplySettings: () => void;
}

export const LeagueConnectPanel = React.memo(function LeagueConnectPanel({
  fantrax,
  onApplySettings,
}: LeagueConnectPanelProps): React.ReactElement {
  const [inputValue, setInputValue] = useState("");
  const [collapsed, setCollapsed] = useState(Boolean(fantrax.leagueId));

  const handleConnect = useCallback(() => {
    const trimmed = inputValue.trim();
    if (trimmed) {
      fantrax.connectLeague(trimmed);
    }
  }, [inputValue, fantrax]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") handleConnect();
    },
    [handleConnect]
  );

  const handleTeamChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const teamId = e.target.value;
      if (teamId) fantrax.selectTeam(teamId);
    },
    [fantrax]
  );
  const importedPointsMode = String(fantrax.suggestedSettings?.points_valuation_mode || "").trim().toLowerCase();
  const importedPointsGuidance = importedPointsMode === "weekly_h2h"
    ? "Weekly H2H points uses a calibrated valuation model, not a day-by-day schedule simulation. Review imported weekly caps and acquisition rules before running the calculator."
    : importedPointsMode === "daily_h2h"
      ? "Daily H2H points uses the day-aware roster management model. Review imported weekly caps and acquisition rules before running the calculator."
      : "";

  return (
    <div className="calc-section fantrax-league-section">
      <button
        type="button"
        className="calc-section-title fantrax-toggle-btn"
        onClick={() => setCollapsed((prev) => !prev)}
        aria-expanded={!collapsed}
      >
        Fantrax League {collapsed ? "+" : "\u2212"}
      </button>

      {!collapsed && (
        <div className="fantrax-panel-body">
          {!fantrax.leagueId && (
            <>
              <p className="calc-note">
                Paste your Fantrax League ID to import roster and scoring settings.
              </p>
              <div className="fantrax-connect-row">
                <input
                  type="text"
                  className="fantrax-league-input"
                  placeholder="League ID"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={fantrax.loading}
                />
                <button
                  type="button"
                  className="fantrax-connect-btn"
                  onClick={handleConnect}
                  disabled={fantrax.loading || !inputValue.trim()}
                >
                  {fantrax.loading ? "Connecting\u2026" : "Connect"}
                </button>
              </div>
            </>
          )}

          {fantrax.leagueId && fantrax.leagueData && (
            <div className="fantrax-connected-info">
              <p className="fantrax-league-name">
                {fantrax.leagueData.league_name}
              </p>
              <p className="calc-note">
                {fantrax.leagueData.team_count} teams &middot;{" "}
                {fantrax.leagueData.scoring_type === "points"
                  ? "Points"
                  : "Roto"}{" "}
                scoring
              </p>

              <div className="fantrax-team-select-row">
                <label htmlFor="fantrax-team-select">My Team</label>
                <select
                  id="fantrax-team-select"
                  value={fantrax.selectedTeamId || ""}
                  onChange={handleTeamChange}
                  disabled={fantrax.loading}
                >
                  <option value="">Select your team</option>
                  {fantrax.leagueData.teams.map((t) => (
                    <option key={t.team_id} value={t.team_id}>
                      {t.team_name} ({t.player_count} players)
                    </option>
                  ))}
                </select>
              </div>

              {fantrax.selectedTeamId && fantrax.rosterPlayerKeys.size > 0 && (
                <p className="calc-note fantrax-roster-status">
                  {fantrax.rosterPlayerKeys.size} players matched to projections
                </p>
              )}

              <div className="fantrax-actions">
                {fantrax.suggestedSettings && (
                  <button
                    type="button"
                    className="fantrax-apply-btn"
                    onClick={onApplySettings}
                    disabled={fantrax.loading}
                  >
                    Import League Settings
                  </button>
                )}
                <button
                  type="button"
                  className="fantrax-disconnect-btn"
                  onClick={fantrax.disconnect}
                >
                  Disconnect
                </button>
              </div>
              {fantrax.leagueData.scoring_type === "points" && importedPointsGuidance ? (
                <p className="calc-note fantrax-roster-status">
                  {importedPointsGuidance}
                </p>
              ) : null}
              {fantrax.suggestedSettings?.import_warnings?.length ? (
                <p className="calc-note fantrax-roster-status">
                  Import warnings: {fantrax.suggestedSettings.import_warnings.join(" ")}
                </p>
              ) : null}
            </div>
          )}

          {fantrax.leagueId && !fantrax.leagueData && fantrax.loading && (
            <p className="calc-note">Loading league data&hellip;</p>
          )}

          {fantrax.error && (
            <p className="calc-note fantrax-error">{fantrax.error}</p>
          )}
        </div>
      )}
    </div>
  );
});
