"""Common-mode valuation math helpers extracted from dynasty_roto_values."""

from __future__ import annotations

import numpy as np
import pandas as pd

try:
    from backend.valuation.active_volume import (
        SYNTHETIC_SEASON_DAYS,
        VolumeEntry,
        allocate_hitter_usage_daily,
        allocate_pitcher_innings_budget,
        allocate_pitcher_usage_daily,
        annual_slot_capacity,
    )
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
    from backend.valuation.replacement import (
        compute_replacement_baselines as compute_replacement_baselines,
    )
    from backend.valuation.replacement import (
        compute_year_player_values_vs_replacement as compute_year_player_values_vs_replacement,
    )
    from backend.valuation.replacement import (
        _positive_save_guard_exempt_categories as _positive_save_guard_exempt_categories,
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
    from backend.valuation.two_way import combine_two_way as combine_two_way
    from backend.valuation.weighting import (
        _initial_hitter_weight as _initial_hitter_weight,
    )
    from backend.valuation.weighting import (
        _initial_pitcher_weight as _initial_pitcher_weight,
    )
except ImportError:
    from valuation.active_volume import (  # type: ignore[no-redef]
        SYNTHETIC_SEASON_DAYS,
        VolumeEntry,
        allocate_hitter_usage_daily,
        allocate_pitcher_innings_budget,
        allocate_pitcher_usage_daily,
        annual_slot_capacity,
    )
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
    from valuation.replacement import (  # type: ignore[no-redef]
        compute_replacement_baselines as compute_replacement_baselines,
    )
    from valuation.replacement import (
        compute_year_player_values_vs_replacement as compute_year_player_values_vs_replacement,
    )
    from valuation.replacement import (
        _positive_save_guard_exempt_categories as _positive_save_guard_exempt_categories,
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
    from valuation.two_way import combine_two_way as combine_two_way  # type: ignore[no-redef]
    from valuation.weighting import (  # type: ignore[no-redef]
        _initial_hitter_weight as _initial_hitter_weight,
    )
    from valuation.weighting import (
        _initial_pitcher_weight as _initial_pitcher_weight,
    )


COMMON_REVERSED_PITCH_CATS: set[str] = {"ERA", "WHIP"}
COMMON_RATE_HIT_CATS: set[str] = {"AVG", "OBP", "SLG", "OPS"}
_USAGE_EPSILON = 1e-9


def _zscore(s: pd.Series) -> pd.Series:
    x = s.astype(float)
    mu = float(x.mean())
    sd = float(x.std(ddof=0))
    if sd == 0.0 or np.isnan(sd):
        return x * 0.0
    return (x - mu) / sd


def _coerce_usage_share(value: float) -> float:
    return float(min(max(value, 0.0), 1.0))


def _common_active_volume_context(
    year: int,
    bat_y: pd.DataFrame,
    pit_y: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    *,
    hit_categories: list[str],
    pit_categories: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, float | int | None], dict[str, float | int | None]]:
    bat_adj = bat_y.copy()
    pit_adj = pit_y.copy()

    hitter_slot_capacity = annual_slot_capacity(
        lg.hitter_slots,
        teams=lg.n_teams,
        season_capacity_per_slot=float(SYNTHETIC_SEASON_DAYS),
    )
    pitcher_slot_capacity = annual_slot_capacity(
        lg.pitcher_slots,
        teams=lg.n_teams,
        season_capacity_per_slot=float(SYNTHETIC_SEASON_DAYS),
    )

    bat_quality = pd.Series(0.0, index=bat_adj.index, dtype="float64")
    if "G" in bat_adj.columns:
        bat_g = pd.to_numeric(bat_adj["G"], errors="coerce")
        bat_weights = _initial_hitter_weight(bat_adj, categories=hit_categories)
        bat_quality = bat_weights.divide(bat_g.where(bat_g > 0.0), fill_value=0.0).replace([np.inf, -np.inf], 0.0).fillna(0.0)

    hitter_entries: list[VolumeEntry] = []
    fallback_hitter_ids: set[str] = set()
    hitter_assigned_games: dict[str, float] = {}
    hitter_usage_share: dict[str, float] = {}
    hitter_requested_games = 0.0
    for idx, row in bat_adj.iterrows():
        player = str(row.get("Player") or "").strip()
        if not player:
            continue
        ab = _coerce_non_negative_float(row.get("AB", 0.0))
        if ab <= 0.0:
            hitter_usage_share[player] = 0.0
            hitter_assigned_games[player] = 0.0
            continue
        slots = eligible_hit_slots(parse_hit_positions(row.get("Pos", ""))) & set(hitter_slot_capacity.keys())
        if not slots:
            hitter_usage_share[player] = 0.0
            hitter_assigned_games[player] = 0.0
            continue
        projected_games = _coerce_non_negative_float(row.get("G", 0.0))
        if projected_games <= 0.0:
            fallback_hitter_ids.add(player)
            hitter_usage_share[player] = 1.0
            hitter_assigned_games[player] = 0.0
            continue
        hitter_requested_games += projected_games
        hitter_entries.append(
            VolumeEntry(
                player_id=player,
                projected_volume=projected_games,
                quality=float(bat_quality.loc[idx]),
                slots=set(slots),
                year=year,
            )
        )

    hitter_usage = allocate_hitter_usage_daily(
        hitter_entries,
        slot_capacity=hitter_slot_capacity,
    )
    hitter_assigned_games.update(hitter_usage.assigned_volume_by_player)
    hitter_usage_share.update(hitter_usage.usage_share_by_player)

    for idx, row in bat_adj.iterrows():
        player = str(row.get("Player") or "").strip()
        if not player:
            continue
        share = 1.0 if player in fallback_hitter_ids else _coerce_usage_share(float(hitter_usage_share.get(player, 0.0)))
        bat_adj.at[idx, "_UsageShare"] = share
        bat_adj.at[idx, "_AssignedGames"] = float(hitter_assigned_games.get(player, 0.0))
        bat_adj.at[idx, "_ProjectedGames"] = _coerce_non_negative_float(row.get("G", 0.0))
        for col in HIT_COMPONENT_COLS:
            bat_adj.at[idx, col] = float(bat_adj.at[idx, col]) * share

    pit_quality = pd.Series(0.0, index=pit_adj.index, dtype="float64")
    if "G" in pit_adj.columns:
        pit_g = pd.to_numeric(pit_adj["G"], errors="coerce")
        pit_weights = _initial_pitcher_weight(pit_adj, categories=pit_categories)
        pit_quality = pit_weights.divide(pit_g.where(pit_g > 0.0), fill_value=0.0).replace([np.inf, -np.inf], 0.0).fillna(0.0)

    pitcher_entries: list[VolumeEntry] = []
    pitcher_start_volume: dict[str, float] = {}
    fallback_pitcher_ids: set[str] = set()
    pitcher_usage_share: dict[str, float] = {}
    pitcher_assigned_starts: dict[str, float] = {}
    pitcher_assigned_non_starts: dict[str, float] = {}
    pitcher_assigned_appearances: dict[str, float] = {}

    for idx, row in pit_adj.iterrows():
        player = str(row.get("Player") or "").strip()
        if not player:
            continue
        ip = _coerce_non_negative_float(row.get("IP", 0.0))
        if ip <= 0.0:
            pitcher_usage_share[player] = 0.0
            pitcher_assigned_starts[player] = 0.0
            pitcher_assigned_non_starts[player] = 0.0
            pitcher_assigned_appearances[player] = 0.0
            continue
        slots = eligible_pit_slots(parse_pit_positions(row.get("Pos", ""))) & set(pitcher_slot_capacity.keys())
        if not slots:
            pitcher_usage_share[player] = 0.0
            pitcher_assigned_starts[player] = 0.0
            pitcher_assigned_non_starts[player] = 0.0
            pitcher_assigned_appearances[player] = 0.0
            continue
        projected_appearances = _coerce_non_negative_float(row.get("G", 0.0))
        if projected_appearances <= 0.0:
            fallback_pitcher_ids.add(player)
            pitcher_usage_share[player] = 1.0
            pitcher_assigned_starts[player] = 0.0
            pitcher_assigned_non_starts[player] = 0.0
            pitcher_assigned_appearances[player] = 0.0
            continue
        projected_starts = min(_coerce_non_negative_float(row.get("GS", 0.0)), projected_appearances)
        if projected_starts < 1.0:
            projected_starts = 0.0
        pitcher_start_volume[player] = projected_starts
        pitcher_entries.append(
            VolumeEntry(
                player_id=player,
                projected_volume=projected_appearances,
                quality=float(pit_quality.loc[idx]),
                slots=set(slots),
                year=year,
            )
        )

    pitcher_usage = allocate_pitcher_usage_daily(
        pitcher_entries,
        start_volume_by_player=pitcher_start_volume,
        slot_capacity=pitcher_slot_capacity,
        capped_start_budget=None,
    )
    pitcher_usage_share.update(pitcher_usage.usage_share_by_player)
    pitcher_assigned_starts.update(pitcher_usage.assigned_starts_by_player)
    pitcher_assigned_non_starts.update(pitcher_usage.assigned_non_start_appearances_by_player)
    pitcher_assigned_appearances.update(pitcher_usage.assigned_appearances_by_player)

    for idx, row in pit_adj.iterrows():
        player = str(row.get("Player") or "").strip()
        if not player:
            continue
        share = 1.0 if player in fallback_pitcher_ids else _coerce_usage_share(float(pitcher_usage_share.get(player, 0.0)))
        pit_adj.at[idx, "_UsageShare"] = share
        pit_adj.at[idx, "_AssignedStarts"] = float(pitcher_assigned_starts.get(player, 0.0))
        pit_adj.at[idx, "_AssignedNonStartAppearances"] = float(pitcher_assigned_non_starts.get(player, 0.0))
        pit_adj.at[idx, "_AssignedAppearances"] = float(pitcher_assigned_appearances.get(player, 0.0))
        pit_adj.at[idx, "_ProjectedAppearances"] = _coerce_non_negative_float(row.get("G", 0.0))
        pit_adj.at[idx, "_ProjectedStarts"] = _coerce_non_negative_float(row.get("GS", 0.0))
        for col in PIT_COMPONENT_COLS:
            pit_adj.at[idx, col] = float(pit_adj.at[idx, col]) * share

    ip_budget = float(lg.ip_max) * max(int(lg.n_teams), 1) if lg.ip_max is not None else None
    pitcher_ip_usage_share: dict[str, float] = {}
    pitcher_assigned_ip: dict[str, float] = {}
    pitcher_ip_allocation = None
    if ip_budget is not None:
        pit_ip_quality = _initial_pitcher_weight(pit_adj, categories=pit_categories)
        ip_entries = [
            VolumeEntry(
                player_id=str(row.get("Player") or "").strip(),
                projected_volume=_coerce_non_negative_float(row.get("IP", 0.0)),
                quality=float(pit_ip_quality.loc[idx]) / max(_coerce_non_negative_float(row.get("IP", 0.0)), _USAGE_EPSILON),
                slots={"IP_CAP"},
                year=year,
            )
            for idx, row in pit_adj.iterrows()
            if str(row.get("Player") or "").strip() and _coerce_non_negative_float(row.get("IP", 0.0)) > 0.0
        ]
        pitcher_ip_allocation = allocate_pitcher_innings_budget(
            ip_entries,
            ip_budget=ip_budget,
        )
        pitcher_ip_usage_share.update(pitcher_ip_allocation.ip_usage_share_by_player)
        pitcher_assigned_ip.update(pitcher_ip_allocation.assigned_ip_by_player)

        for idx, row in pit_adj.iterrows():
            player = str(row.get("Player") or "").strip()
            if not player:
                continue
            ip_share = _coerce_usage_share(float(pitcher_ip_usage_share.get(player, 0.0)))
            if _coerce_non_negative_float(row.get("IP", 0.0)) <= 0.0:
                ip_share = 0.0
            pit_adj.at[idx, "_AppearanceUsageShare"] = float(pit_adj.at[idx, "_UsageShare"])
            pit_adj.at[idx, "_IpUsageShare"] = ip_share
            pit_adj.at[idx, "_AssignedIP"] = float(pitcher_assigned_ip.get(player, 0.0))
            pit_adj.at[idx, "_ProjectedIP"] = _coerce_non_negative_float(row.get("IP", 0.0))
            pit_adj.at[idx, "_UsageShare"] = float(pit_adj.at[idx, "_UsageShare"]) * ip_share
            for col in PIT_COMPONENT_COLS:
                pit_adj.at[idx, col] = float(pit_adj.at[idx, col]) * ip_share
    else:
        for idx, row in pit_adj.iterrows():
            player = str(row.get("Player") or "").strip()
            if not player:
                continue
            pit_adj.at[idx, "_AppearanceUsageShare"] = float(pit_adj.at[idx, "_UsageShare"])
            pit_adj.at[idx, "_IpUsageShare"] = 1.0 if _coerce_non_negative_float(row.get("IP", 0.0)) > 0.0 else 0.0
            pit_adj.at[idx, "_AssignedIP"] = _coerce_non_negative_float(row.get("IP", 0.0))
            pit_adj.at[idx, "_ProjectedIP"] = _coerce_non_negative_float(row.get("IP", 0.0))

    hitter_diagnostics: dict[str, float | int | None] = {
        "slot_game_capacity": round(float(sum(hitter_slot_capacity.values())), 4),
        "assigned_hitter_games": round(float(hitter_usage.total_assigned_volume), 4),
        "unused_hitter_games": round(max(float(hitter_requested_games) - float(hitter_usage.total_assigned_volume), 0.0), 4),
        "fallback_hitter_count": int(len(fallback_hitter_ids)),
        "synthetic_season_days": int(SYNTHETIC_SEASON_DAYS),
    }
    pitcher_diagnostics: dict[str, float | int | None] = {
        "slot_appearance_capacity": round(float(sum(pitcher_slot_capacity.values())), 4),
        "assigned_starts": round(float(pitcher_usage.total_assigned_starts), 4),
        "assigned_non_start_appearances": round(float(pitcher_usage.total_assigned_non_start_appearances), 4),
        "capped_start_budget": None,
        "fallback_pitcher_count": int(len(fallback_pitcher_ids)),
        "synthetic_season_days": int(SYNTHETIC_SEASON_DAYS),
        "ip_cap_budget": round(float(ip_budget), 4) if ip_budget is not None else None,
        "requested_pitcher_ip_pre_cap": round(
            float(pitcher_ip_allocation.total_requested_ip) if pitcher_ip_allocation is not None else float(pit_adj["IP"].sum()),
            4,
        ),
        "assigned_pitcher_ip": round(
            float(pitcher_ip_allocation.total_assigned_ip) if pitcher_ip_allocation is not None else float(pit_adj["IP"].sum()),
            4,
        ),
        "unused_pitcher_ip": round(float(pitcher_ip_allocation.unused_ip), 4)
        if pitcher_ip_allocation is not None and pitcher_ip_allocation.unused_ip is not None
        else None,
        "trimmed_pitcher_ip": round(float(pitcher_ip_allocation.trimmed_ip), 4)
        if pitcher_ip_allocation is not None
        else 0.0,
        "ip_cap_binding": bool(pitcher_ip_allocation.ip_cap_binding) if pitcher_ip_allocation is not None else False,
    }

    return bat_adj, pit_adj, hitter_diagnostics, pitcher_diagnostics


def _active_common_hit_categories(lg: CommonDynastyRotoSettings) -> list[str]:
    configured = getattr(lg, "hitter_categories", None)
    if not configured:
        return list(HIT_CATS)
    wanted = {str(cat).strip().upper() for cat in configured if str(cat).strip()}
    selected = [cat for cat in HIT_CATS if cat.upper() in wanted]
    return selected or list(HIT_CATS)


def _active_common_pitch_categories(lg: CommonDynastyRotoSettings) -> list[str]:
    configured = getattr(lg, "pitcher_categories", None)
    if not configured:
        return list(PIT_CATS)
    wanted = {str(cat).strip().upper() for cat in configured if str(cat).strip()}
    selected = [cat for cat in PIT_CATS if cat.upper() in wanted]
    return selected or list(PIT_CATS)


def compute_year_context(
    year: int,
    bat: pd.DataFrame,
    pit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng_seed: int | None = None,
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

    bat_y, pit_y, hitter_usage_diagnostics, pitcher_usage_diagnostics = _common_active_volume_context(
        year,
        bat_y,
        pit_y,
        lg,
        hit_categories=hit_categories,
        pit_categories=pit_categories,
    )

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
        fill_to_ip_min=True,
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
        "hitter_usage_diagnostics": hitter_usage_diagnostics,
        "pitcher_usage_diagnostics": pitcher_usage_diagnostics,
    }


def compute_year_player_values(ctx: dict, lg: CommonDynastyRotoSettings) -> tuple[pd.DataFrame, pd.DataFrame]:
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
        best_stat_sgps: dict[str, float] = {}

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

            val = 0.0
            stat_sgps: dict[str, float] = {}
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
        best_stat_sgps: dict[str, float] = {}

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
                fill_to_ip_min=True,
            )

            new_pit_cats = common_pitch_category_totals(new_tot_bounded)
            delta: dict[str, float] = {}
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
                    positive_exempt_categories=_positive_save_guard_exempt_categories(
                        lg=lg,
                        pit_categories=pit_categories,
                        slot=slot,
                        row=row,
                    ),
                )
                _apply_low_volume_ratio_guard(
                    delta,
                    pit_categories=pit_categories,
                    pitcher_ip=_coerce_non_negative_float(row.get("IP", 0.0)),
                    slot_ip_reference=_coerce_non_negative_float(b.get("IP", 0.0)),
                )

            val = 0.0
            stat_sgps: dict[str, float] = {}
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
