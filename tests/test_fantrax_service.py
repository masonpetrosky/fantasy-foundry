"""Tests for Fantrax league integration service and mapping."""

import pytest

from backend.services.fantrax.mapping import (
    build_player_lookup,
    build_suggested_settings,
    extract_reserve_slot_counts,
    map_points_scoring,
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


def test_extract_reserve_slot_counts():
    bench, minors, ir = extract_reserve_slot_counts(["C", "OF", "BN", "BN", "NA", "IL", "IL"])
    assert bench == 2
    assert minors == 1
    assert ir == 2


def test_map_points_scoring_handles_total_bases_holds_and_hbp():
    mapped, warnings = map_points_scoring(
        [
            {"name": "R", "value": 1.0, "scope": "batting"},
            {"name": "TB", "value": 1.0, "scope": "batting"},
            {"name": "K", "value": -1.0, "scope": "batting"},
            {"name": "HBP", "value": 1.0, "scope": "batting"},
            {"name": "IP", "value": 3.0, "scope": "pitching"},
            {"name": "HD", "value": 2.0, "scope": "pitching"},
            {"name": "HB", "value": -1.0, "scope": "pitching"},
        ]
    )
    assert warnings == []
    assert mapped["pts_hit_r"] == 1.0
    assert mapped["pts_hit_1b"] == 1.0
    assert mapped["pts_hit_2b"] == 2.0
    assert mapped["pts_hit_3b"] == 3.0
    assert mapped["pts_hit_hr"] == 4.0
    assert mapped["pts_hit_so"] == -1.0
    assert mapped["pts_hit_hbp"] == 1.0
    assert mapped["pts_pit_ip"] == 3.0
    assert mapped["pts_pit_hld"] == 2.0
    assert mapped["pts_pit_hbp"] == -1.0


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


def test_build_suggested_settings_points_league_carries_weekly_rules():
    league = LeagueInfo(
        league_id="pts",
        league_name="Points League",
        team_count=12,
        scoring_type="points",
        scoring_categories=["R", "TB", "IP"],
        roster_positions=["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "DH", "UTIL", "P", "P", "P", "P", "P", "P", "P", "BN", "BN", "IL"],
        points_scoring={"pts_hit_r": 1.0, "pts_pit_ip": 3.0},
        bench=2,
        minors=0,
        ir=1,
        keeper_limit=7,
        points_valuation_mode="weekly_h2h",
        weekly_starts_cap=12,
        allow_same_day_starts_overflow=True,
        weekly_acquisition_cap=7,
        import_warnings=["weekly review"],
    )
    settings = build_suggested_settings(league)
    assert settings.scoring_mode == "points"
    assert settings.points_scoring["pts_hit_r"] == 1.0
    assert settings.bench == 2
    assert settings.ir == 1
    assert settings.keeper_limit == 7
    assert settings.points_valuation_mode == "weekly_h2h"
    assert settings.weekly_starts_cap == 12
    assert settings.allow_same_day_starts_overflow is True
    assert settings.weekly_acquisition_cap == 7
    assert settings.import_warnings == ["weekly review"]


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
