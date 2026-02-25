"""League-mode valuation orchestration extracted from legacy dynasty module."""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Set

import pandas as pd

try:
    from backend.dynasty_roto_values import (
        DERIVED_HIT_RATE_COLS,
        DERIVED_PIT_RATE_COLS,
        HAVE_SCIPY,
        LEAGUE_COLUMN_ALIASES,
        PLAYER_ENTITY_KEY_COL,
        LeagueSettings,
        _add_player_identity_keys,
        _apply_negative_value_stash_rules,
        _attach_identity_columns_to_output,
        _build_bench_stash_penalty_map,
        _build_player_identity_lookup,
        _fillna_bool,
        _find_projection_date_col,
        _players_with_playing_time,
        _resolve_minor_eligibility_by_year,
        average_recent_projections,
        dynasty_keep_or_drop_value,
        league_combine_hitter_pitcher_year,
        league_compute_replacement_baselines,
        league_compute_year_context,
        league_compute_year_player_values,
        league_compute_year_player_values_vs_replacement,
        league_ensure_pitch_cols,
        normalize_input_schema,
        numeric_stat_cols_for_recent_avg,
        projection_meta_for_start_year,
        recompute_league_rates_hit,
        recompute_league_rates_pit,
        reorder_detail_columns,
        require_cols,
    )
