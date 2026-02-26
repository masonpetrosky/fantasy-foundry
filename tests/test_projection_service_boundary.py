from __future__ import annotations

import re

import pytest
from fastapi import HTTPException

from backend.services.projections import ProjectionDynastyHelpers, ProjectionRateLimits
from backend.services.projections import service as projection_service_module
from backend.services.projections.service import ProjectionService, ProjectionServiceContext


def _build_service() -> ProjectionService:
    normalize_player_key = lambda value: str(value or "").strip().lower().replace(" ", "-")
    dynasty_helpers = ProjectionDynastyHelpers(
        year_range_token_re=re.compile(r"^(\d{4})\s*-\s*(\d{4})$"),
        get_default_dynasty_lookup=lambda: ({}, {}, set(), []),
        normalize_player_key=normalize_player_key,
        player_key_col="PlayerKey",
        player_entity_key_col="PlayerEntityKey",
        lookup_required_error_type=RuntimeError,
    )
    ctx = ProjectionServiceContext(
        refresh_data_if_needed=lambda: None,
        get_bat_data=lambda: [],
        get_pit_data=lambda: [],
        get_meta=lambda: {"years": [2026, 2027]},
        normalize_player_key=normalize_player_key,
        dynasty_helpers=dynasty_helpers,
        coerce_meta_years=lambda meta: [2026, 2027],
        tabular_export_response=lambda *args, **kwargs: {"args": args, "kwargs": kwargs},
        calculator_overlay_values_for_job=lambda job_id: {},
        player_key_col="PlayerKey",
        player_entity_key_col="PlayerEntityKey",
        position_token_split_re=re.compile(r"[\s,/]+"),
        position_display_order=("C", "1B", "2B", "3B", "SS", "OF", "SP", "RP"),
        projection_text_sort_cols={"Player", "Team", "Pos", "Type", "Years"},
        all_tab_hitter_stat_cols=("AB", "R", "HR"),
        all_tab_pitch_stat_cols=("IP", "K", "BB", "H", "HR"),
        projection_query_cache_maxsize=4,
        rate_limits=ProjectionRateLimits(read_per_minute=120, export_per_minute=30),
        filter_records=None,
    )
    return ProjectionService(ctx)


def test_default_projection_export_columns_delegates_to_core(monkeypatch) -> None:
    service = _build_service()
    calls: dict[str, object] = {}

    def fake_default_columns(
        rows,
        *,
        dataset,
        career_totals,
        hitter_core_export_cols,
        pitcher_core_export_cols,
        value_col_sort_key_fn,
    ):
        calls["rows"] = rows
        calls["dataset"] = dataset
        calls["career_totals"] = career_totals
        calls["hitter_core_export_cols"] = hitter_core_export_cols
        calls["pitcher_core_export_cols"] = pitcher_core_export_cols
        calls["value_col_sort_key_fn"] = value_col_sort_key_fn
        return ["Player", "DynastyValue"]

    monkeypatch.setattr(projection_service_module, "core_default_projection_export_columns", fake_default_columns)
    rows = [{"Player": "A"}]
    out = service._default_projection_export_columns(rows, dataset="all", career_totals=True)

    assert out == ["Player", "DynastyValue"]
    assert calls["rows"] == rows
    assert calls["dataset"] == "all"
    assert calls["career_totals"] is True
    assert calls["hitter_core_export_cols"] == projection_service_module.PROJECTION_HITTER_CORE_EXPORT_COLS
    assert calls["pitcher_core_export_cols"] == projection_service_module.PROJECTION_PITCHER_CORE_EXPORT_COLS
    sort_key_fn = calls["value_col_sort_key_fn"]
    assert callable(sort_key_fn)
    assert sort_key_fn("Value_2027") == (0, 2027)


