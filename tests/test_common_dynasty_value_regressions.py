from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from backend.valuation.common_orchestration import calculate_common_dynasty_values
from backend.valuation.models import CommonDynastyRotoSettings

pytestmark = pytest.mark.valuation


def _hitter_slots(*, of: int = 0, ut: int = 0) -> dict[str, int]:
    return {
        "C": 0,
        "1B": 0,
        "2B": 0,
        "3B": 0,
        "SS": 0,
        "CI": 0,
        "MI": 0,
        "OF": of,
        "DH": 0,
        "UT": ut,
    }


def _pitcher_slots(*, p: int = 0, sp: int = 0, rp: int = 0) -> dict[str, int]:
    return {"P": p, "SP": sp, "RP": rp}


def _make_hitter(
    name: str,
    *,
    year: int,
    team: str | None = None,
    age: int = 26,
    pos: str = "OF",
    games: float = 150.0,
    ab: float = 600.0,
    hits: float = 170.0,
    runs: float = 80.0,
    hr: float = 20.0,
    rbi: float = 80.0,
    sb: float = 5.0,
    bb: float = 40.0,
    hbp: float = 2.0,
    sf: float = 3.0,
    doubles: float = 20.0,
    triples: float = 2.0,
    minor_eligibility: bool = False,
) -> dict[str, object]:
    return {
        "Player": name,
        "Year": year,
        "Team": team or name[:3],
        "Age": age,
        "Pos": pos,
        "G": games,
        "AB": ab,
        "H": hits,
        "R": runs,
        "HR": hr,
        "RBI": rbi,
        "SB": sb,
        "BB": bb,
        "HBP": hbp,
        "SF": sf,
        "2B": doubles,
        "3B": triples,
        # Avoid the exact "minor_eligible" input column name because the
        # explicit-input parser currently rewrites and drops that label.
        "MinorEligibility": minor_eligibility,
    }


def _make_pitcher(
    name: str,
    *,
    year: int,
    team: str | None = None,
    age: int = 29,
    pos: str = "SP",
    games: float = 30.0,
    gs: float = 30.0,
    ip: float = 160.0,
    wins: float = 10.0,
    strikeouts: float = 150.0,
    er: float = 60.0,
    hits_allowed: float = 140.0,
    walks: float = 45.0,
    saves: float = 0.0,
    qs: float = 14.0,
    qa3: float | None = None,
    minor_eligibility: bool = False,
) -> dict[str, object]:
    return {
        "Player": name,
        "Year": year,
        "Team": team or name[:3],
        "Age": age,
        "Pos": pos,
        "G": games,
        "GS": gs,
        "IP": ip,
        "W": wins,
        "K": strikeouts,
        "ER": er,
        "H": hits_allowed,
        "BB": walks,
        "SV": saves,
        "QS": qs,
        "QA3": qs if qa3 is None else qa3,
        "MinorEligibility": minor_eligibility,
    }


def _write_workbook(tmp_path: Path, *, bat_rows: list[dict[str, object]], pit_rows: list[dict[str, object]]) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "projections.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(bat_rows).to_excel(writer, sheet_name="Bat", index=False)
        pd.DataFrame(pit_rows).to_excel(writer, sheet_name="Pitch", index=False)
    return path


def _run_common_values(
    tmp_path: Path,
    *,
    bat_rows: list[dict[str, object]],
    pit_rows: list[dict[str, object]],
    start_year: int = 2026,
    seed: int = 11,
    **settings_overrides: object,
) -> pd.DataFrame:
    workbook = _write_workbook(tmp_path, bat_rows=bat_rows, pit_rows=pit_rows)
    base_settings = dict(
        n_teams=2,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(p=1),
        bench_slots=0,
        minor_slots=0,
        ir_slots=0,
        sims_for_sgp=50,
        discount=1.0,
        horizon_years=1,
        hitter_categories=("HR",),
        pitcher_categories=("W",),
        two_way="sum",
        # This file locks long-lived common-mode math expectations and should
        # not drift when default methodology tuning changes elsewhere.
        enable_replacement_blend=False,
        replacement_depth_mode="flat",
    )
    base_settings.update(settings_overrides)
    out = calculate_common_dynasty_values(
        str(workbook),
        CommonDynastyRotoSettings(**base_settings),
        start_year=start_year,
        verbose=False,
        seed=seed,
    )
    if isinstance(out, tuple):
        return out[0]
    return out


