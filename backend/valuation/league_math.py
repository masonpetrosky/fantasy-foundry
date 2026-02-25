"""League-mode valuation math helpers extracted from dynasty_roto_values."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

try:
    from backend.valuation.assignment import (
        league_assign_players_to_slots,
        league_build_team_slot_template,
        league_expand_slot_counts,
    )
    from backend.valuation.models import LEAGUE_HIT_STAT_COLS, LeagueSettings
    from backend.valuation.positions import (
        league_eligible_hit_slots,
        league_eligible_pit_slots,
        league_parse_hit_positions,
        league_parse_pit_positions,
    )
except ImportError:
    from valuation.assignment import (
        league_assign_players_to_slots,
        league_build_team_slot_template,
        league_expand_slot_counts,
    )
    from valuation.models import LEAGUE_HIT_STAT_COLS, LeagueSettings
    from valuation.positions import (
        league_eligible_hit_slots,
        league_eligible_pit_slots,
        league_parse_hit_positions,
        league_parse_pit_positions,
    )

_REVERSED_PITCH_CATS: Set[str] = {"ERA", "WHIP"}


def _coerce_non_negative_float(value: object) -> float:
    """Best-effort numeric coercion for IP/share guards."""
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return 0.0
    return float(max(number, 0.0))


def _low_volume_positive_credit_scale(
    *,
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> float:
    """Return a [0, 1] positive-credit scale based on projected innings share."""
    slot_ip = _coerce_non_negative_float(slot_ip_reference)
    player_ip = _coerce_non_negative_float(pitcher_ip)
    if slot_ip <= 0.0:
        return 1.0

    share = player_ip / slot_ip
    min_share = float(min_share_for_positive_ratio_credit)
    full_share = float(full_share_for_positive_ratio_credit)

    if full_share <= min_share:
        return 1.0 if share >= full_share else 0.0
    if share <= min_share:
        return 0.0
    if share >= full_share:
        return 1.0
    return float((share - min_share) / (full_share - min_share))


def _apply_low_volume_ratio_guard(
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> None:
    """Scale positive ERA/WHIP credit based on projected innings share."""
    scale = _low_volume_positive_credit_scale(
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )
    if scale >= 1.0:
        return

    for cat in _REVERSED_PITCH_CATS:
        if cat in pit_categories and float(delta.get(cat, 0.0)) > 0.0:
            delta[cat] = float(delta[cat]) * scale


def _mean_adjacent_rank_gap(values: np.ndarray, *, ascending: bool) -> float:
    """Mean absolute adjacent difference after rank-order sorting."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size < 2:
        return 0.0

    sorted_arr = np.sort(arr)
    if not ascending:
        sorted_arr = sorted_arr[::-1]

    diffs = np.abs(np.diff(sorted_arr))
    if diffs.size == 0:
        return 0.0
    return float(diffs.mean())


# ----------------------------
# Helpers: stat components
# ----------------------------


