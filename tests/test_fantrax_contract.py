"""Contract tests for Fantrax API response schema."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.fantrax import build_fantrax_router
from backend.services.fantrax.models import (
    LeagueInfo,
    RosterPlayer,
    TeamRoster,
)

pytestmark = pytest.mark.integration


def _make_league_info() -> LeagueInfo:
    return LeagueInfo(
        league_id="contract-test-league",
        league_name="Contract Test League",
        teams=[
            TeamRoster(
                team_id="t1",
                team_name="Team Alpha",
                players=[
                    RosterPlayer(fantrax_id="p1", name="Mike Trout", position="CF", team="LAA"),
                ],
            ),
        ],
        team_count=1,
        scoring_type="roto",
        scoring_categories=["R", "HR", "RBI", "SB", "AVG", "W", "K", "SV", "ERA", "WHIP"],
        roster_positions=["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "UT", "P", "P"],
    )


def _make_player_summary() -> dict:
    return {
        "mike-trout__laa": {"name": "Mike Trout", "team": "LAA", "pos": "CF", "age": 34, "type": "H"},
    }


@pytest.fixture()
def contract_client() -> TestClient:
    app = FastAPI()
    router = build_fantrax_router(
        enforce_rate_limit=MagicMock(),
        client_ip_resolver=MagicMock(return_value="127.0.0.1"),
        league_fetcher=AsyncMock(return_value=_make_league_info()),
        player_summary_getter=MagicMock(return_value=_make_player_summary()),
    )
    app.include_router(router)
    return TestClient(app)


def test_league_response_schema(contract_client: TestClient) -> None:
    """Verify /api/fantrax/league returns all required fields with correct types."""
    resp = contract_client.get("/api/fantrax/league?leagueId=contract-test-league")
    assert resp.status_code == 200
    body = resp.json()

    assert isinstance(body["league_id"], str)
    assert isinstance(body["league_name"], str)
    assert isinstance(body["team_count"], int)
    assert isinstance(body["scoring_type"], str)
    assert isinstance(body["scoring_categories"], list)
    assert isinstance(body["roster_positions"], list)
    assert isinstance(body["teams"], list)

    required_keys = {"league_id", "league_name", "team_count", "scoring_type", "scoring_categories", "roster_positions", "teams"}
    assert required_keys <= set(body.keys())

    team = body["teams"][0]
    assert isinstance(team["team_id"], str)
    assert isinstance(team["team_name"], str)
    assert isinstance(team["player_count"], int)


def test_roster_response_schema(contract_client: TestClient) -> None:
    """Verify /api/fantrax/league/roster returns all required fields with correct types."""
    resp = contract_client.get("/api/fantrax/league/roster?leagueId=contract-test-league&teamId=t1")
    assert resp.status_code == 200
    body = resp.json()

    assert isinstance(body["team_id"], str)
    assert isinstance(body["team_name"], str)
    assert isinstance(body["matched_count"], int)
    assert isinstance(body["total_count"], int)
    assert isinstance(body["players"], list)

    required_keys = {"team_id", "team_name", "matched_count", "total_count", "players"}
    assert required_keys <= set(body.keys())

    player = body["players"][0]
    player_required_keys = {"fantrax_id", "name", "position", "team", "player_entity_key", "match_method"}
    assert player_required_keys <= set(player.keys())
    assert isinstance(player["fantrax_id"], str)
    assert isinstance(player["name"], str)
    assert player["match_method"] in ("name_team", "name_only", "unmatched")


def test_settings_response_schema(contract_client: TestClient) -> None:
    """Verify /api/fantrax/league/settings returns all required fields with correct types."""
    resp = contract_client.get("/api/fantrax/league/settings?leagueId=contract-test-league")
    assert resp.status_code == 200
    body = resp.json()

    assert isinstance(body["teams"], int)
    assert isinstance(body["scoring_mode"], str)
    assert isinstance(body["roto_categories"], dict)
    assert isinstance(body["roster_slots"], dict)

    required_keys = {"teams", "scoring_mode", "roto_categories", "roster_slots"}
    assert required_keys <= set(body.keys())
