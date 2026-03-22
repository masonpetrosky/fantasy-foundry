from __future__ import annotations

import pytest

from backend.core.points_audit_review import (
    render_points_audit_markdown,
    render_points_audit_memo_markdown,
    review_points_audit,
)
from scripts.report_default_dynasty_divergence import _deep_roto_params, _points_profile_params

pytestmark = pytest.mark.valuation


def _profile_snapshot(*, mode: str, fingerprint: str) -> dict:
    return {
        "rows": [],
        "explanations": {},
        "valuation_diagnostics": {
            "PointsValuationMode": mode,
            "ReplacementRank": 1,
            "InSeasonReplacementRank": 1,
            "KeeperLimit": None,
        },
        "settings_snapshot": {"points_valuation_mode": mode},
        "methodology_fingerprint": fingerprint,
    }


def _player_key(player: str) -> str:
    return str(player).lower().replace(" ", "-")


def _points_player_row(
    *,
    player: str,
    pos: str,
    dynasty_value: float,
    selected_points: float,
    raw_dynasty_value: float | None = None,
    pitching_usage_share: float | None = None,
    pitching_assigned_starts: float | None = None,
    pitching_assigned_ip: float | None = None,
    minor_eligible: bool = False,
) -> tuple[dict, dict]:
    player_key = _player_key(player)
    row = {
        "Player": player,
        "PlayerKey": player_key,
        "PlayerEntityKey": player_key,
        "Team": "SEA",
        "Pos": pos,
        "DynastyValue": dynasty_value,
        "RawDynastyValue": dynasty_value if raw_dynasty_value is None else raw_dynasty_value,
        "SelectedPoints": selected_points,
        "minor_eligible": minor_eligible,
    }
    points = {"selected_points": selected_points}
    if pitching_usage_share is not None:
        points["pitching_usage_share"] = pitching_usage_share
    if pitching_assigned_starts is not None:
        points["pitching_assigned_starts"] = pitching_assigned_starts
    if pitching_assigned_ip is not None:
        points["pitching_assigned_ip"] = pitching_assigned_ip
    explanation = {player_key: {"per_year": [{"year": 2026, "points": points}]}}
    return row, explanation


def _merge_explanations(*maps: dict) -> dict:
    merged: dict = {}
    for item in maps:
        merged.update(item)
    return merged


def _scenario_snapshot(
    *,
    rows_with_explanations: list[tuple[dict, dict]],
    mode: str,
    replacement_rank: int,
    in_season_replacement_rank: int,
    keeper_limit: int | None = None,
    extra_diagnostics: dict | None = None,
    fingerprint: str = "scenario123",
    settings_snapshot: dict | None = None,
) -> dict:
    diagnostics = {
        "PointsValuationMode": mode,
        "ReplacementRank": replacement_rank,
        "InSeasonReplacementRank": in_season_replacement_rank,
        "KeeperLimit": keeper_limit,
    }
    if isinstance(extra_diagnostics, dict):
        diagnostics.update(extra_diagnostics)
    rows = [row for row, _ in rows_with_explanations]
    explanations = _merge_explanations(*(explanation for _, explanation in rows_with_explanations))
    return {
        "rows": rows,
        "explanations": explanations,
        "valuation_diagnostics": diagnostics,
        "settings_snapshot": settings_snapshot or {"points_valuation_mode": mode},
        "methodology_fingerprint": fingerprint,
    }


def _profile_snapshots() -> dict[str, dict]:
    return {
        "points_season_total": _profile_snapshot(mode="season_total", fingerprint="season123"),
        "points_weekly_h2h": _profile_snapshot(mode="weekly_h2h", fingerprint="weekly123"),
        "points_daily_h2h": _profile_snapshot(mode="daily_h2h", fingerprint="daily123"),
    }


def test_deep_roto_params_resolve_current_deep_preset() -> None:
    deep = _deep_roto_params()

    assert deep["hit_c"] == 2
    assert deep["hit_ut"] == 2
    assert deep["pit_p"] == 3
    assert deep["pit_sp"] == 3
    assert deep["pit_rp"] == 3
    assert deep["bench"] == 14
    assert deep["minors"] == 20
    assert deep["ir"] == 8
    assert deep["ip_min"] == 1000.0
    assert deep["ip_max"] == 1500.0
    assert deep["roto_hit_ops"] is True
    assert deep["roto_pit_qa3"] is True
    assert deep["roto_pit_svh"] is True


