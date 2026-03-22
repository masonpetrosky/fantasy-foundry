"""Output and valuation helpers for points-mode dynasty calculations."""

from __future__ import annotations

from typing import Any, Callable, cast

import pandas as pd

try:
    from backend.core.points_calculator_preparation import PointsPreparationResult
    from backend.core.points_calculator_usage import PointsUsageResult
except ImportError:  # pragma: no cover - direct script execution fallback
    from points_calculator_preparation import PointsPreparationResult  # type: ignore[no-redef]
    from points_calculator_usage import PointsUsageResult  # type: ignore[no-redef]


def _apply_pitcher_replacement_adjustment(
    *,
    pit_points: float,
    pit_best_slot: str | None,
    pit_best_replacement: float | None,
    pit_best_value: float | None,
    pit_assigned_slot: str | None,
    pit_assigned_replacement: float,
    pit_assigned_value: float,
    pit_assigned_points: float,
    projected_pit_appearances: float,
    projected_pit_starts: float,
    starter_replacement: float | None,
    reliever_replacement: float | None,
    zero_epsilon: float,
) -> tuple[float | None, float | None, float, float]:
    if (
        starter_replacement is not None
        and projected_pit_starts >= 1.0
        and starter_replacement > zero_epsilon
    ):
        if pit_best_slot == "P" and starter_replacement < (float(pit_best_replacement or 0.0) - zero_epsilon):
            pit_best_replacement = float(starter_replacement)
            pit_best_value = float(pit_points - pit_best_replacement)
        if pit_assigned_slot == "P" and starter_replacement < (float(pit_assigned_replacement) - zero_epsilon):
            pit_assigned_replacement = float(starter_replacement)
            pit_assigned_value = float(pit_assigned_points - pit_assigned_replacement)
    elif (
        reliever_replacement is not None
        and projected_pit_appearances > 0.0
        and projected_pit_starts < 1.0
        and reliever_replacement > zero_epsilon
    ):
        if pit_best_slot == "P" and reliever_replacement < (float(pit_best_replacement or 0.0) - zero_epsilon):
            pit_best_replacement = float(reliever_replacement)
            pit_best_value = float(pit_points - pit_best_replacement)
        if pit_assigned_slot == "P" and reliever_replacement < (float(pit_assigned_replacement) - zero_epsilon):
            pit_assigned_replacement = float(reliever_replacement)
            pit_assigned_value = float(pit_assigned_points - pit_assigned_replacement)

    return pit_best_replacement, pit_best_value, pit_assigned_replacement, pit_assigned_value


def _selected_points_summary(
    *,
    two_way: str,
    hit_selected_value: float,
    pit_selected_value: float,
    hit_assigned_slot: str | None,
    pit_assigned_slot: str | None,
    hit_selected_raw_points: float,
    pit_selected_raw_points: float,
) -> tuple[float, float, str]:
    selected_side = "none"
    if two_way == "sum":
        year_points = hit_selected_value + pit_selected_value
        selected_raw_points = hit_selected_raw_points + pit_selected_raw_points
        if year_points > 0:
            selected_side = "sum"
        elif year_points < 0:
            selected_side = "sum_negative"
        return year_points, selected_raw_points, selected_side

    if hit_selected_value > pit_selected_value:
        return (
            hit_selected_value,
            hit_selected_raw_points,
            "hitting" if hit_assigned_slot is not None else "hitting_negative",
        )
    if pit_selected_value > hit_selected_value:
        return (
            pit_selected_value,
            pit_selected_raw_points,
            "pitching" if pit_assigned_slot is not None else "pitching_negative",
        )
    if hit_selected_value != 0.0:
        return (
            hit_selected_value,
            hit_selected_raw_points,
            "hitting" if hit_assigned_slot is not None else "hitting_negative",
        )
    return 0.0, 0.0, selected_side


