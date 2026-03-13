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
    from backend.valuation.credit_guards import (
        _apply_hitter_playing_time_reliability_guard as _apply_hitter_playing_time_reliability_guard,
    )
    from backend.valuation.credit_guards import (
        _apply_low_volume_non_ratio_positive_guard as _apply_low_volume_non_ratio_positive_guard,
    )
    from backend.valuation.credit_guards import (
        _apply_low_volume_ratio_guard as _apply_low_volume_ratio_guard,
    )
    from backend.valuation.credit_guards import (
        _apply_pitcher_playing_time_reliability_guard as _apply_pitcher_playing_time_reliability_guard,
    )
    from backend.valuation.credit_guards import (
        _coerce_non_negative_float as _coerce_non_negative_float,
    )
    from backend.valuation.credit_guards import (
        _low_volume_positive_credit_scale as _low_volume_positive_credit_scale,
    )
    from backend.valuation.credit_guards import (
        _positive_credit_scale as _positive_credit_scale,
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
    from backend.valuation.sgp_math import (
        _mean_adjacent_rank_gap as _mean_adjacent_rank_gap,
    )
    from backend.valuation.sgp_math import (
        _sgp_denominator_floor as _sgp_denominator_floor,
    )
    from backend.valuation.sgp_math import (
        _sgp_estimator_options as _sgp_estimator_options,
    )
    from backend.valuation.sgp_math import (
        simulate_sgp_hit as simulate_sgp_hit,
    )
    from backend.valuation.sgp_math import (
        simulate_sgp_pit as simulate_sgp_pit,
    )
    from backend.valuation.team_stats import (
        _team_avg as _team_avg,
    )
    from backend.valuation.team_stats import (
        _team_era as _team_era,
    )
    from backend.valuation.team_stats import (
        _team_obp as _team_obp,
    )
    from backend.valuation.team_stats import (
        _team_whip as _team_whip,
    )
    from backend.valuation.team_stats import (
        common_apply_pitching_bounds as common_apply_pitching_bounds,
    )
    from backend.valuation.team_stats import (
        common_hit_category_totals as common_hit_category_totals,
    )
    from backend.valuation.team_stats import (
        common_pitch_category_totals as common_pitch_category_totals,
    )
    from backend.valuation.team_stats import (
        common_replacement_pitcher_rates as common_replacement_pitcher_rates,
    )
except ImportError:
    from valuation.assignment import (  # type: ignore[no-redef]
        assign_players_to_slots_with_vacancy_fill,
        build_team_slot_template,
        expand_slot_counts,
    )
    from valuation.credit_guards import (  # type: ignore[no-redef]
        _apply_hitter_playing_time_reliability_guard as _apply_hitter_playing_time_reliability_guard,
    )
    from valuation.credit_guards import (
        _apply_low_volume_non_ratio_positive_guard as _apply_low_volume_non_ratio_positive_guard,
    )
    from valuation.credit_guards import (
        _apply_low_volume_ratio_guard as _apply_low_volume_ratio_guard,
    )
    from valuation.credit_guards import (
        _apply_pitcher_playing_time_reliability_guard as _apply_pitcher_playing_time_reliability_guard,
    )
    from valuation.credit_guards import (
        _coerce_non_negative_float as _coerce_non_negative_float,
    )
    from valuation.credit_guards import (
        _low_volume_positive_credit_scale as _low_volume_positive_credit_scale,
    )
    from valuation.credit_guards import (
        _positive_credit_scale as _positive_credit_scale,
    )
    from valuation.models import (  # type: ignore[no-redef]
        HIT_CATS,
        HIT_COMPONENT_COLS,
        PIT_CATS,
        PIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )
    from valuation.positions import (  # type: ignore[no-redef]
        eligible_hit_slots,
        eligible_pit_slots,
        parse_hit_positions,
        parse_pit_positions,
    )
    from valuation.sgp_math import (  # type: ignore[no-redef]
        _mean_adjacent_rank_gap as _mean_adjacent_rank_gap,
    )
    from valuation.sgp_math import (
        _sgp_denominator_floor as _sgp_denominator_floor,
    )
    from valuation.sgp_math import (
        _sgp_estimator_options as _sgp_estimator_options,
    )
    from valuation.sgp_math import (
        simulate_sgp_hit as simulate_sgp_hit,
    )
    from valuation.sgp_math import (
        simulate_sgp_pit as simulate_sgp_pit,
    )
    from valuation.team_stats import (  # type: ignore[no-redef]
        _team_avg as _team_avg,
    )
    from valuation.team_stats import (
        _team_era as _team_era,
    )
    from valuation.team_stats import (
        _team_obp as _team_obp,
    )
    from valuation.team_stats import (
        _team_whip as _team_whip,
    )
    from valuation.team_stats import (
        common_apply_pitching_bounds as common_apply_pitching_bounds,
    )
    from valuation.team_stats import (
        common_hit_category_totals as common_hit_category_totals,
    )
    from valuation.team_stats import (
        common_pitch_category_totals as common_pitch_category_totals,
    )
    from valuation.team_stats import (
        common_replacement_pitcher_rates as common_replacement_pitcher_rates,
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
        raise ValueError(f"Year {year}: no hitters with AB > 0 after filtering. Check Year values and AB projections.")
    if pit_play.empty:
        raise ValueError(f"Year {year}: no pitchers with IP > 0 after filtering. Check Year values and IP projections.")

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
        best_stat_sgps: Dict[str, float] = {}

        for slot in slots:
            if slot not in baseline_hit.index:
                continue
            b = baseline_hit.loc[slot]

            new_tot = base_hit_tot.copy()
            for col in HIT_COMPONENT_COLS:
                new_tot[col] = new_tot[col] - b[col] + float(row.get(col, 0.0))

            new_hit_cats = common_hit_category_totals({col: float(new_tot[col]) for col in HIT_COMPONENT_COLS})
            delta = {cat: float(new_hit_cats.get(cat, 0.0) - base_hit_cats.get(cat, 0.0)) for cat in hit_categories}
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
            stat_sgps: Dict[str, float] = {}
            for c in hit_categories:
                denom = float(sgp_hit[c])
                sgp_c = (delta[c] / denom) if denom else 0.0
                val += sgp_c
                stat_sgps[c] = sgp_c

            if val > best_val:
                best_val = val
                best_slot = slot
                best_stat_sgps = stat_sgps

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
                **{f"SGP_{cat}": best_stat_sgps.get(cat, 0.0) for cat in hit_categories},
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
        best_stat_sgps: Dict[str, float] = {}

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
            stat_sgps: Dict[str, float] = {}
            for c in pit_categories:
                denom = float(sgp_pit[c])
                sgp_c = (delta[c] / denom) if denom else 0.0
                val += sgp_c
                stat_sgps[c] = sgp_c

            if val > best_val:
                best_val = val
                best_slot = slot
                best_stat_sgps = stat_sgps

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
                **{f"SGP_{cat}": best_stat_sgps.get(cat, 0.0) for cat in pit_categories},
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
        cand = fa_hit[fa_hit["elig"].apply(lambda s: slot in s)].sort_values("weight", ascending=False).head(n_repl)
        repl = baseline_hit_avg.loc[slot] if len(cand) == 0 else cand[HIT_COMPONENT_COLS].mean()
        row = {c: float(repl.get(c, 0.0)) for c in HIT_COMPONENT_COLS}
        row["AssignedSlot"] = slot
        repl_hit_rows.append(row)

    repl_hit = pd.DataFrame(repl_hit_rows).set_index("AssignedSlot")

    repl_pit_rows: List[dict] = []
    for slot in baseline_pit_avg.index:
        cand = fa_pit[fa_pit["elig"].apply(lambda s: slot in s)].sort_values("weight", ascending=False).head(n_repl)
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
        best_stat_sgps: Dict[str, float] = {}

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
            delta = {cat: float(new_hit_cats.get(cat, 0.0) - base_hit_cats.get(cat, 0.0)) for cat in hit_categories}

            val = 0.0
            stat_sgps: Dict[str, float] = {}
            for c in hit_categories:
                denom = float(sgp_hit[c])
                sgp_c = (delta[c] / denom) if denom else 0.0
                val += sgp_c
                stat_sgps[c] = sgp_c

            if val > best_val:
                best_val = val
                best_slot = slot
                best_stat_sgps = stat_sgps

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
                **{f"SGP_{cat}": best_stat_sgps.get(cat, 0.0) for cat in hit_categories},
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
        best_stat_sgps: Dict[str, float] = {}

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
            stat_sgps: Dict[str, float] = {}
            for c in pit_categories:
                denom = float(sgp_pit[c])
                sgp_c = (delta[c] / denom) if denom else 0.0
                val += sgp_c
                stat_sgps[c] = sgp_c

            if val > best_val:
                best_val = val
                best_slot = slot
                best_stat_sgps = stat_sgps

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
                **{f"SGP_{cat}": best_stat_sgps.get(cat, 0.0) for cat in pit_categories},
            }
        )

    pit_vals = pd.DataFrame(pit_rows)
    return hit_vals, pit_vals


