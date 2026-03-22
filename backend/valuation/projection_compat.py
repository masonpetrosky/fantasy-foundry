"""Projection/input/xlsx helpers kept for legacy compatibility surfaces."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

try:
    from backend.valuation import projection_averaging as _projection_averaging
    from backend.valuation import projection_identity as _projection_identity
    from backend.valuation import xlsx_formatting as _xlsx_fmt
except ImportError:
    from valuation import projection_averaging as _projection_averaging  # type: ignore[no-redef]
    from valuation import projection_identity as _projection_identity  # type: ignore[no-redef]
    from valuation import xlsx_formatting as _xlsx_fmt  # type: ignore[no-redef]


PROJECTION_DATE_COLS = _projection_identity.PROJECTION_DATE_COLS
PLAYER_KEY_COL = _projection_identity.PLAYER_KEY_COL
PLAYER_ENTITY_KEY_COL = _projection_identity.PLAYER_ENTITY_KEY_COL
PLAYER_KEY_PATTERN = _projection_identity.PLAYER_KEY_PATTERN

DERIVED_HIT_RATE_COLS = _projection_averaging.DERIVED_HIT_RATE_COLS
DERIVED_PIT_RATE_COLS = _projection_averaging.DERIVED_PIT_RATE_COLS

COMMON_COLUMN_ALIASES = {
    "mlbteam": "Team",
    "team": "Team",
    "player_name": "Player",
    "name": "Player",
}


def _find_projection_date_col(df: pd.DataFrame) -> Optional[str]:
    return _projection_identity._find_projection_date_col(df)


def _normalize_player_key(value: object) -> str:
    return _projection_identity._normalize_player_key(value)


def _normalize_team_key(value: object) -> str:
    return _projection_identity._normalize_team_key(value)


def _normalize_year_key(value: object) -> str:
    return _projection_identity._normalize_year_key(value)


def _team_column_for_dataframe(df: pd.DataFrame) -> Optional[str]:
    return _projection_identity._team_column_for_dataframe(df)


def _add_player_identity_keys(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return _projection_identity._add_player_identity_keys(bat, pit)


def _build_player_identity_lookup(bat: pd.DataFrame, pit: pd.DataFrame) -> pd.DataFrame:
    return _projection_identity._build_player_identity_lookup(bat, pit)


def _attach_identity_columns_to_output(out: pd.DataFrame, identity_lookup: pd.DataFrame) -> pd.DataFrame:
    return _projection_identity._attach_identity_columns_to_output(out, identity_lookup)


def average_recent_projections(
    df: pd.DataFrame,
    stat_cols: list[str],
    group_cols: list[str] | None = None,
) -> pd.DataFrame:
    return _projection_averaging.average_recent_projections(df, stat_cols, group_cols=group_cols)


def projection_meta_for_start_year(
    bat_df: pd.DataFrame,
    pit_df: pd.DataFrame,
    start_year: int,
) -> pd.DataFrame:
    return _projection_averaging.projection_meta_for_start_year(bat_df, pit_df, start_year)


def numeric_stat_cols_for_recent_avg(
    df: pd.DataFrame,
    group_cols: list[str] | None = None,
    exclude_cols: set[str] | None = None,
) -> list[str]:
    return _projection_averaging.numeric_stat_cols_for_recent_avg(
        df,
        group_cols=group_cols,
        exclude_cols=exclude_cols,
    )


def reorder_detail_columns(
    df: pd.DataFrame,
    input_cols: list[str],
    add_after: str | None = None,
    extra_cols: list[str] | None = None,
) -> pd.DataFrame:
    return _projection_averaging.reorder_detail_columns(
        df,
        input_cols,
        add_after=add_after,
        extra_cols=extra_cols,
    )


def recompute_common_rates_hit(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute rate stats after averaging counting components."""
    out = df.copy()

    if "H" in out.columns and "AB" in out.columns:
        h = out["H"].to_numpy(dtype=float)
        ab = out["AB"].to_numpy(dtype=float)
        out["AVG"] = np.divide(h, ab, out=np.zeros_like(h), where=ab > 0)

    needed = {"H", "2B", "3B", "HR", "BB", "HBP", "AB", "SF"}
    if needed.issubset(out.columns):
        h = out["H"].to_numpy(dtype=float)
        b2 = out["2B"].to_numpy(dtype=float)
        b3 = out["3B"].to_numpy(dtype=float)
        hr = out["HR"].to_numpy(dtype=float)
        bb = out["BB"].to_numpy(dtype=float)
        hbp = out["HBP"].to_numpy(dtype=float)
        ab = out["AB"].to_numpy(dtype=float)
        sf = out["SF"].to_numpy(dtype=float)

        tb = h + b2 + 2.0 * b3 + 3.0 * hr
        obp_den = ab + bb + hbp + sf
        obp = np.divide(h + bb + hbp, obp_den, out=np.zeros_like(obp_den), where=obp_den > 0)
        slg = np.divide(tb, ab, out=np.zeros_like(ab), where=ab > 0)

        out["TB"] = tb
        out["OBP"] = obp
        out["SLG"] = slg
        out["OPS"] = obp + slg

    return out


