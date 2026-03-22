"""Points-mode dynasty roster modeling helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

try:
    from backend.core.points_assignment import (
        _SEASON_WEEKS,
        _slot_capacity_by_league,
        optimize_points_slot_assignment,
    )
    from backend.core.points_value import _is_near_zero_playing_time
except ImportError:  # pragma: no cover - direct script execution fallback
    from points_assignment import (  # type: ignore[no-redef]
        _SEASON_WEEKS,
        _slot_capacity_by_league,
        optimize_points_slot_assignment,
    )
    from points_value import _is_near_zero_playing_time  # type: ignore[no-redef]


POINTS_CENTERING_ZERO_EPSILON = 1e-12


@dataclass(slots=True)
class PointsH2HRosterModel:
    rostered_player_ids: set[str]
    in_season_rostered_player_ids: set[str]
    replacement_rank: int
    in_season_replacement_rank: int
    held_starter_pitcher_ids: set[str]
    modeled_held_starter_pitchers_per_team: int
    modeled_held_relievers_per_team: int


@dataclass(slots=True)
class PointsStashSelection:
    modeled_minor_roster_ids: set[str]
    modeled_ir_roster_ids: set[str]
    in_season_rostered_player_ids: set[str]
    in_season_replacement_rank: int
    minor_stash_players: set[str]
    ir_stash_players: set[str]
    bench_stash_players: set[str]


def is_h2h_points_mode(points_valuation_mode: str) -> bool:
    return str(points_valuation_mode) in {"weekly_h2h", "daily_h2h"}


def round_half_up_non_negative(value: float) -> int:
    return max(int(max(float(value), 0.0) + 0.5), 0)


def _float_value(value: object, default: float = 0.0) -> float:
    return float(cast(Any, value) or default)


def _entry_points_by_player(entries: list[dict[str, Any]]) -> dict[str, float]:
    points_by_player: dict[str, float] = {}
    for entry in entries:
        player_id = str(entry.get("player_id") or "").strip()
        if not player_id:
            continue
        try:
            points = _float_value(entry.get("points"))
        except (TypeError, ValueError):
            continue
        existing = points_by_player.get(player_id)
        if existing is None or points > existing:
            points_by_player[player_id] = points
    return points_by_player


def active_points_roster_ids(
    entries: list[dict[str, Any]],
    *,
    slot_counts: dict[str, int],
    teams: int,
) -> set[str]:
    active_slots = {slot for slot, count in slot_counts.items() if int(count) > 0}
    if not active_slots:
        return set()
    assignments = optimize_points_slot_assignment(
        entries,
        replacement_by_slot={slot: 0.0 for slot in active_slots},
        slot_capacity=_slot_capacity_by_league(slot_counts, teams=teams),
    )
    return set(assignments.keys())


def select_side_aware_reserve_ids(
    *,
    hit_entries: list[dict[str, Any]],
    pit_entries: list[dict[str, Any]],
    hitter_count: int,
    pitcher_count: int,
    excluded_player_ids: set[str],
) -> tuple[set[str], set[str]]:
    remaining_hitter_count = max(int(hitter_count), 0)
    remaining_pitcher_count = max(int(pitcher_count), 0)
    if remaining_hitter_count <= 0 and remaining_pitcher_count <= 0:
        return set(), set()

    hit_points_by_player = _entry_points_by_player(hit_entries)
    pit_points_by_player = _entry_points_by_player(pit_entries)
    candidate_ids = (set(hit_points_by_player) | set(pit_points_by_player)) - set(excluded_player_ids)
    ranked_candidates = sorted(
        candidate_ids,
        key=lambda player_id: (
            -max(
                float(hit_points_by_player.get(player_id, float("-inf"))),
                float(pit_points_by_player.get(player_id, float("-inf"))),
            ),
            str(player_id),
        ),
    )

    reserve_hitters: set[str] = set()
    reserve_pitchers: set[str] = set()
    for player_id in ranked_candidates:
        options: list[tuple[str, float]] = []
        hitter_points = hit_points_by_player.get(player_id)
        if remaining_hitter_count > 0 and hitter_points is not None and hitter_points > POINTS_CENTERING_ZERO_EPSILON:
            options.append(("hitter", float(hitter_points)))
        pitcher_points = pit_points_by_player.get(player_id)
        if remaining_pitcher_count > 0 and pitcher_points is not None and pitcher_points > POINTS_CENTERING_ZERO_EPSILON:
            options.append(("pitcher", float(pitcher_points)))
        if not options:
            continue
        chosen_side, _chosen_points = sorted(options, key=lambda item: (-item[1], item[0]))[0]
        if chosen_side == "hitter":
            reserve_hitters.add(player_id)
            remaining_hitter_count -= 1
        else:
            reserve_pitchers.add(player_id)
            remaining_pitcher_count -= 1
        if remaining_hitter_count <= 0 and remaining_pitcher_count <= 0:
            break

    return reserve_hitters, reserve_pitchers


def modeled_bench_hitter_slots_per_team(
    *,
    reserve_assigned_games_by_day: dict[int, float],
    teams: int,
    bench_slots: int,
    coverage_target: float = 0.99,
) -> int:
    if int(bench_slots) <= 0 or int(teams) <= 0:
        return 0
    daily_assignable_games = [
        max(float(assigned_games), 0.0)
        for _day, assigned_games in sorted(reserve_assigned_games_by_day.items())
    ]
    total_assignable_games = float(sum(daily_assignable_games))
    if total_assignable_games <= POINTS_CENTERING_ZERO_EPSILON:
        return 0
    for per_team_slots in range(max(int(bench_slots), 0) + 1):
        covered_games = sum(
            min(float(assigned_games), float(per_team_slots) * float(max(int(teams), 1)))
            for assigned_games in daily_assignable_games
        )
        if covered_games + POINTS_CENTERING_ZERO_EPSILON >= total_assignable_games * float(coverage_target):
            return per_team_slots
    return max(int(bench_slots), 0)


def per_day_slot_capacity(
    slot_capacity: dict[str, float],
    *,
    total_days: int,
) -> dict[str, int]:
    per_day_capacity: dict[str, int] = {}
    for slot, capacity in slot_capacity.items():
        daily_capacity = int(round(float(capacity) / max(float(total_days), 1.0)))
        if daily_capacity > 0:
            per_day_capacity[str(slot)] = daily_capacity
    return per_day_capacity


def model_h2h_points_roster(
    *,
    start_year: int,
    points_valuation_mode: str,
    teams: int,
    active_slots_per_team: int,
    bench: int,
    year_hit_entries: dict[int, list[dict[str, Any]]],
    year_pit_entries: dict[int, list[dict[str, Any]]],
    hitter_slot_counts: dict[str, int],
    pitcher_slot_counts: dict[str, int],
    modeled_bench_hitters_per_team_by_year: dict[int, int],
    modeled_bench_pitchers_per_team_by_year: dict[int, int],
    year_active_pitcher_player_ids: dict[int, set[str]],
    year_start_capable_pitcher_ids: dict[int, set[str]],
    pitcher_usage_diagnostics_by_year: dict[int, dict[str, object]],
    default_rostered_player_ids: set[str],
    default_in_season_rostered_player_ids: set[str],
    default_replacement_rank: int,
    default_in_season_replacement_rank: int,
) -> PointsH2HRosterModel:
    active_hitter_player_ids = active_points_roster_ids(
        year_hit_entries.get(start_year, []),
        slot_counts=hitter_slot_counts,
        teams=teams,
    )
    active_pitcher_player_ids = set(
        year_active_pitcher_player_ids.get(
            start_year,
            active_points_roster_ids(
                year_pit_entries.get(start_year, []),
                slot_counts=pitcher_slot_counts,
                teams=teams,
            ),
        )
    )
    start_year_pitcher_entries = year_pit_entries.get(start_year, [])
    start_year_pitcher_points = {
        str(entry.get("player_id") or ""): _float_value(entry.get("points", 0.0))
        for entry in start_year_pitcher_entries
        if str(entry.get("player_id") or "")
    }
    start_year_start_capable_pitcher_ids = set(year_start_capable_pitcher_ids.get(start_year, set()))
    active_starter_pitcher_ids = active_pitcher_player_ids & start_year_start_capable_pitcher_ids
    active_reliever_pitcher_ids = active_pitcher_player_ids - active_starter_pitcher_ids
    active_rostered_player_ids = set(active_hitter_player_ids) | set(active_pitcher_player_ids)
    reserve_hitters_per_team = int(modeled_bench_hitters_per_team_by_year.get(start_year, 0))
    reserve_pitchers_per_team = int(modeled_bench_pitchers_per_team_by_year.get(start_year, 0))
    reserve_hitter_count = max(int(teams), 1) * max(reserve_hitters_per_team, 0)
    reserve_pitcher_count = max(int(teams), 1) * max(reserve_pitchers_per_team, 0)
    reserve_hitter_player_ids, _unused_pitcher_reserve_ids = select_side_aware_reserve_ids(
        hit_entries=year_hit_entries.get(start_year, []),
        pit_entries=start_year_pitcher_entries,
        hitter_count=reserve_hitter_count,
        pitcher_count=0,
        excluded_player_ids=active_rostered_player_ids,
    )
    total_pitcher_roster_count = max(int(teams), 1) * max(
        int(sum(pitcher_slot_counts.values())) + int(reserve_pitchers_per_team),
        0,
    )
    reserve_reliever_pitcher_ids: set[str] = set()
    target_total_starter_roster_count = max(
        int(total_pitcher_roster_count)
        - int(len(active_reliever_pitcher_ids))
        - int(len(reserve_reliever_pitcher_ids)),
        int(len(active_starter_pitcher_ids)),
    )
    held_starter_pitcher_ids = set(active_starter_pitcher_ids)
    for entry in sorted(
        (
            entry
            for entry in start_year_pitcher_entries
            if str(entry.get("player_id") or "") in start_year_start_capable_pitcher_ids
            and str(entry.get("player_id") or "") not in held_starter_pitcher_ids
        ),
        key=lambda entry: (-_float_value(entry.get("points", 0.0)), str(entry.get("player_id") or "")),
    ):
        if len(held_starter_pitcher_ids) >= int(target_total_starter_roster_count):
            break
        held_starter_pitcher_ids.add(str(entry.get("player_id") or ""))
    reserve_starter_pitcher_ids = held_starter_pitcher_ids - active_pitcher_player_ids
    reserve_pitcher_player_ids = set(reserve_reliever_pitcher_ids) | set(reserve_starter_pitcher_ids)
    if len(reserve_pitcher_player_ids) < int(reserve_pitcher_count):
        for entry in sorted(
            start_year_pitcher_entries,
            key=lambda entry: (-_float_value(entry.get("points", 0.0)), str(entry.get("player_id") or "")),
        ):
            player_id = str(entry.get("player_id") or "")
            if (
                not player_id
                or player_id in active_pitcher_player_ids
                or player_id in reserve_pitcher_player_ids
            ):
                continue
            reserve_pitcher_player_ids.add(player_id)
            if len(reserve_pitcher_player_ids) >= int(reserve_pitcher_count):
                break
    elif len(reserve_pitcher_player_ids) > int(reserve_pitcher_count):
        reserve_pitcher_player_ids = {
            player_id
            for player_id in sorted(
                reserve_pitcher_player_ids,
                key=lambda player_id: (
                    -float(start_year_pitcher_points.get(player_id, 0.0)),
                    str(player_id),
                ),
            )[:reserve_pitcher_count]
        }

    modeled_held_starter_pitchers_per_team = round_half_up_non_negative(
        float(len(held_starter_pitcher_ids)) / float(max(int(teams), 1))
    )
    modeled_held_relievers_per_team = round_half_up_non_negative(
        float(len(active_reliever_pitcher_ids) + len(reserve_reliever_pitcher_ids))
        / float(max(int(teams), 1))
    )

    rostered_player_ids = (
        active_rostered_player_ids
        | set(reserve_hitter_player_ids)
        | set(reserve_pitcher_player_ids)
    )
    replacement_rank = int(default_replacement_rank)
    in_season_rostered_player_ids = set(default_in_season_rostered_player_ids)
    in_season_replacement_rank = int(default_in_season_replacement_rank)
    if rostered_player_ids:
        replacement_rank = max(int(teams) * max(int(active_slots_per_team) + int(bench), 0), 1)
        in_season_rostered_player_ids = set(rostered_player_ids)
        in_season_replacement_rank = int(replacement_rank)
    else:
        rostered_player_ids = set(default_rostered_player_ids)

    start_year_pitcher_diag = pitcher_usage_diagnostics_by_year.get(start_year)
    if isinstance(start_year_pitcher_diag, dict):
        pitch_diag = cast(dict[str, Any], start_year_pitcher_diag)
        selected_held_starts = _float_value(pitch_diag.get("selected_held_starts"))
        selected_streamed_starts = _float_value(pitch_diag.get("selected_streamed_starts"))
        selected_overflow_starts = _float_value(pitch_diag.get("selected_overflow_starts"))
        effective_weekly_starts_cap_modeled = (
            (selected_held_starts + selected_streamed_starts)
            / float(_SEASON_WEEKS * max(int(teams), 1))
            if points_valuation_mode == "daily_h2h"
            else None
        )
        overflow_starts_per_week = (
            selected_overflow_starts / float(_SEASON_WEEKS * max(int(teams), 1))
            if points_valuation_mode == "daily_h2h"
            else None
        )
        pitch_diag.update(
            {
                "modeled_held_starter_pitchers_per_team": int(modeled_held_starter_pitchers_per_team),
                "modeled_held_relievers_per_team": int(modeled_held_relievers_per_team),
                "modeled_effective_weekly_starts_cap": round(float(effective_weekly_starts_cap_modeled), 4)
                if effective_weekly_starts_cap_modeled is not None
                else None,
                "modeled_overflow_starts_per_week": round(float(overflow_starts_per_week), 4)
                if overflow_starts_per_week is not None
                else None,
            }
        )

    return PointsH2HRosterModel(
        rostered_player_ids=set(rostered_player_ids),
        in_season_rostered_player_ids=set(in_season_rostered_player_ids),
        replacement_rank=int(replacement_rank),
        in_season_replacement_rank=int(in_season_replacement_rank),
        held_starter_pitcher_ids=set(held_starter_pitcher_ids),
        modeled_held_starter_pitchers_per_team=int(modeled_held_starter_pitchers_per_team),
        modeled_held_relievers_per_team=int(modeled_held_relievers_per_team),
    )


def _select_ranked_group(
    *,
    ranked_player_ids: list[str],
    limit: int,
    candidates: set[str],
    used_player_ids: set[str],
) -> set[str]:
    selected: set[str] = set()
    for player_id in ranked_player_ids:
        if len(selected) >= max(int(limit), 0):
            break
        if player_id in used_player_ids or player_id not in candidates:
            continue
        selected.add(player_id)
        used_player_ids.add(player_id)
    return selected


def select_points_stash_groups(
    *,
    stash_scores_by_player: dict[str, float],
    use_h2h_roster_model: bool,
    in_season_rostered_player_ids: set[str],
    in_season_replacement_rank: int,
    minor_eligibility_by_year: dict[tuple[str, int], bool],
    valuation_year_set: list[int],
    start_year: int,
    teams: int,
    minors: int,
    ir: int,
    bench: int,
    ir_candidate_players: set[str],
    negative_year_players: set[str],
    hitter_ab_by_player_year: dict[tuple[str, int], float],
    pitcher_ip_by_player_year: dict[tuple[str, int], float],
) -> PointsStashSelection:
    ranked_stash_player_ids = [
        player_id
        for player_id, _score in sorted(
            stash_scores_by_player.items(),
            key=lambda item: (-float(item[1]), str(item[0])),
        )
    ]

    modeled_minor_roster_ids: set[str] = set()
    modeled_ir_roster_ids: set[str] = set()
    updated_in_season_rostered_player_ids = set(in_season_rostered_player_ids)
    updated_in_season_replacement_rank = int(in_season_replacement_rank)

    if use_h2h_roster_model:
        used_h2h_in_season_players = set(updated_in_season_rostered_player_ids)
        start_year_minor_candidates = {
            player_id
            for player_id in ranked_stash_player_ids
            if bool(minor_eligibility_by_year.get((player_id, int(start_year)), False))
        }
        start_year_ir_candidates = {
            player_id
            for player_id in ranked_stash_player_ids
            if _is_near_zero_playing_time(
                player_id,
                int(start_year),
                hitter_ab_by_player_year=hitter_ab_by_player_year,
                pitcher_ip_by_player_year=pitcher_ip_by_player_year,
            )
        }
        modeled_minor_roster_ids = _select_ranked_group(
            ranked_player_ids=ranked_stash_player_ids,
            limit=int(teams) * int(minors),
            candidates=start_year_minor_candidates,
            used_player_ids=used_h2h_in_season_players,
        )
        modeled_ir_roster_ids = _select_ranked_group(
            ranked_player_ids=ranked_stash_player_ids,
            limit=int(teams) * int(ir),
            candidates=start_year_ir_candidates,
            used_player_ids=used_h2h_in_season_players,
        )
        updated_in_season_rostered_player_ids = (
            set(updated_in_season_rostered_player_ids)
            | set(modeled_minor_roster_ids)
            | set(modeled_ir_roster_ids)
        )
        updated_in_season_replacement_rank = max(len(updated_in_season_rostered_player_ids), 1)

    reserve_ranked_player_ids = [
        player_id
        for player_id in ranked_stash_player_ids
        if player_id in updated_in_season_rostered_player_ids
    ]
    used_reserve_players: set[str] = set()

    minor_candidate_players = {
        player_id
        for player_id in reserve_ranked_player_ids
        if any(bool(minor_eligibility_by_year.get((player_id, year), False)) for year in valuation_year_set)
    }
    minor_stash_players = _select_ranked_group(
        ranked_player_ids=reserve_ranked_player_ids,
        limit=int(teams) * int(minors),
        candidates=minor_candidate_players,
        used_player_ids=used_reserve_players,
    )
    ir_stash_players = _select_ranked_group(
        ranked_player_ids=reserve_ranked_player_ids,
        limit=int(teams) * int(ir),
        candidates=set(reserve_ranked_player_ids) & set(ir_candidate_players),
        used_player_ids=used_reserve_players,
    )
    bench_stash_players = _select_ranked_group(
        ranked_player_ids=reserve_ranked_player_ids,
        limit=int(teams) * int(bench),
        candidates=set(reserve_ranked_player_ids) & set(negative_year_players),
        used_player_ids=used_reserve_players,
    )

    return PointsStashSelection(
        modeled_minor_roster_ids=set(modeled_minor_roster_ids),
        modeled_ir_roster_ids=set(modeled_ir_roster_ids),
        in_season_rostered_player_ids=set(updated_in_season_rostered_player_ids),
        in_season_replacement_rank=int(updated_in_season_replacement_rank),
        minor_stash_players=set(minor_stash_players),
        ir_stash_players=set(ir_stash_players),
        bench_stash_players=set(bench_stash_players),
    )