def combine_two_way(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame:
    hit_sgp_cols = [c for c in hit_vals.columns if c.startswith("SGP_")]
    pit_sgp_cols = [c for c in pit_vals.columns if c.startswith("SGP_")]
    hit_merge_cols = ["Player", "Year", "YearValue", "BestSlot", "Team", "Age", "Pos"] + hit_sgp_cols
    pit_merge_cols = ["Player", "Year", "YearValue", "BestSlot", "Team", "Age", "Pos"] + pit_sgp_cols
    merged = pd.merge(
        hit_vals[[c for c in hit_merge_cols if c in hit_vals.columns]],
        pit_vals[[c for c in pit_merge_cols if c in pit_vals.columns]],
        on=["Player", "Year"],
        how="outer",
        suffixes=("_hit", "_pit"),
    )

    hit_sgp_cat_set = {c[4:] for c in hit_sgp_cols}
    pit_sgp_cat_set = {c[4:] for c in pit_sgp_cols}
    all_sgp_cats = sorted(hit_sgp_cat_set | pit_sgp_cat_set)

    def _get_sgp(r: pd.Series, cat: str, side: str) -> float:
        """Get SGP value for a category from the merged row, handling suffix logic."""
        # If the cat exists on both sides, pandas adds _hit/_pit suffixes
        suffixed = f"SGP_{cat}_{side}"
        if suffixed in r.index:
            v = r[suffixed]
            return float(v) if v is not None and not pd.isna(v) else 0.0
        # If the cat exists only on one side, pandas keeps it unsuffixed
        unsuffixed = f"SGP_{cat}"
        if unsuffixed in r.index:
            # Only return the value if this cat belongs to the requested side
            if (side == "hit" and cat in hit_sgp_cat_set) or (side == "pit" and cat in pit_sgp_cat_set):
                v = r[unsuffixed]
                return float(v) if v is not None and not pd.isna(v) else 0.0
        return 0.0

    out_vals = []
    out_slots = []
    out_sgps: Dict[str, List[float]] = {cat: [] for cat in all_sgp_cats}

    for _, r in merged.iterrows():
        hv = r.get("YearValue_hit")
        pv = r.get("YearValue_pit")

        if pd.isna(hv) and pd.isna(pv):
            out_vals.append(np.nan)
            out_slots.append(None)
            for cat in all_sgp_cats:
                out_sgps[cat].append(0.0)
            continue
        if pd.isna(hv):
            out_vals.append(float(pv))
            out_slots.append(r.get("BestSlot_pit"))
            for cat in all_sgp_cats:
                out_sgps[cat].append(_get_sgp(r, cat, "pit"))
            continue
        if pd.isna(pv):
            out_vals.append(float(hv))
            out_slots.append(r.get("BestSlot_hit"))
            for cat in all_sgp_cats:
                out_sgps[cat].append(_get_sgp(r, cat, "hit"))
            continue

        hv = float(hv)
        pv = float(pv)

        if two_way == "sum":
            out_vals.append(hv + pv)
            out_slots.append(f"{r.get('BestSlot_hit')}+{r.get('BestSlot_pit')}")
            for cat in all_sgp_cats:
                out_sgps[cat].append(_get_sgp(r, cat, "hit") + _get_sgp(r, cat, "pit"))
        else:  # "max"
            if hv >= pv:
                out_vals.append(hv)
                out_slots.append(r.get("BestSlot_hit"))
                for cat in all_sgp_cats:
                    out_sgps[cat].append(_get_sgp(r, cat, "hit"))
            else:
                out_vals.append(pv)
                out_slots.append(r.get("BestSlot_pit"))
                for cat in all_sgp_cats:
                    out_sgps[cat].append(_get_sgp(r, cat, "pit"))

    merged["YearValue"] = out_vals
    merged["BestSlot"] = out_slots
    merged["Team"] = merged["Team_hit"].combine_first(merged["Team_pit"])
    merged["Pos"] = merged["Pos_hit"].combine_first(merged["Pos_pit"])
    merged["Age"] = merged["Age_hit"].combine_first(merged["Age_pit"])
    for cat in all_sgp_cats:
        merged[f"SGP_{cat}"] = out_sgps[cat]

    base_cols = ["Player", "Year", "YearValue", "BestSlot", "Team", "Pos", "Age"]
    return merged[base_cols + [f"SGP_{cat}" for cat in all_sgp_cats]]


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