except ImportError:  # pragma: no cover - direct script execution fallback
    from dynasty_roto_values import (  # type: ignore
        DERIVED_HIT_RATE_COLS,
        DERIVED_PIT_RATE_COLS,
        HAVE_SCIPY,
        LEAGUE_COLUMN_ALIASES,
        PLAYER_ENTITY_KEY_COL,
        LeagueSettings,
        _add_player_identity_keys,
        _apply_negative_value_stash_rules,
        _attach_identity_columns_to_output,
        _build_bench_stash_penalty_map,
        _build_player_identity_lookup,
        _fillna_bool,
        _find_projection_date_col,
        _players_with_playing_time,
        _resolve_minor_eligibility_by_year,
        average_recent_projections,
        dynasty_keep_or_drop_value,
        league_combine_hitter_pitcher_year,
        league_compute_replacement_baselines,
        league_compute_year_context,
        league_compute_year_player_values,
        league_compute_year_player_values_vs_replacement,
        league_ensure_pitch_cols,
        normalize_input_schema,
        numeric_stat_cols_for_recent_avg,
        projection_meta_for_start_year,
        recompute_league_rates_hit,
        recompute_league_rates_pit,
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


def calculate_league_dynasty_values(
    excel_path: str,
    lg: LeagueSettings,
    start_year: Optional[int] = None,
    years: Optional[List[int]] = None,
    verbose: bool = True,
    return_details: bool = False,
    seed: int = 0,
    recent_projections: int = 3,
):
    """League-mode dynasty values (your custom categories/rules).

    If return_details=True, also returns (bat_detail, pit_detail) tables that:
      - collapse duplicate (Player, Year) rows by averaging the most-recent 3 projections
      - keep the original input columns in roughly the same order
      - attach YearValue/BestSlot (per side) and DynastyValue to each Player/Year row
    """
    if not HAVE_SCIPY:
        raise ImportError("scipy is required for league mode (linear_sum_assignment not available).")

    bat_raw = normalize_input_schema(pd.read_excel(excel_path, sheet_name="Bat"), LEAGUE_COLUMN_ALIASES)
    pit_raw = normalize_input_schema(pd.read_excel(excel_path, sheet_name="Pitch"), LEAGUE_COLUMN_ALIASES)

    bat_input_cols = list(bat_raw.columns)
    pit_input_cols = list(pit_raw.columns)
    bat_date_col = _find_projection_date_col(bat_raw)
    pit_date_col = _find_projection_date_col(pit_raw)

    bat_raw, pit_raw = _add_player_identity_keys(bat_raw, pit_raw)
    identity_lookup = _build_player_identity_lookup(bat_raw, pit_raw)
    bat_raw["Player"] = bat_raw[PLAYER_ENTITY_KEY_COL].astype("string").fillna("").str.strip()
    pit_raw["Player"] = pit_raw[PLAYER_ENTITY_KEY_COL].astype("string").fillna("").str.strip()

    # Average *all numeric stat columns* (except derived rates and Age) so the
    # aggregated detail tabs (and category stats like SVH/QA3) reflect the true averaged projections.
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

    bat_df = average_recent_projections(bat_raw, bat_stat_cols, max_entries=recent_projections)
    pit_df = average_recent_projections(pit_raw, pit_stat_cols, max_entries=recent_projections)

    bat_df = recompute_league_rates_hit(bat_df)
    pit_df = recompute_league_rates_pit(pit_df)
    pit_df = league_ensure_pitch_cols(pit_df)

    require_cols(
        bat_df,
        ["Player", "Year", "MLBTeam", "Age", "Pos", "AB", "H", "R", "HR", "RBI", "SB", "BB", "HBP", "SF", "2B", "3B"],
        "Bat",
    )
    require_cols(
        pit_df,
        ["Player", "Year", "MLBTeam", "Age", "Pos", "IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"],
        "Pitch",
    )

    if years is None:
        if start_year is None:
            start_year = int(min(bat_df["Year"].min(), pit_df["Year"].min()))
        max_year = int(max(bat_df["Year"].max(), pit_df["Year"].max()))
        years = [y for y in range(start_year, start_year + lg.horizon_years) if y <= max_year]
    else:
        if start_year is None:
            start_year = int(min(years))
        max_year = int(max(bat_df["Year"].max(), pit_df["Year"].max()))
        years = [y for y in years if y <= max_year]

    if not years:
        raise ValueError("No valuation years available after applying start year / horizon to projection file years.")

    # Projection metadata: how many projections were averaged (<=3) and the oldest date used
    proj_meta = projection_meta_for_start_year(bat_df, pit_df, start_year)
    start_rows = pd.concat(
        [
            bat_df[bat_df["Year"] == int(start_year)][["Player", "Age", "Pos"]],
            pit_df[pit_df["Year"] == int(start_year)][["Player", "Age", "Pos"]],
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

    years_set = {int(y) for y in years}
    elig_year_df = _resolve_minor_eligibility_by_year(
        bat_df,
        pit_df,
        years=years,
        hitter_usage_max=lg.minor_hitters_career_ab_max,
        pitcher_usage_max=lg.minor_pitchers_career_ip_max,
        hitter_age_max=lg.infer_minor_age_max_hit,
        pitcher_age_max=lg.infer_minor_age_max_pit,
    )
    start_minor = elig_year_df[elig_year_df["Year"] == int(start_year)][["Player", "minor_eligible"]].copy()
    if start_minor.empty:
        elig_df = pd.DataFrame(columns=["Player", "minor_eligible"])
    else:
        elig_df = start_minor.groupby("Player", as_index=False)["minor_eligible"].max()

    # Roster depth (league-wide)
    active_per_team = sum(lg.hitter_slots.values()) + sum(lg.pitcher_slots.values())  # should be 23
    total_minor_slots = lg.n_teams * lg.minor_slots
    total_mlb_slots = lg.n_teams * (active_per_team + lg.bench_slots + lg.ir_slots)

    # ------------------------------------------------------------------
    # PASS 1: compute average-starter year values (for a "stash score" that
    #         approximates who is rostered in a deep dynasty league).
    # ------------------------------------------------------------------
    year_contexts: Dict[int, dict] = {}
    year_tables_avg: List[pd.DataFrame] = []

    for y in years:
        if verbose:
            print(f"Year {y}: building baseline + SGP + player values (avg-starter pass) ...")
        ctx = league_compute_year_context(y, bat_df, pit_df, lg, rng_seed=seed + y)
        year_contexts[y] = ctx

        hit_vals, pit_vals = league_compute_year_player_values(ctx, lg)  # vs average starter
        combined = league_combine_hitter_pitcher_year(hit_vals, pit_vals, two_way=lg.two_way)
        year_tables_avg.append(combined)

    all_year_avg = pd.concat(year_tables_avg, ignore_index=True)

    # Stash score: optimal keep/drop value on the avg-starter YearValue stream.
    # Minor-eligible players can be stashed in minors (negative years treated as 0)
    # when the league has minors slots.
    minor_eligibility_by_year = (
        {
            (str(row.Player), int(row.Year)): bool(row.minor_eligible)
            for row in elig_year_df.itertuples(index=False)
            if int(row.Year) in years_set
        }
        if not elig_year_df.empty
        else {}
    )
    bench_stash_players = _players_with_playing_time(bat_df, pit_df, years)

    wide_avg = all_year_avg.pivot_table(index="Player", columns="Year", values="YearValue", aggfunc="max").reset_index()

    # Ensure every horizon year exists as a column (missing years => 0 value)
    for y in years:
        if y not in wide_avg.columns:
            wide_avg[y] = 0.0

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

    # Determine rostered set (minors reserved first, then the rest)
    stash_sorted = stash.sort_values("StashScore", ascending=False).reset_index(drop=True)

    minors_pool = stash_sorted[stash_sorted["minor_eligible"]]
    minors_sel = minors_pool.head(total_minor_slots)
    minor_names = set(minors_sel["Player"])

    remaining = stash_sorted[~stash_sorted["Player"].isin(minor_names)]
    extra_minor_needed = max(total_minor_slots - len(minors_sel), 0)
    extra_minors = remaining.head(extra_minor_needed)
    extra_minor_names = set(extra_minors["Player"])

    remaining = remaining[~remaining["Player"].isin(extra_minor_names)]
    mlb_sel = remaining.head(total_mlb_slots)

    rostered_names: Set[str] = set(mlb_sel["Player"]) | minor_names | extra_minor_names

    # ------------------------------------------------------------------
    # PASS 2: compute per-year values vs *replacement* (from unrostered pool).
    # By default, replacement baselines are frozen from start_year.
    # ------------------------------------------------------------------
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
        frozen_repl_hit, frozen_repl_pit = league_compute_replacement_baselines(
            start_ctx_for_replacement,
            lg,
            rostered_names,
            n_repl=lg.n_teams,
        )

    for y in years:
        if verbose:
            print(f"Year {y}: computing replacement baselines + player values (replacement pass) ...")
        ctx = year_contexts[y]
        if lg.freeze_replacement_baselines:
            # Reuse a fixed replacement baseline from the start year.
            repl_hit = frozen_repl_hit
            repl_pit = frozen_repl_pit
            if blend_enabled:
                current_repl_hit, current_repl_pit = league_compute_replacement_baselines(
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
            repl_hit, repl_pit = league_compute_replacement_baselines(
                ctx,
                lg,
                rostered_names,
                n_repl=lg.n_teams,
            )
        if repl_hit is None or repl_pit is None:
            raise ValueError("Replacement baselines were not initialized.")
        hit_vals, pit_vals = league_compute_year_player_values_vs_replacement(ctx, lg, repl_hit, repl_pit)

        # Store side-specific year values for the detail tabs
        if not hit_vals.empty:
            hit_year_tables.append(hit_vals[["Player", "Year", "BestSlot", "YearValue"]].copy())
        if not pit_vals.empty:
            pit_year_tables.append(pit_vals[["Player", "Year", "BestSlot", "YearValue"]].copy())

        combined = league_combine_hitter_pitcher_year(hit_vals, pit_vals, two_way=lg.two_way)
        year_tables.append(combined)

    all_year_vals = pd.concat(year_tables, ignore_index=True)

    # Wide table (one row per player) with Value_YEAR columns
    wide = all_year_vals.pivot_table(index="Player", columns="Year", values="YearValue", aggfunc="max").reset_index()
    wide.columns = ["Player"] + [f"Value_{int(c)}" for c in wide.columns[1:]]

    # Metadata from start year
    meta = (
        all_year_vals[all_year_vals["Year"] == start_year][["Player", "MLBTeam", "Pos", "Age"]]
        .drop_duplicates("Player")
    )

    out = meta.merge(wide, on="Player", how="right")

    # Attach projection metadata (based on the start-year averaged projections)
    out = out.merge(proj_meta, on="Player", how="left")

    # Raw dynasty value: optimal keep/drop value.
    #
    # - If the player can be stashed in a minors slot (league has minors slots AND player is minors-eligible),
    #   negative years are treated as 0 (no holding penalty while stashed).
    # - Otherwise, negative years *do* count as a cost if you keep the player, but you can drop the player
    #   permanently for 0 at any year boundary.
    raw_vals: List[float] = []
    for _, r in out.iterrows():
        player = str(r.get("Player") or "")
        can_bench_stash = bool(lg.bench_slots and lg.bench_slots > 0 and player in bench_stash_players)
        bench_penalty = float(bench_penalty_by_player.get(player, 1.0))
        player_age = age_by_player.get(player)
        player_profile = profile_by_player.get(player, "hitter")

        vals: List[float] = []
        for y in years:
            col = f"Value_{y}"
            v = r.get(col)
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

    # Attach minor eligibility (for centering + output)
    out = out.merge(elig_df, on="Player", how="left")
    out["minor_eligible"] = _fillna_bool(out["minor_eligible"])

    # Center so replacement-level rostered cutoff ~= 0 (active + bench + minors + IR)
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

    bat_detail = bat_df.merge(hit_year, on=["Player", "Year"], how="left")
    bat_detail = bat_detail.merge(
        player_vals,
        left_on="Player",
        right_on=PLAYER_ENTITY_KEY_COL,
        how="left",
    ).drop(columns=[PLAYER_ENTITY_KEY_COL], errors="ignore")

    pit_detail = pit_df.merge(pit_year, on=["Player", "Year"], how="left")
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
