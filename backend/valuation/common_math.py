"""Common-mode valuation math helpers extracted from dynasty_roto_values."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

try:
    from backend.valuation.assignment import (
        assign_players_to_slots_with_vacancy_fill,
        build_team_slot_template,
        expand_slot_counts,
    )
    from backend.valuation.models import (
        HIT_CATS,
        HIT_COMPONENT_COLS,
        PIT_CATS,
        PIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )
    from backend.valuation.positions import (
        eligible_hit_slots,
        eligible_pit_slots,
        parse_hit_positions,
        parse_pit_positions,
    )
except ImportError:
    from valuation.assignment import (
        assign_players_to_slots_with_vacancy_fill,
        build_team_slot_template,
        expand_slot_counts,
    )
    from valuation.models import (
        HIT_CATS,
        HIT_COMPONENT_COLS,
        PIT_CATS,
        PIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )
    from valuation.positions import (
        eligible_hit_slots,
        eligible_pit_slots,
        parse_hit_positions,
        parse_pit_positions,
    )


COMMON_REVERSED_PITCH_CATS: Set[str] = {"ERA", "WHIP"}
COMMON_RATE_HIT_CATS: Set[str] = {"AVG", "OBP", "SLG", "OPS"}


def _zscore(s: pd.Series) -> pd.Series:
    x = s.astype(float)
    mu = float(x.mean())
    sd = float(x.std(ddof=0))
    if sd == 0.0 or np.isnan(sd):
        return x * 0.0
    return (x - mu) / sd


def _active_common_hit_categories(lg: CommonDynastyRotoSettings) -> List[str]:
    configured = getattr(lg, "hitter_categories", None)
    if not configured:
        return list(HIT_CATS)
    wanted = {str(cat).strip().upper() for cat in configured if str(cat).strip()}
    selected = [cat for cat in HIT_CATS if cat.upper() in wanted]
    return selected or list(HIT_CATS)


def _active_common_pitch_categories(lg: CommonDynastyRotoSettings) -> List[str]:
    configured = getattr(lg, "pitcher_categories", None)
    if not configured:
        return list(PIT_CATS)
    wanted = {str(cat).strip().upper() for cat in configured if str(cat).strip()}
    selected = [cat for cat in PIT_CATS if cat.upper() in wanted]
    return selected or list(PIT_CATS)


def _initial_hitter_weight(df: pd.DataFrame, categories: Optional[List[str]] = None) -> pd.Series:
    """Rough first-pass weight for baseline starter-pool construction."""
    df = df.copy()
    selected = {str(cat).strip().upper() for cat in (categories or list(HIT_CATS))}
    components: List[pd.Series] = []

    h = df["H"].astype(float)
    ab = df["AB"].astype(float)
    b2 = df["2B"].astype(float)
    b3 = df["3B"].astype(float)
    hr = df["HR"].astype(float)
    bb = df["BB"].astype(float)
    hbp = df["HBP"].astype(float)
    sf = df["SF"].astype(float)

    tb = h + b2 + 2.0 * b3 + 3.0 * hr
    obp_den = ab + bb + hbp + sf
    avg = np.divide(h, ab, out=np.zeros_like(ab, dtype=float), where=ab > 0)
    obp = np.divide(h + bb + hbp, obp_den, out=np.zeros_like(obp_den, dtype=float), where=obp_den > 0)
    slg = np.divide(tb, ab, out=np.zeros_like(ab, dtype=float), where=ab > 0)
    ops = obp + slg

    counting_sources: Dict[str, pd.Series] = {
        "R": df["R"].astype(float),
        "RBI": df["RBI"].astype(float),
        "HR": hr,
        "SB": df["SB"].astype(float),
        "H": h,
        "BB": bb,
        "2B": b2,
        "TB": pd.Series(tb, index=df.index),
    }
    for cat, series in counting_sources.items():
        if cat in selected:
            components.append(_zscore(series))

    if "AVG" in selected:
        mean_avg = float(np.nanmean(avg)) if len(avg) else 0.0
        components.append(_zscore(pd.Series((avg - mean_avg) * ab, index=df.index)))
    if "OBP" in selected:
        mean_obp = float(np.nanmean(obp)) if len(obp) else 0.0
        components.append(_zscore(pd.Series((obp - mean_obp) * obp_den, index=df.index)))
    if "SLG" in selected:
        mean_slg = float(np.nanmean(slg)) if len(slg) else 0.0
        components.append(_zscore(pd.Series((slg - mean_slg) * ab, index=df.index)))
    if "OPS" in selected:
        mean_ops = float(np.nanmean(ops)) if len(ops) else 0.0
        components.append(_zscore(pd.Series((ops - mean_ops) * ab, index=df.index)))

    if not components:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)

    w = components[0].copy()
    for component in components[1:]:
        w = w + component
    return w


def _initial_pitcher_weight(df: pd.DataFrame, categories: Optional[List[str]] = None) -> pd.Series:
    """Rough first-pass weight for baseline starter-pool construction."""
    df = df.copy()
    selected = {str(cat).strip().upper() for cat in (categories or list(PIT_CATS))}
    components: List[pd.Series] = []

    for cat in ("W", "K", "SV", "QS", "QA3", "SVH"):
        if cat in selected:
            components.append(_zscore(df[cat]))

    if "ERA" in selected or "WHIP" in selected:
        ip_sum = float(df["IP"].sum())
        mean_era = float(9.0 * df["ER"].sum() / ip_sum) if ip_sum > 0 else float(df["ERA"].mean())
        mean_whip = float((df["H"].sum() + df["BB"].sum()) / ip_sum) if ip_sum > 0 else float(df["WHIP"].mean())
        if "ERA" in selected:
            df["ERA_surplus_ER"] = (mean_era - df["ERA"]) * df["IP"] / 9.0
            components.append(_zscore(df["ERA_surplus_ER"]))
        if "WHIP" in selected:
            df["WHIP_surplus"] = (mean_whip - df["WHIP"]) * df["IP"]
            components.append(_zscore(df["WHIP_surplus"]))

    if not components:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)

    w = components[0].copy()
    for component in components[1:]:
        w = w + component
    return w


def _team_avg(h: float, ab: float) -> float:
    return float(h / ab) if ab > 0 else 0.0


def _team_obp(h: float, bb: float, hbp: float, ab: float, sf: float) -> float:
    den = ab + bb + hbp + sf
    return float((h + bb + hbp) / den) if den > 0 else 0.0


def _team_era(er: float, ip: float) -> float:
    return float(9.0 * er / ip) if ip > 0 else float("nan")


def _team_whip(h: float, bb: float, ip: float) -> float:
    return float((h + bb) / ip) if ip > 0 else float("nan")


def common_hit_category_totals(totals: Dict[str, float]) -> Dict[str, float]:
    h = float(totals.get("H", 0.0))
    ab = float(totals.get("AB", 0.0))
    b2 = float(totals.get("2B", 0.0))
    b3 = float(totals.get("3B", 0.0))
    hr = float(totals.get("HR", 0.0))
    bb = float(totals.get("BB", 0.0))
    hbp = float(totals.get("HBP", 0.0))
    sf = float(totals.get("SF", 0.0))

    tb = h + b2 + 2.0 * b3 + 3.0 * hr
    obp = _team_obp(h, bb, hbp, ab, sf)
    slg = float(tb / ab) if ab > 0 else 0.0

    return {
        "R": float(totals.get("R", 0.0)),
        "RBI": float(totals.get("RBI", 0.0)),
        "HR": hr,
        "SB": float(totals.get("SB", 0.0)),
        "AVG": _team_avg(h, ab),
        "OBP": obp,
        "SLG": slg,
        "OPS": obp + slg,
        "H": h,
        "BB": bb,
        "2B": b2,
        "TB": tb,
    }


def common_pitch_category_totals(totals: Dict[str, float]) -> Dict[str, float]:
    return {
        "W": float(totals.get("W", 0.0)),
        "K": float(totals.get("K", 0.0)),
        "SV": float(totals.get("SV", 0.0)),
        "ERA": float(totals.get("ERA", 0.0)),
        "WHIP": float(totals.get("WHIP", 0.0)),
        "QS": float(totals.get("QS", 0.0)),
        "QA3": float(totals.get("QA3", 0.0)),
        "SVH": float(totals.get("SVH", 0.0)),
    }


def common_replacement_pitcher_rates(
    all_pit_df: pd.DataFrame,
    assigned_pit_df: pd.DataFrame,
    n_rep: int,
) -> Dict[str, float]:
    """Per-inning replacement rates from the best available non-starter pitchers."""
    assigned_players = set(assigned_pit_df["Player"])
    rep = all_pit_df[~all_pit_df["Player"].isin(assigned_players)].copy()
    rep = rep.sort_values("weight", ascending=False).head(max(int(n_rep), 1))

    ip = float(rep["IP"].sum()) if not rep.empty else 0.0
    if ip <= 0:
        return {k: 0.0 for k in ["W", "QS", "QA3", "K", "SV", "SVH", "ER", "H", "BB"]}

    return {
        "W": float(rep["W"].sum() / ip),
        "QS": float(rep["QS"].sum() / ip),
        "QA3": float(rep["QA3"].sum() / ip),
        "K": float(rep["K"].sum() / ip),
        "SV": float(rep["SV"].sum() / ip),
        "SVH": float(rep["SVH"].sum() / ip),
        "ER": float(rep["ER"].sum() / ip),
        "H": float(rep["H"].sum() / ip),
        "BB": float(rep["BB"].sum() / ip),
    }


def common_apply_pitching_bounds(
    totals: Dict[str, float],
    lg: CommonDynastyRotoSettings,
    rep_rates: Optional[Dict[str, float]],
    *,
    fill_to_ip_max: bool = True,
    enforce_ip_min: bool = True,
) -> Dict[str, float]:
    """Apply optional IP cap/fill and IP-min qualification to common-mode pitching totals."""
    out = {k: float(totals.get(k, 0.0)) for k in PIT_COMPONENT_COLS}
    ip = float(out["IP"])

    if lg.ip_max is not None:
        ip_cap = float(lg.ip_max)

        # If over cap, scale all counting components down to cap.
        if ip > ip_cap and ip > 0:
            factor = ip_cap / ip
            for col in PIT_COMPONENT_COLS:
                out[col] = float(out[col]) * factor
            ip = ip_cap

        # If under cap, assume streamable replacement innings.
        if fill_to_ip_max and ip < ip_cap and rep_rates is not None:
            add = ip_cap - ip
            out["IP"] = ip_cap
            for col in ["W", "QS", "QA3", "K", "SV", "SVH", "ER", "H", "BB"]:
                out[col] = float(out[col]) + add * float(rep_rates.get(col, 0.0))
            ip = ip_cap

    out["ERA"] = _team_era(out["ER"], ip)
    out["WHIP"] = _team_whip(out["H"], out["BB"], ip)

    # Optional IP minimum qualification rule (default OFF)
    if enforce_ip_min and lg.ip_min and lg.ip_min > 0 and ip < lg.ip_min:
        out["ERA"] = 99.0
        out["WHIP"] = 5.0

    return out


def _coerce_non_negative_float(value: object) -> float:
    """Best-effort numeric coercion for IP/share guards."""
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return 0.0
    return float(max(number, 0.0))


def _positive_credit_scale(
    *,
    player_volume: float,
    slot_volume_reference: float,
    min_share_for_positive_credit: float = 0.35,
    full_share_for_positive_credit: float = 1.00,
) -> float:
    """Return a [0, 1] positive-credit scale based on projected workload share."""
    slot_volume = _coerce_non_negative_float(slot_volume_reference)
    player_workload = _coerce_non_negative_float(player_volume)
    if slot_volume <= 0.0:
        return 1.0

    share = player_workload / slot_volume
    min_share = float(min_share_for_positive_credit)
    full_share = float(full_share_for_positive_credit)

    if full_share <= min_share:
        return 1.0 if share >= full_share else 0.0
    if share <= min_share:
        return 0.0
    if share >= full_share:
        return 1.0
    return float((share - min_share) / (full_share - min_share))


def _low_volume_positive_credit_scale(
    *,
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> float:
    """Return a [0, 1] positive-credit scale based on projected innings share."""
    return _positive_credit_scale(
        player_volume=pitcher_ip,
        slot_volume_reference=slot_ip_reference,
        min_share_for_positive_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_credit=full_share_for_positive_ratio_credit,
    )


def _apply_low_volume_non_ratio_positive_guard(
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> None:
    """Scale positive non-ratio pitching category credit for tiny workloads."""
    scale = _low_volume_positive_credit_scale(
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )
    if scale >= 1.0:
        return

    for cat in pit_categories:
        if cat in COMMON_REVERSED_PITCH_CATS:
            continue
        if float(delta.get(cat, 0.0)) > 0.0:
            delta[cat] = float(delta[cat]) * scale


def _apply_low_volume_ratio_guard(
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> None:
    """Scale positive ERA/WHIP credit based on projected innings share."""
    scale = _low_volume_positive_credit_scale(
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )
    if scale >= 1.0:
        return

    for cat in COMMON_REVERSED_PITCH_CATS:
        if cat in pit_categories and float(delta.get(cat, 0.0)) > 0.0:
            delta[cat] = float(delta[cat]) * scale


def _apply_hitter_playing_time_reliability_guard(
    delta: Dict[str, float],
    *,
    hit_categories: List[str],
    hitter_ab: float,
    slot_ab_reference: float,
    min_share_for_positive_credit: float = 0.35,
    full_share_for_positive_credit: float = 1.00,
) -> None:
    """Scale positive hitter category credit for low projected AB workloads."""
    scale = _positive_credit_scale(
        player_volume=hitter_ab,
        slot_volume_reference=slot_ab_reference,
        min_share_for_positive_credit=min_share_for_positive_credit,
        full_share_for_positive_credit=full_share_for_positive_credit,
    )
    if scale >= 1.0:
        return
    for cat in hit_categories:
        if float(delta.get(cat, 0.0)) > 0.0:
            delta[cat] = float(delta[cat]) * scale


def _apply_pitcher_playing_time_reliability_guard(
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_credit: float = 0.35,
    full_share_for_positive_credit: float = 1.00,
) -> None:
    """Scale positive pitching category credit for low projected IP workloads."""
    scale = _positive_credit_scale(
        player_volume=pitcher_ip,
        slot_volume_reference=slot_ip_reference,
        min_share_for_positive_credit=min_share_for_positive_credit,
        full_share_for_positive_credit=full_share_for_positive_credit,
    )
    if scale >= 1.0:
        return
    for cat in pit_categories:
        if float(delta.get(cat, 0.0)) > 0.0:
            delta[cat] = float(delta[cat]) * scale


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
    diffs = {c: [] for c in active_categories}

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

        vals = {c: [] for c in active_categories}
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
    diffs = {c: [] for c in active_categories}
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

        vals = {c: [] for c in active_categories}
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


def compute_year_context(
    year: int,
    bat: pd.DataFrame,
    pit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng_seed: Optional[int] = None,
) -> dict:
    bat_y = bat[bat["Year"] == year].copy()
    pit_y = pit[pit["Year"] == year].copy()
    hit_categories = _active_common_hit_categories(lg)
    pit_categories = _active_common_pitch_categories(lg)

    # Keep QS/QA3 interchangeable for compatibility with mixed schemas.
    if "QS" not in pit_y.columns and "QA3" in pit_y.columns:
        pit_y["QS"] = pit_y["QA3"]
    if "QA3" not in pit_y.columns and "QS" in pit_y.columns:
        pit_y["QA3"] = pit_y["QS"]

    # Clean numeric NaNs
    for c in HIT_COMPONENT_COLS:
        if c not in bat_y.columns:
            bat_y[c] = 0.0
        bat_y[c] = bat_y[c].fillna(0.0)
    for c in PIT_COMPONENT_COLS:
        if c not in pit_y.columns:
            pit_y[c] = 0.0
        pit_y[c] = pit_y[c].fillna(0.0)

    # Starter-pool candidates (must have playing time)
    bat_play = bat_y[bat_y["AB"] > 0].copy()
    pit_play = pit_y[pit_y["IP"] > 0].copy()

    if bat_play.empty:
        raise ValueError(
            f"Year {year}: no hitters with AB > 0 after filtering. Check Year values and AB projections."
        )
    if pit_play.empty:
        raise ValueError(
            f"Year {year}: no pitchers with IP > 0 after filtering. Check Year values and IP projections."
        )

    # Initial weights to define the league baseline pool/positional scarcity
    bat_play["weight"] = _initial_hitter_weight(bat_play, categories=hit_categories)
    pit_play["weight"] = _initial_pitcher_weight(pit_play, categories=pit_categories)

    league_hit_slots = expand_slot_counts(lg.hitter_slots, lg.n_teams)
    league_pit_slots = expand_slot_counts(lg.pitcher_slots, lg.n_teams)

    assigned_hit = assign_players_to_slots_with_vacancy_fill(
        bat_play,
        league_hit_slots,
        eligible_hit_slots,
        stat_cols=HIT_COMPONENT_COLS,
        year=year,
        side_label="hitter",
        weight_col="weight",
    )
    assigned_pit = assign_players_to_slots_with_vacancy_fill(
        pit_play,
        league_pit_slots,
        eligible_pit_slots,
        stat_cols=PIT_COMPONENT_COLS,
        year=year,
        side_label="pitcher",
        weight_col="weight",
    )

    baseline_hit = assigned_hit.groupby("AssignedSlot")[HIT_COMPONENT_COLS].mean()
    baseline_pit = assigned_pit.groupby("AssignedSlot")[PIT_COMPONENT_COLS].mean()

    # Baseline "average team" totals
    team_hit_slots = build_team_slot_template(lg.hitter_slots)
    team_pit_slots = build_team_slot_template(lg.pitcher_slots)

    base_hit_tot = baseline_hit.loc[team_hit_slots].sum()
    base_avg = _team_avg(float(base_hit_tot["H"]), float(base_hit_tot["AB"]))

    base_pit_tot = baseline_pit.loc[team_pit_slots].sum()
    rep_rates = common_replacement_pitcher_rates(
        pit_play,
        assigned_pit,
        n_rep=lg.replacement_pitchers_n,
    )
    base_pit_bounded = common_apply_pitching_bounds(
        {col: float(base_pit_tot[col]) for col in PIT_COMPONENT_COLS},
        lg,
        rep_rates,
    )

    # SGP denominators by simulation
    seed = year if rng_seed is None else int(rng_seed)
    rng_hit = np.random.default_rng(seed)
    rng_pit = np.random.default_rng(seed + 1)
    sgp_hit = simulate_sgp_hit(assigned_hit, lg, rng_hit, categories=hit_categories)
    sgp_pit = simulate_sgp_pit(assigned_pit, lg, rng_pit, rep_rates=rep_rates, categories=pit_categories)

    return {
        "year": year,
        "bat_y": bat_y,
        "pit_y": pit_y,
        "assigned_hit": assigned_hit,
        "assigned_pit": assigned_pit,
        "baseline_hit": baseline_hit,
        "baseline_pit": baseline_pit,
        "base_hit_tot": base_hit_tot,
        "base_avg": base_avg,
        "base_pit_tot": base_pit_tot,
        "base_pit_bounded": base_pit_bounded,
        "rep_rates": rep_rates,
        "sgp_hit": sgp_hit,
        "sgp_pit": sgp_pit,
        "hit_categories": hit_categories,
        "pit_categories": pit_categories,
    }


def compute_year_player_values(ctx: dict, lg: CommonDynastyRotoSettings) -> Tuple[pd.DataFrame, pd.DataFrame]:
    year = int(ctx["year"])
    bat_y = ctx["bat_y"]
    pit_y = ctx["pit_y"]

    baseline_hit = ctx["baseline_hit"]
    baseline_pit = ctx["baseline_pit"]
    base_hit_tot = ctx["base_hit_tot"]
    base_hit_cats = common_hit_category_totals({col: float(base_hit_tot[col]) for col in HIT_COMPONENT_COLS})

    base_pit_tot = ctx["base_pit_tot"]
    rep_rates = ctx.get("rep_rates")
    base_pit_bounded = dict(ctx["base_pit_bounded"])
    base_pit_cats = common_pitch_category_totals(base_pit_bounded)

    sgp_hit = ctx["sgp_hit"]
    sgp_pit = ctx["sgp_pit"]
    hit_categories = ctx.get("hit_categories") or _active_common_hit_categories(lg)
    pit_categories = ctx.get("pit_categories") or _active_common_pitch_categories(lg)

    # --- Hitters: best eligible slot vs average starter at that slot ---
    hit_rows = []
    for row in bat_y.to_dict(orient="records"):
        pos_set = parse_hit_positions(row.get("Pos", ""))
        slots = eligible_hit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_hit.index:
                continue
            b = baseline_hit.loc[slot]

            new_tot = base_hit_tot.copy()
            for col in HIT_COMPONENT_COLS:
                new_tot[col] = new_tot[col] - b[col] + float(row.get(col, 0.0))

            new_hit_cats = common_hit_category_totals({col: float(new_tot[col]) for col in HIT_COMPONENT_COLS})
            delta = {
                cat: float(new_hit_cats.get(cat, 0.0) - base_hit_cats.get(cat, 0.0))
                for cat in hit_categories
            }
            if bool(getattr(lg, "enable_playing_time_reliability", False)):
                _apply_hitter_playing_time_reliability_guard(
                    delta,
                    hit_categories=hit_categories,
                    hitter_ab=_coerce_non_negative_float(row.get("AB", 0.0)),
                    slot_ab_reference=_coerce_non_negative_float(b.get("AB", 0.0)),
                )
            if bool(getattr(lg, "enable_playing_time_reliability", False)):
                _apply_hitter_playing_time_reliability_guard(
                    delta,
                    hit_categories=hit_categories,
                    hitter_ab=_coerce_non_negative_float(row.get("AB", 0.0)),
                    slot_ab_reference=_coerce_non_negative_float(b.get("AB", 0.0)),
                )

            val = 0.0
            for c in hit_categories:
                denom = float(sgp_hit[c])
                val += (delta[c] / denom) if denom else 0.0

            if val > best_val:
                best_val = val
                best_slot = slot

        hit_rows.append(
            {
                "Player": row.get("Player"),
                "Year": year,
                "Type": "H",
                "Team": row.get("Team", np.nan),
                "Age": row.get("Age", np.nan),
                "Pos": row.get("Pos", np.nan),
                "BestSlot": best_slot,
                "YearValue": float(best_val),
            }
        )

    hit_vals = pd.DataFrame(hit_rows)

    # --- Pitchers: best eligible slot vs average starter at that slot ---
    pit_rows = []
    for row in pit_y.to_dict(orient="records"):
        pos_set = parse_pit_positions(row.get("Pos", ""))
        slots = eligible_pit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_pit.index:
                continue
            b = baseline_pit.loc[slot]

            new_tot = base_pit_tot.copy()
            for col in PIT_COMPONENT_COLS:
                new_tot[col] = new_tot[col] - b[col] + float(row.get(col, 0.0))

            new_tot_bounded = common_apply_pitching_bounds(
                {col: float(new_tot[col]) for col in PIT_COMPONENT_COLS},
                lg,
                rep_rates,
            )

            new_pit_cats = common_pitch_category_totals(new_tot_bounded)
            delta: Dict[str, float] = {}
            for cat in pit_categories:
                new_val = float(new_pit_cats.get(cat, 0.0))
                base_val = float(base_pit_cats.get(cat, 0.0))
                if cat in COMMON_REVERSED_PITCH_CATS:
                    delta[cat] = base_val - new_val
                else:
                    delta[cat] = new_val - base_val
            if bool(getattr(lg, "enable_playing_time_reliability", False)):
                _apply_pitcher_playing_time_reliability_guard(
                    delta,
                    pit_categories=pit_categories,
                    pitcher_ip=_coerce_non_negative_float(row.get("IP", 0.0)),
                    slot_ip_reference=_coerce_non_negative_float(b.get("IP", 0.0)),
                )
            else:
                _apply_low_volume_non_ratio_positive_guard(
                    delta,
                    pit_categories=pit_categories,
                    pitcher_ip=_coerce_non_negative_float(row.get("IP", 0.0)),
                    slot_ip_reference=_coerce_non_negative_float(b.get("IP", 0.0)),
                )
                _apply_low_volume_ratio_guard(
                    delta,
                    pit_categories=pit_categories,
                    pitcher_ip=_coerce_non_negative_float(row.get("IP", 0.0)),
                    slot_ip_reference=_coerce_non_negative_float(b.get("IP", 0.0)),
                )

            val = 0.0
            for c in pit_categories:
                denom = float(sgp_pit[c])
                val += (delta[c] / denom) if denom else 0.0

            if val > best_val:
                best_val = val
                best_slot = slot

        pit_rows.append(
            {
                "Player": row.get("Player"),
                "Year": year,
                "Type": "P",
                "Team": row.get("Team", np.nan),
                "Age": row.get("Age", np.nan),
                "Pos": row.get("Pos", np.nan),
                "BestSlot": best_slot,
                "YearValue": float(best_val),
            }
        )

    pit_vals = pd.DataFrame(pit_rows)
    return hit_vals, pit_vals


def compute_replacement_baselines(
    ctx: dict,
    lg: CommonDynastyRotoSettings,
    rostered_players: Set[str],
    n_repl: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Build per-slot replacement baselines from the unrostered pool."""
    n_repl = int(n_repl or lg.n_teams)

    bat_y = ctx["bat_y"].copy()
    pit_y = ctx["pit_y"].copy()

    for c in HIT_COMPONENT_COLS:
        bat_y[c] = bat_y[c].fillna(0.0)
    for c in PIT_COMPONENT_COLS:
        pit_y[c] = pit_y[c].fillna(0.0)

    hit_categories = ctx.get("hit_categories") or _active_common_hit_categories(lg)
    pit_categories = ctx.get("pit_categories") or _active_common_pitch_categories(lg)
    bat_y["weight"] = _initial_hitter_weight(bat_y, categories=hit_categories)
    pit_y["weight"] = _initial_pitcher_weight(pit_y, categories=pit_categories)

    fa_hit = bat_y[(~bat_y["Player"].isin(rostered_players)) & (bat_y["AB"] > 0)].copy()
    fa_pit = pit_y[(~pit_y["Player"].isin(rostered_players)) & (pit_y["IP"] > 0)].copy()

    fa_hit["elig"] = fa_hit["Pos"].apply(lambda p: eligible_hit_slots(parse_hit_positions(p)))
    fa_pit["elig"] = fa_pit["Pos"].apply(lambda p: eligible_pit_slots(parse_pit_positions(p)))

    baseline_hit_avg = ctx["baseline_hit"]
    baseline_pit_avg = ctx["baseline_pit"]

    repl_hit_rows: List[dict] = []
    for slot in baseline_hit_avg.index:
        cand = (
            fa_hit[fa_hit["elig"].apply(lambda s: slot in s)]
            .sort_values("weight", ascending=False)
            .head(n_repl)
        )
        repl = baseline_hit_avg.loc[slot] if len(cand) == 0 else cand[HIT_COMPONENT_COLS].mean()
        row = {c: float(repl.get(c, 0.0)) for c in HIT_COMPONENT_COLS}
        row["AssignedSlot"] = slot
        repl_hit_rows.append(row)

    repl_hit = pd.DataFrame(repl_hit_rows).set_index("AssignedSlot")

    repl_pit_rows: List[dict] = []
    for slot in baseline_pit_avg.index:
        cand = (
            fa_pit[fa_pit["elig"].apply(lambda s: slot in s)]
            .sort_values("weight", ascending=False)
            .head(n_repl)
        )
        repl = baseline_pit_avg.loc[slot] if len(cand) == 0 else cand[PIT_COMPONENT_COLS].mean()
        row = {c: float(repl.get(c, 0.0)) for c in PIT_COMPONENT_COLS}
        row["AssignedSlot"] = slot
        repl_pit_rows.append(row)

    repl_pit = pd.DataFrame(repl_pit_rows).set_index("AssignedSlot")
    return repl_hit, repl_pit


