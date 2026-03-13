"""Fantrax league integration endpoints."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.services.fantrax.mapping import (
    build_player_lookup,
    build_suggested_settings,
    match_roster,
)
from backend.services.fantrax.models import LeagueInfo

logger = logging.getLogger(__name__)

_LEAGUE_ID_MAX_LEN = 64
_LEAGUE_ID_MIN_LEN = 5

LeagueFetcher = Callable[[str], Any]
PlayerSummaryGetter = Callable[[], dict[str, dict[str, Any]]]


def _validate_league_id(league_id: str | None) -> str:
    if not league_id or not league_id.strip():
        raise HTTPException(status_code=400, detail="leagueId query parameter is required.")
    league_id = league_id.strip()
    if len(league_id) < _LEAGUE_ID_MIN_LEN or len(league_id) > _LEAGUE_ID_MAX_LEN:
        raise HTTPException(status_code=400, detail="Invalid leagueId format.")
    return league_id


def build_fantrax_router(
    *,
    enforce_rate_limit: object,
    client_ip_resolver: object,
    league_fetcher: LeagueFetcher,
    player_summary_getter: PlayerSummaryGetter,
    rate_limit_per_minute: int = 10,
) -> APIRouter:
    """Create Fantrax league integration routes."""
    router = APIRouter(tags=["fantrax"])

    @router.get("/api/fantrax/league")
    async def get_league(request: Request, leagueId: str | None = None) -> JSONResponse:
        """Fetch Fantrax league info (teams, scoring, slots)."""
        client_ip = client_ip_resolver(request)
        enforce_rate_limit(client_ip, "fantrax", rate_limit_per_minute)

        league_id = _validate_league_id(leagueId)

        try:
            league_info: LeagueInfo = await league_fetcher(league_id)
        except Exception:
            logger.exception("Failed to fetch Fantrax league %s", league_id)
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch league data from Fantrax. Please verify the League ID and try again.",
            )

        return JSONResponse(
            {
                "league_id": league_info.league_id,
                "league_name": league_info.league_name,
                "team_count": league_info.team_count,
                "scoring_type": league_info.scoring_type,
                "scoring_categories": league_info.scoring_categories,
                "roster_positions": league_info.roster_positions,
                "teams": [
                    {
                        "team_id": t.team_id,
                        "team_name": t.team_name,
                        "player_count": len(t.players),
                    }
                    for t in league_info.teams
                ],
            }
        )

    @router.get("/api/fantrax/league/roster")
    async def get_league_roster(
        request: Request,
        leagueId: str | None = None,
        teamId: str | None = None,
    ) -> JSONResponse:
        """Fetch a team's roster with FF player key matches."""
        client_ip = client_ip_resolver(request)
        enforce_rate_limit(client_ip, "fantrax", rate_limit_per_minute)

        league_id = _validate_league_id(leagueId)
        if not teamId or not teamId.strip():
            raise HTTPException(status_code=400, detail="teamId query parameter is required.")
        team_id = teamId.strip()

        try:
            league_info: LeagueInfo = await league_fetcher(league_id)
        except Exception:
            logger.exception("Failed to fetch Fantrax league %s", league_id)
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch league data from Fantrax.",
            )

        team = None
        for t in league_info.teams:
            if t.team_id == team_id:
                team = t
                break

        if team is None:
            raise HTTPException(status_code=404, detail=f"Team '{team_id}' not found in league.")

        player_summary = player_summary_getter()
        name_team_index, name_only_index = build_player_lookup(player_summary)
        matched = match_roster(
            team.team_id, team.team_name, team.players, name_team_index, name_only_index
        )

        return JSONResponse(
            {
                "team_id": matched.team_id,
                "team_name": matched.team_name,
                "matched_count": matched.matched_count,
                "total_count": matched.total_count,
                "players": [
                    {
                        "fantrax_id": p.fantrax_id,
                        "name": p.name,
                        "position": p.position,
                        "team": p.team,
                        "player_entity_key": p.player_entity_key,
                        "match_method": p.match_method,
                    }
                    for p in matched.players
                ],
            }
        )

    @router.get("/api/fantrax/league/settings")
    async def get_league_settings(
        request: Request,
        leagueId: str | None = None,
    ) -> JSONResponse:
        """Get calculator-compatible settings derived from league configuration."""
        client_ip = client_ip_resolver(request)
        enforce_rate_limit(client_ip, "fantrax", rate_limit_per_minute)

        league_id = _validate_league_id(leagueId)

        try:
            league_info: LeagueInfo = await league_fetcher(league_id)
        except Exception:
            logger.exception("Failed to fetch Fantrax league %s", league_id)
            raise HTTPException(
                status_code=502,
                detail="Failed to fetch league data from Fantrax.",
            )

        suggested = build_suggested_settings(league_info)
        return JSONResponse(
            {
                "teams": suggested.teams,
                "scoring_mode": suggested.scoring_mode,
                "roto_categories": suggested.roto_categories,
                "roster_slots": suggested.roster_slots,
            }
        )

    return router
