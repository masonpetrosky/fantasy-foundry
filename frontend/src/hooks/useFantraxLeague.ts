import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import {
  readFantraxLeague,
  writeFantraxLeague,
} from "../app_state_storage";
import { extractApiErrorMessage } from "../utils/apiErrors";
import type { FantraxLeagueState } from "../app_state_storage";

interface FantraxTeamSummary {
  team_id: string;
  team_name: string;
  player_count: number;
}

interface FantraxLeagueData {
  league_id: string;
  league_name: string;
  team_count: number;
  scoring_type: string;
  scoring_categories: string[];
  roster_positions: string[];
  teams: FantraxTeamSummary[];
}

interface FantraxMatchedPlayer {
  fantrax_id: string;
  name: string;
  position: string;
  team: string;
  player_entity_key: string | null;
  match_method: string;
}

interface FantraxRosterResponse {
  team_id: string;
  team_name: string;
  matched_count: number;
  total_count: number;
  players: FantraxMatchedPlayer[];
}

interface FantraxSettingsResponse {
  teams: number;
  scoring_mode: string;
  roto_categories: Record<string, boolean>;
  roster_slots: Record<string, number>;
}

export interface UseFantraxLeagueResult {
  leagueId: string | null;
  selectedTeamId: string | null;
  leagueData: FantraxLeagueData | null;
  rosterPlayerKeys: Set<string>;
  suggestedSettings: FantraxSettingsResponse | null;
  loading: boolean;
  error: string | null;
  connectLeague: (leagueId: string) => void;
  selectTeam: (teamId: string) => void;
  disconnect: () => void;
  applyLeagueSettings: (update: (key: string, val: unknown) => void) => void;
}

export function useFantraxLeague(): UseFantraxLeagueResult {
  const [leagueId, setLeagueId] = useState<string | null>(null);
  const [selectedTeamId, setSelectedTeamId] = useState<string | null>(null);
  const [leagueData, setLeagueData] = useState<FantraxLeagueData | null>(null);
  const [rosterPlayerKeys, setRosterPlayerKeys] = useState<Set<string>>(new Set());
  const [suggestedSettings, setSuggestedSettings] = useState<FantraxSettingsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const initializedRef = useRef(false);

  // Load persisted state on mount
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;
    const stored = readFantraxLeague();
    if (stored) {
      setLeagueId(stored.leagueId);
      setSelectedTeamId(stored.selectedTeamId);
      // Re-fetch league data silently
      fetchLeagueData(stored.leagueId, stored.selectedTeamId);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- init-only effect, guarded by initializedRef
  }, []);

  const fetchLeagueData = useCallback(async (lid: string, teamId: string | null) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError(null);

    try {
      const leagueResp = await fetch(
        `/api/fantrax/league?leagueId=${encodeURIComponent(lid)}`,
        { signal: controller.signal }
      );
      if (!leagueResp.ok) {
        const body = await leagueResp.json().catch(() => ({}));
        throw new Error(body.detail || `Failed to fetch league (${leagueResp.status})`);
      }
      const league: FantraxLeagueData = await leagueResp.json();
      setLeagueData(league);

      // Fetch settings
      const settingsResp = await fetch(
        `/api/fantrax/league/settings?leagueId=${encodeURIComponent(lid)}`,
        { signal: controller.signal }
      );
      if (settingsResp.ok) {
        const settings: FantraxSettingsResponse = await settingsResp.json();
        setSuggestedSettings(settings);
      }

      // Fetch roster if team is selected
      if (teamId) {
        const rosterResp = await fetch(
          `/api/fantrax/league/roster?leagueId=${encodeURIComponent(lid)}&teamId=${encodeURIComponent(teamId)}`,
          { signal: controller.signal }
        );
        if (rosterResp.ok) {
          const roster: FantraxRosterResponse = await rosterResp.json();
          const keys = new Set<string>();
          roster.players.forEach((p) => {
            if (p.player_entity_key) keys.add(p.player_entity_key);
          });
          setRosterPlayerKeys(keys);
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") return;
      setError(extractApiErrorMessage(err));
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
      }
    }
  }, []);

  const connectLeague = useCallback((lid: string) => {
    const trimmed = lid.trim();
    if (!trimmed) return;
    setLeagueId(trimmed);
    setSelectedTeamId(null);
    setRosterPlayerKeys(new Set());
    writeFantraxLeague({ leagueId: trimmed, selectedTeamId: null });
    fetchLeagueData(trimmed, null);
  }, [fetchLeagueData]);

  const selectTeam = useCallback((teamId: string) => {
    setSelectedTeamId(teamId);
    if (leagueId) {
      writeFantraxLeague({ leagueId, selectedTeamId: teamId });
      // Fetch roster for the selected team
      const controller = new AbortController();
      abortRef.current?.abort();
      abortRef.current = controller;
      setLoading(true);
      fetch(
        `/api/fantrax/league/roster?leagueId=${encodeURIComponent(leagueId)}&teamId=${encodeURIComponent(teamId)}`,
        { signal: controller.signal }
      )
        .then((resp) => {
          if (!resp.ok) throw new Error("Failed to fetch roster");
          return resp.json();
        })
        .then((roster: FantraxRosterResponse) => {
          const keys = new Set<string>();
          roster.players.forEach((p) => {
            if (p.player_entity_key) keys.add(p.player_entity_key);
          });
          setRosterPlayerKeys(keys);
          setLoading(false);
        })
        .catch((err: unknown) => {
          if (err instanceof Error && err.name === "AbortError") return;
          setError(extractApiErrorMessage(err));
          setLoading(false);
        });
    }
  }, [leagueId]);

  const disconnect = useCallback(() => {
    abortRef.current?.abort();
    setLeagueId(null);
    setSelectedTeamId(null);
    setLeagueData(null);
    setRosterPlayerKeys(new Set());
    setSuggestedSettings(null);
    setError(null);
    writeFantraxLeague(null);
  }, []);

  const applyLeagueSettings = useCallback((update: (key: string, val: unknown) => void) => {
    if (!suggestedSettings) return;

    update("teams", suggestedSettings.teams);
    update("scoring_mode", suggestedSettings.scoring_mode);

    // Apply roto categories
    Object.entries(suggestedSettings.roto_categories).forEach(([key, val]) => {
      update(key, val);
    });

    // Apply roster slots
    Object.entries(suggestedSettings.roster_slots).forEach(([key, val]) => {
      update(key, val);
    });
  }, [suggestedSettings]);

  const stableRosterPlayerKeys = useMemo(() => rosterPlayerKeys, [rosterPlayerKeys]);

  return {
    leagueId,
    selectedTeamId,
    leagueData,
    rosterPlayerKeys: stableRosterPlayerKeys,
    suggestedSettings,
    loading,
    error,
    connectLeague,
    selectTeam,
    disconnect,
    applyLeagueSettings,
  };
}
