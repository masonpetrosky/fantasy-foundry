"""SGP (Standings Gain Points) simulation and denominator estimation."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd

try:
    from backend.valuation.models import (
        HIT_CATS,
        HIT_COMPONENT_COLS,
        PIT_CATS,
        PIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )
except ImportError:
    from valuation.models import (  # type: ignore[no-redef]
        HIT_CATS,
        HIT_COMPONENT_COLS,
        PIT_CATS,
        PIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )

try:
    from backend.valuation.team_stats import (
        common_apply_pitching_bounds,
        common_hit_category_totals,
        common_pitch_category_totals,
    )
except ImportError:
    from valuation.team_stats import (  # type: ignore[no-redef]
        common_apply_pitching_bounds,
        common_hit_category_totals,
        common_pitch_category_totals,
    )


COMMON_REVERSED_PITCH_CATS: Set[str] = {"ERA", "WHIP"}
COMMON_RATE_HIT_CATS: Set[str] = {"AVG", "OBP", "SLG", "OPS"}


def _mean_adjacent_rank_gap(
    values: np.ndarray,
    *,
    ascending: bool,
    robust: bool = False,
    winsor_low_pct: float = 0.10,
    winsor_high_pct: float = 0.90,
) -> float:
    """Mean absolute adjacent difference after rank-order sorting."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return 0.0

    sorted_arr = np.sort(arr)
    if not ascending:
        sorted_arr = sorted_arr[::-1]
    diffs = np.abs(np.diff(sorted_arr))
    if diffs.size == 0:
        return 0.0
    if robust:
        low = float(np.clip(winsor_low_pct, 0.0, 1.0))
        high = float(np.clip(winsor_high_pct, 0.0, 1.0))
        if high < low:
            low, high = high, low
        lo_val = float(np.quantile(diffs, low))
        hi_val = float(np.quantile(diffs, high))
        diffs = np.clip(diffs, lo_val, hi_val)
    return float(np.mean(diffs))


def _sgp_estimator_options(lg: CommonDynastyRotoSettings) -> tuple[bool, float, float]:
    mode = str(getattr(lg, "sgp_denominator_mode", "classic") or "classic").strip().lower()
    robust = mode == "robust"
    low = float(getattr(lg, "sgp_winsor_low_pct", 0.10))
    high = float(getattr(lg, "sgp_winsor_high_pct", 0.90))
    return robust, low, high


def _sgp_denominator_floor(*, lg: CommonDynastyRotoSettings, category: str) -> float:
    mode = str(getattr(lg, "sgp_denominator_mode", "classic") or "classic").strip().lower()
    if mode != "robust":
        return 0.0
    if category in COMMON_REVERSED_PITCH_CATS or category in COMMON_RATE_HIT_CATS:
        return float(max(getattr(lg, "sgp_epsilon_ratio", 0.0015), 0.0))
    return float(max(getattr(lg, "sgp_epsilon_counting", 0.15), 0.0))


