"""Projection/preprocessing helper adapters used by backend runtime orchestration."""

from __future__ import annotations

import re

import pandas as pd

from backend.core.export_utils import as_float as core_as_float
from backend.core.projection_preprocessing import (
    average_recent_projection_rows as core_average_recent_projection_rows,
)
from backend.core.projection_preprocessing import (
    coerce_iso_date_text as core_coerce_iso_date_text,
)
from backend.core.projection_preprocessing import (
    find_projection_date_col as core_find_projection_date_col,
)
from backend.core.projection_preprocessing import (
    normalize_player_key as core_normalize_player_key,
)
from backend.core.projection_preprocessing import (
    normalize_team_key as core_normalize_team_key,
)
from backend.core.projection_preprocessing import (
    normalize_year_key as core_normalize_year_key,
)
from backend.core.projection_preprocessing import (
    parse_projection_dates as core_parse_projection_dates,
)
from backend.core.projection_preprocessing import (
    pick_first_existing_col as core_pick_first_existing_col,
)
from backend.core.projection_preprocessing import (
    with_player_identity_keys as core_with_player_identity_keys,
)
from backend.core.projection_utils import (
    coerce_numeric as core_coerce_numeric,
)
from backend.core.projection_utils import (
    coerce_record_year as core_coerce_record_year,
)
from backend.core.projection_utils import (
    max_projection_count as core_max_projection_count,
)
from backend.core.projection_utils import (
    merge_position_value as core_merge_position_value,
)
from backend.core.projection_utils import (
    oldest_projection_date as core_oldest_projection_date,
)
from backend.core.projection_utils import (
    position_sort_key as core_position_sort_key,
)
from backend.core.projection_utils import (
    position_tokens as core_position_tokens,
)
from backend.core.projection_utils import (
    row_team_value as core_row_team_value,
)
from backend.domain.constants import PLAYER_ENTITY_KEY_COL, PLAYER_KEY_COL

PROJECTION_DATE_COLS = ["ProjectionDate", "Date", "Updated", "LastUpdated", "Timestamp", "Created", "AsOf"]
DERIVED_HIT_RATE_COLS = {"AVG", "OBP", "SLG", "OPS"}
DERIVED_PIT_RATE_COLS = {"ERA", "WHIP"}
TEAM_COL_CANDIDATES = ("Team", "MLBTeam")
PLAYER_KEY_PATTERN = re.compile(r"[^a-z0-9]+")
POSITION_TOKEN_SPLIT_RE = re.compile(r"[,\s/]+")
POSITION_DISPLAY_ORDER = ("C", "1B", "2B", "3B", "SS", "OF", "DH", "UT", "SP", "RP")


def pick_first_existing_col(df: pd.DataFrame, candidates: list[str] | tuple[str, ...]) -> str | None:
    return core_pick_first_existing_col(df, candidates)


def find_projection_date_col(df: pd.DataFrame) -> str | None:
    return core_find_projection_date_col(df, projection_date_cols=PROJECTION_DATE_COLS)


def parse_projection_dates(values: pd.Series) -> pd.Series:
    return core_parse_projection_dates(values)


def coerce_iso_date_text(value: object) -> str | None:
    return core_coerce_iso_date_text(value)


def normalize_player_key(value: object) -> str:
    return core_normalize_player_key(value, player_key_pattern=PLAYER_KEY_PATTERN)


def normalize_team_key(value: object) -> str:
    return core_normalize_team_key(value)


def normalize_year_key(value: object) -> str:
    return core_normalize_year_key(value)


def with_player_identity_keys(
    bat_records: list[dict],
    pit_records: list[dict],
) -> tuple[list[dict], list[dict]]:
    return core_with_player_identity_keys(
        bat_records,
        pit_records,
        player_key_col=PLAYER_KEY_COL,
        player_entity_key_col=PLAYER_ENTITY_KEY_COL,
        normalize_player_key_fn=normalize_player_key,
        normalize_team_key_fn=normalize_team_key,
        normalize_year_key_fn=normalize_year_key,
    )


def average_recent_projection_rows(
    records: list[dict],
    *,
    max_entries: int = 3,
    is_hitter: bool,
) -> list[dict]:
    return core_average_recent_projection_rows(
        records,
        max_entries=max_entries,
        is_hitter=is_hitter,
        team_col_candidates=TEAM_COL_CANDIDATES,
        projection_date_cols=PROJECTION_DATE_COLS,
        derived_hit_rate_cols=DERIVED_HIT_RATE_COLS,
        derived_pit_rate_cols=DERIVED_PIT_RATE_COLS,
    )


def projection_freshness_payload(
    bat_rows: list[dict],
    pit_rows: list[dict],
) -> dict[str, object]:
    oldest_date: str | None = None
    newest_date: str | None = None
    rows_with_projection_date = 0
    total_rows = len(bat_rows) + len(pit_rows)

    for row in [*bat_rows, *pit_rows]:
        date_text = coerce_iso_date_text(row.get("OldestProjectionDate"))
        if not date_text:
            continue
        rows_with_projection_date += 1
        if oldest_date is None or date_text < oldest_date:
            oldest_date = date_text
        if newest_date is None or date_text > newest_date:
            newest_date = date_text

    coverage = (rows_with_projection_date / total_rows * 100.0) if total_rows else 0.0
    return {
        "oldest_projection_date": oldest_date,
        "newest_projection_date": newest_date,
        "rows_with_projection_date": rows_with_projection_date,
        "total_rows": total_rows,
        "date_coverage_pct": round(coverage, 1),
    }


def coerce_meta_years(meta: dict) -> list[int]:
    years: list[int] = []
    for value in meta.get("years", []):
        try:
            years.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(years))


def value_col_sort_key(col: str) -> tuple[int, int | str]:
    suffix = col.split("_", 1)[1] if "_" in col else col
    return (0, int(suffix)) if suffix.isdigit() else (1, suffix)


def coerce_record_year(value: object) -> int | None:
    return core_coerce_record_year(value)


def position_tokens(value: object) -> set[str]:
    return core_position_tokens(value, split_re=POSITION_TOKEN_SPLIT_RE)


def position_sort_key(token: str) -> tuple[int, str]:
    return core_position_sort_key(token, display_order=POSITION_DISPLAY_ORDER)


def row_team_value(row: dict) -> str:
    return core_row_team_value(row)


def merge_position_value(hit_pos: object, pit_pos: object) -> str | None:
    return core_merge_position_value(
        hit_pos,
        pit_pos,
        split_re=POSITION_TOKEN_SPLIT_RE,
        display_order=POSITION_DISPLAY_ORDER,
    )


def max_projection_count(*values: object) -> int | None:
    return core_max_projection_count(*values)


def oldest_projection_date(*values: object) -> str | None:
    return core_oldest_projection_date(*values)


def coerce_numeric(value: object) -> float | None:
    return core_coerce_numeric(value)


def as_float(value: object) -> float | None:
    return core_as_float(value)
