"""Slot assignment helpers for points-mode valuation."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Any, cast


@dataclass(slots=True)
class _FlowEdge:
    to: int
    rev: int
    capacity: int
    cost: int


_SEASON_WEEKS = 26.0


def _coerce_float(value: object, default: float = 0.0) -> float:
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return float(default)


def _effective_weekly_starts_cap(
    weekly_starts_cap: int | None,
    *,
    allow_same_day_starts_overflow: bool,
    starter_slot_capacity: int,
) -> float | None:
    if weekly_starts_cap is None or int(weekly_starts_cap) <= 0:
        return None

    effective_cap = float(weekly_starts_cap)
    if allow_same_day_starts_overflow:
        overflow_bonus = min(2.0, max(float(starter_slot_capacity), 1.0) * 0.20)
        effective_cap += max(0.5, overflow_bonus)
    return effective_cap


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
        points = _coerce_float(entry.get("points"), 0.0)
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
        if existing is None or _coerce_float(existing.get("points"), 0.0) < points:
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

    slot_node_by_name = {slot: first_slot_node + idx for idx, slot in enumerate(slot_names)}
    player_node_by_id = {player_id: first_player_node + idx for idx, player_id in enumerate(player_ids)}

    for slot in slot_names:
        add_edge(slot_node_by_name[slot], sink, normalized_slot_capacity[slot], 0)
    for player_id in player_ids:
        add_edge(source, player_node_by_id[player_id], 1, 0)

    player_edges: dict[str, list[tuple[str, int, int]]] = {}
    scale = 1000.0

    for player_id in player_ids:
        player_node = player_node_by_id[player_id]
        row = player_rows[player_id]
        points = _coerce_float(row["points"], 0.0)
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
        points = _coerce_float(player_rows[player_id]["points"], 0.0)
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
