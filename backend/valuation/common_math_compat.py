"""Legacy common-math helper exports routed through extracted valuation modules."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Optional

import numpy as np
import pandas as pd

try:
    from backend.valuation import common_math as _common_math
    from backend.valuation import team_stats as _team_stats
    from backend.valuation.models import CommonDynastyRotoSettings
    from backend.valuation.year_context import CommonYearContext, CommonYearContextLike
except ImportError:
    from valuation import common_math as _common_math  # type: ignore[no-redef]
    from valuation import team_stats as _team_stats  # type: ignore[no-redef]
    from valuation.models import CommonDynastyRotoSettings  # type: ignore[no-redef]
    from valuation.year_context import CommonYearContext, CommonYearContextLike  # type: ignore[no-redef]


COMMON_REVERSED_PITCH_CATS = _common_math.COMMON_REVERSED_PITCH_CATS


def zscore(s: pd.Series) -> pd.Series:
    return _common_math._zscore(s)


def _active_common_hit_categories(lg: CommonDynastyRotoSettings) -> list[str]:
    return _common_math._active_common_hit_categories(lg)


def _active_common_pitch_categories(lg: CommonDynastyRotoSettings) -> list[str]:
    return _common_math._active_common_pitch_categories(lg)


def initial_hitter_weight(df: pd.DataFrame, categories: list[str] | None = None) -> pd.Series:
    return _common_math._initial_hitter_weight(df, categories=categories)


def initial_pitcher_weight(df: pd.DataFrame, categories: list[str] | None = None) -> pd.Series:
    return _common_math._initial_pitcher_weight(df, categories=categories)


def team_avg(h: float, ab: float) -> float:
    return _team_stats._team_avg(h, ab)


def team_obp(h: float, bb: float, hbp: float, ab: float, sf: float) -> float:
    return _team_stats._team_obp(h, bb, hbp, ab, sf)


def team_ops(h: float, bb: float, hbp: float, ab: float, sf: float, b2: float, b3: float, hr: float) -> float:
    obp = team_obp(h, bb, hbp, ab, sf)
    slg = float((h + b2 + 2.0 * b3 + 3.0 * hr) / ab) if ab > 0 else 0.0
    return float(obp + slg)


def team_era(er: float, ip: float) -> float:
    return _team_stats._team_era(er, ip)


def team_whip(h: float, bb: float, ip: float) -> float:
    return _team_stats._team_whip(h, bb, ip)


def common_hit_category_totals(totals: dict[str, float]) -> dict[str, float]:
    return _common_math.common_hit_category_totals(totals)


def common_pitch_category_totals(totals: dict[str, float]) -> dict[str, float]:
    return _common_math.common_pitch_category_totals(totals)


def common_replacement_pitcher_rates(
    all_pit_df: pd.DataFrame,
    assigned_pit_df: pd.DataFrame,
    n_rep: int,
) -> dict[str, float]:
    return _common_math.common_replacement_pitcher_rates(all_pit_df, assigned_pit_df, n_rep)


def common_apply_pitching_bounds(
    totals: dict[str, float],
    lg: CommonDynastyRotoSettings,
    rep_rates: dict[str, float] | None,
    *,
    fill_to_ip_max: bool = True,
    fill_to_ip_min: bool = False,
    enforce_ip_min: bool = True,
) -> dict[str, float]:
    return _common_math.common_apply_pitching_bounds(
        totals,
        lg,
        rep_rates,
        fill_to_ip_max=fill_to_ip_max,
        fill_to_ip_min=fill_to_ip_min,
        enforce_ip_min=enforce_ip_min,
    )


def _coerce_non_negative_float(value: object) -> float:
    return _common_math._coerce_non_negative_float(value)


def _low_volume_positive_credit_scale(
    *,
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> float:
    return _common_math._low_volume_positive_credit_scale(
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )


def _apply_low_volume_non_ratio_positive_guard(
    delta: dict[str, float],
    *,
    pit_categories: list[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> None:
    return _common_math._apply_low_volume_non_ratio_positive_guard(
        delta,
        pit_categories=pit_categories,
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )


def _apply_low_volume_ratio_guard(
    delta: dict[str, float],
    *,
    pit_categories: list[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> None:
    return _common_math._apply_low_volume_ratio_guard(
        delta,
        pit_categories=pit_categories,
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )


def _mean_adjacent_rank_gap(values: np.ndarray, *, ascending: bool) -> float:
    return _common_math._mean_adjacent_rank_gap(values, ascending=ascending)


def simulate_sgp_hit(
    assigned_hit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng: np.random.Generator,
    categories: list[str] | None = None,
) -> dict[str, float]:
    return _common_math.simulate_sgp_hit(assigned_hit, lg, rng, categories=categories)


def simulate_sgp_pit(
    assigned_pit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng: np.random.Generator,
    rep_rates: dict[str, float] | None = None,
    categories: list[str] | None = None,
) -> dict[str, float]:
    return _common_math.simulate_sgp_pit(
        assigned_pit,
        lg,
        rng,
        rep_rates=rep_rates,
        categories=categories,
    )


def compute_year_context(
    year: int,
    bat: pd.DataFrame,
    pit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng_seed: Optional[int] = None,
) -> CommonYearContext:
    return _common_math.compute_year_context(year, bat, pit, lg, rng_seed=rng_seed)


def compute_year_player_values(
    ctx: CommonYearContextLike | Mapping[str, object],
    lg: CommonDynastyRotoSettings,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return _common_math.compute_year_player_values(ctx, lg)


def compute_replacement_baselines(
    ctx: CommonYearContextLike | Mapping[str, object],
    lg: CommonDynastyRotoSettings,
    rostered_players: set[str],
    n_repl: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return _common_math.compute_replacement_baselines(
        ctx,
        lg,
        rostered_players=rostered_players,
        n_repl=n_repl,
    )


def compute_year_player_values_vs_replacement(
    ctx: CommonYearContextLike | Mapping[str, object],
    lg: CommonDynastyRotoSettings,
    repl_hit: pd.DataFrame,
    repl_pit: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return _common_math.compute_year_player_values_vs_replacement(
        ctx,
        lg,
        repl_hit=repl_hit,
        repl_pit=repl_pit,
    )


def combine_two_way(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame:
    return _common_math.combine_two_way(hit_vals, pit_vals, two_way)


__all__ = [
    "COMMON_REVERSED_PITCH_CATS",
    "CommonYearContext",
    "_active_common_hit_categories",
    "_active_common_pitch_categories",
    "_apply_low_volume_non_ratio_positive_guard",
    "_apply_low_volume_ratio_guard",
    "_coerce_non_negative_float",
    "_low_volume_positive_credit_scale",
    "_mean_adjacent_rank_gap",
    "combine_two_way",
    "common_apply_pitching_bounds",
    "common_hit_category_totals",
    "common_pitch_category_totals",
    "common_replacement_pitcher_rates",
    "compute_replacement_baselines",
    "compute_year_context",
    "compute_year_player_values",
    "compute_year_player_values_vs_replacement",
    "initial_hitter_weight",
    "initial_pitcher_weight",
    "simulate_sgp_hit",
    "simulate_sgp_pit",
    "team_avg",
    "team_era",
    "team_obp",
    "team_ops",
    "team_whip",
    "zscore",
]