def league_hitter_components(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Total Bases: TB = H + 2B + 2*3B + 3*HR
    df["TB"] = df["H"] + df["2B"] + 2 * df["3B"] + 3 * df["HR"]

    # OBP numerator/denominator (standard OBP)
    df["OBP_num"] = df["H"] + df["BB"] + df["HBP"]
    df["OBP_den"] = df["AB"] + df["BB"] + df["HBP"] + df["SF"]

    return df


def league_ensure_pitch_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Allow alternative source columns if needed
    if "SVH" not in df.columns:
        if "SV" in df.columns and "HLD" in df.columns:
            df["SVH"] = df["SV"].fillna(0) + df["HLD"].fillna(0)
        else:
            df["SVH"] = 0.0

    return df


# ----------------------------
# Core math: baseline, assignment, SGP
# ----------------------------


def league_zscore(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    mu = s.mean()
    sd = s.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return (s - mu) * 0.0
    return (s - mu) / sd


def league_initial_hitter_weight(df: pd.DataFrame) -> pd.Series:
    """
    Rough first-pass weight used only to determine the starter pool and average slot baselines.
    """
    df = df.copy()
    mean_hit_rate = df["H"].sum() / df["AB"].sum() if df["AB"].sum() > 0 else 0.0
    mean_ops = df["OPS"].mean() if "OPS" in df.columns else 0.0

    df["H_surplus"] = df["H"] - mean_hit_rate * df["AB"]
    df["OPS_surplus"] = (df.get("OPS", 0.0) - mean_ops) * df["AB"]

    cols = ["R", "HR", "RBI", "SB", "H_surplus", "OPS_surplus"]
    zsum = 0.0
    for c in cols:
        zsum += league_zscore(df[c])
    return zsum


def league_initial_pitcher_weight(df: pd.DataFrame) -> pd.Series:
    """
    Rough first-pass weight used only to determine the starter pool and average slot baselines.
    """
    df = df.copy()
    ip_sum = df["IP"].sum()
    mean_era = (df["ER"].sum() * 9 / ip_sum) if ip_sum > 0 else df["ERA"].mean()
    mean_whip = ((df["H"].sum() + df["BB"].sum()) / ip_sum) if ip_sum > 0 else df["WHIP"].mean()

    # Convert ratios into "runs prevented" / "baserunners prevented" relative to mean
    df["ERA_surplus_ER"] = (mean_era - df["ERA"]) * df["IP"] / 9
    df["WHIP_surplus"] = (mean_whip - df["WHIP"]) * df["IP"]

    cols = ["W", "K", "SVH", "QA3", "ERA_surplus_ER", "WHIP_surplus"]
    zsum = 0.0
    for c in cols:
        zsum += league_zscore(df[c])
    return zsum


def league_team_avg_ops(hit_tot: pd.Series) -> Tuple[float, float]:
    ab = float(hit_tot["AB"])
    avg = float(hit_tot["H"] / ab) if ab > 0 else 0.0
    obp_den = float(hit_tot["OBP_den"])
    obp = float(hit_tot["OBP_num"] / obp_den) if obp_den > 0 else 0.0
    slg = float(hit_tot["TB"] / ab) if ab > 0 else 0.0
    ops = obp + slg
    return avg, ops


def league_replacement_pitcher_rates(all_pit_df: pd.DataFrame, assigned_pit_df: pd.DataFrame, n_rep: int = 100) -> Dict[str, float]:
    """
    Compute per-inning replacement rates from the best available non-starter pitchers.
    """
    assigned_players = set(assigned_pit_df["Player"])
    rep = all_pit_df[~all_pit_df["Player"].isin(assigned_players)].copy()
    rep = rep.sort_values("weight", ascending=False).head(n_rep)

    ip = rep["IP"].sum()
    if ip <= 0:
        return {k: 0.0 for k in ["W", "K", "SVH", "QA3", "ER", "H", "BB"]}

    return {
        "W": rep["W"].sum() / ip,
        "K": rep["K"].sum() / ip,
        "SVH": rep["SVH"].sum() / ip,
        "QA3": rep["QA3"].sum() / ip,
        "ER": rep["ER"].sum() / ip,
        "H": rep["H"].sum() / ip,
        "BB": rep["BB"].sum() / ip,
    }


def league_apply_ip_cap(t: Dict[str, float], ip_cap: float, rep_rates: Optional[Dict[str, float]]) -> Dict[str, float]:
    """
    Enforce the 1500 IP cap and fill missing innings with replacement to reach the cap.
    """
    out = dict(t)
    ip = float(out.get("IP", 0.0))

    # If over cap: scale everything down proportionally (exactly matches "stats stop accruing at 1500")
    if ip > ip_cap and ip > 0:
        f = ip_cap / ip
        for k in ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]:
            out[k] = float(out.get(k, 0.0)) * f
        ip = ip_cap

    # If under cap: fill with replacement innings
    if ip < ip_cap and rep_rates is not None:
        add = ip_cap - ip
        out["IP"] = ip_cap
        for k in ["W", "K", "SVH", "QA3", "ER", "H", "BB"]:
            out[k] = float(out.get(k, 0.0)) + add * float(rep_rates.get(k, 0.0))
        ip = ip_cap

    # Ratios on capped totals
    out["ERA"] = 9.0 * out["ER"] / ip if ip > 0 else np.nan
    out["WHIP"] = (out["H"] + out["BB"]) / ip if ip > 0 else np.nan
    return out


def league_simulate_sgp_hit(assigned_hit_df: pd.DataFrame, lg: LeagueSettings, rng: np.random.Generator) -> Dict[str, float]:
    """
    Monte Carlo estimate of the average adjacent gap between roto ranks ("stat per roto point").
    """
    # Group players by the slot they were assigned to in the league-wide optimal assignment
    groups = {slot: assigned_hit_df[assigned_hit_df["AssignedSlot"] == slot] for slot in assigned_hit_df["AssignedSlot"].unique()}
    per_team = lg.hitter_slots

    cats = ["R", "HR", "RBI", "SB", "AVG", "OPS"]
    diffs = {c: [] for c in cats}

    for _ in range(lg.sims_for_sgp):
        # Team totals for each simulation
        team_tot = [{col: 0.0 for col in LEAGUE_HIT_STAT_COLS} for _ in range(lg.n_teams)]

        for slot, df_slot in groups.items():
            cnt = per_team[slot]
            idx = rng.permutation(len(df_slot))
            arr = df_slot.iloc[idx][LEAGUE_HIT_STAT_COLS].to_numpy()
            arr = arr.reshape(lg.n_teams, cnt, len(LEAGUE_HIT_STAT_COLS))

            # Vector sums per team, then add
            for t in range(lg.n_teams):
                sums = arr[t].sum(axis=0)
                for k, col in enumerate(LEAGUE_HIT_STAT_COLS):
                    team_tot[t][col] += float(sums[k])

        # Compute category totals
        vals = {c: [] for c in cats}
        for t in range(lg.n_teams):
            tot = team_tot[t]
            avg, ops = league_team_avg_ops(pd.Series(tot))
            vals["R"].append(tot["R"])
            vals["HR"].append(tot["HR"])
            vals["RBI"].append(tot["RBI"])
            vals["SB"].append(tot["SB"])
            vals["AVG"].append(avg)
            vals["OPS"].append(ops)

        for c in cats:
            arr = np.array(vals[c], dtype=float)
            diffs[c].append(_mean_adjacent_rank_gap(arr, ascending=False))

    return {c: (float(np.mean(diffs[c])) if diffs[c] else 0.0) for c in cats}


def league_simulate_sgp_pit(assigned_pit_df: pd.DataFrame, lg: LeagueSettings, rep_rates: Dict[str, float], rng: np.random.Generator) -> Dict[str, float]:
    """
    Monte Carlo estimate of the average adjacent gap between roto ranks ("stat per roto point") for pitching.
    """
    groups = {slot: assigned_pit_df[assigned_pit_df["AssignedSlot"] == slot] for slot in assigned_pit_df["AssignedSlot"].unique()}
    per_team = lg.pitcher_slots

    cats = ["W", "K", "SVH", "QA3", "ERA", "WHIP"]
    diffs = {c: [] for c in cats}

    base_cols = ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]

    for _ in range(lg.sims_for_sgp):
        team_raw = [{col: 0.0 for col in base_cols} for _ in range(lg.n_teams)]

        for slot, df_slot in groups.items():
            cnt = per_team[slot]
            idx = rng.permutation(len(df_slot))
            arr = df_slot.iloc[idx][base_cols].to_numpy()
            arr = arr.reshape(lg.n_teams, cnt, len(base_cols))

            for t in range(lg.n_teams):
                sums = arr[t].sum(axis=0)
                for k, col in enumerate(base_cols):
                    team_raw[t][col] += float(sums[k])

        vals = {c: [] for c in cats}
        for t in range(lg.n_teams):
            capped = league_apply_ip_cap(team_raw[t], ip_cap=lg.ip_max, rep_rates=rep_rates)
            vals["W"].append(capped["W"])
            vals["K"].append(capped["K"])
            vals["SVH"].append(capped["SVH"])
            vals["QA3"].append(capped["QA3"])
            vals["ERA"].append(capped["ERA"])
            vals["WHIP"].append(capped["WHIP"])

        for c in cats:
            arr = np.array(vals[c], dtype=float)
            diffs[c].append(_mean_adjacent_rank_gap(arr, ascending=(c in {"ERA", "WHIP"})))

    return {c: (float(np.mean(diffs[c])) if diffs[c] else 0.0) for c in cats}


