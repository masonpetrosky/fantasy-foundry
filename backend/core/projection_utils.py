"""Projection utility helpers shared by API wiring and tests."""

from __future__ import annotations

import re

import pandas as pd


def coerce_record_year(value: object) -> int | None:
    """Normalize JSON year values from int/float/string to int."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = float(text)
        except ValueError:
            return None
        return int(parsed) if parsed.is_integer() else None
    return None


def position_tokens(value: object, *, split_re: re.Pattern[str]) -> set[str]:
    text = str(value or "").strip().upper()
    if not text:
        return set()
    return {token for token in split_re.split(text) if token}


def position_sort_key(token: str, *, display_order: tuple[str, ...]) -> tuple[int, str]:
    order_map = {pos: idx for idx, pos in enumerate(display_order)}
    return (order_map.get(token, len(order_map)), token)


def row_team_value(row: dict) -> str:
    return str(row.get("Team") or row.get("MLBTeam") or "").strip()


def merge_position_value(
    hit_pos: object,
    pit_pos: object,
    *,
    split_re: re.Pattern[str],
    display_order: tuple[str, ...],
) -> str | None:
    tokens = position_tokens(hit_pos, split_re=split_re) | position_tokens(pit_pos, split_re=split_re)
    if tokens:
        return "/".join(sorted(tokens, key=lambda token: position_sort_key(token, display_order=display_order)))
    hit_text = str(hit_pos or "").strip()
    if hit_text:
        return hit_text
    pit_text = str(pit_pos or "").strip()
    return pit_text or None


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
