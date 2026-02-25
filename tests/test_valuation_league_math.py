from __future__ import annotations

import numpy as np
import pandas as pd

from backend.valuation import league_math
from backend.valuation.models import LEAGUE_HIT_STAT_COLS, LeagueSettings


def test_league_ensure_pitch_cols_builds_svh_from_sv_and_hld() -> None:
    df = pd.DataFrame([{"SV": 10.0, "HLD": 15.0}])

    out = league_math.league_ensure_pitch_cols(df)

    assert "SVH" in out.columns
    assert float(out.loc[0, "SVH"]) == 25.0


def test_league_team_avg_ops_computes_avg_and_ops() -> None:
    hit_tot = pd.Series({"AB": 100.0, "H": 30.0, "TB": 55.0, "OBP_num": 40.0, "OBP_den": 120.0})

    avg, ops = league_math.league_team_avg_ops(hit_tot)

    assert avg == 0.3
    assert ops == (40.0 / 120.0) + (55.0 / 100.0)


def test_league_replacement_pitcher_rates_returns_zero_when_no_free_agents() -> None:
    all_pit = pd.DataFrame(
        [
            {"Player": "A", "weight": 1.0, "IP": 100.0, "W": 8.0, "K": 100.0, "SVH": 0.0, "QA3": 10.0, "ER": 40.0, "H": 90.0, "BB": 30.0}
        ]
    )
    assigned = pd.DataFrame([{"Player": "A"}])

    rates = league_math.league_replacement_pitcher_rates(all_pit, assigned, n_rep=10)

    assert rates == {"W": 0.0, "K": 0.0, "SVH": 0.0, "QA3": 0.0, "ER": 0.0, "H": 0.0, "BB": 0.0}


def test_league_apply_ip_cap_scales_over_and_fills_under() -> None:
    over = {"IP": 200.0, "W": 20.0, "K": 200.0, "SVH": 40.0, "QA3": 20.0, "ER": 80.0, "H": 160.0, "BB": 60.0}
    over_capped = league_math.league_apply_ip_cap(over, ip_cap=100.0, rep_rates=None)
    assert over_capped["IP"] == 100.0
    assert over_capped["W"] == 10.0
    assert over_capped["ERA"] == 9.0 * 40.0 / 100.0

    under = {"IP": 80.0, "W": 8.0, "K": 80.0, "SVH": 16.0, "QA3": 8.0, "ER": 32.0, "H": 64.0, "BB": 24.0}
    rep_rates = {"W": 0.1, "K": 1.0, "SVH": 0.2, "QA3": 0.1, "ER": 0.4, "H": 0.8, "BB": 0.3}
    under_capped = league_math.league_apply_ip_cap(under, ip_cap=100.0, rep_rates=rep_rates)
    assert under_capped["IP"] == 100.0
    assert under_capped["W"] == 10.0
    assert under_capped["K"] == 100.0


def test_league_simulate_sgp_hit_and_pit_return_expected_category_keys() -> None:
    lg = LeagueSettings(
        n_teams=2,
        sims_for_sgp=2,
        hitter_slots={"C": 0, "1B": 0, "2B": 0, "3B": 0, "SS": 0, "CI": 0, "MI": 0, "OF": 1, "UT": 0},
        pitcher_slots={"SP": 1, "RP": 0, "P": 0},
        ip_max=150.0,
    )

    hit_rows = []
    for player, r, hr, rbi, sb in [("A", 80.0, 20.0, 75.0, 10.0), ("B", 70.0, 15.0, 65.0, 8.0)]:
        row = {col: 0.0 for col in LEAGUE_HIT_STAT_COLS}
        row.update(
            {
                "Player": player,
                "AssignedSlot": "OF",
                "AB": 500.0,
                "H": 145.0 if player == "A" else 135.0,
                "R": r,
                "HR": hr,
                "RBI": rbi,
                "SB": sb,
                "BB": 55.0,
                "HBP": 4.0,
                "SF": 5.0,
                "2B": 30.0,
                "3B": 2.0,
                "TB": 240.0 if player == "A" else 220.0,
                "OBP_num": 204.0 if player == "A" else 194.0,
                "OBP_den": 564.0,
            }
        )
        hit_rows.append(row)
    assigned_hit = pd.DataFrame(hit_rows)

    assigned_pit = pd.DataFrame(
        [
            {"Player": "P1", "AssignedSlot": "SP", "IP": 160.0, "W": 12.0, "K": 170.0, "SVH": 0.0, "QA3": 16.0, "ER": 60.0, "H": 145.0, "BB": 45.0},
            {"Player": "P2", "AssignedSlot": "SP", "IP": 150.0, "W": 10.0, "K": 155.0, "SVH": 0.0, "QA3": 14.0, "ER": 62.0, "H": 150.0, "BB": 48.0},
        ]
    )

    sgp_hit = league_math.league_simulate_sgp_hit(assigned_hit, lg, np.random.default_rng(1))
    sgp_pit = league_math.league_simulate_sgp_pit(
        assigned_pit,
        lg,
        rep_rates={"W": 0.0, "K": 0.0, "SVH": 0.0, "QA3": 0.0, "ER": 0.0, "H": 0.0, "BB": 0.0},
        rng=np.random.default_rng(2),
    )

    assert set(sgp_hit.keys()) == {"R", "HR", "RBI", "SB", "AVG", "OPS"}
    assert set(sgp_pit.keys()) == {"W", "K", "SVH", "QA3", "ERA", "WHIP"}
    assert all(np.isfinite(float(v)) for v in sgp_hit.values())
    assert all(np.isfinite(float(v)) for v in sgp_pit.values())


