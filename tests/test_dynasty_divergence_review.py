from __future__ import annotations

from backend.core.dynasty_divergence_review import (
    aggregation_tail_recommendation,
    attribution_recommendation,
    classify_divergence,
    classify_aggregation_tail_gap,
    classify_attribution_layer,
    classify_deep_roto_change,
    classify_projection_delta,
    classify_raw_value_gap_cause,
    classify_suspect_gap_refresh_label,
    deep_roto_recommendation,
    explanation_review_metrics,
    load_dynasty_benchmark,
    render_deep_roto_markdown,
    render_deep_roto_memo_markdown,
    render_aggregation_gap_memo_markdown,
    render_attribution_memo_markdown,
    render_dynasty_divergence_memo_markdown,
    render_dynasty_divergence_markdown,
    render_projection_refresh_memo_markdown,
    render_slot_context_memo_markdown,
    projection_refresh_recommendation,
    review_deep_roto_profile,
    review_dynasty_divergence,
    review_slot_context_candidates,
    summarize_divergence_drivers,
    triage_bucket,
    weighted_mean_absolute_rank_error,
)


def test_summarize_divergence_drivers_surfaces_long_horizon_and_volume_flags() -> None:
    summary = summarize_divergence_drivers(
        {
            "profile": "hitter",
            "current_year_volume": {"ab": 280.0, "ip": 0.0},
            "per_year": [
                {"year": 2026, "discounted_contribution": 1.0, "prospect_risk_multiplier": 1.0},
                {"year": 2030, "discounted_contribution": 4.0, "prospect_risk_multiplier": 1.0},
                {"year": 2031, "discounted_contribution": 3.0, "prospect_risk_multiplier": 1.0},
            ],
        }
    )

    assert "long_horizon_weight" in summary["driver_reasons"]
    assert "light_start_year_ab" in summary["driver_reasons"]


def test_classify_divergence_flags_large_unexplained_gaps_as_suspect() -> None:
    classification = classify_divergence(
        model_rank=32,
        benchmark_rank=6,
        explanation={"per_year": [], "current_year_volume": {"ab": 550.0, "ip": 0.0}},
        delta_threshold=15,
    )

    assert classification == "suspect_model_gap"


def test_explanation_review_metrics_extracts_discounted_totals_and_positive_year_stats() -> None:
    metrics = explanation_review_metrics(
        {
            "start_year_best_slot": "OF",
            "start_year_replacement_pool_depth": 24,
            "start_year_replacement_depth_mode": "half_depth",
            "start_year_replacement_depth_blend_alpha": 0.25,
            "start_year_slot_count_per_team": 5,
            "start_year_slot_capacity_league": 60,
            "start_year_category_sgp": {"R": 1.5},
            "per_year": [
                {"year": 2026, "year_value": 10.0, "adjusted_year_value_before_discount": 10.0, "discounted_contribution": 10.0},
                {"year": 2027, "year_value": 8.0, "adjusted_year_value_before_discount": 8.0, "discounted_contribution": 7.5},
                {"year": 2028, "year_value": -1.0, "adjusted_year_value_before_discount": -1.0, "discounted_contribution": 0.0},
                {"year": 2029, "year_value": 3.0, "adjusted_year_value_before_discount": 3.0, "discounted_contribution": 2.0},
            ]
        }
    )

    assert metrics["start_year"] == 2026
    assert metrics["start_year_value"] == 10.0
    assert metrics["discounted_three_year_total"] == 17.5
    assert metrics["discounted_full_total"] == 19.5
    assert metrics["positive_year_count"] == 3
    assert metrics["last_positive_year"] == 2029
    assert metrics["start_year_best_slot"] == "OF"
    assert metrics["start_year_category_sgp"] == {"R": 1.5}
    assert metrics["start_year_replacement_pool_depth"] == 24
    assert metrics["start_year_replacement_depth_mode"] == "half_depth"
    assert metrics["start_year_replacement_depth_blend_alpha"] == 0.25
    assert metrics["start_year_slot_count_per_team"] == 5
    assert metrics["start_year_slot_capacity_league"] == 60
    assert metrics["first_near_zero_year"] is None
    assert metrics["first_non_positive_adjusted_year"] == 2028
    assert metrics["positive_year_span"] == 4
    assert metrics["tail_value_after_year_3"] == 2.0
    assert metrics["tail_share_after_year_3"] == 0.1026
    assert metrics["tail_preview"][0]["year"] == 2026


def test_classify_aggregation_tail_gap_prefers_comp_horizon_gap_when_comps_last_longer() -> None:
    assert (
        classify_aggregation_tail_gap(
            triage_bucket="aggregation_gap",
            start_year_rank=9,
            positive_year_count=4,
            tail_share_after_year_3=0.08,
            comp_positive_year_counts=[7, 6, 8],
        )
        == "comp_horizon_gap"
    )
    assert (
        classify_aggregation_tail_gap(
            triage_bucket="aggregation_gap",
            start_year_rank=21,
            positive_year_count=5,
            tail_share_after_year_3=0.16,
            comp_positive_year_counts=[7, 6, 8],
        )
        == "mixed"
    )


