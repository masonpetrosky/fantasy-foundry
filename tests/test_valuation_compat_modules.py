from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from backend.valuation import (
    common_math,
    common_math_compat,
    dynasty_aggregation,
    minor_eligibility,
    minor_eligibility_compat,
    projection_compat,
    projection_identity,
    xlsx_formatting,
)
from backend.valuation.models import CommonDynastyRotoSettings


def test_projection_compat_identity_wrapper_delegates() -> None:
    frame = pd.DataFrame([{"Date": "2026-01-01"}])
    with patch.object(projection_identity, "_find_projection_date_col", return_value="Date") as mocked:
        result = projection_compat._find_projection_date_col(frame)
    mocked.assert_called_once_with(frame)
    assert result == "Date"


def test_projection_compat_schema_and_rate_helpers_smoke() -> None:
    raw = pd.DataFrame(
        [
            {
                "player_name": "A",
                "team": "AAA",
                "Year": 2026,
                "AB": 100.0,
                "H": 30.0,
                "2B": 5.0,
                "3B": 1.0,
                "HR": 4.0,
                "BB": 10.0,
                "HBP": 2.0,
                "SF": 3.0,
            }
        ]
    )

    normalized = projection_compat.normalize_input_schema(raw, projection_compat.COMMON_COLUMN_ALIASES)
    projection_compat.require_cols(normalized, ["Player", "Team", "AB", "H"], "Bat")
    recomputed = projection_compat.recompute_common_rates_hit(normalized)

    assert list(normalized[["Player", "Team"]].iloc[0]) == ["A", "AAA"]
    assert recomputed.loc[0, "AVG"] == pytest.approx(0.3)
    assert recomputed.loc[0, "TB"] == pytest.approx(49.0)
    assert recomputed.loc[0, "OPS"] == pytest.approx(recomputed.loc[0, "OBP"] + recomputed.loc[0, "SLG"])


def test_projection_compat_xlsx_wrapper_delegates() -> None:
    ws = object()
    with patch.object(xlsx_formatting, "_xlsx_add_table", return_value=None) as mocked:
        projection_compat._xlsx_add_table(ws, table_name="PlayerValuesTbl", style_name="TableStyleLight1")
    mocked.assert_called_once_with(ws, table_name="PlayerValuesTbl", style_name="TableStyleLight1")


def test_common_math_compat_wrapper_delegates() -> None:
    values = np.array([1.0, 2.0, 3.0])
    with patch.object(common_math, "_mean_adjacent_rank_gap", return_value=1.5) as mocked:
        result = common_math_compat._mean_adjacent_rank_gap(values, ascending=False)
    mocked.assert_called_once_with(values, ascending=False)
    assert result == 1.5


def test_common_math_compat_team_ops_smoke() -> None:
    result = common_math_compat.team_ops(10.0, 2.0, 1.0, 20.0, 1.0, 2.0, 1.0, 3.0)
    assert result == pytest.approx((13.0 / 24.0) + (23.0 / 20.0))


def test_minor_eligibility_compat_wrapper_delegates() -> None:
    series = pd.Series([True, None], dtype="boolean")
    with patch.object(minor_eligibility, "_fillna_bool", return_value=series) as mocked:
        result = minor_eligibility_compat._fillna_bool(series, default=True)
    mocked.assert_called_once_with(series, default=True)
    assert result is series


def test_dynasty_aggregation_keep_or_drop_value() -> None:
    result = dynasty_aggregation.dynasty_keep_or_drop_value([5.0, -10.0, 4.0], [2026, 2027, 2028], 0.9)
    assert result == pytest.approx(5.0)

    with pytest.raises(ValueError, match="years must be increasing"):
        dynasty_aggregation.dynasty_keep_or_drop_value([1.0, 2.0], [2027, 2026], 0.9)


def test_common_math_compat_compute_year_context_delegates() -> None:
    bat = pd.DataFrame([{"Year": 2026}])
    pit = pd.DataFrame([{"Year": 2026}])
    lg = CommonDynastyRotoSettings()
    sentinel = object()
    with patch.object(common_math, "compute_year_context", return_value=sentinel) as mocked:
        result = common_math_compat.compute_year_context(2026, bat, pit, lg, rng_seed=7)
    mocked.assert_called_once_with(2026, bat, pit, lg, rng_seed=7)
    assert result is sentinel
