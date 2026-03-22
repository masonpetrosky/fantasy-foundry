"""Review assembly helpers for dynasty divergence analysis."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from backend.core.dynasty_divergence_shared import (
    ATTRIBUTION_CLASSES,
    ATTRIBUTION_OF_CONTROL_PLAYERS,
    ATTRIBUTION_OF_TARGET_PLAYERS,
    ATTRIBUTION_P_CONTROL_PLAYERS,
    ATTRIBUTION_P_TARGET_PLAYERS,
    TRIAGE_BUCKETS,
    _category_sgp_mapping_from_row,
    _coerce_float,
    _coerce_int,
    _median_or_none,
    _projection_stat_snapshot,
    _projection_top_stat_deltas,
    _slot_projection_movers,
    _summarize_attribution_cohort,
    _top_category_entries_from_mapping,
    aggregation_tail_recommendation,
    attribution_recommendation,
    classify_aggregation_tail_gap,
    classify_attribution_layer,
    classify_divergence,
    classify_projection_delta,
    classify_raw_value_gap_cause,
    classify_suspect_gap_refresh_label,
    explanation_review_metrics,
    normalize_player_name,
    projection_refresh_recommendation,
    summarize_divergence_drivers,
    triage_bucket,
    weighted_mean_absolute_rank_error,
)


def summarize_triage_buckets(entries: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    bucket_map: dict[str, list[dict[str, Any]]] = {bucket: [] for bucket in TRIAGE_BUCKETS}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        bucket = str(entry.get("triage_bucket") or "").strip()
        if bucket in bucket_map:
            bucket_map[bucket].append(entry)

    summaries: dict[str, dict[str, Any]] = {}
    for bucket, bucket_entries in bucket_map.items():
        count = len(bucket_entries)
        summary: dict[str, Any] = {
            "count": count,
            "median_start_year_rank": _median_or_none((entry.get("start_year_rank") for entry in bucket_entries), digits=1),
            "median_model_rank": _median_or_none((entry.get("model_rank") for entry in bucket_entries), digits=1),
            "median_benchmark_rank": _median_or_none((entry.get("benchmark_rank") for entry in bucket_entries), digits=1),
            "median_abs_rank_delta": _median_or_none((entry.get("abs_rank_delta") for entry in bucket_entries), digits=1),
            "median_positive_year_count": _median_or_none(
                (entry.get("positive_year_count") for entry in bucket_entries), digits=1
            ),
            "median_last_positive_year": _median_or_none(
                (entry.get("last_positive_year") for entry in bucket_entries), digits=0
            ),
            "median_three_year_share": _median_or_none(
                (
                    (
                        float(entry.get("discounted_three_year_total") or 0.0)
                        / float(entry.get("discounted_full_total") or 1.0)
                    )
                    if float(entry.get("discounted_full_total") or 0.0) > 0.0
                    else None
                    for entry in bucket_entries
                ),
                digits=4,
            ),
        }
        if bucket == "aggregation_gap":
            if count:
                summary["summary"] = (
                    f"{count} tracked players still rank inside the top-25 in start-year roto value "
                    f"(median start-year rank {summary['median_start_year_rank']}) but fall to a median dynasty rank "
                    f"of {summary['median_model_rank']} against median benchmark rank {summary['median_benchmark_rank']}. "
                    f"This points to a dynasty aggregation problem rather than a one-year valuation miss."
                )
            else:
                summary["summary"] = "No tracked aggregation-gap players in the current review."
        elif bucket == "raw_value_gap":
            if count:
                summary["summary"] = (
                    f"{count} tracked players are already outside the top-25 in start-year roto value "
                    f"(median start-year rank {summary['median_start_year_rank']}), so their gap starts before dynasty "
                    f"aggregation. This points to one-year roto or replacement-context assumptions rather than horizon discounting."
                )
            else:
                summary["summary"] = "No tracked raw-value-gap players in the current review."
        else:
            if count:
                summary["summary"] = (
                    f"{count} tracked players sit near the start-year split line and need manual review before they can be "
                    "assigned cleanly to raw-value or aggregation work."
                )
            else:
                summary["summary"] = "No tracked mixed-gap players in the current review."
        summaries[bucket] = summary
    return summaries


def review_dynasty_divergence(
    *,
    model_rows: Iterable[dict[str, Any]],
    explanations: dict[str, dict[str, Any]] | None,
    benchmark_entries: Iterable[dict[str, Any]],
    raw_start_year_rows: Iterable[dict[str, Any]] | None = None,
    start_year_projection_stats_by_entity: dict[str, dict[str, float]] | None = None,
    delta_threshold: int = 15,
    top_n_absolute: int = 20,
    methodology_fingerprint: str | None = None,
    projection_data_version: str | None = None,
    projection_delta_details: dict[str, dict[str, Any]] | None = None,
    has_previous_projection_snapshot: bool = False,
    previous_projection_source: str | None = None,
    profile_id: str = "standard_roto",
    settings_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    benchmark_list = [entry for entry in benchmark_entries if isinstance(entry, dict)]
    ranked_rows = sorted(
        [row for row in model_rows if isinstance(row, dict)],
        key=lambda row: float(row.get("DynastyValue") or 0.0),
        reverse=True,
    )
    explanation_map = explanations if isinstance(explanations, dict) else {}
    projection_delta_detail_map = projection_delta_details if isinstance(projection_delta_details, dict) else {}
    benchmark_rank_by_key = {
        str(entry.get("player_key") or normalize_player_name(entry.get("player"))): _coerce_int(entry.get("benchmark_rank"))
        for entry in benchmark_list
    }
    raw_projection_stats_by_entity = (
        start_year_projection_stats_by_entity
        if isinstance(start_year_projection_stats_by_entity, dict)
        else {}
    )
    raw_ranked_rows = sorted(
        [row for row in (raw_start_year_rows or []) if isinstance(row, dict)],
        key=lambda row: (-float(row.get("YearValue") or 0.0), str(row.get("Player") or "")),
    )
    raw_start_year_index: dict[str, dict[str, Any]] = {}
    for idx, row in enumerate(raw_ranked_rows, start=1):
        player = str(row.get("Player") or "").strip()
        if not player:
            continue
        player_key = str(row.get("PlayerKey") or normalize_player_name(player)).strip() or normalize_player_name(player)
        entity_key = str(row.get("PlayerEntityKey") or player_key).strip() or player_key
        category_sgp = _category_sgp_mapping_from_row(row)
        raw_start_year_index.setdefault(
            normalize_player_name(player),
            {
                "player": player,
                "player_key": player_key,
                "entity_key": entity_key,
                "raw_start_year_rank": idx,
                "raw_start_year_value": round(float(_coerce_float(row.get("YearValue")) or 0.0), 4),
                "raw_start_year_best_slot": str(row.get("BestSlot") or "").strip() or None,
                "raw_start_year_category_sgp": category_sgp,
                "raw_start_year_top_positive_categories": _top_category_entries_from_mapping(
                    category_sgp,
                    positive=True,
                ),
                "raw_start_year_top_negative_categories": _top_category_entries_from_mapping(
                    category_sgp,
                    positive=False,
                ),
            },
        )

    model_index: dict[str, dict[str, Any]] = {}
    ranked_model_entries: list[dict[str, Any]] = []
    for idx, row in enumerate(ranked_rows, start=1):
        player = str(row.get("Player") or "").strip()
        if not player:
            continue
        player_key = str(row.get("PlayerKey") or normalize_player_name(player)).strip() or normalize_player_name(player)
        entity_key = str(row.get("PlayerEntityKey") or player_key).strip() or player_key
        explanation = explanation_map.get(entity_key) or explanation_map.get(player_key)
        explanation = explanation if isinstance(explanation, dict) else None
        metrics = explanation_review_metrics(explanation)
        model_entry = {
            "player": player,
            "player_key": player_key,
            "entity_key": entity_key,
            "team": str(row.get("Team") or "").strip() or None,
            "dynasty_value": float(row.get("DynastyValue") or 0.0),
            "model_rank": idx,
            "benchmark_rank": benchmark_rank_by_key.get(normalize_player_name(player)),
            "explanation": explanation,
            **metrics,
        }
        model_index.setdefault(normalize_player_name(player), model_entry)
        ranked_model_entries.append(model_entry)

    start_year_rank_entries = sorted(
        [entry for entry in ranked_model_entries if entry.get("start_year_value") is not None],
        key=lambda entry: (
            -float(entry.get("start_year_value") or 0.0),
            int(entry.get("model_rank") or 10**9),
            str(entry.get("player") or ""),
        ),
    )
    for idx, entry in enumerate(start_year_rank_entries, start=1):
        entry["start_year_rank"] = idx
    for idx, entry in enumerate(ranked_model_entries):
        comps_above = []
        for comp in ranked_model_entries[max(0, idx - 3) : idx]:
            comps_above.append(
                {
                    "player": comp.get("player"),
                    "model_rank": comp.get("model_rank"),
                    "benchmark_rank": comp.get("benchmark_rank"),
                    "start_year_rank": comp.get("start_year_rank"),
                    "positive_year_count": comp.get("positive_year_count"),
                    "last_positive_year": comp.get("last_positive_year"),
                    "first_near_zero_year": comp.get("first_near_zero_year"),
                    "positive_year_span": comp.get("positive_year_span"),
                    "tail_share_after_year_3": comp.get("tail_share_after_year_3"),
                }
            )
        entry["model_comps_above"] = comps_above

    entries: list[dict[str, Any]] = []
    for benchmark in benchmark_list:
        player_key = str(benchmark.get("player_key") or normalize_player_name(benchmark.get("player")))
        indexed_model_entry = model_index.get(player_key)
        explanation = indexed_model_entry.get("explanation") if isinstance(indexed_model_entry, dict) else None
        benchmark_rank = _coerce_int(benchmark.get("benchmark_rank"))
        model_rank = int(indexed_model_entry["model_rank"]) if isinstance(indexed_model_entry, dict) else None
        raw_start_year_entry = raw_start_year_index.get(player_key)
        raw_start_year_rank = (
            _coerce_int(raw_start_year_entry.get("raw_start_year_rank"))
            if isinstance(raw_start_year_entry, dict)
            else None
        )
        delta = (int(model_rank) - int(benchmark_rank)) if model_rank is not None and benchmark_rank is not None else None
        abs_delta = abs(delta) if delta is not None else None
        driver_summary = summarize_divergence_drivers(explanation if isinstance(explanation, dict) else None)
        start_year_rank = _coerce_int(model_entry.get("start_year_rank")) if isinstance(model_entry, dict) else None
        start_year_projection_stats = {}
        if isinstance(model_entry, dict):
            entity_key = str(model_entry.get("entity_key") or "").strip()
            player_key_fallback = str(model_entry.get("player_key") or "").strip()
            start_year_projection_stats = _projection_stat_snapshot(
                raw_projection_stats_by_entity.get(entity_key)
                or raw_projection_stats_by_entity.get(player_key_fallback)
            )
        current_triage_bucket = triage_bucket(
            abs_rank_delta=abs_delta,
            start_year_rank=start_year_rank,
            delta_threshold=delta_threshold,
        )
        model_comps_above = model_entry.get("model_comps_above") if isinstance(model_entry, dict) else []
        model_comps_above = model_comps_above if isinstance(model_comps_above, list) else []
        comp_positive_year_counts = [
            _coerce_int(comp.get("positive_year_count"))
            for comp in model_comps_above
            if isinstance(comp, dict)
        ]
        aggregation_tail_classification = classify_aggregation_tail_gap(
            triage_bucket=current_triage_bucket,
            start_year_rank=start_year_rank,
            positive_year_count=_coerce_int(model_entry.get("positive_year_count")) if isinstance(model_entry, dict) else None,
            tail_share_after_year_3=(
                _coerce_float(model_entry.get("tail_share_after_year_3")) if isinstance(model_entry, dict) else None
            ),
            comp_positive_year_counts=comp_positive_year_counts,
        )
        projection_delta_detail = (
            projection_delta_detail_map.get(str(model_entry.get("entity_key") or "").strip())
            if isinstance(model_entry, dict)
            else None
        )
        if not isinstance(projection_delta_detail, dict) and isinstance(model_entry, dict):
            projection_delta_detail = projection_delta_detail_map.get(str(model_entry.get("player_key") or "").strip())
        projection_delta_type = classify_projection_delta(
            projection_delta_detail=projection_delta_detail if isinstance(projection_delta_detail, dict) else None,
            has_previous_projection_snapshot=has_previous_projection_snapshot,
        )
        classification = classify_divergence(
            model_rank=model_rank,
            benchmark_rank=benchmark_rank,
            explanation=explanation if isinstance(explanation, dict) else None,
            delta_threshold=delta_threshold,
        )
        attribution_class = classify_attribution_layer(
            benchmark_rank=benchmark_rank,
            raw_start_year_rank=raw_start_year_rank,
            start_year_rank=start_year_rank,
            model_rank=model_rank,
        )
        entries.append(
            {
                "player": str(benchmark.get("player") or "").strip(),
                "team": model_entry.get("team") if isinstance(model_entry, dict) else None,
                "benchmark_rank": benchmark_rank,
                "model_rank": model_rank,
                "rank_delta": delta,
                "abs_rank_delta": abs_delta,
                "absolute_benchmark_error": abs_delta,
                "dynasty_value": model_entry.get("dynasty_value") if isinstance(model_entry, dict) else None,
                "start_year": model_entry.get("start_year") if isinstance(model_entry, dict) else None,
                "start_year_rank": start_year_rank,
                "start_year_value": model_entry.get("start_year_value") if isinstance(model_entry, dict) else None,
                "raw_start_year_rank": raw_start_year_rank,
                "raw_start_year_value": (
                    raw_start_year_entry.get("raw_start_year_value") if isinstance(raw_start_year_entry, dict) else None
                ),
                "raw_start_year_best_slot": (
                    raw_start_year_entry.get("raw_start_year_best_slot")
                    if isinstance(raw_start_year_entry, dict)
                    else None
                ),
                "raw_start_year_category_sgp": (
                    raw_start_year_entry.get("raw_start_year_category_sgp")
                    if isinstance(raw_start_year_entry, dict)
                    else {}
                ),
                "raw_start_year_top_positive_categories": (
                    raw_start_year_entry.get("raw_start_year_top_positive_categories")
                    if isinstance(raw_start_year_entry, dict)
                    else []
                ),
                "raw_start_year_top_negative_categories": (
                    raw_start_year_entry.get("raw_start_year_top_negative_categories")
                    if isinstance(raw_start_year_entry, dict)
                    else []
                ),
                "raw_to_replacement_rank_delta": (
                    int(start_year_rank) - int(raw_start_year_rank)
                    if start_year_rank is not None and raw_start_year_rank is not None
                    else None
                ),
                "replacement_to_dynasty_rank_delta": (
                    int(model_rank) - int(start_year_rank)
                    if model_rank is not None and start_year_rank is not None
                    else None
                ),
                "start_year_projection_stats": start_year_projection_stats,
                "discounted_three_year_total": (
                    model_entry.get("discounted_three_year_total") if isinstance(model_entry, dict) else None
                ),
                "discounted_full_total": (
                    model_entry.get("discounted_full_total") if isinstance(model_entry, dict) else None
                ),
                "positive_year_count": model_entry.get("positive_year_count") if isinstance(model_entry, dict) else None,
                "last_positive_year": model_entry.get("last_positive_year") if isinstance(model_entry, dict) else None,
                "first_near_zero_year": model_entry.get("first_near_zero_year") if isinstance(model_entry, dict) else None,
                "first_non_positive_adjusted_year": (
                    model_entry.get("first_non_positive_adjusted_year") if isinstance(model_entry, dict) else None
                ),
                "positive_year_span": model_entry.get("positive_year_span") if isinstance(model_entry, dict) else None,
                "tail_value_after_year_3": model_entry.get("tail_value_after_year_3") if isinstance(model_entry, dict) else None,
                "tail_share_after_year_3": model_entry.get("tail_share_after_year_3") if isinstance(model_entry, dict) else None,
                "tail_preview": model_entry.get("tail_preview") if isinstance(model_entry, dict) else [],
                "top_discounted_years": model_entry.get("top_discounted_years") if isinstance(model_entry, dict) else [],
                "start_year_best_slot": model_entry.get("start_year_best_slot") if isinstance(model_entry, dict) else None,
                "start_year_category_sgp": (
                    model_entry.get("start_year_category_sgp") if isinstance(model_entry, dict) else {}
                ),
                "start_year_top_positive_categories": (
                    model_entry.get("start_year_top_positive_categories") if isinstance(model_entry, dict) else []
                ),
                "start_year_top_negative_categories": (
                    model_entry.get("start_year_top_negative_categories") if isinstance(model_entry, dict) else []
                ),
                "start_year_slot_baseline_reference": (
                    model_entry.get("start_year_slot_baseline_reference") if isinstance(model_entry, dict) else {}
                ),
                "start_year_replacement_reference": (
                    model_entry.get("start_year_replacement_reference") if isinstance(model_entry, dict) else {}
                ),
                "start_year_replacement_pool_depth": (
                    model_entry.get("start_year_replacement_pool_depth") if isinstance(model_entry, dict) else None
                ),
                "start_year_replacement_depth_mode": (
                    model_entry.get("start_year_replacement_depth_mode") if isinstance(model_entry, dict) else None
                ),
                "start_year_replacement_depth_blend_alpha": (
                    model_entry.get("start_year_replacement_depth_blend_alpha")
                    if isinstance(model_entry, dict)
                    else None
                ),
                "start_year_slot_count_per_team": (
                    model_entry.get("start_year_slot_count_per_team") if isinstance(model_entry, dict) else None
                ),
                "start_year_slot_capacity_league": (
                    model_entry.get("start_year_slot_capacity_league") if isinstance(model_entry, dict) else None
                ),
                "start_year_guard_summary": (
                    model_entry.get("start_year_guard_summary") if isinstance(model_entry, dict) else {}
                ),
                "start_year_bounds_summary": (
                    model_entry.get("start_year_bounds_summary") if isinstance(model_entry, dict) else {}
                ),
                "model_comps_above": model_comps_above,
                "aggregation_comp_positive_year_count_median": _median_or_none(comp_positive_year_counts, digits=1),
                "aggregation_tail_classification": aggregation_tail_classification,
                "classification": classification,
                "raw_value_gap_cause": classify_raw_value_gap_cause(
                    explanation if isinstance(explanation, dict) else None
                ),
                "projection_composite_delta": (
                    round(float(_coerce_float(projection_delta_detail.get("composite_delta")) or 0.0), 3)
                    if isinstance(projection_delta_detail, dict)
                    else None
                ),
                "projection_delta_type": projection_delta_type,
                "projection_top_stat_deltas": _projection_top_stat_deltas(
                    projection_delta_detail if isinstance(projection_delta_detail, dict) else None
                ),
                "suspect_gap_refresh_label": classify_suspect_gap_refresh_label(
                    classification=classification,
                    projection_delta_type=projection_delta_type,
                ),
                "attribution_class": attribution_class,
                "triage_bucket": current_triage_bucket,
                "driver_summary": driver_summary,
                "source": benchmark.get("source"),
                "notes": benchmark.get("notes"),
            }
        )

    entries = sorted(
        entries,
        key=lambda entry: (
            -(int(entry["abs_rank_delta"]) if entry.get("abs_rank_delta") is not None else -1),
            str(entry.get("player") or ""),
        ),
    )
    review_candidates = [
        entry
        for entry in entries
        if entry.get("classification") != "explained"
        or (entry.get("abs_rank_delta") is not None and int(entry["abs_rank_delta"]) >= int(delta_threshold))
    ][:top_n_absolute]

    classification_counts = {
        label: sum(1 for entry in entries if entry.get("classification") == label)
        for label in ("explained", "suspect_model_gap", "needs_manual_review")
    }
    triage_counts = Counter(
        str(entry.get("triage_bucket") or "").strip()
        for entry in entries
        if str(entry.get("triage_bucket") or "").strip() in TRIAGE_BUCKETS
    )
    attribution_counts = Counter(
        str(entry.get("attribution_class") or "").strip()
        for entry in entries
        if str(entry.get("attribution_class") or "").strip() in ATTRIBUTION_CLASSES
    )
    return {
        "profile_id": str(profile_id or "").strip() or "standard_roto",
        "settings_snapshot": settings_snapshot if isinstance(settings_snapshot, dict) else {},
        "benchmark_player_count": len(entries),
        "delta_threshold": int(delta_threshold),
        "top_n_absolute": int(top_n_absolute),
        "projection_data_version": str(projection_data_version or "").strip() or None,
        "methodology_fingerprint": methodology_fingerprint,
        "has_previous_projection_snapshot": bool(has_previous_projection_snapshot),
        "previous_projection_source": str(previous_projection_source or "").strip() or None,
        "weighted_mean_absolute_rank_error": weighted_mean_absolute_rank_error(entries),
        "classification_counts": classification_counts,
        "triage_counts": {bucket: int(triage_counts.get(bucket, 0)) for bucket in TRIAGE_BUCKETS},
        "attribution_counts": {label: int(attribution_counts.get(label, 0)) for label in ATTRIBUTION_CLASSES},
        "triage_summaries": summarize_triage_buckets(entries),
        "aggregation_tail_recommendation": aggregation_tail_recommendation(entries),
        "projection_refresh_recommendation": projection_refresh_recommendation(entries),
        "attribution_recommendation": attribution_recommendation(entries),
        "attribution_cohort_summaries": {
            "of_targets": _summarize_attribution_cohort(entries, players=ATTRIBUTION_OF_TARGET_PLAYERS),
            "of_controls": _summarize_attribution_cohort(entries, players=ATTRIBUTION_OF_CONTROL_PLAYERS),
            "p_targets": _summarize_attribution_cohort(entries, players=ATTRIBUTION_P_TARGET_PLAYERS),
            "p_controls": _summarize_attribution_cohort(entries, players=ATTRIBUTION_P_CONTROL_PLAYERS),
        },
        "slot_mover_summaries": {
            "OF": _slot_projection_movers(
                ranked_model_entries,
                projection_delta_details=projection_delta_detail_map,
                slots={"OF"},
                has_previous_projection_snapshot=has_previous_projection_snapshot,
            ),
            "P": _slot_projection_movers(
                ranked_model_entries,
                projection_delta_details=projection_delta_detail_map,
                slots={"P", "SP", "RP"},
                has_previous_projection_snapshot=has_previous_projection_snapshot,
            ),
        },
        "entries": entries,
        "review_candidates": review_candidates,
    }
