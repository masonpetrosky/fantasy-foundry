"""Week-over-week projection change tracking.

Computes per-player deltas between current and previous projection snapshots.
Used to power the "Risers & Fallers" / movers feature.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Stats to compare for hitters (career-total sums across all projection years)
_HITTER_DELTA_STATS = ("HR", "R", "RBI", "SB", "AVG", "OPS")
# Stats to compare for pitchers
_PITCHER_DELTA_STATS = ("K", "W", "SV", "ERA", "WHIP")
# Rate stats — averaged across years rather than summed
_RATE_STATS = frozenset({"AVG", "OPS", "ERA", "WHIP"})

# How many top risers/fallers to return
DEFAULT_MOVERS_COUNT = 20


def _aggregate_player_stats(
    rows: list[dict[str, Any]], *, stat_cols: tuple[str, ...], player_type: str
) -> dict[str, dict[str, Any]]:
    """Aggregate stats per player entity key across all projection years.

    For counting stats: sum across years.
    For rate stats: weighted average (by AB for hitters, IP for pitchers).
    """
    accumulator: dict[str, dict[str, Any]] = {}
    weight_key = "AB" if player_type == "H" else "IP"

    for row in rows:
        key = str(row.get("PlayerEntityKey", "")).strip()
        if not key:
            continue
        if key not in accumulator:
            accumulator[key] = {s: 0.0 for s in stat_cols}
            accumulator[key]["_weight"] = 0.0
            accumulator[key]["_name"] = ""
            accumulator[key]["_team"] = ""
            accumulator[key]["_pos"] = ""

        weight = float(row.get(weight_key, 0) or 0)
        accumulator[key]["_weight"] += weight
        if not accumulator[key]["_name"]:
            accumulator[key]["_name"] = row.get("Player", "")
            accumulator[key]["_team"] = row.get("Team", "")
            accumulator[key]["_pos"] = row.get("Pos", "")

        for stat in stat_cols:
            val = float(row.get(stat, 0) or 0)
            if stat in _RATE_STATS:
                accumulator[key][stat] += val * weight
            else:
                accumulator[key][stat] += val

    # Finalize rate stats
    result: dict[str, dict[str, Any]] = {}
    for key, stats in accumulator.items():
        total_weight = float(stats.pop("_weight"))
        name = stats.pop("_name")
        team = stats.pop("_team")
        pos = stats.pop("_pos")
        finalized: dict[str, Any] = {"_name": name, "_team": team, "_pos": pos}
        for stat in stat_cols:
            if stat in _RATE_STATS and total_weight > 0:
                finalized[stat] = round(stats[stat] / total_weight, 3)
            else:
                finalized[stat] = round(stats[stat], 1)
        result[key] = finalized

    return result


def _compute_composite_delta(
    current_stats: dict[str, float],
    previous_stats: dict[str, float],
    stat_cols: tuple[str, ...],
) -> float:
    """Compute a single composite delta score for ranking movers.

    Uses z-score-like approach: each stat's absolute change is divided by a
    rough scale factor to make stats comparable, then summed.  Reversed stats
    (ERA, WHIP) flip sign so lower = better.
    """
    _SCALE: dict[str, float] = {
        "HR": 30.0, "R": 60.0, "RBI": 60.0, "SB": 15.0, "AVG": 0.020,
        "OPS": 0.040, "K": 120.0, "W": 8.0, "SV": 20.0, "ERA": 0.30, "WHIP": 0.05,
    }
    _REVERSED = frozenset({"ERA", "WHIP"})

    score = 0.0
    for stat in stat_cols:
        curr = current_stats.get(stat, 0.0)
        prev = previous_stats.get(stat, 0.0)
        delta = curr - prev
        scale = _SCALE.get(stat, 1.0)
        if scale > 0:
            normalized = delta / scale
        else:
            normalized = delta
        if stat in _REVERSED:
            normalized = -normalized
        score += normalized
    return round(score, 3)


def compute_projection_delta_detail_map(
    current_bat: list[dict[str, Any]],
    current_pit: list[dict[str, Any]],
    prev_bat: list[dict[str, Any]],
    prev_pit: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Compute per-player projection deltas with stat-level detail.

    This is the internal richer representation used by divergence-review and
    audit tooling. The public delta endpoint still trims the response down to
    the compact movers payload returned by ``compute_projection_deltas``.
    """
    curr_hit_agg = _aggregate_player_stats(current_bat, stat_cols=_HITTER_DELTA_STATS, player_type="H")
    prev_hit_agg = _aggregate_player_stats(prev_bat, stat_cols=_HITTER_DELTA_STATS, player_type="H")
    curr_pit_agg = _aggregate_player_stats(current_pit, stat_cols=_PITCHER_DELTA_STATS, player_type="P")
    prev_pit_agg = _aggregate_player_stats(prev_pit, stat_cols=_PITCHER_DELTA_STATS, player_type="P")

    detail_map: dict[str, dict[str, Any]] = {}

    for key in curr_hit_agg:
        if key not in prev_hit_agg:
            continue
        stat_deltas = {
            stat: round(curr_hit_agg[key].get(stat, 0) - prev_hit_agg[key].get(stat, 0), 3)
            for stat in _HITTER_DELTA_STATS
        }
        composite = _compute_composite_delta(curr_hit_agg[key], prev_hit_agg[key], _HITTER_DELTA_STATS)
        detail_map[key] = {
            "player": curr_hit_agg[key]["_name"],
            "team": curr_hit_agg[key]["_team"],
            "pos": curr_hit_agg[key]["_pos"],
            "type": "H",
            "deltas": stat_deltas,
            "composite_delta": composite,
        }

    for key in curr_pit_agg:
        if key not in prev_pit_agg:
            continue
        stat_deltas = {
            stat: round(curr_pit_agg[key].get(stat, 0) - prev_pit_agg[key].get(stat, 0), 3)
            for stat in _PITCHER_DELTA_STATS
        }
        composite = _compute_composite_delta(curr_pit_agg[key], prev_pit_agg[key], _PITCHER_DELTA_STATS)
        if key in detail_map:
            detail_map[key]["deltas"].update(stat_deltas)
            detail_map[key]["composite_delta"] = round(detail_map[key]["composite_delta"] + composite, 3)
        else:
            detail_map[key] = {
                "player": curr_pit_agg[key]["_name"],
                "team": curr_pit_agg[key]["_team"],
                "pos": curr_pit_agg[key]["_pos"],
                "type": "P",
                "deltas": stat_deltas,
                "composite_delta": composite,
            }

    return detail_map


