from __future__ import annotations

from backend.core.projections_aggregation import (
    aggregate_all_projection_career_rows,
    aggregate_projection_career_rows,
    merge_all_projection_rows,
)


def _normalize_player_key(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "-")


def _career_group_key(player_key_col: str, player_entity_key_col: str, row: dict) -> str:
    player_name = str(row.get("Player", "")).strip()
    player_key = str(row.get(player_key_col) or "").strip() or _normalize_player_key(player_name)
    return str(row.get(player_entity_key_col) or "").strip() or player_key


def _row_team_value(row: dict) -> str:
    return str(row.get("Team") or row.get("MLBTeam") or "").strip()


def _position_tokens(value: object) -> set[str]:
    text = str(value or "").strip().upper()
    if not text:
        return set()
    out = set()
    for token in text.replace(",", "/").split("/"):
        token = token.strip()
        if token:
            out.add(token)
    return out


def _position_sort_key(token: str) -> tuple[int, str]:
    order = {"C": 0, "1B": 1, "2B": 2, "3B": 3, "SS": 4, "OF": 5, "SP": 6, "RP": 7}
    return (order.get(token, len(order)), token)


def _coerce_record_year(value: object) -> int | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return int(parsed) if parsed.is_integer() else None


def _merge_position_value(hit_pos: object, pit_pos: object) -> str | None:
    tokens = _position_tokens(hit_pos) | _position_tokens(pit_pos)
    if tokens:
        return "/".join(sorted(tokens, key=_position_sort_key))
    hit_text = str(hit_pos or "").strip()
    pit_text = str(pit_pos or "").strip()
    return hit_text or pit_text or None


def _projection_merge_key(player_entity_key_col: str, player_key_col: str, row: dict) -> tuple[str, object, str]:
    player = str(
        row.get(player_entity_key_col)
        or row.get(player_key_col)
        or row.get("Player", "")
    ).strip()
    year = _coerce_record_year(row.get("Year"))
    merge_year = year if year is not None else str(row.get("Year", "")).strip()
    team = _row_team_value(row).upper()
    return (player, merge_year, team)


def test_aggregate_projection_career_rows_hitter_rolls_up_years_and_stats() -> None:
    rows = [
        {
            "Player": "John Doe",
            "Team": "SEA",
            "Pos": "1B/OF",
            "Year": 2026,
            "Age": 24,
            "AB": 100,
            "H": 30,
            "2B": 5,
            "3B": 1,
            "HR": 4,
            "R": 20,
            "RBI": 18,
            "SB": 3,
            "BB": 8,
            "HBP": 1,
            "SF": 2,
            "SO": 22,
            "OldestProjectionDate": "2025-12-01",
            "PlayerKey": "john-doe",
            "PlayerEntityKey": "john-doe",
        },
        {
            "Player": "John Doe",
            "Team": "SEA",
            "Pos": "OF",
            "Year": 2027,
            "Age": 25,
            "AB": 120,
            "H": 36,
            "2B": 7,
            "3B": 0,
            "HR": 6,
            "R": 24,
            "RBI": 22,
            "SB": 4,
            "BB": 10,
            "HBP": 2,
            "SF": 3,
            "SO": 24,
            "OldestProjectionDate": "2025-11-15",
            "PlayerKey": "john-doe",
            "PlayerEntityKey": "john-doe",
        },
    ]

    out = aggregate_projection_career_rows(
        rows,
        is_hitter=True,
        career_group_key_fn=lambda row: _career_group_key("PlayerKey", "PlayerEntityKey", row),
        row_team_value_fn=_row_team_value,
        normalize_player_key_fn=_normalize_player_key,
        player_key_col="PlayerKey",
        player_entity_key_col="PlayerEntityKey",
        position_tokens_fn=_position_tokens,
        position_sort_key_fn=_position_sort_key,
        coerce_record_year_fn=_coerce_record_year,
    )

    assert len(out) == 1
    row = out[0]
    assert row["Year"] is None
    assert row["YearStart"] == 2026
    assert row["YearEnd"] == 2027
    assert row["Years"] == "2026-2027"
    assert row["OldestProjectionDate"] == "2025-11-15"
    assert row["AB"] == 220.0
    assert row["H"] == 66.0
    assert row["AVG"] == 66.0 / 220.0
    assert row["Pos"] == "1B/OF"


