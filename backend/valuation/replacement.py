"""Replacement-level baseline and value-vs-replacement computations."""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional, Set, SupportsFloat, SupportsIndex, Tuple, cast

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
    from backend.valuation.credit_guards import (
        _positive_credit_scale as _positive_credit_scale,
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
    from backend.valuation.year_context import (
        CommonYearContextLike,
        context_optional_value,
        context_value,
    )
except ImportError:
    from valuation.credit_guards import (  # type: ignore[no-redef]
        _apply_hitter_playing_time_reliability_guard as _apply_hitter_playing_time_reliability_guard,
    )
    from valuation.credit_guards import (  # type: ignore[no-redef]
        _apply_low_volume_non_ratio_positive_guard as _apply_low_volume_non_ratio_positive_guard,
    )
    from valuation.credit_guards import (  # type: ignore[no-redef]
        _apply_low_volume_ratio_guard as _apply_low_volume_ratio_guard,
    )
    from valuation.credit_guards import (  # type: ignore[no-redef]
        _apply_pitcher_playing_time_reliability_guard as _apply_pitcher_playing_time_reliability_guard,
    )
    from valuation.credit_guards import (  # type: ignore[no-redef]
        _coerce_non_negative_float as _coerce_non_negative_float,
    )
    from valuation.credit_guards import (  # type: ignore[no-redef]
        _positive_credit_scale as _positive_credit_scale,
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
    from valuation.year_context import (  # type: ignore[no-redef]
        CommonYearContextLike,
        context_optional_value,
        context_value,
    )

COMMON_REVERSED_PITCH_CATS: Set[str] = {"ERA", "WHIP"}
REPLACEMENT_DEPTH_MODES: Set[str] = {"flat", "half_depth", "full_depth", "blended_depth"}
DEPTH_AWARE_REPLACEMENT_SLOTS: Set[str] = {"OF", "P"}


def _round_float_map(values: dict[str, float], *, digits: int = 4) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in values.items():
        try:
            out[str(key)] = round(float(value), digits)
        except (TypeError, ValueError):
            continue
    return out


def _coerce_float(value: object) -> float | None:
    if isinstance(value, (str, bytes, bytearray, SupportsFloat, SupportsIndex)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None


def _round_component_map(values: Mapping[str, object], *, digits: int = 4) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, value in values.items():
        candidate = _coerce_float(value)
        if candidate is None:
            continue
        out[str(key)] = round(candidate, digits)
    return out


def _reference_summary(
    *,
    slot: str,
    row: pd.Series,
    component_cols: list[str],
) -> dict[str, Any]:
    components = {col: float(row.get(col, 0.0)) for col in component_cols}
    volume = {
        "ab": round(float(components.get("AB", 0.0)), 4),
        "ip": round(float(components.get("IP", 0.0)), 4),
    }
    return {
        "slot": str(slot),
        "replacement_pool_depth": int(row.get("ReplacementPoolDepth", 0) or 0),
        "replacement_depth_mode": str(row.get("ReplacementDepthMode") or "").strip() or "flat",
        "replacement_depth_blend_alpha": (
            round(float(row.get("ReplacementDepthBlendAlpha", 0.0)), 4)
            if row.get("ReplacementDepthBlendAlpha") is not None
            else None
        ),
        "slot_count_per_team": int(row.get("SlotCountPerTeam", 0) or 0),
        "slot_capacity_league": int(row.get("SlotCapacityLeague", 0) or 0),
        "volume": volume,
        "components": _round_component_map(components),
    }


def _normalized_replacement_depth_mode(lg: CommonDynastyRotoSettings) -> str:
    mode = str(getattr(lg, "replacement_depth_mode", "flat") or "flat").strip().lower()
    return mode if mode in REPLACEMENT_DEPTH_MODES else "flat"


def _normalized_replacement_depth_blend_alpha(lg: CommonDynastyRotoSettings) -> float:
    try:
        alpha = float(getattr(lg, "replacement_depth_blend_alpha", 0.33))
    except (TypeError, ValueError):
        alpha = 0.33
    return min(max(alpha, 0.0), 1.0)


def _normalized_replacement_depth_blend_alpha_by_slot(
    lg: CommonDynastyRotoSettings,
) -> dict[str, float]:
    raw_mapping = getattr(lg, "replacement_depth_blend_alpha_by_slot", {}) or {}
    if not isinstance(raw_mapping, dict):
        return {}
    out: dict[str, float] = {}
    for raw_slot, raw_alpha in raw_mapping.items():
        slot = str(raw_slot or "").strip().upper()
        if slot not in DEPTH_AWARE_REPLACEMENT_SLOTS:
            continue
        try:
            alpha = float(raw_alpha)
        except (TypeError, ValueError):
            continue
        out[slot] = min(max(alpha, 0.0), 1.0)
    return out


def _replacement_depth_blend_alpha_for_slot(
    lg: CommonDynastyRotoSettings,
    slot: str,
) -> float:
    by_slot = _normalized_replacement_depth_blend_alpha_by_slot(lg)
    normalized_slot = str(slot or "").strip().upper()
    if normalized_slot in by_slot:
        return by_slot[normalized_slot]
    return _normalized_replacement_depth_blend_alpha(lg)


def _slot_count_per_team(lg: CommonDynastyRotoSettings, slot: str) -> int:
    hitter_slots = getattr(lg, "hitter_slots", {}) or {}
    pitcher_slots = getattr(lg, "pitcher_slots", {}) or {}
    if slot in hitter_slots:
        return max(int(hitter_slots.get(slot, 0) or 0), 0)
    if slot in pitcher_slots:
        return max(int(pitcher_slots.get(slot, 0) or 0), 0)
    return 0


def _slot_capacity_league(lg: CommonDynastyRotoSettings, slot: str) -> int:
    return max(int(lg.n_teams), 0) * _slot_count_per_team(lg, slot)


def _replacement_pool_depth(
    *,
    lg: CommonDynastyRotoSettings,
    slot: str,
    n_repl: int,
    mode: str,
) -> int:
    base_depth = max(int(n_repl), 1)
    slot_count = _slot_count_per_team(lg, slot)
    if slot not in DEPTH_AWARE_REPLACEMENT_SLOTS or slot_count <= 1:
        return base_depth
    if mode == "half_depth":
        return max(base_depth, max(int(lg.n_teams), 1) * int(math.ceil(slot_count / 2.0)))
    if mode == "full_depth":
        return max(base_depth, max(int(lg.n_teams), 1) * slot_count)
    return base_depth


def _replacement_row(
    *,
    slot: str,
    baseline_row: pd.Series,
    candidates: pd.DataFrame,
    component_cols: list[str],
    lg: CommonDynastyRotoSettings,
    n_repl: int,
    mode: str,
) -> dict[str, Any]:
    normalized_mode = mode if mode in REPLACEMENT_DEPTH_MODES else "flat"
    slot_count = _slot_count_per_team(lg, slot)
    slot_capacity = _slot_capacity_league(lg, slot)
    effective_mode = normalized_mode if slot in DEPTH_AWARE_REPLACEMENT_SLOTS and slot_count > 1 else "flat"

    if effective_mode == "blended_depth":
        blend_alpha = _replacement_depth_blend_alpha_for_slot(lg, slot)
        flat_depth = _replacement_pool_depth(lg=lg, slot=slot, n_repl=n_repl, mode="flat")
        full_depth = _replacement_pool_depth(lg=lg, slot=slot, n_repl=n_repl, mode="full_depth")
        flat_candidates = candidates.head(flat_depth)
        full_candidates = candidates.head(full_depth)
        flat_row = baseline_row if len(flat_candidates) == 0 else flat_candidates[component_cols].mean()
        full_row = baseline_row if len(full_candidates) == 0 else full_candidates[component_cols].mean()
        replacement_row = (
            flat_row.astype(float) * (1.0 - blend_alpha)
            + full_row.astype(float) * blend_alpha
        )
        replacement_pool_depth = int(
            round((len(flat_candidates) * (1.0 - blend_alpha)) + (len(full_candidates) * blend_alpha))
        )
    else:
        replacement_pool_depth = _replacement_pool_depth(
            lg=lg,
            slot=slot,
            n_repl=n_repl,
            mode=effective_mode,
        )
        selected = candidates.head(replacement_pool_depth)
        replacement_pool_depth = len(selected)
        replacement_row = baseline_row if len(selected) == 0 else selected[component_cols].mean()

    row: dict[str, Any] = {c: float(replacement_row.get(c, 0.0)) for c in component_cols}
    row["AssignedSlot"] = slot
    row["ReplacementPoolDepth"] = replacement_pool_depth
    row["ReplacementDepthMode"] = effective_mode
    row["ReplacementDepthBlendAlpha"] = (
        _replacement_depth_blend_alpha_for_slot(lg, slot) if effective_mode == "blended_depth" else None
    )
    row["SlotCountPerTeam"] = slot_count
    row["SlotCapacityLeague"] = slot_capacity
    return row


def _pitching_totals_summary(values: Mapping[str, object]) -> dict[str, float]:
    totals = {col: float(_coerce_float(values.get(col, 0.0)) or 0.0) for col in PIT_COMPONENT_COLS}
    totals["ERA"] = float(_coerce_float(values.get("ERA", 0.0)) or 0.0)
    totals["WHIP"] = float(_coerce_float(values.get("WHIP", 0.0)) or 0.0)
    return _round_component_map(totals)


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


def _pitcher_is_rp_only(row: dict[str, object] | pd.Series) -> bool:
    pos_set = parse_pit_positions(str(row.get("Pos", "") or ""))
    return "RP" in pos_set and "SP" not in pos_set


def _generic_p_save_context_active(
    lg: CommonDynastyRotoSettings,
    *,
    pit_categories: list[str],
) -> bool:
    if _slot_count_per_team(lg, "P") <= 0 or _slot_count_per_team(lg, "RP") > 0:
        return False
    active_cats = {str(cat).upper() for cat in pit_categories}
    return bool(active_cats & {"SV", "SVH"})


def _positive_save_guard_exempt_categories(
    *,
    lg: CommonDynastyRotoSettings,
    pit_categories: list[str],
    slot: str,
    row: dict[str, object] | pd.Series,
) -> set[str]:
    if str(slot).upper() != "P":
        return set()
    if not _generic_p_save_context_active(lg, pit_categories=pit_categories):
        return set()
    if not _pitcher_is_rp_only(row):
        return set()
    return {cat for cat in pit_categories if str(cat).upper() in {"SV", "SVH"}}


def compute_replacement_baselines(
    ctx: CommonYearContextLike,
    lg: CommonDynastyRotoSettings,
    rostered_players: Set[str],
    n_repl: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Build per-slot replacement baselines from the unrostered pool."""
    n_repl = int(n_repl or lg.n_teams)

    bat_y = cast(pd.DataFrame, context_value(ctx, "bat_y")).copy()
    pit_y = cast(pd.DataFrame, context_value(ctx, "pit_y")).copy()

    for c in HIT_COMPONENT_COLS:
        bat_y[c] = bat_y[c].fillna(0.0)
    for c in PIT_COMPONENT_COLS:
        pit_y[c] = pit_y[c].fillna(0.0)

    hit_categories = cast(list[str] | None, context_optional_value(ctx, "hit_categories")) or _active_common_hit_categories(lg)
    pit_categories = cast(list[str] | None, context_optional_value(ctx, "pit_categories")) or _active_common_pitch_categories(lg)
    bat_y["weight"] = _initial_hitter_weight(bat_y, categories=hit_categories)
    pit_y["weight"] = _initial_pitcher_weight(pit_y, categories=pit_categories)

    fa_hit = bat_y[(~bat_y["Player"].isin(rostered_players)) & (bat_y["AB"] > 0)].copy()
    fa_pit = pit_y[(~pit_y["Player"].isin(rostered_players)) & (pit_y["IP"] > 0)].copy()

    fa_hit["elig"] = fa_hit["Pos"].apply(lambda p: eligible_hit_slots(parse_hit_positions(p)))
    fa_pit["elig"] = fa_pit["Pos"].apply(lambda p: eligible_pit_slots(parse_pit_positions(p)))

    baseline_hit_avg = cast(pd.DataFrame, context_value(ctx, "baseline_hit"))
    baseline_pit_avg = cast(pd.DataFrame, context_value(ctx, "baseline_pit"))
    replacement_depth_mode = _normalized_replacement_depth_mode(lg)

    repl_hit_rows: List[dict] = []
    for slot in baseline_hit_avg.index:
        hit_slot_mask = fa_hit["elig"].apply(lambda s: slot in s).astype(bool)
        candidates = fa_hit.loc[hit_slot_mask].sort_values("weight", ascending=False)
        repl_hit_rows.append(
            _replacement_row(
                slot=str(slot),
                baseline_row=baseline_hit_avg.loc[slot],
                candidates=candidates,
                component_cols=HIT_COMPONENT_COLS,
                lg=lg,
                n_repl=n_repl,
                mode=replacement_depth_mode,
            )
        )

    repl_hit = pd.DataFrame(repl_hit_rows).set_index("AssignedSlot")

    repl_pit_rows: List[dict] = []
    for slot in baseline_pit_avg.index:
        pit_slot_mask = fa_pit["elig"].apply(lambda s: slot in s).astype(bool)
        candidates = fa_pit.loc[pit_slot_mask].sort_values("weight", ascending=False)
        repl_pit_rows.append(
            _replacement_row(
                slot=str(slot),
                baseline_row=baseline_pit_avg.loc[slot],
                candidates=candidates,
                component_cols=PIT_COMPONENT_COLS,
                lg=lg,
                n_repl=n_repl,
                mode=replacement_depth_mode,
            )
        )

    repl_pit = pd.DataFrame(repl_pit_rows).set_index("AssignedSlot")
    if _generic_p_save_context_active(lg, pit_categories=pit_categories) and "P" in baseline_pit_avg.index:
        rp_only_mask = fa_pit["Pos"].apply(
            lambda value: _pitcher_is_rp_only({"Pos": value})
        ).astype(bool)
        rp_only_candidates = fa_pit.loc[rp_only_mask].sort_values("weight", ascending=False)
        if not rp_only_candidates.empty:
            rp_context_row = _replacement_row(
                slot="P",
                baseline_row=baseline_pit_avg.loc["P"],
                candidates=rp_only_candidates,
                component_cols=PIT_COMPONENT_COLS,
                lg=lg,
                n_repl=n_repl,
                mode=replacement_depth_mode,
            )
            rp_context_row["AssignedSlot"] = "P_RP_CONTEXT"
            repl_pit = pd.concat(
                [repl_pit, pd.DataFrame([rp_context_row]).set_index("AssignedSlot")],
                axis=0,
            )
    return repl_hit, repl_pit


def compute_year_player_values_vs_replacement(
    ctx: CommonYearContextLike,
    lg: CommonDynastyRotoSettings,
    repl_hit: pd.DataFrame,
    repl_pit: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute per-year values as marginal roto points above replacement."""
    year = int(cast(int, context_value(ctx, "year")))
    bat_y = cast(pd.DataFrame, context_value(ctx, "bat_y"))
    pit_y = cast(pd.DataFrame, context_value(ctx, "pit_y"))

    baseline_hit_avg = cast(pd.DataFrame, context_value(ctx, "baseline_hit"))
    baseline_pit_avg = cast(pd.DataFrame, context_value(ctx, "baseline_pit"))
    base_hit_tot_avg = cast(pd.Series, context_value(ctx, "base_hit_tot"))
    base_pit_tot_avg = cast(pd.Series, context_value(ctx, "base_pit_tot"))
    rep_rates = cast(dict[str, float] | None, context_optional_value(ctx, "rep_rates"))

    sgp_hit = cast(dict[str, float], context_value(ctx, "sgp_hit"))
    sgp_pit = cast(dict[str, float], context_value(ctx, "sgp_pit"))
    hit_categories = cast(list[str] | None, context_optional_value(ctx, "hit_categories")) or _active_common_hit_categories(lg)
    pit_categories = cast(list[str] | None, context_optional_value(ctx, "pit_categories")) or _active_common_pitch_categories(lg)

    hit_rows = []
    for row in bat_y.to_dict(orient="records"):
        pos_set = parse_hit_positions(row.get("Pos", ""))
        slots = eligible_hit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None
        best_stat_sgps: Dict[str, float] = {}
        best_diag: dict[str, Any] | None = None

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
            delta_before_guard = dict(delta)
            hitter_ab = _coerce_non_negative_float(row.get("AB", 0.0))
            slot_ab_reference = _coerce_non_negative_float(b_avg.get("AB", 0.0))
            guard_mode = "none"
            positive_credit_scale = 1.0
            if bool(getattr(lg, "enable_playing_time_reliability", False)):
                guard_mode = "playing_time_reliability"
                positive_credit_scale = _positive_credit_scale(
                    player_volume=hitter_ab,
                    slot_volume_reference=slot_ab_reference,
                )
                _apply_hitter_playing_time_reliability_guard(
                    delta,
                    hit_categories=hit_categories,
                    hitter_ab=hitter_ab,
                    slot_ab_reference=slot_ab_reference,
                )

            val = 0.0
            stat_sgps: Dict[str, float] = {}
            for c in hit_categories:
                denom = float(sgp_hit[c])
                sgp_c = (delta[c] / denom) if denom else 0.0
                val += sgp_c
                stat_sgps[c] = sgp_c

            workload_share = (hitter_ab / slot_ab_reference) if slot_ab_reference > 0.0 else None
            candidate_diag: dict[str, Any] = {
                "side": "hit",
                "best_slot": str(slot),
                "category_sgp": _round_float_map(stat_sgps),
                "slot_baseline_reference": _reference_summary(
                    slot=str(slot),
                    row=b_avg,
                    component_cols=HIT_COMPONENT_COLS,
                ),
                "replacement_reference": _reference_summary(
                    slot=str(slot),
                    row=b_rep,
                    component_cols=HIT_COMPONENT_COLS,
                ),
                "guard": {
                    "mode": guard_mode,
                    "player_volume": round(hitter_ab, 4),
                    "slot_volume_reference": round(slot_ab_reference, 4),
                    "workload_share": round(float(workload_share), 6) if workload_share is not None else None,
                    "positive_credit_scale": round(float(positive_credit_scale), 6),
                    "pre_guard_category_delta": _round_float_map(delta_before_guard),
                    "post_guard_category_delta": _round_float_map(delta),
                },
            }

            if val > best_val:
                best_val = val
                best_slot = slot
                best_stat_sgps = stat_sgps
                best_diag = candidate_diag

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
                "ReplacementDiagnostics": best_diag,
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
        best_pitch_stat_sgps: Dict[str, float] = {}
        best_pitch_diag: dict[str, Any] | None = None

        for slot in slots:
            if slot not in baseline_pit_avg.index or slot not in repl_pit.index:
                continue

            b_avg = baseline_pit_avg.loc[slot]
            b_rep = (
                repl_pit.loc["P_RP_CONTEXT"]
                if slot == "P" and _pitcher_is_rp_only(row) and "P_RP_CONTEXT" in repl_pit.index
                else repl_pit.loc[slot]
            )

            base_raw = {c: float(base_pit_tot_avg[c]) for c in PIT_COMPONENT_COLS}
            new_raw = {c: float(base_pit_tot_avg[c]) for c in PIT_COMPONENT_COLS}
            for col in PIT_COMPONENT_COLS:
                base_raw[col] = base_raw[col] - float(b_avg[col]) + float(b_rep[col])
                new_raw[col] = new_raw[col] - float(b_avg[col]) + float(row.get(col, 0.0))

            new_bounded = common_apply_pitching_bounds(
                new_raw,
                lg,
                rep_rates,
                fill_to_ip_min=True,
            )
            base_bounded = common_apply_pitching_bounds(
                base_raw,
                lg,
                rep_rates,
                fill_to_ip_min=True,
            )

            base_pit_cats = common_pitch_category_totals(base_bounded)
            new_pit_cats = common_pitch_category_totals(new_bounded)
            pitch_delta: Dict[str, float] = {}
            for cat in pit_categories:
                new_val = float(new_pit_cats.get(cat, 0.0))
                base_val = float(base_pit_cats.get(cat, 0.0))
                if cat in COMMON_REVERSED_PITCH_CATS:
                    pitch_delta[cat] = base_val - new_val
                else:
                    pitch_delta[cat] = new_val - base_val
            delta_before_guard = dict(pitch_delta)
            pitcher_ip = _coerce_non_negative_float(row.get("IP", 0.0))
            slot_ip_reference = _coerce_non_negative_float(b_avg.get("IP", 0.0))
            positive_credit_scale = _positive_credit_scale(
                player_volume=pitcher_ip,
                slot_volume_reference=slot_ip_reference,
            )
            guard_mode = "none"
            if bool(getattr(lg, "enable_playing_time_reliability", False)):
                guard_mode = "playing_time_reliability"
                _apply_pitcher_playing_time_reliability_guard(
                    pitch_delta,
                    pit_categories=pit_categories,
                    pitcher_ip=pitcher_ip,
                    slot_ip_reference=slot_ip_reference,
                )
            else:
                guard_mode = "low_volume_split"
                _apply_low_volume_non_ratio_positive_guard(
                    pitch_delta,
                    pit_categories=pit_categories,
                    pitcher_ip=pitcher_ip,
                    slot_ip_reference=slot_ip_reference,
                    positive_exempt_categories=_positive_save_guard_exempt_categories(
                        lg=lg,
                        pit_categories=pit_categories,
                        slot=slot,
                        row=row,
                    ),
                )
                _apply_low_volume_ratio_guard(
                    pitch_delta,
                    pit_categories=pit_categories,
                    pitcher_ip=pitcher_ip,
                    slot_ip_reference=slot_ip_reference,
                )

            val = 0.0
            pitcher_stat_sgps: Dict[str, float] = {}
            for c in pit_categories:
                denom = float(sgp_pit[c])
                sgp_c = (pitch_delta[c] / denom) if denom else 0.0
                val += sgp_c
                pitcher_stat_sgps[c] = sgp_c

            workload_share = (pitcher_ip / slot_ip_reference) if slot_ip_reference > 0.0 else None
            base_ip_raw = float(base_raw.get("IP", 0.0))
            player_ip_raw = float(new_raw.get("IP", 0.0))
            base_ip_bounded = float(base_bounded.get("IP", 0.0))
            player_ip_bounded = float(new_bounded.get("IP", 0.0))
            candidate_diag = {
                "side": "pit",
                "best_slot": str(slot),
                "category_sgp": _round_float_map(pitcher_stat_sgps),
                "slot_baseline_reference": _reference_summary(
                    slot=str(slot),
                    row=b_avg,
                    component_cols=PIT_COMPONENT_COLS,
                ),
                "replacement_reference": _reference_summary(
                    slot=str(b_rep.get("AssignedSlot", slot)),
                    row=b_rep,
                    component_cols=PIT_COMPONENT_COLS,
                ),
                "guard": {
                    "mode": guard_mode,
                    "player_volume": round(pitcher_ip, 4),
                    "slot_volume_reference": round(slot_ip_reference, 4),
                    "workload_share": round(float(workload_share), 6) if workload_share is not None else None,
                    "positive_credit_scale": round(float(positive_credit_scale), 6),
                    "pre_guard_category_delta": _round_float_map(delta_before_guard),
                    "post_guard_category_delta": _round_float_map(pitch_delta),
                },
                "bounds": {
                    "applied": bool(
                        abs(base_ip_bounded - base_ip_raw) > 1e-9 or abs(player_ip_bounded - player_ip_raw) > 1e-9
                    ),
                    "base_ip_min_fill_applied": bool(base_ip_bounded > base_ip_raw + 1e-9),
                    "base_ip_max_trim_applied": bool(base_ip_bounded < base_ip_raw - 1e-9),
                    "player_ip_min_fill_applied": bool(player_ip_bounded > player_ip_raw + 1e-9),
                    "player_ip_max_trim_applied": bool(player_ip_bounded < player_ip_raw - 1e-9),
                    "base_raw_totals": _pitching_totals_summary(base_raw),
                    "base_bounded_totals": _pitching_totals_summary(base_bounded),
                    "player_raw_totals": _pitching_totals_summary(new_raw),
                    "player_bounded_totals": _pitching_totals_summary(new_bounded),
                },
            }

            if val > best_val:
                best_val = val
                best_slot = slot
                best_pitch_stat_sgps = pitcher_stat_sgps
                best_pitch_diag = candidate_diag

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
                "ReplacementDiagnostics": best_pitch_diag,
                **{f"SGP_{cat}": best_pitch_stat_sgps.get(cat, 0.0) for cat in pit_categories},
            }
        )

    pit_vals = pd.DataFrame(pit_rows)
    return hit_vals, pit_vals
