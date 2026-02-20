"""Common (roto) dynasty calculator orchestration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd


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
    recent_projections: int,
    roto_category_settings: dict[str, bool],
    roto_hitter_fields: tuple[tuple[str, str, bool], ...],
    roto_pitcher_fields: tuple[tuple[str, str, bool], ...],
    coerce_bool_fn: Callable[..., bool],
) -> pd.DataFrame:
    ensure_backend_module_path_fn()
    from dynasty_roto_values import CommonDynastyRotoSettings, calculate_common_dynasty_values

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

    league_settings = CommonDynastyRotoSettings(
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
        hitter_categories=tuple(hitter_categories),
        pitcher_categories=tuple(pitcher_categories),
    )

    return calculate_common_dynasty_values(
        str(excel_path),
        league_settings,
        start_year=start_year,
        verbose=False,
        return_details=False,
        seed=0,
        recent_projections=recent_projections,
    )
