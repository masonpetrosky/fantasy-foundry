"""Legacy minor-eligibility helper exports routed through extracted modules."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd

try:
    from backend.valuation import minor_eligibility as _minor_elig
    from backend.valuation.models import CommonDynastyRotoSettings
except ImportError:
    from valuation import minor_eligibility as _minor_elig  # type: ignore[no-redef]
    from valuation.models import CommonDynastyRotoSettings  # type: ignore[no-redef]


BENCH_STASH_MIN_PENALTY = 0.10
BENCH_STASH_MAX_PENALTY = 0.85
BENCH_STASH_PENALTY_GAMMA = 1.35


def _infer_minor_eligibility_by_year(
    bat_df: pd.DataFrame,
    pit_df: pd.DataFrame,
    *,
    years: list[int] | None,
    hitter_usage_max: int,
    pitcher_usage_max: int,
    hitter_age_max: int,
    pitcher_age_max: int,
) -> pd.DataFrame:
    return _minor_elig._infer_minor_eligibility_by_year(
        bat_df,
        pit_df,
        years=years,
        hitter_usage_max=hitter_usage_max,
        pitcher_usage_max=pitcher_usage_max,
        hitter_age_max=hitter_age_max,
        pitcher_age_max=pitcher_age_max,
    )


def infer_minor_eligible(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    start_year: int,
) -> pd.DataFrame:
    return _minor_elig.infer_minor_eligible(bat, pit, lg, start_year)


def _non_vacant_player_names(df: pd.DataFrame | None) -> set[str]:
    return _minor_elig._non_vacant_player_names(df)


def _players_with_playing_time(bat_df: pd.DataFrame, pit_df: pd.DataFrame, years: list[int]) -> set[str]:
    return _minor_elig._players_with_playing_time(bat_df, pit_df, years)


def _select_mlb_roster_with_active_floor(
    stash_sorted: pd.DataFrame,
    *,
    excluded_players: set[str],
    total_mlb_slots: int,
    active_floor_names: set[str],
    mlb_playing_time_players: set[str] | None = None,
) -> pd.DataFrame:
    return _minor_elig._select_mlb_roster_with_active_floor(
        stash_sorted,
        excluded_players=excluded_players,
        total_mlb_slots=total_mlb_slots,
        active_floor_names=active_floor_names,
        mlb_playing_time_players=mlb_playing_time_players,
    )


def _estimate_bench_negative_penalty(start_ctx: Mapping[str, object], lg: object) -> float:
    return _minor_elig._estimate_bench_negative_penalty(start_ctx, lg)


def _bench_stash_round_penalty(
    round_number: int,
    *,
    bench_slots: int,
    min_penalty: float = BENCH_STASH_MIN_PENALTY,
    max_penalty: float = BENCH_STASH_MAX_PENALTY,
    gamma: float = BENCH_STASH_PENALTY_GAMMA,
) -> float:
    return _minor_elig._bench_stash_round_penalty(
        round_number,
        bench_slots=bench_slots,
        min_penalty=min_penalty,
        max_penalty=max_penalty,
        gamma=gamma,
    )


def _build_bench_stash_penalty_map(
    stash_sorted: pd.DataFrame,
    *,
    bench_stash_players: set[str],
    n_teams: int,
    bench_slots: int,
) -> dict[str, float]:
    return _minor_elig._build_bench_stash_penalty_map(
        stash_sorted,
        bench_stash_players=bench_stash_players,
        n_teams=n_teams,
        bench_slots=bench_slots,
    )


def _apply_negative_value_stash_rules(
    value: float,
    *,
    can_minor_stash: bool,
    can_ir_stash: bool = False,
    ir_negative_penalty: float = 1.0,
    can_bench_stash: bool,
    bench_negative_penalty: float,
) -> float:
    return _minor_elig._apply_negative_value_stash_rules(
        value,
        can_minor_stash=can_minor_stash,
        can_ir_stash=can_ir_stash,
        ir_negative_penalty=ir_negative_penalty,
        can_bench_stash=can_bench_stash,
        bench_negative_penalty=bench_negative_penalty,
    )


def _fillna_bool(series: pd.Series, default: bool = False) -> pd.Series:
    return _minor_elig._fillna_bool(series, default=default)


def _normalize_minor_eligibility(series: pd.Series) -> pd.Series:
    return _minor_elig._normalize_minor_eligibility(series)


def minor_eligibility_by_year_from_input(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
) -> pd.DataFrame | None:
    return _minor_elig.minor_eligibility_by_year_from_input(bat, pit)


def minor_eligibility_from_input(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
    start_year: int,
) -> pd.DataFrame | None:
    return _minor_elig.minor_eligibility_from_input(bat, pit, start_year)


def _resolve_minor_eligibility_by_year(
    bat_df: pd.DataFrame,
    pit_df: pd.DataFrame,
    *,
    years: list[int],
    hitter_usage_max: int,
    pitcher_usage_max: int,
    hitter_age_max: int,
    pitcher_age_max: int,
) -> pd.DataFrame:
    return _minor_elig._resolve_minor_eligibility_by_year(
        bat_df,
        pit_df,
        years=years,
        hitter_usage_max=hitter_usage_max,
        pitcher_usage_max=pitcher_usage_max,
        hitter_age_max=hitter_age_max,
        pitcher_age_max=pitcher_age_max,
    )


__all__ = [
    "BENCH_STASH_MAX_PENALTY",
    "BENCH_STASH_MIN_PENALTY",
    "BENCH_STASH_PENALTY_GAMMA",
    "_apply_negative_value_stash_rules",
    "_bench_stash_round_penalty",
    "_build_bench_stash_penalty_map",
    "_estimate_bench_negative_penalty",
    "_fillna_bool",
    "_infer_minor_eligibility_by_year",
    "_non_vacant_player_names",
    "_normalize_minor_eligibility",
    "_players_with_playing_time",
    "_resolve_minor_eligibility_by_year",
    "_select_mlb_roster_with_active_floor",
    "infer_minor_eligible",
    "minor_eligibility_by_year_from_input",
    "minor_eligibility_from_input",
]
