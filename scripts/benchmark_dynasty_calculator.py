"""Benchmark common-mode dynasty calculator runtime for known heavy configs."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


CASES = {
    "exact": {
        "teams": 12,
        "start_year": 2026,
        "horizon_years": 20,
        "sims_for_sgp": 300,
        "discount": 0.94,
        "hitter_slots": {"C": 2, "1B": 1, "2B": 1, "3B": 1, "SS": 1, "CI": 1, "MI": 1, "OF": 5, "UT": 2},
        "pitcher_slots": {"P": 3, "SP": 3, "RP": 3},
        "bench_slots": 14,
        "minor_slots": 20,
        "ir_slots": 8,
        "ip_min": 1000.0,
        "ip_max": 1500.0,
        "two_way": "sum",
        "hitter_categories": ("R", "RBI", "HR", "SB", "AVG", "OPS"),
        "pitcher_categories": ("W", "K", "ERA", "WHIP", "QA3", "SVH"),
    },
    "h20_s100": {
        "teams": 12,
        "start_year": 2026,
        "horizon_years": 20,
        "sims_for_sgp": 100,
        "discount": 0.94,
        "hitter_slots": {"C": 2, "1B": 1, "2B": 1, "3B": 1, "SS": 1, "CI": 1, "MI": 1, "OF": 5, "UT": 2},
        "pitcher_slots": {"P": 3, "SP": 3, "RP": 3},
        "bench_slots": 14,
        "minor_slots": 20,
        "ir_slots": 8,
        "ip_min": 1000.0,
        "ip_max": 1500.0,
        "two_way": "sum",
        "hitter_categories": ("R", "RBI", "HR", "SB", "AVG", "OPS"),
        "pitcher_categories": ("W", "K", "ERA", "WHIP", "QA3", "SVH"),
    },
    "h10_s300": {
        "teams": 12,
        "start_year": 2026,
        "horizon_years": 10,
        "sims_for_sgp": 300,
        "discount": 0.94,
        "hitter_slots": {"C": 2, "1B": 1, "2B": 1, "3B": 1, "SS": 1, "CI": 1, "MI": 1, "OF": 5, "UT": 2},
        "pitcher_slots": {"P": 3, "SP": 3, "RP": 3},
        "bench_slots": 14,
        "minor_slots": 20,
        "ir_slots": 8,
        "ip_min": 1000.0,
        "ip_max": 1500.0,
        "two_way": "sum",
        "hitter_categories": ("R", "RBI", "HR", "SB", "AVG", "OPS"),
        "pitcher_categories": ("W", "K", "ERA", "WHIP", "QA3", "SVH"),
    },
}


def _build_settings(case: dict) -> object:
    from backend.valuation.models import CommonDynastyRotoSettings

    return CommonDynastyRotoSettings(
        n_teams=int(case["teams"]),
        hitter_slots=dict(case["hitter_slots"]),
        pitcher_slots=dict(case["pitcher_slots"]),
        bench_slots=int(case["bench_slots"]),
        minor_slots=int(case["minor_slots"]),
        ir_slots=int(case["ir_slots"]),
        ip_min=float(case["ip_min"]),
        ip_max=float(case["ip_max"]) if case["ip_max"] is not None else None,
        sims_for_sgp=int(case["sims_for_sgp"]),
        discount=float(case["discount"]),
        horizon_years=int(case["horizon_years"]),
        freeze_replacement_baselines=True,
        two_way=str(case["two_way"]),
        hitter_categories=tuple(case["hitter_categories"]),
        pitcher_categories=tuple(case["pitcher_categories"]),
    )


def _run_case(name: str, *, input_path: Path, repeat: int) -> dict[str, object]:
    from backend.valuation.common_orchestration import calculate_common_dynasty_values

    case = CASES[name]
    durations: list[float] = []
    rows = 0
    for _ in range(repeat):
        start = time.perf_counter()
        out = calculate_common_dynasty_values(
            str(input_path),
            _build_settings(case),
            start_year=int(case["start_year"]),
            verbose=False,
            return_details=False,
            seed=0,
        )
        durations.append(time.perf_counter() - start)
        rows = len(out)

    return {
        "case": name,
        "rows": rows,
        "repeat": repeat,
        "best_seconds": round(min(durations), 3),
        "avg_seconds": round(sum(durations) / len(durations), 3),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        action="append",
        choices=sorted(CASES.keys()),
        help="Benchmark only the selected case(s). Defaults to all predefined cases.",
    )
    parser.add_argument("--repeat", type=int, default=1, help="Run each case N times and report best/average runtime.")
    parser.add_argument(
        "--input",
        default=str(Path("data") / "Dynasty Baseball Projections.xlsx"),
        help="Path to the dynasty projection workbook.",
    )
    args = parser.parse_args()

    selected_cases = args.case or list(CASES.keys())
    input_path = Path(args.input)

    for case_name in selected_cases:
        print(json.dumps(_run_case(case_name, input_path=input_path, repeat=max(args.repeat, 1)), sort_keys=True))


if __name__ == "__main__":
    main()
