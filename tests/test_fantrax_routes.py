"""Tests for Fantrax league integration API routes."""

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


def _make_league_info():
    return LeagueInfo(
        league_id="test-league-id",
        league_name="Test Dynasty League",
        teams=[
            TeamRoster(
                team_id="t1",
                team_name="Team Alpha",
                players=[
                    RosterPlayer(fantrax_id="p1", name="Mike Trout", position="CF", team="LAA"),
                    RosterPlayer(fantrax_id="p2", name="Shohei Ohtani", position="DH", team="LAD"),
                ],
            ),
            TeamRoster(
                team_id="t2",
                team_name="Team Beta",
                players=[
                    RosterPlayer(fantrax_id="p3", name="Aaron Judge", position="RF", team="NYY"),
                ],
            ),
        ],
        team_count=2,
        scoring_type="roto",
        scoring_categories=["R", "HR", "RBI", "SB", "AVG", "W", "K", "SV", "ERA", "WHIP"],
        roster_positions=["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "UT", "P", "P"],
    )


def _make_player_summary():
    return {
        "mike-trout__laa": {"name": "Mike Trout", "team": "LAA", "pos": "CF", "age": 34, "type": "H"},
        "shohei-ohtani__lad": {"name": "Shohei Ohtani", "team": "LAD", "pos": "DH", "age": 31, "type": "H"},
        "aaron-judge__nyy": {"name": "Aaron Judge", "team": "NYY", "pos": "RF", "age": 34, "type": "H"},
    }


@pytest.fixture()
def fantrax_app():
    enforce_rate_limit = MagicMock()
    client_ip_resolver = MagicMock(return_value="127.0.0.1")
    league_fetcher = AsyncMock(return_value=_make_league_info())
    player_summary_getter = MagicMock(return_value=_make_player_summary())

    app = FastAPI()
    router = build_fantrax_router(
        enforce_rate_limit=enforce_rate_limit,
        client_ip_resolver=client_ip_resolver,
        league_fetcher=league_fetcher,
        player_summary_getter=player_summary_getter,
        rate_limit_per_minute=10,
    )
    app.include_router(router)
    return app, enforce_rate_limit, league_fetcher


def test_get_league_success(fantrax_app):
    app, _, _ = fantrax_app
    client = TestClient(app)
    resp = client.get("/api/fantrax/league?leagueId=test-league-id")
    assert resp.status_code == 200
    body = resp.json()
    assert body["league_name"] == "Test Dynasty League"
    assert body["team_count"] == 2
    assert len(body["teams"]) == 2


def test_get_league_missing_id(fantrax_app):
    app, _, _ = fantrax_app
    client = TestClient(app)
    resp = client.get("/api/fantrax/league")
    assert resp.status_code == 400


def test_get_league_short_id(fantrax_app):
    app, _, _ = fantrax_app
    client = TestClient(app)
    resp = client.get("/api/fantrax/league?leagueId=ab")
    assert resp.status_code == 400


def test_get_league_roster_success(fantrax_app):
    app, _, _ = fantrax_app
    client = TestClient(app)
    resp = client.get("/api/fantrax/league/roster?leagueId=test-league-id&teamId=t1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["team_name"] == "Team Alpha"
    assert body["total_count"] == 2
    assert body["matched_count"] == 2
    assert any(p["player_entity_key"] == "mike-trout__laa" for p in body["players"])


def test_get_league_roster_missing_team(fantrax_app):
    app, _, _ = fantrax_app
    client = TestClient(app)
    resp = client.get("/api/fantrax/league/roster?leagueId=test-league-id")
    assert resp.status_code == 400


def test_get_league_roster_unknown_team(fantrax_app):
    app, _, _ = fantrax_app
    client = TestClient(app)
    resp = client.get("/api/fantrax/league/roster?leagueId=test-league-id&teamId=nonexistent")
    assert resp.status_code == 404


def test_get_league_settings(fantrax_app):
    app, _, _ = fantrax_app
    client = TestClient(app)
    resp = client.get("/api/fantrax/league/settings?leagueId=test-league-id")
    assert resp.status_code == 200
    body = resp.json()
    assert body["teams"] == 2
    assert body["scoring_mode"] == "roto"
    assert body["roto_categories"]["roto_hit_r"] is True
    assert "roster_slots" in body


def test_get_league_fetcher_error(fantrax_app):
    app, _, league_fetcher = fantrax_app
    league_fetcher.side_effect = OSError("Fantrax unavailable")
    client = TestClient(app)
    resp = client.get("/api/fantrax/league?leagueId=test-league-id")
    assert resp.status_code == 502


def test_rate_limit_called(fantrax_app):
    app, enforce_rate_limit, _ = fantrax_app
    client = TestClient(app)
    client.get("/api/fantrax/league?leagueId=test-league-id")
    enforce_rate_limit.assert_called_once_with("127.0.0.1", "fantrax", 10)
