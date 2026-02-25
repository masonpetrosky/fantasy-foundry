"""Projection averaging and projection-meta helpers."""

from __future__ import annotations

from typing import Dict, List, Optional, Set

import numpy as np
import pandas as pd

try:
    from backend.valuation.projection_identity import _find_projection_date_col, _team_column_for_dataframe
except ImportError:  # pragma: no cover - direct script execution fallback
    from valuation.projection_identity import _find_projection_date_col, _team_column_for_dataframe  # type: ignore


DERIVED_HIT_RATE_COLS: Set[str] = {"AVG", "OBP", "SLG", "OPS"}
DERIVED_PIT_RATE_COLS: Set[str] = {"ERA", "WHIP"}


def average_recent_projections(
    df: pd.DataFrame,
    stat_cols: List[str],
    group_cols: Optional[List[str]] = None,
    max_entries: int = 3,
) -> pd.DataFrame:
    """
    If multiple projections exist for the same (Player, Year), average the most recent
    `max_entries` rows (by projection date column if present, otherwise file order).

    Adds two columns to the averaged output:
      - ProjectionsUsed: number of rows actually averaged (<= max_entries)
      - OldestProjectionDate: the oldest projection date among the rows averaged
        (i.e., the "third-oldest" among the selected rows when max_entries=3).
        If no projection date column exists, this will be NaT.
    """
    if max_entries < 1:
        raise ValueError("max_entries must be >= 1")

    df = df.copy()
    group_cols = group_cols or ["Player", "Year"]
    effective_group_cols = list(group_cols)

    missing_group_cols = [c for c in group_cols if c not in df.columns]
    if missing_group_cols:
        raise ValueError(f"average_recent_projections missing required group columns: {missing_group_cols}")

    team_col = _team_column_for_dataframe(df)
    if (
        team_col
        and "Player" in group_cols
        and "Year" in group_cols
        and "_entity_team" not in effective_group_cols
    ):
        team_values = df[team_col].astype("string").fillna("").str.strip()
        team_nonempty = team_values.where(team_values != "", pd.NA)
        team_counts = team_nonempty.groupby([df[c] for c in group_cols], dropna=False).transform("nunique")
        if team_counts.gt(1).any():
            # Split only ambiguous same-name/same-year groups where teams differ.
            df["_entity_team"] = team_values.where(team_counts > 1, "")
            effective_group_cols.append("_entity_team")

    date_col = _find_projection_date_col(df)

    df["_projection_order"] = np.arange(len(df))

    # Always create _projection_date so downstream logic can rely on it.
    if date_col:
        df["_projection_date"] = pd.to_datetime(df[date_col], errors="coerce")
        df["_sort_key"] = df["_projection_date"].fillna(pd.Timestamp.min)
    else:
        df["_projection_date"] = pd.NaT
        df["_sort_key"] = df["_projection_order"]

    # Keep up to `max_entries` most-recent rows per (Player, Year)
    recent = (
        df.sort_values(["_sort_key", "_projection_order"], ascending=False)
        .groupby(effective_group_cols, as_index=False, sort=False)
        .head(max_entries)
    )

    # Per-row markers so we can aggregate to group-level metadata
    recent["ProjectionsUsed"] = 1
    recent["OldestProjectionDate"] = recent["_projection_date"]

    stat_cols_present = [c for c in stat_cols if c in recent.columns]

    # Meta cols are carried forward from the most recent row (same behavior as before)
    meta_cols = [
        c for c in recent.columns
        if c not in stat_cols_present
        and c not in effective_group_cols
        and c
        not in {
            "_projection_order",
            "_projection_date",
            "_sort_key",
            "ProjectionsUsed",
            "OldestProjectionDate",
        }
    ]

    agg: Dict[str, str] = {c: "mean" for c in stat_cols_present}
    agg["ProjectionsUsed"] = "sum"
    agg["OldestProjectionDate"] = "min"
    for c in meta_cols:
        agg[c] = "first"

    out = (
        recent.sort_values(["_sort_key", "_projection_order"], ascending=False)
        .groupby(effective_group_cols, as_index=False, sort=False)
        .agg(agg)
    )
    out = out.drop(columns=["_entity_team"], errors="ignore")

    # Nice column order: group keys, then the new metadata columns, then everything else
    front = list(group_cols) + ["ProjectionsUsed", "OldestProjectionDate"]
    rest = [c for c in out.columns if c not in front]
    return out[front + rest]