# ----------------------------
# Year context + player year-values
# ----------------------------


def league_sum_slots(baseline_df: pd.DataFrame, slot_list: List[str]) -> pd.Series:
    return baseline_df.loc[slot_list].sum()


def league_compute_year_context(year: int, bat_df: pd.DataFrame, pit_df: pd.DataFrame, lg: LeagueSettings, rng_seed: int) -> dict:
    bat_y = league_hitter_components(bat_df[bat_df["Year"] == year].copy())
    pit_y = league_ensure_pitch_cols(pit_df[pit_df["Year"] == year].copy())

    # Use only playing-time > 0 rows to build the "starter pool" baselines
    bat_play = bat_y[bat_y["AB"] > 0].copy()
    pit_play = pit_y[pit_y["IP"] > 0].copy()

    if bat_play.empty:
        raise ValueError(
            f"Year {year}: no hitters with AB > 0 after filtering. Check Year values and AB projections."
        )
    if pit_play.empty:
        raise ValueError(
            f"Year {year}: no pitchers with IP > 0 after filtering. Check Year values and IP projections."
        )

    bat_play["weight"] = league_initial_hitter_weight(bat_play)
    pit_play["weight"] = league_initial_pitcher_weight(pit_play)

    league_hit_slots = league_expand_slot_counts(lg.hitter_slots, lg.n_teams)
    league_pit_slots = league_expand_slot_counts(lg.pitcher_slots, lg.n_teams)

    assigned_hit = league_assign_players_to_slots(bat_play, league_hit_slots, league_eligible_hit_slots, weight_col="weight")
    assigned_pit = league_assign_players_to_slots(pit_play, league_pit_slots, league_eligible_pit_slots, weight_col="weight")

    baseline_hit = assigned_hit.groupby("AssignedSlot")[LEAGUE_HIT_STAT_COLS].mean()
    baseline_pit = assigned_pit.groupby("AssignedSlot")[["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]].mean()

    team_hit_slots = league_build_team_slot_template(lg.hitter_slots)
    team_pit_slots = league_build_team_slot_template(lg.pitcher_slots)

    base_hit_tot = league_sum_slots(baseline_hit, team_hit_slots)
    base_avg, base_ops = league_team_avg_ops(base_hit_tot)

    base_pit_raw = league_sum_slots(baseline_pit, team_pit_slots)
    base_pit_raw_dict = {k: float(base_pit_raw[k]) for k in ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]}

    rep_rates = league_replacement_pitcher_rates(pit_play.assign(weight=league_initial_pitcher_weight(pit_play)), assigned_pit, n_rep=lg.replacement_pitchers_n)

    rng_hit = np.random.default_rng(rng_seed)
    rng_pit = np.random.default_rng(rng_seed + 1)
    sgp_hit = league_simulate_sgp_hit(assigned_hit, lg, rng_hit)
    sgp_pit = league_simulate_sgp_pit(assigned_pit, lg, rep_rates, rng_pit)

    return {
        "year": year,
        "bat_y": bat_y,
        "pit_y": pit_y,
        "baseline_hit": baseline_hit,
        "baseline_pit": baseline_pit,
        "base_hit_tot": base_hit_tot,
        "base_avg": base_avg,
        "base_ops": base_ops,
        "base_pit_raw": base_pit_raw_dict,
        "rep_rates": rep_rates,
        "sgp_hit": sgp_hit,
        "sgp_pit": sgp_pit,
    }


def league_compute_year_player_values(ctx: dict, lg: LeagueSettings) -> Tuple[pd.DataFrame, pd.DataFrame]:
    year = int(ctx["year"])
    bat_y = ctx["bat_y"]
    pit_y = ctx["pit_y"]

    baseline_hit = ctx["baseline_hit"]
    baseline_pit = ctx["baseline_pit"]
    base_hit_tot = ctx["base_hit_tot"]
    base_avg = float(ctx["base_avg"])
    base_ops = float(ctx["base_ops"])

    base_pit_raw = dict(ctx["base_pit_raw"])
    rep_rates = ctx["rep_rates"]

    sgp_hit = ctx["sgp_hit"]
    sgp_pit = ctx["sgp_pit"]

    base_pit_capped = league_apply_ip_cap(base_pit_raw, ip_cap=lg.ip_max, rep_rates=rep_rates)

    # --- Hitters: best-slot marginal SGP vs average starter in that slot ---
    hit_rows = []
    for row in bat_y.to_dict(orient="records"):
        pos_set = league_parse_hit_positions(row.get("Pos", ""))
        slots = league_eligible_hit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_hit.index:
                continue

            b = baseline_hit.loc[slot]
            new_tot = base_hit_tot.copy()
            for col in LEAGUE_HIT_STAT_COLS:
                new_tot[col] = new_tot[col] - b[col] + float(row.get(col, 0.0))

            new_avg, new_ops = league_team_avg_ops(new_tot)

            delta_R = float(new_tot["R"] - base_hit_tot["R"])
            delta_HR = float(new_tot["HR"] - base_hit_tot["HR"])
            delta_RBI = float(new_tot["RBI"] - base_hit_tot["RBI"])
            delta_SB = float(new_tot["SB"] - base_hit_tot["SB"])
            delta_AVG = float(new_avg - base_avg)
            delta_OPS = float(new_ops - base_ops)

            val = (
                (delta_R / sgp_hit["R"] if sgp_hit["R"] else 0.0)
                + (delta_HR / sgp_hit["HR"] if sgp_hit["HR"] else 0.0)
                + (delta_RBI / sgp_hit["RBI"] if sgp_hit["RBI"] else 0.0)
                + (delta_SB / sgp_hit["SB"] if sgp_hit["SB"] else 0.0)
                + (delta_AVG / sgp_hit["AVG"] if sgp_hit["AVG"] else 0.0)
                + (delta_OPS / sgp_hit["OPS"] if sgp_hit["OPS"] else 0.0)
            )

            if val > best_val:
                best_val = val
                best_slot = slot

        hit_rows.append(
            {
                "Player": row.get("Player"),
                "Year": year,
                "Type": "H",
                "MLBTeam": row.get("MLBTeam", np.nan),
                "Age": row.get("Age", np.nan),
                "Pos": row.get("Pos", np.nan),
                "BestSlot": best_slot,
                "YearValue": float(best_val),
            }
        )

    hit_vals = pd.DataFrame(hit_rows)

    # --- Pitchers: best-slot marginal SGP vs average starter in that slot, with IP cap ---
    pit_rows = []
    for row in pit_y.to_dict(orient="records"):
        pos_set = league_parse_pit_positions(row.get("Pos", ""))
        slots = league_eligible_pit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_pit.index:
                continue

            b = baseline_pit.loc[slot]
            new_raw = dict(base_pit_raw)
            for col in ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]:
                new_raw[col] = float(new_raw[col]) - float(b[col]) + float(row.get(col, 0.0))

            new_capped = league_apply_ip_cap(new_raw, ip_cap=lg.ip_max, rep_rates=rep_rates)

            delta_W = float(new_capped["W"] - base_pit_capped["W"])
            delta_K = float(new_capped["K"] - base_pit_capped["K"])
            delta_SVH = float(new_capped["SVH"] - base_pit_capped["SVH"])
            delta_QA3 = float(new_capped["QA3"] - base_pit_capped["QA3"])

            # Lower is better for ERA/WHIP => improvement = base - new
            delta_ERA = float(base_pit_capped["ERA"] - new_capped["ERA"])
            delta_WHIP = float(base_pit_capped["WHIP"] - new_capped["WHIP"])
            delta = {
                "W": delta_W,
                "K": delta_K,
                "SVH": delta_SVH,
                "QA3": delta_QA3,
                "ERA": delta_ERA,
                "WHIP": delta_WHIP,
            }
            _apply_low_volume_ratio_guard(
                delta,
                pit_categories=["W", "K", "SVH", "QA3", "ERA", "WHIP"],
                pitcher_ip=_coerce_non_negative_float(row.get("IP", 0.0)),
                slot_ip_reference=_coerce_non_negative_float(b.get("IP", 0.0)),
            )

            val = (
                (delta["W"] / sgp_pit["W"] if sgp_pit["W"] else 0.0)
                + (delta["K"] / sgp_pit["K"] if sgp_pit["K"] else 0.0)
                + (delta["SVH"] / sgp_pit["SVH"] if sgp_pit["SVH"] else 0.0)
                + (delta["QA3"] / sgp_pit["QA3"] if sgp_pit["QA3"] else 0.0)
                + (delta["ERA"] / sgp_pit["ERA"] if sgp_pit["ERA"] else 0.0)
                + (delta["WHIP"] / sgp_pit["WHIP"] if sgp_pit["WHIP"] else 0.0)
            )

            if val > best_val:
                best_val = val
                best_slot = slot

        pit_rows.append(
            {
                "Player": row.get("Player"),
                "Year": year,
                "Type": "P",
                "MLBTeam": row.get("MLBTeam", np.nan),
                "Age": row.get("Age", np.nan),
                "Pos": row.get("Pos", np.nan),
                "BestSlot": best_slot,
                "YearValue": float(best_val),
            }
        )

    pit_vals = pd.DataFrame(pit_rows)
    return hit_vals, pit_vals


