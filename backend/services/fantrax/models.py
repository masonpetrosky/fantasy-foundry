"""Pydantic models for Fantrax league data."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    players: list[RosterPlayer] = Field(default_factory=list)


class LeagueInfo(BaseModel):
    """Normalized Fantrax league data."""

    league_id: str
    league_name: str
    teams: list[TeamRoster] = Field(default_factory=list)
    team_count: int = 0
    scoring_type: str = "roto"
    scoring_categories: list[str] = Field(default_factory=list)
    roster_positions: list[str] = Field(default_factory=list)
    points_scoring: dict[str, float] = Field(default_factory=dict)
    bench: int | None = None
    minors: int | None = None
    ir: int | None = None
    keeper_limit: int | None = None
    points_valuation_mode: str = "season_total"
    weekly_starts_cap: int | None = None
    allow_same_day_starts_overflow: bool = False
    weekly_acquisition_cap: int | None = None
    import_warnings: list[str] = Field(default_factory=list)


class MatchedRoster(BaseModel):
    """A team roster with FF player key matches."""

    team_id: str
    team_name: str
    players: list[MatchedPlayer] = Field(default_factory=list)
    matched_count: int = 0
    total_count: int = 0


class LeagueSuggestedSettings(BaseModel):
    """Calculator settings suggested from Fantrax league configuration."""

    teams: int = 12
    scoring_mode: str = "roto"
    roto_categories: dict[str, bool] = Field(default_factory=dict)
    roster_slots: dict[str, int] = Field(default_factory=dict)
    points_scoring: dict[str, float] = Field(default_factory=dict)
    bench: int | None = None
    minors: int | None = None
    ir: int | None = None
    keeper_limit: int | None = None
    points_valuation_mode: str = "season_total"
    weekly_starts_cap: int | None = None
    allow_same_day_starts_overflow: bool = False
    weekly_acquisition_cap: int | None = None
    import_warnings: list[str] = Field(default_factory=list)