def _build_keeper_start_year_values(
    *,
    ctx: Any,
    prep: PointsPreparationResult,
    usage: PointsUsageResult,
    start_year: int,
    two_way: str,
    points_centering_zero_epsilon: float,
    start_capable_pitcher_replacement_value: Callable[..., float | None],
    relief_pitcher_replacement_value: Callable[..., float | None],
    optimize_points_slot_assignment: Callable[..., dict[str, dict[str, Any]]],
    best_slot_surplus: Callable[..., tuple[float | None, str | None, float | None]],
    negative_fallback_value: Callable[..., float],
) -> dict[str, float]:
    keeper_start_year_value_by_player: dict[str, float] = {}
    keeper_hit_replacement = ctx.points_slot_replacement(
        usage.year_hit_entries.get(start_year, []),
        active_slots=prep.active_hitter_slots,
        rostered_player_ids=usage.year_active_hitter_player_ids.get(start_year, set()),
        n_replacement=prep.n_replacement,
    )
    keeper_pit_replacement = ctx.points_slot_replacement(
        usage.year_pit_entries.get(start_year, []),
        active_slots=prep.active_pitcher_slots,
        rostered_player_ids=usage.year_active_pitcher_player_ids.get(start_year, set()),
        n_replacement=prep.n_replacement,
    )
    keeper_start_capable_pitcher_replacement: float | None = None
    keeper_relief_pitcher_replacement: float | None = None
    if prep.active_pitcher_slots == {"P"}:
        keeper_start_capable_pitcher_replacement = start_capable_pitcher_replacement_value(
            points_slot_replacement=ctx.points_slot_replacement,
            year_pit_entries=usage.year_pit_entries,
            start_year=start_year,
            year_start_capable_pitcher_ids=usage.year_start_capable_pitcher_ids,
            starter_replacement_rostered_ids=(
                set(usage.year_active_pitcher_player_ids.get(start_year, set()))
                & set(usage.year_start_capable_pitcher_ids.get(start_year, set()))
            ),
            n_replacement=prep.n_replacement,
        )
        keeper_relief_pitcher_replacement = relief_pitcher_replacement_value(
            points_slot_replacement=ctx.points_slot_replacement,
            year_pit_entries=usage.year_pit_entries,
            start_year=start_year,
            year_relief_pitcher_ids=usage.year_relief_pitcher_ids,
            reliever_replacement_rostered_ids=(
                set(usage.year_active_pitcher_player_ids.get(start_year, set()))
                - set(usage.year_start_capable_pitcher_ids.get(start_year, set()))
            ),
            n_replacement=prep.n_replacement,
        )
    hitter_slot_capacity = {slot: int(count) * int(prep.n_replacement) for slot, count in prep.hitter_slot_counts.items()}
    pitcher_slot_capacity = {
        slot: int(count) * int(prep.n_replacement) for slot, count in prep.pitcher_slot_counts.items()
    }
    keeper_hit_assignments = optimize_points_slot_assignment(
        usage.year_hit_entries.get(start_year, []),
        replacement_by_slot=keeper_hit_replacement,
        slot_capacity=hitter_slot_capacity,
    )
    keeper_pit_assignments = optimize_points_slot_assignment(
        usage.year_pit_entries.get(start_year, []),
        replacement_by_slot=keeper_pit_replacement,
        slot_capacity=pitcher_slot_capacity,
    )
    for player_id in prep.player_meta:
        info = prep.per_player_year.get(player_id, {}).get(start_year, {})
        hit_points = float(info.get("hit_points", 0.0))
        pit_points = float(info.get("pit_points", 0.0))
        hit_slots = set(info.get("hit_slots", set()))
        pit_slots = set(info.get("pit_slots", set()))

        hit_best_value, _hit_best_slot, _hit_best_replacement = best_slot_surplus(
            points=hit_points,
            eligible_slots=hit_slots,
            replacement_by_slot=keeper_hit_replacement,
        )
        pit_best_value, pit_best_slot, pit_best_replacement = best_slot_surplus(
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
        pit_assigned_replacement = (
            float(pit_assignment.get("replacement", 0.0)) if isinstance(pit_assignment, dict) else 0.0
        )
        projected_pit_appearances = float(info.get("projected_pit_appearances", 0.0))
        projected_pit_starts = float(info.get("projected_pit_starts", 0.0))
        pit_best_replacement, pit_best_value, pit_assigned_replacement, pit_assigned_value = (
            _apply_pitcher_replacement_adjustment(
                pit_points=pit_points,
                pit_best_slot=pit_best_slot,
                pit_best_replacement=pit_best_replacement,
                pit_best_value=pit_best_value,
                pit_assigned_slot=pit_assigned_slot,
                pit_assigned_replacement=pit_assigned_replacement,
                pit_assigned_value=pit_assigned_value,
                pit_assigned_points=pit_assigned_points,
                projected_pit_appearances=projected_pit_appearances,
                projected_pit_starts=projected_pit_starts,
                starter_replacement=keeper_start_capable_pitcher_replacement,
                reliever_replacement=keeper_relief_pitcher_replacement,
                zero_epsilon=points_centering_zero_epsilon,
            )
        )
        hit_selected_value = negative_fallback_value(
            best_value=hit_best_value,
            assigned_slot=hit_assigned_slot,
            assigned_value=hit_assigned_value,
        )
        pit_selected_value = negative_fallback_value(
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

    return keeper_start_year_value_by_player


def finalize_points_calculation(
    *,
    ctx: Any,
    prep: PointsPreparationResult,
    usage: PointsUsageResult,
    teams: int,
    bench: int,
    minors: int,
    ir: int,
    start_year: int,
    discount: float,
    two_way: str,
    keeper_limit: int | None,
    points_valuation_mode: str,
    weekly_starts_cap: int | None,
    allow_same_day_starts_overflow: bool,
    weekly_acquisition_cap: int | None,
    enable_prospect_risk_adjustment: bool,
    enable_bench_stash_relief: bool,
    bench_negative_penalty: float,
    enable_ir_stash_relief: bool,
    ir_negative_penalty: float,
    build_empty_points_value_frame: Callable[..., pd.DataFrame],
    calculate_points_raw_totals: Callable[..., dict[str, float]],
    model_h2h_points_roster: Callable[..., Any],
    start_capable_pitcher_replacement_value: Callable[..., float | None],
    relief_pitcher_replacement_value: Callable[..., float | None],
    slot_capacity_by_league: Callable[..., dict[str, int]],
    optimize_points_slot_assignment: Callable[..., dict[str, dict[str, Any]]],
    best_slot_surplus: Callable[..., tuple[float | None, str | None, float | None]],
    negative_fallback_value: Callable[..., float],
    is_near_zero_playing_time: Callable[..., bool],
    prospect_risk_multiplier: Callable[..., float],
    dynasty_keep_or_drop_values: Callable[..., Any],
    select_points_stash_groups: Callable[..., Any],
    build_points_result_rows: Callable[..., list[dict[str, Any]]],
    finalize_points_dynasty_output: Callable[..., pd.DataFrame],
    points_centering_zero_epsilon: float,
) -> pd.DataFrame:
    player_raw_totals = calculate_points_raw_totals(
        per_player_year=prep.per_player_year,
        valuation_year_set=prep.valuation_year_set,
        discount=float(discount),
        two_way=two_way,
    )

    if not prep.player_meta:
        return build_empty_points_value_frame(
            valuation_year_set=prep.valuation_year_set,
            player_key_col=ctx.player_key_col,
            player_entity_key_col=ctx.player_entity_key_col,
        )

    ranked_players = sorted(
        player_raw_totals.items(),
        key=lambda item: (-float(item[1]), str(item[0])),
    )
    replacement_rank = int(prep.replacement_rank)
    in_season_replacement_rank = int(prep.in_season_replacement_rank)
    rostered_player_ids = {player_id for player_id, _score in ranked_players[:replacement_rank]}
    in_season_rostered_player_ids = {player_id for player_id, _score in ranked_players[:in_season_replacement_rank]}
    modeled_ir_roster_ids: set[str] = set()
    modeled_minor_roster_ids: set[str] = set()
    held_starter_pitcher_ids: set[str] = set()
    modeled_held_starter_pitchers_per_team_by_year: dict[int, int] = {}
    modeled_held_relievers_per_team_by_year: dict[int, int] = {}

    if prep.use_h2h_roster_model:
        h2h_roster_model = model_h2h_points_roster(
            start_year=start_year,
            points_valuation_mode=points_valuation_mode,
            teams=teams,
            active_slots_per_team=prep.active_slots_per_team,
            bench=bench,
            year_hit_entries=usage.year_hit_entries,
            year_pit_entries=usage.year_pit_entries,
            hitter_slot_counts=prep.hitter_slot_counts,
            pitcher_slot_counts=prep.pitcher_slot_counts,
            modeled_bench_hitters_per_team_by_year=usage.modeled_bench_hitters_per_team_by_year,
            modeled_bench_pitchers_per_team_by_year=usage.modeled_bench_pitchers_per_team_by_year,
            year_active_pitcher_player_ids=usage.year_active_pitcher_player_ids,
            year_start_capable_pitcher_ids=usage.year_start_capable_pitcher_ids,
            pitcher_usage_diagnostics_by_year=usage.pitcher_usage_diagnostics_by_year,
            default_rostered_player_ids=rostered_player_ids,
            default_in_season_rostered_player_ids=in_season_rostered_player_ids,
            default_replacement_rank=prep.default_replacement_rank,
            default_in_season_replacement_rank=prep.in_season_replacement_rank,
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
    if prep.freeze_replacement_baselines:
        frozen_hit = ctx.points_slot_replacement(
            usage.year_hit_entries.get(start_year, []),
            active_slots=prep.active_hitter_slots,
            rostered_player_ids=rostered_player_ids,
            n_replacement=prep.n_replacement,
        )
        frozen_pit = ctx.points_slot_replacement(
            usage.year_pit_entries.get(start_year, []),
            active_slots=prep.active_pitcher_slots,
            rostered_player_ids=rostered_player_ids,
            n_replacement=prep.n_replacement,
        )
        for year in prep.valuation_year_set:
            year_hit_replacement[year] = dict(frozen_hit)
            year_pit_replacement[year] = dict(frozen_pit)
    else:
        for year in prep.valuation_year_set:
            year_hit_replacement[year] = ctx.points_slot_replacement(
                usage.year_hit_entries.get(year, []),
                active_slots=prep.active_hitter_slots,
                rostered_player_ids=rostered_player_ids,
                n_replacement=prep.n_replacement,
            )
            year_pit_replacement[year] = ctx.points_slot_replacement(
                usage.year_pit_entries.get(year, []),
                active_slots=prep.active_pitcher_slots,
                rostered_player_ids=rostered_player_ids,
                n_replacement=prep.n_replacement,
            )

    starter_pitcher_replacement_start_year: float | None = None
    reliever_pitcher_replacement_start_year: float | None = None
    use_start_capable_pitcher_replacement = bool(prep.use_h2h_roster_model and prep.active_pitcher_slots == {"P"})
    if use_start_capable_pitcher_replacement:
        starter_replacement_rostered_ids = set(held_starter_pitcher_ids) if prep.use_h2h_roster_model else set(rostered_player_ids)
        starter_pitcher_replacement_start_year = start_capable_pitcher_replacement_value(
            points_slot_replacement=ctx.points_slot_replacement,
            year_pit_entries=usage.year_pit_entries,
            start_year=start_year,
            year_start_capable_pitcher_ids=usage.year_start_capable_pitcher_ids,
            starter_replacement_rostered_ids=starter_replacement_rostered_ids,
            n_replacement=prep.n_replacement,
        )
        reliever_replacement_rostered_ids = (
            set(usage.year_active_pitcher_player_ids.get(start_year, set()))
            - set(usage.year_start_capable_pitcher_ids.get(start_year, set()))
        )
        reliever_pitcher_replacement_start_year = relief_pitcher_replacement_value(
            points_slot_replacement=ctx.points_slot_replacement,
            year_pit_entries=usage.year_pit_entries,
            start_year=start_year,
            year_relief_pitcher_ids=usage.year_relief_pitcher_ids,
            reliever_replacement_rostered_ids=reliever_replacement_rostered_ids,
            n_replacement=prep.n_replacement,
        )

    hitter_slot_capacity = slot_capacity_by_league(prep.hitter_slot_counts, teams=teams)
    pitcher_slot_capacity = slot_capacity_by_league(prep.pitcher_slot_counts, teams=teams)
    year_hit_assignments = {
        year: optimize_points_slot_assignment(
            usage.year_hit_entries.get(year, []),
            replacement_by_slot=year_hit_replacement.get(year, {}),
            slot_capacity=hitter_slot_capacity,
        )
        for year in prep.valuation_year_set
    }
    year_pit_assignments = {
        year: optimize_points_slot_assignment(
            usage.year_pit_entries.get(year, []),
            replacement_by_slot=year_pit_replacement.get(year, {}),
            slot_capacity=pitcher_slot_capacity,
        )
        for year in prep.valuation_year_set
    }

    keeper_start_year_value_by_player: dict[str, float] = {}
    if prep.use_h2h_roster_model and keeper_limit is not None:
        keeper_start_year_value_by_player = _build_keeper_start_year_values(
            ctx=ctx,
            prep=prep,
            usage=usage,
            start_year=start_year,
            two_way=two_way,
            points_centering_zero_epsilon=points_centering_zero_epsilon,
            start_capable_pitcher_replacement_value=start_capable_pitcher_replacement_value,
            relief_pitcher_replacement_value=relief_pitcher_replacement_value,
            optimize_points_slot_assignment=optimize_points_slot_assignment,
            best_slot_surplus=best_slot_surplus,
            negative_fallback_value=negative_fallback_value,
        )

    player_year_details: dict[str, list[dict[str, Any]]] = {}
    stash_scores_by_player: dict[str, float] = {}
    negative_year_players: set[str] = set()
    ir_candidate_players: set[str] = set()

    for player_id, meta_row in prep.player_meta.items():
        year_details: list[dict[str, object]] = []

        for year in prep.valuation_year_set:
            info = prep.per_player_year.get(player_id, {}).get(year, {})
            hit_points = float(info.get("hit_points", 0.0))
            pit_points = float(info.get("pit_points", 0.0))
            raw_hit_points = float(info.get("raw_hit_points", 0.0))
            raw_pit_points = float(info.get("raw_pit_points", 0.0))
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))
            hit_breakdown = (
                cast(dict[str, Any], info.get("hit_breakdown"))
                if isinstance(info.get("hit_breakdown"), dict)
                else prep.empty_hit_breakdown
            )
            pit_breakdown = (
                cast(dict[str, Any], info.get("pit_breakdown"))
                if isinstance(info.get("pit_breakdown"), dict)
                else prep.empty_pit_breakdown
            )

            hit_repl_map = year_hit_replacement.get(year, {})
            pit_repl_map = year_pit_replacement.get(year, {})
            hit_best_value, hit_best_slot, hit_best_replacement = best_slot_surplus(
                points=hit_points,
                eligible_slots=hit_slots,
                replacement_by_slot=hit_repl_map,
            )
            pit_best_value, pit_best_slot, pit_best_replacement = best_slot_surplus(
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
            hit_assigned_replacement = (
                float(hit_assignment.get("replacement", 0.0)) if isinstance(hit_assignment, dict) else 0.0
            )
            pit_assigned_replacement = (
                float(pit_assignment.get("replacement", 0.0)) if isinstance(pit_assignment, dict) else 0.0
            )
            projected_pit_appearances = float(info.get("projected_pit_appearances", 0.0))
            projected_pit_starts = float(info.get("projected_pit_starts", 0.0))
            pit_best_replacement, pit_best_value, pit_assigned_replacement, pit_assigned_value = (
                _apply_pitcher_replacement_adjustment(
                    pit_points=pit_points,
                    pit_best_slot=pit_best_slot,
                    pit_best_replacement=pit_best_replacement,
                    pit_best_value=pit_best_value,
                    pit_assigned_slot=pit_assigned_slot,
                    pit_assigned_replacement=pit_assigned_replacement,
                    pit_assigned_value=pit_assigned_value,
                    pit_assigned_points=pit_assigned_points,
                    projected_pit_appearances=projected_pit_appearances,
                    projected_pit_starts=projected_pit_starts,
                    starter_replacement=starter_pitcher_replacement_start_year,
                    reliever_replacement=reliever_pitcher_replacement_start_year,
                    zero_epsilon=points_centering_zero_epsilon,
                )
            )
            hit_selected_value = negative_fallback_value(
                best_value=hit_best_value,
                assigned_slot=hit_assigned_slot,
                assigned_value=hit_assigned_value,
            )
            pit_selected_value = negative_fallback_value(
                best_value=pit_best_value,
                assigned_slot=pit_assigned_slot,
                assigned_value=pit_assigned_value,
            )
            hit_selected_raw_points = (
                hit_assigned_points if hit_assigned_slot is not None else hit_points if hit_selected_value < 0.0 else 0.0
            )
            pit_selected_raw_points = (
                pit_assigned_points if pit_assigned_slot is not None else pit_points if pit_selected_value < 0.0 else 0.0
            )
            year_points, selected_raw_points, selected_side = _selected_points_summary(
                two_way=two_way,
                hit_selected_value=hit_selected_value,
                pit_selected_value=pit_selected_value,
                hit_assigned_slot=hit_assigned_slot,
                pit_assigned_slot=pit_assigned_slot,
                hit_selected_raw_points=hit_selected_raw_points,
                pit_selected_raw_points=pit_selected_raw_points,
            )

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
                if is_near_zero_playing_time(
                    player_id,
                    year,
                    hitter_ab_by_player_year=prep.hitter_ab_by_player_year,
                    pitcher_ip_by_player_year=prep.pitcher_ip_by_player_year,
                ):
                    has_ir_candidate_year = True
            ranking_values.append(
                raw_value
                * prospect_risk_multiplier(
                    year=year,
                    start_year=start_year,
                    profile=prep.player_profile.get(player_id, "hitter"),
                    minor_eligible=bool(prep.minor_eligibility_by_year.get((player_id, year), False)),
                    enabled=enable_prospect_risk_adjustment,
                )
            )

        player_year_details[player_id] = year_details
        stash_scores_by_player[player_id] = dynasty_keep_or_drop_values(
            ranking_values,
            prep.valuation_year_set,
            discount=float(discount),
            continuation_horizon_years=prep.keeper_continuation_horizon_years,
        ).raw_total
        if has_negative_year:
            negative_year_players.add(player_id)
        if has_ir_candidate_year:
            ir_candidate_players.add(player_id)

    stash_selection = select_points_stash_groups(
        stash_scores_by_player=stash_scores_by_player,
        use_h2h_roster_model=prep.use_h2h_roster_model,
        in_season_rostered_player_ids=in_season_rostered_player_ids,
        in_season_replacement_rank=in_season_replacement_rank,
        minor_eligibility_by_year=prep.minor_eligibility_by_year,
        valuation_year_set=prep.valuation_year_set,
        start_year=start_year,
        teams=teams,
        minors=minors,
        ir=ir,
        bench=bench,
        ir_candidate_players=ir_candidate_players,
        negative_year_players=negative_year_players,
        hitter_ab_by_player_year=prep.hitter_ab_by_player_year,
        pitcher_ip_by_player_year=prep.pitcher_ip_by_player_year,
    )
    modeled_minor_roster_ids = set(stash_selection.modeled_minor_roster_ids)
    modeled_ir_roster_ids = set(stash_selection.modeled_ir_roster_ids)
    in_season_rostered_player_ids = set(stash_selection.in_season_rostered_player_ids)
    in_season_replacement_rank = int(stash_selection.in_season_replacement_rank)

    result_rows = build_points_result_rows(
        player_meta=prep.player_meta,
        player_year_details=player_year_details,
        player_profile=prep.player_profile,
        minor_eligibility_by_year=prep.minor_eligibility_by_year,
        start_year=start_year,
        valuation_year_set=prep.valuation_year_set,
        discount=float(discount),
        continuation_horizon_years=prep.keeper_continuation_horizon_years,
        keeper_start_year_value_by_player=keeper_start_year_value_by_player,
        enable_prospect_risk_adjustment=enable_prospect_risk_adjustment,
        minor_stash_players=set(stash_selection.minor_stash_players),
        ir_stash_players=set(stash_selection.ir_stash_players),
        bench_stash_players=set(stash_selection.bench_stash_players),
        enable_ir_stash_relief=enable_ir_stash_relief,
        ir_negative_penalty=float(ir_negative_penalty),
        enable_bench_stash_relief=enable_bench_stash_relief,
        bench_negative_penalty=float(bench_negative_penalty),
        hitter_ab_by_player_year=prep.hitter_ab_by_player_year,
        pitcher_ip_by_player_year=prep.pitcher_ip_by_player_year,
    )

    return finalize_points_dynasty_output(
        result_rows=result_rows,
        valuation_year_set=prep.valuation_year_set,
        player_key_col=ctx.player_key_col,
        player_entity_key_col=ctx.player_entity_key_col,
        rostered_player_ids=rostered_player_ids,
        replacement_rank=replacement_rank,
        in_season_replacement_rank=in_season_replacement_rank,
        active_depth_per_team=prep.active_depth_per_team,
        in_season_depth_per_team=prep.in_season_depth_per_team,
        discount=float(discount),
        keeper_limit=keeper_limit,
        keeper_continuation_rank=prep.keeper_continuation_rank,
        points_valuation_mode=points_valuation_mode,
        weekly_starts_cap=weekly_starts_cap,
        allow_same_day_starts_overflow=allow_same_day_starts_overflow,
        weekly_acquisition_cap=weekly_acquisition_cap,
        use_h2h_roster_model=prep.use_h2h_roster_model,
        modeled_ir_roster_ids=modeled_ir_roster_ids,
        modeled_minor_roster_ids=modeled_minor_roster_ids,
        modeled_bench_hitters_per_team_by_year=usage.modeled_bench_hitters_per_team_by_year,
        modeled_bench_pitchers_per_team_by_year=usage.modeled_bench_pitchers_per_team_by_year,
        modeled_held_pitchers_per_team_by_year=usage.modeled_held_pitchers_per_team_by_year,
        modeled_held_starter_pitchers_per_team_by_year=modeled_held_starter_pitchers_per_team_by_year,
        modeled_held_relievers_per_team_by_year=modeled_held_relievers_per_team_by_year,
        starter_slot_capacity=prep.starter_slot_capacity,
        starter_pitcher_replacement_start_year=starter_pitcher_replacement_start_year,
        reliever_pitcher_replacement_start_year=reliever_pitcher_replacement_start_year,
        hitter_usage_diagnostics_by_year=usage.hitter_usage_diagnostics_by_year,
        pitcher_usage_diagnostics_by_year=usage.pitcher_usage_diagnostics_by_year,
        start_year=start_year,
        teams=teams,
    )