def test_aggregate_all_projection_career_rows_merges_hit_and_pitch_side_data() -> None:
    hit_rows = [
        {
            "Player": "Two Way",
            "Team": "LAD",
            "Pos": "OF",
            "Year": 2026,
            "AB": 50,
            "H": 15,
            "R": 10,
            "HR": 3,
            "RBI": 12,
            "SB": 2,
            "BB": 5,
            "SO": 10,
            "AVG": 0.3,
            "OPS": 0.8,
            "OldestProjectionDate": "2025-12-20",
            "PlayerKey": "two-way",
            "PlayerEntityKey": "two-way",
        }
    ]
    pit_rows = [
        {
            "Player": "Two Way",
            "Team": "LAD",
            "Pos": "SP",
            "Year": 2026,
            "IP": 30,
            "W": 2,
            "K": 35,
            "SV": 0,
            "SVH": 0,
            "ERA": 3.2,
            "WHIP": 1.1,
            "QS": 2,
            "QA3": 2,
            "H": 25,
            "HR": 3,
            "BB": 8,
            "ER": 11,
            "OldestProjectionDate": "2025-12-25",
            "PlayerKey": "two-way",
            "PlayerEntityKey": "two-way",
        }
    ]

    out = aggregate_all_projection_career_rows(
        hit_rows,
        pit_rows,
        aggregate_projection_career_rows_fn=lambda rows, is_hitter: aggregate_projection_career_rows(
            rows,
            is_hitter=is_hitter,
            career_group_key_fn=lambda row: _career_group_key("PlayerKey", "PlayerEntityKey", row),
            row_team_value_fn=_row_team_value,
            normalize_player_key_fn=_normalize_player_key,
            player_key_col="PlayerKey",
            player_entity_key_col="PlayerEntityKey",
            position_tokens_fn=_position_tokens,
            position_sort_key_fn=_position_sort_key,
            coerce_record_year_fn=_coerce_record_year,
        ),
        career_group_key_fn=lambda row: _career_group_key("PlayerKey", "PlayerEntityKey", row),
        row_team_value_fn=_row_team_value,
        merge_position_value_fn=_merge_position_value,
        coerce_record_year_fn=_coerce_record_year,
        all_tab_hitter_stat_cols=("AB", "H", "R", "HR", "RBI", "SB", "BB", "SO", "AVG", "OPS"),
        all_tab_pitch_stat_cols=("IP", "W", "K", "SV", "SVH", "ERA", "WHIP", "QS", "QA3", "ER"),
    )

    assert len(out) == 1
    row = out[0]
    assert row["Type"] == "H/P"
    assert row["Team"] == "LAD"
    assert row["Pos"] == "OF/SP"
    assert row["AB"] == 50.0
    assert row["IP"] == 30.0
    assert row["PitH"] == 25.0
    assert row["PitHR"] == 3.0
    assert row["PitBB"] == 8.0


def test_merge_all_projection_rows_keeps_hitter_and_pitcher_fields_separate() -> None:
    hit_rows = [
        {
            "Player": "Hybrid",
            "Team": "NYM",
            "Pos": "OF",
            "Year": 2026,
            "H": 40,
            "AB": 120,
            "R": 18,
            "HR": 7,
            "RBI": 22,
            "SB": 4,
            "BB": 11,
            "SO": 25,
            "AVG": 0.333,
            "OPS": 0.91,
            "OldestProjectionDate": "2025-12-05",
            "PlayerKey": "hybrid",
            "PlayerEntityKey": "hybrid",
        }
    ]
    pit_rows = [
        {
            "Player": "Hybrid",
            "Team": "NYM",
            "Pos": "RP",
            "Year": 2026,
            "IP": 22,
            "W": 1,
            "K": 28,
            "SV": 10,
            "SVH": 12,
            "ERA": 2.9,
            "WHIP": 1.02,
            "QS": 0,
            "QA3": 0,
            "H": 14,
            "HR": 1,
            "BB": 6,
            "ER": 7,
            "OldestProjectionDate": "2025-12-10",
            "PlayerKey": "hybrid",
            "PlayerEntityKey": "hybrid",
        }
    ]

    out = merge_all_projection_rows(
        hit_rows,
        pit_rows,
        projection_merge_key_fn=lambda row: _projection_merge_key("PlayerEntityKey", "PlayerKey", row),
        row_team_value_fn=_row_team_value,
        merge_position_value_fn=_merge_position_value,
        all_tab_hitter_stat_cols=("AB", "H", "R", "HR", "RBI", "SB", "BB", "SO", "AVG", "OPS"),
        all_tab_pitch_stat_cols=("IP", "W", "K", "SV", "SVH", "ERA", "WHIP", "QS", "QA3", "ER"),
    )

    assert len(out) == 1
    row = out[0]
    assert row["Type"] == "H/P"
    assert row["H"] == 40
    assert row["IP"] == 22
    assert row["PitH"] == 14
    assert row["PitHR"] == 1
    assert row["PitBB"] == 6