def test_aggregate_projection_career_rows_delegates_with_service_adapters(monkeypatch) -> None:
    service = _build_service()
    calls: dict[str, object] = {}

    def fake_aggregate(
        rows,
        *,
        is_hitter,
        career_group_key_fn,
        row_team_value_fn,
        normalize_player_key_fn,
        player_key_col,
        player_entity_key_col,
        position_tokens_fn,
        position_sort_key_fn,
        coerce_record_year_fn,
    ):
        calls["rows"] = rows
        calls["is_hitter"] = is_hitter
        calls["career_group_key"] = career_group_key_fn({"Player": "John Doe"})
        calls["team"] = row_team_value_fn({"Team": "SEA"})
        calls["normalize"] = normalize_player_key_fn("John Doe")
        calls["player_key_col"] = player_key_col
        calls["player_entity_key_col"] = player_entity_key_col
        calls["tokens"] = position_tokens_fn("1B/OF")
        calls["position_sort_key"] = position_sort_key_fn("1B")
        calls["year"] = coerce_record_year_fn("2027")
        return [{"Player": "John Doe", "Year": None}]

    monkeypatch.setattr(projection_service_module, "core_aggregate_projection_career_rows", fake_aggregate)
    out = service._aggregate_projection_career_rows([{"Player": "John Doe", "Year": 2027}], is_hitter=True)

    assert out == [{"Player": "John Doe", "Year": None}]
    assert calls["is_hitter"] is True
    assert calls["career_group_key"] == "john-doe"
    assert calls["team"] == "SEA"
    assert calls["normalize"] == "john-doe"
    assert calls["player_key_col"] == "PlayerKey"
    assert calls["player_entity_key_col"] == "PlayerEntityKey"
    assert calls["tokens"] == {"1B", "OF"}
    assert calls["position_sort_key"] == (1, "1B")
    assert calls["year"] == 2027


def test_aggregate_all_projection_career_rows_delegates_and_uses_callback(monkeypatch) -> None:
    service = _build_service()
    calls: dict[str, object] = {}

    def fake_aggregate_one(rows, *, is_hitter):
        calls.setdefault("aggregate_one_calls", []).append((rows, is_hitter))
        return [{"rows_seen": len(rows), "is_hitter": is_hitter}]

    def fake_aggregate_all(
        hit_rows,
        pit_rows,
        *,
        aggregate_projection_career_rows_fn,
        career_group_key_fn,
        row_team_value_fn,
        merge_position_value_fn,
        coerce_record_year_fn,
        all_tab_hitter_stat_cols,
        all_tab_pitch_stat_cols,
    ):
        calls["hit_rows"] = hit_rows
        calls["pit_rows"] = pit_rows
        calls["hitter_result"] = aggregate_projection_career_rows_fn([{"Player": "A"}], True)
        calls["pitcher_result"] = aggregate_projection_career_rows_fn([{"Player": "B"}], False)
        calls["career_group_key"] = career_group_key_fn({"Player": "X Y"})
        calls["team"] = row_team_value_fn({"MLBTeam": "LAD"})
        calls["pos"] = merge_position_value_fn("OF", "SP")
        calls["year"] = coerce_record_year_fn("2026")
        calls["h_cols"] = all_tab_hitter_stat_cols
        calls["p_cols"] = all_tab_pitch_stat_cols
        return [{"Player": "A", "Type": "H/P"}]

    monkeypatch.setattr(service, "_aggregate_projection_career_rows", fake_aggregate_one)
    monkeypatch.setattr(projection_service_module, "core_aggregate_all_projection_career_rows", fake_aggregate_all)

    out = service._aggregate_all_projection_career_rows([{"Player": "A"}], [{"Player": "B"}])

    assert out == [{"Player": "A", "Type": "H/P"}]
    assert calls["hit_rows"] == [{"Player": "A"}]
    assert calls["pit_rows"] == [{"Player": "B"}]
    assert calls["aggregate_one_calls"] == [([{"Player": "A"}], True), ([{"Player": "B"}], False)]
    assert calls["hitter_result"] == [{"rows_seen": 1, "is_hitter": True}]
    assert calls["pitcher_result"] == [{"rows_seen": 1, "is_hitter": False}]
    assert calls["career_group_key"] == "x-y"
    assert calls["team"] == "LAD"
    assert calls["pos"] == "OF/SP"
    assert calls["year"] == 2026
    assert calls["h_cols"] == ("AB", "R", "HR")
    assert calls["p_cols"] == ("IP", "K", "BB", "H", "HR")