def test_classify_raw_value_gap_cause_prefers_bounds_then_guard_then_volume() -> None:
    assert (
        classify_raw_value_gap_cause(
            {
                "profile": "pitcher",
                "start_year_bounds_summary": {"applied": True},
                "start_year_guard_summary": {"positive_credit_scale": 0.5},
                "current_year_volume": {"ab": 0.0, "ip": 90.0},
            }
        )
        == "pitching_bounds"
    )
    assert (
        classify_raw_value_gap_cause(
            {
                "profile": "hitter",
                "start_year_best_slot": "OF",
                "start_year_guard_summary": {"positive_credit_scale": 0.8},
                "current_year_volume": {"ab": 510.0, "ip": 0.0},
            }
        )
        == "guard_attenuation"
    )
    assert (
        classify_raw_value_gap_cause(
            {
                "profile": "hitter",
                "start_year_best_slot": "OF",
                "current_year_volume": {"ab": 320.0, "ip": 0.0},
            }
        )
        == "projected_volume"
    )


def test_triage_bucket_splits_aggregation_from_raw_value_gaps() -> None:
    assert triage_bucket(abs_rank_delta=20, start_year_rank=12, delta_threshold=15) == "aggregation_gap"
    assert triage_bucket(abs_rank_delta=20, start_year_rank=40, delta_threshold=15) == "raw_value_gap"
    assert triage_bucket(abs_rank_delta=20, start_year_rank=28, delta_threshold=15) == "mixed_gap"
    assert triage_bucket(abs_rank_delta=10, start_year_rank=12, delta_threshold=15) is None


def test_projection_delta_classification_and_refresh_label() -> None:
    assert (
        classify_projection_delta(
            projection_delta_detail={"composite_delta": 12.5},
            has_previous_projection_snapshot=True,
        )
        == "material_riser"
    )
    assert (
        classify_projection_delta(
            projection_delta_detail={"composite_delta": -14.0},
            has_previous_projection_snapshot=True,
        )
        == "material_faller"
    )
    assert (
        classify_projection_delta(
            projection_delta_detail={"composite_delta": 0.0},
            has_previous_projection_snapshot=True,
        )
        == "stable"
    )
    assert (
        classify_projection_delta(
            projection_delta_detail=None,
            has_previous_projection_snapshot=False,
        )
        == "missing_previous_snapshot"
    )
    assert (
        classify_suspect_gap_refresh_label(
            classification="suspect_model_gap",
            projection_delta_type="stable",
        )
        == "stable_model_gap"
    )
    assert (
        classify_suspect_gap_refresh_label(
            classification="suspect_model_gap",
            projection_delta_type="material_riser",
        )
        == "player_projection_shift"
    )
    assert (
        classify_suspect_gap_refresh_label(
            classification="suspect_model_gap",
            projection_delta_type="missing_previous_snapshot",
        )
        == "manual_review"
    )


def test_classify_attribution_layer_splits_projection_roto_aggregation_and_mixed() -> None:
    assert (
        classify_attribution_layer(
            benchmark_rank=20,
            raw_start_year_rank=35,
            start_year_rank=30,
            model_rank=28,
        )
        == "projection_shape_gap"
    )
    assert (
        classify_attribution_layer(
            benchmark_rank=20,
            raw_start_year_rank=28,
            start_year_rank=35,
            model_rank=34,
        )
        == "roto_conversion_gap"
    )
    assert (
        classify_attribution_layer(
            benchmark_rank=20,
            raw_start_year_rank=18,
            start_year_rank=25,
            model_rank=40,
        )
        == "dynasty_aggregation_gap"
    )
    assert (
        classify_attribution_layer(
            benchmark_rank=20,
            raw_start_year_rank=18,
            start_year_rank=24,
            model_rank=28,
        )
        == "mixed_gap"
    )


def test_attribution_recommendation_prefers_projection_then_roto_then_aggregation_thresholds() -> None:
    projection_entries = [
        {"player": f"Player {idx}", "attribution_class": "projection_shape_gap"}
        for idx in range(1, 5)
    ]
    assert (
        attribution_recommendation(
            projection_entries,
            target_players=tuple(f"Player {idx}" for idx in range(1, 5)),
        )
        == "recommend_projection_input_reaudit"
    )

    roto_entries = [
        {"player": f"Player {idx}", "attribution_class": "roto_conversion_gap"}
        for idx in range(1, 5)
    ]
    assert (
        attribution_recommendation(
            roto_entries,
            target_players=tuple(f"Player {idx}" for idx in range(1, 5)),
        )
        == "recommend_roto_conversion_followup"
    )

    aggregation_entries = [
        {"player": f"Player {idx}", "attribution_class": "dynasty_aggregation_gap"}
        for idx in range(1, 5)
    ]
    assert (
        attribution_recommendation(
            aggregation_entries,
            target_players=tuple(f"Player {idx}" for idx in range(1, 5)),
        )
        == "recommend_aggregation_followup"
    )

    mixed_entries = [
        {"player": f"Player {idx}", "attribution_class": "mixed_gap"}
        for idx in range(1, 5)
    ]
    assert (
        attribution_recommendation(
            mixed_entries,
            target_players=tuple(f"Player {idx}" for idx in range(1, 5)),
        )
        == "recommend_no_change_yet"
    )


