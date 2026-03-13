"""Pydantic models for Fantrax league data."""

from __future__ import annotations

from pydantic import BaseModel


class RosterPlayer(BaseModel):
    """A single player on a Fantrax roster."""

    fantrax_id: str
    name: str
    position: str
    team: str = ""


class MatchedPlayer(BaseModel):
    """A Fantrax player matched to a Fantasy Foundry projection entity."""

    fantrax_id: str
    name: str
    position: str
    team: str = ""
    player_entity_key: str | None = None
    match_method: str = "none"


class TeamRoster(BaseModel):
    """A team within a Fantrax league."""

    team_id: str
    team_name: str
    players: list[RosterPlayer] = []


class LeagueInfo(BaseModel):
    """Normalized Fantrax league data."""

    league_id: str
    league_name: str
    teams: list[TeamRoster] = []
    team_count: int = 0
    scoring_type: str = "roto"
    scoring_categories: list[str] = []
    roster_positions: list[str] = []


class MatchedRoster(BaseModel):
    """A team roster with FF player key matches."""

    team_id: str
    team_name: str
    players: list[MatchedPlayer] = []
    matched_count: int = 0
    total_count: int = 0


class LeagueSuggestedSettings(BaseModel):
    """Calculator settings suggested from Fantrax league configuration."""

    teams: int = 12
    scoring_mode: str = "roto"
    roto_categories: dict[str, bool] = {}
    roster_slots: dict[str, int] = {}
