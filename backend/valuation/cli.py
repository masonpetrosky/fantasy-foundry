"""CLI entrypoint for dynasty valuation workflows."""

from __future__ import annotations

import argparse

import pandas as pd

try:
    from backend.valuation import xlsx_formatting as _xlsx_fmt
    from backend.valuation.cli_args import (
        discount_arg,
        non_negative_float_arg,
        non_negative_int_arg,
        optional_non_negative_float_arg,
        positive_int_arg,
        validate_ip_bounds,
    )
    from backend.valuation.common_orchestration import calculate_common_dynasty_values
    from backend.valuation.league_orchestration import calculate_league_dynasty_values
    from backend.valuation.models import CommonDynastyRotoSettings, LeagueSettings
except ImportError:  # pragma: no cover - direct script execution fallback
    from valuation import xlsx_formatting as _xlsx_fmt
    from valuation.cli_args import (
        discount_arg,
        non_negative_float_arg,
        non_negative_int_arg,
        optional_non_negative_float_arg,
        positive_int_arg,
        validate_ip_bounds,
    )
    from valuation.common_orchestration import calculate_common_dynasty_values
    from valuation.league_orchestration import calculate_league_dynasty_values
    from valuation.models import CommonDynastyRotoSettings, LeagueSettings


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)

    common = sub.add_parser("common", help="Run the common 5x5 dynasty roto valuation.")
    common.add_argument(
        "--input",
        default="Dynasty Baseball Projections.xlsx",
        help="Excel file with Bat and Pitch sheets (default: Dynasty Baseball Projections.xlsx).",
    )
    common.add_argument("--start-year", type=int, default=None, help="First valuation year (default: min Year in file).")
    common.add_argument("--teams", type=positive_int_arg, default=12)
    common.add_argument("--sims", type=positive_int_arg, default=200, help="Monte Carlo sims for SGP denominators.")
    common.add_argument("--horizon", type=positive_int_arg, default=10, help="Dynasty horizon years.")
    common.add_argument("--discount", type=discount_arg, default=0.94, help="Annual discount factor in (0, 1].")
    common.add_argument("--seed", type=int, default=0, help="Global random seed offset for deterministic simulations.")
    common.add_argument("--bench", type=non_negative_int_arg, default=6)
    common.add_argument("--minors", type=non_negative_int_arg, default=0)
    common.add_argument("--ir", type=non_negative_int_arg, default=0)
    common.add_argument("--ip-min", type=non_negative_float_arg, default=0.0, help="Optional IP minimum to qualify for ERA/WHIP (default 0).")
    common.add_argument(
        "--ip-max",
        type=optional_non_negative_float_arg,
        default=None,
        help="Optional IP maximum/cap (default none). Accepts numeric values or 'none'.",
    )
    common.add_argument(
        "--dynamic-replacement-baselines",
        action="store_true",
        help="Recompute replacement baselines for each valuation year (legacy behavior).",
    )
    common.add_argument("--out-prefix", default="common_player_values", help="Output prefix for CSV/XLSX.")

    league = sub.add_parser("league", help="Run the custom league valuation from the original my-league script.")
    league.add_argument(
        "--input",
        default="Dynasty Baseball Projections.xlsx",
        help="Excel file with Bat and Pitch sheets (default: Dynasty Baseball Projections.xlsx).",
    )
    league.add_argument("--start-year", type=int, default=None, help="First valuation year (default: min Year in file).")
    league.add_argument("--sims", type=positive_int_arg, default=200, help="Monte Carlo sims for SGP denominators.")
    league.add_argument("--horizon", type=positive_int_arg, default=10, help="Dynasty horizon years.")
    league.add_argument("--discount", type=discount_arg, default=0.94, help="Annual discount factor in (0, 1].")
    league.add_argument("--seed", type=int, default=0, help="Global random seed offset for deterministic simulations.")
    league.add_argument(
        "--dynamic-replacement-baselines",
        action="store_true",
        help="Recompute replacement baselines for each valuation year (legacy behavior).",
    )
    league.add_argument("--out-prefix", default="player_values", help="Output prefix for CSV/XLSX.")

    return p