def test_weighted_mean_absolute_rank_error_uses_top_rank_weights() -> None:
    score = weighted_mean_absolute_rank_error(
        [
            {"benchmark_rank": 5, "abs_rank_delta": 10},
            {"benchmark_rank": 20, "abs_rank_delta": 5},
            {"benchmark_rank": 70, "abs_rank_delta": 2},
        ]
    )

    assert score == 7.0


def test_review_dynasty_divergence_joins_rows_and_renders_markdown() -> None:
    review = review_dynasty_divergence(
        model_rows=[
            {"Player": "Corbin Carroll", "Team": "ARI", "DynastyValue": 10.0, "PlayerEntityKey": "corbin-carroll"},
            {"Player": "Bobby Witt Jr.", "Team": "KC", "DynastyValue": 20.0, "PlayerEntityKey": "bobby-witt-jr"},
        ],
        explanations={
            "corbin-carroll": {
                "profile": "hitter",
                "current_year_volume": {"ab": 280.0, "ip": 0.0},
                "start_year_best_slot": "OF",
                "start_year_replacement_pool_depth": 36,
                "start_year_replacement_depth_mode": "blended_depth",
                "start_year_replacement_depth_blend_alpha": 0.33,
                "start_year_slot_count_per_team": 5,
                "start_year_slot_capacity_league": 60,
                "start_year_top_positive_categories": [{"category": "SB", "value": 1.5}],
                "start_year_top_negative_categories": [{"category": "AVG", "value": -0.3}],
                "start_year_replacement_reference": {
                    "slot": "OF",
                    "replacement_pool_depth": 36,
                    "replacement_depth_mode": "blended_depth",
                    "replacement_depth_blend_alpha": 0.33,
                    "slot_count_per_team": 5,
                    "slot_capacity_league": 60,
                    "volume": {"ab": 422.6, "ip": 0.0},
                },
                "start_year_guard_summary": {"mode": "none", "positive_credit_scale": 1.0, "workload_share": 0.7},
                "per_year": [
                    {"year": 2026, "year_value": 12.0, "adjusted_year_value_before_discount": 12.0, "discounted_contribution": 1.0},
                    {"year": 2030, "year_value": 5.0, "adjusted_year_value_before_discount": 5.0, "discounted_contribution": 3.0},
                ],
            },
            "bobby-witt-jr": {
                "profile": "hitter",
                "current_year_volume": {"ab": 600.0, "ip": 0.0},
                "start_year_best_slot": "SS",
                "per_year": [{"year": 2026, "year_value": 5.0, "adjusted_year_value_before_discount": 5.0, "discounted_contribution": 5.0}],
            },
        },
        benchmark_entries=[
            {"player": "Corbin Carroll", "player_key": "corbin-carroll", "benchmark_rank": 20, "source": "fixture"},
            {"player": "Bobby Witt Jr.", "player_key": "bobby-witt-jr", "benchmark_rank": 1, "source": "fixture"},
        ],
        raw_start_year_rows=[
            {
                "Player": "Corbin Carroll",
                "PlayerKey": "corbin-carroll",
                "PlayerEntityKey": "corbin-carroll",
                "BestSlot": "OF",
                "YearValue": 18.0,
                "SGP_SB": 2.1,
                "SGP_AVG": -0.2,
            },
            {
                "Player": "Bobby Witt Jr.",
                "PlayerKey": "bobby-witt-jr",
                "PlayerEntityKey": "bobby-witt-jr",
                "BestSlot": "SS",
                "YearValue": 22.0,
                "SGP_HR": 1.8,
                "SGP_SB": 0.9,
            },
        ],
        start_year_projection_stats_by_entity={
            "corbin-carroll": {
                "AB": 280.0,
                "R": 70.0,
                "HR": 14.0,
                "RBI": 56.0,
                "SB": 31.0,
                "AVG": 0.261,
                "OPS": 0.790,
            },
            "bobby-witt-jr": {
                "AB": 620.0,
                "R": 108.0,
                "HR": 30.0,
                "RBI": 101.0,
                "SB": 34.0,
                "AVG": 0.294,
                "OPS": 0.901,
            },
        },
        delta_threshold=15,
        top_n_absolute=5,
        methodology_fingerprint="abc123",
        projection_data_version="data-v1",
        projection_delta_details={
            "corbin-carroll": {
                "composite_delta": 0.0,
                "deltas": {"SB": 1.5, "R": -0.5, "HR": 0.25},
            },
            "bobby-witt-jr": {
                "composite_delta": 12.0,
                "deltas": {"SB": 4.0, "R": 3.0, "HR": 1.0},
            },
        },
        has_previous_projection_snapshot=True,
        previous_projection_source="bat_prev/pit_prev",
    )

    assert review["classification_counts"]["explained"] == 2
    assert review["profile_id"] == "standard_roto"
    assert review["entries"][0]["player"] == "Corbin Carroll"
    assert review["entries"][0]["start_year_rank"] == 1
    assert review["entries"][0]["triage_bucket"] == "aggregation_gap"
    assert review["entries"][0]["start_year_best_slot"] == "OF"
    assert review["entries"][0]["raw_value_gap_cause"] == "projected_volume"
    assert review["entries"][0]["start_year_replacement_depth_mode"] == "blended_depth"
    assert review["entries"][0]["start_year_replacement_depth_blend_alpha"] == 0.33
    assert review["entries"][0]["start_year_replacement_pool_depth"] == 36
    assert review["entries"][0]["absolute_benchmark_error"] == 18
    assert review["entries"][0]["raw_start_year_rank"] == 2
    assert review["entries"][0]["raw_start_year_best_slot"] == "OF"
    assert review["entries"][0]["raw_to_replacement_rank_delta"] == -1
    assert review["entries"][0]["replacement_to_dynasty_rank_delta"] == 1
    assert review["entries"][0]["start_year_projection_stats"]["SB"] == 31.0
    assert review["entries"][0]["attribution_class"] == "mixed_gap"
    assert review["entries"][0]["aggregation_tail_classification"] == "short_positive_tail"
    assert review["entries"][0]["projection_delta_type"] == "stable"
    assert review["entries"][0]["suspect_gap_refresh_label"] is None
    assert review["projection_data_version"] == "data-v1"
    assert review["has_previous_projection_snapshot"] is True
    assert review["previous_projection_source"] == "bat_prev/pit_prev"
    assert review["slot_mover_summaries"]["OF"][0]["player"] == "Corbin Carroll"
    assert review["attribution_counts"]["mixed_gap"] == 2
    markdown = render_dynasty_divergence_markdown(review)
    assert "Default Dynasty Divergence Review" in markdown
    assert "Corbin Carroll" in markdown
    assert "aggregation_gap" in markdown
    assert "`abc123`" in markdown
    assert "`data-v1`" in markdown
    assert "Settings snapshot" in markdown
    assert "OF Movers" in markdown

    memo = render_dynasty_divergence_memo_markdown(review, target_players=["Corbin Carroll"])
    assert "Default Dynasty Divergence Memo" in memo
    assert "Players immediately above in model rank" in memo
    assert "Bucket Summaries" in memo
    assert "Primary raw-value cause" in memo
    assert "mode=blended_depth" in memo
    assert "blend_alpha=0.33" in memo
    assert "Refresh label" in memo
    assert "Settings snapshot" in memo

    attribution_memo = render_attribution_memo_markdown(review, target_players=["Corbin Carroll"])
    assert "Default Dynasty Attribution Memo" in attribution_memo
    assert "raw start-year rank" in attribution_memo
    assert "Start-year projection snapshot" in attribution_memo
    assert "`recommend_no_change_yet`" in attribution_memo

    refresh_memo = render_projection_refresh_memo_markdown(review, target_players=["Corbin Carroll"])
    assert "Default Dynasty Projection Refresh Memo" in refresh_memo
    assert "Projection delta" in refresh_memo
    assert "`recommend_refresh_specific_reaudit`" in refresh_memo
    assert "Settings snapshot" in refresh_memo


