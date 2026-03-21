"""Points-mode dynasty calculation helpers and orchestration."""

from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Callable

import pandas as pd

try:
    from backend.valuation.active_volume import (
        SYNTHETIC_PERIOD_DAYS,
        SYNTHETIC_SEASON_DAYS,
        VolumeEntry,
        allocate_hitter_usage,
        allocate_hitter_usage_daily,
        allocate_pitcher_innings_budget,
        allocate_pitcher_usage,
        allocate_pitcher_usage_daily,
        annual_slot_capacity,
    )
    from backend.valuation.minor_eligibility import _resolve_minor_eligibility_by_year
    from backend.valuation.models import CommonDynastyRotoSettings
except ImportError:  # pragma: no cover - direct script execution fallback
    from valuation.active_volume import (  # type: ignore[no-redef]
        SYNTHETIC_PERIOD_DAYS,
        SYNTHETIC_SEASON_DAYS,
        VolumeEntry,
        allocate_hitter_usage,
        allocate_hitter_usage_daily,
        allocate_pitcher_innings_budget,
        allocate_pitcher_usage,
        allocate_pitcher_usage_daily,
        annual_slot_capacity,
    )
    from valuation.minor_eligibility import _resolve_minor_eligibility_by_year  # type: ignore[no-redef]
    from valuation.models import CommonDynastyRotoSettings  # type: ignore[no-redef]


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


_SEASON_WEEKS = 26.0


def _prospect_risk_multiplier(
    *,
    year: int,
    start_year: int,
    profile: str,
    minor_eligible: bool,
    enabled: bool,
) -> float:
    if not enabled or not minor_eligible:
        return 1.0

    year_offset = max(int(year) - int(start_year), 0)
    if profile == "pitcher":
        return float(max(0.45, 0.88 ** year_offset))
    return float(max(0.60, 0.92 ** year_offset))


def _is_near_zero_playing_time(
    player_id: str,
    year: int,
    *,
    hitter_ab_by_player_year: dict[tuple[str, int], float],
    pitcher_ip_by_player_year: dict[tuple[str, int], float],
    hitter_ab_threshold: float = 60.0,
    pitcher_ip_threshold: float = 15.0,
) -> bool:
    hit_ab = float(hitter_ab_by_player_year.get((player_id, int(year)), 0.0))
    pit_ip = float(pitcher_ip_by_player_year.get((player_id, int(year)), 0.0))
    return hit_ab <= float(hitter_ab_threshold) and pit_ip <= float(pitcher_ip_threshold)


def _apply_negative_value_stash_rules(
    value: float,
    *,
    can_minor_stash: bool,
    can_ir_stash: bool,
    ir_negative_penalty: float,
    can_bench_stash: bool,
    bench_negative_penalty: float,
) -> float:
    if value >= 0.0:
        return float(value)
    if can_minor_stash:
        return 0.0
    if can_ir_stash:
        return float(value) * float(min(max(ir_negative_penalty, 0.0), 1.0))
    if can_bench_stash:
        return float(value) * float(min(max(bench_negative_penalty, 0.0), 1.0))
    return float(value)


