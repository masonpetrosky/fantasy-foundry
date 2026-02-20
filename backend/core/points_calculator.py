"""Points-mode dynasty calculation helpers and orchestration."""

from __future__ import annotations

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
    recent_projections: int,
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

    if recent_projections == 3:
        bat_rows = ctx.bat_data
        pit_rows = ctx.pit_data
    else:
        bat_rows = ctx.average_recent_projection_rows(ctx.bat_data_raw, max_entries=recent_projections, is_hitter=True)
        pit_rows = ctx.average_recent_projection_rows(ctx.pit_data_raw, max_entries=recent_projections, is_hitter=False)

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

    roster_slots_per_team = (
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
        + bench
        + minors
        + ir
    )
    replacement_rank = max(1, teams * max(1, roster_slots_per_team))
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
                "selected_raw_points": float(selected_raw_points),
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

    result_rows: list[dict] = []
    for player_id, meta_row in player_meta.items():
        row_out: dict[str, object] = dict(meta_row)
        row_out["_ExplainPointsByYear"] = {}

        raw_total = 0.0
        for year_offset, year in enumerate(valuation_year_set):
            info = per_player_year.get(player_id, {}).get(year, {})

            hit_points = float(info.get("hit_points", 0.0))
            pit_points = float(info.get("pit_points", 0.0))
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))
            hit_breakdown = (
                info.get("hit_breakdown")
                if isinstance(info.get("hit_breakdown"), dict)
                else ctx.calculate_hitter_points_breakdown(None, scoring)
            )
            pit_breakdown = (
                info.get("pit_breakdown")
                if isinstance(info.get("pit_breakdown"), dict)
                else ctx.calculate_pitcher_points_breakdown(None, scoring)
            )

            hit_repl_map = year_hit_replacement.get(year, {})
            pit_repl_map = year_pit_replacement.get(year, {})

            hit_best_value: float | None = None
            hit_best_slot: str | None = None
            hit_best_replacement: float | None = None
            for slot in sorted(hit_slots):
                replacement_points = float(hit_repl_map.get(slot, 0.0))
                value = hit_points - replacement_points
                if hit_best_value is None or value > hit_best_value:
                    hit_best_value = float(value)
                    hit_best_slot = slot
                    hit_best_replacement = replacement_points

            pit_best_value: float | None = None
            pit_best_slot: str | None = None
            pit_best_replacement: float | None = None
            for slot in sorted(pit_slots):
                replacement_points = float(pit_repl_map.get(slot, 0.0))
                value = pit_points - replacement_points
                if pit_best_value is None or value > pit_best_value:
                    pit_best_value = float(value)
                    pit_best_slot = slot
                    pit_best_replacement = replacement_points

            selected_raw_points = 0.0
            if hit_best_value is not None and pit_best_value is not None:
                if two_way == "sum":
                    year_points = hit_best_value + pit_best_value
                    selected_raw_points = hit_points + pit_points
                elif hit_best_value >= pit_best_value:
                    year_points = hit_best_value
                    selected_raw_points = hit_points
                else:
                    year_points = pit_best_value
                    selected_raw_points = pit_points
            elif hit_best_value is not None:
                year_points = hit_best_value
                selected_raw_points = hit_points
            elif pit_best_value is not None:
                year_points = pit_best_value
                selected_raw_points = pit_points
            else:
                year_points = 0.0
                selected_raw_points = 0.0

            row_out[f"Value_{year}"] = year_points
            discount_factor = float(discount) ** year_offset
            discounted_value = year_points * discount_factor
            raw_total += discounted_value
            row_out["_ExplainPointsByYear"][str(year)] = {
                "hitting_points": round(hit_points, 4),
                "pitching_points": round(pit_points, 4),
                "hitting_replacement": round(float(hit_best_replacement), 4) if hit_best_replacement is not None else None,
                "pitching_replacement": round(float(pit_best_replacement), 4) if pit_best_replacement is not None else None,
                "hitting_best_slot": hit_best_slot,
                "pitching_best_slot": pit_best_slot,
                "hitting_value": round(float(hit_best_value), 4) if hit_best_value is not None else None,
                "pitching_value": round(float(pit_best_value), 4) if pit_best_value is not None else None,
                "selected_raw_points": round(float(selected_raw_points), 4),
                "selected_points": round(float(year_points), 4),
                "discount_factor": round(float(discount_factor), 6),
                "discounted_contribution": round(float(discounted_value), 4),
                "hitting": hit_breakdown,
                "pitching": pit_breakdown,
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

        row_out["RawDynastyValue"] = float(raw_total)
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