def league_compute_replacement_baselines(
    ctx: dict,
    lg: LeagueSettings,
    rostered_players: Set[str],
    n_repl: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build per-slot replacement-level baselines from the *unrostered* player pool.

    We approximate "replacement at slot" as the mean stat line of the top `n_repl`
    free agents eligible at that slot (default: n_teams).
    """
    n_repl = int(n_repl or lg.n_teams)

    bat_y = ctx["bat_y"].copy()
    pit_y = ctx["pit_y"].copy()

    # Clean numeric NaNs
    for c in LEAGUE_HIT_STAT_COLS:
        if c in bat_y.columns:
            bat_y[c] = bat_y[c].fillna(0.0)
    for c in ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]:
        if c in pit_y.columns:
            pit_y[c] = pit_y[c].fillna(0.0)

    if "ERA" in pit_y.columns:
        pit_y["ERA"] = pit_y["ERA"].fillna(pit_y["ERA"].mean())
    if "WHIP" in pit_y.columns:
        pit_y["WHIP"] = pit_y["WHIP"].fillna(pit_y["WHIP"].mean())

    # Weights for ordering free agents (same rough weights used for starter-pool selection)
    bat_y["weight"] = league_initial_hitter_weight(bat_y)
    pit_y["weight"] = league_initial_pitcher_weight(pit_y)

    # Candidate free-agent pools (must have playing time to be meaningful replacements)
    fa_hit = bat_y[(~bat_y["Player"].isin(rostered_players)) & (bat_y["AB"] > 0)].copy()
    fa_pit = pit_y[(~pit_y["Player"].isin(rostered_players)) & (pit_y["IP"] > 0)].copy()

    fa_hit["elig"] = fa_hit["Pos"].apply(lambda p: league_eligible_hit_slots(league_parse_hit_positions(p)))
    fa_pit["elig"] = fa_pit["Pos"].apply(lambda p: league_eligible_pit_slots(league_parse_pit_positions(p)))

    # Hit replacement baselines per slot
    repl_hit_rows: List[dict] = []
    baseline_hit_avg = ctx["baseline_hit"]
    for slot in baseline_hit_avg.index:
        cand = (
            fa_hit[fa_hit["elig"].apply(lambda s: slot in s)]
            .sort_values("weight", ascending=False)
            .head(n_repl)
        )
        if len(cand) == 0:
            repl = baseline_hit_avg.loc[slot]
        else:
            repl = cand[LEAGUE_HIT_STAT_COLS].mean()

        row = {c: float(repl.get(c, 0.0)) for c in LEAGUE_HIT_STAT_COLS}
        row["AssignedSlot"] = slot
        repl_hit_rows.append(row)

    repl_hit = pd.DataFrame(repl_hit_rows).set_index("AssignedSlot")

    # Pitch replacement baselines per slot
    repl_pit_rows: List[dict] = []
    baseline_pit_avg = ctx["baseline_pit"]
    pit_cols = ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]
    for slot in baseline_pit_avg.index:
        cand = (
            fa_pit[fa_pit["elig"].apply(lambda s: slot in s)]
            .sort_values("weight", ascending=False)
            .head(n_repl)
        )
        if len(cand) == 0:
            repl = baseline_pit_avg.loc[slot]
        else:
            repl = cand[pit_cols].mean()

        row = {c: float(repl.get(c, 0.0)) for c in pit_cols}
        row["AssignedSlot"] = slot
        repl_pit_rows.append(row)

    repl_pit = pd.DataFrame(repl_pit_rows).set_index("AssignedSlot")

    return repl_hit, repl_pit


def league_compute_year_player_values_vs_replacement(
    ctx: dict,
    lg: LeagueSettings,
    repl_hit: pd.DataFrame,
    repl_pit: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute per-year player values as marginal roto points above *replacement level*
    (instead of above the average starter).

    Implementation detail:
    - We keep the *team context* as an average-starter roster for the other slots.
    - For each candidate slot, we compare "player in that slot" vs
      "replacement player in that slot".
    """
    year = int(ctx["year"])
    bat_y = ctx["bat_y"]
    pit_y = ctx["pit_y"]

    baseline_hit_avg = ctx["baseline_hit"]
    baseline_pit_avg = ctx["baseline_pit"]

    base_hit_tot_avg = ctx["base_hit_tot"]

    base_pit_raw_avg = dict(ctx["base_pit_raw"])
    rep_rates = ctx["rep_rates"]

    sgp_hit = ctx["sgp_hit"]
    sgp_pit = ctx["sgp_pit"]

    # --- Hitters ---
    hit_rows = []
    for row in bat_y.to_dict(orient="records"):
        pos_set = league_parse_hit_positions(row.get("Pos", ""))
        slots = league_eligible_hit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_hit_avg.index or slot not in repl_hit.index:
                continue

            b_avg = baseline_hit_avg.loc[slot]
            b_rep = repl_hit.loc[slot]

            # Base team but with replacement in this slot
            base_tot = base_hit_tot_avg.copy()
            for col in LEAGUE_HIT_STAT_COLS:
                base_tot[col] = base_tot[col] - b_avg[col] + b_rep[col]

            # New team with this player in this slot
            new_tot = base_hit_tot_avg.copy()
            for col in LEAGUE_HIT_STAT_COLS:
                new_tot[col] = new_tot[col] - b_avg[col] + float(row.get(col, 0.0))

            base_avg, base_ops = league_team_avg_ops(base_tot)
            new_avg, new_ops = league_team_avg_ops(new_tot)

            delta_R = float(new_tot["R"] - base_tot["R"])
            delta_HR = float(new_tot["HR"] - base_tot["HR"])
            delta_RBI = float(new_tot["RBI"] - base_tot["RBI"])
            delta_SB = float(new_tot["SB"] - base_tot["SB"])
            delta_AVG = float(new_avg - base_avg)
            delta_OPS = float(new_ops - base_ops)

            val = (
                (delta_R / sgp_hit["R"] if sgp_hit["R"] else 0.0)
                + (delta_HR / sgp_hit["HR"] if sgp_hit["HR"] else 0.0)
                + (delta_RBI / sgp_hit["RBI"] if sgp_hit["RBI"] else 0.0)
                + (delta_SB / sgp_hit["SB"] if sgp_hit["SB"] else 0.0)
                + (delta_AVG / sgp_hit["AVG"] if sgp_hit["AVG"] else 0.0)
                + (delta_OPS / sgp_hit["OPS"] if sgp_hit["OPS"] else 0.0)
            )

            if val > best_val:
                best_val = val
                best_slot = slot

        hit_rows.append(
            {
                "Player": row.get("Player"),
                "Year": year,
                "Type": "H",
                "MLBTeam": row.get("MLBTeam", np.nan),
                "Age": row.get("Age", np.nan),
                "Pos": row.get("Pos", np.nan),
                "BestSlot": best_slot,
                "YearValue": float(best_val),
            }
        )

    hit_vals = pd.DataFrame(hit_rows)

    # --- Pitchers ---
    pit_rows = []
    pit_cols = ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]

    for row in pit_y.to_dict(orient="records"):
        pos_set = league_parse_pit_positions(row.get("Pos", ""))
        slots = league_eligible_pit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_pit_avg.index or slot not in repl_pit.index:
                continue

            b_avg = baseline_pit_avg.loc[slot]
            b_rep = repl_pit.loc[slot]

            # Base team but with replacement in this slot
            base_raw = dict(base_pit_raw_avg)
            for col in pit_cols:
                base_raw[col] = float(base_raw.get(col, 0.0)) - float(b_avg.get(col, 0.0)) + float(b_rep.get(col, 0.0))

            # New team with this player in this slot
            new_raw = dict(base_pit_raw_avg)
            for col in pit_cols:
                new_raw[col] = float(new_raw.get(col, 0.0)) - float(b_avg.get(col, 0.0)) + float(row.get(col, 0.0))

            base_capped = league_apply_ip_cap(base_raw, ip_cap=lg.ip_max, rep_rates=rep_rates)
            new_capped = league_apply_ip_cap(new_raw, ip_cap=lg.ip_max, rep_rates=rep_rates)

            delta_W = float(new_capped["W"] - base_capped["W"])
            delta_K = float(new_capped["K"] - base_capped["K"])
            delta_SVH = float(new_capped["SVH"] - base_capped["SVH"])
            delta_QA3 = float(new_capped["QA3"] - base_capped["QA3"])

            # Lower is better for ERA/WHIP
            delta_ERA = float(base_capped["ERA"] - new_capped["ERA"])
            delta_WHIP = float(base_capped["WHIP"] - new_capped["WHIP"])
            delta = {
                "W": delta_W,
                "K": delta_K,
                "SVH": delta_SVH,
                "QA3": delta_QA3,
                "ERA": delta_ERA,
                "WHIP": delta_WHIP,
            }
            _apply_low_volume_ratio_guard(
                delta,
                pit_categories=["W", "K", "SVH", "QA3", "ERA", "WHIP"],
                pitcher_ip=_coerce_non_negative_float(row.get("IP", 0.0)),
                slot_ip_reference=_coerce_non_negative_float(b_avg.get("IP", 0.0)),
            )

            val = (
                (delta["W"] / sgp_pit["W"] if sgp_pit["W"] else 0.0)
                + (delta["K"] / sgp_pit["K"] if sgp_pit["K"] else 0.0)
                + (delta["SVH"] / sgp_pit["SVH"] if sgp_pit["SVH"] else 0.0)
                + (delta["QA3"] / sgp_pit["QA3"] if sgp_pit["QA3"] else 0.0)
                + (delta["ERA"] / sgp_pit["ERA"] if sgp_pit["ERA"] else 0.0)
                + (delta["WHIP"] / sgp_pit["WHIP"] if sgp_pit["WHIP"] else 0.0)
            )

            if val > best_val:
                best_val = val
                best_slot = slot

        pit_rows.append(
            {
                "Player": row.get("Player"),
                "Year": year,
                "Type": "P",
                "MLBTeam": row.get("MLBTeam", np.nan),
                "Age": row.get("Age", np.nan),
                "Pos": row.get("Pos", np.nan),
                "BestSlot": best_slot,
                "YearValue": float(best_val),
            }
        )

    pit_vals = pd.DataFrame(pit_rows)
    return hit_vals, pit_vals


