"""Points-mode dynasty calculation helpers and orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, cast

import pandas as pd

try:
    from backend.core.points_assignment import (
        _SEASON_WEEKS,
        _best_slot_surplus,
        _effective_weekly_starts_cap,
        _slot_capacity_by_league,
        optimize_points_slot_assignment,
    )
    from backend.core.points_output import (
        build_empty_points_value_frame,
        build_points_result_rows,
        calculate_points_raw_totals,
        finalize_points_dynasty_output,
        relief_pitcher_replacement_value,
        start_capable_pitcher_replacement_value,
    )
    from backend.core.points_roster_model import (
        POINTS_CENTERING_ZERO_EPSILON,
        active_points_roster_ids,
        is_h2h_points_mode,
        model_h2h_points_roster,
        modeled_bench_hitter_slots_per_team,
        per_day_slot_capacity,
        select_points_stash_groups,
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
        allocate_hitter_usage_daily_detail,
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
    from points_output import (  # type: ignore[no-redef]
        build_empty_points_value_frame,
        build_points_result_rows,
        calculate_points_raw_totals,
        finalize_points_dynasty_output,
        relief_pitcher_replacement_value,
        start_capable_pitcher_replacement_value,
    )
    from points_roster_model import (  # type: ignore[no-redef]
        POINTS_CENTERING_ZERO_EPSILON,
        active_points_roster_ids,
        is_h2h_points_mode,
        model_h2h_points_roster,
        modeled_bench_hitter_slots_per_team,
        per_day_slot_capacity,
        select_points_stash_groups,
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
        allocate_hitter_usage_daily_detail,
        allocate_pitcher_innings_budget,
        allocate_pitcher_usage,
        allocate_pitcher_usage_daily,
        annual_slot_capacity,
    )
    from valuation.minor_eligibility import _resolve_minor_eligibility_by_year  # type: ignore[no-redef]
    from valuation.models import CommonDynastyRotoSettings  # type: ignore[no-redef]


@dataclass(slots=True)
class PointsCalculatorContext:
    bat_data: list[dict[str, Any]]
    pit_data: list[dict[str, Any]]
    bat_data_raw: list[dict[str, Any]]
    pit_data_raw: list[dict[str, Any]]
    meta: dict[str, Any]
    average_recent_projection_rows: Callable[..., list[dict[str, Any]]]
    coerce_meta_years: Callable[[dict[str, Any]], list[int]]
    valuation_years: Callable[[int, int, list[int]], list[int]]
    coerce_record_year: Callable[[object], int | None]
    points_player_identity: Callable[[dict[str, Any]], str]
    normalize_player_key: Callable[[object], str]
    player_key_col: str
    player_entity_key_col: str
    row_team_value: Callable[[dict[str, Any]], str]
    merge_position_value: Callable[[object, object], str | None]
    coerce_minor_eligible: Callable[[object], bool]
    calculate_hitter_points_breakdown: Callable[[dict[str, Any] | None, dict[str, float]], dict[str, Any]]
    calculate_pitcher_points_breakdown: Callable[[dict[str, Any] | None, dict[str, float]], dict[str, Any]]
    stat_or_zero: Callable[[dict[str, Any] | None, str], float]
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
        "pts_hit_1b": float(pts_hit_1b), "pts_hit_2b": float(pts_hit_2b), "pts_hit_3b": float(pts_hit_3b),
        "pts_hit_hr": float(pts_hit_hr), "pts_hit_r": float(pts_hit_r), "pts_hit_rbi": float(pts_hit_rbi),
        "pts_hit_sb": float(pts_hit_sb), "pts_hit_bb": float(pts_hit_bb), "pts_hit_hbp": float(pts_hit_hbp),
        "pts_hit_so": float(pts_hit_so), "pts_pit_ip": float(pts_pit_ip), "pts_pit_w": float(pts_pit_w),
        "pts_pit_l": float(pts_pit_l), "pts_pit_k": float(pts_pit_k), "pts_pit_sv": float(pts_pit_sv),
        "pts_pit_hld": float(pts_pit_hld), "pts_pit_h": float(pts_pit_h), "pts_pit_er": float(pts_pit_er),
        "pts_pit_bb": float(pts_pit_bb), "pts_pit_hbp": float(pts_pit_hbp),
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
        hit_c + hit_1b + hit_2b + hit_3b + hit_ss + hit_ci + hit_mi + hit_of + hit_dh + hit_ut + pit_p + pit_sp + pit_rp
    )
    active_depth_per_team = max(1, active_slots_per_team)
    in_season_depth_per_team = max(1, active_slots_per_team + bench + minors + ir)
    default_replacement_rank = max(1, teams * in_season_depth_per_team)
    replacement_rank = default_replacement_rank
    in_season_replacement_rank = default_replacement_rank
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
    use_h2h_roster_model = is_h2h_points_mode(points_valuation_mode)
    keeper_continuation_horizon_years = 3 if use_h2h_roster_model and keeper_limit is not None else None

    player_meta: dict[str, dict[str, Any]] = {}
    per_player_year: dict[str, dict[int, dict[str, Any]]] = {}
    year_hit_entries: dict[int, list[dict[str, Any]]] = {year: [] for year in valuation_year_set}
    year_pit_entries: dict[int, list[dict[str, Any]]] = {year: [] for year in valuation_year_set}
    player_profile: dict[str, str] = {}
    hitter_usage_diagnostics_by_year: dict[int, dict[str, object]] = {}
    pitcher_usage_diagnostics_by_year: dict[int, dict[str, object]] = {}
    modeled_bench_hitters_per_team_by_year: dict[int, int] = {}
    modeled_bench_pitchers_per_team_by_year: dict[int, int] = {}
    modeled_held_pitchers_per_team_by_year: dict[int, int] = {}
    modeled_held_starter_pitchers_per_team_by_year: dict[int, int] = {}
    modeled_held_relievers_per_team_by_year: dict[int, int] = {}
    year_active_hitter_player_ids: dict[int, set[str]] = {}
    year_start_capable_pitcher_ids: dict[int, set[str]] = {}
    year_relief_pitcher_ids: dict[int, set[str]] = {}
    year_active_pitcher_player_ids: dict[int, set[str]] = {}
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
    h2h_daily_hitter_slot_capacity = annual_slot_capacity(
        hitter_slot_counts,
        teams=teams,
        season_capacity_per_slot=float(SYNTHETIC_SEASON_DAYS),
    )
    h2h_hitter_coverage_slot_capacity = annual_slot_capacity(
        hitter_slot_counts,
        teams=teams,
        season_capacity_per_slot=162.0,
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

        year_map: dict[int, dict[str, Any]] = {}

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
        year_start_capable_pitcher_ids[year] = {
            player_id
            for player_id, projected_starts in pitcher_start_volume.items()
            if float(projected_starts) >= 1.0
        }
        year_relief_pitcher_ids[year] = set(pitcher_start_volume.keys()) - set(year_start_capable_pitcher_ids[year])

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
        reserve_hitter_usage = hitter_usage
        if use_h2h_roster_model:
            reserve_hitter_usage = allocate_hitter_usage_daily_detail(
                hitter_entries,
                slot_capacity=h2h_daily_hitter_slot_capacity,
            ).allocation
        reserve_hitter_assignment_entries: list[dict[str, Any]] = []
        active_hitter_ids_for_bench: set[str] = set()
        if use_h2h_roster_model:
            for player_id, year_map in per_player_year.items():
                info = year_map.get(year, {})
                hit_slots = set(info.get("hit_slots", set()))
                if not hit_slots:
                    continue
                raw_hit_points = float(info.get("raw_hit_points", 0.0))
                reserve_hit_share = (
                    1.0 if player_id in fallback_hitter_ids else float(reserve_hitter_usage.usage_share_by_player.get(player_id, 0.0))
                )
                reserve_hit_share = float(min(max(reserve_hit_share, 0.0), 1.0))
                reserve_hitter_assignment_entries.append(
                    {
                        "player_id": player_id,
                        "points": float(raw_hit_points * reserve_hit_share),
                        "slots": set(hit_slots),
                    }
                )
            active_hitter_ids_for_bench = active_points_roster_ids(
                reserve_hitter_assignment_entries,
                slot_counts=hitter_slot_counts,
                teams=teams,
            )
            year_active_hitter_player_ids[year] = set(active_hitter_ids_for_bench)

        effective_weekly_cap: float | None = None
        capped_start_budget: float | None = None
        held_pitcher_ids: set[str] | None = None
        streaming_adds_per_period: int | None = None
        modeled_bench_hitters_per_team = 0
        modeled_bench_pitchers_per_team = 0
        modeled_held_pitchers_per_team = max(int(starter_slot_capacity), 0)
        if points_valuation_mode == "daily_h2h" and weekly_acquisition_cap is not None:
            streaming_adds_per_period = max(int(weekly_acquisition_cap), 0) * max(int(teams), 1)
        if points_valuation_mode == "weekly_h2h":
            effective_weekly_cap = _effective_weekly_starts_cap(
                weekly_starts_cap,
                allow_same_day_starts_overflow=allow_same_day_starts_overflow,
                starter_slot_capacity=starter_slot_capacity,
            )
            if effective_weekly_cap is not None and effective_weekly_cap > 0.0:
                capped_start_budget = float(effective_weekly_cap) * _SEASON_WEEKS * max(int(teams), 1)
        elif points_valuation_mode == "daily_h2h" and weekly_starts_cap is not None and int(weekly_starts_cap) > 0:
            capped_start_budget = float(max(int(weekly_starts_cap), 0)) * _SEASON_WEEKS * max(int(teams), 1)
        if use_h2h_roster_model:
            per_day_hitter_capacity = per_day_slot_capacity(
                h2h_hitter_coverage_slot_capacity,
                total_days=162,
            )
            active_hitter_coverage_detail = allocate_hitter_usage_daily_detail(
                [entry for entry in hitter_entries if entry.player_id in active_hitter_ids_for_bench],
                slot_capacity=h2h_hitter_coverage_slot_capacity,
                total_days=162,
            )
            uncovered_hitter_games_by_day: dict[int, float] = {}
            for day in range(162):
                day_assigned = active_hitter_coverage_detail.assigned_by_day_slot.get(day, {})
                day_uncovered = {
                    slot: max(
                        int(per_day_hitter_capacity.get(slot, 0) - int(round(day_assigned.get(slot, 0.0)))),
                        0,
                    )
                    for slot in per_day_hitter_capacity
                }
                uncovered_hitter_games_by_day[day] = float(sum(day_uncovered.values()))
            modeled_bench_hitters_per_team = modeled_bench_hitter_slots_per_team(
                reserve_assigned_games_by_day=uncovered_hitter_games_by_day,
                teams=teams,
                bench_slots=bench,
            )
            modeled_bench_pitchers_per_team = max(int(bench) - modeled_bench_hitters_per_team, 0)
            modeled_held_pitchers_per_team = max(
                int(starter_slot_capacity) + modeled_bench_pitchers_per_team,
                0,
            )
            if points_valuation_mode == "daily_h2h":
                held_pitcher_budget = max(int(teams), 1) * max(int(modeled_held_pitchers_per_team), 0)
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
            modeled_bench_hitters_per_team_by_year[year] = modeled_bench_hitters_per_team
            modeled_bench_pitchers_per_team_by_year[year] = modeled_bench_pitchers_per_team
            modeled_held_pitchers_per_team_by_year[year] = modeled_held_pitchers_per_team

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
                allow_same_day_starts_overflow=allow_same_day_starts_overflow,
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
            "modeled_bench_hitters_per_team": (
                int(modeled_bench_hitters_per_team) if use_h2h_roster_model else None
            ),
            "modeled_bench_pitchers_per_team": (
                int(modeled_bench_pitchers_per_team) if use_h2h_roster_model else None
            ),
        }
        pitcher_diag: dict[str, object] = {
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
            "selected_overflow_starts": round(float(pitcher_usage.selected_overflow_starts), 4)
            if pitcher_usage.selected_overflow_starts is not None
            else None,
            "effective_period_start_cap": round(float(pitcher_usage.effective_period_start_cap), 4)
            if pitcher_usage.effective_period_start_cap is not None
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
            "modeled_bench_hitters_per_team": (
                int(modeled_bench_hitters_per_team) if use_h2h_roster_model else None
            ),
            "modeled_bench_pitchers_per_team": (
                int(modeled_bench_pitchers_per_team) if use_h2h_roster_model else None
            ),
            "modeled_held_pitchers_per_team": (
                int(modeled_held_pitchers_per_team) if use_h2h_roster_model else None
            ),
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

            raw_hit_breakdown_src = info.get("raw_hit_breakdown")
            hit_breakdown = _scale_points_breakdown(cast(dict[str, Any], raw_hit_breakdown_src) if isinstance(raw_hit_breakdown_src, dict) else empty_hit_breakdown, hit_share)
            raw_pit_breakdown_src = info.get("raw_pit_breakdown")
            pit_breakdown = _scale_points_breakdown(cast(dict[str, Any], raw_pit_breakdown_src) if isinstance(raw_pit_breakdown_src, dict) else empty_pit_breakdown, pit_share)
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
        if use_h2h_roster_model:
            year_active_pitcher_player_ids[year] = active_points_roster_ids(
                year_pit_entries[year],
                slot_counts=pitcher_slot_counts,
                teams=teams,
            )

    player_raw_totals = calculate_points_raw_totals(
        per_player_year=per_player_year,
        valuation_year_set=valuation_year_set,
        discount=float(discount),
        two_way=two_way,
    )

    if not player_meta:
        return build_empty_points_value_frame(
            valuation_year_set=valuation_year_set,
            player_key_col=ctx.player_key_col,
            player_entity_key_col=ctx.player_entity_key_col,
        )

    ranked_players = sorted(
        player_raw_totals.items(),
        key=lambda item: (-float(item[1]), str(item[0])),
    )
    rostered_player_ids = {player_id for player_id, _score in ranked_players[:replacement_rank]}
    in_season_rostered_player_ids = {
        player_id for player_id, _score in ranked_players[:in_season_replacement_rank]
    }
    modeled_ir_roster_ids: set[str] = set()
    modeled_minor_roster_ids: set[str] = set()
    held_starter_pitcher_ids: set[str] = set()
    if use_h2h_roster_model:
        h2h_roster_model = model_h2h_points_roster(
            start_year=start_year,
            points_valuation_mode=points_valuation_mode,
            teams=teams,
            active_slots_per_team=active_slots_per_team,
            bench=bench,
            year_hit_entries=year_hit_entries,
            year_pit_entries=year_pit_entries,
            hitter_slot_counts=hitter_slot_counts,
            pitcher_slot_counts=pitcher_slot_counts,
            modeled_bench_hitters_per_team_by_year=modeled_bench_hitters_per_team_by_year,
            modeled_bench_pitchers_per_team_by_year=modeled_bench_pitchers_per_team_by_year,
            year_active_pitcher_player_ids=year_active_pitcher_player_ids,
            year_start_capable_pitcher_ids=year_start_capable_pitcher_ids,
            pitcher_usage_diagnostics_by_year=pitcher_usage_diagnostics_by_year,
            default_rostered_player_ids=rostered_player_ids,
            default_in_season_rostered_player_ids=in_season_rostered_player_ids,
            default_replacement_rank=replacement_rank,
            default_in_season_replacement_rank=in_season_replacement_rank,
        )
        rostered_player_ids = set(h2h_roster_model.rostered_player_ids)
        in_season_rostered_player_ids = set(h2h_roster_model.in_season_rostered_player_ids)
        replacement_rank = int(h2h_roster_model.replacement_rank)
        in_season_replacement_rank = int(h2h_roster_model.in_season_replacement_rank)
        held_starter_pitcher_ids = set(h2h_roster_model.held_starter_pitcher_ids)
        modeled_held_starter_pitchers_per_team_by_year[start_year] = int(
            h2h_roster_model.modeled_held_starter_pitchers_per_team
        )
        modeled_held_relievers_per_team_by_year[start_year] = int(
            h2h_roster_model.modeled_held_relievers_per_team
        )

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

    starter_pitcher_replacement_start_year: float | None = None
    reliever_pitcher_replacement_start_year: float | None = None
    use_start_capable_pitcher_replacement = bool(use_h2h_roster_model and active_pitcher_slots == {"P"})
    if use_start_capable_pitcher_replacement:
        starter_replacement_rostered_ids = (
            set(held_starter_pitcher_ids) if use_h2h_roster_model else set(rostered_player_ids)
        )
        starter_pitcher_replacement_start_year = start_capable_pitcher_replacement_value(
            points_slot_replacement=ctx.points_slot_replacement,
            year_pit_entries=year_pit_entries,
            start_year=start_year,
            year_start_capable_pitcher_ids=year_start_capable_pitcher_ids,
            starter_replacement_rostered_ids=starter_replacement_rostered_ids,
            n_replacement=n_replacement,
        )
        reliever_replacement_rostered_ids = (
            set(year_active_pitcher_player_ids.get(start_year, set()))
            - set(year_start_capable_pitcher_ids.get(start_year, set()))
        )
        reliever_pitcher_replacement_start_year = relief_pitcher_replacement_value(
            points_slot_replacement=ctx.points_slot_replacement,
            year_pit_entries=year_pit_entries,
            start_year=start_year,
            year_relief_pitcher_ids=year_relief_pitcher_ids,
            reliever_replacement_rostered_ids=reliever_replacement_rostered_ids,
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

    keeper_start_year_value_by_player: dict[str, float] = {}
    if use_h2h_roster_model and keeper_limit is not None:
        keeper_hit_replacement = ctx.points_slot_replacement(
            year_hit_entries.get(start_year, []),
            active_slots=active_hitter_slots,
            rostered_player_ids=year_active_hitter_player_ids.get(start_year, set()),
            n_replacement=n_replacement,
        )
        keeper_pit_replacement = ctx.points_slot_replacement(
            year_pit_entries.get(start_year, []),
            active_slots=active_pitcher_slots,
            rostered_player_ids=year_active_pitcher_player_ids.get(start_year, set()),
            n_replacement=n_replacement,
        )
        keeper_start_capable_pitcher_replacement: float | None = None
        keeper_relief_pitcher_replacement: float | None = None
        if active_pitcher_slots == {"P"}:
            keeper_start_capable_pitcher_replacement = start_capable_pitcher_replacement_value(
                points_slot_replacement=ctx.points_slot_replacement,
                year_pit_entries=year_pit_entries,
                start_year=start_year,
                year_start_capable_pitcher_ids=year_start_capable_pitcher_ids,
                starter_replacement_rostered_ids=(
                    set(year_active_pitcher_player_ids.get(start_year, set()))
                    & set(year_start_capable_pitcher_ids.get(start_year, set()))
                ),
                n_replacement=n_replacement,
            )
            keeper_relief_pitcher_replacement = relief_pitcher_replacement_value(
                points_slot_replacement=ctx.points_slot_replacement,
                year_pit_entries=year_pit_entries,
                start_year=start_year,
                year_relief_pitcher_ids=year_relief_pitcher_ids,
                reliever_replacement_rostered_ids=(
                    set(year_active_pitcher_player_ids.get(start_year, set()))
                    - set(year_start_capable_pitcher_ids.get(start_year, set()))
                ),
                n_replacement=n_replacement,
            )
        keeper_hit_assignments = optimize_points_slot_assignment(
            year_hit_entries.get(start_year, []),
            replacement_by_slot=keeper_hit_replacement,
            slot_capacity=hitter_slot_capacity,
        )
        keeper_pit_assignments = optimize_points_slot_assignment(
            year_pit_entries.get(start_year, []),
            replacement_by_slot=keeper_pit_replacement,
            slot_capacity=pitcher_slot_capacity,
        )
        for player_id in player_meta:
            info = per_player_year.get(player_id, {}).get(start_year, {})
            hit_points = float(info.get("hit_points", 0.0))
            pit_points = float(info.get("pit_points", 0.0))
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))

            hit_best_value, _hit_best_slot, _hit_best_replacement = _best_slot_surplus(
                points=hit_points,
                eligible_slots=hit_slots,
                replacement_by_slot=keeper_hit_replacement,
            )
            pit_best_value, pit_best_slot, pit_best_replacement = _best_slot_surplus(
                points=pit_points,
                eligible_slots=pit_slots,
                replacement_by_slot=keeper_pit_replacement,
            )
            hit_assignment = keeper_hit_assignments.get(player_id)
            pit_assignment = keeper_pit_assignments.get(player_id)
            hit_assigned_slot = str(hit_assignment.get("slot")) if isinstance(hit_assignment, dict) else None
            pit_assigned_slot = str(pit_assignment.get("slot")) if isinstance(pit_assignment, dict) else None
            hit_assigned_value = float(hit_assignment.get("value", 0.0)) if isinstance(hit_assignment, dict) else 0.0
            pit_assigned_value = float(pit_assignment.get("value", 0.0)) if isinstance(pit_assignment, dict) else 0.0
            pit_assigned_points = float(pit_assignment.get("points", 0.0)) if isinstance(pit_assignment, dict) else 0.0
            pit_assigned_replacement = float(pit_assignment.get("replacement", 0.0)) if isinstance(pit_assignment, dict) else 0.0
            projected_pit_appearances = float(info.get("projected_pit_appearances", 0.0))
            projected_pit_starts = float(info.get("projected_pit_starts", 0.0))
            if (
                keeper_start_capable_pitcher_replacement is not None
                and projected_pit_starts >= 1.0
                and keeper_start_capable_pitcher_replacement > POINTS_CENTERING_ZERO_EPSILON
            ):
                if (
                    pit_best_slot == "P"
                    and keeper_start_capable_pitcher_replacement
                    < (float(pit_best_replacement or 0.0) - POINTS_CENTERING_ZERO_EPSILON)
                ):
                    pit_best_replacement = float(keeper_start_capable_pitcher_replacement)
                    pit_best_value = float(pit_points - pit_best_replacement)
                if (
                    pit_assigned_slot == "P"
                    and keeper_start_capable_pitcher_replacement
                    < (float(pit_assigned_replacement) - POINTS_CENTERING_ZERO_EPSILON)
                ):
                    pit_assigned_replacement = float(keeper_start_capable_pitcher_replacement)
                    pit_assigned_value = float(pit_assigned_points - pit_assigned_replacement)
            elif (
                keeper_relief_pitcher_replacement is not None
                and projected_pit_appearances > 0.0
                and projected_pit_starts < 1.0
                and keeper_relief_pitcher_replacement > POINTS_CENTERING_ZERO_EPSILON
            ):
                if (
                    pit_best_slot == "P"
                    and keeper_relief_pitcher_replacement
                    < (float(pit_best_replacement or 0.0) - POINTS_CENTERING_ZERO_EPSILON)
                ):
                    pit_best_replacement = float(keeper_relief_pitcher_replacement)
                    pit_best_value = float(pit_points - pit_best_replacement)
                if (
                    pit_assigned_slot == "P"
                    and keeper_relief_pitcher_replacement
                    < (float(pit_assigned_replacement) - POINTS_CENTERING_ZERO_EPSILON)
                ):
                    pit_assigned_replacement = float(keeper_relief_pitcher_replacement)
                    pit_assigned_value = float(pit_assigned_points - pit_assigned_replacement)
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
            if two_way == "sum":
                keeper_start_year_value_by_player[player_id] = float(hit_selected_value + pit_selected_value)
            else:
                if hit_selected_value > pit_selected_value:
                    keeper_start_year_value_by_player[player_id] = float(hit_selected_value)
                elif pit_selected_value > hit_selected_value:
                    keeper_start_year_value_by_player[player_id] = float(pit_selected_value)
                elif hit_selected_value != 0.0:
                    keeper_start_year_value_by_player[player_id] = float(hit_selected_value)
                else:
                    keeper_start_year_value_by_player[player_id] = 0.0

    player_year_details: dict[str, list[dict[str, Any]]] = {}
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
            hit_breakdown = cast(dict[str, Any], info.get("hit_breakdown")) if isinstance(info.get("hit_breakdown"), dict) else empty_hit_breakdown
            pit_breakdown = cast(dict[str, Any], info.get("pit_breakdown")) if isinstance(info.get("pit_breakdown"), dict) else empty_pit_breakdown

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
            projected_pit_appearances = float(info.get("projected_pit_appearances", 0.0))
            projected_pit_starts = float(info.get("projected_pit_starts", 0.0))
            if (
                starter_pitcher_replacement_start_year is not None
                and projected_pit_starts >= 1.0
                and starter_pitcher_replacement_start_year > POINTS_CENTERING_ZERO_EPSILON
            ):
                if (
                    pit_best_slot == "P"
                    and starter_pitcher_replacement_start_year
                    < (float(pit_best_replacement or 0.0) - POINTS_CENTERING_ZERO_EPSILON)
                ):
                    pit_best_replacement = float(starter_pitcher_replacement_start_year)
                    pit_best_value = float(pit_points - pit_best_replacement)
                if (
                    pit_assigned_slot == "P"
                    and starter_pitcher_replacement_start_year
                    < (float(pit_assigned_replacement) - POINTS_CENTERING_ZERO_EPSILON)
                ):
                    pit_assigned_replacement = float(starter_pitcher_replacement_start_year)
                    pit_assigned_value = float(pit_assigned_points - pit_assigned_replacement)
            elif (
                reliever_pitcher_replacement_start_year is not None
                and projected_pit_appearances > 0.0
                and projected_pit_starts < 1.0
                and reliever_pitcher_replacement_start_year > POINTS_CENTERING_ZERO_EPSILON
            ):
                if (
                    pit_best_slot == "P"
                    and reliever_pitcher_replacement_start_year
                    < (float(pit_best_replacement or 0.0) - POINTS_CENTERING_ZERO_EPSILON)
                ):
                    pit_best_replacement = float(reliever_pitcher_replacement_start_year)
                    pit_best_value = float(pit_points - pit_best_replacement)
                if (
                    pit_assigned_slot == "P"
                    and reliever_pitcher_replacement_start_year
                    < (float(pit_assigned_replacement) - POINTS_CENTERING_ZERO_EPSILON)
                ):
                    pit_assigned_replacement = float(reliever_pitcher_replacement_start_year)
                    pit_assigned_value = float(pit_assigned_points - pit_assigned_replacement)
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
            typed_detail = cast(dict[str, Any], detail)
            year = int(cast(Any, typed_detail["year"]))
            raw_value = float(cast(Any, typed_detail["selected_points_unadjusted"]))
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
            continuation_horizon_years=keeper_continuation_horizon_years,
        ).raw_total
        if has_negative_year:
            negative_year_players.add(player_id)
        if has_ir_candidate_year:
            ir_candidate_players.add(player_id)

    stash_selection = select_points_stash_groups(
        stash_scores_by_player=stash_scores_by_player,
        use_h2h_roster_model=use_h2h_roster_model,
        in_season_rostered_player_ids=in_season_rostered_player_ids,
        in_season_replacement_rank=in_season_replacement_rank,
        minor_eligibility_by_year=minor_eligibility_by_year,
        valuation_year_set=valuation_year_set,
        start_year=start_year,
        teams=teams,
        minors=minors,
        ir=ir,
        bench=bench,
        ir_candidate_players=ir_candidate_players,
        negative_year_players=negative_year_players,
        hitter_ab_by_player_year=hitter_ab_by_player_year,
        pitcher_ip_by_player_year=pitcher_ip_by_player_year,
    )
    modeled_minor_roster_ids = set(stash_selection.modeled_minor_roster_ids)
    modeled_ir_roster_ids = set(stash_selection.modeled_ir_roster_ids)
    in_season_rostered_player_ids = set(stash_selection.in_season_rostered_player_ids)
    in_season_replacement_rank = int(stash_selection.in_season_replacement_rank)

    result_rows = build_points_result_rows(
        player_meta=player_meta,
        player_year_details=player_year_details,
        player_profile=player_profile,
        minor_eligibility_by_year=minor_eligibility_by_year,
        start_year=start_year,
        valuation_year_set=valuation_year_set,
        discount=float(discount),
        continuation_horizon_years=keeper_continuation_horizon_years,
        keeper_start_year_value_by_player=keeper_start_year_value_by_player,
        enable_prospect_risk_adjustment=enable_prospect_risk_adjustment,
        minor_stash_players=set(stash_selection.minor_stash_players),
        ir_stash_players=set(stash_selection.ir_stash_players),
        bench_stash_players=set(stash_selection.bench_stash_players),
        enable_ir_stash_relief=enable_ir_stash_relief,
        ir_negative_penalty=float(ir_negative_penalty),
        enable_bench_stash_relief=enable_bench_stash_relief,
        bench_negative_penalty=float(bench_negative_penalty),
        hitter_ab_by_player_year=hitter_ab_by_player_year,
        pitcher_ip_by_player_year=pitcher_ip_by_player_year,
    )

    return finalize_points_dynasty_output(
        result_rows=result_rows,
        valuation_year_set=valuation_year_set,
        player_key_col=ctx.player_key_col,
        player_entity_key_col=ctx.player_entity_key_col,
        rostered_player_ids=rostered_player_ids,
        replacement_rank=replacement_rank,
        in_season_replacement_rank=in_season_replacement_rank,
        active_depth_per_team=active_depth_per_team,
        in_season_depth_per_team=in_season_depth_per_team,
        discount=float(discount),
        keeper_limit=keeper_limit,
        keeper_continuation_rank=keeper_continuation_rank,
        points_valuation_mode=points_valuation_mode,
        weekly_starts_cap=weekly_starts_cap,
        allow_same_day_starts_overflow=allow_same_day_starts_overflow,
        weekly_acquisition_cap=weekly_acquisition_cap,
        use_h2h_roster_model=use_h2h_roster_model,
        modeled_ir_roster_ids=modeled_ir_roster_ids,
        modeled_minor_roster_ids=modeled_minor_roster_ids,
        modeled_bench_hitters_per_team_by_year=modeled_bench_hitters_per_team_by_year,
        modeled_bench_pitchers_per_team_by_year=modeled_bench_pitchers_per_team_by_year,
        modeled_held_pitchers_per_team_by_year=modeled_held_pitchers_per_team_by_year,
        modeled_held_starter_pitchers_per_team_by_year=modeled_held_starter_pitchers_per_team_by_year,
        modeled_held_relievers_per_team_by_year=modeled_held_relievers_per_team_by_year,
        starter_slot_capacity=starter_slot_capacity,
        starter_pitcher_replacement_start_year=starter_pitcher_replacement_start_year,
        reliever_pitcher_replacement_start_year=reliever_pitcher_replacement_start_year,
        hitter_usage_diagnostics_by_year=hitter_usage_diagnostics_by_year,
        pitcher_usage_diagnostics_by_year=pitcher_usage_diagnostics_by_year,
        start_year=start_year,
        teams=teams,
    )