def test_sort_validate_overlay_and_merge_delegates(monkeypatch) -> None:
    service = _build_service()
    calls: dict[str, object] = {}

    def fake_validate(sort_col, *, dataset, normalize_filter_value_fn, sortable_columns_for_dataset_fn):
        calls["validate"] = (
            sort_col,
            dataset,
            normalize_filter_value_fn("  Team "),
            sortable_columns_for_dataset_fn("bat"),
        )
        return "Team"

    def fake_overlay(
        rows,
        *,
        include_dynasty,
        calculator_job_id,
        normalize_filter_value_fn,
        calculator_overlay_values_for_job_fn,
        row_overlay_lookup_key_fn,
    ):
        calls["overlay"] = (
            rows,
            include_dynasty,
            calculator_job_id,
            normalize_filter_value_fn("  job-1 "),
            calculator_overlay_values_for_job_fn("job-1"),
            row_overlay_lookup_key_fn({"PlayerEntityKey": "A"}),
        )
        return [{"PlayerEntityKey": "a", "DynastyValue": 9.0}]

    def fake_sort(rows, sort_col, sort_dir, *, projection_text_sort_cols, player_key_col, player_entity_key_col):
        calls["sort"] = (rows, sort_col, sort_dir, projection_text_sort_cols, player_key_col, player_entity_key_col)
        return list(reversed(rows))

    def fake_merge(
        hit_rows,
        pit_rows,
        *,
        projection_merge_key_fn,
        row_team_value_fn,
        merge_position_value_fn,
        all_tab_hitter_stat_cols,
        all_tab_pitch_stat_cols,
    ):
        calls["merge"] = (
            hit_rows,
            pit_rows,
            projection_merge_key_fn({"PlayerEntityKey": "x", "Year": "2026", "Team": "lad"}),
            row_team_value_fn({"MLBTeam": "BOS"}),
            merge_position_value_fn("OF", "RP"),
            all_tab_hitter_stat_cols,
            all_tab_pitch_stat_cols,
        )
        return [{"Player": "Merged"}]

    monkeypatch.setattr(projection_service_module, "core_validate_sort_col", fake_validate)
    monkeypatch.setattr(projection_service_module, "core_apply_calculator_overlay_values", fake_overlay)
    monkeypatch.setattr(projection_service_module, "core_sort_projection_rows", fake_sort)
    monkeypatch.setattr(projection_service_module, "core_merge_all_projection_rows", fake_merge)

    sort_col = service._validate_sort_col("Team", dataset="bat")
    overlay_rows = service._apply_calculator_overlay_values(
        [{"PlayerEntityKey": "a", "DynastyValue": 1.0}],
        include_dynasty=True,
        calculator_job_id="job-1",
    )
    sorted_rows = service._sort_projection_rows(
        [{"Player": "A"}, {"Player": "B"}],
        "Player",
        "asc",
    )
    merged_rows = service._merge_all_projection_rows([{"Player": "A"}], [{"Player": "B"}])

    assert sort_col == "Team"
    assert calls["validate"][0:3] == ("Team", "bat", "Team")
    assert "Player" in calls["validate"][3]

    assert overlay_rows == [{"PlayerEntityKey": "a", "DynastyValue": 9.0}]
    assert calls["overlay"][1:4] == (True, "job-1", "job-1")
    assert calls["overlay"][5] == "a"

    assert sorted_rows == [{"Player": "B"}, {"Player": "A"}]
    assert calls["sort"][1:4] == ("Player", "asc", {"Player", "Team", "Pos", "Type", "Years"})
    assert calls["sort"][4:6] == ("PlayerKey", "PlayerEntityKey")

    assert merged_rows == [{"Player": "Merged"}]
    assert calls["merge"][2] == ("x", 2026, "LAD")
    assert calls["merge"][3] == "BOS"
    assert calls["merge"][4] == "OF/RP"
    assert calls["merge"][5] == ("AB", "R", "HR")
    assert calls["merge"][6] == ("IP", "K", "BB", "H", "HR")