def test_league_simulate_sgp_robust_mode_applies_denominator_floors() -> None:
    lg = LeagueSettings(
        n_teams=1,
        sims_for_sgp=2,
        hitter_slots={"C": 0, "1B": 0, "2B": 0, "3B": 0, "SS": 0, "CI": 0, "MI": 0, "OF": 1, "UT": 0},
        pitcher_slots={"SP": 1, "RP": 0, "P": 0},
        ip_max=150.0,
        sgp_denominator_mode="robust",
        sgp_epsilon_counting=0.2,
        sgp_epsilon_ratio=0.005,
    )

    hit_rows = []
    for player in ["A"]:
        row = {col: 0.0 for col in LEAGUE_HIT_STAT_COLS}
        row.update(
            {
                "Player": player,
                "AssignedSlot": "OF",
                "AB": 500.0,
                "H": 145.0,
                "R": 80.0,
                "HR": 20.0,
                "RBI": 75.0,
                "SB": 10.0,
                "BB": 55.0,
                "HBP": 4.0,
                "SF": 5.0,
                "2B": 30.0,
                "3B": 2.0,
                "TB": 240.0,
                "OBP_num": 204.0,
                "OBP_den": 564.0,
            }
        )
        hit_rows.append(row)
    assigned_hit = pd.DataFrame(hit_rows)
    assigned_pit = pd.DataFrame(
        [
            {"Player": "P1", "AssignedSlot": "SP", "IP": 160.0, "W": 12.0, "K": 170.0, "SVH": 0.0, "QA3": 16.0, "ER": 60.0, "H": 145.0, "BB": 45.0}
        ]
    )

    sgp_hit = league_math.league_simulate_sgp_hit(assigned_hit, lg, np.random.default_rng(1))
    sgp_pit = league_math.league_simulate_sgp_pit(
        assigned_pit,
        lg,
        rep_rates={"W": 0.0, "K": 0.0, "SVH": 0.0, "QA3": 0.0, "ER": 0.0, "H": 0.0, "BB": 0.0},
        rng=np.random.default_rng(2),
    )

    assert sgp_hit["R"] >= 0.2
    assert sgp_hit["AVG"] >= 0.005
    assert sgp_pit["W"] >= 0.2
    assert sgp_pit["ERA"] >= 0.005


def test_league_playing_time_reliability_helpers_scale_positive_components_only() -> None:
    hit_delta = {"R": 2.0, "AVG": 0.01, "SB": -0.1}
    league_math._apply_hitter_playing_time_reliability_guard(
        hit_delta,
        hitter_ab=40.0,
        slot_ab_reference=200.0,
    )
    assert hit_delta["R"] == 0.0
    assert hit_delta["AVG"] == 0.0
    assert hit_delta["SB"] == -0.1

    pit_delta = {"W": 1.2, "ERA": 0.8, "WHIP": -0.1}
    league_math._apply_pitcher_playing_time_reliability_guard(
        pit_delta,
        pitcher_ip=20.0,
        slot_ip_reference=100.0,
    )
    assert pit_delta["W"] == 0.0
    assert pit_delta["ERA"] == 0.0
    assert pit_delta["WHIP"] == -0.1


def test_league_combine_hitter_pitcher_year_handles_max_and_sum_modes() -> None:
    hit_vals = pd.DataFrame(
        [
            {"Player": "TwoWay", "Year": 2026, "YearValue": 5.0, "BestSlot": "OF", "Pos": "OF", "MLBTeam": "AAA", "Age": 25},
            {"Player": "OnlyHit", "Year": 2026, "YearValue": 3.0, "BestSlot": "1B", "Pos": "1B", "MLBTeam": "BBB", "Age": 27},
        ]
    )
    pit_vals = pd.DataFrame(
        [
            {"Player": "TwoWay", "Year": 2026, "YearValue": 6.0, "BestSlot": "SP", "Pos": "SP", "MLBTeam": "AAA", "Age": 25},
            {"Player": "OnlyPit", "Year": 2026, "YearValue": 4.0, "BestSlot": "RP", "Pos": "RP", "MLBTeam": "CCC", "Age": 29},
        ]
    )

    max_mode = league_math.league_combine_hitter_pitcher_year(hit_vals, pit_vals, two_way="max")
    sum_mode = league_math.league_combine_hitter_pitcher_year(hit_vals, pit_vals, two_way="sum")

    max_by_player = {row.Player: (float(row.YearValue), row.BestSlot) for row in max_mode.itertuples(index=False)}
    sum_by_player = {row.Player: (float(row.YearValue), row.BestSlot) for row in sum_mode.itertuples(index=False)}

    assert max_by_player["TwoWay"] == (6.0, "SP")
    assert sum_by_player["TwoWay"] == (11.0, "OF+SP")
    assert max_by_player["OnlyHit"] == (3.0, "1B")
    assert max_by_player["OnlyPit"] == (4.0, "RP")