def recompute_common_rates_pit(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "ER" in out.columns and "IP" in out.columns:
        er = out["ER"].to_numpy(dtype=float)
        ip = out["IP"].to_numpy(dtype=float)
        out["ERA"] = np.divide(9.0 * er, ip, out=np.full_like(ip, np.nan), where=ip > 0)
    if "H" in out.columns and "BB" in out.columns and "IP" in out.columns:
        h = out["H"].to_numpy(dtype=float)
        bb = out["BB"].to_numpy(dtype=float)
        ip = out["IP"].to_numpy(dtype=float)
        out["WHIP"] = np.divide(h + bb, ip, out=np.full_like(ip, np.nan), where=ip > 0)
    return out


def require_cols(df: pd.DataFrame, cols: list[str], sheet_name: str) -> None:
    missing = [col for col in cols if col not in df.columns]
    if missing:
        raise ValueError(f"Sheet '{sheet_name}' is missing required columns: {missing}")


def normalize_input_schema(df: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    """Normalize incoming sheet columns while preserving existing names."""
    out = df.copy()
    out.columns = [str(col).strip() for col in out.columns]

    lower_to_actual = {col.lower(): col for col in out.columns}
    rename_map: dict[str, str] = {}
    for alias, canonical in aliases.items():
        actual = lower_to_actual.get(alias.lower())
        if actual and canonical not in out.columns:
            rename_map[actual] = canonical

    if rename_map:
        out = out.rename(columns=rename_map)
    return out


def _xlsx_apply_header_style(ws: object) -> None:
    return _xlsx_fmt._xlsx_apply_header_style(ws)


def _xlsx_set_freeze_filters_and_view(
    ws: object,
    freeze_panes: str,
    add_autofilter: bool = False,
) -> None:
    return _xlsx_fmt._xlsx_set_freeze_filters_and_view(
        ws,
        freeze_panes=freeze_panes,
        add_autofilter=add_autofilter,
    )


def _xlsx_add_table(ws: object, table_name: str, style_name: str = "TableStyleMedium9") -> None:
    return _xlsx_fmt._xlsx_add_table(ws, table_name=table_name, style_name=style_name)


def _xlsx_set_column_widths(
    ws: object,
    df: pd.DataFrame,
    overrides: dict[str, float] | None = None,
    sample_rows: int = 1000,
    min_width: float = 8.0,
    max_width: float = 45.0,
) -> None:
    return _xlsx_fmt._xlsx_set_column_widths(
        ws,
        df,
        overrides=overrides,
        sample_rows=sample_rows,
        min_width=min_width,
        max_width=max_width,
    )


def _xlsx_apply_number_formats(ws: object, df: pd.DataFrame, formats_by_col: dict[str, str]) -> None:
    return _xlsx_fmt._xlsx_apply_number_formats(ws, df, formats_by_col)


def _xlsx_add_value_color_scale(ws: object, df: pd.DataFrame, col_name: str) -> None:
    return _xlsx_fmt._xlsx_add_value_color_scale(ws, df, col_name)


def _xlsx_format_player_values(ws: object, df: pd.DataFrame, table_name: str = "PlayerValuesTbl") -> None:
    return _xlsx_fmt._xlsx_format_player_values(ws, df, table_name=table_name)


def _xlsx_format_detail_sheet(
    ws: object,
    df: pd.DataFrame,
    *,
    table_name: str,
    is_pitch: bool,
) -> None:
    return _xlsx_fmt._xlsx_format_detail_sheet(ws, df, table_name=table_name, is_pitch=is_pitch)


__all__ = [
    "COMMON_COLUMN_ALIASES",
    "DERIVED_HIT_RATE_COLS",
    "DERIVED_PIT_RATE_COLS",
    "PLAYER_ENTITY_KEY_COL",
    "PLAYER_KEY_COL",
    "PLAYER_KEY_PATTERN",
    "PROJECTION_DATE_COLS",
    "_add_player_identity_keys",
    "_attach_identity_columns_to_output",
    "_build_player_identity_lookup",
    "_find_projection_date_col",
    "_normalize_player_key",
    "_normalize_team_key",
    "_normalize_year_key",
    "_team_column_for_dataframe",
    "_xlsx_add_table",
    "_xlsx_add_value_color_scale",
    "_xlsx_apply_header_style",
    "_xlsx_apply_number_formats",
    "_xlsx_format_detail_sheet",
    "_xlsx_format_player_values",
    "_xlsx_set_column_widths",
    "_xlsx_set_freeze_filters_and_view",
    "average_recent_projections",
    "normalize_input_schema",
    "numeric_stat_cols_for_recent_avg",
    "projection_meta_for_start_year",
    "recompute_common_rates_hit",
    "recompute_common_rates_pit",
    "reorder_detail_columns",
    "require_cols",
]
