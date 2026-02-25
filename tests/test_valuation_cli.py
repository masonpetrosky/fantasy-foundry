import sys
from pathlib import Path

import pandas as pd

from backend.valuation import cli


def _common_out_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Player": "Prospect One",
                "ProjectionsUsed": 1,
                "OldestProjectionDate": "2026-01-01",
                "Team": "ATL",
                "Pos": "OF",
                "Age": 22,
                "DynastyValue": 12.5,
                "RawDynastyValue": 14.0,
                "minor_eligible": True,
                "Value_2026": 8.0,
                "CenteringBaselineMean": 2.0,
            }
        ]
    )


def _league_out_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Player": "Prospect Two",
                "ProjectionsUsed": 1,
                "OldestProjectionDate": "2026-01-01",
                "MLBTeam": "SEA",
                "Pos": "SP",
                "Age": 24,
                "DynastyValue": 9.0,
                "RawDynastyValue": 9.5,
                "minor_eligible": False,
                "Value_2026": 6.0,
            }
        ]
    )


def test_build_parser_parses_common_defaults() -> None:
    args = cli._build_parser().parse_args(["common"])
    assert args.mode == "common"
    assert args.teams == 12
    assert args.recent_projections == 3
    assert args.dynamic_replacement_baselines is False


def test_main_common_writes_outputs_even_if_formatting_fails(monkeypatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    def fake_common(excel_path, lg, *, start_year, verbose, return_details, seed, recent_projections):
        calls["excel_path"] = excel_path
        calls["lg"] = lg
        calls["start_year"] = start_year
        calls["verbose"] = verbose
        calls["return_details"] = return_details
        calls["seed"] = seed
        calls["recent_projections"] = recent_projections
        detail = pd.DataFrame([{"Player": "Prospect One", "Year": 2026}])
        return _common_out_frame(), detail, detail.copy()

    monkeypatch.setattr(cli, "calculate_common_dynasty_values", fake_common)

    def raise_format_error(*_args, **_kwargs):
        raise RuntimeError("format failed")

    monkeypatch.setattr(cli._xlsx_fmt, "_xlsx_format_player_values", raise_format_error)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            "common",
            "--input",
            "fake.xlsx",
            "--out-prefix",
            str(tmp_path / "common_values"),
            "--start-year",
            "2026",
            "--recent-projections",
            "2",
        ],
    )

    cli.main()

    assert calls["excel_path"] == "fake.xlsx"
    assert calls["start_year"] == 2026
    assert calls["return_details"] is True
    assert calls["recent_projections"] == 2
    assert (tmp_path / "common_values.csv").exists()
    assert (tmp_path / "common_values.xlsx").exists()


def test_main_league_dispatches_and_writes_outputs(monkeypatch, tmp_path: Path) -> None:
    calls: dict[str, object] = {}

    def fake_league(excel_path, lg, *, start_year, verbose, return_details, seed, recent_projections):
        calls["excel_path"] = excel_path
        calls["lg"] = lg
        calls["start_year"] = start_year
        calls["verbose"] = verbose
        calls["return_details"] = return_details
        calls["seed"] = seed
        calls["recent_projections"] = recent_projections
        detail = pd.DataFrame([{"Player": "Prospect Two", "Year": 2026}])
        return _league_out_frame(), detail, detail.copy()

    monkeypatch.setattr(cli, "calculate_league_dynasty_values", fake_league)
    monkeypatch.setattr(cli._xlsx_fmt, "_xlsx_format_player_values", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(cli._xlsx_fmt, "_xlsx_format_detail_sheet", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prog",
            "league",
            "--input",
            "league.xlsx",
            "--out-prefix",
            str(tmp_path / "league_values"),
            "--seed",
            "9",
            "--recent-projections",
            "4",
        ],
    )

    cli.main()

    assert calls["excel_path"] == "league.xlsx"
    assert calls["start_year"] is None
    assert calls["return_details"] is True
    assert calls["seed"] == 9
    assert calls["recent_projections"] == 4
    assert (tmp_path / "league_values.csv").exists()
    assert (tmp_path / "league_values.xlsx").exists()
