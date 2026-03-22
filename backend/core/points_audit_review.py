"""Scenario-based audit helpers for points dynasty valuation modes."""

from __future__ import annotations

import json
from statistics import median
from typing import Any, Iterable, Sequence

POINTS_PROFILE_IDS: tuple[str, ...] = (
    "points_season_total",
    "points_weekly_h2h",
    "points_daily_h2h",
)
POINTS_PROFILE_MODE_BY_ID: dict[str, str] = {
    "points_season_total": "season_total",
    "points_weekly_h2h": "weekly_h2h",
    "points_daily_h2h": "daily_h2h",
}
POINTS_SCENARIO_BUCKETS: tuple[str, ...] = (
    "replacement_depth_keeper_limit_effect",
    "weekly_streaming_fungibility",
    "daily_starts_cap_effect",
    "innings_cap_trimming",
    "stash_risk_adjustment_effect",
    "mixed",
    "needs_review",
)
POINTS_SCENARIO_STATUSES: tuple[str, ...] = (
    "expected_mechanism",
    "expected_with_pool_recenter",
    "suspect_model_gap",
    "needs_manual_review",
)
POINTS_RECOMMENDATIONS: tuple[str, ...] = (
    "recommend_points_methodology_followup",
    "recommend_no_points_change_yet",
)
POINTS_AUDIT_SCENARIOS: tuple[dict[str, Any], ...] = (
    {
        "id": "season_total_deep_replacement_depth",
        "mode": "season_total",
        "bucket": "replacement_depth_keeper_limit_effect",
        "control_snapshot_id": "season_total_shallow_base",
        "variant_snapshot_id": "season_total_deep_replacement_depth",
        "affected_players": ("Hitter A", "Hitter B", "Hitter C"),
        "cohort_label": "replacement fringe hitters",
        "evaluator": "replacement_depth",
    },
    {
        "id": "season_total_keeper_limit_override",
        "mode": "season_total",
        "bucket": "replacement_depth_keeper_limit_effect",
        "control_snapshot_id": "season_total_keeper_limit_control",
        "variant_snapshot_id": "season_total_keeper_limit_override",
        "affected_players": ("Hitter D",),
        "cohort_label": "keeper-aware future continuation cohort",
        "evaluator": "keeper_limit",
    },
    {
        "id": "weekly_streaming_suppression",
        "mode": "weekly_h2h",
        "bucket": "weekly_streaming_fungibility",
        "control_snapshot_id": "weekly_streaming_control_season_total",
        "variant_snapshot_id": "weekly_streaming_suppression",
        "affected_players": ("Streamer C",),
        "cohort_label": "streamable SP cohort",
        "evaluator": "weekly_streaming_suppression",
        "allow_pool_recenter_status": True,
    },
    {
        "id": "weekly_same_day_starts_overflow",
        "mode": "weekly_h2h",
        "bucket": "weekly_streaming_fungibility",
        "control_snapshot_id": "weekly_same_day_starts_control",
        "variant_snapshot_id": "weekly_same_day_starts_overflow",
        "affected_players": ("Streamer C",),
        "cohort_label": "streamable SP cohort",
        "evaluator": "same_day_starts_overflow",
    },
    {
        "id": "weekly_reliever_fractional_start_handling",
        "mode": "weekly_h2h",
        "bucket": "weekly_streaming_fungibility",
        "control_snapshot_id": "weekly_reliever_fractional_start_handling",
        "variant_snapshot_id": "weekly_reliever_fractional_start_handling",
        "affected_players": ("Reliever C",),
        "cohort_label": "fractional-start relievers",
        "evaluator": "reliever_fractional_starts",
    },
    {
        "id": "daily_starts_cap_behavior",
        "mode": "daily_h2h",
        "bucket": "daily_starts_cap_effect",
        "control_snapshot_id": "daily_starts_cap_control_season_total",
        "variant_snapshot_id": "daily_starts_cap_behavior",
        "affected_players": ("Starter B", "Streamer C", "Starter D"),
        "cohort_label": "daily capped SP cohort",
        "evaluator": "daily_starts_cap",
        "allow_pool_recenter_status": True,
    },
    {
        "id": "season_total_ip_max_hard_cap",
        "mode": "season_total",
        "bucket": "innings_cap_trimming",
        "control_snapshot_id": "season_total_ip_max_control",
        "variant_snapshot_id": "season_total_ip_max_hard_cap",
        "affected_players": ("Starter B", "Starter C"),
        "cohort_label": "IP-capped pitchers",
        "evaluator": "ip_max",
        "allow_pool_recenter_status": True,
    },
    {
        "id": "season_total_bench_ir_stash_relief",
        "mode": "season_total",
        "bucket": "stash_risk_adjustment_effect",
        "control_snapshot_id": "season_total_bench_ir_stash_control",
        "variant_snapshot_id": "season_total_bench_ir_stash_relief",
        "affected_players": ("Bench Bat", "Injured Bat"),
        "cohort_label": "reserve / stash hitters",
        "evaluator": "stash_relief",
    },
    {
        "id": "season_total_prospect_risk_discount",
        "mode": "season_total",
        "bucket": "stash_risk_adjustment_effect",
        "control_snapshot_id": "season_total_without_prospect_risk",
        "variant_snapshot_id": "season_total_prospect_risk_discount",
        "affected_players": ("Prospect A", "Prospect B"),
        "cohort_label": "minor-eligible hitters",
        "evaluator": "prospect_risk",
    },
)


