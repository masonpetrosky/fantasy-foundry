"""League-mode dynasty calculator orchestration helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd


def calculate_league_dynasty_frame(
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
    sgp_denominator_mode: str = "classic",
    sgp_winsor_low_pct: float = 0.10,
    sgp_winsor_high_pct: float = 0.90,
    sgp_epsilon_counting: float = 0.15,
    sgp_epsilon_ratio: float = 0.0015,
    enable_playing_time_reliability: bool = False,
    enable_age_risk_adjustment: bool = False,
    enable_replacement_blend: bool = False,
    replacement_blend_alpha: float = 0.70,
) -> pd.DataFrame:
    ensure_backend_module_path_fn()
    from backend.valuation.league_orchestration import calculate_league_dynasty_values
    from backend.valuation.models import LeagueSettings

    lg = LeagueSettings(
        n_teams=teams,
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
        ip_min=ip_min,
        ip_max=ip_max if ip_max is not None else 1500.0,
        bench_slots=bench,
        minor_slots=minors,
        ir_slots=ir,
        sims_for_sgp=sims,
        discount=discount,
        horizon_years=horizon,
        freeze_replacement_baselines=True,
        enable_replacement_blend=enable_replacement_blend,
        replacement_blend_alpha=replacement_blend_alpha,
        two_way=two_way,
        sgp_denominator_mode=sgp_denominator_mode,
        sgp_winsor_low_pct=sgp_winsor_low_pct,
        sgp_winsor_high_pct=sgp_winsor_high_pct,
        sgp_epsilon_counting=sgp_epsilon_counting,
        sgp_epsilon_ratio=sgp_epsilon_ratio,
        enable_playing_time_reliability=enable_playing_time_reliability,
        enable_age_risk_adjustment=enable_age_risk_adjustment,
    )

    out = calculate_league_dynasty_values(
        str(excel_path),
        lg,
        start_year=start_year,
        verbose=False,
        return_details=False,
        seed=0,
    )

    # Rename MLBTeam → Team for consistency with common mode output schema.
    if "MLBTeam" in out.columns:
        out = out.rename(columns={"MLBTeam": "Team"})

    return out