def main() -> None:
    p = _build_parser()
    args = p.parse_args()

    bat_detail = None
    pit_detail = None

    if args.mode == "common":
        validate_ip_bounds(args.ip_min, args.ip_max)
        lg = CommonDynastyRotoSettings(
            n_teams=args.teams,
            sims_for_sgp=args.sims,
            horizon_years=args.horizon,
            discount=args.discount,
            bench_slots=args.bench,
            minor_slots=args.minors,
            ir_slots=args.ir,
            ip_min=args.ip_min,
            ip_max=args.ip_max,
            freeze_replacement_baselines=not args.dynamic_replacement_baselines,
        )

        out, bat_detail, pit_detail = calculate_common_dynasty_values(
            args.input,
            lg,
            start_year=args.start_year,
            verbose=True,
            return_details=True,
            seed=args.seed,
        )

        year_cols = [c for c in out.columns if c.startswith("Value_")]
        df = out[
            [
                "Player",
                "OldestProjectionDate",
                "Team",
                "Pos",
                "Age",
                "DynastyValue",
                "RawDynastyValue",
                "minor_eligible",
            ]
            + year_cols
            + ["CenteringBaselineMean"]
        ]

    else:
        lg = LeagueSettings(
            sims_for_sgp=args.sims,
            horizon_years=args.horizon,
            discount=args.discount,
            two_way="max",
            freeze_replacement_baselines=not args.dynamic_replacement_baselines,
        )
        validate_ip_bounds(lg.ip_min, lg.ip_max)

        out, bat_detail, pit_detail = calculate_league_dynasty_values(
            args.input,
            lg,
            start_year=args.start_year,
            verbose=True,
            return_details=True,
            seed=args.seed,
        )

        year_cols = [c for c in out.columns if c.startswith("Value_")]
        df = out[
            [
                "Player",
                "OldestProjectionDate",
                "MLBTeam",
                "Pos",
                "Age",
                "DynastyValue",
                "RawDynastyValue",
                "minor_eligible",
            ]
            + year_cols
        ]

    csv_path = f"{args.out_prefix}.csv"
    xlsx_path = f"{args.out_prefix}.xlsx"

    df.to_csv(csv_path, index=False)

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="PlayerValues", index=False)
        if bat_detail is not None:
            bat_detail.to_excel(writer, sheet_name="Bat_Aggregated", index=False)
        if pit_detail is not None:
            pit_detail.to_excel(writer, sheet_name="Pitch_Aggregated", index=False)

        try:
            if "PlayerValues" in writer.sheets:
                _xlsx_fmt._xlsx_format_player_values(writer.sheets["PlayerValues"], df, table_name="PlayerValuesTbl")

            if bat_detail is not None and "Bat_Aggregated" in writer.sheets:
                _xlsx_fmt._xlsx_format_detail_sheet(
                    writer.sheets["Bat_Aggregated"],
                    bat_detail,
                    table_name="BatAggregatedTbl",
                    is_pitch=False,
                )

            if pit_detail is not None and "Pitch_Aggregated" in writer.sheets:
                _xlsx_fmt._xlsx_format_detail_sheet(
                    writer.sheets["Pitch_Aggregated"],
                    pit_detail,
                    table_name="PitchAggregatedTbl",
                    is_pitch=True,
                )
        except Exception as e:
            print(f"WARNING: Failed to apply Excel formatting: {e}")

    print("\nTop 25 by DynastyValue:")
    print(df.head(25).to_string(index=False))
    print(f"\nWrote: {csv_path}")
    print(f"Wrote: {xlsx_path}")


if __name__ == "__main__":
    main()
