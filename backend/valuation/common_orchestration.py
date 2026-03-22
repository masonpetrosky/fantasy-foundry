"""Common-mode valuation orchestration extracted from legacy dynasty module."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Set

import pandas as pd

try:
    from backend.core.points_value import (
        apply_dynasty_aggregation_adjustments as _apply_dynasty_aggregation_adjustments,
    )
    from backend.core.points_value import (
        dynasty_keep_or_drop_values as _dynasty_keep_or_drop_values,
    )
    from backend.valuation.common_math import (
        combine_two_way,
        compute_replacement_baselines,
        compute_year_context,
        compute_year_player_values,
        compute_year_player_values_vs_replacement,
    )
    from backend.valuation.dynasty_aggregation import dynasty_keep_or_drop_value
    from backend.valuation.dynasty_value_adjustments import (
        _adjust_dynasty_year_value,
        _coerce_projected_volume,
        _dynasty_year_adjustment_detail,
        _is_near_zero_playing_time,
        _piecewise_age_factor,
        _position_profile,
        _prospect_risk_multiplier,
        _year_risk_multiplier,
    )
    from backend.valuation.minor_eligibility import (
        _fillna_bool,
        _non_vacant_player_names,
        _players_with_playing_time,
        _resolve_minor_eligibility_by_year,
    )
    from backend.valuation.models import (
        HIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )
    from backend.valuation.projection_compat import (
        COMMON_COLUMN_ALIASES,
        DERIVED_HIT_RATE_COLS,
        DERIVED_PIT_RATE_COLS,
        PLAYER_ENTITY_KEY_COL,
        _add_player_identity_keys,
        _attach_identity_columns_to_output,
        _build_player_identity_lookup,
        _find_projection_date_col,
        average_recent_projections,
        normalize_input_schema,
        numeric_stat_cols_for_recent_avg,
        projection_meta_for_start_year,
        recompute_common_rates_hit,
        recompute_common_rates_pit,
        reorder_detail_columns,
        require_cols,
    )
    from backend.valuation.year_context import CommonYearContext
except ImportError:  # pragma: no cover - direct script execution fallback
    from core.points_value import (  # type: ignore
        apply_dynasty_aggregation_adjustments as _apply_dynasty_aggregation_adjustments,
    )
    from core.points_value import (  # type: ignore[no-redef]
        dynasty_keep_or_drop_values as _dynasty_keep_or_drop_values,
    )
    from valuation.common_math import (  # type: ignore
        combine_two_way,
        compute_replacement_baselines,
        compute_year_context,
        compute_year_player_values,
        compute_year_player_values_vs_replacement,
    )
    from valuation.dynasty_aggregation import dynasty_keep_or_drop_value  # type: ignore[no-redef]
    from valuation.dynasty_value_adjustments import (  # type: ignore
        _adjust_dynasty_year_value,
        _coerce_projected_volume,
        _dynasty_year_adjustment_detail,
        _is_near_zero_playing_time,
        _piecewise_age_factor,
        _position_profile,
        _prospect_risk_multiplier,
        _year_risk_multiplier,
    )
    from valuation.minor_eligibility import (  # type: ignore
        _fillna_bool,
        _non_vacant_player_names,
        _players_with_playing_time,
        _resolve_minor_eligibility_by_year,
    )
    from valuation.models import (  # type: ignore[no-redef]
        HIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )
    from valuation.projection_compat import (  # type: ignore
        COMMON_COLUMN_ALIASES,
        DERIVED_HIT_RATE_COLS,
        DERIVED_PIT_RATE_COLS,
        PLAYER_ENTITY_KEY_COL,
        _add_player_identity_keys,
        _attach_identity_columns_to_output,
        _build_player_identity_lookup,
        _find_projection_date_col,
        average_recent_projections,
        normalize_input_schema,
        numeric_stat_cols_for_recent_avg,
        projection_meta_for_start_year,
        recompute_common_rates_hit,
        recompute_common_rates_pit,
        reorder_detail_columns,
        require_cols,
    )
    from valuation.year_context import CommonYearContext  # type: ignore[no-redef]
try:
    from backend.valuation.common_centering import (
        _apply_dynasty_centering,
        _blend_replacement_frame,
        _forced_roster_value,
        _select_roster_groups,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from valuation.common_centering import (  # type: ignore[no-redef]
        _apply_dynasty_centering,
        _blend_replacement_frame,
        _forced_roster_value,
        _select_roster_groups,
    )

__all__ = [
    "_adjust_dynasty_year_value",
    "_apply_dynasty_centering",
    "_blend_replacement_frame",
    "_forced_roster_value",
    "_piecewise_age_factor",
    "_position_profile",
    "_prospect_risk_multiplier",
    "_year_risk_multiplier",
    "calculate_common_dynasty_values",
]


_COMMON_CONTINUATION_TAIL_START_YEAR = 4
_COMMON_CONTINUATION_TAIL_DECAY = 0.80


def _build_stash_frame(
    base_frame: pd.DataFrame,
    *,
    years: List[int],
    value_columns_by_year: Dict[int, object],
    start_year: int,
    lg: CommonDynastyRotoSettings,
    age_by_player: Dict[str, float | None],
    profile_by_player: Dict[str, str],
    minor_eligibility_by_year: Dict[tuple[str, int], bool],
    minor_stash_players: Set[str],
    bench_stash_players: Set[str],
    ir_stash_players: Set[str],
    elig_df: pd.DataFrame,
    hitter_ab_by_player_year: Dict[tuple[str, int], float],
    pitcher_ip_by_player_year: Dict[tuple[str, int], float],
) -> tuple[pd.DataFrame, Set[str], Set[str]]:
    scores: List[float] = []
    negative_year_players: Set[str] = set()
    ir_candidate_players: Set[str] = set()

    for _, row in base_frame.iterrows():
        player = str(row.get("Player") or "")
        player_age = age_by_player.get(player)
        player_profile = profile_by_player.get(player, "hitter")
        adjusted_values: List[float] = []
        has_negative_year = False
        has_ir_candidate_year = False

        for year in years:
            raw_key = value_columns_by_year[int(year)]
            raw_value = row.get(raw_key)
            if pd.isna(raw_value):
                raw_value = 0.0

            adjusted = _adjust_dynasty_year_value(
                float(raw_value),
                player=player,
                year=int(year),
                start_year=int(start_year),
                age_start=player_age,
                profile=player_profile,
                lg=lg,
                minor_eligibility_by_year=minor_eligibility_by_year,
                minor_stash_players=minor_stash_players,
                bench_stash_players=bench_stash_players,
                ir_stash_players=ir_stash_players,
                hitter_ab_by_player_year=hitter_ab_by_player_year,
                pitcher_ip_by_player_year=pitcher_ip_by_player_year,
            )
            adjusted_values.append(adjusted)
            if adjusted < 0.0:
                has_negative_year = True
                if _is_near_zero_playing_time(
                    player,
                    int(year),
                    hitter_ab_by_player_year=hitter_ab_by_player_year,
                    pitcher_ip_by_player_year=pitcher_ip_by_player_year,
                ):
                    has_ir_candidate_year = True

        if has_negative_year:
            negative_year_players.add(player)
        if has_ir_candidate_year:
            ir_candidate_players.add(player)
        aggregation_values = _apply_dynasty_aggregation_adjustments(
            adjusted_values,
            years,
            continuation_tail_start_year=_COMMON_CONTINUATION_TAIL_START_YEAR,
            continuation_tail_decay=_COMMON_CONTINUATION_TAIL_DECAY,
        )
        scores.append(dynasty_keep_or_drop_value(aggregation_values, years, lg.discount))

    stash = base_frame[["Player"]].copy()
    stash["StashScore"] = scores
    stash = stash.merge(elig_df, on="Player", how="left")
    stash["minor_eligible"] = _fillna_bool(stash["minor_eligible"])
    stash = stash.sort_values("StashScore", ascending=False).reset_index(drop=True)
    return stash, negative_year_players, ir_candidate_players

def calculate_common_dynasty_values(
    excel_path: str,
    lg: CommonDynastyRotoSettings,
    start_year: Optional[int] = None,
    years: Optional[List[int]] = None,
    verbose: bool = True,
    return_details: bool = False,
    seed: int = 0,
):
    """Compute common-mode dynasty values.

    If return_details=True, also returns (bat_detail, pit_detail) tables that:
      - collapse duplicate (Player, Year) rows by averaging projections from the most recent date
      - keep the original input columns in roughly the same order
      - attach YearValue/BestSlot (per side) and DynastyValue to each Player/Year row
    """
    bat_raw = normalize_input_schema(pd.read_excel(excel_path, sheet_name="Bat"), COMMON_COLUMN_ALIASES)
    pit_raw = normalize_input_schema(pd.read_excel(excel_path, sheet_name="Pitch"), COMMON_COLUMN_ALIASES)

    bat_input_cols = list(bat_raw.columns)
    pit_input_cols = list(pit_raw.columns)
    bat_date_col = _find_projection_date_col(bat_raw)
    pit_date_col = _find_projection_date_col(pit_raw)

    bat_raw, pit_raw = _add_player_identity_keys(bat_raw, pit_raw)
    identity_lookup = _build_player_identity_lookup(bat_raw, pit_raw)
    bat_raw["Player"] = bat_raw[PLAYER_ENTITY_KEY_COL].astype("string").fillna("").str.strip()
    pit_raw["Player"] = pit_raw[PLAYER_ENTITY_KEY_COL].astype("string").fillna("").str.strip()

    # Average *all numeric stat columns* (except derived rates and Age) so the
    # aggregated detail tabs reflect the true averaged projections.
    bat_stat_cols = numeric_stat_cols_for_recent_avg(
        bat_raw,
        group_cols=["Player", "Year"],
        exclude_cols={"Age"} | DERIVED_HIT_RATE_COLS,
    )
    pit_stat_cols = numeric_stat_cols_for_recent_avg(
        pit_raw,
        group_cols=["Player", "Year"],
        exclude_cols={"Age"} | DERIVED_PIT_RATE_COLS,
    )

    bat = average_recent_projections(bat_raw, bat_stat_cols)
    pit = average_recent_projections(pit_raw, pit_stat_cols)

    # Recompute rates after averaging components
    bat = recompute_common_rates_hit(bat)
    pit = recompute_common_rates_pit(pit)

    # Backfill optional hitter rate components when source files omit them.
    for missing_col in ("BB", "HBP", "SF", "2B", "3B"):
        if missing_col not in bat.columns:
            bat[missing_col] = 0.0

    # Required fields
    require_cols(bat, ["Player", "Year", "Team", "Age", "Pos"] + HIT_COMPONENT_COLS, "Bat")
    require_cols(pit, ["Player", "Year", "Team", "Age", "Pos"], "Pitch")
    require_cols(pit, ["IP", "W", "K", "ER", "H", "BB"], "Pitch")

    # Ensure SV exists (fallback from legacy combined save/hold columns when needed).
    if "SV" not in pit.columns:
        if {"SVH", "HLD"}.issubset(pit.columns):
            pit["SV"] = (pit["SVH"] - pit["HLD"]).clip(lower=0.0).fillna(0.0)
        elif "SVH" in pit.columns:
            pit["SV"] = pit["SVH"].fillna(0.0)
        else:
            pit["SV"] = 0.0
    pit["SV"] = pit["SV"].fillna(0.0)

    # Keep SVH available for exports/other modes.
    if "SVH" not in pit.columns:
        if {"SV", "HLD"}.issubset(pit.columns):
            pit["SVH"] = pit["SV"].fillna(0.0) + pit["HLD"].fillna(0.0)
        else:
            pit["SVH"] = pit["SV"].fillna(0.0)
    pit["SVH"] = pit["SVH"].fillna(0.0)

    # Ensure QS/QA3 both exist (fallback each way for legacy source schemas).
    if "QS" not in pit.columns:
        if "QA3" in pit.columns:
            pit["QS"] = pit["QA3"].fillna(0.0)
        else:
            pit["QS"] = 0.0
    if "QA3" not in pit.columns:
        if "QS" in pit.columns:
            pit["QA3"] = pit["QS"].fillna(0.0)
        else:
            pit["QA3"] = 0.0
    pit["QS"] = pit["QS"].fillna(0.0)
    pit["QA3"] = pit["QA3"].fillna(0.0)

    if start_year is None:
        start_year = int(min(bat["Year"].min(), pit["Year"].min()))

    if years is None:
        max_year = int(max(bat["Year"].max(), pit["Year"].max()))
        years = [y for y in range(start_year, start_year + lg.horizon_years) if y <= max_year]

    if not years:
        raise ValueError("No valuation years available after applying start year / horizon to projection file years.")

    # Projection metadata: how many projections were averaged and the oldest date used
    proj_meta = projection_meta_for_start_year(bat, pit, start_year)

    years_set = {int(y) for y in years}
    start_rows = pd.concat(
        [
            bat[bat["Year"] == int(start_year)][["Player", "Age", "Pos"]],
            pit[pit["Year"] == int(start_year)][["Player", "Age", "Pos"]],
        ],
        ignore_index=True,
    )
    age_by_player: Dict[str, float | None] = {}
    profile_by_player: Dict[str, str] = {}
    if not start_rows.empty:
        for player, group in start_rows.groupby("Player"):
            ages = pd.to_numeric(group["Age"], errors="coerce").dropna()
            age_by_player[str(player)] = float(ages.iloc[0]) if not ages.empty else None
            pos_text = "/".join(
                sorted(
                    {
                        str(value).strip()
                        for value in group["Pos"].tolist()
                        if str(value).strip()
                    }
                )
            )
            profile_by_player[str(player)] = _position_profile(pos_text)
    elig_year_df = _resolve_minor_eligibility_by_year(
        bat,
        pit,
        years=years,
        hitter_usage_max=lg.minor_ab_max,
        pitcher_usage_max=lg.minor_ip_max,
        hitter_age_max=lg.minor_age_max_hit,
        pitcher_age_max=lg.minor_age_max_pit,
    )
    start_minor = elig_year_df[elig_year_df["Year"] == int(start_year)][["Player", "minor_eligible"]].copy()
    if start_minor.empty:
        elig_df = pd.DataFrame(columns=["Player", "minor_eligible"])
    else:
        elig_df = start_minor.groupby("Player", as_index=False)["minor_eligible"].max()

    active_per_team = sum(lg.hitter_slots.values()) + sum(lg.pitcher_slots.values())
    total_active_slots = lg.n_teams * active_per_team
    total_minor_slots = lg.n_teams * lg.minor_slots
    total_bench_slots = lg.n_teams * lg.bench_slots
    total_ir_slots = lg.n_teams * lg.ir_slots

    hitter_ab_by_player_year = {
        (str(row.Player), int(row.Year)): _coerce_projected_volume(row.AB)
        for row in bat[["Player", "Year", "AB"]].itertuples(index=False)
    }
    pitcher_ip_by_player_year = {
        (str(row.Player), int(row.Year)): _coerce_projected_volume(row.IP)
        for row in pit[["Player", "Year", "IP"]].itertuples(index=False)
    }

    # PASS 1: average-starter values to estimate who is rostered in a deep league.
    # Each year's context + player values are independent, so compute in parallel.
    year_contexts: Dict[int, CommonYearContext] = {}
    year_tables_avg: List[pd.DataFrame] = []

    def _compute_year_pass1(y: int) -> tuple[int, CommonYearContext, pd.DataFrame]:
        if verbose:
            print(f"Year {y}: baseline + SGP + player values (avg-starter pass) ...")
        ctx = compute_year_context(y, bat, pit, lg, rng_seed=seed + y)
        hit_vals, pit_vals = compute_year_player_values(ctx, lg)
        combined = combine_two_way(hit_vals, pit_vals, two_way=lg.two_way)
        return y, ctx, combined

    with ThreadPoolExecutor(max_workers=min(len(years), 4)) as executor:
        for y, ctx, combined in executor.map(_compute_year_pass1, years):
            year_contexts[y] = ctx
            year_tables_avg.append(combined)

    start_ctx = year_contexts.get(start_year)
    active_floor_names = (
        _non_vacant_player_names(start_ctx.assigned_hit if start_ctx is not None else None)
        | _non_vacant_player_names(start_ctx.assigned_pit if start_ctx is not None else None)
    )
    active_candidate_players = _players_with_playing_time(bat, pit, [int(start_year)])

    all_year_avg = pd.concat(year_tables_avg, ignore_index=True)
    wide_avg = all_year_avg.pivot_table(index="Player", columns="Year", values="YearValue", aggfunc="max").reset_index()
    for y in years:
        if y not in wide_avg.columns:
            wide_avg[y] = 0.0

    minor_eligibility_by_year = (
        {
            (str(row.Player), int(row.Year)): bool(row.minor_eligible)
            for row in elig_year_df.itertuples(index=False)
            if int(row.Year) in years_set
        }
        if not elig_year_df.empty
        else {}
    )
    minor_candidate_players = set(
        elig_df.loc[_fillna_bool(elig_df.get("minor_eligible", pd.Series(dtype="boolean"))), "Player"].astype(str)
    )
    empty_players: Set[str] = set()
    stash_sorted_base, negative_year_players, ir_candidate_players = _build_stash_frame(
        wide_avg,
        years=years,
        value_columns_by_year={int(year): int(year) for year in years},
        start_year=int(start_year),
        lg=lg,
        age_by_player=age_by_player,
        profile_by_player=profile_by_player,
        minor_eligibility_by_year=minor_eligibility_by_year,
        minor_stash_players=empty_players,
        bench_stash_players=empty_players,
        ir_stash_players=empty_players,
        elig_df=elig_df,
        hitter_ab_by_player_year=hitter_ab_by_player_year,
        pitcher_ip_by_player_year=pitcher_ip_by_player_year,
    )
    provisional_groups = _select_roster_groups(
        stash_sorted_base,
        total_minor_slots=total_minor_slots,
        total_ir_slots=total_ir_slots,
        total_bench_slots=total_bench_slots,
        total_active_slots=total_active_slots,
        active_floor_names=active_floor_names,
        minor_candidate_players=minor_candidate_players,
        ir_candidate_players=ir_candidate_players,
        bench_candidate_players=negative_year_players,
        active_candidate_players=active_candidate_players,
    )
    provisional_minor_players = set(provisional_groups["minor"]["Player"].astype(str).tolist())
    provisional_ir_players = set(provisional_groups["ir"]["Player"].astype(str).tolist()) & ir_candidate_players
    provisional_bench_players = set(provisional_groups["bench"]["Player"].astype(str).tolist()) & negative_year_players

    stash_sorted, final_negative_year_players, final_ir_candidate_players = _build_stash_frame(
        wide_avg,
        years=years,
        value_columns_by_year={int(year): int(year) for year in years},
        start_year=int(start_year),
        lg=lg,
        age_by_player=age_by_player,
        profile_by_player=profile_by_player,
        minor_eligibility_by_year=minor_eligibility_by_year,
        minor_stash_players=provisional_minor_players,
        bench_stash_players=provisional_bench_players,
        ir_stash_players=provisional_ir_players,
        elig_df=elig_df,
        hitter_ab_by_player_year=hitter_ab_by_player_year,
        pitcher_ip_by_player_year=pitcher_ip_by_player_year,
    )
    final_groups = _select_roster_groups(
        stash_sorted,
        total_minor_slots=total_minor_slots,
        total_ir_slots=total_ir_slots,
        total_bench_slots=total_bench_slots,
        total_active_slots=total_active_slots,
        active_floor_names=active_floor_names,
        minor_candidate_players=minor_candidate_players,
        ir_candidate_players=final_ir_candidate_players,
        bench_candidate_players=final_negative_year_players,
        active_candidate_players=active_candidate_players,
    )
    minor_stash_players = set(final_groups["minor"]["Player"].astype(str).tolist()) & minor_candidate_players
    ir_stash_players = set(final_groups["ir"]["Player"].astype(str).tolist()) & final_ir_candidate_players
    bench_stash_players = set(final_groups["bench"]["Player"].astype(str).tolist()) & final_negative_year_players
    rostered_names: Set[str] = (
        set(final_groups["active"]["Player"].astype(str).tolist())
        | set(final_groups["bench"]["Player"].astype(str).tolist())
        | set(final_groups["ir"]["Player"].astype(str).tolist())
        | set(final_groups["minor"]["Player"].astype(str).tolist())
    )

    # PASS 2: replacement-level per-year values from the unrostered pool.
    # By default, replacement baselines are frozen from start_year.
    year_tables: List[pd.DataFrame] = []
    hit_year_tables: List[pd.DataFrame] = []
    pit_year_tables: List[pd.DataFrame] = []

    frozen_repl_hit: Optional[pd.DataFrame] = None
    frozen_repl_pit: Optional[pd.DataFrame] = None
    blend_enabled = bool(lg.freeze_replacement_baselines and getattr(lg, "enable_replacement_blend", False))
    blend_alpha = float(min(max(getattr(lg, "replacement_blend_alpha", 0.40), 0.0), 1.0))
    if lg.freeze_replacement_baselines:
        start_ctx_for_replacement = year_contexts.get(start_year)
        if start_ctx_for_replacement is None:
            raise ValueError(
                f"Start year {start_year} context is unavailable for replacement baseline calculation."
            )
        frozen_repl_hit, frozen_repl_pit = compute_replacement_baselines(
            start_ctx_for_replacement,
            lg,
            rostered_names,
            n_repl=lg.n_teams,
        )

    for y in years:
        if verbose:
            print(f"Year {y}: replacement baselines + player values (replacement pass) ...")
        ctx = year_contexts[y]
        if lg.freeze_replacement_baselines:
            # Reuse a fixed replacement baseline from the start year.
            repl_hit = frozen_repl_hit
            repl_pit = frozen_repl_pit
            if blend_enabled:
                current_repl_hit, current_repl_pit = compute_replacement_baselines(
                    ctx,
                    lg,
                    rostered_names,
                    n_repl=lg.n_teams,
                )
                if repl_hit is not None:
                    repl_hit = _blend_replacement_frame(repl_hit, current_repl_hit, alpha=blend_alpha)
                if repl_pit is not None:
                    repl_pit = _blend_replacement_frame(repl_pit, current_repl_pit, alpha=blend_alpha)
        else:
            repl_hit, repl_pit = compute_replacement_baselines(
                ctx,
                lg,
                rostered_names,
                n_repl=lg.n_teams,
            )
        if repl_hit is None or repl_pit is None:
            raise ValueError("Replacement baselines were not initialized.")
        hit_vals, pit_vals = compute_year_player_values_vs_replacement(ctx, lg, repl_hit, repl_pit)

        if not hit_vals.empty:
            hit_year_tables.append(hit_vals[["Player", "Year", "BestSlot", "YearValue"]].copy())
        if not pit_vals.empty:
            pit_year_tables.append(pit_vals[["Player", "Year", "BestSlot", "YearValue"]].copy())

        combined = combine_two_way(hit_vals, pit_vals, two_way=lg.two_way)
        year_tables.append(combined)

    all_year = pd.concat(year_tables, ignore_index=True) if year_tables else pd.DataFrame()

    # Build sideband per-stat SGP data: player -> cat -> year -> sgp_value
    sgp_cols = [c for c in all_year.columns if c.startswith("SGP_")] if not all_year.empty else []
    stat_sgp_by_player: Dict[str, Dict[str, Dict[int, float]]] = {}
    year_value_by_player: Dict[str, Dict[int, float]] = {}
    if sgp_cols:
        for _, row in all_year.iterrows():
            player = str(row.get("Player") or "")
            year_val = int(row.get("Year", 0))
            yv = row.get("YearValue")
            year_value_by_player.setdefault(player, {})[year_val] = float(yv) if yv is not None and not pd.isna(yv) else 0.0
            player_sgps = stat_sgp_by_player.setdefault(player, {})
            for col in sgp_cols:
                cat = col[4:]  # strip "SGP_"
                v = row.get(col)
                cat_years = player_sgps.setdefault(cat, {})
                cat_years[year_val] = float(v) if v is not None and not pd.isna(v) else 0.0

    replacement_diagnostics_by_player: Dict[str, Dict[int, dict[str, object]]] = {}
    if "ReplacementDiagnostics" in all_year.columns:
        for _, row in all_year.iterrows():
            player = str(row.get("Player") or "")
            if not player:
                continue
            try:
                year_val = int(row.get("Year", 0))
            except (TypeError, ValueError):
                continue
            diagnostics = row.get("ReplacementDiagnostics")
            if isinstance(diagnostics, dict):
                replacement_diagnostics_by_player.setdefault(player, {})[year_val] = diagnostics

    # Wide format: one row per player with Value_YEAR columns
    wide = all_year.pivot_table(index="Player", columns="Year", values="YearValue", aggfunc="max").reset_index()
    wide.columns = ["Player"] + [f"Value_{int(c)}" for c in wide.columns[1:]]

    # Metadata from start year
    meta = (
        all_year[all_year["Year"] == start_year][["Player", "Team", "Pos", "Age"]]
        .drop_duplicates("Player")
    )
    out = meta.merge(wide, on="Player", how="right")

    # Attach projection metadata (based on the start-year averaged projections)
    out = out.merge(proj_meta, on="Player", how="left")
    out = out.merge(elig_df, on="Player", how="left")
    out["minor_eligible"] = _fillna_bool(out["minor_eligible"])

    # Raw dynasty value: optimal keep/drop value.
    #
    # Old behavior: sum of positive years only (i.e., negatives were always free to ignore).
    # New behavior:
    #   - If the player can be stashed in a minors slot (league has minors slots AND player is minors-eligible),
    #     we still treat negative years as 0 (you keep them in minors, so no "holding" penalty).
    #   - Otherwise, negative years *do* count as a cost if you keep the player, but you can always drop
    #     the player permanently for 0 (so truly droppable players won't go negative overall).
    raw_vals: List[float] = []
    forced_roster_vals: List[float] = []
    raw_negative_year_players: Set[str] = set()
    raw_ir_candidate_players: Set[str] = set()
    roto_explanations_by_year: List[dict[str, dict[str, object]]] = []
    player_profiles_for_explanations: List[str] = []
    current_year_volumes_for_explanations: List[dict[str, float]] = []
    risk_flags_for_explanations: List[dict[str, bool]] = []
    for _, r in out.iterrows():
        player = str(r.get("Player") or "")
        player_age = age_by_player.get(player)
        player_profile = profile_by_player.get(player, "hitter")

        vals: List[float] = []
        year_adjustment_details: List[dict[str, object]] = []
        has_negative_year = False
        has_ir_candidate_year = False
        for y in years:
            v = r.get(f"Value_{y}")
            if pd.isna(v):
                v = 0.0
            detail = _dynasty_year_adjustment_detail(
                float(v),
                player=player,
                year=int(y),
                start_year=int(start_year),
                age_start=player_age,
                profile=player_profile,
                lg=lg,
                minor_eligibility_by_year=minor_eligibility_by_year,
                minor_stash_players=minor_stash_players,
                bench_stash_players=bench_stash_players,
                ir_stash_players=ir_stash_players,
                hitter_ab_by_player_year=hitter_ab_by_player_year,
                pitcher_ip_by_player_year=pitcher_ip_by_player_year,
            )
            replacement_diagnostics = replacement_diagnostics_by_player.get(player, {}).get(int(y))
            if isinstance(replacement_diagnostics, dict):
                detail["replacement_value_diagnostics"] = dict(replacement_diagnostics)
                best_slot = str(replacement_diagnostics.get("best_slot") or "").strip()
                if best_slot:
                    detail["best_slot"] = best_slot
            adjusted = float(detail["adjusted_year_value"])
            vals.append(adjusted)
            year_adjustment_details.append(detail)
            if adjusted < 0.0:
                has_negative_year = True
                if _is_near_zero_playing_time(
                    player,
                    int(y),
                    hitter_ab_by_player_year=hitter_ab_by_player_year,
                    pitcher_ip_by_player_year=pitcher_ip_by_player_year,
                ):
                    has_ir_candidate_year = True

        keep_drop = _dynasty_keep_or_drop_values(
            vals,
            years,
            discount=float(lg.discount),
            continuation_tail_start_year=_COMMON_CONTINUATION_TAIL_START_YEAR,
            continuation_tail_decay=_COMMON_CONTINUATION_TAIL_DECAY,
        )
        raw_vals.append(float(keep_drop.raw_total))
        forced_roster_vals.append(
            _forced_roster_value(
                _apply_dynasty_aggregation_adjustments(
                    vals,
                    years,
                    continuation_tail_start_year=_COMMON_CONTINUATION_TAIL_START_YEAR,
                    continuation_tail_decay=_COMMON_CONTINUATION_TAIL_DECAY,
                ),
                years,
                lg.discount,
            )
        )
        explain_by_year: dict[str, dict[str, object]] = {}
        for idx, y in enumerate(years):
            detail = dict(year_adjustment_details[idx])
            detail["discount_factor"] = float(keep_drop.discount_factors[idx])
            detail["discounted_contribution"] = float(keep_drop.discounted_contributions[idx])
            detail["keep_drop_value"] = float(keep_drop.continuation_values[idx])
            detail["keep_drop_hold_value"] = float(keep_drop.hold_values[idx])
            detail["keep_drop_keep"] = bool(keep_drop.keep_flags[idx])
            explain_by_year[str(int(y))] = detail
        roto_explanations_by_year.append(explain_by_year)
        player_profiles_for_explanations.append(player_profile)
        current_year_volumes_for_explanations.append(
            {
                "ab": float(hitter_ab_by_player_year.get((player, int(start_year)), 0.0)),
                "ip": float(pitcher_ip_by_player_year.get((player, int(start_year)), 0.0)),
            }
        )
        risk_flags_for_explanations.append(
            {
                "playing_time_reliability_enabled": bool(getattr(lg, "enable_playing_time_reliability", False)),
                "age_risk_enabled": bool(getattr(lg, "enable_age_risk_adjustment", False)),
                "prospect_risk_enabled": bool(getattr(lg, "enable_prospect_risk_adjustment", False)),
                "bench_stash_relief_enabled": bool(getattr(lg, "enable_bench_stash_relief", False)),
                "ir_stash_relief_enabled": bool(getattr(lg, "enable_ir_stash_relief", False)),
                "replacement_blend_enabled": bool(getattr(lg, "enable_replacement_blend", False)),
            }
        )
        if has_negative_year:
            raw_negative_year_players.add(player)
        if has_ir_candidate_year:
            raw_ir_candidate_players.add(player)

    out["RawDynastyValue"] = raw_vals
    out["_ExplainRotoByYear"] = roto_explanations_by_year
    out["_ExplainPlayerProfile"] = player_profiles_for_explanations
    out["_ExplainCurrentYearVolume"] = current_year_volumes_for_explanations
    out["_ExplainRiskFlags"] = risk_flags_for_explanations

    # Centering: replacement-level roster cutoff with minors reserved first.
    out, valuation_diagnostics = _apply_dynasty_centering(
        out,
        forced_roster_values=forced_roster_vals,
        total_minor_slots=total_minor_slots,
        total_ir_slots=total_ir_slots,
        total_bench_slots=total_bench_slots,
        total_active_slots=total_active_slots,
        active_floor_names=active_floor_names,
        minor_candidate_players=minor_candidate_players,
        ir_candidate_players=raw_ir_candidate_players,
        bench_candidate_players=raw_negative_year_players,
        active_candidate_players=active_candidate_players,
        n_teams=lg.n_teams,
        years=years,
        start_year=int(start_year),
        hitter_ab_by_player_year=hitter_ab_by_player_year,
        pitcher_ip_by_player_year=pitcher_ip_by_player_year,
    )
    def _hitter_usage_diagnostics_for_year(year: int) -> dict[str, float | int | None]:
        ctx = year_contexts.get(year)
        return {} if ctx is None else ctx.hitter_usage_diagnostics

    def _pitcher_usage_diagnostics_for_year(year: int) -> dict[str, float | int | None]:
        ctx = year_contexts.get(year)
        return {} if ctx is None else ctx.pitcher_usage_diagnostics

    valuation_diagnostics["HitterUsageByYear"] = {
        str(year): {
            str(key): value
            for key, value in _hitter_usage_diagnostics_for_year(year).items()
        }
        for year in years
    }
    valuation_diagnostics["PitcherUsageByYear"] = {
        str(year): {
            str(key): value
            for key, value in _pitcher_usage_diagnostics_for_year(year).items()
        }
        for year in years
    }

    # Proportional per-stat dynasty attribution.
    # Only include SGPs from years where the player is above replacement
    # (YearValue > 0). Years with negative YearValue are effectively
    # dropped in the dynasty DP and shouldn't affect the per-stat breakdown.
    if stat_sgp_by_player:
        all_cats = sorted({cat for cats in stat_sgp_by_player.values() for cat in cats})
        stat_dynasty_cols: Dict[str, List[float]] = {cat: [] for cat in all_cats}
        for _, r in out.iterrows():
            player = str(r.get("Player") or "")
            dynasty_val = float(r.get("DynastyValue", 0.0))
            player_sgps = stat_sgp_by_player.get(player, {})
            player_year_values = year_value_by_player.get(player, {})
            discounted_sums: Dict[str, float] = {}
            for cat in all_cats:
                cat_years = player_sgps.get(cat, {})
                ds = 0.0
                for y in years:
                    yv = player_year_values.get(int(y), 0.0)
                    if yv <= 0:
                        continue
                    sgp_v = cat_years.get(int(y), 0.0)
                    offset = int(y) - int(start_year)
                    ds += sgp_v * (lg.discount ** offset)
                discounted_sums[cat] = ds
            total_discounted = sum(discounted_sums.values())
            # Guard against unstable proportions: if the positive-year SGP
            # total is tiny compared to the dynasty value, the per-stat
            # ratios become extreme and misleading.  Fall back to zeros.
            stable = abs(total_discounted) > max(1e-12, abs(dynasty_val) * 0.20)
            for cat in all_cats:
                if stable:
                    stat_dynasty_cols[cat].append(dynasty_val * discounted_sums[cat] / total_discounted)
                else:
                    stat_dynasty_cols[cat].append(0.0)
        for cat in all_cats:
            out[f"StatDynasty_{cat}"] = stat_dynasty_cols[cat]

    out = out.sort_values("DynastyValue", ascending=False).reset_index(drop=True)
    out = _attach_identity_columns_to_output(out, identity_lookup)
    out.attrs["valuation_diagnostics"] = valuation_diagnostics

    if not return_details:
        return out

    # ----------------------------
    # Detail tabs (aggregated projections + value columns)
    # ----------------------------
    hit_year = pd.concat(hit_year_tables, ignore_index=True) if hit_year_tables else pd.DataFrame(columns=["Player", "Year", "BestSlot", "YearValue"])
    pit_year = pd.concat(pit_year_tables, ignore_index=True) if pit_year_tables else pd.DataFrame(columns=["Player", "Year", "BestSlot", "YearValue"])

    player_vals = out[[PLAYER_ENTITY_KEY_COL, "DynastyValue", "RawDynastyValue", "minor_eligible"]].copy()

    bat_detail = bat.merge(hit_year, on=["Player", "Year"], how="left")
    bat_detail = bat_detail.merge(
        player_vals,
        left_on="Player",
        right_on=PLAYER_ENTITY_KEY_COL,
        how="left",
    ).drop(columns=[PLAYER_ENTITY_KEY_COL], errors="ignore")

    pit_detail = pit.merge(pit_year, on=["Player", "Year"], how="left")
    pit_detail = pit_detail.merge(
        player_vals,
        left_on="Player",
        right_on=PLAYER_ENTITY_KEY_COL,
        how="left",
    ).drop(columns=[PLAYER_ENTITY_KEY_COL], errors="ignore")

    display_by_entity = (
        dict(zip(identity_lookup[PLAYER_ENTITY_KEY_COL], identity_lookup["Player"]))
        if not identity_lookup.empty
        else {}
    )
    if display_by_entity:
        bat_detail["Player"] = bat_detail["Player"].map(display_by_entity).fillna(bat_detail["Player"])
        pit_detail["Player"] = pit_detail["Player"].map(display_by_entity).fillna(pit_detail["Player"])

    extra = ["OldestProjectionDate", "BestSlot", "YearValue", "DynastyValue", "RawDynastyValue", "minor_eligible"]
    bat_detail = reorder_detail_columns(bat_detail, bat_input_cols, add_after=bat_date_col, extra_cols=extra)
    pit_detail = reorder_detail_columns(pit_detail, pit_input_cols, add_after=pit_date_col, extra_cols=extra)

    return out, bat_detail, pit_detail
