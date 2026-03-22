"""Shared dynasty-value helpers for points-mode valuation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class KeepDropResult:
    raw_total: float
    continuation_values: list[float]
    hold_values: list[float]
    keep_flags: list[bool]
    discount_factors: list[float]
    discounted_contributions: list[float]


def apply_dynasty_aggregation_adjustments(
    values: list[float],
    years: list[int],
    *,
    continuation_horizon_years: int | None = None,
    continuation_tail_start_year: int | None = None,
    continuation_tail_decay: float = 1.0,
    positive_tail_only: bool = True,
) -> list[float]:
    if len(values) != len(years):
        raise ValueError("values and years must have the same length.")
    if not values:
        return []

    start_year = int(years[0])
    horizon_limit = (
        max(int(continuation_horizon_years), 0)
        if continuation_horizon_years is not None
        else None
    )
    tail_start = (
        max(int(continuation_tail_start_year), 0)
        if continuation_tail_start_year is not None
        else None
    )
    tail_decay = float(continuation_tail_decay)
    adjusted_values: list[float] = []
    for raw_value, raw_year in zip(values, years, strict=True):
        year_offset = max(int(raw_year) - start_year, 0)
        value = float(raw_value)
        if horizon_limit is not None and year_offset >= horizon_limit:
            adjusted_values.append(0.0)
            continue
        if tail_start is not None and tail_decay < 1.0 and year_offset >= tail_start:
            tail_year_index = year_offset - tail_start + 1
            if not positive_tail_only or value > 0.0:
                value *= tail_decay ** tail_year_index
        adjusted_values.append(float(value))
    return adjusted_values


def _prospect_risk_multiplier(
    *,
    year: int,
    start_year: int,
    profile: str,
    minor_eligible: bool,
    enabled: bool,
) -> float:
    if not enabled or not minor_eligible:
        return 1.0

    year_offset = max(int(year) - int(start_year), 0)
    if profile == "pitcher":
        return float(max(0.45, 0.88 ** year_offset))
    return float(max(0.60, 0.92 ** year_offset))


def _is_near_zero_playing_time(
    player_id: str,
    year: int,
    *,
    hitter_ab_by_player_year: dict[tuple[str, int], float],
    pitcher_ip_by_player_year: dict[tuple[str, int], float],
    hitter_ab_threshold: float = 60.0,
    pitcher_ip_threshold: float = 15.0,
) -> bool:
    hit_ab = float(hitter_ab_by_player_year.get((player_id, int(year)), 0.0))
    pit_ip = float(pitcher_ip_by_player_year.get((player_id, int(year)), 0.0))
    return hit_ab <= float(hitter_ab_threshold) and pit_ip <= float(pitcher_ip_threshold)


def _apply_negative_value_stash_rules(
    value: float,
    *,
    can_minor_stash: bool,
    can_ir_stash: bool,
    ir_negative_penalty: float,
    can_bench_stash: bool,
    bench_negative_penalty: float,
) -> float:
    if value >= 0.0:
        return float(value)
    if can_minor_stash:
        return 0.0
    if can_ir_stash:
        return float(value) * float(min(max(ir_negative_penalty, 0.0), 1.0))
    if can_bench_stash:
        return float(value) * float(min(max(bench_negative_penalty, 0.0), 1.0))
    return float(value)


def _negative_fallback_value(
    *,
    best_value: float | None,
    assigned_slot: str | None,
    assigned_value: float,
) -> float:
    if assigned_slot is not None:
        return float(assigned_value)
    if best_value is None:
        return 0.0
    return min(float(best_value), 0.0)


def dynasty_keep_or_drop_values(
    values: list[float],
    years: list[int],
    *,
    discount: float,
    continuation_horizon_years: int | None = None,
    continuation_tail_start_year: int | None = None,
    continuation_tail_decay: float = 1.0,
    positive_tail_only: bool = True,
) -> KeepDropResult:
    if len(values) != len(years):
        raise ValueError("values and years must have the same length.")
    if not values:
        return KeepDropResult(
            raw_total=0.0,
            continuation_values=[],
            hold_values=[],
            keep_flags=[],
            discount_factors=[],
            discounted_contributions=[],
        )

    adjusted_values = apply_dynasty_aggregation_adjustments(
        values,
        years,
        continuation_horizon_years=continuation_horizon_years,
        continuation_tail_start_year=continuation_tail_start_year,
        continuation_tail_decay=continuation_tail_decay,
        positive_tail_only=positive_tail_only,
    )
    annual_discount = float(discount)
    count = len(adjusted_values)
    continuation_values = [0.0] * count
    hold_values = [0.0] * count
    keep_flags = [False] * count

    for idx in range(count - 1, -1, -1):
        future = 0.0
        if idx < count - 1:
            gap = max(1, int(years[idx + 1]) - int(years[idx]))
            future = (annual_discount ** gap) * continuation_values[idx + 1]
        candidate = float(adjusted_values[idx]) + future
        hold_values[idx] = float(candidate)
        if candidate > 0:
            continuation_values[idx] = float(candidate)
            keep_flags[idx] = True

    discount_factors = [1.0] * count
    for idx in range(1, count):
        gap = max(1, int(years[idx]) - int(years[idx - 1]))
        discount_factors[idx] = discount_factors[idx - 1] * (annual_discount ** gap)

    discounted_contributions = [0.0] * count
    active = bool(keep_flags[0])
    if active:
        discounted_contributions[0] = float(adjusted_values[0]) * discount_factors[0]
    for idx in range(1, count):
        if not active:
            break
        if keep_flags[idx]:
            discounted_contributions[idx] = float(adjusted_values[idx]) * discount_factors[idx]
        else:
            active = False

    raw_total = float(continuation_values[0]) if keep_flags[0] else 0.0
    return KeepDropResult(
        raw_total=raw_total,
        continuation_values=continuation_values,
        hold_values=hold_values,
        keep_flags=keep_flags,
        discount_factors=discount_factors,
        discounted_contributions=discounted_contributions,
    )
