"""Points-mode dynasty calculation helpers and orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

try:
    from backend.core.points_assignment import (
        _SEASON_WEEKS,
        _best_slot_surplus,
        _effective_weekly_starts_cap,
        _slot_capacity_by_league,
        optimize_points_slot_assignment,
    )
    from backend.core.points_calculator_output import finalize_points_calculation
    from backend.core.points_calculator_preparation import (
        build_points_scoring,
        prepare_points_calculation,
    )
    from backend.core.points_calculator_usage import calculate_points_usage_by_year
    from backend.core.points_output import (
        build_empty_points_value_frame,
        build_points_result_rows,
        calculate_points_raw_totals,
        finalize_points_dynasty_output,
        relief_pitcher_replacement_value,
        start_capable_pitcher_replacement_value,
    )
    from backend.core.points_roster_model import (
        POINTS_CENTERING_ZERO_EPSILON,
        active_points_roster_ids,
        is_h2h_points_mode,
        model_h2h_points_roster,
        modeled_bench_hitter_slots_per_team,
        per_day_slot_capacity,
        select_points_stash_groups,
    )
    from backend.core.points_utils import (
        _scale_points_breakdown,
        calculate_hitter_points_breakdown,
        calculate_pitcher_points_breakdown,
        coerce_minor_eligible,
        points_hitter_eligible_slots,
        points_pitcher_eligible_slots,
        points_player_identity,
        points_slot_replacement,
        projection_identity_key,
        stat_or_zero,
        valuation_years,
    )
    from backend.core.points_value import (
        KeepDropResult,
        _is_near_zero_playing_time,
        _negative_fallback_value,
        _prospect_risk_multiplier,
        dynasty_keep_or_drop_values,
    )
    from backend.valuation.active_volume import (
        SYNTHETIC_PERIOD_DAYS,
        SYNTHETIC_SEASON_DAYS,
        VolumeEntry,
        allocate_hitter_usage,
        allocate_hitter_usage_daily,
        allocate_hitter_usage_daily_detail,
        allocate_pitcher_innings_budget,
        allocate_pitcher_usage,
        allocate_pitcher_usage_daily,
        annual_slot_capacity,
    )
    from backend.valuation.minor_eligibility import _resolve_minor_eligibility_by_year
    from backend.valuation.models import CommonDynastyRotoSettings
except ImportError:  # pragma: no cover - direct script execution fallback
    from points_assignment import (  # type: ignore[no-redef]
        _SEASON_WEEKS,
        _best_slot_surplus,
        _effective_weekly_starts_cap,
        _slot_capacity_by_league,
        optimize_points_slot_assignment,
    )
    from points_calculator_output import finalize_points_calculation  # type: ignore[no-redef]
    from points_calculator_preparation import (  # type: ignore[no-redef]
        build_points_scoring,
        prepare_points_calculation,
    )
    from points_calculator_usage import calculate_points_usage_by_year  # type: ignore[no-redef]
    from points_output import (  # type: ignore[no-redef]
        build_empty_points_value_frame,
        build_points_result_rows,
        calculate_points_raw_totals,
        finalize_points_dynasty_output,
        relief_pitcher_replacement_value,
        start_capable_pitcher_replacement_value,
    )
    from points_roster_model import (  # type: ignore[no-redef]
        POINTS_CENTERING_ZERO_EPSILON,
        active_points_roster_ids,
        is_h2h_points_mode,
        model_h2h_points_roster,
        modeled_bench_hitter_slots_per_team,
        per_day_slot_capacity,
        select_points_stash_groups,
    )
    from points_utils import (  # type: ignore[no-redef]
        _scale_points_breakdown,
        calculate_hitter_points_breakdown,
        calculate_pitcher_points_breakdown,
        coerce_minor_eligible,
        points_hitter_eligible_slots,
        points_pitcher_eligible_slots,
        points_player_identity,
        points_slot_replacement,
        projection_identity_key,
        stat_or_zero,
        valuation_years,
    )
    from points_value import (  # type: ignore[no-redef]
        KeepDropResult,
        _is_near_zero_playing_time,
        _negative_fallback_value,
        _prospect_risk_multiplier,
        dynasty_keep_or_drop_values,
    )
    from valuation.active_volume import (  # type: ignore[no-redef]
        SYNTHETIC_PERIOD_DAYS,
        SYNTHETIC_SEASON_DAYS,
        VolumeEntry,
        allocate_hitter_usage,
        allocate_hitter_usage_daily,
        allocate_hitter_usage_daily_detail,
        allocate_pitcher_innings_budget,
        allocate_pitcher_usage,
        allocate_pitcher_usage_daily,
        annual_slot_capacity,
    )
    from valuation.minor_eligibility import _resolve_minor_eligibility_by_year  # type: ignore[no-redef]
    from valuation.models import CommonDynastyRotoSettings  # type: ignore[no-redef]


@dataclass(slots=True)
class PointsCalculatorContext:
    bat_data: list[dict[str, Any]]
    pit_data: list[dict[str, Any]]
    bat_data_raw: list[dict[str, Any]]
    pit_data_raw: list[dict[str, Any]]
    meta: dict[str, Any]
    average_recent_projection_rows: Callable[..., list[dict[str, Any]]]
    coerce_meta_years: Callable[[dict[str, Any]], list[int]]
    valuation_years: Callable[[int, int, list[int]], list[int]]
    coerce_record_year: Callable[[object], int | None]
    points_player_identity: Callable[[dict[str, Any]], str]
    normalize_player_key: Callable[[object], str]
    player_key_col: str
    player_entity_key_col: str
    row_team_value: Callable[[dict[str, Any]], str]
    merge_position_value: Callable[[object, object], str | None]
    coerce_minor_eligible: Callable[[object], bool]
    calculate_hitter_points_breakdown: Callable[[dict[str, Any] | None, dict[str, float]], dict[str, Any]]
    calculate_pitcher_points_breakdown: Callable[[dict[str, Any] | None, dict[str, float]], dict[str, Any]]
    stat_or_zero: Callable[[dict[str, Any] | None, str], float]
    points_hitter_eligible_slots: Callable[[object], set[str]]
    points_pitcher_eligible_slots: Callable[[object], set[str]]
    points_slot_replacement: Callable[..., dict[str, float]]


__all__ = [
    "KeepDropResult",
    "PointsCalculatorContext",
    "calculate_hitter_points_breakdown",
    "calculate_pitcher_points_breakdown",
    "calculate_points_dynasty_frame",
    "coerce_minor_eligible",
    "dynasty_keep_or_drop_values",
    "optimize_points_slot_assignment",
    "points_hitter_eligible_slots",
    "points_pitcher_eligible_slots",
    "points_player_identity",
    "points_slot_replacement",
    "projection_identity_key",
    "stat_or_zero",
    "valuation_years",
]


def calculate_points_dynasty_frame(
    *,
    ctx: PointsCalculatorContext,
    teams: int,
    horizon: int,
    discount: float,
    hit_c: int,
    hit_1b: int,
    hit_2b: int,
    hit_3b: int,
    hit_ss: int,
    hit_ci: int,
    hit_mi: int,
    hit_of: int,
    hit_ut: int,
    pit_p: int,
    pit_sp: int,
    pit_rp: int,
    bench: int,
    minors: int,
    ir: int,
    keeper_limit: int | None,
    two_way: str,
    points_valuation_mode: str,
    weekly_starts_cap: int | None,
    allow_same_day_starts_overflow: bool,
    weekly_acquisition_cap: int | None,
    start_year: int,
    pts_hit_1b: float,
    pts_hit_2b: float,
    pts_hit_3b: float,
    pts_hit_hr: float,
    pts_hit_r: float,
    pts_hit_rbi: float,
    pts_hit_sb: float,
    pts_hit_bb: float,
    pts_hit_hbp: float,
    pts_hit_so: float,
    pts_pit_ip: float,
    pts_pit_w: float,
    pts_pit_l: float,
    pts_pit_k: float,
    pts_pit_sv: float,
    pts_pit_hld: float,
    pts_pit_h: float,
    pts_pit_er: float,
    pts_pit_bb: float,
    pts_pit_hbp: float,
    ip_max: float | None = None,
    enable_prospect_risk_adjustment: bool = True,
    enable_bench_stash_relief: bool = False,
    bench_negative_penalty: float = 0.55,
    enable_ir_stash_relief: bool = False,
    ir_negative_penalty: float = 0.20,
    hit_dh: int = 0,
) -> pd.DataFrame:
    scoring = build_points_scoring(
        pts_hit_1b=pts_hit_1b,
        pts_hit_2b=pts_hit_2b,
        pts_hit_3b=pts_hit_3b,
        pts_hit_hr=pts_hit_hr,
        pts_hit_r=pts_hit_r,
        pts_hit_rbi=pts_hit_rbi,
        pts_hit_sb=pts_hit_sb,
        pts_hit_bb=pts_hit_bb,
        pts_hit_hbp=pts_hit_hbp,
        pts_hit_so=pts_hit_so,
        pts_pit_ip=pts_pit_ip,
        pts_pit_w=pts_pit_w,
        pts_pit_l=pts_pit_l,
        pts_pit_k=pts_pit_k,
        pts_pit_sv=pts_pit_sv,
        pts_pit_hld=pts_pit_hld,
        pts_pit_h=pts_pit_h,
        pts_pit_er=pts_pit_er,
        pts_pit_bb=pts_pit_bb,
        pts_pit_hbp=pts_pit_hbp,
    )
    prep = prepare_points_calculation(
        ctx=ctx,
        scoring=scoring,
        teams=teams,
        horizon=horizon,
        keeper_limit=keeper_limit,
        points_valuation_mode=points_valuation_mode,
        bench=bench,
        minors=minors,
        ir=ir,
        start_year=start_year,
        hit_c=hit_c,
        hit_1b=hit_1b,
        hit_2b=hit_2b,
        hit_3b=hit_3b,
        hit_ss=hit_ss,
        hit_ci=hit_ci,
        hit_mi=hit_mi,
        hit_of=hit_of,
        hit_ut=hit_ut,
        pit_p=pit_p,
        pit_sp=pit_sp,
        pit_rp=pit_rp,
        hit_dh=hit_dh,
        common_settings_factory=CommonDynastyRotoSettings,
        resolve_minor_eligibility_by_year=_resolve_minor_eligibility_by_year,
        is_h2h_points_mode=is_h2h_points_mode,
        annual_slot_capacity=annual_slot_capacity,
        synthetic_season_days=SYNTHETIC_SEASON_DAYS,
    )
    usage = calculate_points_usage_by_year(
        prep=prep,
        teams=teams,
        bench=bench,
        points_valuation_mode=points_valuation_mode,
        weekly_starts_cap=weekly_starts_cap,
        allow_same_day_starts_overflow=allow_same_day_starts_overflow,
        weekly_acquisition_cap=weekly_acquisition_cap,
        ip_max=ip_max,
        season_weeks=int(_SEASON_WEEKS),
        synthetic_season_days=SYNTHETIC_SEASON_DAYS,
        synthetic_period_days=SYNTHETIC_PERIOD_DAYS,
        volume_entry_factory=VolumeEntry,
        allocate_hitter_usage=allocate_hitter_usage,
        allocate_hitter_usage_daily=allocate_hitter_usage_daily,
        allocate_hitter_usage_daily_detail=allocate_hitter_usage_daily_detail,
        allocate_pitcher_usage=allocate_pitcher_usage,
        allocate_pitcher_usage_daily=allocate_pitcher_usage_daily,
        allocate_pitcher_innings_budget=allocate_pitcher_innings_budget,
        active_points_roster_ids=active_points_roster_ids,
        per_day_slot_capacity=per_day_slot_capacity,
        modeled_bench_hitter_slots_per_team=modeled_bench_hitter_slots_per_team,
        effective_weekly_starts_cap=_effective_weekly_starts_cap,
        scale_points_breakdown=_scale_points_breakdown,
    )
    return finalize_points_calculation(
        ctx=ctx,
        prep=prep,
        usage=usage,
        teams=teams,
        bench=bench,
        minors=minors,
        ir=ir,
        start_year=start_year,
        discount=discount,
        two_way=two_way,
        keeper_limit=keeper_limit,
        points_valuation_mode=points_valuation_mode,
        weekly_starts_cap=weekly_starts_cap,
        allow_same_day_starts_overflow=allow_same_day_starts_overflow,
        weekly_acquisition_cap=weekly_acquisition_cap,
        enable_prospect_risk_adjustment=enable_prospect_risk_adjustment,
        enable_bench_stash_relief=enable_bench_stash_relief,
        bench_negative_penalty=bench_negative_penalty,
        enable_ir_stash_relief=enable_ir_stash_relief,
        ir_negative_penalty=ir_negative_penalty,
        build_empty_points_value_frame=build_empty_points_value_frame,
        calculate_points_raw_totals=calculate_points_raw_totals,
        model_h2h_points_roster=model_h2h_points_roster,
        start_capable_pitcher_replacement_value=start_capable_pitcher_replacement_value,
        relief_pitcher_replacement_value=relief_pitcher_replacement_value,
        slot_capacity_by_league=_slot_capacity_by_league,
        optimize_points_slot_assignment=optimize_points_slot_assignment,
        best_slot_surplus=_best_slot_surplus,
        negative_fallback_value=_negative_fallback_value,
        is_near_zero_playing_time=_is_near_zero_playing_time,
        prospect_risk_multiplier=_prospect_risk_multiplier,
        dynasty_keep_or_drop_values=dynasty_keep_or_drop_values,
        select_points_stash_groups=select_points_stash_groups,
        build_points_result_rows=build_points_result_rows,
        finalize_points_dynasty_output=finalize_points_dynasty_output,
        points_centering_zero_epsilon=POINTS_CENTERING_ZERO_EPSILON,
    )
