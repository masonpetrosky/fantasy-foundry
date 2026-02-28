"""Points-mode dynasty calculation helpers and orchestration."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(slots=True)
class PointsCalculatorContext:
    bat_data: list[dict]
    pit_data: list[dict]
    bat_data_raw: list[dict]
    pit_data_raw: list[dict]
    meta: dict
    average_recent_projection_rows: Callable[..., list[dict]]
    coerce_meta_years: Callable[[dict], list[int]]
    valuation_years: Callable[[int, int, list[int]], list[int]]
    coerce_record_year: Callable[[object], int | None]
    points_player_identity: Callable[[dict], str]
    normalize_player_key: Callable[[object], str]
    player_key_col: str
    player_entity_key_col: str
    row_team_value: Callable[[dict], str]
    merge_position_value: Callable[[object, object], str | None]
    coerce_minor_eligible: Callable[[object], bool]
    calculate_hitter_points_breakdown: Callable[[dict | None, dict[str, float]], dict]
    calculate_pitcher_points_breakdown: Callable[[dict | None, dict[str, float]], dict]
    stat_or_zero: Callable[[dict | None, str], float]
    points_hitter_eligible_slots: Callable[[object], set[str]]
    points_pitcher_eligible_slots: Callable[[object], set[str]]
    points_slot_replacement: Callable[..., dict[str, float]]


@dataclass(slots=True)
class KeepDropResult:
    raw_total: float
    continuation_values: list[float]
    hold_values: list[float]
    keep_flags: list[bool]
    discount_factors: list[float]
    discounted_contributions: list[float]


@dataclass(slots=True)
class _FlowEdge:
    to: int
    rev: int
    capacity: int
    cost: int


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
        "SVH": stat_or_zero_fn(row, "SVH"),
        "H": stat_or_zero_fn(row, "H"),
        "ER": stat_or_zero_fn(row, "ER"),
        "BB": stat_or_zero_fn(row, "BB"),
    }
    rule_points = {
        "IP": inputs["IP"] * scoring["pts_pit_ip"],
        "W": inputs["W"] * scoring["pts_pit_w"],
        "L": inputs["L"] * scoring["pts_pit_l"],
        "K": inputs["K"] * scoring["pts_pit_k"],
        "SV": inputs["SV"] * scoring["pts_pit_sv"],
        "SVH": inputs["SVH"] * scoring["pts_pit_svh"],
        "H": inputs["H"] * scoring["pts_pit_h"],
        "ER": inputs["ER"] * scoring["pts_pit_er"],
        "BB": inputs["BB"] * scoring["pts_pit_bb"],
    }
    total_points = float(sum(rule_points.values()))
    return {
        "stats": {key: round(float(value), 4) for key, value in inputs.items()},
        "rule_points": {key: round(float(value), 4) for key, value in rule_points.items()},
        "total_points": round(total_points, 4),
    }


def points_player_identity(
    row: dict,
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
        "DH": "UT",
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


def _best_slot_surplus(
    *,
    points: float,
    eligible_slots: set[str],
    replacement_by_slot: dict[str, float],
) -> tuple[float | None, str | None, float | None]:
    best_value: float | None = None
    best_slot: str | None = None
    best_replacement: float | None = None
    for slot in sorted(eligible_slots):
        replacement_points = float(replacement_by_slot.get(slot, 0.0))
        value = float(points - replacement_points)
        if best_value is None or value > best_value:
            best_value = value
            best_slot = slot
            best_replacement = replacement_points
    return best_value, best_slot, best_replacement


def _slot_capacity_by_league(slot_counts: dict[str, int], *, teams: int) -> dict[str, int]:
    league_teams = max(int(teams), 1)
    return {
        slot: league_teams * max(int(count), 0)
        for slot, count in sorted(slot_counts.items())
        if int(count) > 0
    }


def optimize_points_slot_assignment(
    entries: list[dict[str, object]],
    *,
    replacement_by_slot: dict[str, float],
    slot_capacity: dict[str, int],
) -> dict[str, dict[str, float | str]]:
    normalized_slot_capacity = {
        str(slot): max(int(capacity), 0)
        for slot, capacity in slot_capacity.items()
        if int(capacity) > 0
    }
    if not normalized_slot_capacity:
        return {}

    player_rows: dict[str, dict[str, object]] = {}
    for entry in entries:
        player_id = str(entry.get("player_id") or "").strip()
        if not player_id:
            continue
        try:
            points = float(entry.get("points") or 0.0)
        except (TypeError, ValueError):
            continue
        raw_slots = entry.get("slots")
        if isinstance(raw_slots, set):
            slots = {str(slot) for slot in raw_slots}
        elif isinstance(raw_slots, (list, tuple)):
            slots = {str(slot) for slot in raw_slots}
        else:
            continue
        eligible_slots = {
            slot
            for slot in slots
            if slot in normalized_slot_capacity and normalized_slot_capacity[slot] > 0
        }
        if not eligible_slots:
            continue

        existing = player_rows.get(player_id)
        if existing is None or float(existing.get("points") or 0.0) < points:
            player_rows[player_id] = {"points": points, "slots": eligible_slots}

    if not player_rows:
        return {}

    player_ids = sorted(player_rows.keys())
    slot_names = sorted(normalized_slot_capacity.keys())
    source = 0
    first_player_node = 1
    first_slot_node = first_player_node + len(player_ids)
    sink = first_slot_node + len(slot_names)
    node_count = sink + 1
    graph: list[list[_FlowEdge]] = [[] for _ in range(node_count)]

    def add_edge(from_node: int, to_node: int, capacity: int, cost: int) -> None:
        forward = _FlowEdge(to=to_node, rev=len(graph[to_node]), capacity=capacity, cost=cost)
        backward = _FlowEdge(to=from_node, rev=len(graph[from_node]), capacity=0, cost=-cost)
        graph[from_node].append(forward)
        graph[to_node].append(backward)

    slot_node_by_name = {
        slot: first_slot_node + idx
        for idx, slot in enumerate(slot_names)
    }
    player_node_by_id = {
        player_id: first_player_node + idx
        for idx, player_id in enumerate(player_ids)
    }

    for slot in slot_names:
        add_edge(slot_node_by_name[slot], sink, normalized_slot_capacity[slot], 0)
    for player_id in player_ids:
        player_node = player_node_by_id[player_id]
        add_edge(source, player_node, 1, 0)

    player_edges: dict[str, list[tuple[str, int, int]]] = {}
    scale = 1000.0

    for player_id in player_ids:
        player_node = player_node_by_id[player_id]
        row = player_rows[player_id]
        points = float(row["points"])
        slots = set(row["slots"]) if isinstance(row["slots"], set) else set()
        for slot in sorted(slots):
            replacement_points = float(replacement_by_slot.get(slot, 0.0))
            surplus = points - replacement_points
            if surplus <= 1e-9:
                continue
            scaled_surplus = int(round(surplus * scale))
            if scaled_surplus <= 0:
                continue
            edge_idx = len(graph[player_node])
            add_edge(player_node, slot_node_by_name[slot], 1, -scaled_surplus)
            player_edges.setdefault(player_id, []).append((slot, edge_idx, player_node))

    if not player_edges:
        return {}

    inf = 10**18
    potentials = [0] * node_count

    while True:
        dist = [inf] * node_count
        parent_node = [-1] * node_count
        parent_edge_idx = [-1] * node_count
        dist[source] = 0
        pq: list[tuple[int, int]] = [(0, source)]

        while pq:
            cur_dist, node = heapq.heappop(pq)
            if cur_dist != dist[node]:
                continue
            for edge_idx, edge in enumerate(graph[node]):
                if edge.capacity <= 0:
                    continue
                next_node = edge.to
                next_dist = cur_dist + edge.cost + potentials[node] - potentials[next_node]
                if next_dist < dist[next_node]:
                    dist[next_node] = next_dist
                    parent_node[next_node] = node
                    parent_edge_idx[next_node] = edge_idx
                    heapq.heappush(pq, (next_dist, next_node))

        if dist[sink] == inf:
            break

        path_cost = dist[sink] + potentials[sink] - potentials[source]
        if path_cost >= 0:
            break

        for node_idx, node_dist in enumerate(dist):
            if node_dist < inf:
                potentials[node_idx] += node_dist

        cursor = sink
        while cursor != source:
            prev = parent_node[cursor]
            if prev < 0:
                break
            edge_idx = parent_edge_idx[cursor]
            edge = graph[prev][edge_idx]
            edge.capacity -= 1
            reverse = graph[cursor][edge.rev]
            reverse.capacity += 1
            cursor = prev

    assignments: dict[str, dict[str, float | str]] = {}
    for player_id in player_ids:
        edges = player_edges.get(player_id, [])
        if not edges:
            continue
        points = float(player_rows[player_id]["points"])
        for slot, edge_idx, player_node in edges:
            edge = graph[player_node][edge_idx]
            if edge.capacity != 0:
                continue
            replacement_points = float(replacement_by_slot.get(slot, 0.0))
            assignments[player_id] = {
                "slot": slot,
                "points": points,
                "replacement": replacement_points,
                "value": points - replacement_points,
            }
            break

    return assignments


def dynasty_keep_or_drop_values(values: list[float], years: list[int], *, discount: float) -> KeepDropResult:
    if len(values) != len(years):
        raise ValueError("values and years must have the same length.")
    if not values:
        return KeepDropResult(
            raw_total=0.0,
            continuation_values=[],
            hold_values=[],
            keep_flags=[],
            discount_factors=[],
            discounted_contributions=[],
        )

    annual_discount = float(discount)
    count = len(values)
    continuation_values = [0.0] * count
    hold_values = [0.0] * count
    keep_flags = [False] * count

    for idx in range(count - 1, -1, -1):
        future = 0.0
        if idx < count - 1:
            gap = max(1, int(years[idx + 1]) - int(years[idx]))
            future = (annual_discount ** gap) * continuation_values[idx + 1]
        candidate = float(values[idx]) + future
        hold_values[idx] = float(candidate)
        if candidate > 0:
            continuation_values[idx] = float(candidate)
            keep_flags[idx] = True

    discount_factors = [1.0] * count
    for idx in range(1, count):
        gap = max(1, int(years[idx]) - int(years[idx - 1]))
        discount_factors[idx] = discount_factors[idx - 1] * (annual_discount ** gap)

    discounted_contributions = [0.0] * count
    active = bool(keep_flags[0])
    if active:
        discounted_contributions[0] = float(values[0]) * discount_factors[0]
    for idx in range(1, count):
        if not active:
            break
        if keep_flags[idx]:
            discounted_contributions[idx] = float(values[idx]) * discount_factors[idx]
        else:
            active = False

    raw_total = float(continuation_values[0]) if keep_flags[0] else 0.0
    return KeepDropResult(
        raw_total=raw_total,
        continuation_values=continuation_values,
        hold_values=hold_values,
        keep_flags=keep_flags,
        discount_factors=discount_factors,
        discounted_contributions=discounted_contributions,
    )


def calculate_points_dynasty_frame(
    *,
    ctx: PointsCalculatorContext,
    teams: int,
    horizon: int,
    discount: float,
    hit_c: int,
    hit_1b: int,
    hit_2b: int,
    hit_3b: int,
    hit_ss: int,
    hit_ci: int,
    hit_mi: int,
    hit_of: int,
    hit_ut: int,
    pit_p: int,
    pit_sp: int,
    pit_rp: int,
    bench: int,
    minors: int,
    ir: int,
    two_way: str,
    start_year: int,
    pts_hit_1b: float,
    pts_hit_2b: float,
    pts_hit_3b: float,
    pts_hit_hr: float,
    pts_hit_r: float,
    pts_hit_rbi: float,
    pts_hit_sb: float,
    pts_hit_bb: float,
    pts_hit_so: float,
    pts_pit_ip: float,
    pts_pit_w: float,
    pts_pit_l: float,
    pts_pit_k: float,
    pts_pit_sv: float,
    pts_pit_svh: float,
    pts_pit_h: float,
    pts_pit_er: float,
    pts_pit_bb: float,
) -> pd.DataFrame:
    scoring = {
        "pts_hit_1b": float(pts_hit_1b),
        "pts_hit_2b": float(pts_hit_2b),
        "pts_hit_3b": float(pts_hit_3b),
        "pts_hit_hr": float(pts_hit_hr),
        "pts_hit_r": float(pts_hit_r),
        "pts_hit_rbi": float(pts_hit_rbi),
        "pts_hit_sb": float(pts_hit_sb),
        "pts_hit_bb": float(pts_hit_bb),
        "pts_hit_so": float(pts_hit_so),
        "pts_pit_ip": float(pts_pit_ip),
        "pts_pit_w": float(pts_pit_w),
        "pts_pit_l": float(pts_pit_l),
        "pts_pit_k": float(pts_pit_k),
        "pts_pit_sv": float(pts_pit_sv),
        "pts_pit_svh": float(pts_pit_svh),
        "pts_pit_h": float(pts_pit_h),
        "pts_pit_er": float(pts_pit_er),
        "pts_pit_bb": float(pts_pit_bb),
    }

    bat_rows = ctx.bat_data
    pit_rows = ctx.pit_data

    valid_years = ctx.coerce_meta_years(ctx.meta)
    valuation_year_set = ctx.valuation_years(start_year, horizon, valid_years)
    year_set = set(valuation_year_set)

    if not valuation_year_set:
        raise ValueError("No valuation years available for selected start_year and horizon.")

    rows_by_player: dict[str, dict[int, dict[str, dict | None]]] = {}

    for row in bat_rows:
        year = ctx.coerce_record_year(row.get("Year"))
        if year is None or year not in year_set:
            continue
        player_id = ctx.points_player_identity(row)
        bucket = rows_by_player.setdefault(player_id, {})
        pair = bucket.setdefault(year, {"hit": None, "pit": None})
        pair["hit"] = row

    for row in pit_rows:
        year = ctx.coerce_record_year(row.get("Year"))
        if year is None or year not in year_set:
            continue
        player_id = ctx.points_player_identity(row)
        bucket = rows_by_player.setdefault(player_id, {})
        pair = bucket.setdefault(year, {"hit": None, "pit": None})
        pair["pit"] = row

    active_slots_per_team = (
        hit_c
        + hit_1b
        + hit_2b
        + hit_3b
        + hit_ss
        + hit_ci
        + hit_mi
        + hit_of
        + hit_ut
        + pit_p
        + pit_sp
        + pit_rp
    )
    # Points mode values only active lineup slots, so centering must use the
    # same active-slot roster depth (excluding bench/minors/IL).
    replacement_rank = max(1, teams * max(1, active_slots_per_team))
    hitter_slot_counts = {
        "C": int(hit_c),
        "1B": int(hit_1b),
        "2B": int(hit_2b),
        "3B": int(hit_3b),
        "SS": int(hit_ss),
        "CI": int(hit_ci),
        "MI": int(hit_mi),
        "OF": int(hit_of),
        "UT": int(hit_ut),
    }
    pitcher_slot_counts = {
        "P": int(pit_p),
        "SP": int(pit_sp),
        "RP": int(pit_rp),
    }
    active_hitter_slots = {slot for slot, count in hitter_slot_counts.items() if count > 0}
    active_pitcher_slots = {slot for slot, count in pitcher_slot_counts.items() if count > 0}
    n_replacement = max(int(teams), 1)
    freeze_replacement_baselines = True

    player_meta: dict[str, dict[str, object]] = {}
    per_player_year: dict[str, dict[int, dict[str, object]]] = {}
    year_hit_entries: dict[int, list[dict[str, object]]] = {}
    year_pit_entries: dict[int, list[dict[str, object]]] = {}
    player_raw_totals: dict[str, float] = {}
    empty_hit_breakdown = ctx.calculate_hitter_points_breakdown(None, scoring)
    empty_pit_breakdown = ctx.calculate_pitcher_points_breakdown(None, scoring)

    for player_id, per_year in rows_by_player.items():
        if not per_year:
            continue

        start_pair = per_year.get(start_year)
        if start_pair and (start_pair.get("hit") or start_pair.get("pit")):
            meta_hit = start_pair.get("hit")
            meta_pit = start_pair.get("pit")
        else:
            first_year = min(per_year.keys())
            fallback_pair = per_year[first_year]
            meta_hit = fallback_pair.get("hit")
            meta_pit = fallback_pair.get("pit")

        meta_row = meta_hit or meta_pit or {}
        player_name = str(meta_row.get("Player") or "").strip()
        player_key = str(meta_row.get(ctx.player_key_col) or "").strip() or ctx.normalize_player_key(player_name)
        entity_key = str(meta_row.get(ctx.player_entity_key_col) or "").strip() or player_key

        player_meta[player_id] = {
            "Player": player_name,
            "Team": ctx.row_team_value(meta_hit or {}) or ctx.row_team_value(meta_pit or {}),
            "Pos": ctx.merge_position_value((meta_hit or {}).get("Pos"), (meta_pit or {}).get("Pos")),
            "Age": (meta_hit or {}).get("Age") if (meta_hit or {}).get("Age") is not None else (meta_pit or {}).get("Age"),
            "minor_eligible": ctx.coerce_minor_eligible((meta_hit or {}).get("minor_eligible"))
            or ctx.coerce_minor_eligible((meta_pit or {}).get("minor_eligible")),
            ctx.player_key_col: player_key,
            ctx.player_entity_key_col: entity_key,
        }

        year_map: dict[int, dict[str, object]] = {}
        raw_total = 0.0

        for year_offset, year in enumerate(valuation_year_set):
            pair = per_year.get(year) or {"hit": None, "pit": None}
            hit_row = pair.get("hit")
            pit_row = pair.get("pit")

            hit_breakdown = ctx.calculate_hitter_points_breakdown(hit_row, scoring)
            pit_breakdown = ctx.calculate_pitcher_points_breakdown(pit_row, scoring)
            hit_points = float(hit_breakdown["total_points"])
            pit_points = float(pit_breakdown["total_points"])

            hit_slots = set()
            if isinstance(hit_row, dict) and ctx.stat_or_zero(hit_row, "AB") > 0:
                hit_slots = ctx.points_hitter_eligible_slots(hit_row.get("Pos")) & active_hitter_slots
            pit_slots = set()
            if isinstance(pit_row, dict) and ctx.stat_or_zero(pit_row, "IP") > 0:
                pit_slots = ctx.points_pitcher_eligible_slots(pit_row.get("Pos")) & active_pitcher_slots

            if hit_slots:
                year_hit_entries.setdefault(year, []).append(
                    {"player_id": player_id, "points": hit_points, "slots": set(hit_slots)}
                )
            if pit_slots:
                year_pit_entries.setdefault(year, []).append(
                    {"player_id": player_id, "points": pit_points, "slots": set(pit_slots)}
                )

            selected_raw_points = 0.0
            if hit_slots and pit_slots:
                selected_raw_points = hit_points + pit_points if two_way == "sum" else max(hit_points, pit_points)
            elif hit_slots:
                selected_raw_points = hit_points
            elif pit_slots:
                selected_raw_points = pit_points

            raw_total += selected_raw_points * (float(discount) ** year_offset)

            year_map[year] = {
                "hit_breakdown": hit_breakdown,
                "pit_breakdown": pit_breakdown,
                "hit_points": hit_points,
                "pit_points": pit_points,
                "hit_slots": set(hit_slots),
                "pit_slots": set(pit_slots),
            }

        per_player_year[player_id] = year_map
        player_raw_totals[player_id] = float(raw_total)

    if not player_meta:
        empty_columns = [
            "Player",
            "Team",
            "Pos",
            "Age",
            "DynastyValue",
            "RawDynastyValue",
            "minor_eligible",
            ctx.player_key_col,
            ctx.player_entity_key_col,
        ] + [f"Value_{year}" for year in valuation_year_set]
        return pd.DataFrame(columns=empty_columns)

    ranked_players = sorted(
        player_raw_totals.items(),
        key=lambda item: (-float(item[1]), str(item[0])),
    )
    rostered_player_ids = {player_id for player_id, _score in ranked_players[:replacement_rank]}

    year_hit_replacement: dict[int, dict[str, float]] = {}
    year_pit_replacement: dict[int, dict[str, float]] = {}
    if freeze_replacement_baselines:
        frozen_hit = ctx.points_slot_replacement(
            year_hit_entries.get(start_year, []),
            active_slots=active_hitter_slots,
            rostered_player_ids=rostered_player_ids,
            n_replacement=n_replacement,
        )
        frozen_pit = ctx.points_slot_replacement(
            year_pit_entries.get(start_year, []),
            active_slots=active_pitcher_slots,
            rostered_player_ids=rostered_player_ids,
            n_replacement=n_replacement,
        )
        for year in valuation_year_set:
            year_hit_replacement[year] = dict(frozen_hit)
            year_pit_replacement[year] = dict(frozen_pit)
    else:
        for year in valuation_year_set:
            year_hit_replacement[year] = ctx.points_slot_replacement(
                year_hit_entries.get(year, []),
                active_slots=active_hitter_slots,
                rostered_player_ids=rostered_player_ids,
                n_replacement=n_replacement,
            )
            year_pit_replacement[year] = ctx.points_slot_replacement(
                year_pit_entries.get(year, []),
                active_slots=active_pitcher_slots,
                rostered_player_ids=rostered_player_ids,
                n_replacement=n_replacement,
            )

    hitter_slot_capacity = _slot_capacity_by_league(hitter_slot_counts, teams=teams)
    pitcher_slot_capacity = _slot_capacity_by_league(pitcher_slot_counts, teams=teams)
    year_hit_assignments = {
        year: optimize_points_slot_assignment(
            year_hit_entries.get(year, []),
            replacement_by_slot=year_hit_replacement.get(year, {}),
            slot_capacity=hitter_slot_capacity,
        )
        for year in valuation_year_set
    }
    year_pit_assignments = {
        year: optimize_points_slot_assignment(
            year_pit_entries.get(year, []),
            replacement_by_slot=year_pit_replacement.get(year, {}),
            slot_capacity=pitcher_slot_capacity,
        )
        for year in valuation_year_set
    }

    result_rows: list[dict] = []
    for player_id, meta_row in player_meta.items():
        row_out: dict[str, object] = dict(meta_row)
        row_out["_ExplainPointsByYear"] = {}
        year_details: list[dict[str, object]] = []

        for year in valuation_year_set:
            info = per_player_year.get(player_id, {}).get(year, {})
            hit_points = float(info.get("hit_points", 0.0))
            pit_points = float(info.get("pit_points", 0.0))
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))
            hit_breakdown = info.get("hit_breakdown") if isinstance(info.get("hit_breakdown"), dict) else empty_hit_breakdown
            pit_breakdown = info.get("pit_breakdown") if isinstance(info.get("pit_breakdown"), dict) else empty_pit_breakdown

            hit_repl_map = year_hit_replacement.get(year, {})
            pit_repl_map = year_pit_replacement.get(year, {})
            hit_best_value, hit_best_slot, hit_best_replacement = _best_slot_surplus(
                points=hit_points,
                eligible_slots=hit_slots,
                replacement_by_slot=hit_repl_map,
            )
            pit_best_value, pit_best_slot, pit_best_replacement = _best_slot_surplus(
                points=pit_points,
                eligible_slots=pit_slots,
                replacement_by_slot=pit_repl_map,
            )

            hit_assignment = year_hit_assignments.get(year, {}).get(player_id)
            pit_assignment = year_pit_assignments.get(year, {}).get(player_id)
            hit_assigned_slot = str(hit_assignment.get("slot")) if isinstance(hit_assignment, dict) else None
            pit_assigned_slot = str(pit_assignment.get("slot")) if isinstance(pit_assignment, dict) else None
            hit_assigned_value = float(hit_assignment.get("value", 0.0)) if isinstance(hit_assignment, dict) else 0.0
            pit_assigned_value = float(pit_assignment.get("value", 0.0)) if isinstance(pit_assignment, dict) else 0.0
            hit_assigned_points = float(hit_assignment.get("points", 0.0)) if isinstance(hit_assignment, dict) else 0.0
            pit_assigned_points = float(pit_assignment.get("points", 0.0)) if isinstance(pit_assignment, dict) else 0.0
            hit_assigned_replacement = float(hit_assignment.get("replacement", 0.0)) if isinstance(hit_assignment, dict) else 0.0
            pit_assigned_replacement = float(pit_assignment.get("replacement", 0.0)) if isinstance(pit_assignment, dict) else 0.0

            selected_side = "none"
            if two_way == "sum":
                year_points = hit_assigned_value + pit_assigned_value
                selected_raw_points = hit_assigned_points + pit_assigned_points
                if year_points > 0:
                    selected_side = "sum"
            else:
                if hit_assigned_value > pit_assigned_value:
                    year_points = hit_assigned_value
                    selected_raw_points = hit_assigned_points
                    selected_side = "hitting"
                elif pit_assigned_value > hit_assigned_value:
                    year_points = pit_assigned_value
                    selected_raw_points = pit_assigned_points
                    selected_side = "pitching"
                elif hit_assigned_value > 0:
                    year_points = hit_assigned_value
                    selected_raw_points = hit_assigned_points
                    selected_side = "hitting"
                else:
                    year_points = 0.0
                    selected_raw_points = 0.0

            year_details.append(
                {
                    "year": year,
                    "hitting_points": hit_points,
                    "pitching_points": pit_points,
                    "hitting_replacement": hit_best_replacement,
                    "pitching_replacement": pit_best_replacement,
                    "hitting_best_slot": hit_best_slot,
                    "pitching_best_slot": pit_best_slot,
                    "hitting_value": hit_best_value,
                    "pitching_value": pit_best_value,
                    "hitting_assignment_slot": hit_assigned_slot,
                    "pitching_assignment_slot": pit_assigned_slot,
                    "hitting_assignment_value": hit_assigned_value,
                    "pitching_assignment_value": pit_assigned_value,
                    "hitting_assignment_replacement": hit_assigned_replacement,
                    "pitching_assignment_replacement": pit_assigned_replacement,
                    "selected_side": selected_side,
                    "selected_raw_points": float(selected_raw_points),
                    "selected_points": float(year_points),
                    "hitting": hit_breakdown,
                    "pitching": pit_breakdown,
                }
            )

        selected_values = [float(detail["selected_points"]) for detail in year_details]
        keep_drop = dynasty_keep_or_drop_values(selected_values, valuation_year_set, discount=float(discount))

        for idx, detail in enumerate(year_details):
            year = int(detail["year"])
            row_out[f"Value_{year}"] = float(detail["selected_points"])
            row_out["_ExplainPointsByYear"][str(year)] = {
                "hitting_points": round(float(detail["hitting_points"]), 4),
                "pitching_points": round(float(detail["pitching_points"]), 4),
                "hitting_replacement": round(float(detail["hitting_replacement"]), 4)
                if detail["hitting_replacement"] is not None
                else None,
                "pitching_replacement": round(float(detail["pitching_replacement"]), 4)
                if detail["pitching_replacement"] is not None
                else None,
                "hitting_best_slot": detail["hitting_best_slot"],
                "pitching_best_slot": detail["pitching_best_slot"],
                "hitting_value": round(float(detail["hitting_value"]), 4) if detail["hitting_value"] is not None else None,
                "pitching_value": round(float(detail["pitching_value"]), 4) if detail["pitching_value"] is not None else None,
                "hitting_assignment_slot": detail["hitting_assignment_slot"],
                "pitching_assignment_slot": detail["pitching_assignment_slot"],
                "hitting_assignment_value": round(float(detail["hitting_assignment_value"]), 4),
                "pitching_assignment_value": round(float(detail["pitching_assignment_value"]), 4),
                "hitting_assignment_replacement": round(float(detail["hitting_assignment_replacement"]), 4)
                if detail["hitting_assignment_slot"] is not None
                else None,
                "pitching_assignment_replacement": round(float(detail["pitching_assignment_replacement"]), 4)
                if detail["pitching_assignment_slot"] is not None
                else None,
                "selected_side": detail["selected_side"],
                "selected_raw_points": round(float(detail["selected_raw_points"]), 4),
                "selected_points": round(float(detail["selected_points"]), 4),
                "discount_factor": round(float(keep_drop.discount_factors[idx]), 6),
                "discounted_contribution": round(float(keep_drop.discounted_contributions[idx]), 4),
                "keep_drop_value": round(float(keep_drop.continuation_values[idx]), 4),
                "keep_drop_hold_value": round(float(keep_drop.hold_values[idx]), 4),
                "keep_drop_keep": bool(keep_drop.keep_flags[idx]),
                "hitting": detail["hitting"],
                "pitching": detail["pitching"],
            }

        start_year_points = row_out["_ExplainPointsByYear"].get(str(start_year), {})
        if isinstance(start_year_points, dict):
            row_out["HittingPoints"] = start_year_points.get("hitting_points")
            row_out["PitchingPoints"] = start_year_points.get("pitching_points")
            row_out["SelectedPoints"] = start_year_points.get("selected_points")
            row_out["HittingBestSlot"] = start_year_points.get("hitting_best_slot")
            row_out["PitchingBestSlot"] = start_year_points.get("pitching_best_slot")
            row_out["HittingValue"] = start_year_points.get("hitting_value")
            row_out["PitchingValue"] = start_year_points.get("pitching_value")
            row_out["HittingAssignmentSlot"] = start_year_points.get("hitting_assignment_slot")
            row_out["PitchingAssignmentSlot"] = start_year_points.get("pitching_assignment_slot")
            row_out["HittingAssignmentValue"] = start_year_points.get("hitting_assignment_value")
            row_out["PitchingAssignmentValue"] = start_year_points.get("pitching_assignment_value")
            row_out["KeepDropValue"] = start_year_points.get("keep_drop_value")

        row_out["RawDynastyValue"] = float(keep_drop.raw_total)
        result_rows.append(row_out)

    if not result_rows:
        empty_columns = [
            "Player",
            "Team",
            "Pos",
            "Age",
            "DynastyValue",
            "RawDynastyValue",
            "minor_eligible",
            ctx.player_key_col,
            ctx.player_entity_key_col,
        ] + [f"Value_{year}" for year in valuation_year_set]
        return pd.DataFrame(columns=empty_columns)

    sorted_raw_values = sorted((float(row["RawDynastyValue"]) for row in result_rows), reverse=True)
    cutoff_idx = min(replacement_rank - 1, len(sorted_raw_values) - 1)
    replacement_raw = sorted_raw_values[cutoff_idx]

    for row in result_rows:
        row["DynastyValue"] = float(row["RawDynastyValue"]) - replacement_raw

    return pd.DataFrame.from_records(result_rows)