def _rows_by_player(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.set_index("Player")


def test_hr_only_of_league_locks_expected_hitter_values(tmp_path: Path) -> None:
    bat_rows = [
        _make_hitter("Slugger", year=2026, hr=40),
        _make_hitter("Balanced", year=2026, hr=30),
        _make_hitter("Bat3", year=2026, hr=24),
        _make_hitter("Bat4", year=2026, hr=20),
        _make_hitter("Bat5", year=2026, hr=18),
        _make_hitter("Bat6", year=2026, hr=15),
    ]
    pit_rows = [_make_pitcher(f"P{i}", year=2026, wins=10) for i in range(1, 7)]

    out = _run_common_values(
        tmp_path,
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(p=1),
        hitter_categories=("HR",),
        pitcher_categories=("W",),
    )
    rows = _rows_by_player(out)

    assert rows.loc["Slugger", "DynastyValue"] == pytest.approx(3.493333333333333)
    assert rows.loc["Balanced", "DynastyValue"] == pytest.approx(2.493333333333333)
    assert rows.loc["Bat3", "DynastyValue"] == pytest.approx(0.4533333333333333)
    assert rows.loc["Bat4", "DynastyValue"] == pytest.approx(-0.4533333333333333)
    assert rows.loc["Slugger", "RawDynastyValue"] == pytest.approx(3.493333333333333)
    assert rows.loc["Bat4", "RawDynastyValue"] == pytest.approx(0.0)


def test_sv_only_rp_league_locks_expected_reliever_values(tmp_path: Path) -> None:
    bat_rows = [_make_hitter(f"Bat{i}", year=2026, hr=20) for i in range(1, 7)]
    pit_rows = [
        _make_pitcher("CloserA", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=35, qs=0, qa3=0),
        _make_pitcher("CloserB", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=28, qs=0, qa3=0),
        _make_pitcher("RP3", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=18, qs=0, qa3=0),
        _make_pitcher("RP4", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=12, qs=0, qa3=0),
        _make_pitcher("RP5", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=8, qs=0, qa3=0),
        _make_pitcher("RP6", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=5, qs=0, qa3=0),
    ]

    out = _run_common_values(
        tmp_path,
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(rp=1),
        hitter_categories=("HR",),
        pitcher_categories=("SV",),
    )
    rows = _rows_by_player(out)

    assert rows.loc["CloserA", "DynastyValue"] == pytest.approx(2.857142857142857)
    assert rows.loc["CloserB", "DynastyValue"] == pytest.approx(1.8571428571428572)
    assert rows.loc["RP3", "DynastyValue"] == pytest.approx(0.42857142857142855)
    assert rows.loc["RP4", "DynastyValue"] == pytest.approx(-0.42857142857142855)
    assert rows.loc["CloserA", "RawDynastyValue"] == pytest.approx(2.857142857142857)


def test_sv_only_generic_p_league_keeps_rp_only_closer_value(tmp_path: Path) -> None:
    bat_rows = [_make_hitter(f"Bat{i}", year=2026, hr=20) for i in range(1, 7)]
    pit_rows = [
        _make_pitcher(
            "CloserA",
            year=2026,
            pos="RP",
            games=65,
            gs=0,
            ip=65,
            wins=4,
            strikeouts=80,
            er=20,
            hits_allowed=45,
            walks=18,
            saves=35,
            qs=0,
            qa3=0,
        ),
        _make_pitcher(
            "CloserB",
            year=2026,
            pos="RP",
            games=65,
            gs=0,
            ip=65,
            wins=4,
            strikeouts=80,
            er=20,
            hits_allowed=45,
            walks=18,
            saves=28,
            qs=0,
            qa3=0,
        ),
        _make_pitcher("SP3", year=2026, pos="SP", games=30, gs=30, ip=170, wins=10, strikeouts=170, saves=0),
        _make_pitcher("SP4", year=2026, pos="SP", games=30, gs=30, ip=165, wins=9, strikeouts=160, saves=0),
        _make_pitcher("SP5", year=2026, pos="SP", games=30, gs=30, ip=160, wins=8, strikeouts=150, saves=0),
        _make_pitcher("SP6", year=2026, pos="SP", games=30, gs=30, ip=155, wins=7, strikeouts=140, saves=0),
    ]

    out = _run_common_values(
        tmp_path,
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(p=1),
        hitter_categories=("HR",),
        pitcher_categories=("SV",),
    )
    rows = _rows_by_player(out)

    assert rows.loc["CloserA", "DynastyValue"] > 2.5
    assert rows.loc["CloserB", "DynastyValue"] > 1.5
    assert rows.loc["SP3", "DynastyValue"] == pytest.approx(0.0)
    assert rows.loc["SP4", "DynastyValue"] == pytest.approx(0.0)


def test_two_way_sum_mode_exceeds_max_mode_for_dual_threat(tmp_path: Path) -> None:
    bat_rows = [
        _make_hitter("Dual Threat", year=2026, hr=40),
        _make_hitter("Slugger", year=2026, hr=38),
        _make_hitter("Balanced", year=2026, hr=30),
        _make_hitter("Bat4", year=2026, hr=20),
        _make_hitter("Bat5", year=2026, hr=18),
        _make_hitter("Bat6", year=2026, hr=15),
    ]
    pit_rows = [
        _make_pitcher("Dual Threat", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=35, qs=0, qa3=0),
        _make_pitcher("CloserA", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=34, qs=0, qa3=0),
        _make_pitcher("CloserB", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=28, qs=0, qa3=0),
        _make_pitcher("RP4", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=12, qs=0, qa3=0),
        _make_pitcher("RP5", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=8, qs=0, qa3=0),
        _make_pitcher("RP6", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=5, qs=0, qa3=0),
    ]

    out_max = _run_common_values(
        tmp_path / "max",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(rp=1),
        hitter_categories=("HR",),
        pitcher_categories=("SV",),
        two_way="max",
    )
    out_sum = _run_common_values(
        tmp_path / "sum",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(rp=1),
        hitter_categories=("HR",),
        pitcher_categories=("SV",),
        two_way="sum",
    )
    max_rows = _rows_by_player(out_max)
    sum_rows = _rows_by_player(out_sum)

    assert max_rows.loc["Dual Threat", "RawDynastyValue"] == pytest.approx(20.6)
    assert sum_rows.loc["Dual Threat", "RawDynastyValue"] == pytest.approx(36.6)
    assert max_rows.loc["Dual Threat", "DynastyValue"] == pytest.approx(19.676923076923078)
    assert sum_rows.loc["Dual Threat", "DynastyValue"] == pytest.approx(35.67692307692308)
    assert sum_rows.loc["Dual Threat", "RawDynastyValue"] > max_rows.loc["Dual Threat", "RawDynastyValue"]


def test_deeper_outfield_configuration_lowers_replacement_baseline_and_lifts_fringe_bats(tmp_path: Path) -> None:
    bat_rows = [
        _make_hitter("Slugger", year=2026, hr=40),
        _make_hitter("Balanced", year=2026, hr=30),
        _make_hitter("Bat3", year=2026, hr=24),
        _make_hitter("Bat4", year=2026, hr=20),
        _make_hitter("Bat5", year=2026, hr=18),
        _make_hitter("Bat6", year=2026, hr=15),
        _make_hitter("Bat7", year=2026, hr=12),
        _make_hitter("Bat8", year=2026, hr=10),
    ]
    pit_rows = [_make_pitcher(f"P{i}", year=2026, wins=15 - i) for i in range(1, 9)]

    shallow = _run_common_values(
        tmp_path / "shallow",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(p=1),
    )
    deeper = _run_common_values(
        tmp_path / "deeper",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=2),
        pitcher_slots=_pitcher_slots(p=1),
    )
    shallow_rows = _rows_by_player(shallow)
    deep_rows = _rows_by_player(deeper)

    assert shallow.attrs["valuation_diagnostics"]["CenteringBaselineValue"] == pytest.approx(1.5)
    assert deeper.attrs["valuation_diagnostics"]["CenteringBaselineValue"] == pytest.approx(1.0104166666666665)
    assert deep_rows.loc["Bat3", "DynastyValue"] > shallow_rows.loc["Bat3", "DynastyValue"]
    assert deep_rows.loc["Bat4", "DynastyValue"] > shallow_rows.loc["Bat4", "DynastyValue"]
    assert deep_rows.loc["Bat4", "DynastyValue"] == pytest.approx(0.0)


