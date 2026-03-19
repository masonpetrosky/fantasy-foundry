"""Shared valuation data models and stat/category constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

HIT_COMPONENT_COLS = ["AB", "H", "R", "HR", "RBI", "SB", "BB", "HBP", "SF", "2B", "3B"]
PIT_COMPONENT_COLS = ["IP", "W", "QS", "QA3", "K", "SV", "SVH", "ER", "H", "BB"]

HIT_CATS = ["R", "RBI", "HR", "SB", "AVG", "OBP", "SLG", "OPS", "H", "BB", "2B", "TB"]
PIT_CATS = ["W", "K", "SV", "ERA", "WHIP", "QS", "QA3", "SVH"]

@dataclass
class CommonDynastyRotoSettings:
    n_teams: int = 12

    # Typical roto hitter lineup (NFBC-ish)
    hitter_slots: Dict[str, int] = field(
        default_factory=lambda: {
            "C": 1,
            "1B": 1,
            "2B": 1,
            "3B": 1,
            "SS": 1,
            "CI": 1,
            "MI": 1,
            "OF": 5,
            "UT": 1,
        }
    )

    # Default common setup: nine generic pitcher slots.
    pitcher_slots: Dict[str, int] = field(
        default_factory=lambda: {
            "P": 9,
            "SP": 0,
            "RP": 0,
        }
    )

    # Typical dynasty roster extras (you can tune these)
    bench_slots: int = 6
    minor_slots: int = 0
    ir_slots: int = 0

    # Many "standard" roto leagues do NOT enforce an IP cap.
    # Some do enforce an IP minimum for ERA/WHIP qualification; default off.
    ip_min: float = 0.0
    ip_max: Optional[float] = None

    # Monte Carlo settings for SGP denominators
    sims_for_sgp: int = 200
    replacement_pitchers_n: int = 100

    # Dynasty parameters
    discount: float = 0.94
    horizon_years: int = 10
    # If True, compute replacement baselines from start_year once and reuse
    # for all future valuation years. This avoids late-horizon value inflation
    # caused by an increasingly thin projected replacement pool.
    freeze_replacement_baselines: bool = True
    # Optional blend between frozen and in-year replacement baselines.
    enable_replacement_blend: bool = False
    replacement_blend_alpha: float = 0.70

    # Two-way players: "max" = choose best of hitter/pitcher per year
    # (Most leagues effectively work like this for valuation purposes)
    two_way: str = "max"

    # Active roto categories (common mode defaults to standard 5x5).
    hitter_categories: tuple[str, ...] = tuple(HIT_CATS)
    pitcher_categories: tuple[str, ...] = tuple(PIT_CATS)
    # SGP denominator estimator controls.
    sgp_denominator_mode: str = "classic"
    sgp_winsor_low_pct: float = 0.10
    sgp_winsor_high_pct: float = 0.90
    sgp_epsilon_counting: float = 0.15
    sgp_epsilon_ratio: float = 0.0015
    # Optional predictive modifiers.
    enable_playing_time_reliability: bool = False
    enable_age_risk_adjustment: bool = False
    enable_prospect_risk_adjustment: bool = False
    enable_bench_stash_relief: bool = False
    bench_negative_penalty: float = 0.55
    enable_ir_stash_relief: bool = False
    ir_negative_penalty: float = 0.20

    # Minor eligibility (best-effort inference, since projections file usually
    # lacks career AB/IP):
    minor_ab_max: int = 130
    minor_ip_max: int = 50
    minor_age_max_hit: int = 25
    minor_age_max_pit: int = 26


__all__ = [
    "CommonDynastyRotoSettings",
    "HIT_COMPONENT_COLS",
    "PIT_COMPONENT_COLS",
    "HIT_CATS",
    "PIT_CATS",
]
