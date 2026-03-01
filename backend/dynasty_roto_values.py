"""Legacy compatibility surface for dynasty valuation helpers and CLI."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

try:
    from backend.valuation import common_math as _common_math
    from backend.valuation import minor_eligibility as _minor_elig
    from backend.valuation import projection_averaging as _projection_averaging
    from backend.valuation import projection_identity as _projection_identity
    from backend.valuation import xlsx_formatting as _xlsx_fmt
    from backend.valuation.assignment import (
        HAVE_SCIPY as HAVE_SCIPY,
    )
    from backend.valuation.assignment import (
        assign_players_to_slots as assign_players_to_slots,
    )
    from backend.valuation.assignment import (
        assign_players_to_slots_with_vacancy_fill as assign_players_to_slots_with_vacancy_fill,
    )
    from backend.valuation.assignment import (
        build_slot_list as build_slot_list,
    )
    from backend.valuation.assignment import (
        build_team_slot_template as build_team_slot_template,
    )
    from backend.valuation.assignment import (
        expand_slot_counts as expand_slot_counts,
    )
    from backend.valuation.assignment import (
        validate_assigned_slots as validate_assigned_slots,
    )
    from backend.valuation.models import (
        HIT_CATS as HIT_CATS,
    )
    from backend.valuation.models import (
        HIT_COMPONENT_COLS as HIT_COMPONENT_COLS,
    )
    from backend.valuation.models import (
        PIT_CATS as PIT_CATS,
    )
    from backend.valuation.models import (
        PIT_COMPONENT_COLS as PIT_COMPONENT_COLS,
    )
    from backend.valuation.models import (
        CommonDynastyRotoSettings as CommonDynastyRotoSettings,
    )
    from backend.valuation.positions import (
        eligible_hit_slots as eligible_hit_slots,
    )
    from backend.valuation.positions import (
        eligible_pit_slots as eligible_pit_slots,
    )
    from backend.valuation.positions import (
        parse_hit_positions as parse_hit_positions,
    )
    from backend.valuation.positions import (
        parse_pit_positions as parse_pit_positions,
    )
except ImportError:
    # Support direct execution/import when /backend is added to sys.path.
    from valuation import common_math as _common_math  # type: ignore[no-redef]
    from valuation import minor_eligibility as _minor_elig  # type: ignore[no-redef]
    from valuation import projection_averaging as _projection_averaging  # type: ignore[no-redef]
    from valuation import projection_identity as _projection_identity  # type: ignore[no-redef]
    from valuation import xlsx_formatting as _xlsx_fmt  # type: ignore[no-redef]
    from valuation.assignment import (  # type: ignore[no-redef]
        HAVE_SCIPY as HAVE_SCIPY,
    )
    from valuation.assignment import (
        assign_players_to_slots as assign_players_to_slots,
    )
    from valuation.assignment import (
        assign_players_to_slots_with_vacancy_fill as assign_players_to_slots_with_vacancy_fill,
    )
    from valuation.assignment import (
        build_slot_list as build_slot_list,
    )
    from valuation.assignment import (
        build_team_slot_template as build_team_slot_template,
    )
    from valuation.assignment import (
        expand_slot_counts as expand_slot_counts,
    )
    from valuation.assignment import (
        validate_assigned_slots as validate_assigned_slots,
    )
    from valuation.models import (  # type: ignore[no-redef]
        HIT_CATS as HIT_CATS,
    )
    from valuation.models import (
        HIT_COMPONENT_COLS as HIT_COMPONENT_COLS,
    )
    from valuation.models import (
        PIT_CATS as PIT_CATS,
    )
    from valuation.models import (
        PIT_COMPONENT_COLS as PIT_COMPONENT_COLS,
    )
    from valuation.models import (
        CommonDynastyRotoSettings as CommonDynastyRotoSettings,
    )
    from valuation.positions import (  # type: ignore[no-redef]
        eligible_hit_slots as eligible_hit_slots,
    )
    from valuation.positions import (
        eligible_pit_slots as eligible_pit_slots,
    )
    from valuation.positions import (
        parse_hit_positions as parse_hit_positions,
    )
    from valuation.positions import (
        parse_pit_positions as parse_pit_positions,
    )

# Projection de-duplication helpers
PROJECTION_DATE_COLS = _projection_identity.PROJECTION_DATE_COLS
PLAYER_KEY_COL = _projection_identity.PLAYER_KEY_COL
PLAYER_ENTITY_KEY_COL = _projection_identity.PLAYER_ENTITY_KEY_COL
PLAYER_KEY_PATTERN = _projection_identity.PLAYER_KEY_PATTERN

# Bench-stash penalty curve defaults:
# - first stash round per team should still carry a small cost
# - later rounds are progressively more punitive
BENCH_STASH_MIN_PENALTY = 0.10
BENCH_STASH_MAX_PENALTY = 0.85
BENCH_STASH_PENALTY_GAMMA = 1.35


def _find_projection_date_col(df: pd.DataFrame) -> Optional[str]:
    return _projection_identity._find_projection_date_col(df)


def _normalize_player_key(value: object) -> str:
    return _projection_identity._normalize_player_key(value)


def _normalize_team_key(value: object) -> str:
    return _projection_identity._normalize_team_key(value)


def _normalize_year_key(value: object) -> str:
    return _projection_identity._normalize_year_key(value)


def _team_column_for_dataframe(df: pd.DataFrame) -> Optional[str]:
    return _projection_identity._team_column_for_dataframe(df)


def _add_player_identity_keys(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return _projection_identity._add_player_identity_keys(bat, pit)


def _build_player_identity_lookup(bat: pd.DataFrame, pit: pd.DataFrame) -> pd.DataFrame:
    return _projection_identity._build_player_identity_lookup(bat, pit)


def _attach_identity_columns_to_output(out: pd.DataFrame, identity_lookup: pd.DataFrame) -> pd.DataFrame:
    return _projection_identity._attach_identity_columns_to_output(out, identity_lookup)


def average_recent_projections(
    df: pd.DataFrame,
    stat_cols: List[str],
    group_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    return _projection_averaging.average_recent_projections(
        df,
        stat_cols,
        group_cols=group_cols,
    )


def projection_meta_for_start_year(
    bat_df: pd.DataFrame,
    pit_df: pd.DataFrame,
    start_year: int,
) -> pd.DataFrame:
    return _projection_averaging.projection_meta_for_start_year(bat_df, pit_df, start_year)

# ----------------------------
# Helpers: recent-projection averaging + detail sheet formatting
# ----------------------------

DERIVED_HIT_RATE_COLS = _projection_averaging.DERIVED_HIT_RATE_COLS
DERIVED_PIT_RATE_COLS = _projection_averaging.DERIVED_PIT_RATE_COLS


def numeric_stat_cols_for_recent_avg(
    df: pd.DataFrame,
    group_cols: Optional[List[str]] = None,
    exclude_cols: Optional[Set[str]] = None,
) -> List[str]:
    return _projection_averaging.numeric_stat_cols_for_recent_avg(
        df,
        group_cols=group_cols,
        exclude_cols=exclude_cols,
    )


def reorder_detail_columns(
    df: pd.DataFrame,
    input_cols: List[str],
    add_after: Optional[str] = None,
    extra_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    return _projection_averaging.reorder_detail_columns(
        df,
        input_cols,
        add_after=add_after,
        extra_cols=extra_cols,
    )





def recompute_common_rates_hit(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute rate stats after averaging counting components.

    Recompute AVG/OBP/SLG/OPS (plus TB) from counting components when possible so
    aggregated rows stay internally consistent.
    """
    df = df.copy()

    # AVG = H / AB
    if "H" in df.columns and "AB" in df.columns:
        h = df["H"].to_numpy(dtype=float)
        ab = df["AB"].to_numpy(dtype=float)
        df["AVG"] = np.divide(h, ab, out=np.zeros_like(h), where=ab > 0)

    # OBP + OPS (OPS = OBP + SLG)
    needed = {"H", "2B", "3B", "HR", "BB", "HBP", "AB", "SF"}
    if needed.issubset(df.columns):
        h = df["H"].to_numpy(dtype=float)
        b2 = df["2B"].to_numpy(dtype=float)
        b3 = df["3B"].to_numpy(dtype=float)
        hr = df["HR"].to_numpy(dtype=float)
        bb = df["BB"].to_numpy(dtype=float)
        hbp = df["HBP"].to_numpy(dtype=float)
        ab = df["AB"].to_numpy(dtype=float)
        sf = df["SF"].to_numpy(dtype=float)

        # TB = 1B + 2*2B + 3*3B + 4*HR, and 1B = H - 2B - 3B - HR
        # => TB = H + 2B + 2*3B + 3*HR
        tb = h + b2 + 2.0 * b3 + 3.0 * hr

        obp_den = ab + bb + hbp + sf
        obp = np.divide(h + bb + hbp, obp_den, out=np.zeros_like(obp_den), where=obp_den > 0)
        slg = np.divide(tb, ab, out=np.zeros_like(ab), where=ab > 0)

        df["TB"] = tb
        df["OBP"] = obp
        df["SLG"] = slg
        df["OPS"] = obp + slg

    return df