def simulate_sgp_hit(
    assigned_hit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng: np.random.Generator,
    categories: Optional[List[str]] = None,
) -> Dict[str, float]:
    """Estimate SGP denominators for hitting categories via simulation."""
    per_team = lg.hitter_slots
    active_categories = [c for c in HIT_CATS if c in set(categories or HIT_CATS)]
    if not active_categories:
        return {}
    robust, winsor_low, winsor_high = _sgp_estimator_options(lg)
    diffs: Dict[str, List[float]] = {c: [] for c in active_categories}

    groups = {slot: assigned_hit[assigned_hit["AssignedSlot"] == slot] for slot in per_team.keys()}
    component_idx = {col: HIT_COMPONENT_COLS.index(col) for col in HIT_COMPONENT_COLS}

    for _ in range(lg.sims_for_sgp):
        totals = {col: np.zeros(lg.n_teams) for col in HIT_COMPONENT_COLS}

        for slot, cnt in per_team.items():
            df_slot = groups[slot]
            idx = rng.permutation(len(df_slot))
            arr = df_slot.iloc[idx][HIT_COMPONENT_COLS].to_numpy(dtype=float)
            arr = arr.reshape(lg.n_teams, cnt, len(HIT_COMPONENT_COLS))
            sums = arr.sum(axis=1)

            for col, idx_col in component_idx.items():
                totals[col] += sums[:, idx_col]

        vals: Dict[str, List[float]] = {c: [] for c in active_categories}
        for t in range(lg.n_teams):
            team_totals = {col: float(totals[col][t]) for col in HIT_COMPONENT_COLS}
            team_cats = common_hit_category_totals(team_totals)
            for cat in active_categories:
                vals[cat].append(float(team_cats.get(cat, 0.0)))

        for c in active_categories:
            x = np.array(vals[c], dtype=float)
            diffs[c].append(
                _mean_adjacent_rank_gap(
                    x,
                    ascending=False,
                    robust=robust,
                    winsor_low_pct=winsor_low,
                    winsor_high_pct=winsor_high,
                )
            )

    out: Dict[str, float] = {}
    for category in active_categories:
        value = float(np.mean(diffs[category])) if diffs[category] else 0.0
        floor = _sgp_denominator_floor(lg=lg, category=category)
        out[category] = max(value, floor) if floor > 0.0 else value
    return out


def simulate_sgp_pit(
    assigned_pit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng: np.random.Generator,
    rep_rates: Optional[Dict[str, float]] = None,
    categories: Optional[List[str]] = None,
) -> Dict[str, float]:
    active_categories = [c for c in PIT_CATS if c in set(categories or PIT_CATS)]
    if not active_categories:
        return {}
    robust, winsor_low, winsor_high = _sgp_estimator_options(lg)
    diffs: Dict[str, List[float]] = {c: [] for c in active_categories}
    per_team = lg.pitcher_slots
    groups = {slot: assigned_pit[assigned_pit["AssignedSlot"] == slot] for slot in per_team.keys()}
    component_idx = {col: PIT_COMPONENT_COLS.index(col) for col in PIT_COMPONENT_COLS}

    for _ in range(lg.sims_for_sgp):
        totals = {col: np.zeros(lg.n_teams) for col in PIT_COMPONENT_COLS}

        for slot, cnt in per_team.items():
            df_slot = groups[slot]
            idx = rng.permutation(len(df_slot))
            arr = df_slot.iloc[idx][PIT_COMPONENT_COLS].to_numpy(dtype=float)
            arr = arr.reshape(lg.n_teams, cnt, len(PIT_COMPONENT_COLS))
            sums = arr.sum(axis=1)

            for col, idx_col in component_idx.items():
                totals[col] += sums[:, idx_col]

        vals: Dict[str, List[float]] = {c: [] for c in active_categories}
        for t in range(lg.n_teams):
            bounded = common_apply_pitching_bounds(
                {col: float(totals[col][t]) for col in PIT_COMPONENT_COLS},
                lg,
                rep_rates,
            )
            team_cats = common_pitch_category_totals(bounded)
            for cat in active_categories:
                vals[cat].append(float(team_cats.get(cat, 0.0)))

        for c in active_categories:
            x = np.array(vals[c], dtype=float)
            diffs[c].append(
                _mean_adjacent_rank_gap(
                    x,
                    ascending=(c in COMMON_REVERSED_PITCH_CATS),
                    robust=robust,
                    winsor_low_pct=winsor_low,
                    winsor_high_pct=winsor_high,
                )
            )

    out: Dict[str, float] = {}
    for category in active_categories:
        value = float(np.mean(diffs[category])) if diffs[category] else 0.0
        floor = _sgp_denominator_floor(lg=lg, category=category)
        out[category] = max(value, floor) if floor > 0.0 else value
    return out