def test_points_profile_params_resolve_canonical_modes() -> None:
    season = _points_profile_params("points_season_total")
    weekly = _points_profile_params("points_weekly_h2h")
    daily = _points_profile_params("points_daily_h2h")

    assert season["points_valuation_mode"] == "season_total"
    assert season["weekly_starts_cap"] is None
    assert weekly["points_valuation_mode"] == "weekly_h2h"
    assert weekly["weekly_starts_cap"] == 7
    assert weekly["weekly_acquisition_cap"] == 2
    assert daily["points_valuation_mode"] == "daily_h2h"
    assert daily["weekly_starts_cap"] == 7
    assert daily["weekly_acquisition_cap"] == 2


def test_review_points_audit_uses_replacement_rank_for_depth_scenarios() -> None:
    hitter_a = _points_player_row(player="Hitter A", pos="OF", dynasty_value=10.0, selected_points=10.0)
    hitter_b = _points_player_row(player="Hitter B", pos="OF", dynasty_value=8.0, selected_points=8.0)
    hitter_c = _points_player_row(player="Hitter C", pos="OF", dynasty_value=6.0, selected_points=6.0)
    hitter_d_control = _points_player_row(
        player="Hitter D",
        pos="OF",
        dynasty_value=0.92,
        raw_dynasty_value=0.92,
        selected_points=0.0,
    )
    hitter_d_keeper = _points_player_row(
        player="Hitter D",
        pos="OF",
        dynasty_value=1.84,
        raw_dynasty_value=0.92,
        selected_points=0.0,
    )

    scenario_snapshots = {
        "season_total_shallow_base": _scenario_snapshot(
            rows_with_explanations=[hitter_a, hitter_b, hitter_c, hitter_d_control],
            mode="season_total",
            replacement_rank=1,
            in_season_replacement_rank=1,
            fingerprint="shallow123",
        ),
        "season_total_deep_replacement_depth": _scenario_snapshot(
            rows_with_explanations=[hitter_a, hitter_b, hitter_c, hitter_d_control],
            mode="season_total",
            replacement_rank=27,
            in_season_replacement_rank=27,
            fingerprint="deep123",
            settings_snapshot={"points_valuation_mode": "season_total", "bench": 8, "minors": 12, "ir": 6},
        ),
        "season_total_keeper_limit_control": _scenario_snapshot(
            rows_with_explanations=[hitter_a, hitter_b, hitter_c, hitter_d_control],
            mode="season_total",
            replacement_rank=3,
            in_season_replacement_rank=3,
            fingerprint="keeper-control123",
            settings_snapshot={"points_valuation_mode": "season_total", "bench": 2, "horizon": 2},
        ),
        "season_total_keeper_limit_override": _scenario_snapshot(
            rows_with_explanations=[hitter_a, hitter_b, hitter_c, hitter_d_keeper],
            mode="season_total",
            replacement_rank=3,
            in_season_replacement_rank=3,
            keeper_limit=1,
            fingerprint="keeper123",
            extra_diagnostics={"KeeperContinuationRank": 1, "KeeperContinuationBaselineValue": 0.92},
            settings_snapshot={"points_valuation_mode": "season_total", "keeper_limit": 1, "horizon": 2},
        ),
    }

    review = review_points_audit(
        profile_snapshots=_profile_snapshots(),
        scenario_snapshots=scenario_snapshots,
        projection_data_version="data-v1",
        profile_id="points_season_total",
    )

    results = {item["scenario_id"]: item for item in review["scenario_results"]}
    assert results["season_total_deep_replacement_depth"]["status"] == "expected_mechanism"
    assert results["season_total_keeper_limit_override"]["status"] == "expected_mechanism"
    assert results["season_total_deep_replacement_depth"]["pool_recenter_metrics"]["replacement_rank_change"] == 26
    assert results["season_total_keeper_limit_override"]["pool_recenter_metrics"]["replacement_rank_change"] == 0
    assert results["season_total_keeper_limit_override"]["pool_recenter_metrics"]["variant_keeper_continuation_rank"] == 1
    assert (
        results["season_total_keeper_limit_override"]["pool_recenter_metrics"][
            "variant_keeper_continuation_baseline_value"
        ]
        == 0.92
    )
    assert review["recommendation"] == "recommend_no_points_change_yet"