def recompute_common_rates_pit(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "ER" in df.columns and "IP" in df.columns:
        er = df["ER"].to_numpy(dtype=float)
        ip = df["IP"].to_numpy(dtype=float)
        df["ERA"] = np.divide(9.0 * er, ip, out=np.full_like(ip, np.nan), where=ip > 0)
    if "H" in df.columns and "BB" in df.columns and "IP" in df.columns:
        h = df["H"].to_numpy(dtype=float)
        bb = df["BB"].to_numpy(dtype=float)
        ip = df["IP"].to_numpy(dtype=float)
        df["WHIP"] = np.divide(h + bb, ip, out=np.full_like(ip, np.nan), where=ip > 0)
    return df


# ----------------------------
# Column aliases and requirements
# ----------------------------

COMMON_COLUMN_ALIASES = {
    "mlbteam": "Team",
    "team": "Team",
    "player_name": "Player",
    "name": "Player",
}

def require_cols(df: pd.DataFrame, cols: List[str], sheet_name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Sheet '{sheet_name}' is missing required columns: {missing}")


def normalize_input_schema(df: pd.DataFrame, aliases: Dict[str, str]) -> pd.DataFrame:
    """Normalize incoming sheet columns (trim + alias mapping) while preserving existing names."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    lower_to_actual = {c.lower(): c for c in out.columns}
    rename_map: Dict[str, str] = {}
    for alias, canonical in aliases.items():
        actual = lower_to_actual.get(alias.lower())
        if actual and canonical not in out.columns:
            rename_map[actual] = canonical

    if rename_map:
        out = out.rename(columns=rename_map)
    return out


# ----------------------------
# Utility: z-scores for initial starter-pool weights
# (only used to construct baseline + starter pool; not the final valuation)
# ----------------------------

def zscore(s: pd.Series) -> pd.Series:
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


def initial_hitter_weight(df: pd.DataFrame, categories: Optional[List[str]] = None) -> pd.Series:
    """
    Rough first-pass weight to select/assign starters with positional scarcity.
    Uses selected categories with rate stats translated into counting impact.
    """
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
            components.append(zscore(series))

    if "AVG" in selected:
        mean_avg = float(np.nanmean(avg)) if len(avg) else 0.0
        components.append(zscore(pd.Series((avg - mean_avg) * ab, index=df.index)))
    if "OBP" in selected:
        mean_obp = float(np.nanmean(obp)) if len(obp) else 0.0
        components.append(zscore(pd.Series((obp - mean_obp) * obp_den, index=df.index)))
    if "SLG" in selected:
        mean_slg = float(np.nanmean(slg)) if len(slg) else 0.0
        components.append(zscore(pd.Series((slg - mean_slg) * ab, index=df.index)))
    if "OPS" in selected:
        mean_ops = float(np.nanmean(ops)) if len(ops) else 0.0
        components.append(zscore(pd.Series((ops - mean_ops) * ab, index=df.index)))

    if not components:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)

    w = components[0].copy()
    for component in components[1:]:
        w = w + component
    return w


def initial_pitcher_weight(df: pd.DataFrame, categories: Optional[List[str]] = None) -> pd.Series:
    """
    Rough first-pass weight for pitchers:
    counting stats + "runs prevented" (ERA) + "baserunners prevented" (WHIP),
    both scaled by IP to reflect volume.
    """
    df = df.copy()
    selected = {str(cat).strip().upper() for cat in (categories or list(PIT_CATS))}
    components: List[pd.Series] = []

    for cat in ("W", "K", "SV", "QS", "QA3", "SVH"):
        if cat in selected:
            components.append(zscore(df[cat]))

    if "ERA" in selected or "WHIP" in selected:
        ip_sum = float(df["IP"].sum())
        mean_era = float(9.0 * df["ER"].sum() / ip_sum) if ip_sum > 0 else float(df["ERA"].mean())
        mean_whip = float((df["H"].sum() + df["BB"].sum()) / ip_sum) if ip_sum > 0 else float(df["WHIP"].mean())
        if "ERA" in selected:
            df["ERA_surplus_ER"] = (mean_era - df["ERA"]) * df["IP"] / 9.0
            components.append(zscore(df["ERA_surplus_ER"]))
        if "WHIP" in selected:
            df["WHIP_surplus"] = (mean_whip - df["WHIP"]) * df["IP"]
            components.append(zscore(df["WHIP_surplus"]))

    if not components:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)

    w = components[0].copy()
    for component in components[1:]:
        w = w + component
    return w


# ----------------------------
# Team stat calculations (default 5x5)
# ----------------------------

def team_avg(H: float, AB: float) -> float:
    return float(H / AB) if AB > 0 else 0.0

def team_obp(H: float, BB: float, HBP: float, AB: float, SF: float) -> float:
    den = AB + BB + HBP + SF
    return float((H + BB + HBP) / den) if den > 0 else 0.0

def team_ops(H: float, BB: float, HBP: float, AB: float, SF: float, b2: float, b3: float, HR: float) -> float:
    obp = team_obp(H, BB, HBP, AB, SF)
    slg = float((H + b2 + 2.0 * b3 + 3.0 * HR) / AB) if AB > 0 else 0.0
    return float(obp + slg)

def team_era(ER: float, IP: float) -> float:
    return float(9.0 * ER / IP) if IP > 0 else float("nan")

def team_whip(H: float, BB: float, IP: float) -> float:
    return float((H + BB) / IP) if IP > 0 else float("nan")


COMMON_REVERSED_PITCH_CATS: Set[str] = {"ERA", "WHIP"}


def common_hit_category_totals(totals: Dict[str, float]) -> Dict[str, float]:
    return _common_math.common_hit_category_totals(totals)


def common_pitch_category_totals(totals: Dict[str, float]) -> Dict[str, float]:
    return _common_math.common_pitch_category_totals(totals)


def common_replacement_pitcher_rates(
    all_pit_df: pd.DataFrame,
    assigned_pit_df: pd.DataFrame,
    n_rep: int,
) -> Dict[str, float]:
    return _common_math.common_replacement_pitcher_rates(all_pit_df, assigned_pit_df, n_rep)


def common_apply_pitching_bounds(
    totals: Dict[str, float],
    lg: CommonDynastyRotoSettings,
    rep_rates: Optional[Dict[str, float]],
    *,
    fill_to_ip_max: bool = True,
    enforce_ip_min: bool = True,
) -> Dict[str, float]:
    return _common_math.common_apply_pitching_bounds(
        totals,
        lg,
        rep_rates,
        fill_to_ip_max=fill_to_ip_max,
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
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
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
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
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


# ----------------------------
# Monte Carlo SGP denominators
# ----------------------------

def _mean_adjacent_rank_gap(values: np.ndarray, *, ascending: bool) -> float:
    return _common_math._mean_adjacent_rank_gap(values, ascending=ascending)


def simulate_sgp_hit(
    assigned_hit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng: np.random.Generator,
    categories: Optional[List[str]] = None,
) -> Dict[str, float]:
    return _common_math.simulate_sgp_hit(assigned_hit, lg, rng, categories=categories)

def simulate_sgp_pit(
    assigned_pit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng: np.random.Generator,
    rep_rates: Optional[Dict[str, float]] = None,
    categories: Optional[List[str]] = None,
) -> Dict[str, float]:
    return _common_math.simulate_sgp_pit(
        assigned_pit,
        lg,
        rng,
        rep_rates=rep_rates,
        categories=categories,
    )


# ----------------------------
# Year context + player year values
# ----------------------------

def compute_year_context(year: int, bat: pd.DataFrame, pit: pd.DataFrame, lg: CommonDynastyRotoSettings, rng_seed: Optional[int] = None) -> dict:
    return _common_math.compute_year_context(year, bat, pit, lg, rng_seed=rng_seed)

def compute_year_player_values(ctx: dict, lg: CommonDynastyRotoSettings) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return _common_math.compute_year_player_values(ctx, lg)


def compute_replacement_baselines(
    ctx: dict,
    lg: CommonDynastyRotoSettings,
    rostered_players: Set[str],
    n_repl: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return _common_math.compute_replacement_baselines(
        ctx,
        lg,
        rostered_players=rostered_players,
        n_repl=n_repl,
    )


def compute_year_player_values_vs_replacement(
    ctx: dict,
    lg: CommonDynastyRotoSettings,
    repl_hit: pd.DataFrame,
    repl_pit: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return _common_math.compute_year_player_values_vs_replacement(
        ctx,
        lg,
        repl_hit=repl_hit,
        repl_pit=repl_pit,
    )


def combine_two_way(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame:
    return _common_math.combine_two_way(hit_vals, pit_vals, two_way)


# ----------------------------
# Dynasty aggregation + centering
# ----------------------------


# ----------------------------
# Dynasty aggregation utilities
# ----------------------------

def dynasty_keep_or_drop_value(values: List[float], years: List[int], discount: float) -> float:
    """Compute the optimal discounted value of owning a player with a drop option.

    At the start of each season you either:
      - **Keep** the player for that season (receiving that season's `values[i]`, which may be negative), or
      - **Drop** the player permanently and receive 0 from that season onward.

    Discounting is applied between seasons using `discount ** year_gap`, where
    `year_gap = years[i+1] - years[i]`.

    This implements the one-dimensional dynamic program:

        F[i] = max(0, values[i] + discount**(gap) * F[i+1])

    Returns the optimal value in "start-year" units (i.e., relative to `years[0]`).
    """
    if not years or not values:
        return 0.0
    if len(values) != len(years):
        raise ValueError("values and years must have the same length")
    if len(years) == 1:
        return float(max(values[0], 0.0))

    f_next = 0.0
    for i in range(len(years) - 1, -1, -1):
        v = float(values[i])
        if i == len(years) - 1:
            hold = v
        else:
            gap = int(years[i + 1]) - int(years[i])
            if gap < 0:
                raise ValueError("years must be increasing")
            hold = v + (discount ** gap) * f_next
        f_next = max(0.0, hold)

    return float(f_next)

def _infer_minor_eligibility_by_year(
    bat_df: pd.DataFrame,
    pit_df: pd.DataFrame,
    *,
    years: Optional[List[int]],
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


def infer_minor_eligible(bat: pd.DataFrame, pit: pd.DataFrame, lg: CommonDynastyRotoSettings, start_year: int) -> pd.DataFrame:
    return _minor_elig.infer_minor_eligible(bat, pit, lg, start_year)


def _non_vacant_player_names(df: Optional[pd.DataFrame]) -> Set[str]:
    return _minor_elig._non_vacant_player_names(df)


def _players_with_playing_time(bat_df: pd.DataFrame, pit_df: pd.DataFrame, years: List[int]) -> Set[str]:
    return _minor_elig._players_with_playing_time(bat_df, pit_df, years)


def _select_mlb_roster_with_active_floor(
    stash_sorted: pd.DataFrame,
    *,
    excluded_players: Set[str],
    total_mlb_slots: int,
    active_floor_names: Set[str],
) -> pd.DataFrame:
    return _minor_elig._select_mlb_roster_with_active_floor(
        stash_sorted,
        excluded_players=excluded_players,
        total_mlb_slots=total_mlb_slots,
        active_floor_names=active_floor_names,
    )


def _estimate_bench_negative_penalty(start_ctx: dict, lg: object) -> float:
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
    bench_stash_players: Set[str],
    n_teams: int,
    bench_slots: int,
) -> Dict[str, float]:
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
    can_bench_stash: bool,
    bench_negative_penalty: float,
) -> float:
    return _minor_elig._apply_negative_value_stash_rules(
        value,
        can_minor_stash=can_minor_stash,
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
) -> Optional[pd.DataFrame]:
    return _minor_elig.minor_eligibility_by_year_from_input(bat, pit)


def minor_eligibility_from_input(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
    start_year: int,
) -> Optional[pd.DataFrame]:
    return _minor_elig.minor_eligibility_from_input(bat, pit, start_year)


def _resolve_minor_eligibility_by_year(
    bat_df: pd.DataFrame,
    pit_df: pd.DataFrame,
    *,
    years: List[int],
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

def calculate_common_dynasty_values(
    excel_path: str,
    lg: CommonDynastyRotoSettings,
    start_year: Optional[int] = None,
    years: Optional[List[int]] = None,
    verbose: bool = True,
    return_details: bool = False,
    seed: int = 0,
):
    """Compatibility wrapper delegating to extracted common orchestration."""
    try:  # pragma: no branch
        from backend.valuation import common_orchestration as _orchestration
    except ImportError:  # pragma: no cover - direct script execution fallback
        from valuation import common_orchestration as _orchestration
    return _orchestration.calculate_common_dynasty_values(
        excel_path,
        lg,
        start_year=start_year,
        years=years,
        verbose=verbose,
        return_details=return_details,
        seed=seed,
    )
def _xlsx_apply_header_style(ws) -> None: return _xlsx_fmt._xlsx_apply_header_style(ws)
def _xlsx_set_freeze_filters_and_view(ws, freeze_panes: str, add_autofilter: bool = False) -> None: return _xlsx_fmt._xlsx_set_freeze_filters_and_view(ws, freeze_panes=freeze_panes, add_autofilter=add_autofilter)
def _xlsx_add_table(ws, table_name: str, style_name: str = "TableStyleMedium9") -> None: return _xlsx_fmt._xlsx_add_table(ws, table_name=table_name, style_name=style_name)
def _xlsx_set_column_widths(ws, df: pd.DataFrame, overrides: Optional[Dict[str, float]] = None, sample_rows: int = 1000, min_width: float = 8.0, max_width: float = 45.0) -> None: return _xlsx_fmt._xlsx_set_column_widths(ws, df, overrides=overrides, sample_rows=sample_rows, min_width=min_width, max_width=max_width)
def _xlsx_apply_number_formats(ws, df: pd.DataFrame, formats_by_col: Dict[str, str]) -> None: return _xlsx_fmt._xlsx_apply_number_formats(ws, df, formats_by_col)
def _xlsx_add_value_color_scale(ws, df: pd.DataFrame, col_name: str) -> None: return _xlsx_fmt._xlsx_add_value_color_scale(ws, df, col_name)
def _xlsx_format_player_values(ws, df: pd.DataFrame, table_name: str = "PlayerValuesTbl") -> None: return _xlsx_fmt._xlsx_format_player_values(ws, df, table_name=table_name)
def _xlsx_format_detail_sheet(ws, df: pd.DataFrame, *, table_name: str, is_pitch: bool) -> None: return _xlsx_fmt._xlsx_format_detail_sheet(ws, df, table_name=table_name, is_pitch=is_pitch)

def main() -> None:
    try:  # pragma: no branch
        from backend.valuation import cli as _cli
    except ImportError:  # pragma: no cover - direct script execution fallback
        from valuation import cli as _cli
    _cli.main()
if __name__ == "__main__":
    main()
