"""Tests for player SEO meta tag enrichment."""

from backend.api.routes.frontend_assets import build_player_summary_index


def test_build_player_summary_index_basic():
    bat = [
        {"PlayerEntityKey": "juan-soto", "Player": "Juan Soto", "Team": "Mets", "Pos": "OF", "Age": 27, "Year": 2026},
        {"PlayerEntityKey": "juan-soto", "Player": "Juan Soto", "Team": "Mets", "Pos": "OF", "Age": 28, "Year": 2027},
    ]
    pit = [
        {"PlayerEntityKey": "gerrit-cole", "Player": "Gerrit Cole", "Team": "Yankees", "Pos": "SP", "Age": 35, "Year": 2026},
    ]
    index = build_player_summary_index(bat, pit)
    assert "juan-soto" in index
    assert index["juan-soto"]["name"] == "Juan Soto"
    assert index["juan-soto"]["team"] == "Mets"
    assert index["juan-soto"]["pos"] == "OF"
    assert index["juan-soto"]["age"] == 27
    assert index["juan-soto"]["type"] == "H"

    assert "gerrit-cole" in index
    assert index["gerrit-cole"]["name"] == "Gerrit Cole"
    assert index["gerrit-cole"]["type"] == "P"


def test_build_player_summary_index_hitters_override_pitchers():
    """Two-way players should use the hitter entry."""
    bat = [{"PlayerEntityKey": "shohei-ohtani", "Player": "Shohei Ohtani", "Team": "Dodgers", "Pos": "OF", "Age": 31}]
    pit = [{"PlayerEntityKey": "shohei-ohtani", "Player": "Shohei Ohtani", "Team": "Dodgers", "Pos": "SP", "Age": 31}]
    index = build_player_summary_index(bat, pit)
    assert index["shohei-ohtani"]["type"] == "H"
    assert index["shohei-ohtani"]["pos"] == "OF"


def test_build_player_summary_index_empty_data():
    index = build_player_summary_index([], [])
    assert index == {}


def test_build_player_summary_index_skips_blank_keys():
    bat = [{"PlayerEntityKey": "", "Player": "Nobody"}]
    index = build_player_summary_index(bat, [])
    assert len(index) == 0
