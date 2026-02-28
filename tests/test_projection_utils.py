import re

from backend.core import projection_utils


def test_position_tokens_and_sort_key():
    split_re = re.compile(r"[\s/]+")
    tokens = projection_utils.position_tokens("of/1b sp", split_re=split_re)
    assert tokens == {"OF", "1B", "SP"}
    assert projection_utils.position_sort_key("SP", display_order=("C", "1B", "OF", "SP")) == (3, "SP")


def test_merge_position_value_prefers_sorted_tokens_then_text_fallback():
    split_re = re.compile(r"[\s/]+")
    merged = projection_utils.merge_position_value(
        "OF/1B",
        "SP",
        split_re=split_re,
        display_order=("C", "1B", "OF", "SP"),
    )
    assert merged == "1B/OF/SP"

    assert projection_utils.merge_position_value(
        "",
        "RP",
        split_re=split_re,
        display_order=("C", "1B", "OF", "SP", "RP"),
    ) == "RP"


def test_row_team_value_prefers_team_then_mlbteam():
    assert projection_utils.row_team_value({"Team": "ATL", "MLBTeam": "NYY"}) == "ATL"
    assert projection_utils.row_team_value({"MLBTeam": "NYY"}) == "NYY"


def test_oldest_projection_date_returns_oldest_valid_date_then_text_fallback():
    assert projection_utils.oldest_projection_date("2026-03-01", "2025-12-31", "not-a-date") == "2025-12-31"
    assert projection_utils.oldest_projection_date("", "unknown") == "unknown"
    assert projection_utils.oldest_projection_date("", None) is None


def test_coerce_numeric_handles_invalid_and_nan_values():
    assert projection_utils.coerce_numeric("4.2") == 4.2
    assert projection_utils.coerce_numeric(True) is None
    assert projection_utils.coerce_numeric("nan") is None
