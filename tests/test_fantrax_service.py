"""Tests for Fantrax league integration service and mapping."""

import pytest

from backend.services.fantrax.mapping import (
    build_player_lookup,
    build_suggested_settings,
    map_roster_slots,
    map_scoring_categories,
    match_player,
    match_roster,
)
from backend.services.fantrax.models import (
    LeagueInfo,
    RosterPlayer,
    TeamRoster,
)
from backend.services.fantrax.service import (
    _parse_rosters_response,
    _parse_standings_response,
)

# --- Player matching tests ---


@pytest.fixture()
def player_summary_index():
    return {
        "mike-trout__laa": {"name": "Mike Trout", "team": "LAA", "pos": "CF", "age": 34, "type": "H"},
        "shohei-ohtani__lad": {"name": "Shohei Ohtani", "team": "LAD", "pos": "DH", "age": 31, "type": "H"},
        "vladimir-guerrero-jr__tor": {"name": "Vladimir Guerrero Jr.", "team": "TOR", "pos": "1B", "age": 27, "type": "H"},
        "gerrit-cole__nyy": {"name": "Gerrit Cole", "team": "NYY", "pos": "SP", "age": 35, "type": "P"},
    }


def test_build_player_lookup(player_summary_index):
    name_team_idx, name_only_idx = build_player_lookup(player_summary_index)
    assert ("mike trout", "LAA") in name_team_idx
    assert name_team_idx[("mike trout", "LAA")] == "mike-trout__laa"
    assert "mike trout" in name_only_idx


def test_match_player_exact_name_team(player_summary_index):
    name_team_idx, name_only_idx = build_player_lookup(player_summary_index)
    player = RosterPlayer(fantrax_id="123", name="Mike Trout", position="CF", team="LAA")
    matched = match_player(player, name_team_idx, name_only_idx)
    assert matched.player_entity_key == "mike-trout__laa"
    assert matched.match_method == "name_team"


def test_match_player_name_no_suffix(player_summary_index):
    name_team_idx, name_only_idx = build_player_lookup(player_summary_index)
    player = RosterPlayer(fantrax_id="456", name="Vladimir Guerrero", position="1B", team="TOR")
    matched = match_player(player, name_team_idx, name_only_idx)
    assert matched.player_entity_key == "vladimir-guerrero-jr__tor"
    assert matched.match_method in ("name_team", "name_no_suffix_team")


def test_match_player_name_only(player_summary_index):
    name_team_idx, name_only_idx = build_player_lookup(player_summary_index)
    player = RosterPlayer(fantrax_id="789", name="Gerrit Cole", position="SP", team="NYM")
    matched = match_player(player, name_team_idx, name_only_idx)
    assert matched.player_entity_key == "gerrit-cole__nyy"
    assert matched.match_method == "name_only"


def test_match_player_no_match(player_summary_index):
    name_team_idx, name_only_idx = build_player_lookup(player_summary_index)
    player = RosterPlayer(fantrax_id="000", name="Nonexistent Player", position="OF", team="NYM")
    matched = match_player(player, name_team_idx, name_only_idx)
    assert matched.player_entity_key is None
    assert matched.match_method == "none"


def test_match_roster(player_summary_index):
    name_team_idx, name_only_idx = build_player_lookup(player_summary_index)
    players = [
        RosterPlayer(fantrax_id="1", name="Mike Trout", position="CF", team="LAA"),
        RosterPlayer(fantrax_id="2", name="Unknown Dude", position="OF", team="NYM"),
    ]
    result = match_roster("team1", "Team A", players, name_team_idx, name_only_idx)
    assert result.matched_count == 1
    assert result.total_count == 2


# --- Scoring category mapping ---


def test_map_scoring_categories_roto():
    cats = ["R", "HR", "RBI", "SB", "AVG", "W", "K", "SV", "ERA", "WHIP"]
    result = map_scoring_categories(cats)
    assert result["roto_hit_r"] is True
    assert result["roto_hit_hr"] is True
    assert result["roto_pit_era"] is True
    assert result["roto_hit_obp"] is False  # Not in the list


def test_map_scoring_categories_long_names():
    cats = ["Runs", "Home Runs", "Stolen Bases", "Batting Average", "Wins", "Strikeouts", "Saves", "Earned Run Average", "WHIP"]
    result = map_scoring_categories(cats)
    assert result["roto_hit_r"] is True
    assert result["roto_hit_hr"] is True
    assert result["roto_hit_sb"] is True
    assert result["roto_pit_w"] is True
    assert result["roto_pit_k"] is True


# --- Roster slot mapping ---


def test_map_roster_slots():
    positions = ["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "UT", "SP", "SP", "SP", "RP", "RP"]
    result = map_roster_slots(positions)
    assert result["hit_c"] == 1
    assert result["hit_of"] == 3
    assert result["hit_ut"] == 1
    assert result["pit_sp"] == 3
    assert result["pit_rp"] == 2


# --- Suggested settings ---


def test_build_suggested_settings():
    league = LeagueInfo(
        league_id="abc",
        league_name="Test League",
        teams=[TeamRoster(team_id="1", team_name="T1"), TeamRoster(team_id="2", team_name="T2")],
        team_count=2,
        scoring_type="roto",
        scoring_categories=["R", "HR", "SB", "AVG", "RBI", "W", "K", "SV", "ERA", "WHIP"],
        roster_positions=["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "UT", "P", "P", "P"],
    )
    settings = build_suggested_settings(league)
    assert settings.teams == 2
    assert settings.scoring_mode == "roto"
    assert settings.roto_categories["roto_hit_r"] is True
    assert settings.roster_slots["hit_c"] == 1
    assert settings.roster_slots["pit_p"] == 3


# --- API response parsing ---


def test_parse_rosters_response():
    data = {
        "rosters": {
            "team1": {
                "teamName": "My Team",
                "rosterItems": [
                    {"id": "p1", "name": "Player One", "pos": "CF", "team": "NYY"},
                    {"id": "p2", "name": "Player Two", "position": "1B", "teamAbbrev": "BOS"},
                ],
            }
        }
    }
    teams = _parse_rosters_response(data, "league1")
    assert len(teams) == 1
    assert teams[0].team_name == "My Team"
    assert len(teams[0].players) == 2
    assert teams[0].players[0].name == "Player One"
    assert teams[0].players[1].position == "1B"


def test_parse_standings_response():
    data = {
        "leagueName": "Dynasty League",
        "scoringType": "Rotisserie",
        "scoringCategories": [{"name": "R"}, {"name": "HR"}],
        "rosterPositions": [{"code": "C"}, {"code": "SS"}],
    }
    name, scoring, cats, positions = _parse_standings_response(data)
    assert name == "Dynasty League"
    assert scoring == "roto"
    assert cats == ["R", "HR"]
    assert positions == ["C", "SS"]


def test_parse_standings_response_points():
    data = {"leagueName": "Points League", "scoringType": "Points"}
    name, scoring, cats, positions = _parse_standings_response(data)
    assert scoring == "points"