def test_longer_horizon_and_lighter_discount_favor_future_heavy_prospect(tmp_path: Path) -> None:
    years = [2026, 2027, 2028]
    bat_rows: list[dict[str, object]] = [
        _make_hitter("Veteran", year=2026, age=33, hr=40),
        _make_hitter("Veteran", year=2027, age=34, hr=12),
        _make_hitter("Veteran", year=2028, age=35, hr=8),
        _make_hitter("Prospect", year=2026, age=21, hr=8, minor_eligibility=True),
        _make_hitter("Prospect", year=2027, age=22, hr=24, minor_eligibility=True),
        _make_hitter("Prospect", year=2028, age=23, hr=38),
    ]
    for i, hr_base in enumerate([30, 26, 22, 18, 16, 14, 10, 8], start=1):
        for year in years:
            bat_rows.append(
                _make_hitter(
                    f"Bat{i}",
                    year=year,
                    age=25 + (i % 5),
                    hr=max(4, hr_base - (year - 2026) * 2),
                )
            )
    pit_rows = [
        _make_pitcher(f"P{i}", year=year, age=29 + (year - 2026), wins=10)
        for i in range(1, 11)
        for year in years
    ]

    short = _run_common_values(
        tmp_path / "short",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        horizon_years=1,
        discount=0.9,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(p=1),
        enable_prospect_risk_adjustment=False,
        enable_age_risk_adjustment=False,
    )
    long = _run_common_values(
        tmp_path / "long",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        horizon_years=3,
        discount=1.0,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(p=1),
        enable_prospect_risk_adjustment=False,
        enable_age_risk_adjustment=False,
    )
    short_rows = _rows_by_player(short)
    long_rows = _rows_by_player(long)

    assert short_rows.loc["Veteran", "DynastyValue"] > short_rows.loc["Prospect", "DynastyValue"]
    assert long_rows.loc["Prospect", "DynastyValue"] > 0.0
    assert long_rows.loc["Prospect", "DynastyValue"] > short_rows.loc["Prospect", "DynastyValue"]
    assert long_rows.loc["Prospect", "DynastyValue"] > long_rows.loc["Veteran", "DynastyValue"] - 0.5


