from backend import dynasty_roto_values
from backend.valuation import cli, common_orchestration, league_orchestration


def test_common_wrapper_delegates_to_extracted_module(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_common(excel_path, lg, *, start_year, years, verbose, return_details, seed, recent_projections):
        calls["excel_path"] = excel_path
        calls["lg"] = lg
        calls["start_year"] = start_year
        calls["years"] = years
        calls["verbose"] = verbose
        calls["return_details"] = return_details
        calls["seed"] = seed
        calls["recent_projections"] = recent_projections
        return "common-ok"

    monkeypatch.setattr(common_orchestration, "calculate_common_dynasty_values", fake_common)
    out = dynasty_roto_values.calculate_common_dynasty_values(
        "values.xlsx",
        {"kind": "lg"},
        start_year=2026,
        years=[2026, 2027],
        verbose=False,
        return_details=True,
        seed=11,
        recent_projections=5,
    )

    assert out == "common-ok"
    assert calls["excel_path"] == "values.xlsx"
    assert calls["start_year"] == 2026
    assert calls["years"] == [2026, 2027]
    assert calls["verbose"] is False
    assert calls["return_details"] is True
    assert calls["seed"] == 11
    assert calls["recent_projections"] == 5


def test_league_wrapper_delegates_to_extracted_module(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_league(excel_path, lg, *, start_year, years, verbose, return_details, seed, recent_projections):
        calls["excel_path"] = excel_path
        calls["lg"] = lg
        calls["start_year"] = start_year
        calls["years"] = years
        calls["verbose"] = verbose
        calls["return_details"] = return_details
        calls["seed"] = seed
        calls["recent_projections"] = recent_projections
        return "league-ok"

    monkeypatch.setattr(league_orchestration, "calculate_league_dynasty_values", fake_league)
    out = dynasty_roto_values.calculate_league_dynasty_values(
        "league.xlsx",
        {"kind": "lg"},
        start_year=2027,
        years=[2027],
        verbose=False,
        return_details=True,
        seed=3,
        recent_projections=2,
    )

    assert out == "league-ok"
    assert calls["excel_path"] == "league.xlsx"
    assert calls["start_year"] == 2027
    assert calls["years"] == [2027]
    assert calls["verbose"] is False
    assert calls["return_details"] is True
    assert calls["seed"] == 3
    assert calls["recent_projections"] == 2


def test_main_wrapper_delegates_to_cli_module(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_main() -> None:
        calls["count"] += 1

    monkeypatch.setattr(cli, "main", fake_main)
    dynasty_roto_values.main()
    assert calls["count"] == 1
