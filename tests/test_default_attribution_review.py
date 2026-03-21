from __future__ import annotations

import pytest

from backend.core.dynasty_divergence_review import load_dynasty_benchmark, review_dynasty_divergence
from scripts.report_default_dynasty_divergence import (
    _common_roto_snapshot,
    _default_roto_params,
    _raw_start_year_snapshot,
)

pytestmark = [pytest.mark.full_regression, pytest.mark.slow, pytest.mark.valuation]


def test_default_standard_roto_attribution_pass_recommends_aggregation_followup() -> None:
    params = _default_roto_params()
    snapshot = _common_roto_snapshot(params=params)
    raw_snapshot = _raw_start_year_snapshot(params=params)
    review = review_dynasty_divergence(
        model_rows=snapshot["rows"],
        explanations=snapshot["explanations"],
        benchmark_entries=load_dynasty_benchmark(),
        raw_start_year_rows=raw_snapshot["rows"],
        start_year_projection_stats_by_entity=raw_snapshot["start_year_projection_stats_by_entity"],
        delta_threshold=15,
        top_n_absolute=999,
        methodology_fingerprint=str(snapshot["methodology_fingerprint"]),
    )

    assert review["attribution_recommendation"] == "recommend_aggregation_followup"