def test_classify_deep_roto_change_prefers_stash_then_category_mix_then_forced_roster() -> None:
    assert (
        classify_deep_roto_change(
            standard_entry={"tail_share_after_year_3": 0.20},
            deep_entry={
                "tail_share_after_year_3": 0.15,
                "explanation": {
                    "centering": {"mode": "forced_roster_minor_cost", "minor_slot_cost_value": -0.12},
                    "per_year": [],
                },
            },
        )
        == "stash_economics"
    )
    assert (
        classify_deep_roto_change(
            standard_entry={"tail_share_after_year_3": 0.20},
            deep_entry={
                "tail_share_after_year_3": 0.15,
                "explanation": {"stat_dynasty_contributions": {"OPS": 3.2, "HR": 1.0}},
            },
        )
        == "category_mix"
    )
    assert (
        classify_deep_roto_change(
            standard_entry={"tail_share_after_year_3": 0.20},
            deep_entry={
                "tail_share_after_year_3": 0.15,
                "explanation": {"centering": {"mode": "forced_roster", "fallback_applied": True}},
            },
        )
        == "forced_roster_centering"
    )


def test_review_deep_roto_profile_renders_memo_and_recommendation() -> None:
    review = review_deep_roto_profile(
        deep_model_rows=[
            {
                "Player": "Roman Anthony",
                "Team": "BOS",
                "Pos": "OF",
                "DynastyValue": 14.0,
                "PlayerEntityKey": "roman-anthony",
                "PlayerKey": "roman-anthony",
            },
            {
                "Player": "Cal Raleigh",
                "Team": "SEA",
                "Pos": "C",
                "DynastyValue": 12.0,
                "PlayerEntityKey": "cal-raleigh",
                "PlayerKey": "cal-raleigh",
            },
        ],
        deep_explanations={
            "roman-anthony": {
                "pos": "OF",
                "start_year_best_slot": "OF",
                "start_year_top_positive_categories": [{"category": "OPS", "value": 1.2}],
                "start_year_top_negative_categories": [{"category": "SB", "value": -0.2}],
                "start_year_replacement_reference": {"slot": "OF", "replacement_pool_depth": 48},
                "start_year_slot_baseline_reference": {"slot": "OF", "replacement_pool_depth": 48},
                "stat_dynasty_contributions": {"OPS": 3.2, "HR": 1.1},
                "centering": {"mode": "forced_roster_minor_cost", "fallback_applied": True, "forced_roster_value": -0.3},
                "per_year": [
                    {
                        "year": 2026,
                        "year_value": 8.0,
                        "adjusted_year_value_before_discount": 8.0,
                        "discounted_contribution": 8.0,
                        "stash_adjustment_applied": True,
                    }
                ],
            },
            "cal-raleigh": {
                "pos": "C",
                "start_year_best_slot": "C",
                "start_year_top_positive_categories": [{"category": "OPS", "value": 0.8}],
                "start_year_replacement_reference": {"slot": "C", "replacement_pool_depth": 24},
                "start_year_slot_baseline_reference": {"slot": "C", "replacement_pool_depth": 24},
                "stat_dynasty_contributions": {"OPS": 2.4, "HR": 0.9},
                "centering": {"mode": "standard", "fallback_applied": False, "forced_roster_value": 0.0},
                "per_year": [
                    {
                        "year": 2026,
                        "year_value": 7.0,
                        "adjusted_year_value_before_discount": 7.0,
                        "discounted_contribution": 7.0,
                    }
                ],
            },
        },
        deep_valuation_diagnostics={
            "CenteringMode": "forced_roster_minor_cost",
            "ForcedRosterFallbackApplied": True,
            "ResidualMinorSlotCostApplied": True,
            "deep_roster_zero_baseline_warning": True,
        },
        standard_model_rows=[
            {
                "Player": "Roman Anthony",
                "Team": "BOS",
                "Pos": "OF",
                "DynastyValue": 8.0,
                "PlayerEntityKey": "roman-anthony",
                "PlayerKey": "roman-anthony",
            },
            {
                "Player": "Cal Raleigh",
                "Team": "SEA",
                "Pos": "C",
                "DynastyValue": 4.0,
                "PlayerEntityKey": "cal-raleigh",
                "PlayerKey": "cal-raleigh",
            },
        ],
        standard_explanations={
            "roman-anthony": {
                "pos": "OF",
                "start_year_best_slot": "OF",
                "per_year": [
                    {
                        "year": 2026,
                        "year_value": 5.0,
                        "adjusted_year_value_before_discount": 5.0,
                        "discounted_contribution": 5.0,
                    }
                ],
            },
            "cal-raleigh": {
                "pos": "C",
                "start_year_best_slot": "C",
                "per_year": [
                    {
                        "year": 2026,
                        "year_value": 3.0,
                        "adjusted_year_value_before_discount": 3.0,
                        "discounted_contribution": 3.0,
                    }
                ],
            },
        },
        projection_data_version="data-v1",
        methodology_fingerprint="deep123",
        settings_snapshot={"teams": 12, "bench": 14, "minors": 20},
    )

    assert review["profile_id"] == "deep_roto"
    assert review["recommendation"] in {
        "recommend_deep_roto_methodology_followup",
        "recommend_no_deep_specific_change_yet",
    }
    assert deep_roto_recommendation(review["entries"], target_players=("Roman Anthony", "Cal Raleigh")) in {
        "recommend_deep_roto_methodology_followup",
        "recommend_no_deep_specific_change_yet",
    }
    markdown = render_deep_roto_markdown(review)
    assert "Deep Dynasty Roto Audit Review" in markdown
    assert "Roman Anthony" in markdown
    memo = render_deep_roto_memo_markdown(review, target_players=("Roman Anthony", "Cal Raleigh"))
    assert "Deep Dynasty Roto Audit Memo" in memo
    assert "Settings snapshot" in memo
    assert "`deep_roto`" in memo


