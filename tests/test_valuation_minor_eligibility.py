from __future__ import annotations

import pandas as pd
import pytest

from backend.valuation import minor_eligibility

pytestmark = pytest.mark.valuation


def test_infer_minor_eligibility_by_year_enforces_once_lost_rule() -> None:
    bat = pd.DataFrame(
        [
            {"Player": "Prospect", "Year": 2026, "AB": 60.0, "Age": 22.0},
            {"Player": "Prospect", "Year": 2027, "AB": 80.0, "Age": 23.0},
            {"Player": "Prospect", "Year": 2028, "AB": 20.0, "Age": 24.0},
            {"Player": "Steady", "Year": 2026, "AB": 30.0, "Age": 21.0},
            {"Player": "Steady", "Year": 2027, "AB": 30.0, "Age": 22.0},
        ]
    )
    pit = pd.DataFrame(columns=["Player", "Year", "IP", "Age"])

    inferred = minor_eligibility._infer_minor_eligibility_by_year(
        bat,
        pit,
        years=[2026, 2027, 2028],
        hitter_usage_max=130,
        pitcher_usage_max=50,
        hitter_age_max=25,
        pitcher_age_max=26,
    )

    by_key = {(row.Player, int(row.Year)): bool(row.minor_eligible) for row in inferred.itertuples(index=False)}
    assert by_key[("Prospect", 2026)] is True
    assert by_key[("Prospect", 2027)] is False
    assert by_key[("Prospect", 2028)] is False
    assert by_key[("Steady", 2026)] is True
    assert by_key[("Steady", 2027)] is True


def test_minor_eligibility_by_year_from_input_normalizes_and_prefers_true() -> None:
    bat = pd.DataFrame(
        [
            {"Player": "A", "Year": 2026, "Minor Eligible": "yes"},
            {"Player": "B", "Year": 2026, "Minor Eligible": "0"},
            {"Player": "C", "Year": 2026, "Minor Eligible": None},
        ]
    )
    pit = pd.DataFrame(
        [
            {"Player": "B", "Year": 2026, "Minor Eligible": 1},
            {"Player": "D", "Year": 2027, "Minor Eligible": "n"},
        ]
    )

    resolved = minor_eligibility.minor_eligibility_by_year_from_input(bat, pit)
    assert resolved is not None

    by_key = {(row.Player, int(row.Year)): bool(row.minor_eligible) for row in resolved.itertuples(index=False)}
    assert by_key[("A", 2026)] is True
    assert by_key[("B", 2026)] is True
    assert by_key[("D", 2027)] is False
    assert ("C", 2026) not in by_key


def test_resolve_minor_eligibility_by_year_prefers_explicit_flags_over_inference() -> None:
    bat = pd.DataFrame(
        [
            {"Player": "Prospect", "Year": 2026, "AB": 60.0, "Age": 22.0},
            {"Player": "Prospect", "Year": 2027, "AB": 80.0, "Age": 23.0},
        ]
    )
    pit = pd.DataFrame(
        [
            {"Player": "Prospect", "Year": 2026, "IP": 0.0, "Age": 22.0, "Minor Eligible": 0},
            {"Player": "Prospect", "Year": 2027, "IP": 0.0, "Age": 23.0, "Minor Eligible": 1},
        ]
    )

    resolved = minor_eligibility._resolve_minor_eligibility_by_year(
        bat,
        pit,
        years=[2026, 2027],
        hitter_usage_max=130,
        pitcher_usage_max=50,
        hitter_age_max=25,
        pitcher_age_max=26,
    )

    by_key = {(row.Player, int(row.Year)): bool(row.minor_eligible) for row in resolved.itertuples(index=False)}
    assert by_key[("Prospect", 2026)] is False
    assert by_key[("Prospect", 2027)] is True


def test_build_bench_stash_penalty_map_groups_players_into_team_rounds() -> None:
    stash_sorted = pd.DataFrame(
        [
            {"Player": "A", "StashScore": 10.0},
            {"Player": "B", "StashScore": 9.0},
            {"Player": "C", "StashScore": 8.0},
            {"Player": "D", "StashScore": 7.0},
            {"Player": "E", "StashScore": 6.0},
        ]
    )

    penalties = minor_eligibility._build_bench_stash_penalty_map(
        stash_sorted,
        bench_stash_players={"A", "B", "C", "D", "E"},
        n_teams=2,
        bench_slots=2,
    )

    assert penalties["A"] == penalties["B"]
    assert penalties["C"] == penalties["D"]
    assert penalties["A"] < penalties["C"]
    assert penalties["E"] == 1.0


def test_apply_negative_value_stash_rules_respects_minor_ir_and_bench_paths() -> None:
    assert minor_eligibility._apply_negative_value_stash_rules(
        -4.0,
        can_minor_stash=True,
        can_ir_stash=True,
        ir_negative_penalty=0.1,
        can_bench_stash=True,
        bench_negative_penalty=0.2,
    ) == 0.0

    assert minor_eligibility._apply_negative_value_stash_rules(
        -4.0,
        can_minor_stash=False,
        can_ir_stash=True,
        ir_negative_penalty=0.25,
        can_bench_stash=True,
        bench_negative_penalty=0.5,
    ) == -1.0

    assert minor_eligibility._apply_negative_value_stash_rules(
        -4.0,
        can_minor_stash=False,
        can_ir_stash=False,
        ir_negative_penalty=0.25,
        can_bench_stash=True,
        bench_negative_penalty=0.25,
    ) == -1.0

    assert minor_eligibility._apply_negative_value_stash_rules(
        -4.0,
        can_minor_stash=False,
        can_ir_stash=False,
        ir_negative_penalty=0.25,
        can_bench_stash=True,
        bench_negative_penalty=2.0,
    ) == -4.0
