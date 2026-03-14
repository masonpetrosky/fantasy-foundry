"""Standalone filter and lookup helpers extracted from ProjectionService.

All functions are pure (no class state) – config values that the service
previously accessed via ``self._ctx`` are passed in explicitly.
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Year / value coercion
# ---------------------------------------------------------------------------


def coerce_record_year(value: object) -> int | None:
    """Normalize JSON year values from int/float/string to int for robust filtering."""
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


# ---------------------------------------------------------------------------
# Position helpers
# ---------------------------------------------------------------------------


def position_tokens(value: object, *, split_re: re.Pattern[str]) -> set[str]:
    """Parse a position string into a set of upper-cased tokens."""
    text = str(value or "").strip().upper()
    if not text:
        return set()
    return {token for token in split_re.split(text) if token}


def position_sort_key(token: str, *, position_display_order: tuple[str, ...]) -> tuple[int, str]:
    """Sort key for a single position token given the canonical display order."""
    order_map = {pos: idx for idx, pos in enumerate(position_display_order)}
    return (order_map.get(token, len(order_map)), token)


# ---------------------------------------------------------------------------
# Player-key helpers
# ---------------------------------------------------------------------------


def normalize_player_keys_filter(value: str | None) -> str:
    """Canonical, sorted, comma-joined representation of a player-keys filter."""
    text = str(value or "").strip()
    if not text:
        return ""
    tokens = sorted({token.strip().lower() for token in re.split(r"[\s,]+", text) if token.strip()})
    return ",".join(tokens)


def parse_player_keys_filter(value: str | None) -> set[str] | None:
    """Parse a player-keys filter string into a set (or *None* if empty)."""
    normalized = normalize_player_keys_filter(value)
    if not normalized:
        return None
    return {token for token in normalized.split(",") if token}


def row_player_filter_keys(
    row: dict,
    *,
    player_key_col: str,
    player_entity_key_col: str,
) -> set[str]:
    """Return the set of lower-cased identity keys present on *row*."""
    keys: set[str] = set()
    entity_key = str(row.get(player_entity_key_col) or "").strip().lower()
    if entity_key:
        keys.add(entity_key)
    player_key = str(row.get(player_key_col) or "").strip().lower()
    if player_key:
        keys.add(player_key)
    return keys


# ---------------------------------------------------------------------------
# Generic filter / normalize helpers
# ---------------------------------------------------------------------------


def normalize_filter_value(value: str | None) -> str:
    """Strip whitespace from a filter value (or return empty string)."""
    return (value or "").strip()


# ---------------------------------------------------------------------------
# Sort-key helpers
# ---------------------------------------------------------------------------


def value_col_sort_key(col: str) -> tuple[int, int | str]:
    """Sort key for ``Value_<year>`` columns – numeric suffixes first."""
    suffix = col.split("_", 1)[1] if "_" in col else col
    return (0, int(suffix)) if str(suffix).isdigit() else (1, suffix)


# ---------------------------------------------------------------------------
# Row accessors
# ---------------------------------------------------------------------------


def row_team_value(row: dict) -> str:
    """Extract the team string from a projection row."""
    return str(row.get("Team") or row.get("MLBTeam") or "").strip()


def projection_merge_key(
    row: dict,
    *,
    player_entity_key_col: str,
    player_key_col: str,
) -> tuple[str, object, str]:
    """Deterministic merge key: (player, year, team)."""
    player = str(
        row.get(player_entity_key_col)
        or row.get(player_key_col)
        or row.get("Player", "")
    ).strip()
    parsed_year = coerce_record_year(row.get("Year"))
    merge_year: object = parsed_year if parsed_year is not None else str(row.get("Year", "")).strip()
    team = row_team_value(row).upper()
    return player, merge_year, team


def merge_position_value(
    hit_pos: object,
    pit_pos: object,
    *,
    split_re: re.Pattern[str],
    position_display_order: tuple[str, ...],
) -> str | None:
    """Merge hitter and pitcher position strings into a single display value."""
    tokens = position_tokens(hit_pos, split_re=split_re) | position_tokens(pit_pos, split_re=split_re)
    if tokens:
        return "/".join(sorted(tokens, key=lambda t: position_sort_key(t, position_display_order=position_display_order)))
    hit_text = str(hit_pos or "").strip()
    if hit_text:
        return hit_text
    pit_text = str(pit_pos or "").strip()
    return pit_text or None


def career_group_key(
    row: dict,
    *,
    player_key_col: str,
    player_entity_key_col: str,
    normalize_player_key_fn: Any,
) -> str:
    """Grouping key for career-total aggregation."""
    player_name = str(row.get("Player", "")).strip()
    player_key = str(row.get(player_key_col) or "").strip() or normalize_player_key_fn(player_name)
    return str(row.get(player_entity_key_col) or "").strip() or player_key


def row_overlay_lookup_key(
    row: dict,
    *,
    player_entity_key_col: str,
    player_key_col: str,
) -> str:
    """Lower-cased identity key used for calculator overlay lookups."""
    entity_key = str(row.get(player_entity_key_col) or "").strip().lower()
    if entity_key:
        return entity_key
    return str(row.get(player_key_col) or "").strip().lower()
