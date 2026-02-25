from __future__ import annotations

from unittest.mock import patch

import pandas as pd

import backend.dynasty_roto_values as dynasty_roto_values
from backend.valuation import xlsx_formatting


def test_wrapper_xlsx_apply_header_style_delegates_to_new_module() -> None:
    ws = object()
    sentinel = object()
    with patch.object(xlsx_formatting, "_xlsx_apply_header_style", return_value=sentinel) as mocked:
        result = dynasty_roto_values._xlsx_apply_header_style(ws)
    mocked.assert_called_once_with(ws)
    assert result is sentinel


def test_wrapper_xlsx_set_freeze_filters_and_view_delegates_to_new_module() -> None:
    ws = object()
    sentinel = object()
    with patch.object(xlsx_formatting, "_xlsx_set_freeze_filters_and_view", return_value=sentinel) as mocked:
        result = dynasty_roto_values._xlsx_set_freeze_filters_and_view(
            ws,
            freeze_panes="B2",
            add_autofilter=True,
        )
    mocked.assert_called_once_with(ws, freeze_panes="B2", add_autofilter=True)
    assert result is sentinel


def test_wrapper_xlsx_add_table_delegates_to_new_module() -> None:
    ws = object()
    sentinel = object()
    with patch.object(xlsx_formatting, "_xlsx_add_table", return_value=sentinel) as mocked:
        result = dynasty_roto_values._xlsx_add_table(ws, table_name="PlayerValuesTbl", style_name="TableStyleLight1")
    mocked.assert_called_once_with(ws, table_name="PlayerValuesTbl", style_name="TableStyleLight1")
    assert result is sentinel


def test_wrapper_xlsx_set_column_widths_delegates_to_new_module() -> None:
    ws = object()
    df = pd.DataFrame([{"Player": "A"}])
    sentinel = object()
    with patch.object(xlsx_formatting, "_xlsx_set_column_widths", return_value=sentinel) as mocked:
        result = dynasty_roto_values._xlsx_set_column_widths(
            ws,
            df,
            overrides={"Player": 20.0},
            sample_rows=50,
            min_width=5.0,
            max_width=30.0,
        )
    mocked.assert_called_once_with(
        ws,
        df,
        overrides={"Player": 20.0},
        sample_rows=50,
        min_width=5.0,
        max_width=30.0,
    )
    assert result is sentinel


def test_wrapper_xlsx_apply_number_formats_delegates_to_new_module() -> None:
    ws = object()
    df = pd.DataFrame([{"Age": 20}])
    sentinel = object()
    with patch.object(xlsx_formatting, "_xlsx_apply_number_formats", return_value=sentinel) as mocked:
        result = dynasty_roto_values._xlsx_apply_number_formats(ws, df, {"Age": "0"})
    mocked.assert_called_once_with(ws, df, {"Age": "0"})
    assert result is sentinel


def test_wrapper_xlsx_add_value_color_scale_delegates_to_new_module() -> None:
    ws = object()
    df = pd.DataFrame([{"DynastyValue": 1.0}])
    sentinel = object()
    with patch.object(xlsx_formatting, "_xlsx_add_value_color_scale", return_value=sentinel) as mocked:
        result = dynasty_roto_values._xlsx_add_value_color_scale(ws, df, "DynastyValue")
    mocked.assert_called_once_with(ws, df, "DynastyValue")
    assert result is sentinel


def test_wrapper_xlsx_format_player_values_delegates_to_new_module() -> None:
    ws = object()
    df = pd.DataFrame([{"Player": "A"}])
    sentinel = object()
    with patch.object(xlsx_formatting, "_xlsx_format_player_values", return_value=sentinel) as mocked:
        result = dynasty_roto_values._xlsx_format_player_values(ws, df, table_name="SummaryTbl")
    mocked.assert_called_once_with(ws, df, table_name="SummaryTbl")
    assert result is sentinel


def test_wrapper_xlsx_format_detail_sheet_delegates_to_new_module() -> None:
    ws = object()
    df = pd.DataFrame([{"Player": "A", "Year": 2026}])
    sentinel = object()
    with patch.object(xlsx_formatting, "_xlsx_format_detail_sheet", return_value=sentinel) as mocked:
        result = dynasty_roto_values._xlsx_format_detail_sheet(
            ws,
            df,
            table_name="DetailTbl",
            is_pitch=True,
        )
    mocked.assert_called_once_with(ws, df, table_name="DetailTbl", is_pitch=True)
    assert result is sentinel