def test_review_points_audit_classifies_weekly_streaming_with_pool_recenter() -> None:
    ace_control = _points_player_row(
        player="Ace A",
        pos="SP",
        dynasty_value=20.0,
        selected_points=20.0,
        pitching_usage_share=1.0,
        pitching_assigned_starts=26.0,
    )
    starter_control = _points_player_row(
        player="Starter B",
        pos="SP",
        dynasty_value=18.0,
        selected_points=18.0,
        pitching_usage_share=1.0,
        pitching_assigned_starts=26.0,
    )
    streamer_control = _points_player_row(
        player="Streamer C",
        pos="SP",
        dynasty_value=16.0,
        selected_points=12.0,
        pitching_usage_share=1.0,
        pitching_assigned_starts=26.0,
    )
    utility_control = _points_player_row(player="Utility Bat", pos="OF", dynasty_value=8.0, selected_points=8.0)
    ace_variant = _points_player_row(
        player="Ace A",
        pos="SP",
        dynasty_value=19.0,
        selected_points=18.0,
        pitching_usage_share=0.9,
        pitching_assigned_starts=22.0,
    )
    starter_variant = _points_player_row(
        player="Starter B",
        pos="SP",
        dynasty_value=15.0,
        selected_points=13.0,
        pitching_usage_share=0.7,
        pitching_assigned_starts=18.0,
    )
    streamer_variant = _points_player_row(
        player="Streamer C",
        pos="SP",
        dynasty_value=10.0,
        selected_points=6.0,
        pitching_usage_share=0.4,
        pitching_assigned_starts=8.0,
    )
    utility_variant = _points_player_row(player="Utility Bat", pos="OF", dynasty_value=11.0, selected_points=8.5)

    review = review_points_audit(
        profile_snapshots=_profile_snapshots(),
        scenario_snapshots={
            "weekly_streaming_control_season_total": _scenario_snapshot(
                rows_with_explanations=[ace_control, starter_control, streamer_control, utility_control],
                mode="season_total",
                replacement_rank=2,
                in_season_replacement_rank=2,
                fingerprint="control123",
            ),
            "weekly_streaming_suppression": _scenario_snapshot(
                rows_with_explanations=[ace_variant, starter_variant, streamer_variant, utility_variant],
                mode="weekly_h2h",
                replacement_rank=2,
                in_season_replacement_rank=2,
                fingerprint="weekly123",
                extra_diagnostics={"WeeklyStartsCap": 2, "WeeklyAcquisitionCap": 1},
            ),
        },
        projection_data_version="data-v1",
        profile_id="points_weekly_h2h",
    )

    result = next(item for item in review["scenario_results"] if item["scenario_id"] == "weekly_streaming_suppression")
    assert result["status"] == "expected_with_pool_recenter"
    assert result["direct_metrics"]["median_selected_points_delta"] < 0.0
    assert result["direct_metrics"]["median_pitching_usage_share_delta"] < 0.0
    assert result["direct_metrics"]["median_pitching_assigned_starts_delta"] < 0.0
    assert result["pool_recenter_metrics"]["unaffected_top_mover_count"] >= 1