def _coerce_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _serialize_settings_snapshot(settings_snapshot: object) -> str:
    if not isinstance(settings_snapshot, dict):
        return "{}"
    serialized = {
        str(key): value
        for key, value in sorted(settings_snapshot.items(), key=lambda item: str(item[0]))
    }
    return json.dumps(serialized, sort_keys=True, separators=(",", ":"))


def _start_year_points_detail(explanation: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(explanation, dict):
        return {}
    per_year = explanation.get("per_year")
    if not isinstance(per_year, list) or not per_year:
        return {}
    first = per_year[0]
    if not isinstance(first, dict):
        return {}
    points = first.get("points")
    return points if isinstance(points, dict) else {}


def _ranked_points_entries(
    *,
    rows: Iterable[dict[str, Any]],
    explanations: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    ranked_rows = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=lambda row: float(row.get("DynastyValue") or 0.0),
        reverse=True,
    )
    explanation_map = explanations if isinstance(explanations, dict) else {}
    ranked: list[dict[str, Any]] = []
    for idx, row in enumerate(ranked_rows, start=1):
        player = str(row.get("Player") or "").strip()
        if not player:
            continue
        player_key = str(row.get("PlayerKey") or "").strip()
        entity_key = str(row.get("PlayerEntityKey") or player_key).strip() or player_key
        explanation = explanation_map.get(entity_key) or explanation_map.get(player_key)
        explanation = explanation if isinstance(explanation, dict) else None
        start_year_points = _start_year_points_detail(explanation)
        ranked.append(
            {
                "player": player,
                "team": str(row.get("Team") or "").strip() or None,
                "pos": str(row.get("Pos") or "").strip() or None,
                "model_rank": idx,
                "dynasty_value": float(row.get("DynastyValue") or 0.0),
                "selected_points": _coerce_float(row.get("SelectedPoints")),
                "raw_dynasty_value": _coerce_float(row.get("RawDynastyValue")),
                "minor_eligible": bool(row.get("minor_eligible")),
                "explanation": explanation,
                "start_year_points": start_year_points,
            }
        )
    return ranked


def _player_index(entries: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }


def _paired_cohort_entries(
    *,
    control_entries: Sequence[dict[str, Any]],
    variant_entries: Sequence[dict[str, Any]],
    players: Sequence[str],
) -> list[dict[str, Any]]:
    control_index = _player_index(control_entries)
    variant_index = _player_index(variant_entries)
    pairs: list[dict[str, Any]] = []
    for player in players:
        control = control_index.get(str(player).strip())
        variant = variant_index.get(str(player).strip())
        if not isinstance(control, dict) or not isinstance(variant, dict):
            continue
        control_points = control.get("start_year_points") if isinstance(control.get("start_year_points"), dict) else {}
        variant_points = variant.get("start_year_points") if isinstance(variant.get("start_year_points"), dict) else {}
        pairs.append(
            {
                "player": str(player).strip(),
                "control": control,
                "variant": variant,
                "control_rank": _coerce_int(control.get("model_rank")),
                "variant_rank": _coerce_int(variant.get("model_rank")),
                "rank_delta": (
                    int(_coerce_int(control.get("model_rank")) or 0) - int(_coerce_int(variant.get("model_rank")) or 0)
                ),
                "selected_points_delta": (
                    float(_coerce_float(variant.get("selected_points")) or 0.0)
                    - float(_coerce_float(control.get("selected_points")) or 0.0)
                ),
                "dynasty_value_delta": (
                    float(_coerce_float(variant.get("dynasty_value")) or 0.0)
                    - float(_coerce_float(control.get("dynasty_value")) or 0.0)
                ),
                "raw_dynasty_value_delta": (
                    float(_coerce_float(variant.get("raw_dynasty_value")) or 0.0)
                    - float(_coerce_float(control.get("raw_dynasty_value")) or 0.0)
                ),
                "pitching_usage_share_delta": (
                    float(_coerce_float(variant_points.get("pitching_usage_share")) or 0.0)
                    - float(_coerce_float(control_points.get("pitching_usage_share")) or 0.0)
                ),
                "pitching_assigned_starts_delta": (
                    float(_coerce_float(variant_points.get("pitching_assigned_starts")) or 0.0)
                    - float(_coerce_float(control_points.get("pitching_assigned_starts")) or 0.0)
                ),
                "pitching_assigned_ip_delta": (
                    float(_coerce_float(variant_points.get("pitching_assigned_ip")) or 0.0)
                    - float(_coerce_float(control_points.get("pitching_assigned_ip")) or 0.0)
                ),
                "variant_pitching_assigned_starts": _coerce_float(variant_points.get("pitching_assigned_starts")),
                "variant_pitching_assigned_ip": _coerce_float(variant_points.get("pitching_assigned_ip")),
                "variant_pitching_usage_share": _coerce_float(variant_points.get("pitching_usage_share")),
                "variant_minor_eligible": bool(variant.get("minor_eligible")),
            }
        )
    return pairs


def _median_or_none(values: Iterable[float | int | None], *, digits: int = 4) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return round(float(median(numeric)), digits)


def _mean_or_none(values: Iterable[float | int | None], *, digits: int = 4) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return round(sum(numeric) / len(numeric), digits)


def _direct_cohort_metrics(pairs: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "affected_player_count": len(pairs),
        "affected_players": [str(pair.get("player") or "") for pair in pairs],
        "median_selected_points_delta": _median_or_none(pair.get("selected_points_delta") for pair in pairs),
        "mean_selected_points_delta": _mean_or_none(pair.get("selected_points_delta") for pair in pairs),
        "median_dynasty_value_delta": _median_or_none(pair.get("dynasty_value_delta") for pair in pairs),
        "mean_dynasty_value_delta": _mean_or_none(pair.get("dynasty_value_delta") for pair in pairs),
        "median_raw_dynasty_value_delta": _median_or_none(pair.get("raw_dynasty_value_delta") for pair in pairs),
        "mean_raw_dynasty_value_delta": _mean_or_none(pair.get("raw_dynasty_value_delta") for pair in pairs),
        "median_rank_delta": _median_or_none(pair.get("rank_delta") for pair in pairs),
        "median_pitching_usage_share_delta": _median_or_none(
            pair.get("pitching_usage_share_delta") for pair in pairs
        ),
        "mean_pitching_usage_share_delta": _mean_or_none(
            pair.get("pitching_usage_share_delta") for pair in pairs
        ),
        "median_pitching_assigned_starts_delta": _median_or_none(
            pair.get("pitching_assigned_starts_delta") for pair in pairs
        ),
        "mean_pitching_assigned_starts_delta": _mean_or_none(
            pair.get("pitching_assigned_starts_delta") for pair in pairs
        ),
        "median_pitching_assigned_ip_delta": _median_or_none(
            pair.get("pitching_assigned_ip_delta") for pair in pairs
        ),
        "mean_pitching_assigned_ip_delta": _mean_or_none(
            pair.get("pitching_assigned_ip_delta") for pair in pairs
        ),
        "median_variant_pitching_assigned_starts": _median_or_none(
            pair.get("variant_pitching_assigned_starts") for pair in pairs
        ),
        "median_variant_pitching_assigned_ip": _median_or_none(
            pair.get("variant_pitching_assigned_ip") for pair in pairs
        ),
        "median_variant_pitching_usage_share": _median_or_none(
            pair.get("variant_pitching_usage_share") for pair in pairs
        ),
    }


def _top_rank_movers(
    *,
    control_entries: Sequence[dict[str, Any]],
    variant_entries: Sequence[dict[str, Any]],
    exclude_players: Sequence[str] | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    control_index = _player_index(control_entries)
    excluded = {str(player).strip() for player in (exclude_players or ()) if str(player).strip()}
    movers: list[dict[str, Any]] = []
    for variant in variant_entries:
        if not isinstance(variant, dict):
            continue
        player = str(variant.get("player") or "").strip()
        if not player or player in excluded:
            continue
        control = control_index.get(player)
        if not isinstance(control, dict):
            continue
        control_rank = _coerce_int(control.get("model_rank"))
        variant_rank = _coerce_int(variant.get("model_rank"))
        if control_rank is None or variant_rank is None:
            continue
        movers.append(
            {
                "player": player,
                "pos": variant.get("pos") or control.get("pos"),
                "control_rank": control_rank,
                "variant_rank": variant_rank,
                "rank_delta": int(control_rank) - int(variant_rank),
            }
        )
    return sorted(
        movers,
        key=lambda entry: (-abs(int(entry.get("rank_delta") or 0)), str(entry.get("player") or "")),
    )[:limit]


def _pool_recenter_metrics(
    *,
    control_snapshot: dict[str, Any],
    variant_snapshot: dict[str, Any],
    control_entries: Sequence[dict[str, Any]],
    variant_entries: Sequence[dict[str, Any]],
    affected_players: Sequence[str],
) -> dict[str, Any]:
    control_diagnostics = control_snapshot.get("valuation_diagnostics")
    control_diagnostics = control_diagnostics if isinstance(control_diagnostics, dict) else {}
    variant_diagnostics = variant_snapshot.get("valuation_diagnostics")
    variant_diagnostics = variant_diagnostics if isinstance(variant_diagnostics, dict) else {}
    unaffected_top_movers = _top_rank_movers(
        control_entries=control_entries,
        variant_entries=variant_entries,
        exclude_players=affected_players,
    )
    return {
        "control_replacement_rank": _coerce_int(control_diagnostics.get("ReplacementRank")),
        "variant_replacement_rank": _coerce_int(variant_diagnostics.get("ReplacementRank")),
        "replacement_rank_change": (
            int(_coerce_int(variant_diagnostics.get("ReplacementRank")) or 0)
            - int(_coerce_int(control_diagnostics.get("ReplacementRank")) or 0)
        ),
        "control_in_season_replacement_rank": _coerce_int(control_diagnostics.get("InSeasonReplacementRank")),
        "variant_in_season_replacement_rank": _coerce_int(variant_diagnostics.get("InSeasonReplacementRank")),
        "in_season_replacement_rank_change": (
            int(_coerce_int(variant_diagnostics.get("InSeasonReplacementRank")) or 0)
            - int(_coerce_int(control_diagnostics.get("InSeasonReplacementRank")) or 0)
        ),
        "control_keeper_continuation_rank": _coerce_int(control_diagnostics.get("KeeperContinuationRank")),
        "variant_keeper_continuation_rank": _coerce_int(variant_diagnostics.get("KeeperContinuationRank")),
        "keeper_continuation_rank_change": (
            int(_coerce_int(variant_diagnostics.get("KeeperContinuationRank")) or 0)
            - int(_coerce_int(control_diagnostics.get("KeeperContinuationRank")) or 0)
        ),
        "control_keeper_continuation_baseline_value": _coerce_float(
            control_diagnostics.get("KeeperContinuationBaselineValue")
        ),
        "variant_keeper_continuation_baseline_value": _coerce_float(
            variant_diagnostics.get("KeeperContinuationBaselineValue")
        ),
        "unaffected_top_movers": unaffected_top_movers,
        "unaffected_top_mover_count": len(unaffected_top_movers),
    }


def _status_from_expected(
    *,
    direct_expected: bool,
    allow_pool_recenter_status: bool,
    pool_recenter_metrics: dict[str, Any],
) -> str:
    if not direct_expected:
        return "suspect_model_gap"
    if allow_pool_recenter_status and int(pool_recenter_metrics.get("unaffected_top_mover_count") or 0) > 0:
        return "expected_with_pool_recenter"
    return "expected_mechanism"


def _evaluate_points_scenario(
    *,
    scenario: dict[str, Any],
    control_snapshot: dict[str, Any],
    variant_snapshot: dict[str, Any],
    control_entries: Sequence[dict[str, Any]],
    variant_entries: Sequence[dict[str, Any]],
) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    affected_players = tuple(str(player).strip() for player in (scenario.get("affected_players") or ()) if str(player).strip())
    pairs = _paired_cohort_entries(
        control_entries=control_entries,
        variant_entries=variant_entries,
        players=affected_players,
    )
    direct_metrics = _direct_cohort_metrics(pairs)
    pool_recenter_metrics = _pool_recenter_metrics(
        control_snapshot=control_snapshot,
        variant_snapshot=variant_snapshot,
        control_entries=control_entries,
        variant_entries=variant_entries,
        affected_players=affected_players,
    )
    evaluator = str(scenario.get("evaluator") or "").strip()
    allow_pool_recenter_status = bool(scenario.get("allow_pool_recenter_status"))
    control_diagnostics = control_snapshot.get("valuation_diagnostics")
    control_diagnostics = control_diagnostics if isinstance(control_diagnostics, dict) else {}
    variant_diagnostics = variant_snapshot.get("valuation_diagnostics")
    variant_diagnostics = variant_diagnostics if isinstance(variant_diagnostics, dict) else {}

    if int(direct_metrics.get("affected_player_count") or 0) <= 0:
        return "needs_manual_review", "affected cohort is missing from the scenario snapshots", direct_metrics, pool_recenter_metrics

    direct_expected = False
    reason = "scenario evaluator not configured"
    if evaluator == "replacement_depth":
        direct_expected = int(pool_recenter_metrics.get("replacement_rank_change") or 0) > 0
        reason = "deeper season-total depth should push the replacement rank deeper"
    elif evaluator == "keeper_limit":
        variant_keeper_limit = _coerce_int(variant_diagnostics.get("KeeperLimit"))
        replacement_rank = _coerce_int(variant_diagnostics.get("ReplacementRank"))
        in_season_replacement_rank = _coerce_int(variant_diagnostics.get("InSeasonReplacementRank"))
        keeper_continuation_rank = _coerce_int(variant_diagnostics.get("KeeperContinuationRank"))
        keeper_continuation_baseline_value = _coerce_float(
            variant_diagnostics.get("KeeperContinuationBaselineValue")
        )
        dynasty_shift = _coerce_float(direct_metrics.get("mean_dynasty_value_delta"))
        direct_expected = (
            int(pool_recenter_metrics.get("replacement_rank_change") or 0) == 0
            and int(pool_recenter_metrics.get("in_season_replacement_rank_change") or 0) == 0
            and variant_keeper_limit is not None
            and replacement_rank is not None
            and in_season_replacement_rank is not None
            and replacement_rank == in_season_replacement_rank
            and keeper_continuation_rank is not None
            and keeper_continuation_baseline_value is not None
            and abs(float(dynasty_shift or 0.0)) > 1e-6
        )
        reason = "keeper-limit inputs should preserve full in-season replacement depth while shifting future keeper scarcity"
    elif evaluator == "weekly_streaming_suppression":
        direct_expected = (
            (
                (direct_metrics.get("mean_selected_points_delta") or 0.0) < 0.0
                or (direct_metrics.get("mean_dynasty_value_delta") or 0.0) < 0.0
            )
            and (direct_metrics.get("mean_pitching_usage_share_delta") or 0.0) < 0.0
            and (direct_metrics.get("mean_pitching_assigned_starts_delta") or 0.0) < 0.0
        )
        reason = "weekly starts/acquisition caps should reduce SP usage share and assigned starts, with lower selected points or dynasty value for the direct SP cohort"
    elif evaluator == "same_day_starts_overflow":
        direct_expected = (
            (
                (direct_metrics.get("mean_selected_points_delta") or 0.0) > 0.0
                or (direct_metrics.get("mean_dynasty_value_delta") or 0.0) > 0.0
            )
            and (direct_metrics.get("mean_pitching_assigned_starts_delta") or 0.0) > 0.0
        )
        reason = "same-day starts overflow should increase the capped SP cohort's assigned starts and raise selected points or dynasty value"
    elif evaluator == "reliever_fractional_starts":
        reliever_pair = pairs[0] if pairs else {}
        variant_assigned_starts = _coerce_float(reliever_pair.get("variant_pitching_assigned_starts"))
        direct_expected = variant_assigned_starts is not None and abs(float(variant_assigned_starts)) <= 1e-6
        reason = "relievers with fractional GS should not pick up streaming starts"
    elif evaluator == "daily_starts_cap":
        direct_expected = (
            (direct_metrics.get("mean_selected_points_delta") or 0.0) < 0.0
            and (direct_metrics.get("mean_pitching_assigned_starts_delta") or 0.0) < 0.0
        )
        reason = "daily starts caps should reduce assigned starts and selected points for the capped SP cohort"
    elif evaluator == "ip_max":
        direct_expected = (
            bool(variant_diagnostics.get("PitcherUsageByYear", {}).get("2026", {}).get("ip_cap_binding"))
            and (direct_metrics.get("mean_selected_points_delta") or 0.0) < 0.0
            and (direct_metrics.get("mean_pitching_assigned_ip_delta") or 0.0) < 0.0
        )
        reason = "ip_max should bind, trim assigned IP, and lower selected points for the pitcher cohort"
    elif evaluator == "stash_relief":
        direct_expected = (
            (direct_metrics.get("mean_selected_points_delta") or 0.0) > 0.0
            or (direct_metrics.get("mean_dynasty_value_delta") or 0.0) > 0.0
        )
        reason = "stash relief should raise selected points for reserve or injured hitters"
    elif evaluator == "prospect_risk":
        direct_expected = (
            (direct_metrics.get("mean_dynasty_value_delta") or 0.0) < 0.0
            or (direct_metrics.get("mean_raw_dynasty_value_delta") or 0.0) < 0.0
        )
        reason = "prospect risk should lower dynasty value for minor-eligible players even when start-year points stay flat"

    status = _status_from_expected(
        direct_expected=direct_expected,
        allow_pool_recenter_status=allow_pool_recenter_status,
        pool_recenter_metrics=pool_recenter_metrics,
    )
    return status, reason, direct_metrics, pool_recenter_metrics


def points_audit_recommendation(scenarios: Iterable[dict[str, Any]]) -> str:
    suspect_families = {
        str(scenario.get("classification_bucket") or "").strip()
        for scenario in scenarios
        if isinstance(scenario, dict) and str(scenario.get("status") or "").strip() == "suspect_model_gap"
    }
    if len({family for family in suspect_families if family}) >= 2:
        return "recommend_points_methodology_followup"
    return "recommend_no_points_change_yet"


def review_points_audit(
    *,
    profile_snapshots: dict[str, dict[str, Any]],
    scenario_snapshots: dict[str, dict[str, Any]],
    projection_data_version: str | None = None,
    profile_id: str = "points_season_total",
) -> dict[str, Any]:
    normalized_profiles = {
        str(key): value
        for key, value in profile_snapshots.items()
        if str(key) in POINTS_PROFILE_IDS and isinstance(value, dict)
    }
    snapshot_index = {
        str(key): value
        for key, value in scenario_snapshots.items()
        if isinstance(value, dict)
    }
    snapshot_index.update(normalized_profiles)

    profile_reviews: dict[str, dict[str, Any]] = {}
    for key, snapshot in normalized_profiles.items():
        rows = snapshot.get("rows")
        explanations = snapshot.get("explanations")
        profile_reviews[key] = {
            "profile_id": key,
            "mode": POINTS_PROFILE_MODE_BY_ID.get(key),
            "settings_snapshot": snapshot.get("settings_snapshot") if isinstance(snapshot.get("settings_snapshot"), dict) else {},
            "methodology_fingerprint": str(snapshot.get("methodology_fingerprint") or "").strip() or None,
            "valuation_diagnostics": snapshot.get("valuation_diagnostics") if isinstance(snapshot.get("valuation_diagnostics"), dict) else {},
            "entries": _ranked_points_entries(
                rows=rows if isinstance(rows, list) else [],
                explanations=explanations if isinstance(explanations, dict) else {},
            ),
        }

    scenario_results: list[dict[str, Any]] = []
    for scenario in POINTS_AUDIT_SCENARIOS:
        scenario_id = str(scenario.get("id") or "").strip()
        control_snapshot = snapshot_index.get(str(scenario.get("control_snapshot_id") or "").strip())
        variant_snapshot = snapshot_index.get(str(scenario.get("variant_snapshot_id") or "").strip())
        if not isinstance(control_snapshot, dict) or not isinstance(variant_snapshot, dict):
            continue
        control_entries = _ranked_points_entries(
            rows=control_snapshot.get("rows") if isinstance(control_snapshot.get("rows"), list) else [],
            explanations=control_snapshot.get("explanations") if isinstance(control_snapshot.get("explanations"), dict) else {},
        )
        variant_entries = _ranked_points_entries(
            rows=variant_snapshot.get("rows") if isinstance(variant_snapshot.get("rows"), list) else [],
            explanations=variant_snapshot.get("explanations") if isinstance(variant_snapshot.get("explanations"), dict) else {},
        )
        status, evaluation_reason, direct_metrics, pool_recenter_metrics = _evaluate_points_scenario(
            scenario=scenario,
            control_snapshot=control_snapshot,
            variant_snapshot=variant_snapshot,
            control_entries=control_entries,
            variant_entries=variant_entries,
        )
        scenario_results.append(
            {
                "scenario_id": scenario_id,
                "mode": str(scenario.get("mode") or "").strip() or None,
                "classification_bucket": str(scenario.get("bucket") or "mixed"),
                "cohort_label": str(scenario.get("cohort_label") or "").strip() or "affected cohort",
                "status": status,
                "expected_movement": status in {"expected_mechanism", "expected_with_pool_recenter"},
                "expected_reason": evaluation_reason,
                "control_snapshot_id": str(scenario.get("control_snapshot_id") or "").strip() or None,
                "variant_snapshot_id": str(scenario.get("variant_snapshot_id") or "").strip() or None,
                "control_settings_snapshot": (
                    control_snapshot.get("settings_snapshot") if isinstance(control_snapshot.get("settings_snapshot"), dict) else {}
                ),
                "variant_settings_snapshot": (
                    variant_snapshot.get("settings_snapshot") if isinstance(variant_snapshot.get("settings_snapshot"), dict) else {}
                ),
                "control_methodology_fingerprint": str(control_snapshot.get("methodology_fingerprint") or "").strip() or None,
                "variant_methodology_fingerprint": str(variant_snapshot.get("methodology_fingerprint") or "").strip() or None,
                "control_valuation_diagnostics": (
                    control_snapshot.get("valuation_diagnostics")
                    if isinstance(control_snapshot.get("valuation_diagnostics"), dict)
                    else {}
                ),
                "variant_valuation_diagnostics": (
                    variant_snapshot.get("valuation_diagnostics")
                    if isinstance(variant_snapshot.get("valuation_diagnostics"), dict)
                    else {}
                ),
                "direct_metrics": direct_metrics,
                "pool_recenter_metrics": pool_recenter_metrics,
            }
        )

    scenario_results = sorted(
        scenario_results,
        key=lambda item: (str(item.get("mode") or ""), str(item.get("scenario_id") or "")),
    )
    recommendation = points_audit_recommendation(scenario_results)
    return {
        "profile_id": str(profile_id or "").strip() or "points_season_total",
        "projection_data_version": str(projection_data_version or "").strip() or None,
        "profiles": profile_reviews,
        "scenario_results": scenario_results,
        "classification_counts": {
            label: sum(1 for scenario in scenario_results if scenario.get("classification_bucket") == label)
            for label in POINTS_SCENARIO_BUCKETS
        },
        "status_counts": {
            label: sum(1 for scenario in scenario_results if scenario.get("status") == label)
            for label in POINTS_SCENARIO_STATUSES
        },
        "recommendation": recommendation,
    }


def _format_top_movers(movers: object) -> str:
    if not isinstance(movers, list):
        return "none"
    parts: list[str] = []
    for mover in movers[:5]:
        if not isinstance(mover, dict):
            continue
        parts.append(
            f"{mover.get('player') or 'n/a'} ({mover.get('control_rank') or 'n/a'} -> {mover.get('variant_rank') or 'n/a'}, {int(mover.get('rank_delta') or 0):+d})"
        )
    return ", ".join(parts) or "none"


def _format_direct_metrics(metrics: object) -> str:
    if not isinstance(metrics, dict):
        return "none"
    parts: list[str] = []
    count = _coerce_int(metrics.get("affected_player_count"))
    if count is not None:
        parts.append(f"count={count}")
    for label, key in (
        ("med_pts", "median_selected_points_delta"),
        ("mean_pts", "mean_selected_points_delta"),
        ("med_dyn", "median_dynasty_value_delta"),
        ("mean_dyn", "mean_dynasty_value_delta"),
        ("med_raw", "median_raw_dynasty_value_delta"),
        ("mean_raw", "mean_raw_dynasty_value_delta"),
        ("med_rank", "median_rank_delta"),
        ("med_usage", "median_pitching_usage_share_delta"),
        ("mean_usage", "mean_pitching_usage_share_delta"),
        ("med_starts", "median_pitching_assigned_starts_delta"),
        ("mean_starts", "mean_pitching_assigned_starts_delta"),
        ("med_ip", "median_pitching_assigned_ip_delta"),
        ("mean_ip", "mean_pitching_assigned_ip_delta"),
    ):
        value = _coerce_float(metrics.get(key))
        if value is not None:
            parts.append(f"{label}={value:+.4f}")
    return ", ".join(parts) or "none"


def _format_pool_recenter_metrics(metrics: object) -> str:
    if not isinstance(metrics, dict):
        return "none"
    parts = [
        f"replacement_rank_delta={int(metrics.get('replacement_rank_change') or 0):+d}",
        f"in_season_replacement_rank_delta={int(metrics.get('in_season_replacement_rank_change') or 0):+d}",
    ]
    keeper_continuation_rank = _coerce_int(metrics.get("variant_keeper_continuation_rank"))
    if keeper_continuation_rank is not None:
        parts.append(f"keeper_continuation_rank={keeper_continuation_rank}")
    keeper_continuation_baseline_value = _coerce_float(metrics.get("variant_keeper_continuation_baseline_value"))
    if keeper_continuation_baseline_value is not None:
        parts.append(f"keeper_continuation_baseline={keeper_continuation_baseline_value:.4f}")
    unaffected_count = int(metrics.get("unaffected_top_mover_count") or 0)
    parts.append(f"unaffected_top_movers={unaffected_count}")
    if unaffected_count > 0:
        parts.append(f"examples={_format_top_movers(metrics.get('unaffected_top_movers'))}")
    return ", ".join(parts)


def render_points_audit_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Points Dynasty Audit Review",
        "",
        f"- Focus profile id: `{str(review.get('profile_id') or 'points_season_total').strip() or 'points_season_total'}`",
    ]
    projection_data_version = str(review.get("projection_data_version") or "").strip()
    if projection_data_version:
        lines.append(f"- Projection data version: `{projection_data_version}`")
    lines.extend(["", "## Canonical Profiles", ""])
    profiles = review.get("profiles")
    profiles = profiles if isinstance(profiles, dict) else {}
    for profile_id in POINTS_PROFILE_IDS:
        profile = profiles.get(profile_id)
        profile = profile if isinstance(profile, dict) else {}
        valuation_diagnostics = profile.get("valuation_diagnostics")
        valuation_diagnostics = valuation_diagnostics if isinstance(valuation_diagnostics, dict) else {}
        lines.extend(
            [
                f"### {profile_id}",
                "",
                f"- Mode: `{profile.get('mode') or 'n/a'}`",
                f"- Methodology fingerprint: `{profile.get('methodology_fingerprint') or 'n/a'}`",
                f"- Settings snapshot: `{_serialize_settings_snapshot(profile.get('settings_snapshot'))}`",
                (
                    f"- Replacement rank `{valuation_diagnostics.get('ReplacementRank')}`, "
                    f"in-season replacement rank `{valuation_diagnostics.get('InSeasonReplacementRank')}`, "
                    f"keeper limit `{valuation_diagnostics.get('KeeperLimit')}`."
                ),
                "",
            ]
        )
    lines.extend(["## Scenario Results", ""])
    for scenario in review.get("scenario_results") if isinstance(review.get("scenario_results"), list) else []:
        if not isinstance(scenario, dict):
            continue
        lines.append(
            (
                f"- `{scenario.get('scenario_id') or 'n/a'}` "
                f"({scenario.get('mode') or 'n/a'} / {scenario.get('classification_bucket') or 'mixed'}): "
                f"status `{scenario.get('status') or 'needs_manual_review'}`; "
                f"cohort `{scenario.get('cohort_label') or 'affected cohort'}`; "
                f"direct {_format_direct_metrics(scenario.get('direct_metrics'))}; "
                f"recenter {_format_pool_recenter_metrics(scenario.get('pool_recenter_metrics'))}."
            )
        )
    lines.extend(["", "## Recommendation", "", f"- `{review.get('recommendation') or 'recommend_no_points_change_yet'}`", ""])
    return "\n".join(lines)


def render_points_audit_memo_markdown(review: dict[str, Any]) -> str:
    profiles = review.get("profiles")
    profiles = profiles if isinstance(profiles, dict) else {}
    scenarios = review.get("scenario_results")
    scenarios = scenarios if isinstance(scenarios, list) else []
    lines = [
        "# Points Dynasty Audit Memo",
        "",
        f"- Focus profile id: `{str(review.get('profile_id') or 'points_season_total').strip() or 'points_season_total'}`",
        (
            f"- Projection data version: `{str(review.get('projection_data_version') or '').strip()}`"
            if str(review.get("projection_data_version") or "").strip()
            else "- Projection data version: unavailable"
        ),
        "",
    ]
    for mode in ("season_total", "weekly_h2h", "daily_h2h"):
        lines.extend([f"## {mode}", ""])
        matching_profiles = [
            profile
            for profile in profiles.values()
            if isinstance(profile, dict) and str(profile.get("mode") or "").strip() == mode
        ]
        for profile in matching_profiles:
            valuation_diagnostics = profile.get("valuation_diagnostics")
            valuation_diagnostics = valuation_diagnostics if isinstance(valuation_diagnostics, dict) else {}
            lines.extend(
                [
                    f"- Profile `{profile.get('profile_id') or 'n/a'}` fingerprint `{profile.get('methodology_fingerprint') or 'n/a'}`.",
                    f"- Settings snapshot: `{_serialize_settings_snapshot(profile.get('settings_snapshot'))}`.",
                    (
                        f"- Replacement rank `{valuation_diagnostics.get('ReplacementRank')}`, "
                        f"in-season replacement rank `{valuation_diagnostics.get('InSeasonReplacementRank')}`, "
                        f"keeper limit `{valuation_diagnostics.get('KeeperLimit')}`."
                    ),
                ]
            )
        mode_scenarios = [scenario for scenario in scenarios if isinstance(scenario, dict) and scenario.get("mode") == mode]
        if not mode_scenarios:
            lines.extend(["- No audit scenarios for this mode.", ""])
            continue
        for scenario in mode_scenarios:
            lines.extend(
                [
                    (
                        f"- `{scenario.get('scenario_id') or 'n/a'}` "
                        f"bucket `{scenario.get('classification_bucket') or 'mixed'}` "
                        f"-> status `{scenario.get('status') or 'needs_manual_review'}`."
                    ),
                    f"- Audit reason: {scenario.get('expected_reason') or 'none'}.",
                    f"- Cohort `{scenario.get('cohort_label') or 'affected cohort'}` direct metrics: {_format_direct_metrics(scenario.get('direct_metrics'))}.",
                    f"- Pool recenter metrics: {_format_pool_recenter_metrics(scenario.get('pool_recenter_metrics'))}.",
                ]
            )
        lines.append("")
    lines.extend(
        [
            "## Recommendation",
            "",
            f"- `{review.get('recommendation') or 'recommend_no_points_change_yet'}`",
            "",
        ]
    )
    return "\n".join(lines)
