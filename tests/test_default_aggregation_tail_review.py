from __future__ import annotations

import pytest

from backend.core.dynasty_divergence_review import load_dynasty_benchmark, review_dynasty_divergence
from scripts.report_default_dynasty_divergence import _default_roto_snapshot

pytestmark = [pytest.mark.full_regression, pytest.mark.slow, pytest.mark.valuation]

TARGET_PLAYERS = ("Aaron Judge", "Ronald Acuna Jr.", "Jose Ramirez")


def test_default_flat_control_routes_aggregation_targets_to_tail_review_without_shipping_change() -> None:
    rows, explanations, methodology_fingerprint = _default_roto_snapshot(overrides={"replacement_depth_mode": "flat"})
    review = review_dynasty_divergence(
        model_rows=rows,
        explanations=explanations,
        benchmark_entries=load_dynasty_benchmark(),
        delta_threshold=15,
        top_n_absolute=999,
        methodology_fingerprint=methodology_fingerprint,
    )
    entries = {
        str(entry.get("player") or ""): entry
        for entry in review["entries"]
        if isinstance(entry, dict) and str(entry.get("player") or "")
    }

    assert review["aggregation_tail_recommendation"] == "recommend_no_methodology_change_yet"
    for player in TARGET_PLAYERS:
        entry = entries[player]
        assert entry["triage_bucket"] == "aggregation_gap"
        assert entry["aggregation_tail_classification"] in {"short_positive_tail", "comp_horizon_gap", "mixed"}