def test_review_points_audit_classifies_ip_max_with_pool_recenter() -> None:
    ace_control = _points_player_row(
        player="Ace A",
        pos="SP",
        dynasty_value=20.0,
        selected_points=20.0,
        pitching_assigned_ip=180.0,
    )
    starter_b_control = _points_player_row(
        player="Starter B",
        pos="SP",
        dynasty_value=18.0,
        selected_points=18.0,
        pitching_assigned_ip=160.0,
    )
    starter_c_control = _points_player_row(
        player="Starter C",
        pos="SP",
        dynasty_value=16.0,
        selected_points=15.0,
        pitching_assigned_ip=120.0,
    )
    utility_control = _points_player_row(player="Utility Bat", pos="OF", dynasty_value=8.0, selected_points=8.0)
    ace_variant = _points_player_row(
        player="Ace A",
        pos="SP",
        dynasty_value=20.0,
        selected_points=20.0,
        pitching_assigned_ip=180.0,
    )
    starter_b_variant = _points_player_row(
        player="Starter B",
        pos="SP",
        dynasty_value=13.0,
        selected_points=12.0,
        pitching_assigned_ip=60.0,
    )
    starter_c_variant = _points_player_row(
        player="Starter C",
        pos="SP",
        dynasty_value=7.0,
        selected_points=0.0,
        pitching_assigned_ip=0.0,
    )
    utility_variant = _points_player_row(player="Utility Bat", pos="OF", dynasty_value=10.0, selected_points=8.0)

    review = review_points_audit(
        profile_snapshots=_profile_snapshots(),
        scenario_snapshots={
            "season_total_ip_max_control": _scenario_snapshot(
                rows_with_explanations=[ace_control, starter_b_control, starter_c_control, utility_control],
                mode="season_total",
                replacement_rank=2,
                in_season_replacement_rank=2,
                fingerprint="ip-control123",
            ),
            "season_total_ip_max_hard_cap": _scenario_snapshot(
                rows_with_explanations=[ace_variant, starter_b_variant, starter_c_variant, utility_variant],
                mode="season_total",
                replacement_rank=2,
                in_season_replacement_rank=2,
                fingerprint="ip-cap123",
                extra_diagnostics={"PitcherUsageByYear": {"2026": {"ip_cap_binding": True}}},
            ),
        },
        projection_data_version="data-v1",
        profile_id="points_season_total",
    )

    result = next(item for item in review["scenario_results"] if item["scenario_id"] == "season_total_ip_max_hard_cap")
    assert result["status"] == "expected_with_pool_recenter"
    assert result["direct_metrics"]["median_selected_points_delta"] < 0.0
    assert result["direct_metrics"]["median_pitching_assigned_ip_delta"] < 0.0
    assert result["pool_recenter_metrics"]["unaffected_top_mover_count"] >= 1


def test_review_points_audit_reliever_fractional_starts_stays_expected() -> None:
    ace = _points_player_row(
        player="Ace A",
        pos="SP",
        dynasty_value=20.0,
        selected_points=20.0,
        pitching_usage_share=1.0,
        pitching_assigned_starts=30.0,
    )
    starter = _points_player_row(
        player="Starter B",
        pos="SP",
        dynasty_value=18.0,
        selected_points=18.0,
        pitching_usage_share=1.0,
        pitching_assigned_starts=22.0,
    )
    reliever = _points_player_row(
        player="Reliever C",
        pos="RP",
        dynasty_value=4.0,
        selected_points=3.0,
        pitching_usage_share=0.0,
        pitching_assigned_starts=0.0,
    )

    review = review_points_audit(
        profile_snapshots=_profile_snapshots(),
        scenario_snapshots={
            "weekly_reliever_fractional_start_handling": _scenario_snapshot(
                rows_with_explanations=[ace, starter, reliever],
                mode="weekly_h2h",
                replacement_rank=1,
                in_season_replacement_rank=1,
                fingerprint="reliever123",
                extra_diagnostics={"WeeklyStartsCap": 2, "WeeklyAcquisitionCap": 1},
            )
        },
        projection_data_version="data-v1",
        profile_id="points_weekly_h2h",
    )

    result = next(
        item for item in review["scenario_results"] if item["scenario_id"] == "weekly_reliever_fractional_start_handling"
    )
    assert result["status"] == "expected_mechanism"
    assert result["direct_metrics"]["median_variant_pitching_assigned_starts"] == 0.0