def compute_projection_deltas(
    current_bat: list[dict[str, Any]],
    current_pit: list[dict[str, Any]],
    prev_bat: list[dict[str, Any]],
    prev_pit: list[dict[str, Any]],
    *,
    movers_count: int = DEFAULT_MOVERS_COUNT,
) -> dict[str, Any]:
    """Compute projection deltas between current and previous snapshots.

    Returns:
        {
            "risers": [...top N players with biggest positive composite delta],
            "fallers": [...top N players with biggest negative composite delta],
            "delta_map": {player_entity_key: {composite_delta}},
            "has_previous": True
        }
    """
    delta_map = compute_projection_delta_detail_map(
        current_bat=current_bat,
        current_pit=current_pit,
        prev_bat=prev_bat,
        prev_pit=prev_pit,
    )

    # Sort for risers/fallers
    all_entries = sorted(delta_map.items(), key=lambda kv: kv[1]["composite_delta"], reverse=True)
    risers = [
        {"key": k, **v}
        for k, v in all_entries[:movers_count]
        if v["composite_delta"] > 0
    ]
    fallers = [
        {"key": k, **v}
        for k, v in reversed(all_entries[-movers_count:])
        if v["composite_delta"] < 0
    ]
    # Sort fallers by most negative first
    fallers.sort(key=lambda x: x["composite_delta"])

    return {
        "risers": risers,
        "fallers": fallers,
        "delta_map": {
            k: {"composite_delta": v["composite_delta"]}
            for k, v in delta_map.items()
        },
        "has_previous": True,
    }


def load_previous_data(data_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """Load previous projection snapshots if available."""
    bat_prev = data_dir / "bat_prev.json"
    pit_prev = data_dir / "pit_prev.json"
    if not bat_prev.exists() or not pit_prev.exists():
        return None
    try:
        with bat_prev.open(encoding="utf-8") as f:
            prev_bat = json.load(f)
        with pit_prev.open(encoding="utf-8") as f:
            prev_pit = json.load(f)
        return prev_bat, prev_pit
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to load previous projection data", exc_info=True)
        return None


def empty_delta_response() -> dict[str, Any]:
    """Return an empty delta response when no previous data is available."""
    return {
        "risers": [],
        "fallers": [],
        "delta_map": {},
        "has_previous": False,
    }
