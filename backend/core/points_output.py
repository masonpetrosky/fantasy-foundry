"""Points-mode dynasty output shaping and centering helpers."""

from __future__ import annotations

from typing import Any, Callable, cast

import pandas as pd

try:
    from backend.core.points_assignment import _SEASON_WEEKS
    from backend.core.points_roster_model import POINTS_CENTERING_ZERO_EPSILON
    from backend.core.points_value import (
        KeepDropResult,
        _apply_negative_value_stash_rules,
        _is_near_zero_playing_time,
        _prospect_risk_multiplier,
        dynasty_keep_or_drop_values,
    )
    from backend.valuation.active_volume import (
        SYNTHETIC_PERIOD_DAYS,
        SYNTHETIC_SEASON_DAYS,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from points_assignment import _SEASON_WEEKS  # type: ignore[no-redef]
    from points_roster_model import POINTS_CENTERING_ZERO_EPSILON  # type: ignore[no-redef]
    from points_value import (  # type: ignore[no-redef]
        KeepDropResult,
        _apply_negative_value_stash_rules,
        _is_near_zero_playing_time,
        _prospect_risk_multiplier,
        dynasty_keep_or_drop_values,
    )
    from valuation.active_volume import (  # type: ignore[no-redef]
        SYNTHETIC_PERIOD_DAYS,
        SYNTHETIC_SEASON_DAYS,
    )


POINTS_DEEP_ROSTER_ZERO_CLUSTER_MIN_SHARE = 0.10


def _float_value(value: object, default: float = 0.0) -> float:
    return float(cast(Any, value) or default)


def points_centering_baseline(
    frame: pd.DataFrame,
    *,
    score_col: str,
    replacement_rank: int,
    player_entity_key_col: str,
    player_key_col: str,
) -> float:
    if frame.empty:
        return 0.0
    sortable = frame.copy()
    sortable["_points_sort_score"] = pd.to_numeric(sortable.get(score_col), errors="coerce").fillna(0.0)
    sortable["_points_sort_entity"] = sortable.get(player_entity_key_col, "").astype(str)
    sortable["_points_sort_player_key"] = sortable.get(player_key_col, "").astype(str)
    sortable["_points_sort_player"] = sortable.get("Player", "").astype(str)
    sorted_frame = sortable.sort_values(
        ["_points_sort_score", "_points_sort_entity", "_points_sort_player_key", "_points_sort_player"],
        ascending=[False, True, True, True],
        kind="mergesort",
    ).reset_index(drop=True)
    cutoff_idx = min(max(int(replacement_rank), 1) - 1, len(sorted_frame) - 1)
    return float(sorted_frame.iloc[cutoff_idx]["_points_sort_score"])


def points_centering_baseline_for_roster(
    frame: pd.DataFrame,
    *,
    score_col: str,
    rostered_player_ids: set[str],
    minimum_roster_size: int,
    player_entity_key_col: str,
    player_key_col: str,
) -> float:
    if frame.empty:
        return 0.0
    sortable = frame.copy()
    sortable["_points_sort_score"] = pd.to_numeric(sortable.get(score_col), errors="coerce").fillna(0.0)
    player_entity = sortable.get(player_entity_key_col, "").astype(str)
    player_key = sortable.get(player_key_col, "").astype(str)
    mask = player_entity.isin(rostered_player_ids) | player_key.isin(rostered_player_ids)
    if not bool(mask.any()):
        return 0.0
    baseline_value = float(sortable.loc[mask, "_points_sort_score"].min())
    if int(minimum_roster_size) > int(mask.sum()):
        baseline_value = min(baseline_value, 0.0)
    return baseline_value


def future_continuation_value(keep_drop: KeepDropResult) -> float:
    if len(keep_drop.continuation_values) <= 1:
        return 0.0
    return float(keep_drop.continuation_values[1])


def _build_points_explain_year(
    *,
    detail: dict[str, Any],
    adjusted_value: float,
    keep_drop: KeepDropResult,
    idx: int,
) -> dict[str, object]:
    typed_detail = cast(dict[str, Any], detail)
    return {
        "hitting_points": round(_float_value(typed_detail["hitting_points"]), 4),
        "pitching_points": round(_float_value(typed_detail["pitching_points"]), 4),
        "hitting_raw_points": round(_float_value(typed_detail["hitting_raw_points"]), 4),
        "pitching_raw_points": round(_float_value(typed_detail["pitching_raw_points"]), 4),
        "hitting_usage_share": round(_float_value(typed_detail["hitting_usage_share"]), 6),
        "pitching_usage_share": round(_float_value(typed_detail["pitching_usage_share"]), 6),
        "pitching_appearance_usage_share": round(_float_value(typed_detail["pitching_appearance_usage_share"]), 6),
        "pitching_ip_usage_share": round(_float_value(typed_detail["pitching_ip_usage_share"]), 6),
        "hitting_assigned_games": round(_float_value(typed_detail["hitting_assigned_games"]), 4)
        if typed_detail["hitting_assigned_games"] is not None
        else None,
        "pitching_assigned_appearances": round(_float_value(typed_detail["pitching_assigned_appearances"]), 4)
        if typed_detail["pitching_assigned_appearances"] is not None
        else None,
        "pitching_assigned_starts": round(_float_value(typed_detail["pitching_assigned_starts"]), 4)
        if typed_detail["pitching_assigned_starts"] is not None
        else None,
        "pitching_assigned_non_start_appearances": round(
            _float_value(typed_detail["pitching_assigned_non_start_appearances"]),
            4,
        )
        if typed_detail["pitching_assigned_non_start_appearances"] is not None
        else None,
        "pitching_assigned_ip": round(_float_value(typed_detail["pitching_assigned_ip"]), 4)
        if typed_detail["pitching_assigned_ip"] is not None
        else None,
        "hitting_projected_games": round(_float_value(typed_detail["hitting_projected_games"]), 4),
        "pitching_projected_appearances": round(_float_value(typed_detail["pitching_projected_appearances"]), 4),
        "pitching_projected_starts": round(_float_value(typed_detail["pitching_projected_starts"]), 4),
        "pitching_projected_ip": round(_float_value(typed_detail["pitching_projected_ip"]), 4),
        "hitting_replacement": round(_float_value(typed_detail["hitting_replacement"]), 4)
        if typed_detail["hitting_replacement"] is not None
        else None,
        "pitching_replacement": round(_float_value(typed_detail["pitching_replacement"]), 4)
        if typed_detail["pitching_replacement"] is not None
        else None,
        "hitting_best_slot": typed_detail["hitting_best_slot"],
        "pitching_best_slot": typed_detail["pitching_best_slot"],
        "hitting_value": round(_float_value(typed_detail["hitting_value"]), 4)
        if typed_detail["hitting_value"] is not None
        else None,
        "pitching_value": round(_float_value(typed_detail["pitching_value"]), 4)
        if typed_detail["pitching_value"] is not None
        else None,
        "hitting_assignment_slot": typed_detail["hitting_assignment_slot"],
        "pitching_assignment_slot": typed_detail["pitching_assignment_slot"],
        "hitting_assignment_value": round(_float_value(typed_detail["hitting_assignment_value"]), 4),
        "pitching_assignment_value": round(_float_value(typed_detail["pitching_assignment_value"]), 4),
        "hitting_assignment_replacement": round(_float_value(typed_detail["hitting_assignment_replacement"]), 4)
        if typed_detail["hitting_assignment_slot"] is not None
        else None,
        "pitching_assignment_replacement": round(_float_value(typed_detail["pitching_assignment_replacement"]), 4)
        if typed_detail["pitching_assignment_slot"] is not None
        else None,
        "selected_side": typed_detail["selected_side"],
        "selected_raw_points": round(_float_value(typed_detail["selected_raw_points"]), 4),
        "selected_points_unadjusted": round(_float_value(typed_detail["selected_points_unadjusted"]), 4),
        "selected_points": round(float(adjusted_value), 4),
        "discount_factor": round(float(keep_drop.discount_factors[idx]), 6),
        "discounted_contribution": round(float(keep_drop.discounted_contributions[idx]), 4),
        "keep_drop_value": round(float(keep_drop.continuation_values[idx]), 4),
        "keep_drop_hold_value": round(float(keep_drop.hold_values[idx]), 4),
        "keep_drop_keep": bool(keep_drop.keep_flags[idx]),
        "hitting": typed_detail["hitting"],
        "pitching": typed_detail["pitching"],
    }


def build_points_result_rows(
    *,
    player_meta: dict[str, dict[str, Any]],
    player_year_details: dict[str, list[dict[str, Any]]],
    player_profile: dict[str, str],
    minor_eligibility_by_year: dict[tuple[str, int], bool],
    start_year: int,
    valuation_year_set: list[int],
    discount: float,
    enable_prospect_risk_adjustment: bool,
    minor_stash_players: set[str],
    ir_stash_players: set[str],
    bench_stash_players: set[str],
    enable_ir_stash_relief: bool,
    ir_negative_penalty: float,
    enable_bench_stash_relief: bool,
    bench_negative_penalty: float,
    hitter_ab_by_player_year: dict[tuple[str, int], float],
    pitcher_ip_by_player_year: dict[tuple[str, int], float],
) -> list[dict[str, Any]]:
    result_rows: list[dict[str, Any]] = []
    for player_id, meta_row in player_meta.items():
        row_out: dict[str, Any] = dict(meta_row)
        row_out["minor_eligible"] = bool(
            row_out.get("minor_eligible")
            or minor_eligibility_by_year.get((player_id, int(start_year)), False)
        )
        explain_points_by_year: dict[str, dict[str, Any]] = {}
        row_out["_ExplainPointsByYear"] = explain_points_by_year
        year_details = player_year_details.get(player_id, [])
        adjusted_values: list[float] = []

        for detail in year_details:
            typed_detail = cast(dict[str, Any], detail)
            year = int(cast(Any, typed_detail["year"]))
            adjusted_value = _float_value(typed_detail["selected_points_unadjusted"])
            adjusted_value *= _prospect_risk_multiplier(
                year=year,
                start_year=start_year,
                profile=player_profile.get(player_id, "hitter"),
                minor_eligible=bool(minor_eligibility_by_year.get((player_id, year), False)),
                enabled=enable_prospect_risk_adjustment,
            )
            adjusted_value = _apply_negative_value_stash_rules(
                adjusted_value,
                can_minor_stash=player_id in minor_stash_players
                and bool(minor_eligibility_by_year.get((player_id, year), False)),
                can_ir_stash=enable_ir_stash_relief
                and player_id in ir_stash_players
                and _is_near_zero_playing_time(
                    player_id,
                    year,
                    hitter_ab_by_player_year=hitter_ab_by_player_year,
                    pitcher_ip_by_player_year=pitcher_ip_by_player_year,
                ),
                ir_negative_penalty=ir_negative_penalty,
                can_bench_stash=enable_bench_stash_relief and player_id in bench_stash_players,
                bench_negative_penalty=bench_negative_penalty,
            )
            adjusted_values.append(adjusted_value)

        keep_drop = dynasty_keep_or_drop_values(adjusted_values, valuation_year_set, discount=float(discount))

        for idx, detail in enumerate(year_details):
            typed_detail = cast(dict[str, Any], detail)
            year = int(cast(Any, typed_detail["year"]))
            row_out[f"Value_{year}"] = float(adjusted_values[idx])
            explain_points_by_year[str(year)] = _build_points_explain_year(
                detail=typed_detail,
                adjusted_value=float(adjusted_values[idx]),
                keep_drop=keep_drop,
                idx=idx,
            )

        start_year_points = explain_points_by_year.get(str(start_year), {})
        if isinstance(start_year_points, dict):
            row_out["HittingPoints"] = start_year_points.get("hitting_points")
            row_out["PitchingPoints"] = start_year_points.get("pitching_points")
            row_out["SelectedPoints"] = start_year_points.get("selected_points")
            row_out["HittingBestSlot"] = start_year_points.get("hitting_best_slot")
            row_out["PitchingBestSlot"] = start_year_points.get("pitching_best_slot")
            row_out["HittingValue"] = start_year_points.get("hitting_value")
            row_out["PitchingValue"] = start_year_points.get("pitching_value")
            row_out["HittingAssignmentSlot"] = start_year_points.get("hitting_assignment_slot")
            row_out["PitchingAssignmentSlot"] = start_year_points.get("pitching_assignment_slot")
            row_out["HittingAssignmentValue"] = start_year_points.get("hitting_assignment_value")
            row_out["PitchingAssignmentValue"] = start_year_points.get("pitching_assignment_value")
            row_out["KeepDropValue"] = start_year_points.get("keep_drop_value")
            row_out["KeepDropHoldValue"] = start_year_points.get("keep_drop_hold_value")
            row_out["KeepDropKeep"] = start_year_points.get("keep_drop_keep")

        first_year_gap = (
            max(int(valuation_year_set[1]) - int(valuation_year_set[0]), 0)
            if len(valuation_year_set) > 1
            else 0
        )
        start_year_value = float(adjusted_values[0]) if adjusted_values else 0.0
        row_out["RawDynastyValue"] = float(keep_drop.raw_total)
        row_out["StartYearValue"] = start_year_value
        row_out["FutureContinuationValue"] = future_continuation_value(keep_drop)
        row_out["FutureContinuationDiscountGap"] = int(first_year_gap)
        result_rows.append(row_out)

    return result_rows


def build_empty_points_value_frame(
    *,
    valuation_year_set: list[int],
    player_key_col: str,
    player_entity_key_col: str,
) -> pd.DataFrame:
    empty_columns = [
        "Player",
        "Team",
        "Pos",
        "Age",
        "DynastyValue",
        "RawDynastyValue",
        "minor_eligible",
        player_key_col,
        player_entity_key_col,
    ] + [f"Value_{year}" for year in valuation_year_set]
    return pd.DataFrame(columns=empty_columns)


def calculate_points_raw_totals(
    *,
    per_player_year: dict[str, dict[int, dict[str, Any]]],
    valuation_year_set: list[int],
    discount: float,
    two_way: str,
) -> dict[str, float]:
    player_raw_totals: dict[str, float] = {}
    for player_id, year_map in per_player_year.items():
        raw_total = 0.0
        for year_offset, year in enumerate(valuation_year_set):
            typed_info = cast(dict[str, Any], year_map.get(year, {}))
            hit_points = _float_value(typed_info.get("hit_points", 0.0))
            pit_points = _float_value(typed_info.get("pit_points", 0.0))
            hit_slots = set(cast(set[str], typed_info.get("hit_slots", set())))
            pit_slots = set(cast(set[str], typed_info.get("pit_slots", set())))

            selected_raw_points = 0.0
            if hit_slots and pit_slots:
                selected_raw_points = hit_points + pit_points if two_way == "sum" else max(hit_points, pit_points)
            elif hit_slots:
                selected_raw_points = hit_points
            elif pit_slots:
                selected_raw_points = pit_points

            raw_total += selected_raw_points * (float(discount) ** year_offset)
        player_raw_totals[player_id] = float(raw_total)
    return player_raw_totals


def start_capable_pitcher_replacement_value(
    *,
    points_slot_replacement: Callable[..., dict[str, float]],
    year_pit_entries: dict[int, list[dict[str, Any]]],
    start_year: int,
    year_start_capable_pitcher_ids: dict[int, set[str]],
    starter_replacement_rostered_ids: set[str],
    n_replacement: int,
) -> float:
    start_capable_pitcher_replacement = points_slot_replacement(
        [
            entry
            for entry in year_pit_entries.get(start_year, [])
            if str(entry.get("player_id") or "") in year_start_capable_pitcher_ids.get(start_year, set())
        ],
        active_slots={"P"},
        rostered_player_ids=starter_replacement_rostered_ids,
        n_replacement=n_replacement,
    )
    return _float_value(start_capable_pitcher_replacement.get("P", 0.0))


def finalize_points_dynasty_output(
    *,
    result_rows: list[dict[str, Any]],
    valuation_year_set: list[int],
    player_key_col: str,
    player_entity_key_col: str,
    rostered_player_ids: set[str],
    replacement_rank: int,
    in_season_replacement_rank: int,
    active_depth_per_team: int,
    in_season_depth_per_team: int,
    discount: float,
    keeper_limit: int | None,
    keeper_continuation_rank: int | None,
    points_valuation_mode: str,
    weekly_starts_cap: int | None,
    allow_same_day_starts_overflow: bool,
    weekly_acquisition_cap: int | None,
    use_h2h_roster_model: bool,
    modeled_ir_roster_ids: set[str],
    modeled_minor_roster_ids: set[str],
    modeled_bench_hitters_per_team_by_year: dict[int, int],
    modeled_bench_pitchers_per_team_by_year: dict[int, int],
    modeled_held_pitchers_per_team_by_year: dict[int, int],
    modeled_held_starter_pitchers_per_team_by_year: dict[int, int],
    modeled_held_relievers_per_team_by_year: dict[int, int],
    starter_slot_capacity: int,
    starter_pitcher_replacement_start_year: float | None,
    hitter_usage_diagnostics_by_year: dict[int, dict[str, object]],
    pitcher_usage_diagnostics_by_year: dict[int, dict[str, object]],
    start_year: int,
    teams: int,
) -> pd.DataFrame:
    if not result_rows:
        empty_columns = [
            "Player",
            "Team",
            "Pos",
            "Age",
            "DynastyValue",
            "RawDynastyValue",
            "StartYearValue",
            "FutureContinuationValue",
            "FutureContinuationDiscountGap",
            "KeeperAdjustedFutureContinuationValue",
            "ForcedRosterValue",
            "CenteringScore",
            "CenteringMode",
            "ForcedRosterFallbackApplied",
            "CenteringBaselineValue",
            "CenteringScoreBaselineValue",
            "minor_eligible",
            player_key_col,
            player_entity_key_col,
        ] + [f"Value_{year}" for year in valuation_year_set]
        return pd.DataFrame(columns=empty_columns)

    out = pd.DataFrame.from_records(result_rows)
    raw_series = pd.to_numeric(out["RawDynastyValue"], errors="coerce").fillna(0.0)
    if use_h2h_roster_model:
        raw_baseline_value = points_centering_baseline_for_roster(
            out,
            score_col="RawDynastyValue",
            rostered_player_ids=rostered_player_ids,
            minimum_roster_size=replacement_rank,
            player_entity_key_col=player_entity_key_col,
            player_key_col=player_key_col,
        )
    else:
        raw_baseline_value = points_centering_baseline(
            out,
            score_col="RawDynastyValue",
            replacement_rank=replacement_rank,
            player_entity_key_col=player_entity_key_col,
            player_key_col=player_key_col,
        )

    future_continuation_baseline_value: float | None = None
    if keeper_continuation_rank is not None:
        future_continuation_baseline_value = points_centering_baseline(
            out,
            score_col="FutureContinuationValue",
            replacement_rank=keeper_continuation_rank,
            player_entity_key_col=player_entity_key_col,
            player_key_col=player_key_col,
        )

    keeper_adjusted_future_continuation = pd.to_numeric(
        out["FutureContinuationValue"],
        errors="coerce",
    ).fillna(0.0)
    if future_continuation_baseline_value is not None:
        keeper_adjusted_future_continuation = keeper_adjusted_future_continuation - float(
            future_continuation_baseline_value
        )
    out["KeeperAdjustedFutureContinuationValue"] = keeper_adjusted_future_continuation.astype(float)
    out["ForcedRosterValue"] = (
        pd.to_numeric(out["StartYearValue"], errors="coerce").fillna(0.0)
        + pd.to_numeric(out["FutureContinuationDiscountGap"], errors="coerce").fillna(0.0).map(
            lambda gap: float(discount) ** int(max(gap, 0))
        )
        * keeper_adjusted_future_continuation
    )
    h2h_keeper_adjusted_scoring = bool(use_h2h_roster_model and keeper_limit is not None)
    out["CenteringScore"] = (
        pd.to_numeric(out["ForcedRosterValue"], errors="coerce").fillna(0.0)
        if h2h_keeper_adjusted_scoring
        else raw_series.astype(float)
    )

    raw_zero_mask = raw_series.abs() <= float(POINTS_CENTERING_ZERO_EPSILON)
    raw_zero_value_count = int(raw_zero_mask.sum())
    raw_zero_share = (float(raw_zero_value_count) / float(len(out))) if len(out) else 0.0

    if use_h2h_roster_model:
        centering_score_baseline_value = points_centering_baseline_for_roster(
            out,
            score_col="CenteringScore",
            rostered_player_ids=rostered_player_ids,
            minimum_roster_size=replacement_rank,
            player_entity_key_col=player_entity_key_col,
            player_key_col=player_key_col,
        )
    else:
        centering_score_baseline_value = points_centering_baseline(
            out,
            score_col="CenteringScore",
            replacement_rank=replacement_rank,
            player_entity_key_col=player_entity_key_col,
            player_key_col=player_key_col,
        )
    centering_score_series = pd.to_numeric(out["CenteringScore"], errors="coerce").fillna(0.0)
    centering_score_zero_share = (
        float((centering_score_series.abs() <= float(POINTS_CENTERING_ZERO_EPSILON)).sum()) / float(len(out))
        if len(out)
        else 0.0
    )
    deep_roster_zero_baseline_warning = bool(
        abs(float(centering_score_baseline_value)) <= float(POINTS_CENTERING_ZERO_EPSILON)
        and len(out) > 0
        and (
            centering_score_zero_share >= float(POINTS_DEEP_ROSTER_ZERO_CLUSTER_MIN_SHARE)
            if h2h_keeper_adjusted_scoring
            else raw_zero_share >= float(POINTS_DEEP_ROSTER_ZERO_CLUSTER_MIN_SHARE)
        )
    )

    centering_mode = "keeper_adjusted_h2h" if h2h_keeper_adjusted_scoring else "standard"
    forced_roster_fallback_applied = False
    if deep_roster_zero_baseline_warning and not h2h_keeper_adjusted_scoring:
        forced_roster_zero_mask = raw_zero_mask.copy()
        if use_h2h_roster_model:
            player_entity = out[player_entity_key_col].astype(str)
            player_key = out[player_key_col].astype(str)
            healthy_roster_mask = player_entity.isin(rostered_player_ids) | player_key.isin(rostered_player_ids)
            forced_roster_zero_mask = raw_zero_mask & healthy_roster_mask
        if bool(forced_roster_zero_mask.any()):
            out.loc[forced_roster_zero_mask, "CenteringScore"] = pd.to_numeric(
                out.loc[forced_roster_zero_mask, "ForcedRosterValue"],
                errors="coerce",
            ).fillna(0.0)
            if use_h2h_roster_model:
                centering_score_baseline_value = points_centering_baseline_for_roster(
                    out,
                    score_col="CenteringScore",
                    rostered_player_ids=rostered_player_ids,
                    minimum_roster_size=replacement_rank,
                    player_entity_key_col=player_entity_key_col,
                    player_key_col=player_key_col,
                )
            else:
                centering_score_baseline_value = points_centering_baseline(
                    out,
                    score_col="CenteringScore",
                    replacement_rank=replacement_rank,
                    player_entity_key_col=player_entity_key_col,
                    player_key_col=player_key_col,
                )
            centering_mode = "forced_roster"
            forced_roster_fallback_applied = True

    out["DynastyValue"] = pd.to_numeric(out["CenteringScore"], errors="coerce").fillna(0.0) - float(
        centering_score_baseline_value
    )
    out["CenteringMode"] = centering_mode
    out["ForcedRosterFallbackApplied"] = forced_roster_fallback_applied
    out["CenteringBaselineValue"] = float(raw_baseline_value)
    out["CenteringScoreBaselineValue"] = float(centering_score_baseline_value)

    centering_score_series = pd.to_numeric(out["CenteringScore"], errors="coerce").fillna(0.0)
    dynasty_series = pd.to_numeric(out["DynastyValue"], errors="coerce").fillna(0.0)
    valuation_diagnostics: dict[str, object] = {
        "PointsValuationMode": points_valuation_mode,
        "KeeperLimit": int(keeper_limit) if keeper_limit is not None else None,
        "H2HKeeperAdjustedScoringApplied": bool(h2h_keeper_adjusted_scoring),
        "KeeperContinuationRank": int(keeper_continuation_rank) if keeper_continuation_rank is not None else None,
        "KeeperContinuationBaselineValue": (
            float(future_continuation_baseline_value)
            if future_continuation_baseline_value is not None
            else None
        ),
        "ReplacementRank": int(replacement_rank),
        "InSeasonReplacementRank": int(in_season_replacement_rank),
        "ActiveDepthPerTeam": int(active_depth_per_team),
        "InSeasonDepthPerTeam": int(in_season_depth_per_team),
        "CenteringMode": centering_mode,
        "ForcedRosterFallbackApplied": forced_roster_fallback_applied,
        "CenteringBaselineValue": float(raw_baseline_value),
        "CenteringScoreBaselineValue": float(centering_score_baseline_value),
        "RawZeroValuePlayerCount": int(raw_zero_value_count),
        "CenteringScoreZeroPlayerCount": int(
            (centering_score_series.abs() <= float(POINTS_CENTERING_ZERO_EPSILON)).sum()
        ),
        "DynastyZeroValuePlayerCount": int((dynasty_series.abs() <= float(POINTS_CENTERING_ZERO_EPSILON)).sum()),
        "PositiveValuePlayerCount": int((dynasty_series > float(POINTS_CENTERING_ZERO_EPSILON)).sum()),
        "deep_roster_zero_baseline_warning": deep_roster_zero_baseline_warning,
        "HitterUsageByYear": {
            str(year): diagnostics
            for year, diagnostics in sorted(hitter_usage_diagnostics_by_year.items())
        },
        "PitcherUsageByYear": {
            str(year): diagnostics
            for year, diagnostics in sorted(pitcher_usage_diagnostics_by_year.items())
        },
    }
    if use_h2h_roster_model:
        start_year_pitcher_diag = cast(dict[str, Any], pitcher_usage_diagnostics_by_year.get(start_year, {}) or {})
        valuation_diagnostics.update(
            {
                "ModeledBenchHittersPerTeam": int(modeled_bench_hitters_per_team_by_year.get(start_year, 0)),
                "ModeledBenchPitchersPerTeam": int(modeled_bench_pitchers_per_team_by_year.get(start_year, 0)),
                "ModeledHeldPitchersPerTeam": int(
                    modeled_held_pitchers_per_team_by_year.get(start_year, max(int(starter_slot_capacity), 0))
                ),
                "ModeledHeldStarterPitchersPerTeam": int(
                    modeled_held_starter_pitchers_per_team_by_year.get(start_year, 0)
                ),
                "ModeledHeldRelieversPerTeam": int(modeled_held_relievers_per_team_by_year.get(start_year, 0)),
                "ModeledReserveRosterSize": int(len(rostered_player_ids)),
                "ModeledIrRosterSize": int(len(modeled_ir_roster_ids)),
                "ModeledMinorRosterSize": int(len(modeled_minor_roster_ids)),
                "ModeledStarterPitcherReplacement": (
                    float(starter_pitcher_replacement_start_year)
                    if starter_pitcher_replacement_start_year is not None
                    else None
                ),
                "ModeledEffectiveWeeklyStartsCap": (
                    round(
                        (
                            _float_value(start_year_pitcher_diag.get("selected_held_starts"))
                            + _float_value(start_year_pitcher_diag.get("selected_streamed_starts"))
                        )
                        / float(_SEASON_WEEKS * max(int(teams), 1)),
                        4,
                    )
                    if points_valuation_mode == "daily_h2h"
                    else None
                ),
                "ModeledOverflowStartsPerWeek": (
                    round(
                        _float_value(start_year_pitcher_diag.get("selected_overflow_starts"))
                        / float(_SEASON_WEEKS * max(int(teams), 1)),
                        4,
                    )
                    if points_valuation_mode == "daily_h2h"
                    else None
                ),
            }
        )
    if points_valuation_mode == "weekly_h2h":
        valuation_diagnostics.update(
            {
                "WeeklyStartsCap": weekly_starts_cap,
                "AllowSameDayStartsOverflow": bool(allow_same_day_starts_overflow),
                "WeeklyAcquisitionCap": weekly_acquisition_cap,
                "WeeklyPitchingByYear": {
                    str(year): diagnostics
                    for year, diagnostics in sorted(pitcher_usage_diagnostics_by_year.items())
                },
            }
        )
    if points_valuation_mode == "daily_h2h":
        valuation_diagnostics.update(
            {
                "WeeklyStartsCap": weekly_starts_cap,
                "AllowSameDayStartsOverflow": bool(allow_same_day_starts_overflow),
                "WeeklyAcquisitionCap": weekly_acquisition_cap,
                "SyntheticSeasonDays": int(SYNTHETIC_SEASON_DAYS),
                "SyntheticPeriodDays": int(SYNTHETIC_PERIOD_DAYS),
                "DailyPitchingByYear": {
                    str(year): diagnostics
                    for year, diagnostics in sorted(pitcher_usage_diagnostics_by_year.items())
                },
            }
        )
    out.attrs["valuation_diagnostics"] = valuation_diagnostics
    return out