def test_render_points_audit_outputs_status_and_recenter_metrics() -> None:
    hitter_a = _points_player_row(player="Hitter A", pos="OF", dynasty_value=10.0, selected_points=10.0)
    hitter_b = _points_player_row(player="Hitter B", pos="OF", dynasty_value=8.0, selected_points=8.0)
    hitter_c = _points_player_row(player="Hitter C", pos="OF", dynasty_value=6.0, selected_points=6.0)
    ace_control = _points_player_row(
        player="Ace A",
        pos="SP",
        dynasty_value=20.0,
        selected_points=20.0,
        pitching_usage_share=1.0,
        pitching_assigned_starts=26.0,
    )
    starter_control = _points_player_row(
        player="Starter B",
        pos="SP",
        dynasty_value=18.0,
        selected_points=18.0,
        pitching_usage_share=1.0,
        pitching_assigned_starts=26.0,
    )
    streamer_control = _points_player_row(
        player="Streamer C",
        pos="SP",
        dynasty_value=16.0,
        selected_points=12.0,
        pitching_usage_share=1.0,
        pitching_assigned_starts=26.0,
    )
    utility_control = _points_player_row(player="Utility Bat", pos="OF", dynasty_value=8.0, selected_points=8.0)
    ace_variant = _points_player_row(
        player="Ace A",
        pos="SP",
        dynasty_value=19.0,
        selected_points=18.0,
        pitching_usage_share=0.9,
        pitching_assigned_starts=22.0,
    )
    starter_variant = _points_player_row(
        player="Starter B",
        pos="SP",
        dynasty_value=15.0,
        selected_points=13.0,
        pitching_usage_share=0.7,
        pitching_assigned_starts=18.0,
    )
    streamer_variant = _points_player_row(
        player="Streamer C",
        pos="SP",
        dynasty_value=10.0,
        selected_points=6.0,
        pitching_usage_share=0.4,
        pitching_assigned_starts=8.0,
    )
    utility_variant = _points_player_row(player="Utility Bat", pos="OF", dynasty_value=11.0, selected_points=8.5)
    ace = _points_player_row(
        player="Ace A",
        pos="SP",
        dynasty_value=20.0,
        selected_points=20.0,
        pitching_usage_share=1.0,
        pitching_assigned_starts=30.0,
    )
    starter = _points_player_row(
        player="Starter B",
        pos="SP",
        dynasty_value=18.0,
        selected_points=18.0,
        pitching_usage_share=1.0,
        pitching_assigned_starts=22.0,
    )
    reliever = _points_player_row(
        player="Reliever C",
        pos="RP",
        dynasty_value=4.0,
        selected_points=3.0,
        pitching_usage_share=0.0,
        pitching_assigned_starts=0.0,
    )

    review = review_points_audit(
        profile_snapshots=_profile_snapshots(),
        scenario_snapshots={
            "season_total_shallow_base": _scenario_snapshot(
                rows_with_explanations=[hitter_a, hitter_b, hitter_c],
                mode="season_total",
                replacement_rank=1,
                in_season_replacement_rank=1,
                fingerprint="shallow123",
            ),
            "season_total_deep_replacement_depth": _scenario_snapshot(
                rows_with_explanations=[hitter_a, hitter_b, hitter_c],
                mode="season_total",
                replacement_rank=27,
                in_season_replacement_rank=27,
                fingerprint="deep123",
            ),
            "weekly_streaming_control_season_total": _scenario_snapshot(
                rows_with_explanations=[ace_control, starter_control, streamer_control, utility_control],
                mode="season_total",
                replacement_rank=2,
                in_season_replacement_rank=2,
                fingerprint="control123",
            ),
            "weekly_streaming_suppression": _scenario_snapshot(
                rows_with_explanations=[ace_variant, starter_variant, streamer_variant, utility_variant],
                mode="weekly_h2h",
                replacement_rank=2,
                in_season_replacement_rank=2,
                fingerprint="weekly123",
                extra_diagnostics={"WeeklyStartsCap": 2, "WeeklyAcquisitionCap": 1},
            ),
            "weekly_reliever_fractional_start_handling": _scenario_snapshot(
                rows_with_explanations=[ace, starter, reliever],
                mode="weekly_h2h",
                replacement_rank=1,
                in_season_replacement_rank=1,
                fingerprint="reliever123",
                extra_diagnostics={"WeeklyStartsCap": 2, "WeeklyAcquisitionCap": 1},
            ),
        },
        projection_data_version="data-v1",
        profile_id="points_weekly_h2h",
    )

    markdown = render_points_audit_markdown(review)
    assert "Points Dynasty Audit Review" in markdown
    assert "expected_with_pool_recenter" in markdown
    assert "expected_mechanism" in markdown
    assert "direct count=" in markdown
    assert "recenter replacement_rank_delta=" in markdown

    memo = render_points_audit_memo_markdown(review)
    assert "Points Dynasty Audit Memo" in memo
    assert "weekly_h2h" in memo
    assert "direct metrics" in memo
    assert "Pool recenter metrics" in memo
