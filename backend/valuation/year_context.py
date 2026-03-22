"""Typed year-context boundary for common valuation workflows."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass

import pandas as pd

_YEAR_CONTEXT_FIELDS: tuple[str, ...] = (
    "year",
    "bat_y",
    "pit_y",
    "assigned_hit",
    "assigned_pit",
    "baseline_hit",
    "baseline_pit",
    "base_hit_tot",
    "base_avg",
    "base_pit_tot",
    "base_pit_bounded",
    "rep_rates",
    "sgp_hit",
    "sgp_pit",
    "hit_categories",
    "pit_categories",
    "hitter_usage_diagnostics",
    "pitcher_usage_diagnostics",
)


@dataclass(slots=True)
class CommonYearContext(Mapping[str, object]):
    year: int
    bat_y: pd.DataFrame
    pit_y: pd.DataFrame
    assigned_hit: pd.DataFrame
    assigned_pit: pd.DataFrame
    baseline_hit: pd.DataFrame
    baseline_pit: pd.DataFrame
    base_hit_tot: pd.Series
    base_avg: float
    base_pit_tot: pd.Series
    base_pit_bounded: dict[str, float]
    rep_rates: dict[str, float] | None
    sgp_hit: dict[str, float]
    sgp_pit: dict[str, float]
    hit_categories: list[str]
    pit_categories: list[str]
    hitter_usage_diagnostics: dict[str, float | int | None]
    pitcher_usage_diagnostics: dict[str, float | int | None]

    def __getitem__(self, key: str) -> object:
        if key not in _YEAR_CONTEXT_FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self) -> Iterator[str]:
        return iter(_YEAR_CONTEXT_FIELDS)

    def __len__(self) -> int:
        return len(_YEAR_CONTEXT_FIELDS)

    def as_dict(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in _YEAR_CONTEXT_FIELDS}


CommonYearContextLike = CommonYearContext | Mapping[str, object]


def context_value(ctx: CommonYearContextLike, key: str) -> object:
    if isinstance(ctx, CommonYearContext):
        return getattr(ctx, key)
    return ctx[key]


def context_optional_value(ctx: CommonYearContextLike, key: str, default: object | None = None) -> object:
    if isinstance(ctx, CommonYearContext):
        return getattr(ctx, key)
    return ctx.get(key, default)