def _negative_fallback_value(
    *,
    best_value: float | None,
    assigned_slot: str | None,
    assigned_value: float,
) -> float:
    if assigned_slot is not None:
        return float(assigned_value)
    if best_value is None:
        return 0.0
    return min(float(best_value), 0.0)


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
    stats = breakdown.get("stats") if isinstance(breakdown.get("stats"), dict) else {}
    rule_points = breakdown.get("rule_points") if isinstance(breakdown.get("rule_points"), dict) else {}
    return {
        "stats": {
            str(key): round(float(value) * scaled_share, 4)
            for key, value in stats.items()
        },
        "rule_points": {
            str(key): round(float(value) * scaled_share, 4)
            for key, value in rule_points.items()
        },
        "total_points": round(float(breakdown.get("total_points", 0.0)) * scaled_share, 4),
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


def _weekly_pitcher_streaming_bonus_by_slot(
    entries: list[dict[str, object]],
    *,
    in_season_rostered_player_ids: set[str],
    teams: int,
    starter_slot_capacity: int,
    total_pitcher_slots: int,
    weekly_starts_cap: int | None,
    allow_same_day_starts_overflow: bool,
    weekly_acquisition_cap: int | None,
) -> tuple[dict[str, float], dict[str, float | int | None]]:
    diagnostics: dict[str, float | int | None] = {
        "season_weeks": _SEASON_WEEKS,
        "weekly_starts_cap": weekly_starts_cap,
        "effective_weekly_starts_cap": None,
        "weekly_acquisition_cap": weekly_acquisition_cap,
        "held_starts_per_week": None,
        "theoretical_streamable_starts_per_week": None,
        "streamable_starts_per_week": None,
        "streaming_realization_factor": None,
        "replacement_points_per_start": None,
        "streaming_points_per_sp_slot": None,
        "streaming_points_per_p_slot": None,
    }
    if starter_slot_capacity <= 0 or weekly_acquisition_cap is None or weekly_acquisition_cap <= 0:
        return {}, diagnostics

    effective_weekly_cap = _effective_weekly_starts_cap(
        weekly_starts_cap,
        allow_same_day_starts_overflow=allow_same_day_starts_overflow,
        starter_slot_capacity=starter_slot_capacity,
    )
    if effective_weekly_cap is None or effective_weekly_cap <= 0:
        return {}, diagnostics
    diagnostics["effective_weekly_starts_cap"] = round(effective_weekly_cap, 4)

    starter_entries: list[dict[str, float | str]] = []
    for entry in entries:
        raw_slots = entry.get("slots")
        if not isinstance(raw_slots, (set, list, tuple)):
            continue

        player_id = str(entry.get("player_id") or "").strip()
        if not player_id:
            continue
        try:
            points = float(entry.get("points") or 0.0)
            gs = float(entry.get("gs") or 0.0)
        except (TypeError, ValueError):
            continue
        # Weekly starts caps apply to meaningful starters, not RP rows with a
        # few fractional projected starts. Using a GS floor keeps P-only leagues
        # calibratable without letting relievers dominate points-per-start.
        if gs < 5.0:
            continue
        if gs <= 0 or points <= 0:
            continue
        starter_entries.append(
            {
                "player_id": player_id,
                "points": points,
                "gs": gs,
                "points_per_start": points / gs,
            }
        )

    if not starter_entries:
        return {}, diagnostics

    active_starter_count = max(int(teams) * max(int(starter_slot_capacity), 1), 1)
    top_rostered_starters = sorted(
        starter_entries,
        key=lambda entry: (
            -float(entry["points"]),
            -float(entry["gs"]),
            str(entry["player_id"]),
        ),
    )[:active_starter_count]
    if not top_rostered_starters:
        return {}, diagnostics

    avg_rostered_starts = sum(float(entry["gs"]) for entry in top_rostered_starters) / len(top_rostered_starters)
    held_starts_per_week = (avg_rostered_starts / _SEASON_WEEKS) * float(starter_slot_capacity)
    diagnostics["held_starts_per_week"] = round(held_starts_per_week, 4)

    streamable_starts_per_week = min(
        max(effective_weekly_cap - held_starts_per_week, 0.0),
        float(weekly_acquisition_cap),
    )
    diagnostics["theoretical_streamable_starts_per_week"] = round(streamable_starts_per_week, 4)
    diagnostics["streamable_starts_per_week"] = round(streamable_starts_per_week, 4)
    # Generic P baselines already reflect held-start production from a managed
    # season-long staff. Scale the additive weekly uplift by the streamable
    # share of the combined held-start plus capped-start environment so we do
    # not spread the full theoretical cap surplus across every P slot.
    streaming_realization_factor = min(
        max(
            streamable_starts_per_week / max(effective_weekly_cap + held_starts_per_week, 1e-9),
            0.0,
        ),
        1.0,
    )
    diagnostics["streaming_realization_factor"] = round(streaming_realization_factor, 4)
    if streamable_starts_per_week <= 1e-9:
        return {}, diagnostics

    free_agent_starters = [
        entry for entry in starter_entries if str(entry["player_id"]) not in in_season_rostered_player_ids
    ]
    if not free_agent_starters:
        free_agent_starters = sorted(
            starter_entries,
            key=lambda entry: (
                -float(entry["points"]),
                -float(entry["gs"]),
                str(entry["player_id"]),
            ),
        )[active_starter_count:]
    if not free_agent_starters:
        return {}, diagnostics

    candidate_pps = sorted(
        (
            float(entry["points_per_start"])
            for entry in free_agent_starters
            if float(entry["points_per_start"]) > 0
        ),
        reverse=True,
    )
    if not candidate_pps:
        return {}, diagnostics

    top_n = candidate_pps[: max(int(teams), 1)]
    replacement_points_per_start = float(sum(top_n) / len(top_n))
    diagnostics["replacement_points_per_start"] = round(replacement_points_per_start, 4)

    streaming_points_per_sp_slot = (
        replacement_points_per_start
        * (streamable_starts_per_week / float(starter_slot_capacity))
        * _SEASON_WEEKS
    )
    generic_slot_share = min(
        1.0,
        float(starter_slot_capacity) / max(float(total_pitcher_slots), 1.0),
    )
    # Generic P baselines already capture the held-start portion of a managed
    # staff, so only the realized stream-derived share should be layered onto
    # P slots.
    streaming_points_per_p_slot = (
        streaming_points_per_sp_slot
        * streaming_realization_factor
        * generic_slot_share
    )
    diagnostics["streaming_points_per_sp_slot"] = round(streaming_points_per_sp_slot, 4)
    diagnostics["streaming_points_per_p_slot"] = round(streaming_points_per_p_slot, 4)

    bonus_by_slot: dict[str, float] = {}
    if streaming_points_per_sp_slot > 1e-9:
        bonus_by_slot["SP"] = float(streaming_points_per_sp_slot)
    if streaming_points_per_p_slot > 1e-9:
        bonus_by_slot["P"] = float(streaming_points_per_p_slot)
    return bonus_by_slot, diagnostics


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
    keeper_limit: int | None,
    two_way: str,
    points_valuation_mode: str,
    weekly_starts_cap: int | None,
    allow_same_day_starts_overflow: bool,
    weekly_acquisition_cap: int | None,
    start_year: int,
    pts_hit_1b: float,
    pts_hit_2b: float,
    pts_hit_3b: float,
    pts_hit_hr: float,
    pts_hit_r: float,
    pts_hit_rbi: float,
    pts_hit_sb: float,
    pts_hit_bb: float,
    pts_hit_hbp: float,
    pts_hit_so: float,
    pts_pit_ip: float,
    pts_pit_w: float,
    pts_pit_l: float,
    pts_pit_k: float,
    pts_pit_sv: float,
    pts_pit_hld: float,
    pts_pit_h: float,
    pts_pit_er: float,
    pts_pit_bb: float,
    pts_pit_hbp: float,
    ip_max: float | None = None,
    enable_prospect_risk_adjustment: bool = False,
    enable_bench_stash_relief: bool = False,
    bench_negative_penalty: float = 0.55,
    enable_ir_stash_relief: bool = False,
    ir_negative_penalty: float = 0.20,
    hit_dh: int = 0,
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
        "pts_hit_hbp": float(pts_hit_hbp),
        "pts_hit_so": float(pts_hit_so),
        "pts_pit_ip": float(pts_pit_ip),
        "pts_pit_w": float(pts_pit_w),
        "pts_pit_l": float(pts_pit_l),
        "pts_pit_k": float(pts_pit_k),
        "pts_pit_sv": float(pts_pit_sv),
        "pts_pit_hld": float(pts_pit_hld),
        "pts_pit_h": float(pts_pit_h),
        "pts_pit_er": float(pts_pit_er),
        "pts_pit_bb": float(pts_pit_bb),
        "pts_pit_hbp": float(pts_pit_hbp),
    }

    bat_rows = ctx.bat_data
    pit_rows = ctx.pit_data

    valid_years = ctx.coerce_meta_years(ctx.meta)
    valuation_year_set = ctx.valuation_years(start_year, horizon, valid_years)
    year_set = set(valuation_year_set)

    if not valuation_year_set:
        raise ValueError("No valuation years available for selected start_year and horizon.")

    minor_defaults = CommonDynastyRotoSettings()
    bat_minor_rows = [{**row, "Player": ctx.points_player_identity(row)} for row in bat_rows]
    pit_minor_rows = [{**row, "Player": ctx.points_player_identity(row)} for row in pit_rows]
    minor_eligibility_frame = _resolve_minor_eligibility_by_year(
        pd.DataFrame.from_records(bat_minor_rows),
        pd.DataFrame.from_records(pit_minor_rows),
        years=valuation_year_set,
        hitter_usage_max=minor_defaults.minor_ab_max,
        pitcher_usage_max=minor_defaults.minor_ip_max,
        hitter_age_max=minor_defaults.minor_age_max_hit,
        pitcher_age_max=minor_defaults.minor_age_max_pit,
    )
    minor_eligibility_by_year = {
        (str(row["Player"]), int(row["Year"])): bool(row["minor_eligible"])
        for row in minor_eligibility_frame.to_dict(orient="records")
    }

    rows_by_player: dict[str, dict[int, dict[str, dict | None]]] = {}
    hitter_ab_by_player_year: dict[tuple[str, int], float] = {}
    pitcher_ip_by_player_year: dict[tuple[str, int], float] = {}

    for row in bat_rows:
        year = ctx.coerce_record_year(row.get("Year"))
        if year is None or year not in year_set:
            continue
        player_id = ctx.points_player_identity(row)
        hitter_ab_by_player_year[(player_id, year)] = ctx.stat_or_zero(row, "AB")
        bucket = rows_by_player.setdefault(player_id, {})
        pair = bucket.setdefault(year, {"hit": None, "pit": None})
        pair["hit"] = row

    for row in pit_rows:
        year = ctx.coerce_record_year(row.get("Year"))
        if year is None or year not in year_set:
            continue
        player_id = ctx.points_player_identity(row)
        pitcher_ip_by_player_year[(player_id, year)] = ctx.stat_or_zero(row, "IP")
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
        + hit_dh
        + hit_ut
        + pit_p
        + pit_sp
        + pit_rp
    )
    active_depth_per_team = max(1, active_slots_per_team)
    in_season_depth_per_team = max(1, active_slots_per_team + bench + minors + ir)
    replacement_depth_per_team = int(keeper_limit) if keeper_limit is not None else in_season_depth_per_team
    replacement_rank = max(1, teams * max(replacement_depth_per_team, 1))
    in_season_replacement_rank = max(1, teams * in_season_depth_per_team)
    hitter_slot_counts = {
        "C": int(hit_c),
        "1B": int(hit_1b),
        "2B": int(hit_2b),
        "3B": int(hit_3b),
        "SS": int(hit_ss),
        "CI": int(hit_ci),
        "MI": int(hit_mi),
        "OF": int(hit_of),
        "DH": int(hit_dh),
        "UT": int(hit_ut),
    }
    pitcher_slot_counts = {
        "P": int(pit_p),
        "SP": int(pit_sp),
        "RP": int(pit_rp),
    }
    active_hitter_slots = {slot for slot, count in hitter_slot_counts.items() if count > 0}
    active_pitcher_slots = {slot for slot, count in pitcher_slot_counts.items() if count > 0}
    starter_slot_capacity = max(int(pit_p) + int(pit_sp), 0)
    n_replacement = max(int(teams), 1)
    freeze_replacement_baselines = True

    player_meta: dict[str, dict[str, object]] = {}
    per_player_year: dict[str, dict[int, dict[str, object]]] = {}
    year_hit_entries: dict[int, list[dict[str, object]]] = {year: [] for year in valuation_year_set}
    year_pit_entries: dict[int, list[dict[str, object]]] = {year: [] for year in valuation_year_set}
    player_raw_totals: dict[str, float] = {}
    player_profile: dict[str, str] = {}
    hitter_usage_diagnostics_by_year: dict[int, dict[str, float | int | None]] = {}
    pitcher_usage_diagnostics_by_year: dict[int, dict[str, float | int | None]] = {}
    empty_hit_breakdown = ctx.calculate_hitter_points_breakdown(None, scoring)
    empty_pit_breakdown = ctx.calculate_pitcher_points_breakdown(None, scoring)
    use_daily_volume = points_valuation_mode in {"season_total", "daily_h2h"}
    annual_hitter_slot_capacity = annual_slot_capacity(
        hitter_slot_counts,
        teams=teams,
        season_capacity_per_slot=float(SYNTHETIC_SEASON_DAYS) if use_daily_volume else 162.0,
    )
    annual_pitcher_slot_capacity = annual_slot_capacity(
        pitcher_slot_counts,
        teams=teams,
        season_capacity_per_slot=float(SYNTHETIC_SEASON_DAYS) if use_daily_volume else 162.0,
    )

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
        player_profile[player_id] = "pitcher" if meta_pit and not meta_hit else "hitter"

        year_map: dict[int, dict[str, object]] = {}

        for year in valuation_year_set:
            pair = per_year.get(year) or {"hit": None, "pit": None}
            hit_row = pair.get("hit")
            pit_row = pair.get("pit")

            raw_hit_breakdown = ctx.calculate_hitter_points_breakdown(hit_row, scoring)
            raw_pit_breakdown = ctx.calculate_pitcher_points_breakdown(pit_row, scoring)
            raw_hit_points = float(raw_hit_breakdown["total_points"])
            raw_pit_points = float(raw_pit_breakdown["total_points"])

            hit_slots = set()
            if isinstance(hit_row, dict) and ctx.stat_or_zero(hit_row, "AB") > 0:
                hit_slots = ctx.points_hitter_eligible_slots(hit_row.get("Pos")) & active_hitter_slots
            pit_slots = set()
            if isinstance(pit_row, dict) and ctx.stat_or_zero(pit_row, "IP") > 0:
                pit_slots = ctx.points_pitcher_eligible_slots(pit_row.get("Pos")) & active_pitcher_slots

            projected_hit_games = ctx.stat_or_zero(hit_row, "G")
            projected_pit_appearances = ctx.stat_or_zero(pit_row, "G")
            projected_pit_starts = min(ctx.stat_or_zero(pit_row, "GS"), projected_pit_appearances) if projected_pit_appearances > 0.0 else 0.0
            projected_pit_ip = ctx.stat_or_zero(pit_row, "IP")

            year_map[year] = {
                "raw_hit_breakdown": raw_hit_breakdown,
                "raw_pit_breakdown": raw_pit_breakdown,
                "raw_hit_points": raw_hit_points,
                "raw_pit_points": raw_pit_points,
                "hit_slots": set(hit_slots),
                "pit_slots": set(pit_slots),
                "hit_has_volume": bool(hit_slots),
                "pit_has_volume": bool(pit_slots),
                "projected_hit_games": float(projected_hit_games),
                "projected_pit_appearances": float(projected_pit_appearances),
                "projected_pit_starts": float(projected_pit_starts),
                "projected_pit_ip": float(projected_pit_ip),
            }

        per_player_year[player_id] = year_map

    for year in valuation_year_set:
        hitter_entries: list[VolumeEntry] = []
        pitcher_entries: list[VolumeEntry] = []
        pitcher_start_volume: dict[str, float] = {}
        fallback_hitter_ids: set[str] = set()
        fallback_pitcher_ids: set[str] = set()
        requested_hitter_games = 0.0

        for player_id, year_map in per_player_year.items():
            info = year_map.get(year, {})
            hit_slots = set(info.get("hit_slots", set()))
            projected_hit_games = float(info.get("projected_hit_games", 0.0))
            raw_hit_points = float(info.get("raw_hit_points", 0.0))
            if hit_slots:
                if projected_hit_games > 0.0:
                    requested_hitter_games += projected_hit_games
                    hitter_entries.append(
                        VolumeEntry(
                            player_id=player_id,
                            projected_volume=projected_hit_games,
                            quality=raw_hit_points / projected_hit_games,
                            slots=set(hit_slots),
                            year=year,
                        )
                    )
                else:
                    fallback_hitter_ids.add(player_id)

            pit_slots = set(info.get("pit_slots", set()))
            projected_pit_appearances = float(info.get("projected_pit_appearances", 0.0))
            raw_pit_points = float(info.get("raw_pit_points", 0.0))
            if pit_slots:
                if projected_pit_appearances > 0.0:
                    pitcher_entries.append(
                        VolumeEntry(
                            player_id=player_id,
                            projected_volume=projected_pit_appearances,
                            quality=raw_pit_points / projected_pit_appearances,
                            slots=set(pit_slots),
                            year=year,
                        )
                    )
                    projected_start_volume = min(
                        float(info.get("projected_pit_starts", 0.0)),
                        projected_pit_appearances,
                    )
                    pitcher_start_volume[player_id] = projected_start_volume if projected_start_volume >= 1.0 else 0.0
                else:
                    fallback_pitcher_ids.add(player_id)

        if points_valuation_mode == "weekly_h2h":
            hitter_usage = allocate_hitter_usage(
                hitter_entries,
                slot_capacity=annual_hitter_slot_capacity,
            )
        else:
            hitter_usage = allocate_hitter_usage_daily(
                hitter_entries,
                slot_capacity=annual_hitter_slot_capacity,
            )

        effective_weekly_cap: float | None = None
        capped_start_budget: float | None = None
        held_pitcher_ids: set[str] | None = None
        streaming_adds_per_period: int | None = None
        if points_valuation_mode in {"weekly_h2h", "daily_h2h"}:
            effective_weekly_cap = _effective_weekly_starts_cap(
                weekly_starts_cap,
                allow_same_day_starts_overflow=allow_same_day_starts_overflow,
                starter_slot_capacity=starter_slot_capacity,
            )
            if effective_weekly_cap is not None and effective_weekly_cap > 0.0:
                capped_start_budget = float(effective_weekly_cap) * _SEASON_WEEKS * max(int(teams), 1)
        if points_valuation_mode == "daily_h2h":
            held_pitcher_budget = max(int(teams), 1) * max(int(starter_slot_capacity), 0)
            held_pitcher_ids = {
                entry.player_id
                for entry in sorted(
                    (
                        entry
                        for entry in pitcher_entries
                        if float(pitcher_start_volume.get(entry.player_id, 0.0)) >= 1.0
                    ),
                    key=lambda entry: (-float(entry.quality), str(entry.player_id)),
                )[:held_pitcher_budget]
            }
            if weekly_acquisition_cap is not None:
                streaming_adds_per_period = max(int(weekly_acquisition_cap), 0) * max(int(teams), 1)

        if points_valuation_mode == "weekly_h2h":
            pitcher_usage = allocate_pitcher_usage(
                pitcher_entries,
                start_volume_by_player=pitcher_start_volume,
                slot_capacity=annual_pitcher_slot_capacity,
                capped_start_budget=capped_start_budget,
            )
        else:
            pitcher_usage = allocate_pitcher_usage_daily(
                pitcher_entries,
                start_volume_by_player=pitcher_start_volume,
                slot_capacity=annual_pitcher_slot_capacity,
                capped_start_budget=capped_start_budget,
                held_player_ids=held_pitcher_ids,
                streaming_adds_per_period=streaming_adds_per_period,
                total_days=SYNTHETIC_SEASON_DAYS,
                period_days=SYNTHETIC_PERIOD_DAYS,
            )

        ip_budget = float(ip_max) * max(int(teams), 1) if ip_max is not None else None
        pitcher_appearance_usage_share: dict[str, float] = {}
        pitcher_ip_usage_share: dict[str, float] = {}
        pitcher_requested_ip_pre_cap: dict[str, float] = {}
        pitcher_assigned_ip: dict[str, float] = {}
        requested_pitcher_ip_pre_cap = 0.0
        ip_entries: list[VolumeEntry] = []

        for player_id, year_map in per_player_year.items():
            info = year_map.get(year, {})
            pit_slots = set(info.get("pit_slots", set()))
            if not pit_slots:
                continue
            projected_pit_ip = float(info.get("projected_pit_ip", 0.0))
            if projected_pit_ip <= 0.0:
                pitcher_appearance_usage_share[player_id] = 0.0
                pitcher_ip_usage_share[player_id] = 0.0
                pitcher_requested_ip_pre_cap[player_id] = 0.0
                pitcher_assigned_ip[player_id] = 0.0
                continue
            appearance_share = (
                1.0 if player_id in fallback_pitcher_ids else float(pitcher_usage.usage_share_by_player.get(player_id, 0.0))
            )
            appearance_share = float(min(max(appearance_share, 0.0), 1.0))
            requested_ip = projected_pit_ip * appearance_share
            pitcher_appearance_usage_share[player_id] = appearance_share
            pitcher_requested_ip_pre_cap[player_id] = requested_ip
            requested_pitcher_ip_pre_cap += requested_ip
            if requested_ip > 0.0:
                raw_pit_points = float(info.get("raw_pit_points", 0.0))
                requested_points = raw_pit_points * appearance_share
                ip_entries.append(
                    VolumeEntry(
                        player_id=player_id,
                        projected_volume=requested_ip,
                        quality=requested_points / requested_ip,
                        slots={"IP_CAP"},
                        year=year,
                    )
                )

        pitcher_ip_allocation = allocate_pitcher_innings_budget(ip_entries, ip_budget=ip_budget)
        pitcher_ip_usage_share.update(pitcher_ip_allocation.ip_usage_share_by_player)
        pitcher_assigned_ip.update(pitcher_ip_allocation.assigned_ip_by_player)

        hitter_usage_diagnostics_by_year[year] = {
            "slot_game_capacity": round(float(sum(annual_hitter_slot_capacity.values())), 4),
            "assigned_hitter_games": round(float(hitter_usage.total_assigned_volume), 4),
            "unused_hitter_games": round(
                max(float(requested_hitter_games) - float(hitter_usage.total_assigned_volume), 0.0),
                4,
            ),
            "fallback_hitter_count": int(len(fallback_hitter_ids)),
            "synthetic_season_days": int(SYNTHETIC_SEASON_DAYS) if use_daily_volume else None,
        }
        pitcher_diag: dict[str, float | int | None] = {
            "slot_appearance_capacity": round(float(sum(annual_pitcher_slot_capacity.values())), 4),
            "assigned_starts": round(float(pitcher_usage.total_assigned_starts), 4),
            "assigned_non_start_appearances": round(float(pitcher_usage.total_assigned_non_start_appearances), 4),
            "capped_start_budget": round(float(capped_start_budget), 4) if capped_start_budget is not None else None,
            "fallback_pitcher_count": int(len(fallback_pitcher_ids)),
            "synthetic_season_days": int(SYNTHETIC_SEASON_DAYS) if use_daily_volume else None,
            "selected_held_starts": round(float(pitcher_usage.selected_held_starts), 4)
            if pitcher_usage.selected_held_starts is not None
            else None,
            "selected_streamed_starts": round(float(pitcher_usage.selected_streamed_starts), 4)
            if pitcher_usage.selected_streamed_starts is not None
            else None,
            "streaming_adds_per_period": pitcher_usage.streaming_adds_per_period,
            "ip_cap_budget": round(float(ip_budget), 4) if ip_budget is not None else None,
            "requested_pitcher_ip_pre_cap": round(float(requested_pitcher_ip_pre_cap), 4),
            "assigned_pitcher_ip": round(float(pitcher_ip_allocation.total_assigned_ip), 4),
            "unused_pitcher_ip": round(float(pitcher_ip_allocation.unused_ip), 4)
            if pitcher_ip_allocation.unused_ip is not None
            else None,
            "trimmed_pitcher_ip": round(float(pitcher_ip_allocation.trimmed_ip), 4),
            "ip_cap_binding": bool(pitcher_ip_allocation.ip_cap_binding),
        }
        if points_valuation_mode == "weekly_h2h":
            pitcher_diag.update(
                {
                    "season_weeks": _SEASON_WEEKS,
                    "weekly_starts_cap": weekly_starts_cap,
                    "effective_weekly_starts_cap": round(float(effective_weekly_cap), 4)
                    if effective_weekly_cap is not None
                    else None,
                    "weekly_acquisition_cap": weekly_acquisition_cap,
                }
            )
        if points_valuation_mode == "daily_h2h":
            pitcher_diag.update(
                {
                    "season_weeks": _SEASON_WEEKS,
                    "weekly_starts_cap": weekly_starts_cap,
                    "effective_weekly_starts_cap": round(float(effective_weekly_cap), 4)
                    if effective_weekly_cap is not None
                    else None,
                    "weekly_acquisition_cap": weekly_acquisition_cap,
                    "synthetic_period_days": int(SYNTHETIC_PERIOD_DAYS),
                }
            )
        pitcher_usage_diagnostics_by_year[year] = pitcher_diag

        for player_id, year_map in per_player_year.items():
            info = year_map.get(year, {})
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))
            raw_hit_points = float(info.get("raw_hit_points", 0.0))
            raw_pit_points = float(info.get("raw_pit_points", 0.0))

            hit_share = 0.0
            if hit_slots:
                hit_share = 1.0 if player_id in fallback_hitter_ids else float(hitter_usage.usage_share_by_player.get(player_id, 0.0))
            pit_appearance_share = 0.0
            pit_ip_share = 0.0
            pit_share = 0.0
            if pit_slots:
                pit_appearance_share = float(pitcher_appearance_usage_share.get(player_id, 0.0))
                pit_ip_share = float(pitcher_ip_usage_share.get(player_id, 0.0))
                pit_share = float(min(max(pit_appearance_share * pit_ip_share, 0.0), 1.0))

            hit_breakdown = _scale_points_breakdown(
                info.get("raw_hit_breakdown") if isinstance(info.get("raw_hit_breakdown"), dict) else empty_hit_breakdown,
                hit_share,
            )
            pit_breakdown = _scale_points_breakdown(
                info.get("raw_pit_breakdown") if isinstance(info.get("raw_pit_breakdown"), dict) else empty_pit_breakdown,
                pit_share,
            )
            hit_points = float(raw_hit_points * hit_share)
            pit_points = float(raw_pit_points * pit_share)

            info.update(
                {
                    "hit_breakdown": hit_breakdown,
                    "pit_breakdown": pit_breakdown,
                    "hit_points": hit_points,
                    "pit_points": pit_points,
                    "hit_usage_share": float(min(max(hit_share, 0.0), 1.0)),
                    "pit_usage_share": float(min(max(pit_share, 0.0), 1.0)),
                    "pit_appearance_usage_share": float(min(max(pit_appearance_share, 0.0), 1.0)),
                    "pit_ip_usage_share": float(min(max(pit_ip_share, 0.0), 1.0)),
                    "hit_assigned_games": None
                    if player_id in fallback_hitter_ids
                    else float(hitter_usage.assigned_volume_by_player.get(player_id, 0.0)),
                    "pit_assigned_appearances": None
                    if player_id in fallback_pitcher_ids
                    else float(pitcher_usage.assigned_appearances_by_player.get(player_id, 0.0)),
                    "pit_assigned_starts": None
                    if player_id in fallback_pitcher_ids
                    else float(pitcher_usage.assigned_starts_by_player.get(player_id, 0.0)),
                    "pit_assigned_non_start_appearances": None
                    if player_id in fallback_pitcher_ids
                    else float(pitcher_usage.assigned_non_start_appearances_by_player.get(player_id, 0.0)),
                    "pit_assigned_ip": float(pitcher_assigned_ip.get(player_id, 0.0)) if pit_slots else None,
                }
            )
            if hit_slots:
                year_hit_entries[year].append(
                    {"player_id": player_id, "points": hit_points, "slots": set(hit_slots)}
                )
            if pit_slots:
                year_pit_entries[year].append(
                    {"player_id": player_id, "points": pit_points, "slots": set(pit_slots)}
                )

    for player_id, year_map in per_player_year.items():
        raw_total = 0.0
        for year_offset, year in enumerate(valuation_year_set):
            info = year_map.get(year, {})
            hit_points = float(info.get("hit_points", 0.0))
            pit_points = float(info.get("pit_points", 0.0))
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))

            selected_raw_points = 0.0
            if hit_slots and pit_slots:
                selected_raw_points = hit_points + pit_points if two_way == "sum" else max(hit_points, pit_points)
            elif hit_slots:
                selected_raw_points = hit_points
            elif pit_slots:
                selected_raw_points = pit_points

            raw_total += selected_raw_points * (float(discount) ** year_offset)
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
    in_season_rostered_player_ids = {
        player_id for player_id, _score in ranked_players[:in_season_replacement_rank]
    }

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

    player_year_details: dict[str, list[dict[str, object]]] = {}
    stash_scores_by_player: dict[str, float] = {}
    negative_year_players: set[str] = set()
    ir_candidate_players: set[str] = set()

    for player_id, meta_row in player_meta.items():
        year_details: list[dict[str, object]] = []

        for year in valuation_year_set:
            info = per_player_year.get(player_id, {}).get(year, {})
            hit_points = float(info.get("hit_points", 0.0))
            pit_points = float(info.get("pit_points", 0.0))
            raw_hit_points = float(info.get("raw_hit_points", 0.0))
            raw_pit_points = float(info.get("raw_pit_points", 0.0))
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
            hit_selected_value = _negative_fallback_value(
                best_value=hit_best_value,
                assigned_slot=hit_assigned_slot,
                assigned_value=hit_assigned_value,
            )
            pit_selected_value = _negative_fallback_value(
                best_value=pit_best_value,
                assigned_slot=pit_assigned_slot,
                assigned_value=pit_assigned_value,
            )
            hit_selected_raw_points = (
                hit_assigned_points
                if hit_assigned_slot is not None
                else hit_points if hit_selected_value < 0.0 else 0.0
            )
            pit_selected_raw_points = (
                pit_assigned_points
                if pit_assigned_slot is not None
                else pit_points if pit_selected_value < 0.0 else 0.0
            )

            selected_side = "none"
            if two_way == "sum":
                year_points = hit_selected_value + pit_selected_value
                selected_raw_points = hit_selected_raw_points + pit_selected_raw_points
                if year_points > 0:
                    selected_side = "sum"
                elif year_points < 0:
                    selected_side = "sum_negative"
            else:
                if hit_selected_value > pit_selected_value:
                    year_points = hit_selected_value
                    selected_raw_points = hit_selected_raw_points
                    selected_side = "hitting" if hit_assigned_slot is not None else "hitting_negative"
                elif pit_selected_value > hit_selected_value:
                    year_points = pit_selected_value
                    selected_raw_points = pit_selected_raw_points
                    selected_side = "pitching" if pit_assigned_slot is not None else "pitching_negative"
                elif hit_selected_value != 0.0:
                    year_points = hit_selected_value
                    selected_raw_points = hit_selected_raw_points
                    selected_side = "hitting" if hit_assigned_slot is not None else "hitting_negative"
                else:
                    year_points = 0.0
                    selected_raw_points = 0.0

            year_details.append(
                {
                    "year": year,
                    "hitting_points": raw_hit_points if not hit_slots else hit_points,
                    "pitching_points": raw_pit_points if not pit_slots else pit_points,
                    "hitting_raw_points": raw_hit_points,
                    "pitching_raw_points": raw_pit_points,
                    "hitting_usage_share": float(info.get("hit_usage_share", 0.0)),
                    "pitching_usage_share": float(info.get("pit_usage_share", 0.0)),
                    "pitching_appearance_usage_share": float(info.get("pit_appearance_usage_share", 0.0)),
                    "pitching_ip_usage_share": float(info.get("pit_ip_usage_share", 0.0)),
                    "hitting_assigned_games": info.get("hit_assigned_games"),
                    "pitching_assigned_appearances": info.get("pit_assigned_appearances"),
                    "pitching_assigned_starts": info.get("pit_assigned_starts"),
                    "pitching_assigned_non_start_appearances": info.get("pit_assigned_non_start_appearances"),
                    "pitching_assigned_ip": info.get("pit_assigned_ip"),
                    "hitting_projected_games": float(info.get("projected_hit_games", 0.0)),
                    "pitching_projected_appearances": float(info.get("projected_pit_appearances", 0.0)),
                    "pitching_projected_starts": float(info.get("projected_pit_starts", 0.0)),
                    "pitching_projected_ip": float(info.get("projected_pit_ip", 0.0)),
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
                    "selected_points_unadjusted": float(year_points),
                    "hitting": hit_breakdown,
                    "pitching": pit_breakdown,
                }
            )

        ranking_values: list[float] = []
        has_negative_year = False
        has_ir_candidate_year = False
        for detail in year_details:
            year = int(detail["year"])
            raw_value = float(detail["selected_points_unadjusted"])
            if raw_value < 0.0:
                has_negative_year = True
                if _is_near_zero_playing_time(
                    player_id,
                    year,
                    hitter_ab_by_player_year=hitter_ab_by_player_year,
                    pitcher_ip_by_player_year=pitcher_ip_by_player_year,
                ):
                    has_ir_candidate_year = True
            ranking_values.append(
                raw_value
                * _prospect_risk_multiplier(
                    year=year,
                    start_year=start_year,
                    profile=player_profile.get(player_id, "hitter"),
                    minor_eligible=bool(minor_eligibility_by_year.get((player_id, year), False)),
                    enabled=enable_prospect_risk_adjustment,
                )
            )

        player_year_details[player_id] = year_details
        stash_scores_by_player[player_id] = dynasty_keep_or_drop_values(
            ranking_values,
            valuation_year_set,
            discount=float(discount),
        ).raw_total
        if has_negative_year:
            negative_year_players.add(player_id)
        if has_ir_candidate_year:
            ir_candidate_players.add(player_id)

    reserve_ranked_player_ids = [
        player_id
        for player_id, _score in sorted(
            stash_scores_by_player.items(),
            key=lambda item: (-float(item[1]), str(item[0])),
        )
        if player_id in in_season_rostered_player_ids
    ]
    used_reserve_players: set[str] = set()

    def _select_reserve_group(limit: int, candidates: set[str]) -> set[str]:
        selected: set[str] = set()
        for player_id in reserve_ranked_player_ids:
            if len(selected) >= max(int(limit), 0):
                break
            if player_id in used_reserve_players or player_id not in candidates:
                continue
            selected.add(player_id)
            used_reserve_players.add(player_id)
        return selected

    minor_candidate_players = {
        player_id
        for player_id in reserve_ranked_player_ids
        if any(bool(minor_eligibility_by_year.get((player_id, year), False)) for year in valuation_year_set)
    }
    minor_stash_players = _select_reserve_group(int(teams) * int(minors), minor_candidate_players)
    ir_stash_players = _select_reserve_group(int(teams) * int(ir), set(reserve_ranked_player_ids) & ir_candidate_players)
    bench_stash_players = _select_reserve_group(
        int(teams) * int(bench),
        set(reserve_ranked_player_ids) & negative_year_players,
    )

    result_rows: list[dict] = []
    for player_id, meta_row in player_meta.items():
        row_out: dict[str, object] = dict(meta_row)
        row_out["minor_eligible"] = bool(
            row_out.get("minor_eligible")
            or minor_eligibility_by_year.get((player_id, int(start_year)), False)
        )
        row_out["_ExplainPointsByYear"] = {}
        year_details = player_year_details.get(player_id, [])
        adjusted_values: list[float] = []

        for detail in year_details:
            year = int(detail["year"])
            adjusted_value = float(detail["selected_points_unadjusted"])
            adjusted_value *= _prospect_risk_multiplier(
                year=year,
                start_year=start_year,
                profile=player_profile.get(player_id, "hitter"),
                minor_eligible=bool(minor_eligibility_by_year.get((player_id, year), False)),
                enabled=enable_prospect_risk_adjustment,
            )
            adjusted_value = _apply_negative_value_stash_rules(
                adjusted_value,
                can_minor_stash=player_id in minor_stash_players and bool(minor_eligibility_by_year.get((player_id, year), False)),
                can_ir_stash=enable_ir_stash_relief
                and player_id in ir_stash_players
                and _is_near_zero_playing_time(
                    player_id,
                    year,
                    hitter_ab_by_player_year=hitter_ab_by_player_year,
                    pitcher_ip_by_player_year=pitcher_ip_by_player_year,
                ),
                ir_negative_penalty=ir_negative_penalty,
                can_bench_stash=enable_bench_stash_relief and player_id in bench_stash_players,
                bench_negative_penalty=bench_negative_penalty,
            )
            adjusted_values.append(adjusted_value)

        keep_drop = dynasty_keep_or_drop_values(adjusted_values, valuation_year_set, discount=float(discount))

        for idx, detail in enumerate(year_details):
            year = int(detail["year"])
            row_out[f"Value_{year}"] = float(adjusted_values[idx])
            row_out["_ExplainPointsByYear"][str(year)] = {
                "hitting_points": round(float(detail["hitting_points"]), 4),
                "pitching_points": round(float(detail["pitching_points"]), 4),
                "hitting_raw_points": round(float(detail["hitting_raw_points"]), 4),
                "pitching_raw_points": round(float(detail["pitching_raw_points"]), 4),
                "hitting_usage_share": round(float(detail["hitting_usage_share"]), 6),
                "pitching_usage_share": round(float(detail["pitching_usage_share"]), 6),
                "pitching_appearance_usage_share": round(float(detail["pitching_appearance_usage_share"]), 6),
                "pitching_ip_usage_share": round(float(detail["pitching_ip_usage_share"]), 6),
                "hitting_assigned_games": round(float(detail["hitting_assigned_games"]), 4)
                if detail["hitting_assigned_games"] is not None
                else None,
                "pitching_assigned_appearances": round(float(detail["pitching_assigned_appearances"]), 4)
                if detail["pitching_assigned_appearances"] is not None
                else None,
                "pitching_assigned_starts": round(float(detail["pitching_assigned_starts"]), 4)
                if detail["pitching_assigned_starts"] is not None
                else None,
                "pitching_assigned_non_start_appearances": round(float(detail["pitching_assigned_non_start_appearances"]), 4)
                if detail["pitching_assigned_non_start_appearances"] is not None
                else None,
                "pitching_assigned_ip": round(float(detail["pitching_assigned_ip"]), 4)
                if detail["pitching_assigned_ip"] is not None
                else None,
                "hitting_projected_games": round(float(detail["hitting_projected_games"]), 4),
                "pitching_projected_appearances": round(float(detail["pitching_projected_appearances"]), 4),
                "pitching_projected_starts": round(float(detail["pitching_projected_starts"]), 4),
                "pitching_projected_ip": round(float(detail["pitching_projected_ip"]), 4),
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
                "selected_points_unadjusted": round(float(detail["selected_points_unadjusted"]), 4),
                "selected_points": round(float(adjusted_values[idx]), 4),
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
            row_out["KeepDropHoldValue"] = start_year_points.get("keep_drop_hold_value")
            row_out["KeepDropKeep"] = start_year_points.get("keep_drop_keep")

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

    out = pd.DataFrame.from_records(result_rows)
    valuation_diagnostics: dict[str, object] = {
        "PointsValuationMode": points_valuation_mode,
        "KeeperLimit": int(keeper_limit) if keeper_limit is not None else None,
        "ReplacementRank": int(replacement_rank),
        "InSeasonReplacementRank": int(in_season_replacement_rank),
        "ActiveDepthPerTeam": int(active_depth_per_team),
        "InSeasonDepthPerTeam": int(in_season_depth_per_team),
        "HitterUsageByYear": {
            str(year): diagnostics
            for year, diagnostics in sorted(hitter_usage_diagnostics_by_year.items())
        },
        "PitcherUsageByYear": {
            str(year): diagnostics
            for year, diagnostics in sorted(pitcher_usage_diagnostics_by_year.items())
        },
    }
    if points_valuation_mode == "weekly_h2h":
        valuation_diagnostics.update(
            {
                "WeeklyStartsCap": weekly_starts_cap,
                "AllowSameDayStartsOverflow": bool(allow_same_day_starts_overflow),
                "WeeklyAcquisitionCap": weekly_acquisition_cap,
                "WeeklyPitchingByYear": {
                    str(year): diagnostics
                    for year, diagnostics in sorted(pitcher_usage_diagnostics_by_year.items())
                },
            }
        )
    if points_valuation_mode == "daily_h2h":
        valuation_diagnostics.update(
            {
                "WeeklyStartsCap": weekly_starts_cap,
                "AllowSameDayStartsOverflow": bool(allow_same_day_starts_overflow),
                "WeeklyAcquisitionCap": weekly_acquisition_cap,
                "SyntheticSeasonDays": int(SYNTHETIC_SEASON_DAYS),
                "SyntheticPeriodDays": int(SYNTHETIC_PERIOD_DAYS),
                "DailyPitchingByYear": {
                    str(year): diagnostics
                    for year, diagnostics in sorted(pitcher_usage_diagnostics_by_year.items())
                },
            }
        )
    out.attrs["valuation_diagnostics"] = valuation_diagnostics
    return out