def test_age_risk_adjustment_penalizes_older_comparable_bat(tmp_path: Path) -> None:
    years = [2026, 2027, 2028]
    bat_rows: list[dict[str, object]] = []
    for year in years:
        bat_rows.extend(
            [
                _make_hitter("Young Star", year=year, age=24 + (year - 2026), hr=34),
                _make_hitter("Old Star", year=year, age=34 + (year - 2026), hr=34),
                _make_hitter("Elite", year=year, age=27 + (year - 2026), hr=40),
                _make_hitter("Strong", year=year, age=29 + (year - 2026), hr=36),
                _make_hitter("Mid", year=year, age=28 + (year - 2026), hr=28),
                _make_hitter("Low", year=year, age=28 + (year - 2026), hr=20),
                _make_hitter("Bench1", year=year, age=28 + (year - 2026), hr=18),
                _make_hitter("Bench2", year=year, age=28 + (year - 2026), hr=16),
            ]
        )
    pit_rows = [
        _make_pitcher(f"P{i}", year=year, age=29 + (year - 2026), wins=10)
        for i in range(1, 9)
        for year in years
    ]

    no_risk = _run_common_values(
        tmp_path / "no_risk",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        horizon_years=3,
        hitter_slots=_hitter_slots(of=2),
        pitcher_slots=_pitcher_slots(p=2),
        enable_age_risk_adjustment=False,
    )
    with_risk = _run_common_values(
        tmp_path / "with_risk",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        horizon_years=3,
        hitter_slots=_hitter_slots(of=2),
        pitcher_slots=_pitcher_slots(p=2),
        enable_age_risk_adjustment=True,
    )
    no_risk_rows = _rows_by_player(no_risk)
    with_risk_rows = _rows_by_player(with_risk)

    assert no_risk_rows.loc["Young Star", "DynastyValue"] == pytest.approx(no_risk_rows.loc["Old Star", "DynastyValue"])
    assert with_risk_rows.loc["Young Star", "DynastyValue"] == pytest.approx(no_risk_rows.loc["Young Star", "DynastyValue"])
    assert with_risk_rows.loc["Old Star", "DynastyValue"] < no_risk_rows.loc["Old Star", "DynastyValue"]
    assert with_risk_rows.loc["Young Star", "DynastyValue"] > with_risk_rows.loc["Old Star", "DynastyValue"]


