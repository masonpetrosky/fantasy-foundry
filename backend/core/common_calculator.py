"""Common (roto) dynasty calculator orchestration helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pandas as pd

from backend.services.valuation import ValuationService


def _parse_replacement_depth_blend_alpha_by_slot(raw_value: object) -> dict[str, float]:
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return {}
        try:
            raw_value = json.loads(text)
        except json.JSONDecodeError:
            return {}
    if not isinstance(raw_value, dict):
        return {}
    out: dict[str, float] = {}
    for raw_slot, raw_alpha in raw_value.items():
        slot = str(raw_slot or "").strip().upper()
        if not slot:
            continue
        try:
            alpha = float(raw_alpha)
        except (TypeError, ValueError):
            continue
        out[slot] = min(max(alpha, 0.0), 1.0)
    return out


def calculate_common_dynasty_frame(
    *,
    ensure_backend_module_path_fn: Callable[[], None],
    excel_path: Path | str,
    teams: int,
    sims: int,
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
    ip_min: float,
    ip_max: float | None,
    two_way: str,
    start_year: int,
    roto_category_settings: dict[str, bool],
    roto_hitter_fields: tuple[tuple[str, str, bool], ...],
    roto_pitcher_fields: tuple[tuple[str, str, bool], ...],
    coerce_bool_fn: Callable[..., bool],
    sgp_denominator_mode: str = "classic",
    sgp_winsor_low_pct: float = 0.10,
    sgp_winsor_high_pct: float = 0.90,
    sgp_epsilon_counting: float = 0.15,
    sgp_epsilon_ratio: float = 0.0015,
    enable_playing_time_reliability: bool = False,
    enable_age_risk_adjustment: bool = False,
    enable_prospect_risk_adjustment: bool = True,
    enable_bench_stash_relief: bool = False,
    bench_negative_penalty: float = 0.55,
    enable_ir_stash_relief: bool = False,
    ir_negative_penalty: float = 0.20,
    enable_replacement_blend: bool = True,
    replacement_blend_alpha: float = 0.40,
    replacement_depth_mode: str = "blended_depth",
    replacement_depth_blend_alpha: float = 0.33,
    replacement_depth_blend_alpha_by_slot_json: str = "",
    hit_dh: int = 0,
) -> pd.DataFrame:
    valuation_service = ValuationService(ensure_backend_module_path_fn=ensure_backend_module_path_fn)

    hitter_categories = [
        stat_col
        for field_key, stat_col, default_value in roto_hitter_fields
        if coerce_bool_fn(roto_category_settings.get(field_key), default=bool(default_value))
    ]
    pitcher_categories = [
        stat_col
        for field_key, stat_col, default_value in roto_pitcher_fields
        if coerce_bool_fn(roto_category_settings.get(field_key), default=bool(default_value))
    ]

    league_settings = valuation_service.build_common_roto_settings(
        n_teams=teams,
        sims_for_sgp=sims,
        horizon_years=horizon,
        discount=discount,
        hitter_slots={
            "C": hit_c,
            "1B": hit_1b,
            "2B": hit_2b,
            "3B": hit_3b,
            "SS": hit_ss,
            "CI": hit_ci,
            "MI": hit_mi,
            "OF": hit_of,
            "DH": hit_dh,
            "UT": hit_ut,
        },
        pitcher_slots={
            "P": pit_p,
            "SP": pit_sp,
            "RP": pit_rp,
        },
        bench_slots=bench,
        minor_slots=minors,
        ir_slots=ir,
        ip_min=ip_min,
        ip_max=ip_max,
        two_way=two_way,
        sgp_denominator_mode=sgp_denominator_mode,
        sgp_winsor_low_pct=sgp_winsor_low_pct,
        sgp_winsor_high_pct=sgp_winsor_high_pct,
        sgp_epsilon_counting=sgp_epsilon_counting,
        sgp_epsilon_ratio=sgp_epsilon_ratio,
        enable_playing_time_reliability=enable_playing_time_reliability,
        enable_age_risk_adjustment=enable_age_risk_adjustment,
        enable_prospect_risk_adjustment=enable_prospect_risk_adjustment,
        enable_bench_stash_relief=enable_bench_stash_relief,
        bench_negative_penalty=bench_negative_penalty,
        enable_ir_stash_relief=enable_ir_stash_relief,
        ir_negative_penalty=ir_negative_penalty,
        enable_replacement_blend=enable_replacement_blend,
        replacement_blend_alpha=replacement_blend_alpha,
        replacement_depth_mode=replacement_depth_mode,
        replacement_depth_blend_alpha=replacement_depth_blend_alpha,
        replacement_depth_blend_alpha_by_slot=_parse_replacement_depth_blend_alpha_by_slot(
            replacement_depth_blend_alpha_by_slot_json
        ),
        hitter_categories=tuple(hitter_categories),
        pitcher_categories=tuple(pitcher_categories),
    )

    return valuation_service.calculate_common_dynasty_values(
        excel_path,
        league_settings,
        start_year=start_year,
    )