def _slot_context_control_review() -> dict[str, object]:
    base_players = {
        "Yordan Alvarez": (40, 60, 42, 11.0, "OF"),
        "Kyle Tucker": (55, 70, 52, 10.5, "OF"),
        "Fernando Tatis Jr.": (65, 80, 63, 10.0, "OF"),
        "Aaron Judge": (75, 90, 71, 12.0, "OF"),
        "Ronald Acuna Jr.": (85, 100, 82, 11.5, "OF"),
        "Yoshinobu Yamamoto": (35, 50, 33, 9.5, "P"),
        "Bryan Woo": (60, 75, 58, 8.5, "P"),
        "Jose Ramirez": (35, 40, 18, 12.5, "3B"),
        "Corbin Carroll": (30, 30, 20, 10.2, "OF"),
        "Roman Anthony": (34, 34, 24, 9.8, "OF"),
        "Wyatt Langford": (44, 44, 32, 9.4, "OF"),
        "Pete Crow-Armstrong": (54, 54, 41, 8.9, "OF"),
        "Juan Soto": (5, 5, 6, 13.0, "OF"),
        "Julio Rodriguez": (10, 10, 10, 12.2, "OF"),
        "Paul Skenes": (2, 2, 4, 13.4, "P"),
        "Tarik Skubal": (8, 8, 8, 12.6, "P"),
    }
    entries = []
    for player, (benchmark_rank, model_rank, start_year_rank, start_year_value, slot) in base_players.items():
        entries.append(
            {
                "player": player,
                "benchmark_rank": benchmark_rank,
                "model_rank": model_rank,
                "absolute_benchmark_error": abs(model_rank - benchmark_rank),
                "start_year_rank": start_year_rank,
                "start_year_value": start_year_value,
                "discounted_three_year_total": round(start_year_value * 2.0, 4),
                "discounted_full_total": round(start_year_value * 3.0, 4),
                "start_year_best_slot": slot,
                "start_year_replacement_reference": {
                    "slot": slot,
                    "replacement_pool_depth": 36 if slot == "OF" else 24,
                    "replacement_depth_mode": "blended_depth",
                    "replacement_depth_blend_alpha": 0.33,
                    "slot_count_per_team": 5 if slot == "OF" else 9,
                    "slot_capacity_league": 60 if slot == "OF" else 108,
                    "volume": {"ab": 430.0 if slot == "OF" else 0.0, "ip": 0.0 if slot == "OF" else 145.0},
                },
            }
        )
    return {
        "profile_id": "standard_roto",
        "projection_data_version": "data-v1",
        "methodology_fingerprint": "control123",
        "weighted_mean_absolute_rank_error": 12.0,
        "settings_snapshot": {"replacement_depth_blend_alpha": 0.33},
        "entries": entries,
    }