def test_projection_profile_builds_summary_from_series_and_career_totals(monkeypatch) -> None:
    service = _build_service()
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_projection_response(dataset: str, **kwargs):
        calls.append((dataset, kwargs))
        if kwargs.get("career_totals"):
            return {
                "total": 1,
                "offset": 0,
                "limit": 5000,
                "data": [
                    {
                        "Player": "Jane Roe",
                        "Team": "SEA",
                        "Pos": "OF",
                        "PlayerKey": "jane-roe",
                        "PlayerEntityKey": "jane-roe",
                        "DynastyValue": 10.0,
                    }
                ],
            }
        return {
            "total": 2,
            "offset": 0,
            "limit": 5000,
            "data": [
                {"Player": "Jane Roe", "Year": 2026, "PlayerEntityKey": "jane-roe"},
                {"Player": "Jane Roe", "Year": 2027, "PlayerEntityKey": "jane-roe"},
            ],
        }

    monkeypatch.setattr(service, "projection_response", fake_projection_response)
    payload = service.projection_profile(player_id="jane-roe", dataset="all", include_dynasty=True)

    assert payload["player_id"] == "jane-roe"
    assert payload["series_total"] == 2
    assert payload["career_totals_total"] == 1
    assert len(payload["series"]) == 2
    assert len(payload["career_totals"]) == 1
    assert payload["matched_players"] == [
        {
            "player_entity_key": "jane-roe",
            "player_key": "jane-roe",
            "player": "Jane Roe",
            "team": "SEA",
            "pos": "OF",
        }
    ]
    assert calls[0][1]["career_totals"] is False
    assert calls[1][1]["career_totals"] is True


def test_projection_compare_requires_two_player_keys() -> None:
    service = _build_service()

    with pytest.raises(HTTPException, match="at least two"):
        service.projection_compare(player_keys="jane-roe", dataset="all")


def test_projection_compare_returns_matched_identity_keys(monkeypatch) -> None:
    service = _build_service()
    seen: dict[str, object] = {}

    def fake_projection_response(dataset: str, **kwargs):
        seen["dataset"] = dataset
        seen["player_keys"] = kwargs.get("player_keys")
        seen["career_totals"] = kwargs.get("career_totals")
        seen["year"] = kwargs.get("year")
        seen["years"] = kwargs.get("years")
        seen["dynasty_years"] = kwargs.get("dynasty_years")
        return {
            "total": 2,
            "offset": 0,
            "limit": 5000,
            "data": [
                {"PlayerEntityKey": "jane-roe", "PlayerKey": "jane-roe", "DynastyValue": 10.0},
                {"PlayerEntityKey": "john-roe", "PlayerKey": "john-roe", "DynastyValue": 8.0},
            ],
        }

    monkeypatch.setattr(service, "projection_response", fake_projection_response)
    payload = service.projection_compare(
        player_keys="john-roe, jane-roe",
        dataset="all",
        career_totals=False,
        year=2027,
        years="2026,2027",
        dynasty_years="2027",
    )

    assert seen["dataset"] == "all"
    assert seen["player_keys"] == "jane-roe,john-roe"
    assert seen["career_totals"] is False
    assert seen["year"] == 2027
    assert seen["years"] == "2026,2027"
    assert seen["dynasty_years"] == "2027"
    assert payload["requested_player_keys"] == ["jane-roe", "john-roe"]
    assert payload["matched_player_keys"] == ["jane-roe", "john-roe"]
    assert payload["total"] == 2


def test_projection_compare_ignores_year_filters_in_career_totals_mode(monkeypatch) -> None:
    service = _build_service()
    seen: dict[str, object] = {}

    def fake_projection_response(dataset: str, **kwargs):
        seen["year"] = kwargs.get("year")
        seen["years"] = kwargs.get("years")
        seen["career_totals"] = kwargs.get("career_totals")
        return {"total": 0, "offset": 0, "limit": 5000, "data": []}

    monkeypatch.setattr(service, "projection_response", fake_projection_response)
    payload = service.projection_compare(
        player_keys="john-roe, jane-roe",
        dataset="all",
        career_totals=True,
        year=2027,
        years="2026,2027",
    )

    assert seen["career_totals"] is True
    assert seen["year"] is None
    assert seen["years"] is None
    assert payload["career_totals"] is True
