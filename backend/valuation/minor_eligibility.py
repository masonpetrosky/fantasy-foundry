"""Minor-eligibility and bench-stash helpers for dynasty valuation."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd

try:
    from backend.valuation.models import CommonDynastyRotoSettings
except ImportError:
    from valuation.models import CommonDynastyRotoSettings  # type: ignore[no-redef]

# Bench-stash penalty curve defaults:
# - first stash round per team should still carry a small cost
# - later rounds are progressively more punitive
BENCH_STASH_MIN_PENALTY = 0.10
BENCH_STASH_MAX_PENALTY = 0.85
BENCH_STASH_PENALTY_GAMMA = 1.35


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
    """Infer year-level minor eligibility from projected MLB usage and age.

    The rule is intentionally monotonic: once a player is inferred to lose minor
    eligibility, they cannot regain it in later years.
    """

    def _per_side(df: pd.DataFrame, usage_col: str) -> pd.DataFrame:
        if df.empty or "Player" not in df.columns or "Year" not in df.columns:
            return pd.DataFrame(columns=["Player", "Year", usage_col, "Age"])

        cols = ["Player", "Year", usage_col]
        if "Age" in df.columns:
            cols.append("Age")
        side = df[cols].copy()
        side["Year"] = pd.to_numeric(side["Year"], errors="coerce")
        side = side.dropna(subset=["Player", "Year"])
        if side.empty:
            return pd.DataFrame(columns=["Player", "Year", usage_col, "Age"])

        side["Year"] = side["Year"].astype(int)
        side[usage_col] = pd.to_numeric(side[usage_col], errors="coerce").fillna(0.0).clip(lower=0.0)
        if "Age" not in side.columns:
            side["Age"] = np.nan
        else:
            side["Age"] = pd.to_numeric(side["Age"], errors="coerce")

        return side.groupby(["Player", "Year"], as_index=False).agg({usage_col: "max", "Age": "min"})

    bat_year = _per_side(bat_df, "AB")
    pit_year = _per_side(pit_df, "IP")
    merged = bat_year.merge(pit_year, on=["Player", "Year"], how="outer", suffixes=("_hit", "_pit"))
    if merged.empty:
        return pd.DataFrame(columns=["Player", "Year", "minor_eligible"])

    years_set = {int(y) for y in years} if years else None
    if years_set is not None:
        merged = merged[merged["Year"].isin(years_set)].copy()
    if merged.empty:
        return pd.DataFrame(columns=["Player", "Year", "minor_eligible"])

    merged["AB"] = pd.to_numeric(merged["AB"], errors="coerce").fillna(0.0).clip(lower=0.0)
    merged["IP"] = pd.to_numeric(merged["IP"], errors="coerce").fillna(0.0).clip(lower=0.0)
    age_hit = pd.to_numeric(merged["Age_hit"], errors="coerce")
    age_pit = pd.to_numeric(merged["Age_pit"], errors="coerce")
    merged["Age"] = age_hit.combine_first(age_pit)
    merged = merged.sort_values(["Player", "Year"]).reset_index(drop=True)

    merged["cum_AB"] = merged.groupby("Player", sort=False)["AB"].cumsum()
    merged["cum_IP"] = merged.groupby("Player", sort=False)["IP"].cumsum()

    raw_minor = (
        ((merged["cum_AB"] > 0.0) & (merged["cum_AB"] <= float(hitter_usage_max)) & (merged["Age"] <= float(hitter_age_max)))
        | ((merged["cum_IP"] > 0.0) & (merged["cum_IP"] <= float(pitcher_usage_max)) & (merged["Age"] <= float(pitcher_age_max)))
    )
    merged["minor_eligible_raw"] = _fillna_bool(raw_minor.astype("boolean"), default=False)

    def _enforce_once_lost(series: pd.Series) -> pd.Series:
        had_eligibility = False
        lost_eligibility = False
        out: List[bool] = []
        for value in series.tolist():
            eligible_now = bool(value)
            if lost_eligibility:
                out.append(False)
                continue
            if had_eligibility and not eligible_now:
                lost_eligibility = True
                out.append(False)
                continue
            if eligible_now:
                had_eligibility = True
            out.append(eligible_now)
        return pd.Series(out, index=series.index, dtype=bool)

    merged["minor_eligible"] = (
        merged.groupby("Player", sort=False)["minor_eligible_raw"].apply(_enforce_once_lost).reset_index(level=0, drop=True)
    )
    return merged[["Player", "Year", "minor_eligible"]]


def infer_minor_eligible(bat: pd.DataFrame, pit: pd.DataFrame, lg: CommonDynastyRotoSettings, start_year: int) -> pd.DataFrame:
    """Best-effort start-year minor eligibility inference from projections."""
    inferred = _infer_minor_eligibility_by_year(
        bat,
        pit,
        years=[start_year],
        hitter_usage_max=lg.minor_ab_max,
        pitcher_usage_max=lg.minor_ip_max,
        hitter_age_max=lg.minor_age_max_hit,
        pitcher_age_max=lg.minor_age_max_pit,
    )
    out = inferred[inferred["Year"] == int(start_year)][["Player", "minor_eligible"]].copy()
    if out.empty:
        return pd.DataFrame(columns=["Player", "minor_eligible"])
    return out.groupby("Player", as_index=False)["minor_eligible"].max()


def _non_vacant_player_names(df: Optional[pd.DataFrame]) -> Set[str]:
    """Collect non-placeholder player names from an assignment table."""
    if df is None or df.empty or "Player" not in df.columns:
        return set()
    names = df["Player"].dropna().astype(str)
    return {name for name in names if name and not name.startswith("__VACANT_")}


def _players_with_playing_time(bat_df: pd.DataFrame, pit_df: pd.DataFrame, years: List[int]) -> Set[str]:
    """Return players with projected MLB playing time in the valuation window."""
    years_set = {int(y) for y in years}
    players: Set[str] = set()

    if {"Player", "Year", "AB"}.issubset(bat_df.columns):
        hitters = bat_df.loc[(bat_df["Year"].isin(years_set)) & (bat_df["AB"] > 0), "Player"]
        players.update(hitters.dropna().astype(str))

    if {"Player", "Year", "IP"}.issubset(pit_df.columns):
        pitchers = pit_df.loc[(pit_df["Year"].isin(years_set)) & (pit_df["IP"] > 0), "Player"]
        players.update(pitchers.dropna().astype(str))

    return players


def _select_mlb_roster_with_active_floor(
    stash_sorted: pd.DataFrame,
    *,
    excluded_players: Set[str],
    total_mlb_slots: int,
    active_floor_names: Set[str],
    mlb_playing_time_players: Optional[Set[str]] = None,
) -> pd.DataFrame:
    """Pick MLB rostered players while guaranteeing active-floor names when possible."""
    remaining = stash_sorted[~stash_sorted["Player"].isin(excluded_players)].copy()
    if total_mlb_slots <= 0 or remaining.empty:
        return remaining.iloc[0:0].copy()

    floor = remaining[remaining["Player"].isin(active_floor_names)].copy()
    floor = floor.sort_values("StashScore", ascending=False)
    if len(floor) > total_mlb_slots:
        floor = floor.head(total_mlb_slots).copy()

    fill_needed = max(total_mlb_slots - len(floor), 0)
    if fill_needed == 0:
        return floor.reset_index(drop=True)

    selected = floor.reset_index(drop=True)
    selected_names = set(selected["Player"]) if not selected.empty else set()

    preferred_players = {str(player) for player in (mlb_playing_time_players or set()) if str(player)}
    if preferred_players:
        preferred_fill = remaining[
            (~remaining["Player"].isin(selected_names))
            & (remaining["Player"].isin(preferred_players))
        ].head(fill_needed).copy()
        if not preferred_fill.empty:
            selected = pd.concat([selected, preferred_fill], ignore_index=True)
            selected_names = set(selected["Player"])

    remaining_needed = max(total_mlb_slots - len(selected), 0)
    if remaining_needed <= 0:
        return selected.reset_index(drop=True)

    fill = remaining[~remaining["Player"].isin(selected_names)].head(remaining_needed).copy()
    return pd.concat([selected, fill], ignore_index=True)


def _estimate_bench_negative_penalty(start_ctx: dict, lg: object) -> float:
    """Estimate marginal active-slot opportunity cost for one bench stash slot.

    Returns a factor in [0, 1] used to scale negative year values for players
    that can be stashed on the bench instead of occupying an active lineup spot.
    The openness heuristic is derived from hitter usage when available.
    """
    bench_slots = int(getattr(lg, "bench_slots", 0) or 0)
    if bench_slots <= 0:
        return 1.0

    hitter_slots = getattr(lg, "hitter_slots", {}) or {}
    active_hit_slots_per_team = int(sum(max(int(v), 0) for v in hitter_slots.values()))
    if active_hit_slots_per_team <= 0:
        return 1.0

    default_open_fraction = 0.15
    open_fraction = default_open_fraction

    assigned_hit = start_ctx.get("assigned_hit")
    if isinstance(assigned_hit, pd.DataFrame) and not assigned_hit.empty and "G" in assigned_hit.columns:
        non_vacant = assigned_hit[~assigned_hit["Player"].astype(str).str.startswith("__VACANT_")].copy()
        if not non_vacant.empty:
            g_total = float(non_vacant["G"].fillna(0.0).clip(lower=0.0).sum())
            max_games = float(max(len(non_vacant) * 162, 1))
            modeled_open = (max_games - g_total) / max_games
            open_fraction = float(np.clip(modeled_open, 0.0, 1.0))

    # Opportunity cost of one stash slot:
    # 1) Estimate total open hitter slot-seasons across a team.
    # 2) Assume remaining bench slots can absorb those open starts first.
    # 3) Only uncovered open starts create a real stash penalty.
    open_slot_seasons = open_fraction * float(active_hit_slots_per_team)
    remaining_bench_slots = float(max(bench_slots - 1, 0))
    uncovered_open_slots = max(open_slot_seasons - remaining_bench_slots, 0.0)
    return float(np.clip(uncovered_open_slots, 0.0, 1.0))


def _bench_stash_round_penalty(
    round_number: int,
    *,
    bench_slots: int,
    min_penalty: float = BENCH_STASH_MIN_PENALTY,
    max_penalty: float = BENCH_STASH_MAX_PENALTY,
    gamma: float = BENCH_STASH_PENALTY_GAMMA,
) -> float:
    """Penalty factor for a stash round (1-based), clipped to [0, 1]."""
    total_bench_slots = int(max(bench_slots, 0))
    if total_bench_slots <= 0:
        return 1.0

    round_num = max(int(round_number), 1)
    if round_num > total_bench_slots:
        return 1.0

    lo = float(np.clip(min_penalty, 0.0, 1.0))
    hi = float(np.clip(max_penalty, lo, 1.0))
    shape = float(max(gamma, 1e-9))

    if total_bench_slots == 1:
        return hi

    x = float(round_num - 1) / float(total_bench_slots - 1)
    penalty = lo + (hi - lo) * (x ** shape)
    return float(np.clip(penalty, 0.0, 1.0))


def _build_bench_stash_penalty_map(
    stash_sorted: pd.DataFrame,
    *,
    bench_stash_players: Set[str],
    n_teams: int,
    bench_slots: int,
) -> Dict[str, float]:
    """Assign player-specific bench penalties by stash round across teams."""
    if stash_sorted.empty or not bench_stash_players:
        return {}

    team_count = int(max(n_teams, 1))
    penalty_map: Dict[str, float] = {}
    stash_rank = 0

    for player in stash_sorted.get("Player", pd.Series(dtype=object)).dropna().astype(str).tolist():
        if player not in bench_stash_players or player in penalty_map:
            continue
        round_number = 1 + (stash_rank // team_count)
        penalty_map[player] = _bench_stash_round_penalty(round_number, bench_slots=bench_slots)
        stash_rank += 1

    return penalty_map


def _apply_negative_value_stash_rules(
    value: float,
    *,
    can_minor_stash: bool,
    can_ir_stash: bool = False,
    ir_negative_penalty: float = 1.0,
    can_bench_stash: bool,
    bench_negative_penalty: float,
) -> float:
    """Apply stash rules to negative year values before keep/drop aggregation."""
    if value >= 0.0:
        return float(value)
    if can_minor_stash:
        return 0.0
    if can_ir_stash:
        return float(value) * float(np.clip(ir_negative_penalty, 0.0, 1.0))
    if can_bench_stash:
        return float(value) * float(np.clip(bench_negative_penalty, 0.0, 1.0))
    return float(value)


def _fillna_bool(series: pd.Series, default: bool = False) -> pd.Series:
    """
    Coerce a Series to boolean and fill missing values without relying on pandas'
    deprecated silent downcasting behavior (avoids FutureWarning on .fillna/.ffill/.bfill).
    """
    # Use pandas' nullable BooleanDtype to handle NA safely, then convert to plain bool.
    return series.astype("boolean").fillna(default).astype(bool)


def _normalize_minor_eligibility(series: pd.Series) -> pd.Series:
    def _coerce(value: object) -> Optional[bool]:
        if pd.isna(value):
            return None
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if isinstance(value, (int, float, np.integer, np.floating)):
            return bool(value)
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"y", "yes", "true", "t", "1"}:
                return True
            if cleaned in {"n", "no", "false", "f", "0", ""}:
                return False
            coerced = pd.to_numeric(cleaned, errors="coerce")
            if not pd.isna(coerced):
                return bool(coerced)
        return None

    return series.apply(_coerce)


def minor_eligibility_by_year_from_input(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
) -> Optional[pd.DataFrame]:
    """Parse explicit minor-eligibility flags from input at Player/Year granularity."""
    candidates = {"minor", "minor_eligible", "minors_eligible", "minor_eligibility", "minors_eligibility", "minoreligible"}

    def _extract(df: pd.DataFrame) -> Optional[pd.DataFrame]:
        if df.empty or "Player" not in df.columns or "Year" not in df.columns:
            return None

        col_map = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
        matched = [c for c, norm in col_map.items() if norm in candidates or ("minor" in norm and "elig" in norm)]
        if not matched:
            return None

        col = matched[0]
        subset = df[["Player", "Year", col]].copy()
        subset["Year"] = pd.to_numeric(subset["Year"], errors="coerce")
        subset["minor_eligible"] = _normalize_minor_eligibility(subset[col])
        subset = subset.drop(columns=[col]).dropna(subset=["Player", "Year", "minor_eligible"])
        if subset.empty:
            return None

        subset["Year"] = subset["Year"].astype(int)
        subset["minor_score"] = subset["minor_eligible"].map({True: 2, False: 1}).astype(int)
        grouped = subset.groupby(["Player", "Year"], as_index=False)["minor_score"].max()
        grouped["minor_eligible"] = grouped["minor_score"] >= 2
        return grouped[["Player", "Year", "minor_eligible"]]

    parts = [part for part in (_extract(bat), _extract(pit)) if part is not None]
    if not parts:
        return None

    merged = pd.concat(parts, ignore_index=True)
    merged["minor_score"] = merged["minor_eligible"].map({True: 2, False: 1}).astype(int)
    merged = merged.groupby(["Player", "Year"], as_index=False)["minor_score"].max()
    merged["minor_eligible"] = merged["minor_score"] >= 2
    return merged[["Player", "Year", "minor_eligible"]]


def minor_eligibility_from_input(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
    start_year: int,
) -> Optional[pd.DataFrame]:
    """Backward-compatible start-year view of explicit minor eligibility."""
    by_year = minor_eligibility_by_year_from_input(bat, pit)
    if by_year is None or by_year.empty:
        return None

    subset = by_year[by_year["Year"] == int(start_year)][["Player", "minor_eligible"]].copy()
    if subset.empty:
        return None
    return subset.groupby("Player", as_index=False)["minor_eligible"].max()


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
    """Build Player/Year minor eligibility using input flags first, inference fallback."""
    years_set = {int(y) for y in years}

    inferred = _infer_minor_eligibility_by_year(
        bat_df,
        pit_df,
        years=years,
        hitter_usage_max=hitter_usage_max,
        pitcher_usage_max=pitcher_usage_max,
        hitter_age_max=hitter_age_max,
        pitcher_age_max=pitcher_age_max,
    )
    explicit = minor_eligibility_by_year_from_input(bat_df, pit_df)

    if explicit is None or explicit.empty:
        out = inferred.copy()
    else:
        merged = inferred.merge(explicit, on=["Player", "Year"], how="outer", suffixes=("_infer", "_input"))
        # Prefer explicit input flags; fall back to inferred values when explicit is missing.
        input_flags = merged["minor_eligible_input"]
        inferred_flags = merged["minor_eligible_infer"]
        merged["minor_eligible"] = input_flags.where(input_flags.notna(), inferred_flags)
        out = merged[["Player", "Year", "minor_eligible"]].copy()

    if out.empty:
        return pd.DataFrame(columns=["Player", "Year", "minor_eligible"])

    out = out[out["Year"].isin(years_set)].copy()
    if out.empty:
        return pd.DataFrame(columns=["Player", "Year", "minor_eligible"])
    out["minor_eligible"] = _fillna_bool(out["minor_eligible"])
    return out.groupby(["Player", "Year"], as_index=False)["minor_eligible"].max()


__all__ = [
    "BENCH_STASH_MIN_PENALTY",
    "BENCH_STASH_MAX_PENALTY",
    "BENCH_STASH_PENALTY_GAMMA",
    "_infer_minor_eligibility_by_year",
    "infer_minor_eligible",
    "_non_vacant_player_names",
    "_players_with_playing_time",
    "_select_mlb_roster_with_active_floor",
    "_estimate_bench_negative_penalty",
    "_bench_stash_round_penalty",
    "_build_bench_stash_penalty_map",
    "_apply_negative_value_stash_rules",
    "_fillna_bool",
    "_normalize_minor_eligibility",
    "minor_eligibility_by_year_from_input",
    "minor_eligibility_from_input",
    "_resolve_minor_eligibility_by_year",
]
