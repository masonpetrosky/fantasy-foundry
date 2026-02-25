"""Projection aggregation and merge helpers."""

from __future__ import annotations

from typing import Callable

import pandas as pd


def coerce_numeric(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def max_projection_count(*values: object) -> int | None:
    counts: list[int] = []
    for value in values:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if pd.isna(parsed):
            continue
        counts.append(int(round(parsed)))
    return max(counts) if counts else None


def oldest_projection_date(*values: object) -> str | None:
    oldest_ts: pd.Timestamp | None = None
    oldest_text: str | None = None

    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            continue
        if oldest_ts is None or parsed < oldest_ts:
            oldest_ts = parsed
            oldest_text = text

    if oldest_text is not None:
        return oldest_text

    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def rows_year_bounds(
    rows: list[dict],
    *,
    coerce_record_year_fn: Callable[[object], int | None],
) -> tuple[int | None, int | None]:
    years: list[int] = []
    for row in rows:
        parsed = coerce_record_year_fn(row.get("Year"))
        if parsed is not None:
            years.append(parsed)
    if not years:
        return None, None
    return min(years), max(years)


def format_year_span(start_year: int | None, end_year: int | None) -> str | None:
    if start_year is None or end_year is None:
        return None
    return str(start_year) if start_year == end_year else f"{start_year}-{end_year}"


def weighted_rate(
    rows: list[dict],
    rate_col: str,
    weight_col: str,
) -> float | None:
    weighted_total = 0.0
    weight_total = 0.0
    for row in rows:
        rate = coerce_numeric(row.get(rate_col))
        weight = coerce_numeric(row.get(weight_col))
        if rate is None or weight is None or weight <= 0:
            continue
        weighted_total += rate * weight
        weight_total += weight
    if weight_total <= 0:
        return None
    return weighted_total / weight_total


def aggregate_projection_career_rows(
    rows: list[dict],
    *,
    is_hitter: bool,
    career_group_key_fn: Callable[[dict], str],
    row_team_value_fn: Callable[[dict], str],
    normalize_player_key_fn: Callable[[object], str],
    player_key_col: str,
    player_entity_key_col: str,
    position_tokens_fn: Callable[[object], set[str]],
    position_sort_key_fn: Callable[[str], tuple[int, str]],
    coerce_record_year_fn: Callable[[object], int | None],
) -> list[dict]:
    if not rows:
        return []

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(career_group_key_fn(row), []).append(row)

    excluded_from_sum = {
        "Player",
        "Team",
        "MLBTeam",
        "Pos",
        "Type",
        "Year",
        "Age",
        "ProjectionsUsed",
        "OldestProjectionDate",
        "DynastyValue",
        "DynastyMatchStatus",
        "Years",
        "YearStart",
        "YearEnd",
        player_key_col,
        player_entity_key_col,
    }

    aggregated_rows: list[dict] = []
    for entity_key, player_rows in grouped.items():
        latest_row = player_rows[0]
        latest_year = coerce_record_year_fn(latest_row.get("Year"))
        for row in player_rows[1:]:
            row_year = coerce_record_year_fn(row.get("Year"))
            if row_year is None and latest_year is None:
                latest_row = row
                continue
            if row_year is None:
                continue
            if latest_year is None or row_year >= latest_year:
                latest_row = row
                latest_year = row_year

        aggregated = dict(latest_row)
        player_name = str(latest_row.get("Player", "")).strip()
        player_key = str(latest_row.get(player_key_col) or "").strip() or normalize_player_key_fn(player_name)
        aggregated[player_key_col] = player_key
        aggregated[player_entity_key_col] = entity_key or player_key

        team_value = row_team_value_fn(latest_row)
        if not team_value:
            for row in player_rows:
                team_value = row_team_value_fn(row)
                if team_value:
                    break
        if team_value:
            aggregated["Team"] = team_value

        position_tokens: set[str] = set()
        for row in player_rows:
            position_tokens.update(position_tokens_fn(row.get("Pos")))
        if position_tokens:
            aggregated["Pos"] = "/".join(sorted(position_tokens, key=position_sort_key_fn))

        ages = [age for age in (coerce_numeric(row.get("Age")) for row in player_rows) if age is not None]
        if ages:
            aggregated["Age"] = int(round(min(ages)))

        year_start, year_end = rows_year_bounds(player_rows, coerce_record_year_fn=coerce_record_year_fn)
        aggregated["Year"] = None
        aggregated["YearStart"] = year_start
        aggregated["YearEnd"] = year_end
        aggregated["Years"] = format_year_span(year_start, year_end)

        projection_count = max_projection_count(*(row.get("ProjectionsUsed") for row in player_rows))
        if projection_count is not None:
            aggregated["ProjectionsUsed"] = projection_count
        aggregated["OldestProjectionDate"] = oldest_projection_date(
            *(row.get("OldestProjectionDate") for row in player_rows)
        )

        stat_totals: dict[str, float] = {}
        for row in player_rows:
            for key, value in row.items():
                if key in excluded_from_sum or key.startswith("Value_"):
                    continue
                numeric = coerce_numeric(value)
                if numeric is None:
                    continue
                stat_totals[key] = stat_totals.get(key, 0.0) + numeric

        for key, value in stat_totals.items():
            aggregated[key] = value

        if is_hitter:
            h = coerce_numeric(aggregated.get("H"))
            ab = coerce_numeric(aggregated.get("AB"))
            if h is not None and ab is not None and ab > 0:
                aggregated["AVG"] = h / ab
            else:
                weighted_avg = weighted_rate(player_rows, "AVG", "AB")
                if weighted_avg is not None:
                    aggregated["AVG"] = weighted_avg

            b2 = coerce_numeric(aggregated.get("2B"))
            b3 = coerce_numeric(aggregated.get("3B"))
            hr = coerce_numeric(aggregated.get("HR"))
            bb = coerce_numeric(aggregated.get("BB"))
            hbp = coerce_numeric(aggregated.get("HBP"))
            sf = coerce_numeric(aggregated.get("SF"))
            if (
                h is not None
                and b2 is not None
                and b3 is not None
                and hr is not None
                and bb is not None
                and hbp is not None
                and ab is not None
                and sf is not None
                and ab > 0
            ):
                tb = h + b2 + 2.0 * b3 + 3.0 * hr
                obp_den = ab + bb + hbp + sf
                if obp_den > 0:
                    obp = (h + bb + hbp) / obp_den
                    slg = tb / ab
                    aggregated["OBP"] = obp
                    aggregated["OPS"] = obp + slg
                else:
                    weighted_obp = weighted_rate(player_rows, "OBP", "AB")
                    if weighted_obp is not None:
                        aggregated["OBP"] = weighted_obp
            else:
                weighted_obp = weighted_rate(player_rows, "OBP", "AB")
                if weighted_obp is not None:
                    aggregated["OBP"] = weighted_obp
                weighted_ops = weighted_rate(player_rows, "OPS", "AB")
                if weighted_ops is not None:
                    aggregated["OPS"] = weighted_ops
        else:
            svh = coerce_numeric(aggregated.get("SVH"))
            if svh is None:
                sv = coerce_numeric(aggregated.get("SV"))
                hld = coerce_numeric(aggregated.get("HLD"))
                if sv is not None and hld is not None:
                    aggregated["SVH"] = sv + hld
                elif sv is not None:
                    aggregated["SVH"] = sv

            qs = coerce_numeric(aggregated.get("QS"))
            if qs is None:
                qa3 = coerce_numeric(aggregated.get("QA3"))
                if qa3 is not None:
                    aggregated["QS"] = qa3

            er = coerce_numeric(aggregated.get("ER"))
            ip = coerce_numeric(aggregated.get("IP"))
            if er is not None and ip is not None and ip > 0:
                aggregated["ERA"] = (9.0 * er) / ip
            else:
                weighted_era = weighted_rate(player_rows, "ERA", "IP")
                if weighted_era is not None:
                    aggregated["ERA"] = weighted_era

            h = coerce_numeric(aggregated.get("H"))
            bb = coerce_numeric(aggregated.get("BB"))
            if h is not None and bb is not None and ip is not None and ip > 0:
                aggregated["WHIP"] = (h + bb) / ip
            else:
                weighted_whip = weighted_rate(player_rows, "WHIP", "IP")
                if weighted_whip is not None:
                    aggregated["WHIP"] = weighted_whip

        aggregated_rows.append(aggregated)

    return aggregated_rows


def aggregate_all_projection_career_rows(
    hit_rows: list[dict],
    pit_rows: list[dict],
    *,
    aggregate_projection_career_rows_fn: Callable[[list[dict], bool], list[dict]],
    career_group_key_fn: Callable[[dict], str],
    row_team_value_fn: Callable[[dict], str],
    merge_position_value_fn: Callable[[object, object], str | None],
    coerce_record_year_fn: Callable[[object], int | None],
    all_tab_hitter_stat_cols: tuple[str, ...],
    all_tab_pitch_stat_cols: tuple[str, ...],
) -> list[dict]:
    if not hit_rows and not pit_rows:
        return []

    hit_aggregated = aggregate_projection_career_rows_fn(hit_rows, True)
    pit_aggregated = aggregate_projection_career_rows_fn(pit_rows, False)

    hit_by_key = {career_group_key_fn(row): row for row in hit_aggregated}
    pit_by_key = {career_group_key_fn(row): row for row in pit_aggregated}

    ordered_keys: list[str] = []
    seen: set[str] = set()
    for row in list(hit_rows) + list(pit_rows):
        key = career_group_key_fn(row)
        if key in seen:
            continue
        seen.add(key)
        ordered_keys.append(key)
    if not ordered_keys:
        ordered_keys = list(dict.fromkeys(list(hit_by_key.keys()) + list(pit_by_key.keys())))

    merged_rows: list[dict] = []
    for key in ordered_keys:
        hit = hit_by_key.get(key)
        pit = pit_by_key.get(key)
        if not hit and not pit:
            continue

        source = hit or pit or {}
        merged = dict(source)

        merged["Type"] = "H/P" if hit and pit else ("H" if hit else "P")
        merged["Team"] = row_team_value_fn(hit or {}) or row_team_value_fn(pit or {})
        merged["Pos"] = merge_position_value_fn((hit or {}).get("Pos"), (pit or {}).get("Pos"))
        merged["Age"] = (hit or {}).get("Age")
        if merged["Age"] is None:
            merged["Age"] = (pit or {}).get("Age")

        year_start_candidates = [
            parsed
            for value in (
                (hit or {}).get("YearStart"),
                (pit or {}).get("YearStart"),
                (hit or {}).get("Year"),
                (pit or {}).get("Year"),
            )
            if (parsed := coerce_record_year_fn(value)) is not None
        ]
        year_end_candidates = [
            parsed
            for value in (
                (hit or {}).get("YearEnd"),
                (pit or {}).get("YearEnd"),
                (hit or {}).get("Year"),
                (pit or {}).get("Year"),
            )
            if (parsed := coerce_record_year_fn(value)) is not None
        ]
        year_start = min(year_start_candidates) if year_start_candidates else None
        year_end = max(year_end_candidates) if year_end_candidates else None
        merged["Year"] = None
        merged["YearStart"] = year_start
        merged["YearEnd"] = year_end
        merged["Years"] = format_year_span(year_start, year_end)

        projection_total = max_projection_count(
            (hit or {}).get("ProjectionsUsed"),
            (pit or {}).get("ProjectionsUsed"),
        )
        if projection_total is not None:
            merged["ProjectionsUsed"] = projection_total
        merged["OldestProjectionDate"] = oldest_projection_date(
            (hit or {}).get("OldestProjectionDate"),
            (pit or {}).get("OldestProjectionDate"),
        )

        for col in all_tab_hitter_stat_cols:
            merged[col] = (hit or {}).get(col)

        for col in all_tab_pitch_stat_cols:
            merged[col] = (pit or {}).get(col)
        merged["PitH"] = (pit or {}).get("H")
        merged["PitHR"] = (pit or {}).get("HR")
        merged["PitBB"] = (pit or {}).get("BB")

        merged_rows.append(merged)

    return merged_rows


def merge_all_projection_rows(
    hit_rows: list[dict],
    pit_rows: list[dict],
    *,
    projection_merge_key_fn: Callable[[dict], tuple[str, object, str]],
    row_team_value_fn: Callable[[dict], str],
    merge_position_value_fn: Callable[[object, object], str | None],
    all_tab_hitter_stat_cols: tuple[str, ...],
    all_tab_pitch_stat_cols: tuple[str, ...],
) -> list[dict]:
    grouped: dict[tuple[str, object, str], dict[str, dict | None]] = {}
    ordered_keys: list[tuple[str, object, str]] = []

    for side, rows in (("H", hit_rows), ("P", pit_rows)):
        for row in rows:
            key = projection_merge_key_fn(row)
            if key not in grouped:
                grouped[key] = {"hit": None, "pit": None}
                ordered_keys.append(key)
            if side == "H":
                grouped[key]["hit"] = row
            else:
                grouped[key]["pit"] = row

    merged_rows: list[dict] = []
    for key in ordered_keys:
        bucket = grouped[key]
        hit = bucket.get("hit")
        pit = bucket.get("pit")

        source = hit or pit or {}
        merged = dict(source)

        merged["Type"] = "H/P" if hit and pit else ("H" if hit else "P")
        merged["Team"] = row_team_value_fn(hit or {}) or row_team_value_fn(pit or {})
        merged["Pos"] = merge_position_value_fn((hit or {}).get("Pos"), (pit or {}).get("Pos"))
        merged["Age"] = (hit or {}).get("Age")
        if merged["Age"] is None:
            merged["Age"] = (pit or {}).get("Age")

        max_used = max_projection_count((hit or {}).get("ProjectionsUsed"), (pit or {}).get("ProjectionsUsed"))
        if max_used is not None:
            merged["ProjectionsUsed"] = max_used
        merged["OldestProjectionDate"] = oldest_projection_date(
            (hit or {}).get("OldestProjectionDate"),
            (pit or {}).get("OldestProjectionDate"),
        )

        for col in all_tab_hitter_stat_cols:
            merged[col] = (hit or {}).get(col)

        for col in all_tab_pitch_stat_cols:
            merged[col] = (pit or {}).get(col)
        merged["PitH"] = (pit or {}).get("H")
        merged["PitHR"] = (pit or {}).get("HR")
        merged["PitBB"] = (pit or {}).get("BB")

        merged_rows.append(merged)

    return merged_rows
