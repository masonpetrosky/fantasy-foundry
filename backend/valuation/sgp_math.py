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

COMMON_REVERSED_PITCH_CATS: Set[str] = {"ERA", "WHIP"}
COMMON_RATE_HIT_CATS: Set[str] = {"AVG", "OBP", "SLG", "OPS"}
_HIT_COMPONENT_IDX = {col: idx for idx, col in enumerate(HIT_COMPONENT_COLS)}
_PIT_COMPONENT_IDX = {col: idx for idx, col in enumerate(PIT_COMPONENT_COLS)}


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


def _slot_component_arrays(
    assigned: pd.DataFrame,
    *,
    slot_counts: dict[str, int],
    component_cols: list[str],
) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {}
    for slot, count in slot_counts.items():
        if count <= 0:
            arrays[slot] = np.empty((0, len(component_cols)), dtype=float)
            continue
        slot_rows = assigned.loc[assigned["AssignedSlot"] == slot, component_cols]
        arrays[slot] = slot_rows.to_numpy(dtype=float, copy=True)
    return arrays


def _hit_category_matrix(totals: np.ndarray, categories: list[str]) -> np.ndarray:
    if not categories:
        return np.empty((len(totals), 0), dtype=float)

    ab = totals[:, _HIT_COMPONENT_IDX["AB"]]
    h = totals[:, _HIT_COMPONENT_IDX["H"]]
    hr = totals[:, _HIT_COMPONENT_IDX["HR"]]
    bb = totals[:, _HIT_COMPONENT_IDX["BB"]]
    hbp = totals[:, _HIT_COMPONENT_IDX["HBP"]]
    sf = totals[:, _HIT_COMPONENT_IDX["SF"]]
    b2 = totals[:, _HIT_COMPONENT_IDX["2B"]]
    b3 = totals[:, _HIT_COMPONENT_IDX["3B"]]
    tb = h + b2 + (2.0 * b3) + (3.0 * hr)
    avg = np.divide(h, ab, out=np.zeros_like(h), where=ab > 0.0)
    obp_den = ab + bb + hbp + sf
    obp = np.divide(h + bb + hbp, obp_den, out=np.zeros_like(h), where=obp_den > 0.0)
    slg = np.divide(tb, ab, out=np.zeros_like(tb), where=ab > 0.0)

    values = {
        "R": totals[:, _HIT_COMPONENT_IDX["R"]],
        "RBI": totals[:, _HIT_COMPONENT_IDX["RBI"]],
        "HR": hr,
        "SB": totals[:, _HIT_COMPONENT_IDX["SB"]],
        "AVG": avg,
        "OBP": obp,
        "SLG": slg,
        "OPS": obp + slg,
        "H": h,
        "BB": bb,
        "2B": b2,
        "TB": tb,
    }
    return np.column_stack([values[cat] for cat in categories])


def _bounded_pitch_category_matrix(
    totals: np.ndarray,
    *,
    lg: CommonDynastyRotoSettings,
    rep_rates: Optional[Dict[str, float]],
    categories: list[str],
) -> np.ndarray:
    if not categories:
        return np.empty((len(totals), 0), dtype=float)

    bounded = np.array(totals, dtype=float, copy=True)
    ip_idx = _PIT_COMPONENT_IDX["IP"]
    ip = bounded[:, ip_idx]

    if lg.ip_max is not None:
        ip_cap = float(lg.ip_max)
        over_cap = (ip > ip_cap) & (ip > 0.0)
        if np.any(over_cap):
            factors = np.ones_like(ip)
            factors[over_cap] = ip_cap / ip[over_cap]
            bounded[over_cap] *= factors[over_cap, None]
            ip = bounded[:, ip_idx]

        if rep_rates is not None:
            under_cap = ip < ip_cap
            if np.any(under_cap):
                add = ip_cap - ip[under_cap]
                bounded[under_cap, ip_idx] = ip_cap
                for stat_col in ("W", "QS", "QA3", "K", "SV", "SVH", "ER", "H", "BB"):
                    bounded[under_cap, _PIT_COMPONENT_IDX[stat_col]] += add * float(rep_rates.get(stat_col, 0.0))
                ip = bounded[:, ip_idx]

    era = np.full(len(bounded), np.nan, dtype=float)
    whip = np.full(len(bounded), np.nan, dtype=float)
    valid_ip = ip > 0.0
    if np.any(valid_ip):
        era[valid_ip] = 9.0 * bounded[valid_ip, _PIT_COMPONENT_IDX["ER"]] / ip[valid_ip]
        whip[valid_ip] = (
            bounded[valid_ip, _PIT_COMPONENT_IDX["H"]] + bounded[valid_ip, _PIT_COMPONENT_IDX["BB"]]
        ) / ip[valid_ip]

    if lg.ip_min and lg.ip_min > 0:
        below_min = ip < float(lg.ip_min)
        if np.any(below_min):
            era[below_min] = 99.0
            whip[below_min] = 5.0

    values = {
        "W": bounded[:, _PIT_COMPONENT_IDX["W"]],
        "K": bounded[:, _PIT_COMPONENT_IDX["K"]],
        "SV": bounded[:, _PIT_COMPONENT_IDX["SV"]],
        "ERA": era,
        "WHIP": whip,
        "QS": bounded[:, _PIT_COMPONENT_IDX["QS"]],
        "QA3": bounded[:, _PIT_COMPONENT_IDX["QA3"]],
        "SVH": bounded[:, _PIT_COMPONENT_IDX["SVH"]],
    }
    return np.column_stack([values[cat] for cat in categories])


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
    slot_arrays = _slot_component_arrays(
        assigned_hit,
        slot_counts=per_team,
        component_cols=HIT_COMPONENT_COLS,
    )
    totals = np.zeros((lg.n_teams, len(HIT_COMPONENT_COLS)), dtype=float)

    for _ in range(lg.sims_for_sgp):
        totals.fill(0.0)

        for slot, cnt in per_team.items():
            if cnt <= 0:
                continue
            slot_array = slot_arrays[slot]
            idx = rng.permutation(len(slot_array))
            sums = slot_array[idx].reshape(lg.n_teams, cnt, len(HIT_COMPONENT_COLS)).sum(axis=1)
            totals += sums

        values = _hit_category_matrix(totals, active_categories)
        for idx, category in enumerate(active_categories):
            diffs[category].append(
                _mean_adjacent_rank_gap(
                    values[:, idx],
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
    slot_arrays = _slot_component_arrays(
        assigned_pit,
        slot_counts=per_team,
        component_cols=PIT_COMPONENT_COLS,
    )
    totals = np.zeros((lg.n_teams, len(PIT_COMPONENT_COLS)), dtype=float)

    for _ in range(lg.sims_for_sgp):
        totals.fill(0.0)

        for slot, cnt in per_team.items():
            if cnt <= 0:
                continue
            slot_array = slot_arrays[slot]
            idx = rng.permutation(len(slot_array))
            sums = slot_array[idx].reshape(lg.n_teams, cnt, len(PIT_COMPONENT_COLS)).sum(axis=1)
            totals += sums

        values = _bounded_pitch_category_matrix(
            totals,
            lg=lg,
            rep_rates=rep_rates,
            categories=active_categories,
        )
        for idx, category in enumerate(active_categories):
            diffs[category].append(
                _mean_adjacent_rank_gap(
                    values[:, idx],
                    ascending=(category in COMMON_REVERSED_PITCH_CATS),
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