def compute_year_player_values_vs_replacement(
    ctx: dict,
    lg: CommonDynastyRotoSettings,
    repl_hit: pd.DataFrame,
    repl_pit: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute per-year values as marginal roto points above replacement."""
    year = int(ctx["year"])
    bat_y = ctx["bat_y"]
    pit_y = ctx["pit_y"]

    baseline_hit_avg = ctx["baseline_hit"]
    baseline_pit_avg = ctx["baseline_pit"]
    base_hit_tot_avg = ctx["base_hit_tot"]
    base_pit_tot_avg = ctx["base_pit_tot"]
    rep_rates = ctx.get("rep_rates")

    sgp_hit = ctx["sgp_hit"]
    sgp_pit = ctx["sgp_pit"]
    hit_categories = ctx.get("hit_categories") or _active_common_hit_categories(lg)
    pit_categories = ctx.get("pit_categories") or _active_common_pitch_categories(lg)

    hit_rows = []
    for row in bat_y.to_dict(orient="records"):
        pos_set = parse_hit_positions(row.get("Pos", ""))
        slots = eligible_hit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_hit_avg.index or slot not in repl_hit.index:
                continue

            b_avg = baseline_hit_avg.loc[slot]
            b_rep = repl_hit.loc[slot]

            base_tot = base_hit_tot_avg.copy()
            new_tot = base_hit_tot_avg.copy()
            for col in HIT_COMPONENT_COLS:
                base_tot[col] = base_tot[col] - b_avg[col] + b_rep[col]
                new_tot[col] = new_tot[col] - b_avg[col] + float(row.get(col, 0.0))

            base_hit_cats = common_hit_category_totals({col: float(base_tot[col]) for col in HIT_COMPONENT_COLS})
            new_hit_cats = common_hit_category_totals({col: float(new_tot[col]) for col in HIT_COMPONENT_COLS})
            delta = {
                cat: float(new_hit_cats.get(cat, 0.0) - base_hit_cats.get(cat, 0.0))
                for cat in hit_categories
            }

            val = 0.0
            for c in hit_categories:
                denom = float(sgp_hit[c])
                val += (delta[c] / denom) if denom else 0.0

            if val > best_val:
                best_val = val
                best_slot = slot

        hit_rows.append(
            {
                "Player": row.get("Player"),
                "Year": year,
                "Type": "H",
                "Team": row.get("Team", np.nan),
                "Age": row.get("Age", np.nan),
                "Pos": row.get("Pos", np.nan),
                "BestSlot": best_slot,
                "YearValue": float(best_val),
            }
        )

    hit_vals = pd.DataFrame(hit_rows)

    pit_rows = []
    for row in pit_y.to_dict(orient="records"):
        pos_set = parse_pit_positions(row.get("Pos", ""))
        slots = eligible_pit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_pit_avg.index or slot not in repl_pit.index:
                continue

            b_avg = baseline_pit_avg.loc[slot]
            b_rep = repl_pit.loc[slot]

            base_raw = {c: float(base_pit_tot_avg[c]) for c in PIT_COMPONENT_COLS}
            new_raw = {c: float(base_pit_tot_avg[c]) for c in PIT_COMPONENT_COLS}
            for col in PIT_COMPONENT_COLS:
                base_raw[col] = base_raw[col] - float(b_avg[col]) + float(b_rep[col])
                new_raw[col] = new_raw[col] - float(b_avg[col]) + float(row.get(col, 0.0))

            new_bounded = common_apply_pitching_bounds(
                new_raw,
                lg,
                rep_rates,
            )
            base_bounded = common_apply_pitching_bounds(
                base_raw,
                lg,
                rep_rates,
            )

            base_pit_cats = common_pitch_category_totals(base_bounded)
            new_pit_cats = common_pitch_category_totals(new_bounded)
            delta: Dict[str, float] = {}
            for cat in pit_categories:
                new_val = float(new_pit_cats.get(cat, 0.0))
                base_val = float(base_pit_cats.get(cat, 0.0))
                if cat in COMMON_REVERSED_PITCH_CATS:
                    delta[cat] = base_val - new_val
                else:
                    delta[cat] = new_val - base_val
            if bool(getattr(lg, "enable_playing_time_reliability", False)):
                _apply_pitcher_playing_time_reliability_guard(
                    delta,
                    pit_categories=pit_categories,
                    pitcher_ip=_coerce_non_negative_float(row.get("IP", 0.0)),
                    slot_ip_reference=_coerce_non_negative_float(b_avg.get("IP", 0.0)),
                )
            else:
                _apply_low_volume_non_ratio_positive_guard(
                    delta,
                    pit_categories=pit_categories,
                    pitcher_ip=_coerce_non_negative_float(row.get("IP", 0.0)),
                    slot_ip_reference=_coerce_non_negative_float(b_avg.get("IP", 0.0)),
                )
                _apply_low_volume_ratio_guard(
                    delta,
                    pit_categories=pit_categories,
                    pitcher_ip=_coerce_non_negative_float(row.get("IP", 0.0)),
                    slot_ip_reference=_coerce_non_negative_float(b_avg.get("IP", 0.0)),
                )

            val = 0.0
            for c in pit_categories:
                denom = float(sgp_pit[c])
                val += (delta[c] / denom) if denom else 0.0

            if val > best_val:
                best_val = val
                best_slot = slot

        pit_rows.append(
            {
                "Player": row.get("Player"),
                "Year": year,
                "Type": "P",
                "Team": row.get("Team", np.nan),
                "Age": row.get("Age", np.nan),
                "Pos": row.get("Pos", np.nan),
                "BestSlot": best_slot,
                "YearValue": float(best_val),
            }
        )

    pit_vals = pd.DataFrame(pit_rows)
    return hit_vals, pit_vals


def combine_two_way(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame:
    merged = pd.merge(
        hit_vals[["Player", "Year", "YearValue", "BestSlot", "Team", "Age", "Pos"]],
        pit_vals[["Player", "Year", "YearValue", "BestSlot", "Team", "Age", "Pos"]],
        on=["Player", "Year"],
        how="outer",
        suffixes=("_hit", "_pit"),
    )

    out_vals = []
    out_slots = []

    for _, r in merged.iterrows():
        hv = r.get("YearValue_hit")
        pv = r.get("YearValue_pit")

        if pd.isna(hv) and pd.isna(pv):
            out_vals.append(np.nan)
            out_slots.append(None)
            continue
        if pd.isna(hv):
            out_vals.append(float(pv))
            out_slots.append(r.get("BestSlot_pit"))
            continue
        if pd.isna(pv):
            out_vals.append(float(hv))
            out_slots.append(r.get("BestSlot_hit"))
            continue

        hv = float(hv)
        pv = float(pv)

        if two_way == "sum":
            out_vals.append(hv + pv)
            out_slots.append(f"{r.get('BestSlot_hit')}+{r.get('BestSlot_pit')}")
        else:  # "max"
            if hv >= pv:
                out_vals.append(hv)
                out_slots.append(r.get("BestSlot_hit"))
            else:
                out_vals.append(pv)
                out_slots.append(r.get("BestSlot_pit"))

    merged["YearValue"] = out_vals
    merged["BestSlot"] = out_slots
    merged["Team"] = merged["Team_hit"].combine_first(merged["Team_pit"])
    merged["Pos"] = merged["Pos_hit"].combine_first(merged["Pos_pit"])
    merged["Age"] = merged["Age_hit"].combine_first(merged["Age_pit"])

    return merged[["Player", "Year", "YearValue", "BestSlot", "Team", "Pos", "Age"]]


__all__ = [
    "COMMON_REVERSED_PITCH_CATS",
    "common_hit_category_totals",
    "common_pitch_category_totals",
    "common_replacement_pitcher_rates",
    "common_apply_pitching_bounds",
    "_coerce_non_negative_float",
    "_positive_credit_scale",
    "_low_volume_positive_credit_scale",
    "_apply_low_volume_non_ratio_positive_guard",
    "_apply_low_volume_ratio_guard",
    "_apply_hitter_playing_time_reliability_guard",
    "_apply_pitcher_playing_time_reliability_guard",
    "_mean_adjacent_rank_gap",
    "simulate_sgp_hit",
    "simulate_sgp_pit",
    "compute_year_context",
    "compute_year_player_values",
    "compute_replacement_baselines",
    "compute_year_player_values_vs_replacement",
    "combine_two_way",
]
