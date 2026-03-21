"""Replacement-level baseline and value-vs-replacement computations."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

try:
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
    from backend.valuation.models import (
        HIT_COMPONENT_COLS,
        PIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )
    from backend.valuation.positions import (
        eligible_hit_slots,
        eligible_pit_slots,
        parse_hit_positions,
        parse_pit_positions,
    )
    from backend.valuation.team_stats import (
        common_apply_pitching_bounds,
        common_hit_category_totals,
        common_pitch_category_totals,
    )
    from backend.valuation.weighting import (
        _initial_hitter_weight,
        _initial_pitcher_weight,
    )
except ImportError:
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
    from valuation.models import (  # type: ignore[no-redef]
        HIT_COMPONENT_COLS,
        PIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )
    from valuation.positions import (  # type: ignore[no-redef]
        eligible_hit_slots,
        eligible_pit_slots,
        parse_hit_positions,
        parse_pit_positions,
    )
    from valuation.team_stats import (  # type: ignore[no-redef]
        common_apply_pitching_bounds,
        common_hit_category_totals,
        common_pitch_category_totals,
    )
    from valuation.weighting import (  # type: ignore[no-redef]
        _initial_hitter_weight,
        _initial_pitcher_weight,
    )

COMMON_REVERSED_PITCH_CATS: Set[str] = {"ERA", "WHIP"}


def _active_common_hit_categories(lg: CommonDynastyRotoSettings) -> List[str]:
    try:
        from backend.valuation.models import HIT_CATS
    except ImportError:
        from valuation.models import HIT_CATS  # type: ignore[no-redef]
    configured = getattr(lg, "hitter_categories", None)
    if not configured:
        return list(HIT_CATS)
    wanted = {str(cat).strip().upper() for cat in configured if str(cat).strip()}
    selected = [cat for cat in HIT_CATS if cat.upper() in wanted]
    return selected or list(HIT_CATS)


def _active_common_pitch_categories(lg: CommonDynastyRotoSettings) -> List[str]:
    try:
        from backend.valuation.models import PIT_CATS
    except ImportError:
        from valuation.models import PIT_CATS  # type: ignore[no-redef]
    configured = getattr(lg, "pitcher_categories", None)
    if not configured:
        return list(PIT_CATS)
    wanted = {str(cat).strip().upper() for cat in configured if str(cat).strip()}
    selected = [cat for cat in PIT_CATS if cat.upper() in wanted]
    return selected or list(PIT_CATS)


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
        hit_slot_mask = fa_hit["elig"].apply(lambda s: slot in s).astype(bool)
        cand = fa_hit.loc[hit_slot_mask].sort_values("weight", ascending=False).head(n_repl)
        repl = baseline_hit_avg.loc[slot] if len(cand) == 0 else cand[HIT_COMPONENT_COLS].mean()
        row = {c: float(repl.get(c, 0.0)) for c in HIT_COMPONENT_COLS}
        row["AssignedSlot"] = slot
        repl_hit_rows.append(row)

    repl_hit = pd.DataFrame(repl_hit_rows).set_index("AssignedSlot")

    repl_pit_rows: List[dict] = []
    for slot in baseline_pit_avg.index:
        pit_slot_mask = fa_pit["elig"].apply(lambda s: slot in s).astype(bool)
        cand = fa_pit.loc[pit_slot_mask].sort_values("weight", ascending=False).head(n_repl)
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
            if bool(getattr(lg, "enable_playing_time_reliability", False)):
                _apply_hitter_playing_time_reliability_guard(
                    delta,
                    hit_categories=hit_categories,
                    hitter_ab=_coerce_non_negative_float(row.get("AB", 0.0)),
                    slot_ab_reference=_coerce_non_negative_float(b_avg.get("AB", 0.0)),
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
