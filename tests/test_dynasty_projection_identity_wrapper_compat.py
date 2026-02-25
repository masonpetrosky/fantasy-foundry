from __future__ import annotations

import pandas as pd

from backend import dynasty_roto_values
from backend.valuation import projection_identity


def test_wrapper_identity_constants_alias_extracted_module() -> None:
    assert dynasty_roto_values.PROJECTION_DATE_COLS == projection_identity.PROJECTION_DATE_COLS
    assert dynasty_roto_values.PLAYER_KEY_COL == projection_identity.PLAYER_KEY_COL
    assert dynasty_roto_values.PLAYER_ENTITY_KEY_COL == projection_identity.PLAYER_ENTITY_KEY_COL
    assert dynasty_roto_values.PLAYER_KEY_PATTERN.pattern == projection_identity.PLAYER_KEY_PATTERN.pattern


def test_wrapper_find_projection_date_col_delegates(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_find(df: pd.DataFrame):
        calls["df"] = df
        return "Date"

    monkeypatch.setattr(projection_identity, "_find_projection_date_col", fake_find)
    frame = pd.DataFrame([{"Date": "2026-01-01"}])
    out = dynasty_roto_values._find_projection_date_col(frame)

    assert out == "Date"
    assert calls["df"] is frame


def test_wrapper_normalizers_delegate(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_player(value: object) -> str:
        calls["player"] = value
        return "player-key"

    def fake_team(value: object) -> str:
        calls["team"] = value
        return "TEAM"

    def fake_year(value: object) -> str:
        calls["year"] = value
        return "2026"

    monkeypatch.setattr(projection_identity, "_normalize_player_key", fake_player)
    monkeypatch.setattr(projection_identity, "_normalize_team_key", fake_team)
    monkeypatch.setattr(projection_identity, "_normalize_year_key", fake_year)

    assert dynasty_roto_values._normalize_player_key("John Doe") == "player-key"
    assert dynasty_roto_values._normalize_team_key("sea") == "TEAM"
    assert dynasty_roto_values._normalize_year_key("2026.0") == "2026"
    assert calls == {"player": "John Doe", "team": "sea", "year": "2026.0"}


def test_wrapper_identity_dataframe_helpers_delegate(monkeypatch) -> None:
    calls: dict[str, object] = {}
    bat = pd.DataFrame([{"Player": "A"}])
    pit = pd.DataFrame([{"Player": "B"}])
    out = pd.DataFrame([{"Player": "a"}])
    lookup = pd.DataFrame([{"PlayerEntityKey": "a", "PlayerKey": "a", "Player": "A"}])

    def fake_team_column(df: pd.DataFrame):
        calls["team_column"] = df
        return "Team"

    def fake_add_keys(bat_df: pd.DataFrame, pit_df: pd.DataFrame):
        calls["add_keys"] = (bat_df, pit_df)
        return bat_df, pit_df

    def fake_lookup(bat_df: pd.DataFrame, pit_df: pd.DataFrame):
        calls["lookup"] = (bat_df, pit_df)
        return lookup

    def fake_attach(values_df: pd.DataFrame, identity_lookup: pd.DataFrame):
        calls["attach"] = (values_df, identity_lookup)
        return out

    monkeypatch.setattr(projection_identity, "_team_column_for_dataframe", fake_team_column)
    monkeypatch.setattr(projection_identity, "_add_player_identity_keys", fake_add_keys)
    monkeypatch.setattr(projection_identity, "_build_player_identity_lookup", fake_lookup)
    monkeypatch.setattr(projection_identity, "_attach_identity_columns_to_output", fake_attach)

    assert dynasty_roto_values._team_column_for_dataframe(bat) == "Team"
    bat_out, pit_out = dynasty_roto_values._add_player_identity_keys(bat, pit)
    lookup_out = dynasty_roto_values._build_player_identity_lookup(bat, pit)
    attached = dynasty_roto_values._attach_identity_columns_to_output(out, lookup)

    assert calls["team_column"] is bat
    assert calls["add_keys"] == (bat, pit)
    assert bat_out is bat
    assert pit_out is pit
    assert calls["lookup"] == (bat, pit)
    assert lookup_out is lookup
    assert calls["attach"] == (out, lookup)
    assert attached is out