def _slot_context_candidate_review(
    control_review: dict[str, object],
    *,
    weighted_mae: float,
    of_alpha: float,
    p_alpha: float,
    dynasty_rank_changes: dict[str, int] | None = None,
    start_year_rank_changes: dict[str, int] | None = None,
) -> dict[str, object]:
    dynasty_rank_changes = dynasty_rank_changes or {}
    start_year_rank_changes = start_year_rank_changes or {}
    control_entries = {
        str(entry["player"]): entry
        for entry in control_review["entries"]  # type: ignore[index]
        if isinstance(entry, dict)
    }
    entries = []
    for player, control_entry in control_entries.items():
        model_rank = int(control_entry["model_rank"]) - int(dynasty_rank_changes.get(player, 0))
        start_year_rank = int(control_entry["start_year_rank"]) - int(start_year_rank_changes.get(player, 0))
        start_year_value = float(control_entry["start_year_value"]) + (0.1 * float(start_year_rank_changes.get(player, 0)))
        replacement_reference = dict(control_entry["start_year_replacement_reference"])
        replacement_reference["replacement_depth_blend_alpha"] = of_alpha if replacement_reference["slot"] == "OF" else p_alpha
        entries.append(
            {
                **control_entry,
                "model_rank": model_rank,
                "absolute_benchmark_error": abs(model_rank - int(control_entry["benchmark_rank"])),
                "start_year_rank": start_year_rank,
                "start_year_value": round(start_year_value, 4),
                "discounted_three_year_total": round(
                    float(control_entry["discounted_three_year_total"]) + (0.2 * float(dynasty_rank_changes.get(player, 0))),
                    4,
                ),
                "discounted_full_total": round(
                    float(control_entry["discounted_full_total"]) + (0.3 * float(dynasty_rank_changes.get(player, 0))),
                    4,
                ),
                "start_year_replacement_reference": replacement_reference,
            }
        )
    settings_snapshot: dict[str, object] = {"replacement_depth_blend_alpha": 0.33}
    if abs(of_alpha - 0.33) > 1e-9 or abs(p_alpha - 0.33) > 1e-9:
        settings_snapshot["replacement_depth_blend_alpha_by_slot"] = {"OF": of_alpha, "P": p_alpha}
    return {
        "profile_id": "standard_roto",
        "projection_data_version": "data-v1",
        "methodology_fingerprint": f"candidate-{of_alpha:.2f}-{p_alpha:.2f}",
        "weighted_mean_absolute_rank_error": weighted_mae,
        "settings_snapshot": settings_snapshot,
        "entries": entries,
    }


