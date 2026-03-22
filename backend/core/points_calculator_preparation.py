"""Preparation helpers for points-mode dynasty calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd


@dataclass(slots=True)
class PointsPreparationResult:
    scoring: dict[str, float]
    valuation_year_set: list[int]
    minor_eligibility_by_year: dict[tuple[str, int], bool]
    hitter_ab_by_player_year: dict[tuple[str, int], float]
    pitcher_ip_by_player_year: dict[tuple[str, int], float]
    player_meta: dict[str, dict[str, Any]]
    per_player_year: dict[str, dict[int, dict[str, Any]]]
    player_profile: dict[str, str]
    active_slots_per_team: int
    active_depth_per_team: int
    in_season_depth_per_team: int
    default_replacement_rank: int
    replacement_rank: int
    in_season_replacement_rank: int
    keeper_continuation_rank: int | None
    hitter_slot_counts: dict[str, int]
    pitcher_slot_counts: dict[str, int]
    active_hitter_slots: set[str]
    active_pitcher_slots: set[str]
    starter_slot_capacity: int
    n_replacement: int
    freeze_replacement_baselines: bool
    use_h2h_roster_model: bool
    keeper_continuation_horizon_years: int | None
    empty_hit_breakdown: dict[str, Any]
    empty_pit_breakdown: dict[str, Any]
    annual_hitter_slot_capacity: dict[str, float]
    annual_pitcher_slot_capacity: dict[str, float]
    h2h_daily_hitter_slot_capacity: dict[str, float]
    h2h_hitter_coverage_slot_capacity: dict[str, float]


def build_points_scoring(
    *,
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
) -> dict[str, float]:
    return {
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


def prepare_points_calculation(
    *,
    ctx: Any,
    scoring: dict[str, float],
    teams: int,
    horizon: int,
    keeper_limit: int | None,
    points_valuation_mode: str,
    bench: int,
    minors: int,
    ir: int,
    start_year: int,
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
    hit_dh: int,
    common_settings_factory: Callable[[], Any],
    resolve_minor_eligibility_by_year: Callable[..., pd.DataFrame],
    is_h2h_points_mode: Callable[[str], bool],
    annual_slot_capacity: Callable[..., dict[str, float]],
    synthetic_season_days: int,
) -> PointsPreparationResult:
    bat_rows = ctx.bat_data
    pit_rows = ctx.pit_data

    valid_years = ctx.coerce_meta_years(ctx.meta)
    valuation_year_set = ctx.valuation_years(start_year, horizon, valid_years)
    year_set = set(valuation_year_set)

    if not valuation_year_set:
        raise ValueError("No valuation years available for selected start_year and horizon.")

    minor_defaults = common_settings_factory()
    bat_minor_rows = [{**row, "Player": ctx.points_player_identity(row)} for row in bat_rows]
    pit_minor_rows = [{**row, "Player": ctx.points_player_identity(row)} for row in pit_rows]
    minor_eligibility_frame = resolve_minor_eligibility_by_year(
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

    rows_by_player: dict[str, dict[int, dict[str, dict[str, Any] | None]]] = {}
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
    player_profile: dict[str, str] = {}
    empty_hit_breakdown = ctx.calculate_hitter_points_breakdown(None, scoring)
    empty_pit_breakdown = ctx.calculate_pitcher_points_breakdown(None, scoring)
    use_daily_volume = points_valuation_mode in {"season_total", "daily_h2h"}
    annual_hitter_slot_capacity = annual_slot_capacity(
        hitter_slot_counts,
        teams=teams,
        season_capacity_per_slot=float(synthetic_season_days) if use_daily_volume else 162.0,
    )
    annual_pitcher_slot_capacity = annual_slot_capacity(
        pitcher_slot_counts,
        teams=teams,
        season_capacity_per_slot=float(synthetic_season_days) if use_daily_volume else 162.0,
    )
    h2h_daily_hitter_slot_capacity = annual_slot_capacity(
        hitter_slot_counts,
        teams=teams,
        season_capacity_per_slot=float(synthetic_season_days),
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
            "Age": (meta_hit or {}).get("Age")
            if (meta_hit or {}).get("Age") is not None
            else (meta_pit or {}).get("Age"),
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
            projected_pit_starts = (
                min(ctx.stat_or_zero(pit_row, "GS"), projected_pit_appearances)
                if projected_pit_appearances > 0.0
                else 0.0
            )
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

    return PointsPreparationResult(
        scoring=dict(scoring),
        valuation_year_set=valuation_year_set,
        minor_eligibility_by_year=minor_eligibility_by_year,
        hitter_ab_by_player_year=hitter_ab_by_player_year,
        pitcher_ip_by_player_year=pitcher_ip_by_player_year,
        player_meta=player_meta,
        per_player_year=per_player_year,
        player_profile=player_profile,
        active_slots_per_team=active_slots_per_team,
        active_depth_per_team=active_depth_per_team,
        in_season_depth_per_team=in_season_depth_per_team,
        default_replacement_rank=default_replacement_rank,
        replacement_rank=replacement_rank,
        in_season_replacement_rank=in_season_replacement_rank,
        keeper_continuation_rank=keeper_continuation_rank,
        hitter_slot_counts=hitter_slot_counts,
        pitcher_slot_counts=pitcher_slot_counts,
        active_hitter_slots=active_hitter_slots,
        active_pitcher_slots=active_pitcher_slots,
        starter_slot_capacity=starter_slot_capacity,
        n_replacement=n_replacement,
        freeze_replacement_baselines=freeze_replacement_baselines,
        use_h2h_roster_model=use_h2h_roster_model,
        keeper_continuation_horizon_years=keeper_continuation_horizon_years,
        empty_hit_breakdown=empty_hit_breakdown,
        empty_pit_breakdown=empty_pit_breakdown,
        annual_hitter_slot_capacity=annual_hitter_slot_capacity,
        annual_pitcher_slot_capacity=annual_pitcher_slot_capacity,
        h2h_daily_hitter_slot_capacity=h2h_daily_hitter_slot_capacity,
        h2h_hitter_coverage_slot_capacity=h2h_hitter_coverage_slot_capacity,
    )
