"""Shared dynasty value adjustment helpers for common valuation orchestration."""

from __future__ import annotations

import math
import re
from typing import Dict, Set

import pandas as pd

try:
    from backend.dynasty_roto_values import (
        CommonDynastyRotoSettings,
        _apply_negative_value_stash_rules,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from dynasty_roto_values import (  # type: ignore
        CommonDynastyRotoSettings,
        _apply_negative_value_stash_rules,
    )


_PITCH_POSITION_TOKENS = {"P", "SP", "RP"}
_POSITION_TOKEN_RE = re.compile(r"[,\s/;+|]+")


def _position_profile(pos_value: object) -> str:
    text = str(pos_value or "").strip().upper()
    if not text:
        return "hitter"
    tokens = {token for token in _POSITION_TOKEN_RE.split(text) if token}
    has_pitch = any(token in _PITCH_POSITION_TOKENS for token in tokens)
    has_hit = any(token not in _PITCH_POSITION_TOKENS for token in tokens)
    if has_pitch and not has_hit:
        return "pitcher"
    if has_pitch and has_hit:
        return "two_way"
    if tokens == {"C"}:
        return "catcher"
    return "hitter"


def _piecewise_age_factor(age: float, *, profile: str) -> float:
    """Return a 0-to-1 multiplier reflecting age-related decline risk."""
    if profile == "pitcher":
        if age <= 28.0:
            return 1.0
        if age <= 34.0:
            return 1.0 + (0.84 - 1.0) * ((age - 28.0) / 6.0)
        if age <= 38.0:
            return 0.84 + (0.70 - 0.84) * ((age - 34.0) / 4.0)
        return 0.70

    if profile == "catcher":
        if age <= 27.0:
            return 1.0
        if age <= 33.0:
            return 1.0 + (0.82 - 1.0) * ((age - 27.0) / 6.0)
        if age <= 37.0:
            return 0.82 + (0.65 - 0.82) * ((age - 33.0) / 4.0)
        return 0.65

    if age <= 29.0:
        return 1.0
    if age <= 35.0:
        return 1.0 + (0.88 - 1.0) * ((age - 29.0) / 6.0)
    if age <= 39.0:
        return 0.88 + (0.75 - 0.88) * ((age - 35.0) / 4.0)
    return 0.75


def _year_risk_multiplier(
    *,
    age_start: float | None,
    year: int,
    start_year: int,
    profile: str,
    enabled: bool,
) -> float:
    """Scale a player's yearly value by projected age-related decline."""
    if not enabled:
        return 1.0
    if age_start is None or not math.isfinite(age_start):
        return 1.0
    year_offset = max(int(year) - int(start_year), 0)
    age = float(age_start) + float(year_offset)
    factor = _piecewise_age_factor(age, profile=profile)
    if age >= 31.0 and year_offset > 0:
        factor *= float(0.98 ** year_offset)
    return float(max(min(factor, 1.0), 0.0))


def _prospect_risk_multiplier(
    *,
    year: int,
    start_year: int,
    profile: str,
    minor_eligible: bool,
    enabled: bool,
) -> float:
    """Apply an extra uncertainty discount to minor-eligible players."""
    if not enabled or not minor_eligible:
        return 1.0

    year_offset = max(int(year) - int(start_year), 0)
    if profile == "pitcher":
        return float(max(0.45, 0.88 ** year_offset))
    return float(max(0.60, 0.92 ** year_offset))


def _is_near_zero_playing_time(
    player: str,
    year: int,
    *,
    hitter_ab_by_player_year: Dict[tuple[str, int], float],
    pitcher_ip_by_player_year: Dict[tuple[str, int], float],
    hitter_ab_threshold: float = 60.0,
    pitcher_ip_threshold: float = 15.0,
) -> bool:
    hit_ab = float(hitter_ab_by_player_year.get((player, int(year)), 0.0))
    pit_ip = float(pitcher_ip_by_player_year.get((player, int(year)), 0.0))
    return hit_ab <= float(hitter_ab_threshold) and pit_ip <= float(pitcher_ip_threshold)


def _coerce_projected_volume(value: object) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return 0.0
    return float(parsed)


def _adjust_dynasty_year_value(
    value: float,
    *,
    player: str,
    year: int,
    start_year: int,
    age_start: float | None,
    profile: str,
    lg: CommonDynastyRotoSettings,
    minor_eligibility_by_year: Dict[tuple[str, int], bool],
    minor_stash_players: Set[str],
    bench_stash_players: Set[str],
    ir_stash_players: Set[str],
    hitter_ab_by_player_year: Dict[tuple[str, int], float],
    pitcher_ip_by_player_year: Dict[tuple[str, int], float],
) -> float:
    adjusted = float(value)
    adjusted *= _year_risk_multiplier(
        age_start=age_start,
        year=int(year),
        start_year=int(start_year),
        profile=profile,
        enabled=bool(getattr(lg, "enable_age_risk_adjustment", False)),
    )

    minor_eligible = bool(minor_eligibility_by_year.get((player, int(year)), False))
    adjusted *= _prospect_risk_multiplier(
        year=int(year),
        start_year=int(start_year),
        profile=profile,
        minor_eligible=minor_eligible,
        enabled=bool(getattr(lg, "enable_prospect_risk_adjustment", False)),
    )

    return _apply_negative_value_stash_rules(
        adjusted,
        can_minor_stash=player in minor_stash_players and minor_eligible,
        can_ir_stash=bool(getattr(lg, "enable_ir_stash_relief", False))
        and player in ir_stash_players
        and _is_near_zero_playing_time(
            player,
            int(year),
            hitter_ab_by_player_year=hitter_ab_by_player_year,
            pitcher_ip_by_player_year=pitcher_ip_by_player_year,
        ),
        ir_negative_penalty=float(getattr(lg, "ir_negative_penalty", 1.0)),
        can_bench_stash=bool(getattr(lg, "enable_bench_stash_relief", False)) and player in bench_stash_players,
        bench_negative_penalty=float(getattr(lg, "bench_negative_penalty", 1.0)),
    )