def projection_meta_for_start_year(
    bat_df: pd.DataFrame,
    pit_df: pd.DataFrame,
    start_year: int,
) -> pd.DataFrame:
    """
    Produce one row per Player with:
      - ProjectionsUsed: max of Bat vs Pitch (handles hitter-only / pitcher-only / two-way)
      - OldestProjectionDate: min (oldest) of Bat vs Pitch dates

    Uses the already-averaged frames produced by average_recent_projections().
    """
    cols = ["Player", "ProjectionsUsed", "OldestProjectionDate"]

    def _subset_projection_meta(df: pd.DataFrame) -> pd.DataFrame:
        """Return a safe start-year projection metadata slice.

        Handles empty frames and cases where upstream processing provided no rows,
        ensuring we still return the expected metadata columns.
        """
        if df.empty:
            return pd.DataFrame(columns=cols)

        missing = [c for c in ["Year"] + cols if c not in df.columns]
        if missing:
            raise ValueError(f"projection metadata is missing required columns: {missing}")

        return df.loc[df["Year"] == start_year, cols].copy()

    b = _subset_projection_meta(bat_df)
    p = _subset_projection_meta(pit_df)

    m = b.merge(p, on="Player", how="outer", suffixes=("_bat", "_pit"))

    # How many projections were used (cap is enforced upstream by max_entries)
    m["ProjectionsUsed"] = m[["ProjectionsUsed_bat", "ProjectionsUsed_pit"]].max(axis=1, skipna=True)
    m["ProjectionsUsed"] = m["ProjectionsUsed"].round().astype("Int64")

    # Oldest date among whichever side exists (and the min if both exist)
    m["OldestProjectionDate"] = m[["OldestProjectionDate_bat", "OldestProjectionDate_pit"]].min(axis=1, skipna=True)

    # Store as date-only (no time) for cleaner Excel display
    m["OldestProjectionDate"] = pd.to_datetime(m["OldestProjectionDate"], errors="coerce").dt.date

    return m[["Player", "ProjectionsUsed", "OldestProjectionDate"]]


def numeric_stat_cols_for_recent_avg(
    df: pd.DataFrame,
    group_cols: Optional[List[str]] = None,
    exclude_cols: Optional[Set[str]] = None,
) -> List[str]:
    """Return numeric columns that should be averaged when collapsing projections.

    This is used both for valuation (so that any categories you care about get averaged)
    and for building "detail" output tabs that closely match the input sheets.
    """
    group_cols = group_cols or ["Player", "Year"]
    exclude_cols = set(exclude_cols or set())

    cols: List[str] = []
    for c in df.columns:
        if c in group_cols or c in exclude_cols:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols


def reorder_detail_columns(
    df: pd.DataFrame,
    input_cols: List[str],
    add_after: Optional[str] = None,
    extra_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Reorder a detail DataFrame to resemble the original input sheet.

    - Start with input_cols order (only those present).
    - Insert extra_cols immediately after `add_after` if provided and present.
    - Append any remaining columns at the end.
    """
    df = df.copy()

    base = [c for c in input_cols if c in df.columns]
    extras = [c for c in (extra_cols or []) if c in df.columns and c not in base]

    if add_after and add_after in base and extras:
        idx = base.index(add_after) + 1
        ordered = base[:idx] + extras + base[idx:]
    else:
        ordered = base + extras

    remaining = [c for c in df.columns if c not in ordered]
    return df[ordered + remaining]
