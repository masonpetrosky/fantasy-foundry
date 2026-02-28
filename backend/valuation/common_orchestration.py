"""Common-mode valuation orchestration extracted from legacy dynasty module."""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Set

import pandas as pd

try:
    from backend.dynasty_roto_values import (
        COMMON_COLUMN_ALIASES,
        DERIVED_HIT_RATE_COLS,
        DERIVED_PIT_RATE_COLS,
        HIT_COMPONENT_COLS,
        PLAYER_ENTITY_KEY_COL,
        CommonDynastyRotoSettings,
        _add_player_identity_keys,
        _apply_negative_value_stash_rules,
        _attach_identity_columns_to_output,
        _build_bench_stash_penalty_map,
        _build_player_identity_lookup,
        _fillna_bool,
        _find_projection_date_col,
        _non_vacant_player_names,
        _players_with_playing_time,
        _resolve_minor_eligibility_by_year,
        _select_mlb_roster_with_active_floor,
        average_recent_projections,
        combine_two_way,
        compute_replacement_baselines,
        compute_year_context,
        compute_year_player_values,
        compute_year_player_values_vs_replacement,
        dynasty_keep_or_drop_value,
        normalize_input_schema,
        numeric_stat_cols_for_recent_avg,
        projection_meta_for_start_year,
        recompute_common_rates_hit,
        recompute_common_rates_pit,
        reorder_detail_columns,
        require_cols,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from dynasty_roto_values import (  # type: ignore
        COMMON_COLUMN_ALIASES,
        DERIVED_HIT_RATE_COLS,
        DERIVED_PIT_RATE_COLS,
        HIT_COMPONENT_COLS,
        PLAYER_ENTITY_KEY_COL,
        CommonDynastyRotoSettings,
        _add_player_identity_keys,
        _apply_negative_value_stash_rules,
        _attach_identity_columns_to_output,
        _build_bench_stash_penalty_map,
        _build_player_identity_lookup,
        _fillna_bool,
        _find_projection_date_col,
        _non_vacant_player_names,
        _players_with_playing_time,
        _resolve_minor_eligibility_by_year,
        _select_mlb_roster_with_active_floor,
        average_recent_projections,
        combine_two_way,
        compute_replacement_baselines,
        compute_year_context,
        compute_year_player_values,
        compute_year_player_values_vs_replacement,
        dynasty_keep_or_drop_value,
        normalize_input_schema,
        numeric_stat_cols_for_recent_avg,
        projection_meta_for_start_year,
        recompute_common_rates_hit,
        recompute_common_rates_pit,
        reorder_detail_columns,
        require_cols,
    )


_PITCH_POSITION_TOKENS = {"P", "SP", "RP"}
_POSITION_TOKEN_RE = re.compile(r"[,\s/;+|]+")


def _position_profile(pos_value: object) -> str:
    text = str(pos_value or "").strip().upper()
    if not text:
        return "hitter"
    tokens = {token for token in _POSITION_TOKEN_RE.split(text) if token}
    has_pitch = any(token in _PITCH_POSITION_TOKENS for token in tokens)
    has_hit = any(token not in _PITCH_POSITION_TOKENS for token in tokens)
    if has_pitch and not has_hit:
        return "pitcher"
    if has_pitch and has_hit:
        return "two_way"
    # Catcher-only gets steeper aging curve.
    if tokens == {"C"}:
        return "catcher"
    return "hitter"


def _piecewise_age_factor(age: float, *, profile: str) -> float:
    if profile == "pitcher":
        if age <= 28.0:
            return 1.0
        if age <= 34.0:
            return 1.0 + (0.84 - 1.0) * ((age - 28.0) / 6.0)
        if age <= 38.0:
            return 0.84 + (0.70 - 0.84) * ((age - 34.0) / 4.0)
        return 0.70

    # Catchers age faster: peak at 27, steeper decline.
    if profile == "catcher":
        if age <= 27.0:
            return 1.0
        if age <= 33.0:
            return 1.0 + (0.82 - 1.0) * ((age - 27.0) / 6.0)
        if age <= 37.0:
            return 0.82 + (0.65 - 0.82) * ((age - 33.0) / 4.0)
        return 0.65

    # Hitter defaults and two-way fallback.
    if age <= 29.0:
        return 1.0
    if age <= 35.0:
        return 1.0 + (0.88 - 1.0) * ((age - 29.0) / 6.0)
    if age <= 39.0:
        return 0.88 + (0.75 - 0.88) * ((age - 35.0) / 4.0)
    return 0.75


def _year_risk_multiplier(
    *,
    age_start: float | None,
    year: int,
    start_year: int,
    profile: str,
    enabled: bool,
) -> float:
    if not enabled:
        return 1.0
    if age_start is None or not math.isfinite(age_start):
        return 1.0
    year_offset = max(int(year) - int(start_year), 0)
    age = float(age_start) + float(year_offset)
    factor = _piecewise_age_factor(age, profile=profile)
    if age >= 31.0 and year_offset > 0:
        factor *= float(0.98 ** year_offset)
    return float(max(min(factor, 1.0), 0.0))


def _blend_replacement_frame(
    frozen_frame: pd.DataFrame,
    current_frame: pd.DataFrame,
    *,
    alpha: float,
) -> pd.DataFrame:
    frozen = frozen_frame.astype(float)
    current = current_frame.astype(float)
    idx = frozen.index.union(current.index)
    cols = frozen.columns.union(current.columns)
    frozen_aligned = frozen.reindex(index=idx, columns=cols).fillna(0.0)
    current_aligned = current.reindex(index=idx, columns=cols).fillna(0.0)
    return (float(alpha) * frozen_aligned) + ((1.0 - float(alpha)) * current_aligned)


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
    if lg.minor_slots and lg.minor_slots > 0:
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
    else:
        elig_year_df = pd.DataFrame(columns=["Player", "Year", "minor_eligible"])
        elig_df = pd.DataFrame(columns=["Player", "minor_eligible"])

    active_per_team = sum(lg.hitter_slots.values()) + sum(lg.pitcher_slots.values())
    total_minor_slots = lg.n_teams * lg.minor_slots
    total_mlb_slots = lg.n_teams * (active_per_team + lg.bench_slots + lg.ir_slots)

    # PASS 1: average-starter values to estimate who is rostered in a deep league.
    year_contexts: Dict[int, dict] = {}
    year_tables_avg: List[pd.DataFrame] = []

    for y in years:
        if verbose:
            print(f"Year {y}: baseline + SGP + player values (avg-starter pass) ...")
        ctx = compute_year_context(y, bat, pit, lg, rng_seed=seed + y)
        year_contexts[y] = ctx
        hit_vals, pit_vals = compute_year_player_values(ctx, lg)
        combined = combine_two_way(hit_vals, pit_vals, two_way=lg.two_way)
        year_tables_avg.append(combined)

    start_ctx = year_contexts.get(start_year, {})
    active_floor_names = (
        _non_vacant_player_names(start_ctx.get("assigned_hit"))
        | _non_vacant_player_names(start_ctx.get("assigned_pit"))
    )

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
    bench_stash_players = _players_with_playing_time(bat, pit, years)

    def _stash_row(row: pd.Series, bench_penalty_by_player: Dict[str, float]) -> float:
        player = str(row["Player"])
        can_bench_stash = bool(lg.bench_slots and lg.bench_slots > 0 and player in bench_stash_players)
        bench_penalty = float(bench_penalty_by_player.get(player, 1.0))
        player_age = age_by_player.get(player)
        player_profile = profile_by_player.get(player, "hitter")
        vals: List[float] = []
        for y in years:
            v = row.get(y)
            if pd.isna(v):
                v = 0.0
            v = float(v)
            v *= _year_risk_multiplier(
                age_start=player_age,
                year=int(y),
                start_year=int(start_year),
                profile=player_profile,
                enabled=bool(getattr(lg, "enable_age_risk_adjustment", False)),
            )
            v = _apply_negative_value_stash_rules(
                v,
                can_minor_stash=bool(
                    lg.minor_slots
                    and lg.minor_slots > 0
                    and bool(minor_eligibility_by_year.get((player, int(y)), False))
                ),
                can_bench_stash=can_bench_stash,
                bench_negative_penalty=bench_penalty,
            )
            vals.append(v)
        return dynasty_keep_or_drop_value(vals, years, lg.discount)

    provisional_bench_penalty = {player: 0.0 for player in bench_stash_players}
    wide_avg["StashScore"] = wide_avg.apply(lambda row: _stash_row(row, provisional_bench_penalty), axis=1)
    provisional_stash_sorted = wide_avg[["Player", "StashScore"]].sort_values("StashScore", ascending=False).reset_index(drop=True)
    bench_penalty_by_player = _build_bench_stash_penalty_map(
        provisional_stash_sorted,
        bench_stash_players=bench_stash_players,
        n_teams=lg.n_teams,
        bench_slots=lg.bench_slots,
    )
    wide_avg["StashScore"] = wide_avg.apply(lambda row: _stash_row(row, bench_penalty_by_player), axis=1)
    stash = wide_avg[["Player", "StashScore"]].copy()
    stash = stash.merge(elig_df, on="Player", how="left")
    stash["minor_eligible"] = _fillna_bool(stash["minor_eligible"])

    stash_sorted = stash.sort_values("StashScore", ascending=False).reset_index(drop=True)
    minors_pool = stash_sorted[stash_sorted["minor_eligible"]]
    minors_sel = minors_pool.head(total_minor_slots)
    minor_names = set(minors_sel["Player"])

    remaining = stash_sorted[~stash_sorted["Player"].isin(minor_names)]
    extra_minor_needed = max(total_minor_slots - len(minors_sel), 0)
    extra_minors = remaining.head(extra_minor_needed)
    extra_minor_names = set(extra_minors["Player"])

    mlb_sel = _select_mlb_roster_with_active_floor(
        stash_sorted,
        excluded_players=minor_names | extra_minor_names,
        total_mlb_slots=total_mlb_slots,
        active_floor_names=active_floor_names,
    )
    rostered_names: Set[str] = set(mlb_sel["Player"]) | minor_names | extra_minor_names

    # PASS 2: replacement-level per-year values from the unrostered pool.
    # By default, replacement baselines are frozen from start_year.
    year_tables: List[pd.DataFrame] = []
    hit_year_tables: List[pd.DataFrame] = []
    pit_year_tables: List[pd.DataFrame] = []

    frozen_repl_hit: Optional[pd.DataFrame] = None
    frozen_repl_pit: Optional[pd.DataFrame] = None
    blend_enabled = bool(lg.freeze_replacement_baselines and getattr(lg, "enable_replacement_blend", False))
    blend_alpha = float(min(max(getattr(lg, "replacement_blend_alpha", 0.70), 0.0), 1.0))
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
    for _, r in out.iterrows():
        player = str(r.get("Player") or "")
        can_bench_stash = bool(lg.bench_slots and lg.bench_slots > 0 and player in bench_stash_players)
        bench_penalty = float(bench_penalty_by_player.get(player, 1.0))
        player_age = age_by_player.get(player)
        player_profile = profile_by_player.get(player, "hitter")

        vals: List[float] = []
        for y in years:
            v = r.get(f"Value_{y}")
            if pd.isna(v):
                v = 0.0
            v = float(v)
            v *= _year_risk_multiplier(
                age_start=player_age,
                year=int(y),
                start_year=int(start_year),
                profile=player_profile,
                enabled=bool(getattr(lg, "enable_age_risk_adjustment", False)),
            )
            v = _apply_negative_value_stash_rules(
                v,
                can_minor_stash=bool(
                    lg.minor_slots
                    and lg.minor_slots > 0
                    and bool(minor_eligibility_by_year.get((player, int(y)), False))
                ),
                can_bench_stash=can_bench_stash,
                bench_negative_penalty=bench_penalty,
            )
            vals.append(v)

        raw_vals.append(dynasty_keep_or_drop_value(vals, years, lg.discount))

    out["RawDynastyValue"] = raw_vals

    # Centering: replacement-level roster cutoff with minors reserved first.
    out_sorted = out.sort_values("RawDynastyValue", ascending=False).reset_index(drop=True)
    minors_pool = out_sorted[out_sorted["minor_eligible"]]
    minors_sel = minors_pool.head(total_minor_slots)
    minor_names = set(minors_sel["Player"])

    remaining = out_sorted[~out_sorted["Player"].isin(minor_names)]
    extra_minor_needed = max(total_minor_slots - len(minors_sel), 0)
    extra_minors = remaining.head(extra_minor_needed)
    extra_minor_names = set(extra_minors["Player"])

    remaining = remaining[~remaining["Player"].isin(extra_minor_names)]
    mlb_sel = remaining.head(total_mlb_slots)

    rostered = pd.concat([minors_sel, extra_minors, mlb_sel], ignore_index=True)
    baseline_value = float(rostered["RawDynastyValue"].iloc[-1]) if len(rostered) else 0.0

    out["DynastyValue"] = out["RawDynastyValue"] - baseline_value
    out["CenteringBaselineValue"] = baseline_value
    out["CenteringBaselineMean"] = baseline_value

    out = out.sort_values("DynastyValue", ascending=False).reset_index(drop=True)
    out = _attach_identity_columns_to_output(out, identity_lookup)

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

    extra = ["ProjectionsUsed", "OldestProjectionDate", "BestSlot", "YearValue", "DynastyValue", "RawDynastyValue", "minor_eligible"]
    bat_detail = reorder_detail_columns(bat_detail, bat_input_cols, add_after=bat_date_col, extra_cols=extra)
    pit_detail = reorder_detail_columns(pit_detail, pit_input_cols, add_after=pit_date_col, extra_cols=extra)

    return out, bat_detail, pit_detail
