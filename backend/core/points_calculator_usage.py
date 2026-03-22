"""Usage-allocation helpers for points-mode dynasty calculations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, cast

try:
    from backend.core.points_calculator_preparation import PointsPreparationResult
except ImportError:  # pragma: no cover - direct script execution fallback
    from points_calculator_preparation import PointsPreparationResult  # type: ignore[no-redef]


@dataclass(slots=True)
class PointsUsageResult:
    year_hit_entries: dict[int, list[dict[str, Any]]]
    year_pit_entries: dict[int, list[dict[str, Any]]]
    hitter_usage_diagnostics_by_year: dict[int, dict[str, object]]
    pitcher_usage_diagnostics_by_year: dict[int, dict[str, object]]
    modeled_bench_hitters_per_team_by_year: dict[int, int]
    modeled_bench_pitchers_per_team_by_year: dict[int, int]
    modeled_held_pitchers_per_team_by_year: dict[int, int]
    year_active_hitter_player_ids: dict[int, set[str]]
    year_start_capable_pitcher_ids: dict[int, set[str]]
    year_relief_pitcher_ids: dict[int, set[str]]
    year_active_pitcher_player_ids: dict[int, set[str]]


def calculate_points_usage_by_year(
    *,
    prep: PointsPreparationResult,
    teams: int,
    bench: int,
    points_valuation_mode: str,
    weekly_starts_cap: int | None,
    allow_same_day_starts_overflow: bool,
    weekly_acquisition_cap: int | None,
    ip_max: float | None,
    season_weeks: int,
    synthetic_season_days: int,
    synthetic_period_days: int,
    volume_entry_factory: Callable[..., Any],
    allocate_hitter_usage: Callable[..., Any],
    allocate_hitter_usage_daily: Callable[..., Any],
    allocate_hitter_usage_daily_detail: Callable[..., Any],
    allocate_pitcher_usage: Callable[..., Any],
    allocate_pitcher_usage_daily: Callable[..., Any],
    allocate_pitcher_innings_budget: Callable[..., Any],
    active_points_roster_ids: Callable[..., set[str]],
    per_day_slot_capacity: Callable[..., dict[str, int]],
    modeled_bench_hitter_slots_per_team: Callable[..., int],
    effective_weekly_starts_cap: Callable[..., float | None],
    scale_points_breakdown: Callable[[dict[str, Any], float], dict[str, Any]],
) -> PointsUsageResult:
    year_hit_entries: dict[int, list[dict[str, Any]]] = {year: [] for year in prep.valuation_year_set}
    year_pit_entries: dict[int, list[dict[str, Any]]] = {year: [] for year in prep.valuation_year_set}
    hitter_usage_diagnostics_by_year: dict[int, dict[str, object]] = {}
    pitcher_usage_diagnostics_by_year: dict[int, dict[str, object]] = {}
    modeled_bench_hitters_per_team_by_year: dict[int, int] = {}
    modeled_bench_pitchers_per_team_by_year: dict[int, int] = {}
    modeled_held_pitchers_per_team_by_year: dict[int, int] = {}
    year_active_hitter_player_ids: dict[int, set[str]] = {}
    year_start_capable_pitcher_ids: dict[int, set[str]] = {}
    year_relief_pitcher_ids: dict[int, set[str]] = {}
    year_active_pitcher_player_ids: dict[int, set[str]] = {}
    use_daily_volume = points_valuation_mode in {"season_total", "daily_h2h"}

    for year in prep.valuation_year_set:
        hitter_entries: list[Any] = []
        pitcher_entries: list[Any] = []
        pitcher_start_volume: dict[str, float] = {}
        fallback_hitter_ids: set[str] = set()
        fallback_pitcher_ids: set[str] = set()
        requested_hitter_games = 0.0

        for player_id, year_map in prep.per_player_year.items():
            info = year_map.get(year, {})
            hit_slots = set(info.get("hit_slots", set()))
            projected_hit_games = float(info.get("projected_hit_games", 0.0))
            raw_hit_points = float(info.get("raw_hit_points", 0.0))
            if hit_slots:
                if projected_hit_games > 0.0:
                    requested_hitter_games += projected_hit_games
                    hitter_entries.append(
                        volume_entry_factory(
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
                        volume_entry_factory(
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
                slot_capacity=prep.annual_hitter_slot_capacity,
            )
        else:
            hitter_usage = allocate_hitter_usage_daily(
                hitter_entries,
                slot_capacity=prep.annual_hitter_slot_capacity,
            )
        reserve_hitter_usage = hitter_usage
        if prep.use_h2h_roster_model:
            reserve_hitter_usage = allocate_hitter_usage_daily_detail(
                hitter_entries,
                slot_capacity=prep.h2h_daily_hitter_slot_capacity,
            ).allocation
        reserve_hitter_assignment_entries: list[dict[str, Any]] = []
        active_hitter_ids_for_bench: set[str] = set()
        if prep.use_h2h_roster_model:
            for player_id, year_map in prep.per_player_year.items():
                info = year_map.get(year, {})
                hit_slots = set(info.get("hit_slots", set()))
                if not hit_slots:
                    continue
                raw_hit_points = float(info.get("raw_hit_points", 0.0))
                reserve_hit_share = (
                    1.0
                    if player_id in fallback_hitter_ids
                    else float(reserve_hitter_usage.usage_share_by_player.get(player_id, 0.0))
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
                slot_counts=prep.hitter_slot_counts,
                teams=teams,
            )
            year_active_hitter_player_ids[year] = set(active_hitter_ids_for_bench)

        effective_weekly_cap: float | None = None
        capped_start_budget: float | None = None
        held_pitcher_ids: set[str] | None = None
        streaming_adds_per_period: int | None = None
        modeled_bench_hitters_per_team = 0
        modeled_bench_pitchers_per_team = 0
        modeled_held_pitchers_per_team = max(int(prep.starter_slot_capacity), 0)
        if points_valuation_mode == "daily_h2h" and weekly_acquisition_cap is not None:
            streaming_adds_per_period = max(int(weekly_acquisition_cap), 0) * max(int(teams), 1)
        if points_valuation_mode == "weekly_h2h":
            effective_weekly_cap = effective_weekly_starts_cap(
                weekly_starts_cap,
                allow_same_day_starts_overflow=allow_same_day_starts_overflow,
                starter_slot_capacity=prep.starter_slot_capacity,
            )
            if effective_weekly_cap is not None and effective_weekly_cap > 0.0:
                capped_start_budget = float(effective_weekly_cap) * season_weeks * max(int(teams), 1)
        elif points_valuation_mode == "daily_h2h" and weekly_starts_cap is not None and int(weekly_starts_cap) > 0:
            capped_start_budget = float(max(int(weekly_starts_cap), 0)) * season_weeks * max(int(teams), 1)
        if prep.use_h2h_roster_model:
            per_day_hitter_capacity = per_day_slot_capacity(
                prep.h2h_hitter_coverage_slot_capacity,
                total_days=162,
            )
            active_hitter_coverage_detail = allocate_hitter_usage_daily_detail(
                [entry for entry in hitter_entries if entry.player_id in active_hitter_ids_for_bench],
                slot_capacity=prep.h2h_hitter_coverage_slot_capacity,
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
                int(prep.starter_slot_capacity) + modeled_bench_pitchers_per_team,
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
                slot_capacity=prep.annual_pitcher_slot_capacity,
                capped_start_budget=capped_start_budget,
            )
        else:
            pitcher_usage = allocate_pitcher_usage_daily(
                pitcher_entries,
                start_volume_by_player=pitcher_start_volume,
                slot_capacity=prep.annual_pitcher_slot_capacity,
                capped_start_budget=capped_start_budget,
                held_player_ids=held_pitcher_ids,
                streaming_adds_per_period=streaming_adds_per_period,
                allow_same_day_starts_overflow=allow_same_day_starts_overflow,
                total_days=synthetic_season_days,
                period_days=synthetic_period_days,
            )
        ip_budget = float(ip_max) * max(int(teams), 1) if ip_max is not None else None
        pitcher_appearance_usage_share: dict[str, float] = {}
        pitcher_ip_usage_share: dict[str, float] = {}
        pitcher_requested_ip_pre_cap: dict[str, float] = {}
        pitcher_assigned_ip: dict[str, float] = {}
        requested_pitcher_ip_pre_cap = 0.0
        ip_entries: list[Any] = []

        for player_id, year_map in prep.per_player_year.items():
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
                1.0
                if player_id in fallback_pitcher_ids
                else float(pitcher_usage.usage_share_by_player.get(player_id, 0.0))
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
                    volume_entry_factory(
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
            "slot_game_capacity": round(float(sum(prep.annual_hitter_slot_capacity.values())), 4),
            "assigned_hitter_games": round(float(hitter_usage.total_assigned_volume), 4),
            "unused_hitter_games": round(
                max(float(requested_hitter_games) - float(hitter_usage.total_assigned_volume), 0.0),
                4,
            ),
            "fallback_hitter_count": int(len(fallback_hitter_ids)),
            "synthetic_season_days": int(synthetic_season_days) if use_daily_volume else None,
            "modeled_bench_hitters_per_team": (
                int(modeled_bench_hitters_per_team) if prep.use_h2h_roster_model else None
            ),
            "modeled_bench_pitchers_per_team": (
                int(modeled_bench_pitchers_per_team) if prep.use_h2h_roster_model else None
            ),
        }
        pitcher_diag: dict[str, object] = {
            "slot_appearance_capacity": round(float(sum(prep.annual_pitcher_slot_capacity.values())), 4),
            "assigned_starts": round(float(pitcher_usage.total_assigned_starts), 4),
            "assigned_non_start_appearances": round(float(pitcher_usage.total_assigned_non_start_appearances), 4),
            "capped_start_budget": round(float(capped_start_budget), 4) if capped_start_budget is not None else None,
            "fallback_pitcher_count": int(len(fallback_pitcher_ids)),
            "synthetic_season_days": int(synthetic_season_days) if use_daily_volume else None,
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
                int(modeled_bench_hitters_per_team) if prep.use_h2h_roster_model else None
            ),
            "modeled_bench_pitchers_per_team": (
                int(modeled_bench_pitchers_per_team) if prep.use_h2h_roster_model else None
            ),
            "modeled_held_pitchers_per_team": (
                int(modeled_held_pitchers_per_team) if prep.use_h2h_roster_model else None
            ),
        }
        if points_valuation_mode == "weekly_h2h":
            pitcher_diag.update(
                {
                    "season_weeks": season_weeks,
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
                    "season_weeks": season_weeks,
                    "weekly_starts_cap": weekly_starts_cap,
                    "effective_weekly_starts_cap": round(float(effective_weekly_cap), 4)
                    if effective_weekly_cap is not None
                    else None,
                    "weekly_acquisition_cap": weekly_acquisition_cap,
                    "synthetic_period_days": int(synthetic_period_days),
                }
            )
        pitcher_usage_diagnostics_by_year[year] = pitcher_diag

        for player_id, year_map in prep.per_player_year.items():
            info = year_map.get(year, {})
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))
            raw_hit_points = float(info.get("raw_hit_points", 0.0))
            raw_pit_points = float(info.get("raw_pit_points", 0.0))

            hit_share = 0.0
            if hit_slots:
                hit_share = (
                    1.0 if player_id in fallback_hitter_ids else float(hitter_usage.usage_share_by_player.get(player_id, 0.0))
                )
            pit_appearance_share = 0.0
            pit_ip_share = 0.0
            pit_share = 0.0
            if pit_slots:
                pit_appearance_share = float(pitcher_appearance_usage_share.get(player_id, 0.0))
                pit_ip_share = float(pitcher_ip_usage_share.get(player_id, 0.0))
                pit_share = float(min(max(pit_appearance_share * pit_ip_share, 0.0), 1.0))

            raw_hit_breakdown_src = info.get("raw_hit_breakdown")
            hit_breakdown = scale_points_breakdown(
                cast(dict[str, Any], raw_hit_breakdown_src)
                if isinstance(raw_hit_breakdown_src, dict)
                else prep.empty_hit_breakdown,
                hit_share,
            )
            raw_pit_breakdown_src = info.get("raw_pit_breakdown")
            pit_breakdown = scale_points_breakdown(
                cast(dict[str, Any], raw_pit_breakdown_src)
                if isinstance(raw_pit_breakdown_src, dict)
                else prep.empty_pit_breakdown,
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
        if prep.use_h2h_roster_model:
            year_active_pitcher_player_ids[year] = active_points_roster_ids(
                year_pit_entries[year],
                slot_counts=prep.pitcher_slot_counts,
                teams=teams,
            )

    return PointsUsageResult(
        year_hit_entries=year_hit_entries,
        year_pit_entries=year_pit_entries,
        hitter_usage_diagnostics_by_year=hitter_usage_diagnostics_by_year,
        pitcher_usage_diagnostics_by_year=pitcher_usage_diagnostics_by_year,
        modeled_bench_hitters_per_team_by_year=modeled_bench_hitters_per_team_by_year,
        modeled_bench_pitchers_per_team_by_year=modeled_bench_pitchers_per_team_by_year,
        modeled_held_pitchers_per_team_by_year=modeled_held_pitchers_per_team_by_year,
        year_active_hitter_player_ids=year_active_hitter_player_ids,
        year_start_capable_pitcher_ids=year_start_capable_pitcher_ids,
        year_relief_pitcher_ids=year_relief_pitcher_ids,
        year_active_pitcher_player_ids=year_active_pitcher_player_ids,
    )