def test_prospect_risk_adjustment_discounts_minor_eligible_future_value(tmp_path: Path) -> None:
    years = [2026, 2027, 2028]
    bat_rows: list[dict[str, object]] = []
    for year, minor_flag in [(2026, True), (2027, True), (2028, False)]:
        bat_rows.append(_make_hitter("Prospect", year=year, age=21 + (year - 2026), hr=18 if year == 2026 else 34, minor_eligibility=minor_flag))
    for year in years:
        bat_rows.append(_make_hitter("MLB Ready", year=year, age=24 + (year - 2026), hr=18 if year == 2026 else 34))
    for i, hr_base in enumerate([40, 36, 30, 28, 24, 20, 18, 16], start=1):
        for year in years:
            bat_rows.append(
                _make_hitter(
                    f"Bat{i}",
                    year=year,
                    age=26 + (i % 4),
                    hr=max(10, hr_base - (year - 2026)),
                )
            )
    pit_rows = [
        _make_pitcher(f"P{i}", year=year, age=29 + (year - 2026), wins=10)
        for i in range(1, 11)
        for year in years
    ]

    no_discount = _run_common_values(
        tmp_path / "no_discount",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        horizon_years=3,
        hitter_slots=_hitter_slots(of=2),
        pitcher_slots=_pitcher_slots(p=2),
        enable_prospect_risk_adjustment=False,
        enable_age_risk_adjustment=False,
    )
    with_discount = _run_common_values(
        tmp_path / "with_discount",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        horizon_years=3,
        hitter_slots=_hitter_slots(of=2),
        pitcher_slots=_pitcher_slots(p=2),
        enable_prospect_risk_adjustment=True,
        enable_age_risk_adjustment=False,
    )
    no_discount_rows = _rows_by_player(no_discount)
    with_discount_rows = _rows_by_player(with_discount)

    assert bool(with_discount_rows.loc["Prospect", "minor_eligible"]) is True
    assert no_discount_rows.loc["Prospect", "DynastyValue"] == pytest.approx(no_discount_rows.loc["MLB Ready", "DynastyValue"])
    assert with_discount_rows.loc["Prospect", "DynastyValue"] < no_discount_rows.loc["Prospect", "DynastyValue"]
    assert with_discount_rows.loc["MLB Ready", "DynastyValue"] == pytest.approx(no_discount_rows.loc["MLB Ready", "DynastyValue"])


def test_bench_stash_relief_softens_negative_hold_cost_for_future_bat(tmp_path: Path) -> None:
    bat_rows = [
        _make_hitter("Bench Bat", year=2026, age=24, hr=6, games=40, ab=150, hits=38, runs=18, rbi=16, sb=1, bb=10, hbp=0, sf=0, doubles=3, triples=0),
        _make_hitter("Bench Bat", year=2027, age=25, hr=34),
    ]
    for name, hr26, hr27 in [
        ("Anchor", 38, 36),
        ("Second", 30, 28),
        ("Third", 26, 24),
        ("Fourth", 22, 20),
        ("Fifth", 18, 16),
        ("Sixth", 16, 14),
        ("Seventh", 14, 12),
        ("Eighth", 12, 10),
        ("Ninth", 10, 8),
    ]:
        bat_rows.extend(
            [
                _make_hitter(name, year=2026, age=26, hr=hr26, hits=150, runs=65, rbi=72, sb=4, bb=25, hbp=2, sf=2, doubles=15, triples=1),
                _make_hitter(name, year=2027, age=27, hr=hr27, hits=150, runs=65, rbi=72, sb=4, bb=25, hbp=2, sf=2, doubles=15, triples=1),
            ]
        )
    pit_rows = [
        _make_pitcher(f"P{i}", year=2026, age=28, wins=w)
        for i, w in enumerate([14, 13, 12, 11, 10, 9, 8, 7, 6], start=1)
    ] + [
        _make_pitcher(f"P{i}", year=2027, age=29, wins=max(4, w - 1))
        for i, w in enumerate([14, 13, 12, 11, 10, 9, 8, 7, 6], start=1)
    ]

    without_relief = _run_common_values(
        tmp_path / "without_relief",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        horizon_years=2,
        discount=0.94,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(p=1),
        bench_slots=1,
        enable_bench_stash_relief=False,
        bench_negative_penalty=0.5,
    )
    with_relief = _run_common_values(
        tmp_path / "with_relief",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        horizon_years=2,
        discount=0.94,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(p=1),
        bench_slots=1,
        enable_bench_stash_relief=True,
        bench_negative_penalty=0.5,
    )
    without_rows = _rows_by_player(without_relief)
    with_rows = _rows_by_player(with_relief)

    assert without_rows.loc["Bench Bat", "Value_2026"] < 0.0
    assert with_rows.loc["Bench Bat", "RawDynastyValue"] > without_rows.loc["Bench Bat", "RawDynastyValue"]
    assert with_rows.loc["Bench Bat", "ForcedRosterValue"] > without_rows.loc["Bench Bat", "ForcedRosterValue"]


