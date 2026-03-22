"""Deep-roto comparison helpers for dynasty divergence analysis."""

from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Sequence

from backend.core.dynasty_divergence_shared import (
    DEEP_ROTO_CLASSIFICATIONS,
    DEFAULT_DEEP_MEMO_TARGET_PLAYERS,
    _coerce_float,
    _coerce_int,
    _coerce_mapping,
    _per_year_entries,
    explanation_review_metrics,
    normalize_player_name,
    summarize_divergence_drivers,
)


def _ranked_dynasty_entries(
    *,
    model_rows: Iterable[dict[str, Any]],
    explanations: dict[str, dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    ranked_rows = sorted(
        [row for row in model_rows if isinstance(row, dict)],
        key=lambda row: float(row.get("DynastyValue") or 0.0),
        reverse=True,
    )
    explanation_map = explanations if isinstance(explanations, dict) else {}
    ranked_entries: list[dict[str, Any]] = []
    for idx, row in enumerate(ranked_rows, start=1):
        player = str(row.get("Player") or "").strip()
        if not player:
            continue
        player_key = str(row.get("PlayerKey") or normalize_player_name(player)).strip() or normalize_player_name(player)
        entity_key = str(row.get("PlayerEntityKey") or player_key).strip() or player_key
        explanation = explanation_map.get(entity_key) or explanation_map.get(player_key)
        explanation = explanation if isinstance(explanation, dict) else None
        metrics = explanation_review_metrics(explanation)
        ranked_entries.append(
            {
                "player": player,
                "player_key": player_key,
                "entity_key": entity_key,
                "team": str(row.get("Team") or "").strip() or None,
                "pos": str(row.get("Pos") or "").strip() or None,
                "dynasty_value": float(row.get("DynastyValue") or 0.0),
                "model_rank": idx,
                "explanation": explanation,
                **metrics,
            }
        )
    return ranked_entries


def _top_abs_stat_contributions(stat_dynasty_contributions: object, *, limit: int = 3) -> list[dict[str, Any]]:
    mapping = _coerce_mapping(stat_dynasty_contributions)
    ranked = sorted(
        (
            (str(category), float(value))
            for category, value in mapping.items()
            if _coerce_float(value) is not None
        ),
        key=lambda item: (-abs(item[1]), item[0]),
    )
    return [{"category": category, "value": round(value, 4)} for category, value in ranked[:limit]]


def classify_deep_roto_change(
    *,
    standard_entry: dict[str, Any] | None,
    deep_entry: dict[str, Any] | None,
) -> str:
    if not isinstance(deep_entry, dict):
        return "deep_replacement_context"
    explanation = deep_entry.get("explanation")
    explanation = explanation if isinstance(explanation, dict) else {}
    centering = _coerce_mapping(explanation.get("centering"))
    if (
        str(centering.get("mode") or "").strip() == "forced_roster_minor_cost"
        or _coerce_float(centering.get("minor_slot_cost_value")) not in {None, 0.0}
    ):
        return "stash_economics"
    per_year = _per_year_entries(explanation)
    if any(
        bool(entry.get("stash_adjustment_applied"))
        or bool(entry.get("can_minor_stash"))
        or bool(entry.get("can_ir_stash"))
        or bool(entry.get("can_bench_stash"))
        for entry in per_year
        if isinstance(entry, dict)
    ):
        return "stash_economics"
    top_stat_categories = {
        str(entry.get("category") or "").strip()
        for entry in _top_abs_stat_contributions(explanation.get("stat_dynasty_contributions"))
        if isinstance(entry, dict) and str(entry.get("category") or "").strip()
    }
    if top_stat_categories & {"OPS", "QA3", "SVH"}:
        return "category_mix"
    if bool(centering.get("fallback_applied")) or str(centering.get("mode") or "").strip() == "forced_roster":
        return "forced_roster_centering"
    standard_tail_share = _coerce_float((standard_entry or {}).get("tail_share_after_year_3"))
    deep_tail_share = _coerce_float(deep_entry.get("tail_share_after_year_3"))
    if (
        standard_tail_share is not None
        and deep_tail_share is not None
        and deep_tail_share < (standard_tail_share - 0.05)
    ):
        return "aggregation_tail"
    return "deep_replacement_context"


def deep_roto_recommendation(
    entries: Iterable[dict[str, Any]],
    *,
    target_players: Sequence[str] | None = None,
) -> str:
    target_order = [
        str(player).strip()
        for player in (target_players or DEFAULT_DEEP_MEMO_TARGET_PLAYERS)
        if str(player).strip()
    ]
    entry_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    material_targets = [
        entry_by_player[player]
        for player in target_order
        if isinstance(entry_by_player.get(player), dict)
        and abs(int(_coerce_int(entry_by_player[player].get("rank_delta_vs_standard")) or 0)) >= 15
    ]
    classification_counts = Counter(
        str(entry.get("deep_change_classification") or "").strip()
        for entry in material_targets
        if str(entry.get("deep_change_classification") or "").strip() in DEEP_ROTO_CLASSIFICATIONS
    )
    if classification_counts and max(classification_counts.values()) >= 4:
        return "recommend_deep_roto_methodology_followup"
    return "recommend_no_deep_specific_change_yet"


def review_deep_roto_profile(
    *,
    deep_model_rows: Iterable[dict[str, Any]],
    deep_explanations: dict[str, dict[str, Any]] | None,
    deep_valuation_diagnostics: dict[str, Any] | None,
    standard_model_rows: Iterable[dict[str, Any]],
    standard_explanations: dict[str, dict[str, Any]] | None,
    projection_data_version: str | None = None,
    methodology_fingerprint: str | None = None,
    settings_snapshot: dict[str, Any] | None = None,
    profile_id: str = "deep_roto",
    top_n_absolute: int = 20,
) -> dict[str, Any]:
    deep_entries = _ranked_dynasty_entries(model_rows=deep_model_rows, explanations=deep_explanations)
    standard_entries = _ranked_dynasty_entries(model_rows=standard_model_rows, explanations=standard_explanations)
    standard_entry_by_player = {
        normalize_player_name(entry.get("player")): entry
        for entry in standard_entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    comparison_entries: list[dict[str, Any]] = []
    for deep_entry in deep_entries:
        player_key = normalize_player_name(deep_entry.get("player"))
        standard_entry = standard_entry_by_player.get(player_key)
        if not isinstance(standard_entry, dict):
            continue
        deep_rank = _coerce_int(deep_entry.get("model_rank"))
        standard_rank = _coerce_int(standard_entry.get("model_rank"))
        if deep_rank is None or standard_rank is None:
            continue
        rank_delta_vs_standard = int(standard_rank) - int(deep_rank)
        explanation = deep_entry.get("explanation")
        explanation = explanation if isinstance(explanation, dict) else {}
        deep_change_classification = classify_deep_roto_change(
            standard_entry=standard_entry,
            deep_entry=deep_entry,
        )
        comparison_entries.append(
            {
                "player": deep_entry.get("player"),
                "team": deep_entry.get("team"),
                "pos": deep_entry.get("pos") or explanation.get("pos"),
                "standard_rank": standard_rank,
                "deep_rank": deep_rank,
                "rank_delta_vs_standard": rank_delta_vs_standard,
                "standard_dynasty_value": standard_entry.get("dynasty_value"),
                "deep_dynasty_value": deep_entry.get("dynasty_value"),
                "standard_start_year_rank": standard_entry.get("start_year_rank"),
                "deep_start_year_rank": deep_entry.get("start_year_rank"),
                "standard_start_year_best_slot": standard_entry.get("start_year_best_slot"),
                "deep_start_year_best_slot": deep_entry.get("start_year_best_slot"),
                "deep_change_classification": deep_change_classification,
                "deep_top_positive_categories": deep_entry.get("start_year_top_positive_categories") or [],
                "deep_top_negative_categories": deep_entry.get("start_year_top_negative_categories") or [],
                "deep_top_stat_contributions": _top_abs_stat_contributions(
                    explanation.get("stat_dynasty_contributions")
                ),
                "deep_replacement_reference": deep_entry.get("start_year_replacement_reference") or {},
                "deep_slot_baseline_reference": deep_entry.get("start_year_slot_baseline_reference") or {},
                "deep_centering": _coerce_mapping(explanation.get("centering")),
                "deep_tail_share_after_year_3": deep_entry.get("tail_share_after_year_3"),
                "deep_positive_year_count": deep_entry.get("positive_year_count"),
                "deep_last_positive_year": deep_entry.get("last_positive_year"),
                "deep_driver_summary": summarize_divergence_drivers(explanation),
            }
        )
    comparison_entries = sorted(
        comparison_entries,
        key=lambda entry: (
            -abs(int(_coerce_int(entry.get("rank_delta_vs_standard")) or 0)),
            str(entry.get("player") or ""),
        ),
    )
    valuation_diagnostics = deep_valuation_diagnostics if isinstance(deep_valuation_diagnostics, dict) else {}
    diagnostics_summary = {
        "CenteringMode": str(valuation_diagnostics.get("CenteringMode") or "").strip() or None,
        "ForcedRosterFallbackApplied": bool(valuation_diagnostics.get("ForcedRosterFallbackApplied")),
        "ResidualMinorSlotCostApplied": bool(valuation_diagnostics.get("ResidualMinorSlotCostApplied")),
        "CenteringBaselineValue": _coerce_float(valuation_diagnostics.get("CenteringBaselineValue")),
        "CenteringScoreBaselineValue": _coerce_float(valuation_diagnostics.get("CenteringScoreBaselineValue")),
        "PositiveValuePlayerCount": _coerce_int(valuation_diagnostics.get("PositiveValuePlayerCount")),
        "ZeroValuePlayerCount": _coerce_int(valuation_diagnostics.get("ZeroValuePlayerCount")),
        "RawZeroValuePlayerCount": _coerce_int(valuation_diagnostics.get("RawZeroValuePlayerCount")),
        "ResidualZeroMinorCandidateCount": _coerce_int(valuation_diagnostics.get("ResidualZeroMinorCandidateCount")),
        "deep_roster_zero_baseline_warning": bool(valuation_diagnostics.get("deep_roster_zero_baseline_warning")),
    }
    classification_counts = {
        label: sum(1 for entry in comparison_entries if entry.get("deep_change_classification") == label)
        for label in DEEP_ROTO_CLASSIFICATIONS
    }
    movers = comparison_entries[: max(int(top_n_absolute), 1)]
    return {
        "profile_id": str(profile_id or "").strip() or "deep_roto",
        "comparison_profile_id": "standard_roto",
        "settings_snapshot": settings_snapshot if isinstance(settings_snapshot, dict) else {},
        "projection_data_version": str(projection_data_version or "").strip() or None,
        "methodology_fingerprint": methodology_fingerprint,
        "valuation_diagnostics_summary": diagnostics_summary,
        "classification_counts": classification_counts,
        "entries": comparison_entries,
        "review_candidates": movers,
        "recommendation": deep_roto_recommendation(comparison_entries),
    }
