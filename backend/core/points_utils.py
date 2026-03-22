"""Shared stat, identity, and scoring helpers for points-mode valuation."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd


def stat_or_zero(row: dict | None, key: str, *, as_float_fn: Callable[[object], float | None]) -> float:
    if not row:
        return 0.0
    value = as_float_fn(row.get(key))
    return value if value is not None else 0.0


def coerce_minor_eligible(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value > 0
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def projection_identity_key(
    row: dict | pd.Series,
    *,
    player_entity_key_col: str,
    player_key_col: str,
    normalize_player_key_fn: Callable[[object], str],
) -> str:
    entity_key = str(row.get(player_entity_key_col) or "").strip()
    if entity_key:
        return entity_key
    player_key = str(row.get(player_key_col) or "").strip()
    if player_key:
        return player_key
    return normalize_player_key_fn(row.get("Player"))


def valuation_years(start_year: int, horizon: int, valid_years: list[int]) -> list[int]:
    max_year = int(start_year) + max(int(horizon), 1) - 1
    years = [year for year in valid_years if start_year <= year <= max_year]
    if years:
        return years
    return [start_year + offset for offset in range(max(int(horizon), 1))]


def calculate_hitter_points_breakdown(
    row: dict | None,
    scoring: dict[str, float],
    *,
    stat_or_zero_fn: Callable[[dict | None, str], float],
) -> dict:
    hits = stat_or_zero_fn(row, "H")
    doubles = stat_or_zero_fn(row, "2B")
    triples = stat_or_zero_fn(row, "3B")
    hr = stat_or_zero_fn(row, "HR")
    singles = max(0.0, hits - doubles - triples - hr)
    inputs = {
        "1B": singles,
        "2B": doubles,
        "3B": triples,
        "HR": hr,
        "R": stat_or_zero_fn(row, "R"),
        "RBI": stat_or_zero_fn(row, "RBI"),
        "SB": stat_or_zero_fn(row, "SB"),
        "BB": stat_or_zero_fn(row, "BB"),
        "HBP": stat_or_zero_fn(row, "HBP"),
        "SO": stat_or_zero_fn(row, "SO"),
    }
    rule_points = {
        "1B": inputs["1B"] * scoring["pts_hit_1b"],
        "2B": inputs["2B"] * scoring["pts_hit_2b"],
        "3B": inputs["3B"] * scoring["pts_hit_3b"],
        "HR": inputs["HR"] * scoring["pts_hit_hr"],
        "R": inputs["R"] * scoring["pts_hit_r"],
        "RBI": inputs["RBI"] * scoring["pts_hit_rbi"],
        "SB": inputs["SB"] * scoring["pts_hit_sb"],
        "BB": inputs["BB"] * scoring["pts_hit_bb"],
        "HBP": inputs["HBP"] * scoring["pts_hit_hbp"],
        "SO": inputs["SO"] * scoring["pts_hit_so"],
    }
    total_points = float(sum(rule_points.values()))
    return {
        "stats": {key: round(float(value), 4) for key, value in inputs.items()},
        "rule_points": {key: round(float(value), 4) for key, value in rule_points.items()},
        "total_points": round(total_points, 4),
    }


def calculate_pitcher_points_breakdown(
    row: dict | None,
    scoring: dict[str, float],
    *,
    stat_or_zero_fn: Callable[[dict | None, str], float],
) -> dict:
    inputs = {
        "IP": stat_or_zero_fn(row, "IP"),
        "W": stat_or_zero_fn(row, "W"),
        "L": stat_or_zero_fn(row, "L"),
        "K": stat_or_zero_fn(row, "K"),
        "SV": stat_or_zero_fn(row, "SV"),
        "HLD": stat_or_zero_fn(row, "HLD"),
        "H": stat_or_zero_fn(row, "H"),
        "ER": stat_or_zero_fn(row, "ER"),
        "BB": stat_or_zero_fn(row, "BB"),
        "HBP": stat_or_zero_fn(row, "HBP"),
    }
    rule_points = {
        "IP": inputs["IP"] * scoring["pts_pit_ip"],
        "W": inputs["W"] * scoring["pts_pit_w"],
        "L": inputs["L"] * scoring["pts_pit_l"],
        "K": inputs["K"] * scoring["pts_pit_k"],
        "SV": inputs["SV"] * scoring["pts_pit_sv"],
        "HLD": inputs["HLD"] * scoring["pts_pit_hld"],
        "H": inputs["H"] * scoring["pts_pit_h"],
        "ER": inputs["ER"] * scoring["pts_pit_er"],
        "BB": inputs["BB"] * scoring["pts_pit_bb"],
        "HBP": inputs["HBP"] * scoring["pts_pit_hbp"],
    }
    total_points = float(sum(rule_points.values()))
    return {
        "stats": {key: round(float(value), 4) for key, value in inputs.items()},
        "rule_points": {key: round(float(value), 4) for key, value in rule_points.items()},
        "total_points": round(total_points, 4),
    }


def _scale_points_breakdown(breakdown: dict, share: float) -> dict:
    scaled_share = min(max(float(share), 0.0), 1.0)
    raw_stats = breakdown.get("stats")
    stats = raw_stats if isinstance(raw_stats, dict) else {}
    raw_rule_points = breakdown.get("rule_points")
    rule_points = raw_rule_points if isinstance(raw_rule_points, dict) else {}
    return {
        "stats": {str(key): round(float(value) * scaled_share, 4) for key, value in stats.items()},
        "rule_points": {str(key): round(float(value) * scaled_share, 4) for key, value in rule_points.items()},
        "total_points": round(float(breakdown.get("total_points", 0.0)) * scaled_share, 4),
    }


def points_player_identity(
    row: dict,
    *,
    player_entity_key_col: str,
    player_key_col: str,
    normalize_player_key_fn: Callable[[object], str],
) -> str:
    return projection_identity_key(
        row,
        player_entity_key_col=player_entity_key_col,
        player_key_col=player_key_col,
        normalize_player_key_fn=normalize_player_key_fn,
    )


def points_hitter_eligible_slots(
    pos_value: object,
    *,
    position_tokens_fn: Callable[[object], set[str]],
) -> set[str]:
    tokens = position_tokens_fn(pos_value)
    if not tokens:
        return set()

    aliases = {
        "LF": "OF",
        "CF": "OF",
        "RF": "OF",
        "UTIL": "UT",
        "U": "UT",
    }
    normalized = {aliases.get(token, token) for token in tokens}

    slots: set[str] = {"UT"}
    if "C" in normalized:
        slots.add("C")
    if "1B" in normalized:
        slots.update({"1B", "CI"})
    if "3B" in normalized:
        slots.update({"3B", "CI"})
    if "2B" in normalized:
        slots.update({"2B", "MI"})
    if "SS" in normalized:
        slots.update({"SS", "MI"})
    if "OF" in normalized:
        slots.add("OF")
    if "DH" in normalized:
        slots.add("DH")
    if "CI" in normalized:
        slots.add("CI")
    if "MI" in normalized:
        slots.add("MI")
    return slots


def points_pitcher_eligible_slots(
    pos_value: object,
    *,
    position_tokens_fn: Callable[[object], set[str]],
) -> set[str]:
    tokens = position_tokens_fn(pos_value)
    if not tokens:
        return set()

    aliases = {
        "RHP": "SP",
        "LHP": "SP",
    }
    normalized = {aliases.get(token, token) for token in tokens}

    slots: set[str] = {"P"}
    if "SP" in normalized:
        slots.add("SP")
    if "RP" in normalized:
        slots.add("RP")
    return slots


def points_slot_replacement(
    entries: list[dict[str, object]],
    *,
    active_slots: set[str],
    rostered_player_ids: set[str],
    n_replacement: int,
    as_float_fn: Callable[[object], float | None],
) -> dict[str, float]:
    baselines: dict[str, float] = {}
    top_n = max(int(n_replacement), 1)

    for slot in sorted(active_slots):
        candidate_points: list[float] = []
        for entry in entries:
            player_id = str(entry.get("player_id") or "")
            if not player_id or player_id in rostered_player_ids:
                continue
            slots = entry.get("slots")
            if not isinstance(slots, set) or slot not in slots:
                continue
            points = as_float_fn(entry.get("points"))
            if points is None:
                continue
            candidate_points.append(points)

        if not candidate_points:
            baselines[slot] = 0.0
            continue

        candidate_points.sort(reverse=True)
        selected = candidate_points[:top_n]
        baselines[slot] = float(sum(selected) / len(selected))

    return baselines
