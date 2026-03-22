from __future__ import annotations

import pandas as pd
import pytest

from scripts.report_default_dynasty_divergence import (
    _imported_profile_review,
    _keeper_points_imported_params,
    _points_snapshot,
    _projection_refresh_context,
)

pytestmark = [pytest.mark.full_regression, pytest.mark.slow, pytest.mark.valuation]


def test_imported_profile_reviews_stay_within_current_error_bands() -> None:
    projection_data_version, projection_delta_details, has_previous_projection_snapshot, previous_projection_source = (
        _projection_refresh_context()
    )
    reviews = {
        profile_id: _imported_profile_review(
            profile_id=profile_id,
            benchmark_path=None,
            delta_threshold=15,
            top_n_absolute=25,
            projection_data_version=projection_data_version,
            projection_delta_details=projection_delta_details,
            has_previous_projection_snapshot=has_previous_projection_snapshot,
            previous_projection_source=previous_projection_source,
            overrides={},
        )
        for profile_id in ("shallow_roto_imported", "deep_roto_imported", "keeper_points_imported")
    }

    assert reviews["shallow_roto_imported"]["weighted_mean_absolute_rank_error"] < 85.0
    assert reviews["deep_roto_imported"]["weighted_mean_absolute_rank_error"] < 130.0
    assert reviews["keeper_points_imported"]["weighted_mean_absolute_rank_error"] < 89.5

    shallow_entries = {entry["player"]: entry for entry in reviews["shallow_roto_imported"]["entries"]}
    deep_entries = {entry["player"]: entry for entry in reviews["deep_roto_imported"]["entries"]}

    assert shallow_entries["Andres Munoz"]["model_rank"] < 150
    assert shallow_entries["Mason Miller"]["model_rank"] < 130
    assert shallow_entries["Bobby Witt Jr."]["model_rank"] == 1
    assert deep_entries["Andres Munoz"]["model_rank"] < 400
    assert deep_entries["Mason Miller"]["model_rank"] < 300
    assert deep_entries["Paul Skenes"]["model_rank"] <= 5


def test_keeper_points_imported_profile_keeps_current_production_inside_top_50() -> None:
    snapshot = _points_snapshot(params=_keeper_points_imported_params())
    rows = pd.DataFrame(snapshot["rows"]).sort_values("DynastyValue", ascending=False).reset_index(drop=True)
    ranks = {
        str(row.Player): idx + 1
        for idx, row in rows.iterrows()
    }

    assert int((pd.to_numeric(rows.head(50)["SelectedPoints"], errors="coerce").fillna(0.0) <= 0.0).sum()) == 0
    assert ranks["Shohei Ohtani"] <= 3
    assert ranks["Aaron Judge"] <= 10
    assert ranks["Paul Skenes"] < 20
    assert ranks["Tarik Skubal"] < 10
    assert ranks["Garrett Crochet"] < 17
    assert ranks["Kyle Tucker"] < 11
    assert ranks["Ronald Acuna Jr."] < 15
    assert ranks["Fernando Tatis Jr."] < 25
    assert ranks["Corbin Carroll"] < 30
    assert ranks["Julio Rodriguez"] < 35
    assert ranks["Bryan Woo"] < 70
    assert ranks["Logan Gilbert"] < 82
    assert ranks["Yoshinobu Yamamoto"] < 80
    assert ranks["Hunter Brown"] < 75
    assert ranks["Logan Webb"] < 65
    assert ranks["Mason Miller"] < 82
    assert ranks["Edwin Diaz"] < 92
    assert ranks["Cade Smith"] < 96
    assert ranks["Jarren Duran"] < 115
    assert ranks["Christian Yelich"] < 115
    assert ranks["Ian Happ"] < 110
    assert ranks["Taylor Ward"] < 110
    assert ranks["George Kirby"] < 100
    assert ranks["Joe Ryan"] < 105
    assert ranks["Juan Soto"] <= 5
    assert ranks["Bobby Witt Jr."] <= 3
    assert ranks["Vladimir Guerrero Jr."] <= 3
