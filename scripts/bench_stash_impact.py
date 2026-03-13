"""Compare dynasty valuations with and without bench stash benefit.

Runs the full valuation pipeline twice:
1. Default settings (bench_slots=6)
2. bench_slots=0 (no bench stash)

Outputs a comparison of rank changes for specific players.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.valuation.models import CommonDynastyRotoSettings
from backend.valuation.common_orchestration import calculate_common_dynasty_values

EXCEL_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "Dynasty Baseball Projections.xlsx")
SEED = 42
START_YEAR = 2026


def run_valuation(bench_slots: int) -> "pd.DataFrame":
    lg = CommonDynastyRotoSettings(
        n_teams=12,
        bench_slots=bench_slots,
        minor_slots=0,
        discount=0.94,
        horizon_years=10,
        sims_for_sgp=200,
        freeze_replacement_baselines=True,
    )
    result = calculate_common_dynasty_values(
        excel_path=EXCEL_PATH,
        lg=lg,
        start_year=START_YEAR,
        verbose=False,
        return_details=False,
        seed=SEED,
    )
    # result may be a tuple or a DataFrame depending on return_details
    if isinstance(result, tuple):
        result = result[0]
    return result


def main():
    import pandas as pd

    print("=" * 70)
    print("BENCH STASH IMPACT ANALYSIS")
    print("=" * 70)

    print("\nRunning valuation WITH bench stash (bench_slots=6)...")
    df_with = run_valuation(bench_slots=6)

    print("Running valuation WITHOUT bench stash (bench_slots=0)...")
    df_without = run_valuation(bench_slots=0)

    # Standardize column names
    val_col = "DynastyValue"
    if val_col not in df_with.columns:
        # Try RawDynastyValue
        val_col = "RawDynastyValue"

    # Add ranks
    df_with = df_with.sort_values(val_col, ascending=False).reset_index(drop=True)
    df_with["Rank_With"] = range(1, len(df_with) + 1)

    df_without = df_without.sort_values(val_col, ascending=False).reset_index(drop=True)
    df_without["Rank_Without"] = range(1, len(df_without) + 1)

    # Merge
    cols_with = ["Player", val_col, "Rank_With"]
    if "Pos" in df_with.columns:
        cols_with.insert(1, "Pos")
    if "Age" in df_with.columns:
        cols_with.insert(2, "Age")
    if "Team" in df_with.columns:
        cols_with.insert(1, "Team")

    cols_without = ["Player", val_col, "Rank_Without"]

    merged = df_with[cols_with].merge(
        df_without[cols_without],
        on="Player",
        how="outer",
        suffixes=("_with", "_without"),
    )

    val_with = f"{val_col}_with"
    val_without = f"{val_col}_without"

    merged["Value_Delta"] = merged[val_with] - merged[val_without]
    merged["Rank_Delta"] = merged["Rank_Without"] - merged["Rank_With"]  # positive = dropped ranks without stash

    merged = merged.sort_values("Rank_With").reset_index(drop=True)

    # ---- Report ----
    print(f"\nTotal players: {len(merged)}")
    print(f"Value column used: {val_col}")

    # Top 50 overall
    print("\n" + "=" * 70)
    print("TOP 50 PLAYERS — RANK COMPARISON")
    print("=" * 70)
    top50 = merged.head(50)
    for _, row in top50.iterrows():
        name = row["Player"]
        pos = row.get("Pos", "?")
        age = row.get("Age", "?")
        team = row.get("Team", "?")
        r_with = int(row["Rank_With"])
        r_without = int(row["Rank_Without"]) if not pd.isna(row["Rank_Without"]) else "N/A"
        v_with = row[val_with]
        v_without = row[val_without] if not pd.isna(row[val_without]) else 0
        delta = row["Rank_Delta"]
        v_delta = row["Value_Delta"]

        arrow = ""
        if not pd.isna(delta):
            if delta > 0:
                arrow = f"  (dropped {int(delta)} spots without stash)"
            elif delta < 0:
                arrow = f"  (rose {int(-delta)} spots without stash)"

        print(
            f"  #{r_with:>3} → #{r_without:>3}  {name:<25} {str(pos):<6} Age {str(age):<4} "
            f"Val: {v_with:>7.2f} → {v_without:>7.2f} (Δ {v_delta:>+7.2f}){arrow}"
        )

    # Biggest losers among top-200 players (dropped most ranks)
    top200 = merged[merged["Rank_With"] <= 200].copy()
    print("\n" + "=" * 70)
    print("BIGGEST LOSERS (Top 200) — Players who drop the most without bench stash")
    print("=" * 70)
    losers = top200.dropna(subset=["Rank_Delta"]).nlargest(25, "Rank_Delta")
    for _, row in losers.iterrows():
        name = row["Player"]
        pos = row.get("Pos", "?")
        age = row.get("Age", "?")
        r_with = int(row["Rank_With"])
        r_without = int(row["Rank_Without"])
        v_with = row[val_with]
        v_without = row[val_without]
        v_delta = row["Value_Delta"]
        print(
            f"  #{r_with:>3} → #{r_without:>3}  {name:<25} {str(pos):<6} Age {str(age):<4} "
            f"Val: {v_with:>7.2f} → {v_without:>7.2f} (Δ {v_delta:>+7.2f})  DROPPED {int(row['Rank_Delta'])} spots"
        )

    # Biggest winners among top-200 (rose most ranks)
    print("\n" + "=" * 70)
    print("BIGGEST WINNERS (Top 200) — Players who rise the most without bench stash")
    print("=" * 70)
    winners = top200.dropna(subset=["Rank_Delta"]).nsmallest(25, "Rank_Delta")
    for _, row in winners.iterrows():
        name = row["Player"]
        pos = row.get("Pos", "?")
        age = row.get("Age", "?")
        r_with = int(row["Rank_With"])
        r_without = int(row["Rank_Without"])
        v_with = row[val_with]
        v_without = row[val_without]
        v_delta = row["Value_Delta"]
        print(
            f"  #{r_with:>3} → #{r_without:>3}  {name:<25} {str(pos):<6} Age {str(age):<4} "
            f"Val: {v_with:>7.2f} → {v_without:>7.2f} (Δ {v_delta:>+7.2f})  ROSE {int(-row['Rank_Delta'])} spots"
        )

    # Biggest value deltas among top-200 (most value lost)
    print("\n" + "=" * 70)
    print("BIGGEST VALUE LOSSES (Top 200) — Players who lose the most dynasty value")
    print("=" * 70)
    val_losers = top200.dropna(subset=["Value_Delta"]).nlargest(20, "Value_Delta")
    for _, row in val_losers.iterrows():
        name = row["Player"]
        pos = row.get("Pos", "?")
        age = row.get("Age", "?")
        r_with = int(row["Rank_With"])
        r_without = int(row["Rank_Without"])
        v_with = row[val_with]
        v_without = row[val_without]
        v_delta = row["Value_Delta"]
        pct = (v_delta / v_without * 100) if v_without != 0 else 0
        print(
            f"  #{r_with:>3} → #{r_without:>3}  {name:<25} {str(pos):<6} Age {str(age):<4} "
            f"Val: {v_with:>7.2f} → {v_without:>7.2f} (Δ {v_delta:>+7.2f}, {pct:+.1f}%)"
        )

    # Value distribution stats
    print("\n" + "=" * 70)
    print("VALUE IMPACT SUMMARY")
    print("=" * 70)
    deltas = merged["Value_Delta"].dropna()
    print(f"  Players with value DECREASE: {(deltas < -0.01).sum()}")
    print(f"  Players with value INCREASE: {(deltas > 0.01).sum()}")
    print(f"  Players unchanged (±0.01):   {((deltas >= -0.01) & (deltas <= 0.01)).sum()}")
    print(f"  Mean value delta:            {deltas.mean():+.3f}")
    print(f"  Median value delta:          {deltas.median():+.3f}")
    print(f"  Max value loss:              {deltas.min():+.3f}")
    print(f"  Max value gain:              {deltas.max():+.3f}")

    rank_deltas = merged["Rank_Delta"].dropna()
    print(f"\n  Mean rank change:            {rank_deltas.mean():+.1f}")
    print(f"  Max rank drop:               {rank_deltas.max():+.0f}")
    print(f"  Max rank rise:               {rank_deltas.min():+.0f}")


if __name__ == "__main__":
    main()
