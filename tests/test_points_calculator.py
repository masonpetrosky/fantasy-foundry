from backend.core.points_calculator import (
    dynasty_keep_or_drop_values,
    optimize_points_slot_assignment,
)


def test_optimize_points_slot_assignment_respects_slot_capacity() -> None:
    entries = [
        {"player_id": "alpha", "points": 40.0, "slots": {"OF"}},
        {"player_id": "beta", "points": 30.0, "slots": {"OF"}},
    ]
    assigned = optimize_points_slot_assignment(
        entries,
        replacement_by_slot={"OF": 0.0},
        slot_capacity={"OF": 1},
    )

    assert set(assigned.keys()) == {"alpha"}
    assert assigned["alpha"]["slot"] == "OF"
    assert float(assigned["alpha"]["value"]) == 40.0


def test_optimize_points_slot_assignment_skips_non_positive_surplus() -> None:
    entries = [
        {"player_id": "alpha", "points": 5.0, "slots": {"OF"}},
        {"player_id": "beta", "points": 3.0, "slots": {"OF"}},
    ]
    assigned = optimize_points_slot_assignment(
        entries,
        replacement_by_slot={"OF": 6.0},
        slot_capacity={"OF": 1},
    )

    assert assigned == {}


def test_dynasty_keep_or_drop_values_drops_negative_continuation() -> None:
    result = dynasty_keep_or_drop_values(
        [5.0, -10.0, 1.0],
        [2026, 2027, 2028],
        discount=1.0,
    )

    assert result.keep_flags == [True, False, True]
    assert result.continuation_values == [5.0, 0.0, 1.0]
    assert result.discounted_contributions == [5.0, 0.0, 0.0]
    assert result.raw_total == 5.0


def test_dynasty_keep_or_drop_values_respects_year_gaps() -> None:
    result = dynasty_keep_or_drop_values(
        [2.0, 3.0],
        [2026, 2028],
        discount=0.9,
    )

    assert result.keep_flags == [True, True]
    assert abs(result.raw_total - 4.43) < 1e-9
    assert abs(result.discount_factors[1] - 0.81) < 1e-9
    assert abs(result.discounted_contributions[1] - 2.43) < 1e-9
