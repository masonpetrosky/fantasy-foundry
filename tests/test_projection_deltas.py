"""Tests for projection delta (week-over-week change tracking)."""

from backend.services.projections.delta import (
    _aggregate_player_stats,
    compute_projection_deltas,
    empty_delta_response,
)


def _make_bat_rows(player, team, pos, stats_by_year):
    """Helper to create bat projection rows."""
    rows = []
    for year, stats in stats_by_year.items():
        row = {
            "Player": player,
            "Team": team,
            "Pos": pos,
            "Year": year,
            "PlayerEntityKey": player.lower().replace(" ", "-"),
            "PlayerKey": player.lower().replace(" ", "-"),
            "AB": stats.get("AB", 500),
        }
        row.update(stats)
        rows.append(row)
    return rows


def _make_pit_rows(player, team, pos, stats_by_year):
    """Helper to create pitch projection rows."""
    rows = []
    for year, stats in stats_by_year.items():
        row = {
            "Player": player,
            "Team": team,
            "Pos": pos,
            "Year": year,
            "PlayerEntityKey": player.lower().replace(" ", "-"),
            "PlayerKey": player.lower().replace(" ", "-"),
            "IP": stats.get("IP", 180),
        }
        row.update(stats)
        rows.append(row)
    return rows


def test_compute_projection_deltas_hitter_riser():
    curr_bat = _make_bat_rows("Juan Soto", "Mets", "OF", {
        2026: {"HR": 40, "R": 100, "RBI": 110, "SB": 5, "AVG": 0.300, "OPS": 0.950, "AB": 550},
    })
    prev_bat = _make_bat_rows("Juan Soto", "Mets", "OF", {
        2026: {"HR": 35, "R": 90, "RBI": 100, "SB": 5, "AVG": 0.290, "OPS": 0.920, "AB": 550},
    })
    result = compute_projection_deltas(curr_bat, [], prev_bat, [])
    assert result["has_previous"] is True
    assert len(result["risers"]) > 0
    assert result["risers"][0]["key"] == "juan-soto"
    assert result["risers"][0]["composite_delta"] > 0


def test_compute_projection_deltas_pitcher_faller():
    curr_pit = _make_pit_rows("Gerrit Cole", "Yankees", "SP", {
        2026: {"K": 200, "W": 12, "SV": 0, "ERA": 3.80, "WHIP": 1.20, "IP": 180},
    })
    prev_pit = _make_pit_rows("Gerrit Cole", "Yankees", "SP", {
        2026: {"K": 220, "W": 15, "SV": 0, "ERA": 3.20, "WHIP": 1.05, "IP": 180},
    })
    result = compute_projection_deltas([], curr_pit, [], prev_pit)
    assert result["has_previous"] is True
    assert len(result["fallers"]) > 0
    assert result["fallers"][0]["key"] == "gerrit-cole"
    assert result["fallers"][0]["composite_delta"] < 0


def test_compute_projection_deltas_no_overlap():
    """New players without previous data should not appear in deltas."""
    curr_bat = _make_bat_rows("New Player", "Team", "OF", {
        2026: {"HR": 30, "R": 80, "RBI": 90, "SB": 10, "AVG": 0.280, "OPS": 0.860, "AB": 500},
    })
    result = compute_projection_deltas(curr_bat, [], [], [])
    assert result["has_previous"] is True
    assert len(result["risers"]) == 0
    assert len(result["fallers"]) == 0


def test_empty_delta_response():
    result = empty_delta_response()
    assert result["has_previous"] is False
    assert result["risers"] == []
    assert result["fallers"] == []
    assert result["delta_map"] == {}


def test_delta_map_contains_composite():
    curr_bat = _make_bat_rows("Player A", "Team", "OF", {
        2026: {"HR": 30, "R": 80, "RBI": 90, "SB": 10, "AVG": 0.280, "OPS": 0.860, "AB": 500},
    })
    prev_bat = _make_bat_rows("Player A", "Team", "OF", {
        2026: {"HR": 25, "R": 75, "RBI": 85, "SB": 10, "AVG": 0.270, "OPS": 0.840, "AB": 500},
    })
    result = compute_projection_deltas(curr_bat, [], prev_bat, [])
    assert "player-a" in result["delta_map"]
    assert "composite_delta" in result["delta_map"]["player-a"]


def test_aggregate_player_stats_rate_weighted():
    """Rate stats should be weighted by AB/IP."""
    rows = [
        {"PlayerEntityKey": "player-a", "Player": "A", "Team": "T", "Pos": "OF",
         "AB": 500, "AVG": 0.300, "HR": 30},
        {"PlayerEntityKey": "player-a", "Player": "A", "Team": "T", "Pos": "OF",
         "AB": 100, "AVG": 0.200, "HR": 5},
    ]
    result = _aggregate_player_stats(rows, stat_cols=("HR", "AVG"), player_type="H")
    # HR should be sum: 35
    assert result["player-a"]["HR"] == 35.0
    # AVG should be weighted: (0.300*500 + 0.200*100) / 600 ≈ 0.283
    assert abs(result["player-a"]["AVG"] - 0.283) < 0.001