def league_combine_hitter_pitcher_year(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame:
    merged = pd.merge(
        hit_vals[["Player", "Year", "YearValue", "BestSlot", "Pos", "MLBTeam", "Age"]],
        pit_vals[["Player", "Year", "YearValue", "BestSlot", "Pos", "MLBTeam", "Age"]],
        on=["Player", "Year"],
        how="outer",
        suffixes=("_hit", "_pit"),
    )

    combined_val = []
    combined_slot = []

    for _, r in merged.iterrows():
        hv = r.get("YearValue_hit")
        pv = r.get("YearValue_pit")

        if pd.isna(hv) and pd.isna(pv):
            combined_val.append(np.nan)
            combined_slot.append(None)
            continue

        if pd.isna(hv):
            combined_val.append(float(pv))
            combined_slot.append(r.get("BestSlot_pit"))
            continue

        if pd.isna(pv):
            combined_val.append(float(hv))
            combined_slot.append(r.get("BestSlot_hit"))
            continue

        hv = float(hv)
        pv = float(pv)

        if two_way == "sum":
            combined_val.append(hv + pv)
            combined_slot.append(f"{r.get('BestSlot_hit')}+{r.get('BestSlot_pit')}")
        else:
            if hv >= pv:
                combined_val.append(hv)
                combined_slot.append(r.get("BestSlot_hit"))
            else:
                combined_val.append(pv)
                combined_slot.append(r.get("BestSlot_pit"))

    merged["YearValue"] = combined_val
    merged["BestSlot"] = combined_slot

    merged["Pos"] = merged["Pos_hit"].combine_first(merged["Pos_pit"])
    merged["MLBTeam"] = merged["MLBTeam_hit"].combine_first(merged["MLBTeam_pit"])
    merged["Age"] = merged["Age_hit"].combine_first(merged["Age_pit"])

    return merged[["Player", "Year", "YearValue", "BestSlot", "Pos", "MLBTeam", "Age"]]


__all__ = [
    "league_hitter_components",
    "league_ensure_pitch_cols",
    "league_zscore",
    "league_initial_hitter_weight",
    "league_initial_pitcher_weight",
    "league_team_avg_ops",
    "league_replacement_pitcher_rates",
    "league_apply_ip_cap",
    "league_simulate_sgp_hit",
    "league_simulate_sgp_pit",
    "league_sum_slots",
    "league_compute_year_context",
    "league_compute_year_player_values",
    "league_compute_replacement_baselines",
    "league_compute_year_player_values_vs_replacement",
    "league_combine_hitter_pitcher_year",
]
