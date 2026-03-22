"""Shared common-mode centering and roster-selection helpers."""

from __future__ import annotations

import math
from typing import Optional, Set

import pandas as pd

try:
    from backend.valuation.dynasty_aggregation import dynasty_keep_or_drop_value
    from backend.valuation.minor_eligibility import (
        _fillna_bool,
        _select_mlb_roster_with_active_floor,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from valuation.dynasty_aggregation import dynasty_keep_or_drop_value  # type: ignore[no-redef]
    from valuation.minor_eligibility import (  # type: ignore[no-redef]
        _fillna_bool,
        _select_mlb_roster_with_active_floor,
    )

_CENTERING_ZERO_EPSILON = 1e-12
_DEEP_ROSTER_ZERO_CLUSTER_MIN_SHARE = 0.10
ValuationDiagnosticsValue = float | int | bool | str | dict[str, dict[str, object]]


def _select_preferred_players(
    sorted_frame: pd.DataFrame,
    *,
    preferred_players: Set[str],
    count: int,
    excluded_players: Set[str],
    avoid_players: Optional[Set[str]] = None,
) -> pd.DataFrame:
    remaining = sorted_frame[~sorted_frame["Player"].isin(excluded_players)].copy()
    if count <= 0 or remaining.empty:
        return remaining.iloc[0:0].copy()

    avoid = avoid_players or set()
    preferred = remaining[remaining["Player"].isin(preferred_players)]
    preferred_primary = preferred[~preferred["Player"].isin(avoid)].head(count).copy()
    selected = preferred_primary

    if len(selected) < count:
        selected_names = set(selected["Player"])
        preferred_fallback = preferred[
            ~preferred["Player"].isin(selected_names)
        ].head(count - len(selected)).copy()
        if not preferred_fallback.empty:
            selected = pd.concat([selected, preferred_fallback], ignore_index=True)

    if len(selected) < count:
        selected_names = set(selected["Player"])
        fill_primary = remaining[
            (~remaining["Player"].isin(selected_names)) & (~remaining["Player"].isin(avoid))
        ].head(count - len(selected)).copy()
        if not fill_primary.empty:
            selected = pd.concat([selected, fill_primary], ignore_index=True)

    if len(selected) < count:
        selected_names = set(selected["Player"])
        fill_fallback = remaining[
            ~remaining["Player"].isin(selected_names)
        ].head(count - len(selected)).copy()
        if not fill_fallback.empty:
            selected = pd.concat([selected, fill_fallback], ignore_index=True)

    return selected.reset_index(drop=True)


def _select_roster_groups(
    stash_sorted: pd.DataFrame,
    *,
    total_minor_slots: int,
    total_ir_slots: int,
    total_bench_slots: int,
    total_active_slots: int,
    active_floor_names: Set[str],
    minor_candidate_players: Set[str],
    ir_candidate_players: Set[str],
    bench_candidate_players: Set[str],
    active_candidate_players: Optional[Set[str]] = None,
) -> dict[str, pd.DataFrame]:
    used_players: Set[str] = set()

    minor_sel = _select_preferred_players(
        stash_sorted,
        preferred_players=minor_candidate_players,
        count=total_minor_slots,
        excluded_players=used_players,
    )
    used_players.update(minor_sel["Player"].astype(str).tolist())

    ir_sel = _select_preferred_players(
        stash_sorted,
        preferred_players=ir_candidate_players,
        count=total_ir_slots,
        excluded_players=used_players,
        avoid_players=active_floor_names,
    )
    used_players.update(ir_sel["Player"].astype(str).tolist())

    bench_sel = _select_preferred_players(
        stash_sorted,
        preferred_players=bench_candidate_players,
        count=total_bench_slots,
        excluded_players=used_players,
        avoid_players=active_floor_names,
    )
    used_players.update(bench_sel["Player"].astype(str).tolist())

    active_sel = _select_mlb_roster_with_active_floor(
        stash_sorted,
        excluded_players=used_players,
        total_mlb_slots=total_active_slots,
        active_floor_names=active_floor_names,
        mlb_playing_time_players=active_candidate_players,
    )

    return {
        "minor": minor_sel.reset_index(drop=True),
        "ir": ir_sel.reset_index(drop=True),
        "bench": bench_sel.reset_index(drop=True),
        "active": active_sel.reset_index(drop=True),
    }


def _blend_replacement_frame(
    frozen_frame: pd.DataFrame,
    current_frame: pd.DataFrame,
    *,
    alpha: float,
) -> pd.DataFrame:
    idx = frozen_frame.index.union(current_frame.index)
    cols = frozen_frame.columns.union(current_frame.columns)
    numeric_cols = [col for col in cols if str(col) != "ReplacementDepthMode"]

    frozen_numeric = frozen_frame.reindex(index=idx, columns=numeric_cols).astype(float).fillna(0.0)
    current_numeric = current_frame.reindex(index=idx, columns=numeric_cols).astype(float).fillna(0.0)
    blended = (float(alpha) * frozen_numeric) + ((1.0 - float(alpha)) * current_numeric)

    if "ReplacementDepthMode" in cols:
        frozen_mode = frozen_frame.get("ReplacementDepthMode")
        current_mode = current_frame.get("ReplacementDepthMode")
        mode_series = None
        if isinstance(current_mode, pd.Series):
            mode_series = current_mode.reindex(idx)
        if isinstance(frozen_mode, pd.Series):
            frozen_aligned = frozen_mode.reindex(idx)
            mode_series = frozen_aligned if mode_series is None else mode_series.combine_first(frozen_aligned)
        if mode_series is not None:
            blended["ReplacementDepthMode"] = mode_series.fillna("flat")

    return blended.reindex(columns=cols)


def _forced_roster_value(values: list[float], years: list[int], discount: float) -> float:
    """Score a player when the league forces one season of roster occupancy."""
    if not years or not values:
        return 0.0
    if len(values) != len(years):
        raise ValueError("values and years must have the same length")
    if len(values) == 1:
        return float(values[0])

    gap = int(years[1]) - int(years[0])
    if gap < 0:
        raise ValueError("years must be increasing")
    future_value = dynasty_keep_or_drop_value(values[1:], years[1:], discount)
    return float(values[0] + (discount ** gap) * future_value)


def _centering_baseline_from_score(
    frame: pd.DataFrame,
    *,
    score_col: str,
    total_minor_slots: int,
    total_ir_slots: int,
    total_bench_slots: int,
    total_active_slots: int,
    active_floor_names: Set[str],
    minor_candidate_players: Set[str],
    ir_candidate_players: Set[str],
    bench_candidate_players: Set[str],
    active_candidate_players: Optional[Set[str]] = None,
) -> float:
    stash_sorted = frame.sort_values(score_col, ascending=False).reset_index(drop=True).copy()
    stash_sorted["StashScore"] = pd.to_numeric(stash_sorted.get(score_col), errors="coerce").fillna(0.0)
    center_groups = _select_roster_groups(
        stash_sorted,
        total_minor_slots=total_minor_slots,
        total_ir_slots=total_ir_slots,
        total_bench_slots=total_bench_slots,
        total_active_slots=total_active_slots,
        active_floor_names=active_floor_names,
        minor_candidate_players=minor_candidate_players,
        ir_candidate_players=ir_candidate_players,
        bench_candidate_players=bench_candidate_players,
        active_candidate_players=active_candidate_players,
    )
    rostered = pd.concat(
        [
            center_groups["minor"],
            center_groups["ir"],
            center_groups["bench"],
            center_groups["active"],
        ],
        ignore_index=True,
    )
    return float(rostered["StashScore"].iloc[-1]) if len(rostered) else 0.0


def _minor_slot_residual_metrics(
    player: str,
    *,
    years: list[int],
    start_year: int,
    hitter_ab_by_player_year: dict[tuple[str, int], float],
    pitcher_ip_by_player_year: dict[tuple[str, int], float],
) -> tuple[int, float]:
    eta_offset: Optional[int] = None
    total_ab = 0.0
    total_ip = 0.0

    for year in years:
        year_int = int(year)
        if year_int < int(start_year):
            continue
        ab = float(hitter_ab_by_player_year.get((player, year_int), 0.0))
        ip = float(pitcher_ip_by_player_year.get((player, year_int), 0.0))
        if eta_offset is None and (ab > 0.0 or ip > 0.0):
            eta_offset = year_int - int(start_year)
        total_ab += ab
        total_ip += ip

    if eta_offset is None:
        eta_offset = len(years) + 1
    projected_volume_score = total_ab + (3.0 * total_ip)
    return int(eta_offset), float(projected_volume_score)


def _apply_residual_minor_slot_cost(
    centered: pd.DataFrame,
    *,
    raw_zero_mask: pd.Series,
    zero_epsilon: float,
    years: list[int],
    start_year: int,
    n_teams: int,
    hitter_ab_by_player_year: dict[tuple[str, int], float],
    pitcher_ip_by_player_year: dict[tuple[str, int], float],
) -> tuple[pd.DataFrame, int]:
    if "minor_eligible" not in centered.columns:
        return centered, 0

    centering_score = pd.to_numeric(centered["CenteringScore"], errors="coerce").fillna(0.0)
    minor_eligible_series = _fillna_bool(centered["minor_eligible"])
    residual_mask = raw_zero_mask & (centering_score.abs() <= float(zero_epsilon)) & minor_eligible_series
    residual_candidates = centered.loc[residual_mask, ["Player"]].copy()
    if residual_candidates.empty:
        return centered, 0

    negative_forced = pd.to_numeric(centered.loc[raw_zero_mask, "ForcedRosterValue"], errors="coerce").fillna(0.0)
    negative_forced = negative_forced[negative_forced < -float(zero_epsilon)]
    reference_cost = abs(float(negative_forced.min())) if not negative_forced.empty else 0.03
    slot_cost_unit = float(min(max(reference_cost, 0.03), 12.0))
    teams_count = max(int(n_teams), 1)

    eta_offsets: list[int] = []
    projected_volume_scores: list[float] = []
    for player in residual_candidates["Player"].astype(str).tolist():
        eta_offset, projected_volume_score = _minor_slot_residual_metrics(
            player,
            years=years,
            start_year=int(start_year),
            hitter_ab_by_player_year=hitter_ab_by_player_year,
            pitcher_ip_by_player_year=pitcher_ip_by_player_year,
        )
        eta_offsets.append(int(eta_offset))
        projected_volume_scores.append(float(projected_volume_score))

    residual_candidates["MinorEtaOffset"] = eta_offsets
    residual_candidates["MinorProjectedVolumeScore"] = projected_volume_scores
    residual_candidates = residual_candidates.reset_index().rename(columns={"index": "row_index"}).sort_values(
        ["MinorEtaOffset", "MinorProjectedVolumeScore", "Player"],
        ascending=[True, False, True],
        kind="stable",
    ).reset_index(drop=True)

    for rank, row in enumerate(residual_candidates.itertuples(index=False)):
        eta_offset = int(row.MinorEtaOffset)
        round_number = 1 + (rank // teams_count)
        eta_multiplier = 1.0 + (0.15 * min(max(eta_offset, 0), 5))
        round_multiplier = 1.0 + (0.05 * (round_number - 1))
        minor_slot_cost_value = -float(slot_cost_unit * eta_multiplier * round_multiplier) - (1e-6 * float(rank))
        centered.at[int(row.row_index), "MinorSlotCostValue"] = minor_slot_cost_value
        centered.at[int(row.row_index), "MinorEtaOffset"] = float(eta_offset)
        centered.at[int(row.row_index), "MinorProjectedVolumeScore"] = float(row.MinorProjectedVolumeScore)
        centered.at[int(row.row_index), "CenteringScore"] = minor_slot_cost_value

    return centered, int(len(residual_candidates))


def _apply_dynasty_centering(
    out: pd.DataFrame,
    *,
    forced_roster_values: list[float],
    total_minor_slots: int,
    total_ir_slots: int,
    total_bench_slots: int,
    total_active_slots: int,
    active_floor_names: Set[str],
    minor_candidate_players: Set[str],
    ir_candidate_players: Set[str],
    bench_candidate_players: Set[str],
    active_candidate_players: Optional[Set[str]] = None,
    n_teams: int = 1,
    years: Optional[list[int]] = None,
    start_year: int = 0,
    hitter_ab_by_player_year: Optional[dict[tuple[str, int], float]] = None,
    pitcher_ip_by_player_year: Optional[dict[tuple[str, int], float]] = None,
    zero_epsilon: float = _CENTERING_ZERO_EPSILON,
    zero_cluster_min_share: float = _DEEP_ROSTER_ZERO_CLUSTER_MIN_SHARE,
) -> tuple[pd.DataFrame, dict[str, ValuationDiagnosticsValue]]:
    if len(out) != len(forced_roster_values):
        raise ValueError("forced_roster_values must align one-to-one with the output frame")

    centered = out.copy()
    valuation_years = [int(year) for year in (years or ([int(start_year)] if start_year else []))]
    hitter_volume = hitter_ab_by_player_year or {}
    pitcher_volume = pitcher_ip_by_player_year or {}
    raw_series = pd.to_numeric(centered.get("RawDynastyValue"), errors="coerce").fillna(0.0)
    centered["ForcedRosterValue"] = pd.Series(forced_roster_values, index=centered.index, dtype="float64")
    centered["CenteringScore"] = raw_series.astype(float)
    centered["MinorSlotCostValue"] = math.nan
    centered["MinorEtaOffset"] = math.nan
    centered["MinorProjectedVolumeScore"] = math.nan

    raw_baseline_value = _centering_baseline_from_score(
        centered,
        score_col="RawDynastyValue",
        total_minor_slots=total_minor_slots,
        total_ir_slots=total_ir_slots,
        total_bench_slots=total_bench_slots,
        total_active_slots=total_active_slots,
        active_floor_names=active_floor_names,
        minor_candidate_players=minor_candidate_players,
        ir_candidate_players=ir_candidate_players,
        bench_candidate_players=bench_candidate_players,
        active_candidate_players=active_candidate_players,
    )
    raw_zero_mask = raw_series.abs() <= float(zero_epsilon)
    raw_zero_value_count = int(raw_zero_mask.sum())
    raw_zero_share = (float(raw_zero_value_count) / float(len(centered))) if len(centered) else 0.0
    deep_roster_zero_baseline_warning = bool(
        abs(float(raw_baseline_value)) <= float(zero_epsilon)
        and len(centered) > 0
        and raw_zero_share >= float(zero_cluster_min_share)
    )

    centering_mode = "standard"
    fallback_applied = False
    residual_minor_slot_cost_applied = False
    residual_zero_minor_candidate_count = 0
    centering_score_baseline_value = float(raw_baseline_value)
    if deep_roster_zero_baseline_warning:
        centered.loc[raw_zero_mask, "CenteringScore"] = centered.loc[raw_zero_mask, "ForcedRosterValue"]
        centering_score_baseline_value = _centering_baseline_from_score(
            centered,
            score_col="CenteringScore",
            total_minor_slots=total_minor_slots,
            total_ir_slots=total_ir_slots,
            total_bench_slots=total_bench_slots,
            total_active_slots=total_active_slots,
            active_floor_names=active_floor_names,
            minor_candidate_players=minor_candidate_players,
            ir_candidate_players=ir_candidate_players,
            bench_candidate_players=bench_candidate_players,
            active_candidate_players=active_candidate_players,
        )
        centering_mode = "forced_roster"
        fallback_applied = True
        if abs(float(centering_score_baseline_value)) <= float(zero_epsilon):
            centered, residual_zero_minor_candidate_count = _apply_residual_minor_slot_cost(
                centered,
                raw_zero_mask=raw_zero_mask,
                zero_epsilon=float(zero_epsilon),
                years=valuation_years,
                start_year=int(start_year),
                n_teams=int(n_teams),
                hitter_ab_by_player_year=hitter_volume,
                pitcher_ip_by_player_year=pitcher_volume,
            )
            if residual_zero_minor_candidate_count > 0:
                centering_score_baseline_value = _centering_baseline_from_score(
                    centered,
                    score_col="CenteringScore",
                    total_minor_slots=total_minor_slots,
                    total_ir_slots=total_ir_slots,
                    total_bench_slots=total_bench_slots,
                    total_active_slots=total_active_slots,
                    active_floor_names=active_floor_names,
                    minor_candidate_players=minor_candidate_players,
                    ir_candidate_players=ir_candidate_players,
                    bench_candidate_players=bench_candidate_players,
                    active_candidate_players=active_candidate_players,
                )
                centering_mode = "forced_roster_minor_cost"
                residual_minor_slot_cost_applied = True

    centered["DynastyValue"] = centered["CenteringScore"] - float(centering_score_baseline_value)
    centered["CenteringMode"] = centering_mode
    centered["ForcedRosterFallbackApplied"] = fallback_applied
    centered["CenteringBaselineValue"] = float(raw_baseline_value)
    centered["CenteringScoreBaselineValue"] = float(centering_score_baseline_value)
    centered["CenteringBaselineMean"] = float(centering_score_baseline_value)

    centering_score_series = pd.to_numeric(centered["CenteringScore"], errors="coerce").fillna(0.0)
    dynasty_series = pd.to_numeric(centered["DynastyValue"], errors="coerce").fillna(0.0)
    positive_value_count = int((dynasty_series > float(zero_epsilon)).sum())
    centering_score_zero_player_count = int((centering_score_series.abs() <= float(zero_epsilon)).sum())
    dynasty_zero_value_count = int((dynasty_series.abs() <= float(zero_epsilon)).sum())
    valuation_diagnostics: dict[str, ValuationDiagnosticsValue] = {
        "CenteringMode": centering_mode,
        "ForcedRosterFallbackApplied": fallback_applied,
        "ResidualMinorSlotCostApplied": residual_minor_slot_cost_applied,
        "CenteringBaselineValue": float(raw_baseline_value),
        "CenteringScoreBaselineValue": float(centering_score_baseline_value),
        "PositiveValuePlayerCount": positive_value_count,
        "ZeroValuePlayerCount": dynasty_zero_value_count,
        "RawZeroValuePlayerCount": raw_zero_value_count,
        "CenteringScoreZeroPlayerCount": centering_score_zero_player_count,
        "DynastyZeroValuePlayerCount": dynasty_zero_value_count,
        "ResidualZeroMinorCandidateCount": residual_zero_minor_candidate_count,
        "deep_roster_zero_baseline_warning": deep_roster_zero_baseline_warning,
    }
    return centered, valuation_diagnostics