def test_review_slot_context_candidates_selects_of_pilot_and_tracks_benchmark_error_deltas() -> None:
    control_review = _slot_context_control_review()
    candidate_reviews = {
        "A": _slot_context_candidate_review(
            control_review,
            weighted_mae=11.0,
            of_alpha=0.25,
            p_alpha=0.33,
            dynasty_rank_changes={
                "Yordan Alvarez": 10,
                "Kyle Tucker": 10,
                "Fernando Tatis Jr.": 9,
                "Aaron Judge": 8,
                "Ronald Acuna Jr.": 8,
                "Corbin Carroll": -2,
            },
            start_year_rank_changes={
                "Yordan Alvarez": 4,
                "Kyle Tucker": 4,
                "Fernando Tatis Jr.": 3,
                "Aaron Judge": 3,
                "Ronald Acuna Jr.": 3,
            },
        ),
        "C": _slot_context_candidate_review(
            control_review,
            weighted_mae=11.8,
            of_alpha=0.33,
            p_alpha=0.25,
            dynasty_rank_changes={
                "Yoshinobu Yamamoto": 9,
                "Bryan Woo": 8,
                "Tarik Skubal": -5,
            },
            start_year_rank_changes={
                "Yoshinobu Yamamoto": 3,
                "Bryan Woo": 2,
            },
        ),
        "E": _slot_context_candidate_review(
            control_review,
            weighted_mae=10.8,
            of_alpha=0.25,
            p_alpha=0.25,
            dynasty_rank_changes={
                "Yordan Alvarez": 10,
                "Kyle Tucker": 10,
                "Fernando Tatis Jr.": 9,
                "Aaron Judge": 8,
                "Ronald Acuna Jr.": 8,
                "Yoshinobu Yamamoto": 9,
                "Bryan Woo": 8,
                "Corbin Carroll": -7,
            },
            start_year_rank_changes={
                "Yordan Alvarez": 4,
                "Kyle Tucker": 4,
                "Fernando Tatis Jr.": 3,
                "Aaron Judge": 3,
                "Ronald Acuna Jr.": 3,
                "Yoshinobu Yamamoto": 3,
                "Bryan Woo": 2,
            },
        ),
    }

    review = review_slot_context_candidates(
        control_review=control_review,
        candidate_reviews=candidate_reviews,
    )

    assert review["recommendation"] == "recommend_of_split_alpha_pilot"
    candidate_summary_by_id = {
        str(entry["candidate_id"]): entry
        for entry in review["candidate_summaries"]  # type: ignore[index]
        if isinstance(entry, dict)
    }
    assert candidate_summary_by_id["A"]["passes_of_guard"] is True
    assert candidate_summary_by_id["C"]["passes_p_guard"] is False
    yordan_delta = {
        str(entry["player"]): entry
        for entry in candidate_summary_by_id["A"]["player_deltas"]  # type: ignore[index]
        if isinstance(entry, dict)
    }["Yordan Alvarez"]
    assert yordan_delta["absolute_benchmark_error_change_vs_control"] == -10
    memo = render_slot_context_memo_markdown(review, target_players=("Yordan Alvarez", "Jose Ramirez"))
    assert "Default Dynasty Slot-Context Memo" in memo
    assert "`recommend_of_split_alpha_pilot`" in memo
    assert "benchmark error change -10" in memo
    assert "OF=0.25, P=0.33" in memo


def test_review_slot_context_candidates_recommends_no_change_when_all_candidates_fail_guards() -> None:
    control_review = _slot_context_control_review()
    candidate_reviews = {
        "A": _slot_context_candidate_review(
            control_review,
            weighted_mae=11.7,
            of_alpha=0.25,
            p_alpha=0.33,
            dynasty_rank_changes={
                "Yordan Alvarez": 8,
                "Kyle Tucker": 8,
                "Fernando Tatis Jr.": 7,
                "Aaron Judge": 7,
                "Ronald Acuna Jr.": 7,
                "Juan Soto": -8,
            },
        ),
        "C": _slot_context_candidate_review(
            control_review,
            weighted_mae=11.7,
            of_alpha=0.33,
            p_alpha=0.25,
            dynasty_rank_changes={
                "Yoshinobu Yamamoto": 7,
                "Bryan Woo": 7,
                "Paul Skenes": -5,
            },
        ),
    }

    review = review_slot_context_candidates(
        control_review=control_review,
        candidate_reviews=candidate_reviews,
    )

    assert review["recommendation"] == "recommend_no_slot_context_change_yet"


