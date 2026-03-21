"""Points-mode dynasty calculation helpers and orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

try:
    from backend.core.points_assignment import (
        _SEASON_WEEKS,
        _best_slot_surplus,
        _effective_weekly_starts_cap,
        _slot_capacity_by_league,
        optimize_points_slot_assignment,
    )
    from backend.core.points_utils import (
        _scale_points_breakdown,
        calculate_hitter_points_breakdown,
        calculate_pitcher_points_breakdown,
        coerce_minor_eligible,
        points_hitter_eligible_slots,
        points_pitcher_eligible_slots,
        points_player_identity,
        points_slot_replacement,
        projection_identity_key,
        stat_or_zero,
        valuation_years,
    )
    from backend.core.points_value import (
        KeepDropResult,
        _apply_negative_value_stash_rules,
        _is_near_zero_playing_time,
        _negative_fallback_value,
        _prospect_risk_multiplier,
        dynasty_keep_or_drop_values,
    )
    from backend.valuation.active_volume import (
        SYNTHETIC_PERIOD_DAYS,
        SYNTHETIC_SEASON_DAYS,
        VolumeEntry,
        allocate_hitter_usage,
        allocate_hitter_usage_daily,
        allocate_pitcher_innings_budget,
        allocate_pitcher_usage,
        allocate_pitcher_usage_daily,
        annual_slot_capacity,
    )
    from backend.valuation.minor_eligibility import _resolve_minor_eligibility_by_year
    from backend.valuation.models import CommonDynastyRotoSettings
except ImportError:  # pragma: no cover - direct script execution fallback
    from points_assignment import (  # type: ignore[no-redef]
        _SEASON_WEEKS,
        _best_slot_surplus,
        _effective_weekly_starts_cap,
        _slot_capacity_by_league,
        optimize_points_slot_assignment,
    )
    from points_utils import (  # type: ignore[no-redef]
        _scale_points_breakdown,
        calculate_hitter_points_breakdown,
        calculate_pitcher_points_breakdown,
        coerce_minor_eligible,
        points_hitter_eligible_slots,
        points_pitcher_eligible_slots,
        points_player_identity,
        points_slot_replacement,
        projection_identity_key,
        stat_or_zero,
        valuation_years,
    )
    from points_value import (  # type: ignore[no-redef]
        KeepDropResult,
        _apply_negative_value_stash_rules,
        _is_near_zero_playing_time,
        _negative_fallback_value,
        _prospect_risk_multiplier,
        dynasty_keep_or_drop_values,
    )
    from valuation.active_volume import (  # type: ignore[no-redef]
        SYNTHETIC_PERIOD_DAYS,
        SYNTHETIC_SEASON_DAYS,
        VolumeEntry,
        allocate_hitter_usage,
        allocate_hitter_usage_daily,
        allocate_pitcher_innings_budget,
        allocate_pitcher_usage,
        allocate_pitcher_usage_daily,
        annual_slot_capacity,
    )
    from valuation.minor_eligibility import _resolve_minor_eligibility_by_year  # type: ignore[no-redef]
    from valuation.models import CommonDynastyRotoSettings  # type: ignore[no-redef]


@dataclass(slots=True)
class PointsCalculatorContext:
    bat_data: list[dict]
    pit_data: list[dict]
    bat_data_raw: list[dict]
    pit_data_raw: list[dict]
    meta: dict
    average_recent_projection_rows: Callable[..., list[dict]]
    coerce_meta_years: Callable[[dict], list[int]]
    valuation_years: Callable[[int, int, list[int]], list[int]]
    coerce_record_year: Callable[[object], int | None]
    points_player_identity: Callable[[dict], str]
    normalize_player_key: Callable[[object], str]
    player_key_col: str
    player_entity_key_col: str
    row_team_value: Callable[[dict], str]
    merge_position_value: Callable[[object, object], str | None]
    coerce_minor_eligible: Callable[[object], bool]
    calculate_hitter_points_breakdown: Callable[[dict | None, dict[str, float]], dict]
    calculate_pitcher_points_breakdown: Callable[[dict | None, dict[str, float]], dict]
    stat_or_zero: Callable[[dict | None, str], float]
    points_hitter_eligible_slots: Callable[[object], set[str]]
    points_pitcher_eligible_slots: Callable[[object], set[str]]
    points_slot_replacement: Callable[..., dict[str, float]]


__all__ = [
    "KeepDropResult",
    "PointsCalculatorContext",
    "calculate_hitter_points_breakdown",
    "calculate_pitcher_points_breakdown",
    "calculate_points_dynasty_frame",
    "coerce_minor_eligible",
    "dynasty_keep_or_drop_values",
    "optimize_points_slot_assignment",
    "points_hitter_eligible_slots",
    "points_pitcher_eligible_slots",
    "points_player_identity",
    "points_slot_replacement",
    "projection_identity_key",
    "stat_or_zero",
    "valuation_years",
]


_POINTS_CENTERING_ZERO_EPSILON = 1e-12
_POINTS_DEEP_ROSTER_ZERO_CLUSTER_MIN_SHARE = 0.10


def _points_row_sort_frame(
    frame: pd.DataFrame,
    *,
    score_col: str,
    player_entity_key_col: str,
    player_key_col: str,
) -> pd.DataFrame:
    sortable = frame.copy()
    sortable["_points_sort_score"] = pd.to_numeric(sortable.get(score_col), errors="coerce").fillna(0.0)
    sortable["_points_sort_entity"] = sortable.get(player_entity_key_col, "").astype(str)
    sortable["_points_sort_player_key"] = sortable.get(player_key_col, "").astype(str)
    sortable["_points_sort_player"] = sortable.get("Player", "").astype(str)
    return sortable.sort_values(
        ["_points_sort_score", "_points_sort_entity", "_points_sort_player_key", "_points_sort_player"],
        ascending=[False, True, True, True],
        kind="mergesort",
    ).reset_index(drop=True)


def _points_centering_baseline(
    frame: pd.DataFrame,
    *,
    score_col: str,
    replacement_rank: int,
    player_entity_key_col: str,
    player_key_col: str,
) -> float:
    if frame.empty:
        return 0.0
    sorted_frame = _points_row_sort_frame(
        frame,
        score_col=score_col,
        player_entity_key_col=player_entity_key_col,
        player_key_col=player_key_col,
    )
    cutoff_idx = min(max(int(replacement_rank), 1) - 1, len(sorted_frame) - 1)
    return float(sorted_frame.iloc[cutoff_idx]["_points_sort_score"])


def _future_continuation_value(keep_drop: KeepDropResult) -> float:
    if len(keep_drop.continuation_values) <= 1:
        return 0.0
    return float(keep_drop.continuation_values[1])


def calculate_points_dynasty_frame(
    *,
    ctx: PointsCalculatorContext,
    teams: int,
    horizon: int,
    discount: float,
    hit_c: int,
    hit_1b: int,
    hit_2b: int,
    hit_3b: int,
    hit_ss: int,
    hit_ci: int,
    hit_mi: int,
    hit_of: int,
    hit_ut: int,
    pit_p: int,
    pit_sp: int,
    pit_rp: int,
    bench: int,
    minors: int,
    ir: int,
    keeper_limit: int | None,
    two_way: str,
    points_valuation_mode: str,
    weekly_starts_cap: int | None,
    allow_same_day_starts_overflow: bool,
    weekly_acquisition_cap: int | None,
    start_year: int,
    pts_hit_1b: float,
    pts_hit_2b: float,
    pts_hit_3b: float,
    pts_hit_hr: float,
    pts_hit_r: float,
    pts_hit_rbi: float,
    pts_hit_sb: float,
    pts_hit_bb: float,
    pts_hit_hbp: float,
    pts_hit_so: float,
    pts_pit_ip: float,
    pts_pit_w: float,
    pts_pit_l: float,
    pts_pit_k: float,
    pts_pit_sv: float,
    pts_pit_hld: float,
    pts_pit_h: float,
    pts_pit_er: float,
    pts_pit_bb: float,
    pts_pit_hbp: float,
    ip_max: float | None = None,
    enable_prospect_risk_adjustment: bool = True,
    enable_bench_stash_relief: bool = False,
    bench_negative_penalty: float = 0.55,
    enable_ir_stash_relief: bool = False,
    ir_negative_penalty: float = 0.20,
    hit_dh: int = 0,
) -> pd.DataFrame:
    scoring = {
        "pts_hit_1b": float(pts_hit_1b),
        "pts_hit_2b": float(pts_hit_2b),
        "pts_hit_3b": float(pts_hit_3b),
        "pts_hit_hr": float(pts_hit_hr),
        "pts_hit_r": float(pts_hit_r),
        "pts_hit_rbi": float(pts_hit_rbi),
        "pts_hit_sb": float(pts_hit_sb),
        "pts_hit_bb": float(pts_hit_bb),
        "pts_hit_hbp": float(pts_hit_hbp),
        "pts_hit_so": float(pts_hit_so),
        "pts_pit_ip": float(pts_pit_ip),
        "pts_pit_w": float(pts_pit_w),
        "pts_pit_l": float(pts_pit_l),
        "pts_pit_k": float(pts_pit_k),
        "pts_pit_sv": float(pts_pit_sv),
        "pts_pit_hld": float(pts_pit_hld),
        "pts_pit_h": float(pts_pit_h),
        "pts_pit_er": float(pts_pit_er),
        "pts_pit_bb": float(pts_pit_bb),
        "pts_pit_hbp": float(pts_pit_hbp),
    }

    bat_rows = ctx.bat_data
    pit_rows = ctx.pit_data

    valid_years = ctx.coerce_meta_years(ctx.meta)
    valuation_year_set = ctx.valuation_years(start_year, horizon, valid_years)
    year_set = set(valuation_year_set)

    if not valuation_year_set:
        raise ValueError("No valuation years available for selected start_year and horizon.")

    minor_defaults = CommonDynastyRotoSettings()
    bat_minor_rows = [{**row, "Player": ctx.points_player_identity(row)} for row in bat_rows]
    pit_minor_rows = [{**row, "Player": ctx.points_player_identity(row)} for row in pit_rows]
    minor_eligibility_frame = _resolve_minor_eligibility_by_year(
        pd.DataFrame.from_records(bat_minor_rows),
        pd.DataFrame.from_records(pit_minor_rows),
        years=valuation_year_set,
        hitter_usage_max=minor_defaults.minor_ab_max,
        pitcher_usage_max=minor_defaults.minor_ip_max,
        hitter_age_max=minor_defaults.minor_age_max_hit,
        pitcher_age_max=minor_defaults.minor_age_max_pit,
    )
    minor_eligibility_by_year = {
        (str(row["Player"]), int(row["Year"])): bool(row["minor_eligible"])
        for row in minor_eligibility_frame.to_dict(orient="records")
    }

    rows_by_player: dict[str, dict[int, dict[str, dict | None]]] = {}
    hitter_ab_by_player_year: dict[tuple[str, int], float] = {}
    pitcher_ip_by_player_year: dict[tuple[str, int], float] = {}

    for row in bat_rows:
        year = ctx.coerce_record_year(row.get("Year"))
        if year is None or year not in year_set:
            continue
        player_id = ctx.points_player_identity(row)
        hitter_ab_by_player_year[(player_id, year)] = ctx.stat_or_zero(row, "AB")
        bucket = rows_by_player.setdefault(player_id, {})
        pair = bucket.setdefault(year, {"hit": None, "pit": None})
        pair["hit"] = row

    for row in pit_rows:
        year = ctx.coerce_record_year(row.get("Year"))
        if year is None or year not in year_set:
            continue
        player_id = ctx.points_player_identity(row)
        pitcher_ip_by_player_year[(player_id, year)] = ctx.stat_or_zero(row, "IP")
        bucket = rows_by_player.setdefault(player_id, {})
        pair = bucket.setdefault(year, {"hit": None, "pit": None})
        pair["pit"] = row

    active_slots_per_team = (
        hit_c
        + hit_1b
        + hit_2b
        + hit_3b
        + hit_ss
        + hit_ci
        + hit_mi
        + hit_of
        + hit_dh
        + hit_ut
        + pit_p
        + pit_sp
        + pit_rp
    )
    active_depth_per_team = max(1, active_slots_per_team)
    in_season_depth_per_team = max(1, active_slots_per_team + bench + minors + ir)
    replacement_rank = max(1, teams * in_season_depth_per_team)
    in_season_replacement_rank = max(1, teams * in_season_depth_per_team)
    keeper_continuation_rank = (
        max(1, teams * min(int(keeper_limit), in_season_depth_per_team))
        if keeper_limit is not None
        else None
    )
    hitter_slot_counts = {
        "C": int(hit_c),
        "1B": int(hit_1b),
        "2B": int(hit_2b),
        "3B": int(hit_3b),
        "SS": int(hit_ss),
        "CI": int(hit_ci),
        "MI": int(hit_mi),
        "OF": int(hit_of),
        "DH": int(hit_dh),
        "UT": int(hit_ut),
    }
    pitcher_slot_counts = {
        "P": int(pit_p),
        "SP": int(pit_sp),
        "RP": int(pit_rp),
    }
    active_hitter_slots = {slot for slot, count in hitter_slot_counts.items() if count > 0}
    active_pitcher_slots = {slot for slot, count in pitcher_slot_counts.items() if count > 0}
    starter_slot_capacity = max(int(pit_p) + int(pit_sp), 0)
    n_replacement = max(int(teams), 1)
    freeze_replacement_baselines = True

    player_meta: dict[str, dict[str, object]] = {}
    per_player_year: dict[str, dict[int, dict[str, object]]] = {}
    year_hit_entries: dict[int, list[dict[str, object]]] = {year: [] for year in valuation_year_set}
    year_pit_entries: dict[int, list[dict[str, object]]] = {year: [] for year in valuation_year_set}
    player_raw_totals: dict[str, float] = {}
    player_profile: dict[str, str] = {}
    hitter_usage_diagnostics_by_year: dict[int, dict[str, float | int | None]] = {}
    pitcher_usage_diagnostics_by_year: dict[int, dict[str, float | int | None]] = {}
    empty_hit_breakdown = ctx.calculate_hitter_points_breakdown(None, scoring)
    empty_pit_breakdown = ctx.calculate_pitcher_points_breakdown(None, scoring)
    use_daily_volume = points_valuation_mode in {"season_total", "daily_h2h"}
    annual_hitter_slot_capacity = annual_slot_capacity(
        hitter_slot_counts,
        teams=teams,
        season_capacity_per_slot=float(SYNTHETIC_SEASON_DAYS) if use_daily_volume else 162.0,
    )
    annual_pitcher_slot_capacity = annual_slot_capacity(
        pitcher_slot_counts,
        teams=teams,
        season_capacity_per_slot=float(SYNTHETIC_SEASON_DAYS) if use_daily_volume else 162.0,
    )

    for player_id, per_year in rows_by_player.items():
        if not per_year:
            continue

        start_pair = per_year.get(start_year)
        if start_pair and (start_pair.get("hit") or start_pair.get("pit")):
            meta_hit = start_pair.get("hit")
            meta_pit = start_pair.get("pit")
        else:
            first_year = min(per_year.keys())
            fallback_pair = per_year[first_year]
            meta_hit = fallback_pair.get("hit")
            meta_pit = fallback_pair.get("pit")

        meta_row = meta_hit or meta_pit or {}
        player_name = str(meta_row.get("Player") or "").strip()
        player_key = str(meta_row.get(ctx.player_key_col) or "").strip() or ctx.normalize_player_key(player_name)
        entity_key = str(meta_row.get(ctx.player_entity_key_col) or "").strip() or player_key

        player_meta[player_id] = {
            "Player": player_name,
            "Team": ctx.row_team_value(meta_hit or {}) or ctx.row_team_value(meta_pit or {}),
            "Pos": ctx.merge_position_value((meta_hit or {}).get("Pos"), (meta_pit or {}).get("Pos")),
            "Age": (meta_hit or {}).get("Age") if (meta_hit or {}).get("Age") is not None else (meta_pit or {}).get("Age"),
            "minor_eligible": ctx.coerce_minor_eligible((meta_hit or {}).get("minor_eligible"))
            or ctx.coerce_minor_eligible((meta_pit or {}).get("minor_eligible")),
            ctx.player_key_col: player_key,
            ctx.player_entity_key_col: entity_key,
        }
        player_profile[player_id] = "pitcher" if meta_pit and not meta_hit else "hitter"

        year_map: dict[int, dict[str, object]] = {}

        for year in valuation_year_set:
            pair = per_year.get(year) or {"hit": None, "pit": None}
            hit_row = pair.get("hit")
            pit_row = pair.get("pit")

            raw_hit_breakdown = ctx.calculate_hitter_points_breakdown(hit_row, scoring)
            raw_pit_breakdown = ctx.calculate_pitcher_points_breakdown(pit_row, scoring)
            raw_hit_points = float(raw_hit_breakdown["total_points"])
            raw_pit_points = float(raw_pit_breakdown["total_points"])

            hit_slots = set()
            if isinstance(hit_row, dict) and ctx.stat_or_zero(hit_row, "AB") > 0:
                hit_slots = ctx.points_hitter_eligible_slots(hit_row.get("Pos")) & active_hitter_slots
            pit_slots = set()
            if isinstance(pit_row, dict) and ctx.stat_or_zero(pit_row, "IP") > 0:
                pit_slots = ctx.points_pitcher_eligible_slots(pit_row.get("Pos")) & active_pitcher_slots

            projected_hit_games = ctx.stat_or_zero(hit_row, "G")
            projected_pit_appearances = ctx.stat_or_zero(pit_row, "G")
            projected_pit_starts = min(ctx.stat_or_zero(pit_row, "GS"), projected_pit_appearances) if projected_pit_appearances > 0.0 else 0.0
            projected_pit_ip = ctx.stat_or_zero(pit_row, "IP")

            year_map[year] = {
                "raw_hit_breakdown": raw_hit_breakdown,
                "raw_pit_breakdown": raw_pit_breakdown,
                "raw_hit_points": raw_hit_points,
                "raw_pit_points": raw_pit_points,
                "hit_slots": set(hit_slots),
                "pit_slots": set(pit_slots),
                "hit_has_volume": bool(hit_slots),
                "pit_has_volume": bool(pit_slots),
                "projected_hit_games": float(projected_hit_games),
                "projected_pit_appearances": float(projected_pit_appearances),
                "projected_pit_starts": float(projected_pit_starts),
                "projected_pit_ip": float(projected_pit_ip),
            }

        per_player_year[player_id] = year_map

    for year in valuation_year_set:
        hitter_entries: list[VolumeEntry] = []
        pitcher_entries: list[VolumeEntry] = []
        pitcher_start_volume: dict[str, float] = {}
        fallback_hitter_ids: set[str] = set()
        fallback_pitcher_ids: set[str] = set()
        requested_hitter_games = 0.0

        for player_id, year_map in per_player_year.items():
            info = year_map.get(year, {})
            hit_slots = set(info.get("hit_slots", set()))
            projected_hit_games = float(info.get("projected_hit_games", 0.0))
            raw_hit_points = float(info.get("raw_hit_points", 0.0))
            if hit_slots:
                if projected_hit_games > 0.0:
                    requested_hitter_games += projected_hit_games
                    hitter_entries.append(
                        VolumeEntry(
                            player_id=player_id,
                            projected_volume=projected_hit_games,
                            quality=raw_hit_points / projected_hit_games,
                            slots=set(hit_slots),
                            year=year,
                        )
                    )
                else:
                    fallback_hitter_ids.add(player_id)

            pit_slots = set(info.get("pit_slots", set()))
            projected_pit_appearances = float(info.get("projected_pit_appearances", 0.0))
            raw_pit_points = float(info.get("raw_pit_points", 0.0))
            if pit_slots:
                if projected_pit_appearances > 0.0:
                    pitcher_entries.append(
                        VolumeEntry(
                            player_id=player_id,
                            projected_volume=projected_pit_appearances,
                            quality=raw_pit_points / projected_pit_appearances,
                            slots=set(pit_slots),
                            year=year,
                        )
                    )
                    projected_start_volume = min(
                        float(info.get("projected_pit_starts", 0.0)),
                        projected_pit_appearances,
                    )
                    pitcher_start_volume[player_id] = projected_start_volume if projected_start_volume >= 1.0 else 0.0
                else:
                    fallback_pitcher_ids.add(player_id)

        if points_valuation_mode == "weekly_h2h":
            hitter_usage = allocate_hitter_usage(
                hitter_entries,
                slot_capacity=annual_hitter_slot_capacity,
            )
        else:
            hitter_usage = allocate_hitter_usage_daily(
                hitter_entries,
                slot_capacity=annual_hitter_slot_capacity,
            )

        effective_weekly_cap: float | None = None
        capped_start_budget: float | None = None
        held_pitcher_ids: set[str] | None = None
        streaming_adds_per_period: int | None = None
        if points_valuation_mode in {"weekly_h2h", "daily_h2h"}:
            effective_weekly_cap = _effective_weekly_starts_cap(
                weekly_starts_cap,
                allow_same_day_starts_overflow=allow_same_day_starts_overflow,
                starter_slot_capacity=starter_slot_capacity,
            )
            if effective_weekly_cap is not None and effective_weekly_cap > 0.0:
                capped_start_budget = float(effective_weekly_cap) * _SEASON_WEEKS * max(int(teams), 1)
        if points_valuation_mode == "daily_h2h":
            held_pitcher_budget = max(int(teams), 1) * max(int(starter_slot_capacity), 0)
            held_pitcher_ids = {
                entry.player_id
                for entry in sorted(
                    (
                        entry
                        for entry in pitcher_entries
                        if float(pitcher_start_volume.get(entry.player_id, 0.0)) >= 1.0
                    ),
                    key=lambda entry: (-float(entry.quality), str(entry.player_id)),
                )[:held_pitcher_budget]
            }
            if weekly_acquisition_cap is not None:
                streaming_adds_per_period = max(int(weekly_acquisition_cap), 0) * max(int(teams), 1)

        if points_valuation_mode == "weekly_h2h":
            pitcher_usage = allocate_pitcher_usage(
                pitcher_entries,
                start_volume_by_player=pitcher_start_volume,
                slot_capacity=annual_pitcher_slot_capacity,
                capped_start_budget=capped_start_budget,
            )
        else:
            pitcher_usage = allocate_pitcher_usage_daily(
                pitcher_entries,
                start_volume_by_player=pitcher_start_volume,
                slot_capacity=annual_pitcher_slot_capacity,
                capped_start_budget=capped_start_budget,
                held_player_ids=held_pitcher_ids,
                streaming_adds_per_period=streaming_adds_per_period,
                total_days=SYNTHETIC_SEASON_DAYS,
                period_days=SYNTHETIC_PERIOD_DAYS,
            )

        ip_budget = float(ip_max) * max(int(teams), 1) if ip_max is not None else None
        pitcher_appearance_usage_share: dict[str, float] = {}
        pitcher_ip_usage_share: dict[str, float] = {}
        pitcher_requested_ip_pre_cap: dict[str, float] = {}
        pitcher_assigned_ip: dict[str, float] = {}
        requested_pitcher_ip_pre_cap = 0.0
        ip_entries: list[VolumeEntry] = []

        for player_id, year_map in per_player_year.items():
            info = year_map.get(year, {})
            pit_slots = set(info.get("pit_slots", set()))
            if not pit_slots:
                continue
            projected_pit_ip = float(info.get("projected_pit_ip", 0.0))
            if projected_pit_ip <= 0.0:
                pitcher_appearance_usage_share[player_id] = 0.0
                pitcher_ip_usage_share[player_id] = 0.0
                pitcher_requested_ip_pre_cap[player_id] = 0.0
                pitcher_assigned_ip[player_id] = 0.0
                continue
            appearance_share = (
                1.0 if player_id in fallback_pitcher_ids else float(pitcher_usage.usage_share_by_player.get(player_id, 0.0))
            )
            appearance_share = float(min(max(appearance_share, 0.0), 1.0))
            requested_ip = projected_pit_ip * appearance_share
            pitcher_appearance_usage_share[player_id] = appearance_share
            pitcher_requested_ip_pre_cap[player_id] = requested_ip
            requested_pitcher_ip_pre_cap += requested_ip
            if requested_ip > 0.0:
                raw_pit_points = float(info.get("raw_pit_points", 0.0))
                requested_points = raw_pit_points * appearance_share
                ip_entries.append(
                    VolumeEntry(
                        player_id=player_id,
                        projected_volume=requested_ip,
                        quality=requested_points / requested_ip,
                        slots={"IP_CAP"},
                        year=year,
                    )
                )

        pitcher_ip_allocation = allocate_pitcher_innings_budget(ip_entries, ip_budget=ip_budget)
        pitcher_ip_usage_share.update(pitcher_ip_allocation.ip_usage_share_by_player)
        pitcher_assigned_ip.update(pitcher_ip_allocation.assigned_ip_by_player)

        hitter_usage_diagnostics_by_year[year] = {
            "slot_game_capacity": round(float(sum(annual_hitter_slot_capacity.values())), 4),
            "assigned_hitter_games": round(float(hitter_usage.total_assigned_volume), 4),
            "unused_hitter_games": round(
                max(float(requested_hitter_games) - float(hitter_usage.total_assigned_volume), 0.0),
                4,
            ),
            "fallback_hitter_count": int(len(fallback_hitter_ids)),
            "synthetic_season_days": int(SYNTHETIC_SEASON_DAYS) if use_daily_volume else None,
        }
        pitcher_diag: dict[str, float | int | None] = {
            "slot_appearance_capacity": round(float(sum(annual_pitcher_slot_capacity.values())), 4),
            "assigned_starts": round(float(pitcher_usage.total_assigned_starts), 4),
            "assigned_non_start_appearances": round(float(pitcher_usage.total_assigned_non_start_appearances), 4),
            "capped_start_budget": round(float(capped_start_budget), 4) if capped_start_budget is not None else None,
            "fallback_pitcher_count": int(len(fallback_pitcher_ids)),
            "synthetic_season_days": int(SYNTHETIC_SEASON_DAYS) if use_daily_volume else None,
            "selected_held_starts": round(float(pitcher_usage.selected_held_starts), 4)
            if pitcher_usage.selected_held_starts is not None
            else None,
            "selected_streamed_starts": round(float(pitcher_usage.selected_streamed_starts), 4)
            if pitcher_usage.selected_streamed_starts is not None
            else None,
            "streaming_adds_per_period": pitcher_usage.streaming_adds_per_period,
            "ip_cap_budget": round(float(ip_budget), 4) if ip_budget is not None else None,
            "requested_pitcher_ip_pre_cap": round(float(requested_pitcher_ip_pre_cap), 4),
            "assigned_pitcher_ip": round(float(pitcher_ip_allocation.total_assigned_ip), 4),
            "unused_pitcher_ip": round(float(pitcher_ip_allocation.unused_ip), 4)
            if pitcher_ip_allocation.unused_ip is not None
            else None,
            "trimmed_pitcher_ip": round(float(pitcher_ip_allocation.trimmed_ip), 4),
            "ip_cap_binding": bool(pitcher_ip_allocation.ip_cap_binding),
        }
        if points_valuation_mode == "weekly_h2h":
            pitcher_diag.update(
                {
                    "season_weeks": _SEASON_WEEKS,
                    "weekly_starts_cap": weekly_starts_cap,
                    "effective_weekly_starts_cap": round(float(effective_weekly_cap), 4)
                    if effective_weekly_cap is not None
                    else None,
                    "weekly_acquisition_cap": weekly_acquisition_cap,
                }
            )
        if points_valuation_mode == "daily_h2h":
            pitcher_diag.update(
                {
                    "season_weeks": _SEASON_WEEKS,
                    "weekly_starts_cap": weekly_starts_cap,
                    "effective_weekly_starts_cap": round(float(effective_weekly_cap), 4)
                    if effective_weekly_cap is not None
                    else None,
                    "weekly_acquisition_cap": weekly_acquisition_cap,
                    "synthetic_period_days": int(SYNTHETIC_PERIOD_DAYS),
                }
            )
        pitcher_usage_diagnostics_by_year[year] = pitcher_diag

        for player_id, year_map in per_player_year.items():
            info = year_map.get(year, {})
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))
            raw_hit_points = float(info.get("raw_hit_points", 0.0))
            raw_pit_points = float(info.get("raw_pit_points", 0.0))

            hit_share = 0.0
            if hit_slots:
                hit_share = 1.0 if player_id in fallback_hitter_ids else float(hitter_usage.usage_share_by_player.get(player_id, 0.0))
            pit_appearance_share = 0.0
            pit_ip_share = 0.0
            pit_share = 0.0
            if pit_slots:
                pit_appearance_share = float(pitcher_appearance_usage_share.get(player_id, 0.0))
                pit_ip_share = float(pitcher_ip_usage_share.get(player_id, 0.0))
                pit_share = float(min(max(pit_appearance_share * pit_ip_share, 0.0), 1.0))

            hit_breakdown = _scale_points_breakdown(
                info.get("raw_hit_breakdown") if isinstance(info.get("raw_hit_breakdown"), dict) else empty_hit_breakdown,
                hit_share,
            )
            pit_breakdown = _scale_points_breakdown(
                info.get("raw_pit_breakdown") if isinstance(info.get("raw_pit_breakdown"), dict) else empty_pit_breakdown,
                pit_share,
            )
            hit_points = float(raw_hit_points * hit_share)
            pit_points = float(raw_pit_points * pit_share)

            info.update(
                {
                    "hit_breakdown": hit_breakdown,
                    "pit_breakdown": pit_breakdown,
                    "hit_points": hit_points,
                    "pit_points": pit_points,
                    "hit_usage_share": float(min(max(hit_share, 0.0), 1.0)),
                    "pit_usage_share": float(min(max(pit_share, 0.0), 1.0)),
                    "pit_appearance_usage_share": float(min(max(pit_appearance_share, 0.0), 1.0)),
                    "pit_ip_usage_share": float(min(max(pit_ip_share, 0.0), 1.0)),
                    "hit_assigned_games": None
                    if player_id in fallback_hitter_ids
                    else float(hitter_usage.assigned_volume_by_player.get(player_id, 0.0)),
                    "pit_assigned_appearances": None
                    if player_id in fallback_pitcher_ids
                    else float(pitcher_usage.assigned_appearances_by_player.get(player_id, 0.0)),
                    "pit_assigned_starts": None
                    if player_id in fallback_pitcher_ids
                    else float(pitcher_usage.assigned_starts_by_player.get(player_id, 0.0)),
                    "pit_assigned_non_start_appearances": None
                    if player_id in fallback_pitcher_ids
                    else float(pitcher_usage.assigned_non_start_appearances_by_player.get(player_id, 0.0)),
                    "pit_assigned_ip": float(pitcher_assigned_ip.get(player_id, 0.0)) if pit_slots else None,
                }
            )
            if hit_slots:
                year_hit_entries[year].append(
                    {"player_id": player_id, "points": hit_points, "slots": set(hit_slots)}
                )
            if pit_slots:
                year_pit_entries[year].append(
                    {"player_id": player_id, "points": pit_points, "slots": set(pit_slots)}
                )

    for player_id, year_map in per_player_year.items():
        raw_total = 0.0
        for year_offset, year in enumerate(valuation_year_set):
            info = year_map.get(year, {})
            hit_points = float(info.get("hit_points", 0.0))
            pit_points = float(info.get("pit_points", 0.0))
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))

            selected_raw_points = 0.0
            if hit_slots and pit_slots:
                selected_raw_points = hit_points + pit_points if two_way == "sum" else max(hit_points, pit_points)
            elif hit_slots:
                selected_raw_points = hit_points
            elif pit_slots:
                selected_raw_points = pit_points

            raw_total += selected_raw_points * (float(discount) ** year_offset)
        player_raw_totals[player_id] = float(raw_total)

    if not player_meta:
        empty_columns = [
            "Player",
            "Team",
            "Pos",
            "Age",
            "DynastyValue",
            "RawDynastyValue",
            "minor_eligible",
            ctx.player_key_col,
            ctx.player_entity_key_col,
        ] + [f"Value_{year}" for year in valuation_year_set]
        return pd.DataFrame(columns=empty_columns)

    ranked_players = sorted(
        player_raw_totals.items(),
        key=lambda item: (-float(item[1]), str(item[0])),
    )
    rostered_player_ids = {player_id for player_id, _score in ranked_players[:replacement_rank]}
    in_season_rostered_player_ids = {
        player_id for player_id, _score in ranked_players[:in_season_replacement_rank]
    }

    year_hit_replacement: dict[int, dict[str, float]] = {}
    year_pit_replacement: dict[int, dict[str, float]] = {}
    if freeze_replacement_baselines:
        frozen_hit = ctx.points_slot_replacement(
            year_hit_entries.get(start_year, []),
            active_slots=active_hitter_slots,
            rostered_player_ids=rostered_player_ids,
            n_replacement=n_replacement,
        )
        frozen_pit = ctx.points_slot_replacement(
            year_pit_entries.get(start_year, []),
            active_slots=active_pitcher_slots,
            rostered_player_ids=rostered_player_ids,
            n_replacement=n_replacement,
        )
        for year in valuation_year_set:
            year_hit_replacement[year] = dict(frozen_hit)
            year_pit_replacement[year] = dict(frozen_pit)
    else:
        for year in valuation_year_set:
            year_hit_replacement[year] = ctx.points_slot_replacement(
                year_hit_entries.get(year, []),
                active_slots=active_hitter_slots,
                rostered_player_ids=rostered_player_ids,
                n_replacement=n_replacement,
            )
            year_pit_replacement[year] = ctx.points_slot_replacement(
                year_pit_entries.get(year, []),
                active_slots=active_pitcher_slots,
                rostered_player_ids=rostered_player_ids,
                n_replacement=n_replacement,
            )

    hitter_slot_capacity = _slot_capacity_by_league(hitter_slot_counts, teams=teams)
    pitcher_slot_capacity = _slot_capacity_by_league(pitcher_slot_counts, teams=teams)
    year_hit_assignments = {
        year: optimize_points_slot_assignment(
            year_hit_entries.get(year, []),
            replacement_by_slot=year_hit_replacement.get(year, {}),
            slot_capacity=hitter_slot_capacity,
        )
        for year in valuation_year_set
    }
    year_pit_assignments = {
        year: optimize_points_slot_assignment(
            year_pit_entries.get(year, []),
            replacement_by_slot=year_pit_replacement.get(year, {}),
            slot_capacity=pitcher_slot_capacity,
        )
        for year in valuation_year_set
    }

    player_year_details: dict[str, list[dict[str, object]]] = {}
    stash_scores_by_player: dict[str, float] = {}
    negative_year_players: set[str] = set()
    ir_candidate_players: set[str] = set()

    for player_id, meta_row in player_meta.items():
        year_details: list[dict[str, object]] = []

        for year in valuation_year_set:
            info = per_player_year.get(player_id, {}).get(year, {})
            hit_points = float(info.get("hit_points", 0.0))
            pit_points = float(info.get("pit_points", 0.0))
            raw_hit_points = float(info.get("raw_hit_points", 0.0))
            raw_pit_points = float(info.get("raw_pit_points", 0.0))
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))
            hit_breakdown = info.get("hit_breakdown") if isinstance(info.get("hit_breakdown"), dict) else empty_hit_breakdown
            pit_breakdown = info.get("pit_breakdown") if isinstance(info.get("pit_breakdown"), dict) else empty_pit_breakdown

            hit_repl_map = year_hit_replacement.get(year, {})
            pit_repl_map = year_pit_replacement.get(year, {})
            hit_best_value, hit_best_slot, hit_best_replacement = _best_slot_surplus(
                points=hit_points,
                eligible_slots=hit_slots,
                replacement_by_slot=hit_repl_map,
            )
            pit_best_value, pit_best_slot, pit_best_replacement = _best_slot_surplus(
                points=pit_points,
                eligible_slots=pit_slots,
                replacement_by_slot=pit_repl_map,
            )

            hit_assignment = year_hit_assignments.get(year, {}).get(player_id)
            pit_assignment = year_pit_assignments.get(year, {}).get(player_id)
            hit_assigned_slot = str(hit_assignment.get("slot")) if isinstance(hit_assignment, dict) else None
            pit_assigned_slot = str(pit_assignment.get("slot")) if isinstance(pit_assignment, dict) else None
            hit_assigned_value = float(hit_assignment.get("value", 0.0)) if isinstance(hit_assignment, dict) else 0.0
            pit_assigned_value = float(pit_assignment.get("value", 0.0)) if isinstance(pit_assignment, dict) else 0.0
            hit_assigned_points = float(hit_assignment.get("points", 0.0)) if isinstance(hit_assignment, dict) else 0.0
            pit_assigned_points = float(pit_assignment.get("points", 0.0)) if isinstance(pit_assignment, dict) else 0.0
            hit_assigned_replacement = float(hit_assignment.get("replacement", 0.0)) if isinstance(hit_assignment, dict) else 0.0
            pit_assigned_replacement = float(pit_assignment.get("replacement", 0.0)) if isinstance(pit_assignment, dict) else 0.0
            hit_selected_value = _negative_fallback_value(
                best_value=hit_best_value,
                assigned_slot=hit_assigned_slot,
                assigned_value=hit_assigned_value,
            )
            pit_selected_value = _negative_fallback_value(
                best_value=pit_best_value,
                assigned_slot=pit_assigned_slot,
                assigned_value=pit_assigned_value,
            )
            hit_selected_raw_points = (
                hit_assigned_points
                if hit_assigned_slot is not None
                else hit_points if hit_selected_value < 0.0 else 0.0
            )
            pit_selected_raw_points = (
                pit_assigned_points
                if pit_assigned_slot is not None
                else pit_points if pit_selected_value < 0.0 else 0.0
            )

            selected_side = "none"
            if two_way == "sum":
                year_points = hit_selected_value + pit_selected_value
                selected_raw_points = hit_selected_raw_points + pit_selected_raw_points
                if year_points > 0:
                    selected_side = "sum"
                elif year_points < 0:
                    selected_side = "sum_negative"
            else:
                if hit_selected_value > pit_selected_value:
                    year_points = hit_selected_value
                    selected_raw_points = hit_selected_raw_points
                    selected_side = "hitting" if hit_assigned_slot is not None else "hitting_negative"
                elif pit_selected_value > hit_selected_value:
                    year_points = pit_selected_value
                    selected_raw_points = pit_selected_raw_points
                    selected_side = "pitching" if pit_assigned_slot is not None else "pitching_negative"
                elif hit_selected_value != 0.0:
                    year_points = hit_selected_value
                    selected_raw_points = hit_selected_raw_points
                    selected_side = "hitting" if hit_assigned_slot is not None else "hitting_negative"
                else:
                    year_points = 0.0
                    selected_raw_points = 0.0

            year_details.append(
                {
                    "year": year,
                    "hitting_points": raw_hit_points if not hit_slots else hit_points,
                    "pitching_points": raw_pit_points if not pit_slots else pit_points,
                    "hitting_raw_points": raw_hit_points,
                    "pitching_raw_points": raw_pit_points,
                    "hitting_usage_share": float(info.get("hit_usage_share", 0.0)),
                    "pitching_usage_share": float(info.get("pit_usage_share", 0.0)),
                    "pitching_appearance_usage_share": float(info.get("pit_appearance_usage_share", 0.0)),
                    "pitching_ip_usage_share": float(info.get("pit_ip_usage_share", 0.0)),
                    "hitting_assigned_games": info.get("hit_assigned_games"),
                    "pitching_assigned_appearances": info.get("pit_assigned_appearances"),
                    "pitching_assigned_starts": info.get("pit_assigned_starts"),
                    "pitching_assigned_non_start_appearances": info.get("pit_assigned_non_start_appearances"),
                    "pitching_assigned_ip": info.get("pit_assigned_ip"),
                    "hitting_projected_games": float(info.get("projected_hit_games", 0.0)),
                    "pitching_projected_appearances": float(info.get("projected_pit_appearances", 0.0)),
                    "pitching_projected_starts": float(info.get("projected_pit_starts", 0.0)),
                    "pitching_projected_ip": float(info.get("projected_pit_ip", 0.0)),
                    "hitting_replacement": hit_best_replacement,
                    "pitching_replacement": pit_best_replacement,
                    "hitting_best_slot": hit_best_slot,
                    "pitching_best_slot": pit_best_slot,
                    "hitting_value": hit_best_value,
                    "pitching_value": pit_best_value,
                    "hitting_assignment_slot": hit_assigned_slot,
                    "pitching_assignment_slot": pit_assigned_slot,
                    "hitting_assignment_value": hit_assigned_value,
                    "pitching_assignment_value": pit_assigned_value,
                    "hitting_assignment_replacement": hit_assigned_replacement,
                    "pitching_assignment_replacement": pit_assigned_replacement,
                    "selected_side": selected_side,
                    "selected_raw_points": float(selected_raw_points),
                    "selected_points_unadjusted": float(year_points),
                    "hitting": hit_breakdown,
                    "pitching": pit_breakdown,
                }
            )

        ranking_values: list[float] = []
        has_negative_year = False
        has_ir_candidate_year = False
        for detail in year_details:
            year = int(detail["year"])
            raw_value = float(detail["selected_points_unadjusted"])
            if raw_value < 0.0:
                has_negative_year = True
                if _is_near_zero_playing_time(
                    player_id,
                    year,
                    hitter_ab_by_player_year=hitter_ab_by_player_year,
                    pitcher_ip_by_player_year=pitcher_ip_by_player_year,
                ):
                    has_ir_candidate_year = True
            ranking_values.append(
                raw_value
                * _prospect_risk_multiplier(
                    year=year,
                    start_year=start_year,
                    profile=player_profile.get(player_id, "hitter"),
                    minor_eligible=bool(minor_eligibility_by_year.get((player_id, year), False)),
                    enabled=enable_prospect_risk_adjustment,
                )
            )

        player_year_details[player_id] = year_details
        stash_scores_by_player[player_id] = dynasty_keep_or_drop_values(
            ranking_values,
            valuation_year_set,
            discount=float(discount),
        ).raw_total
        if has_negative_year:
            negative_year_players.add(player_id)
        if has_ir_candidate_year:
            ir_candidate_players.add(player_id)

    reserve_ranked_player_ids = [
        player_id
        for player_id, _score in sorted(
            stash_scores_by_player.items(),
            key=lambda item: (-float(item[1]), str(item[0])),
        )
        if player_id in in_season_rostered_player_ids
    ]
    used_reserve_players: set[str] = set()

    def _select_reserve_group(limit: int, candidates: set[str]) -> set[str]:
        selected: set[str] = set()
        for player_id in reserve_ranked_player_ids:
            if len(selected) >= max(int(limit), 0):
                break
            if player_id in used_reserve_players or player_id not in candidates:
                continue
            selected.add(player_id)
            used_reserve_players.add(player_id)
        return selected

    minor_candidate_players = {
        player_id
        for player_id in reserve_ranked_player_ids
        if any(bool(minor_eligibility_by_year.get((player_id, year), False)) for year in valuation_year_set)
    }
    minor_stash_players = _select_reserve_group(int(teams) * int(minors), minor_candidate_players)
    ir_stash_players = _select_reserve_group(int(teams) * int(ir), set(reserve_ranked_player_ids) & ir_candidate_players)
    bench_stash_players = _select_reserve_group(
        int(teams) * int(bench),
        set(reserve_ranked_player_ids) & negative_year_players,
    )

    result_rows: list[dict] = []
    for player_id, meta_row in player_meta.items():
        row_out: dict[str, object] = dict(meta_row)
        row_out["minor_eligible"] = bool(
            row_out.get("minor_eligible")
            or minor_eligibility_by_year.get((player_id, int(start_year)), False)
        )
        row_out["_ExplainPointsByYear"] = {}
        year_details = player_year_details.get(player_id, [])
        adjusted_values: list[float] = []

        for detail in year_details:
            year = int(detail["year"])
            adjusted_value = float(detail["selected_points_unadjusted"])
            adjusted_value *= _prospect_risk_multiplier(
                year=year,
                start_year=start_year,
                profile=player_profile.get(player_id, "hitter"),
                minor_eligible=bool(minor_eligibility_by_year.get((player_id, year), False)),
                enabled=enable_prospect_risk_adjustment,
            )
            adjusted_value = _apply_negative_value_stash_rules(
                adjusted_value,
                can_minor_stash=player_id in minor_stash_players and bool(minor_eligibility_by_year.get((player_id, year), False)),
                can_ir_stash=enable_ir_stash_relief
                and player_id in ir_stash_players
                and _is_near_zero_playing_time(
                    player_id,
                    year,
                    hitter_ab_by_player_year=hitter_ab_by_player_year,
                    pitcher_ip_by_player_year=pitcher_ip_by_player_year,
                ),
                ir_negative_penalty=ir_negative_penalty,
                can_bench_stash=enable_bench_stash_relief and player_id in bench_stash_players,
                bench_negative_penalty=bench_negative_penalty,
            )
            adjusted_values.append(adjusted_value)

        keep_drop = dynasty_keep_or_drop_values(adjusted_values, valuation_year_set, discount=float(discount))

        for idx, detail in enumerate(year_details):
            year = int(detail["year"])
            row_out[f"Value_{year}"] = float(adjusted_values[idx])
            row_out["_ExplainPointsByYear"][str(year)] = {
                "hitting_points": round(float(detail["hitting_points"]), 4),
                "pitching_points": round(float(detail["pitching_points"]), 4),
                "hitting_raw_points": round(float(detail["hitting_raw_points"]), 4),
                "pitching_raw_points": round(float(detail["pitching_raw_points"]), 4),
                "hitting_usage_share": round(float(detail["hitting_usage_share"]), 6),
                "pitching_usage_share": round(float(detail["pitching_usage_share"]), 6),
                "pitching_appearance_usage_share": round(float(detail["pitching_appearance_usage_share"]), 6),
                "pitching_ip_usage_share": round(float(detail["pitching_ip_usage_share"]), 6),
                "hitting_assigned_games": round(float(detail["hitting_assigned_games"]), 4)
                if detail["hitting_assigned_games"] is not None
                else None,
                "pitching_assigned_appearances": round(float(detail["pitching_assigned_appearances"]), 4)
                if detail["pitching_assigned_appearances"] is not None
                else None,
                "pitching_assigned_starts": round(float(detail["pitching_assigned_starts"]), 4)
                if detail["pitching_assigned_starts"] is not None
                else None,
                "pitching_assigned_non_start_appearances": round(float(detail["pitching_assigned_non_start_appearances"]), 4)
                if detail["pitching_assigned_non_start_appearances"] is not None
                else None,
                "pitching_assigned_ip": round(float(detail["pitching_assigned_ip"]), 4)
                if detail["pitching_assigned_ip"] is not None
                else None,
                "hitting_projected_games": round(float(detail["hitting_projected_games"]), 4),
                "pitching_projected_appearances": round(float(detail["pitching_projected_appearances"]), 4),
                "pitching_projected_starts": round(float(detail["pitching_projected_starts"]), 4),
                "pitching_projected_ip": round(float(detail["pitching_projected_ip"]), 4),
                "hitting_replacement": round(float(detail["hitting_replacement"]), 4)
                if detail["hitting_replacement"] is not None
                else None,
                "pitching_replacement": round(float(detail["pitching_replacement"]), 4)
                if detail["pitching_replacement"] is not None
                else None,
                "hitting_best_slot": detail["hitting_best_slot"],
                "pitching_best_slot": detail["pitching_best_slot"],
                "hitting_value": round(float(detail["hitting_value"]), 4) if detail["hitting_value"] is not None else None,
                "pitching_value": round(float(detail["pitching_value"]), 4) if detail["pitching_value"] is not None else None,
                "hitting_assignment_slot": detail["hitting_assignment_slot"],
                "pitching_assignment_slot": detail["pitching_assignment_slot"],
                "hitting_assignment_value": round(float(detail["hitting_assignment_value"]), 4),
                "pitching_assignment_value": round(float(detail["pitching_assignment_value"]), 4),
                "hitting_assignment_replacement": round(float(detail["hitting_assignment_replacement"]), 4)
                if detail["hitting_assignment_slot"] is not None
                else None,
                "pitching_assignment_replacement": round(float(detail["pitching_assignment_replacement"]), 4)
                if detail["pitching_assignment_slot"] is not None
                else None,
                "selected_side": detail["selected_side"],
                "selected_raw_points": round(float(detail["selected_raw_points"]), 4),
                "selected_points_unadjusted": round(float(detail["selected_points_unadjusted"]), 4),
                "selected_points": round(float(adjusted_values[idx]), 4),
                "discount_factor": round(float(keep_drop.discount_factors[idx]), 6),
                "discounted_contribution": round(float(keep_drop.discounted_contributions[idx]), 4),
                "keep_drop_value": round(float(keep_drop.continuation_values[idx]), 4),
                "keep_drop_hold_value": round(float(keep_drop.hold_values[idx]), 4),
                "keep_drop_keep": bool(keep_drop.keep_flags[idx]),
                "hitting": detail["hitting"],
                "pitching": detail["pitching"],
            }

        start_year_points = row_out["_ExplainPointsByYear"].get(str(start_year), {})
        if isinstance(start_year_points, dict):
            row_out["HittingPoints"] = start_year_points.get("hitting_points")
            row_out["PitchingPoints"] = start_year_points.get("pitching_points")
            row_out["SelectedPoints"] = start_year_points.get("selected_points")
            row_out["HittingBestSlot"] = start_year_points.get("hitting_best_slot")
            row_out["PitchingBestSlot"] = start_year_points.get("pitching_best_slot")
            row_out["HittingValue"] = start_year_points.get("hitting_value")
            row_out["PitchingValue"] = start_year_points.get("pitching_value")
            row_out["HittingAssignmentSlot"] = start_year_points.get("hitting_assignment_slot")
            row_out["PitchingAssignmentSlot"] = start_year_points.get("pitching_assignment_slot")
            row_out["HittingAssignmentValue"] = start_year_points.get("hitting_assignment_value")
            row_out["PitchingAssignmentValue"] = start_year_points.get("pitching_assignment_value")
            row_out["KeepDropValue"] = start_year_points.get("keep_drop_value")
            row_out["KeepDropHoldValue"] = start_year_points.get("keep_drop_hold_value")
            row_out["KeepDropKeep"] = start_year_points.get("keep_drop_keep")

        first_year_gap = (
            max(int(valuation_year_set[1]) - int(valuation_year_set[0]), 0)
            if len(valuation_year_set) > 1
            else 0
        )
        start_year_value = float(adjusted_values[0]) if adjusted_values else 0.0
        future_continuation_value = _future_continuation_value(keep_drop)
        row_out["RawDynastyValue"] = float(keep_drop.raw_total)
        row_out["StartYearValue"] = start_year_value
        row_out["FutureContinuationValue"] = future_continuation_value
        row_out["FutureContinuationDiscountGap"] = int(first_year_gap)
        result_rows.append(row_out)

    if not result_rows:
        empty_columns = [
            "Player",
            "Team",
            "Pos",
            "Age",
            "DynastyValue",
            "RawDynastyValue",
            "StartYearValue",
            "FutureContinuationValue",
            "FutureContinuationDiscountGap",
            "KeeperAdjustedFutureContinuationValue",
            "ForcedRosterValue",
            "CenteringScore",
            "CenteringMode",
            "ForcedRosterFallbackApplied",
            "CenteringBaselineValue",
            "CenteringScoreBaselineValue",
            "minor_eligible",
            ctx.player_key_col,
            ctx.player_entity_key_col,
        ] + [f"Value_{year}" for year in valuation_year_set]
        return pd.DataFrame(columns=empty_columns)

    out = pd.DataFrame.from_records(result_rows)
    raw_series = pd.to_numeric(out["RawDynastyValue"], errors="coerce").fillna(0.0)
    raw_baseline_value = _points_centering_baseline(
        out,
        score_col="RawDynastyValue",
        replacement_rank=replacement_rank,
        player_entity_key_col=ctx.player_entity_key_col,
        player_key_col=ctx.player_key_col,
    )
    future_continuation_baseline_value: float | None = None
    if keeper_continuation_rank is not None:
        future_continuation_baseline_value = _points_centering_baseline(
            out,
            score_col="FutureContinuationValue",
            replacement_rank=keeper_continuation_rank,
            player_entity_key_col=ctx.player_entity_key_col,
            player_key_col=ctx.player_key_col,
        )

    keeper_adjusted_future_continuation = pd.to_numeric(
        out["FutureContinuationValue"],
        errors="coerce",
    ).fillna(0.0)
    if future_continuation_baseline_value is not None:
        keeper_adjusted_future_continuation = keeper_adjusted_future_continuation - float(
            future_continuation_baseline_value
        )
    out["KeeperAdjustedFutureContinuationValue"] = keeper_adjusted_future_continuation.astype(float)
    out["ForcedRosterValue"] = (
        pd.to_numeric(out["StartYearValue"], errors="coerce").fillna(0.0)
        + pd.to_numeric(out["FutureContinuationDiscountGap"], errors="coerce").fillna(0.0).map(
            lambda gap: float(discount) ** int(max(gap, 0))
        )
        * keeper_adjusted_future_continuation
    )
    out["CenteringScore"] = raw_series.astype(float)

    raw_zero_mask = raw_series.abs() <= float(_POINTS_CENTERING_ZERO_EPSILON)
    raw_zero_value_count = int(raw_zero_mask.sum())
    raw_zero_share = (float(raw_zero_value_count) / float(len(out))) if len(out) else 0.0
    deep_roster_zero_baseline_warning = bool(
        abs(float(raw_baseline_value)) <= float(_POINTS_CENTERING_ZERO_EPSILON)
        and len(out) > 0
        and raw_zero_share >= float(_POINTS_DEEP_ROSTER_ZERO_CLUSTER_MIN_SHARE)
    )

    centering_mode = "standard"
    forced_roster_fallback_applied = False
    centering_score_baseline_value = float(raw_baseline_value)
    if deep_roster_zero_baseline_warning:
        out.loc[raw_zero_mask, "CenteringScore"] = pd.to_numeric(
            out.loc[raw_zero_mask, "ForcedRosterValue"],
            errors="coerce",
        ).fillna(0.0)
        centering_score_baseline_value = _points_centering_baseline(
            out,
            score_col="CenteringScore",
            replacement_rank=replacement_rank,
            player_entity_key_col=ctx.player_entity_key_col,
            player_key_col=ctx.player_key_col,
        )
        centering_mode = "forced_roster"
        forced_roster_fallback_applied = True

    out["DynastyValue"] = pd.to_numeric(out["CenteringScore"], errors="coerce").fillna(0.0) - float(
        centering_score_baseline_value
    )
    out["CenteringMode"] = centering_mode
    out["ForcedRosterFallbackApplied"] = forced_roster_fallback_applied
    out["CenteringBaselineValue"] = float(raw_baseline_value)
    out["CenteringScoreBaselineValue"] = float(centering_score_baseline_value)

    centering_score_series = pd.to_numeric(out["CenteringScore"], errors="coerce").fillna(0.0)
    dynasty_series = pd.to_numeric(out["DynastyValue"], errors="coerce").fillna(0.0)
    valuation_diagnostics: dict[str, object] = {
        "PointsValuationMode": points_valuation_mode,
        "KeeperLimit": int(keeper_limit) if keeper_limit is not None else None,
        "KeeperContinuationRank": int(keeper_continuation_rank) if keeper_continuation_rank is not None else None,
        "KeeperContinuationBaselineValue": (
            float(future_continuation_baseline_value)
            if future_continuation_baseline_value is not None
            else None
        ),
        "ReplacementRank": int(replacement_rank),
        "InSeasonReplacementRank": int(in_season_replacement_rank),
        "ActiveDepthPerTeam": int(active_depth_per_team),
        "InSeasonDepthPerTeam": int(in_season_depth_per_team),
        "CenteringMode": centering_mode,
        "ForcedRosterFallbackApplied": forced_roster_fallback_applied,
        "CenteringBaselineValue": float(raw_baseline_value),
        "CenteringScoreBaselineValue": float(centering_score_baseline_value),
        "RawZeroValuePlayerCount": int(raw_zero_value_count),
        "CenteringScoreZeroPlayerCount": int(
            (centering_score_series.abs() <= float(_POINTS_CENTERING_ZERO_EPSILON)).sum()
        ),
        "DynastyZeroValuePlayerCount": int((dynasty_series.abs() <= float(_POINTS_CENTERING_ZERO_EPSILON)).sum()),
        "PositiveValuePlayerCount": int((dynasty_series > float(_POINTS_CENTERING_ZERO_EPSILON)).sum()),
        "deep_roster_zero_baseline_warning": deep_roster_zero_baseline_warning,
        "HitterUsageByYear": {
            str(year): diagnostics
            for year, diagnostics in sorted(hitter_usage_diagnostics_by_year.items())
        },
        "PitcherUsageByYear": {
            str(year): diagnostics
            for year, diagnostics in sorted(pitcher_usage_diagnostics_by_year.items())
        },
    }
    if points_valuation_mode == "weekly_h2h":
        valuation_diagnostics.update(
            {
                "WeeklyStartsCap": weekly_starts_cap,
                "AllowSameDayStartsOverflow": bool(allow_same_day_starts_overflow),
                "WeeklyAcquisitionCap": weekly_acquisition_cap,
                "WeeklyPitchingByYear": {
                    str(year): diagnostics
                    for year, diagnostics in sorted(pitcher_usage_diagnostics_by_year.items())
                },
            }
        )
    if points_valuation_mode == "daily_h2h":
        valuation_diagnostics.update(
            {
                "WeeklyStartsCap": weekly_starts_cap,
                "AllowSameDayStartsOverflow": bool(allow_same_day_starts_overflow),
                "WeeklyAcquisitionCap": weekly_acquisition_cap,
                "SyntheticSeasonDays": int(SYNTHETIC_SEASON_DAYS),
                "SyntheticPeriodDays": int(SYNTHETIC_PERIOD_DAYS),
                "DailyPitchingByYear": {
                    str(year): diagnostics
                    for year, diagnostics in sorted(pitcher_usage_diagnostics_by_year.items())
                },
            }
        )
    out.attrs["valuation_diagnostics"] = valuation_diagnostics
    return out
