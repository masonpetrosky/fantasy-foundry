"""Shared dynasty aggregation utilities."""

from __future__ import annotations


def dynasty_keep_or_drop_value(values: list[float], years: list[int], discount: float) -> float:
    """Compute the optimal discounted value of owning a player with a drop option."""
    if not years or not values:
        return 0.0
    if len(values) != len(years):
        raise ValueError("values and years must have the same length")
    if len(years) == 1:
        return float(max(values[0], 0.0))

    f_next = 0.0
    for i in range(len(years) - 1, -1, -1):
        value = float(values[i])
        if i == len(years) - 1:
            hold = value
        else:
            gap = int(years[i + 1]) - int(years[i])
            if gap < 0:
                raise ValueError("years must be increasing")
            hold = value + (discount**gap) * f_next
        f_next = max(0.0, hold)

    return float(f_next)


__all__ = ["dynasty_keep_or_drop_value"]