def test_render_aggregation_gap_memo_markdown_and_recommendation() -> None:
    review = {
        "benchmark_player_count": 30,
        "projection_data_version": "data-v1",
        "methodology_fingerprint": "abc123",
        "weighted_mean_absolute_rank_error": 16.7,
        "triage_counts": {"aggregation_gap": 3},
        "entries": [
            {
                "player": "Aaron Judge",
                "benchmark_rank": 14,
                "model_rank": 51,
                "start_year_rank": 9,
                "discounted_three_year_total": 29.13,
                "discounted_full_total": 31.56,
                "positive_year_count": 4,
                "last_positive_year": 2029,
                "first_near_zero_year": 2030,
                "first_non_positive_adjusted_year": 2030,
                "positive_year_span": 4,
                "tail_value_after_year_3": 2.43,
                "tail_share_after_year_3": 0.077,
                "tail_preview": [{"year": 2026, "adjusted_year_value_before_discount": 12.9, "discounted_contribution": 12.9}],
                "aggregation_tail_classification": "comp_horizon_gap",
                "aggregation_comp_positive_year_count_median": 7.0,
                "projection_composite_delta": 0.0,
                "projection_delta_type": "stable",
                "projection_top_stat_deltas": [{"stat": "HR", "delta": 0.0}],
                "model_comps_above": [
                    {
                        "player": "CJ Abrams",
                        "model_rank": 49,
                        "start_year_rank": 35,
                        "positive_year_count": 7,
                        "first_near_zero_year": 2033,
                        "tail_share_after_year_3": 0.24,
                    }
                ],
            },
            {
                "player": "Ronald Acuna Jr.",
                "benchmark_rank": 10,
                "model_rank": 47,
                "start_year_rank": 21,
                "discounted_three_year_total": 26.63,
                "discounted_full_total": 32.32,
                "positive_year_count": 5,
                "last_positive_year": 2030,
                "first_near_zero_year": 2031,
                "first_non_positive_adjusted_year": 2031,
                "positive_year_span": 5,
                "tail_value_after_year_3": 5.69,
                "tail_share_after_year_3": 0.176,
                "tail_preview": [],
                "aggregation_tail_classification": "mixed",
                "aggregation_comp_positive_year_count_median": 6.0,
                "projection_composite_delta": 0.0,
                "projection_delta_type": "stable",
                "projection_top_stat_deltas": [],
                "model_comps_above": [],
            },
            {
                "player": "Jose Ramirez",
                "benchmark_rank": 22,
                "model_rank": 41,
                "start_year_rank": 7,
                "discounted_three_year_total": 31.26,
                "discounted_full_total": 34.05,
                "positive_year_count": 4,
                "last_positive_year": 2029,
                "first_near_zero_year": 2030,
                "first_non_positive_adjusted_year": 2030,
                "positive_year_span": 4,
                "tail_value_after_year_3": 2.79,
                "tail_share_after_year_3": 0.082,
                "tail_preview": [],
                "aggregation_tail_classification": "comp_horizon_gap",
                "aggregation_comp_positive_year_count_median": 6.0,
                "projection_composite_delta": 0.0,
                "projection_delta_type": "stable",
                "projection_top_stat_deltas": [],
                "model_comps_above": [],
            },
        ],
    }

    assert aggregation_tail_recommendation(review["entries"]) == "recommend_no_methodology_change_yet"
    memo = render_aggregation_gap_memo_markdown(review)
    assert "Default Dynasty Aggregation-Gap Memo" in memo
    assert "first near-zero year 2030" in memo
    assert "CJ Abrams" in memo
    assert "`recommend_no_methodology_change_yet`" in memo
    assert "`data-v1`" in memo


def test_projection_refresh_recommendation_prefers_resume_when_stable_gap_count_crosses_threshold() -> None:
    entries = [
        {"player": f"Player {idx}", "suspect_gap_refresh_label": "stable_model_gap"}
        for idx in range(1, 8)
    ] + [
        {"player": f"Player {idx}", "suspect_gap_refresh_label": "player_projection_shift"}
        for idx in range(8, 13)
    ]

    assert (
        projection_refresh_recommendation(
            entries,
            target_players=tuple(f"Player {idx}" for idx in range(1, 13)),
        )
        == "recommend_resume_model_gap_work"
    )


def test_default_benchmark_fixture_covers_top_30_market_snapshot() -> None:
    benchmark = load_dynasty_benchmark()
    players = {entry["player"] for entry in benchmark}

    assert len(benchmark) >= 30
    assert "Bobby Witt Jr." in players
    assert "Corbin Carroll" in players
    assert "Tarik Skubal" in players
    assert "Ronald Acuna Jr." in players
    assert "Cal Raleigh" in players
