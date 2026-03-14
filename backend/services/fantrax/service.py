"""Fantrax league data fetching service."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from backend.services.fantrax.models import (
    LeagueInfo,
    RosterPlayer,
    TeamRoster,
)

logger = logging.getLogger(__name__)

FANTRAX_BASE_URL = "https://www.fantrax.com/fxea/general"
FANTRAX_ROSTERS_URL = f"{FANTRAX_BASE_URL}/getTeamRosters"
FANTRAX_STANDINGS_URL = f"{FANTRAX_BASE_URL}/getStandings"

# In-memory cache: league_id -> (timestamp, LeagueInfo)
_league_cache: dict[str, tuple[float, LeagueInfo]] = {}
_league_cache_lock = asyncio.Lock()
_CACHE_TTL_SECONDS = 900  # 15 minutes
_MAX_CACHE_ENTRIES = 50


def _prune_cache() -> None:
    """Remove expired or excess cache entries (caller must hold _league_cache_lock)."""
    now = time.monotonic()
    expired = [k for k, (ts, _) in _league_cache.items() if now - ts > _CACHE_TTL_SECONDS]
    for k in expired:
        del _league_cache[k]
    if len(_league_cache) > _MAX_CACHE_ENTRIES:
        by_age = sorted(_league_cache.items(), key=lambda x: x[1][0])
        for k, _ in by_age[: len(_league_cache) - _MAX_CACHE_ENTRIES]:
            del _league_cache[k]


def _get_cached(league_id: str) -> LeagueInfo | None:
    """Read from cache (caller must hold _league_cache_lock)."""
    entry = _league_cache.get(league_id)
    if entry is None:
        return None
    ts, info = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        del _league_cache[league_id]
        return None
    return info


def _set_cached(league_id: str, info: LeagueInfo) -> None:
    """Write to cache (caller must hold _league_cache_lock)."""
    _prune_cache()
    _league_cache[league_id] = (time.monotonic(), info)


def _parse_rosters_response(data: dict[str, Any], league_id: str) -> list[TeamRoster]:
    """Parse the Fantrax getTeamRosters response."""
    teams: list[TeamRoster] = []
    rosters = data.get("rosters", {})
    if isinstance(rosters, dict):
        for team_id, team_data in rosters.items():
            team_name = str(team_data.get("teamName", team_id))
            players: list[RosterPlayer] = []
            player_list = team_data.get("rosterItems", [])
            if isinstance(player_list, list):
                for item in player_list:
                    if not isinstance(item, dict):
                        continue
                    players.append(
                        RosterPlayer(
                            fantrax_id=str(item.get("id", "")),
                            name=str(item.get("name", "")),
                            position=str(item.get("pos", item.get("position", ""))),
                            team=str(item.get("team", item.get("teamAbbrev", ""))),
                        )
                    )
            teams.append(
                TeamRoster(team_id=str(team_id), team_name=team_name, players=players)
            )
    return teams


def _parse_standings_response(
    data: dict[str, Any],
) -> tuple[str, str, list[str], list[str]]:
    """Parse standings response for league name, scoring type, categories, and positions.

    Returns (league_name, scoring_type, categories, positions).
    """
    league_name = str(data.get("leagueName", data.get("league", {}).get("name", "Fantrax League")))
    scoring_type = "roto"

    raw_type = str(data.get("scoringType", data.get("league", {}).get("scoringType", ""))).lower()
    if "point" in raw_type or "pts" in raw_type:
        scoring_type = "points"
    elif "roto" in raw_type or "rotisserie" in raw_type:
        scoring_type = "roto"

    categories: list[str] = []
    raw_cats = data.get("scoringCategories", data.get("categories", []))
    if isinstance(raw_cats, list):
        for cat in raw_cats:
            if isinstance(cat, dict):
                categories.append(str(cat.get("name", cat.get("abbr", ""))))
            elif isinstance(cat, str):
                categories.append(cat)

    positions: list[str] = []
    raw_positions = data.get("rosterPositions", data.get("positions", []))
    if isinstance(raw_positions, list):
        for pos in raw_positions:
            if isinstance(pos, dict):
                positions.append(str(pos.get("code", pos.get("name", ""))))
            elif isinstance(pos, str):
                positions.append(pos)

    return league_name, scoring_type, categories, positions


async def fetch_league_info(league_id: str, *, request_id: str | None = None) -> LeagueInfo:
    """Fetch league info from Fantrax public API.

    Returns cached data if available and fresh.
    """
    async with _league_cache_lock:
        cached = _get_cached(league_id)
    if cached is not None:
        return cached

    league_name = "Fantrax League"
    scoring_type = "roto"
    categories: list[str] = []
    positions: list[str] = []
    teams: list[TeamRoster] = []

    extra_headers: dict[str, str] = {}
    if request_id:
        extra_headers["X-Request-Id"] = request_id

    async with httpx.AsyncClient(timeout=15, headers=extra_headers) as client:
        # Fetch rosters
        try:
            roster_resp = await client.get(
                FANTRAX_ROSTERS_URL, params={"leagueId": league_id}
            )
            roster_resp.raise_for_status()
            roster_data = roster_resp.json()
            teams = _parse_rosters_response(roster_data, league_id)
            # Try to get league name from roster response
            if "leagueName" in roster_data:
                league_name = str(roster_data["leagueName"])
        except httpx.HTTPStatusError:
            logger.warning(
                "Fantrax roster API error for league %s: %s",
                league_id,
                roster_resp.status_code if "roster_resp" in dir() else "unknown",
            )
            raise
        except httpx.RequestError as exc:
            logger.warning("Fantrax roster API request error for league %s: %s", league_id, exc)
            raise

        # Fetch standings for league metadata
        try:
            standings_resp = await client.get(
                FANTRAX_STANDINGS_URL, params={"leagueId": league_id}
            )
            standings_resp.raise_for_status()
            standings_data = standings_resp.json()
            league_name, scoring_type, categories, positions = _parse_standings_response(
                standings_data
            )
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.info(
                "Fantrax standings API unavailable for league %s (non-fatal): %s",
                league_id,
                exc,
            )

    info = LeagueInfo(
        league_id=league_id,
        league_name=league_name,
        teams=teams,
        team_count=len(teams),
        scoring_type=scoring_type,
        scoring_categories=categories,
        roster_positions=positions,
    )
    async with _league_cache_lock:
        _set_cached(league_id, info)
    return info