def test_ir_stash_relief_softens_negative_hold_cost_for_injured_bat(tmp_path: Path) -> None:
    bat_rows = [
        _make_hitter("Injured Bat", year=2026, age=24, hr=0, games=0, ab=0, hits=0, runs=0, rbi=0, sb=0, bb=0, hbp=0, sf=0, doubles=0, triples=0),
        _make_hitter("Injured Bat", year=2027, age=25, hr=34),
    ]
    for name, hr26, hr27 in [
        ("Anchor", 38, 36),
        ("Second", 30, 28),
        ("Third", 26, 24),
        ("Fourth", 22, 20),
        ("Fifth", 18, 16),
        ("Sixth", 16, 14),
        ("Seventh", 14, 12),
        ("Eighth", 12, 10),
        ("Ninth", 10, 8),
    ]:
        bat_rows.extend(
            [
                _make_hitter(name, year=2026, age=26, hr=hr26, hits=150, runs=65, rbi=72, sb=4, bb=25, hbp=2, sf=2, doubles=15, triples=1),
                _make_hitter(name, year=2027, age=27, hr=hr27, hits=150, runs=65, rbi=72, sb=4, bb=25, hbp=2, sf=2, doubles=15, triples=1),
            ]
        )
    pit_rows = [
        _make_pitcher(f"P{i}", year=2026, age=28, wins=w)
        for i, w in enumerate([14, 13, 12, 11, 10, 9, 8, 7, 6], start=1)
    ] + [
        _make_pitcher(f"P{i}", year=2027, age=29, wins=max(4, w - 1))
        for i, w in enumerate([14, 13, 12, 11, 10, 9, 8, 7, 6], start=1)
    ]

    without_relief = _run_common_values(
        tmp_path / "without_relief",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        horizon_years=2,
        discount=0.94,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(p=1),
        ir_slots=1,
        enable_ir_stash_relief=False,
        ir_negative_penalty=0.2,
    )
    with_relief = _run_common_values(
        tmp_path / "with_relief",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        horizon_years=2,
        discount=0.94,
        hitter_slots=_hitter_slots(of=1),
        pitcher_slots=_pitcher_slots(p=1),
        ir_slots=1,
        enable_ir_stash_relief=True,
        ir_negative_penalty=0.2,
    )
    without_rows = _rows_by_player(without_relief)
    with_rows = _rows_by_player(with_relief)

    assert without_rows.loc["Injured Bat", "Value_2026"] < 0.0
    assert with_rows.loc["Injured Bat", "RawDynastyValue"] > without_rows.loc["Injured Bat", "RawDynastyValue"]
    assert with_rows.loc["Injured Bat", "ForcedRosterValue"] > without_rows.loc["Injured Bat", "ForcedRosterValue"]


def test_adding_stolen_bases_lifts_speedster_relative_to_slugger(tmp_path: Path) -> None:
    bat_rows = [
        _make_hitter("Slugger", year=2026, hr=36, sb=3),
        _make_hitter("Speedster", year=2026, hr=12, sb=35),
        _make_hitter("Balanced", year=2026, hr=24, sb=14),
        _make_hitter("Bat4", year=2026, hr=20, sb=8),
        _make_hitter("Bat5", year=2026, hr=16, sb=6),
        _make_hitter("Bat6", year=2026, hr=12, sb=4),
        _make_hitter("Bat7", year=2026, hr=10, sb=3),
        _make_hitter("Bat8", year=2026, hr=8, sb=2),
    ]
    pit_rows = [_make_pitcher(f"P{i}", year=2026, wins=15 - i) for i in range(1, 9)]

    hr_only = _run_common_values(
        tmp_path / "hr_only",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=2),
        pitcher_slots=_pitcher_slots(p=2),
        hitter_categories=("HR",),
    )
    hr_sb = _run_common_values(
        tmp_path / "hr_sb",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=2),
        pitcher_slots=_pitcher_slots(p=2),
        hitter_categories=("HR", "SB"),
    )
    hr_only_rows = _rows_by_player(hr_only)
    hr_sb_rows = _rows_by_player(hr_sb)

    assert hr_only_rows.loc["Slugger", "DynastyValue"] > hr_only_rows.loc["Speedster", "DynastyValue"]
    assert hr_sb_rows.loc["Speedster", "DynastyValue"] > hr_only_rows.loc["Speedster", "DynastyValue"]
    assert hr_sb_rows.loc["Speedster", "DynastyValue"] > hr_sb_rows.loc["Slugger", "DynastyValue"] - 0.2


def test_rp_slot_and_saves_category_raise_closer_relative_to_starter(tmp_path: Path) -> None:
    bat_rows = [
        _make_hitter("Bat1", year=2026, hr=30),
        _make_hitter("Bat2", year=2026, hr=26),
        _make_hitter("Bat3", year=2026, hr=22),
        _make_hitter("Bat4", year=2026, hr=18),
        _make_hitter("Bat5", year=2026, hr=14),
        _make_hitter("Bat6", year=2026, hr=12),
        _make_hitter("Bat7", year=2026, hr=10),
        _make_hitter("Bat8", year=2026, hr=8),
    ]
    pit_rows = [
        _make_pitcher("Starter Ace", year=2026, wins=15, strikeouts=180, ip=180, qs=18),
        _make_pitcher("Starter 2", year=2026, wins=12, strikeouts=170, ip=175, qs=17),
        _make_pitcher("Starter 3", year=2026, wins=10, strikeouts=160, ip=170, qs=16),
        _make_pitcher("Starter 4", year=2026, wins=8, strikeouts=150, ip=165, qs=15),
        _make_pitcher("Closer Ace", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=85, er=20, hits_allowed=45, walks=18, saves=35, qs=0, qa3=0),
        _make_pitcher("Closer 2", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=80, er=20, hits_allowed=45, walks=18, saves=28, qs=0, qa3=0),
        _make_pitcher("Closer 3", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=75, er=20, hits_allowed=45, walks=18, saves=18, qs=0, qa3=0),
        _make_pitcher("Closer 4", year=2026, pos="RP", games=65, gs=0, ip=65, wins=4, strikeouts=70, er=20, hits_allowed=45, walks=18, saves=12, qs=0, qa3=0),
    ]

    starter_context = _run_common_values(
        tmp_path / "starter_context",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=2),
        pitcher_slots=_pitcher_slots(p=1),
        pitcher_categories=("W",),
    )
    reliever_context = _run_common_values(
        tmp_path / "reliever_context",
        bat_rows=bat_rows,
        pit_rows=pit_rows,
        hitter_slots=_hitter_slots(of=2),
        pitcher_slots=_pitcher_slots(rp=1),
        pitcher_categories=("SV",),
    )
    starter_rows = _rows_by_player(starter_context)
    reliever_rows = _rows_by_player(reliever_context)

    assert starter_rows.loc["Starter Ace", "DynastyValue"] > starter_rows.loc["Closer Ace", "DynastyValue"]
    assert reliever_rows.loc["Closer Ace", "DynastyValue"] > reliever_rows.loc["Starter Ace", "DynastyValue"]
    assert reliever_rows.loc["Closer Ace", "RawDynastyValue"] > 0.0
