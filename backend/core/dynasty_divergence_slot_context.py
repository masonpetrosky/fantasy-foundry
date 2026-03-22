"""Slot-context candidate review helpers for dynasty divergence analysis."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from backend.core.dynasty_divergence_shared import (
    DEFAULT_SLOT_CONTEXT_MEMO_TARGET_PLAYERS,
    SLOT_CONTEXT_EXPLAINED_HITTER_CONTROL_PLAYERS,
    SLOT_CONTEXT_OF_TARGET_PLAYERS,
    SLOT_CONTEXT_P_TARGET_PLAYERS,
    SLOT_CONTEXT_PITCHER_CONTROL_PLAYERS,
    _coerce_float,
    _coerce_int,
    _coerce_mapping,
)


def _review_entries_by_player(review: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entries = review.get("entries")
    entries = entries if isinstance(entries, list) else []
    return {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }


def _slot_context_candidate_group(
    *,
    control_of_alpha: float,
    control_p_alpha: float,
    candidate_of_alpha: float,
    candidate_p_alpha: float,
) -> str:
    same_of = abs(float(candidate_of_alpha) - float(control_of_alpha)) < 1e-9
    same_p = abs(float(candidate_p_alpha) - float(control_p_alpha)) < 1e-9
    if same_of and same_p:
        return "control"
    if not same_of and same_p:
        return "of_only"
    if same_of and not same_p:
        return "p_only"
    return "combined"


def _rank_change_vs_control(
    control_rank: object,
    candidate_rank: object,
) -> int | None:
    control_rank_int = _coerce_int(control_rank)
    candidate_rank_int = _coerce_int(candidate_rank)
    if control_rank_int is None or candidate_rank_int is None:
        return None
    return int(control_rank_int) - int(candidate_rank_int)


def _slot_context_player_delta(
    *,
    player: str,
    control_entry: dict[str, Any] | None,
    candidate_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    control_entry = control_entry if isinstance(control_entry, dict) else {}
    candidate_entry = candidate_entry if isinstance(candidate_entry, dict) else {}
    control_model_rank = _coerce_int(control_entry.get("model_rank"))
    candidate_model_rank = _coerce_int(candidate_entry.get("model_rank"))
    control_start_year_rank = _coerce_int(control_entry.get("start_year_rank"))
    candidate_start_year_rank = _coerce_int(candidate_entry.get("start_year_rank"))
    control_start_year_value = _coerce_float(control_entry.get("start_year_value"))
    candidate_start_year_value = _coerce_float(candidate_entry.get("start_year_value"))
    control_three_year_total = _coerce_float(control_entry.get("discounted_three_year_total"))
    candidate_three_year_total = _coerce_float(candidate_entry.get("discounted_three_year_total"))
    control_full_total = _coerce_float(control_entry.get("discounted_full_total"))
    candidate_full_total = _coerce_float(candidate_entry.get("discounted_full_total"))
    control_abs_error = _coerce_int(
        control_entry.get("absolute_benchmark_error", control_entry.get("abs_rank_delta"))
    )
    candidate_abs_error = _coerce_int(
        candidate_entry.get("absolute_benchmark_error", candidate_entry.get("abs_rank_delta"))
    )
    return {
        "player": player,
        "benchmark_rank": _coerce_int(candidate_entry.get("benchmark_rank", control_entry.get("benchmark_rank"))),
        "control_model_rank": control_model_rank,
        "candidate_model_rank": candidate_model_rank,
        "dynasty_rank_change_vs_control": _rank_change_vs_control(control_model_rank, candidate_model_rank),
        "control_absolute_benchmark_error": control_abs_error,
        "candidate_absolute_benchmark_error": candidate_abs_error,
        "absolute_benchmark_error_change_vs_control": (
            int(candidate_abs_error) - int(control_abs_error)
            if candidate_abs_error is not None and control_abs_error is not None
            else None
        ),
        "control_start_year_rank": control_start_year_rank,
        "candidate_start_year_rank": candidate_start_year_rank,
        "start_year_rank_change_vs_control": _rank_change_vs_control(
            control_start_year_rank,
            candidate_start_year_rank,
        ),
        "control_start_year_value": control_start_year_value,
        "candidate_start_year_value": candidate_start_year_value,
        "start_year_value_change_vs_control": (
            round(float(candidate_start_year_value) - float(control_start_year_value), 4)
            if candidate_start_year_value is not None and control_start_year_value is not None
            else None
        ),
        "discounted_three_year_total_change_vs_control": (
            round(float(candidate_three_year_total) - float(control_three_year_total), 4)
            if candidate_three_year_total is not None and control_three_year_total is not None
            else None
        ),
        "discounted_full_total_change_vs_control": (
            round(float(candidate_full_total) - float(control_full_total), 4)
            if candidate_full_total is not None and control_full_total is not None
            else None
        ),
        "candidate_start_year_best_slot": str(candidate_entry.get("start_year_best_slot") or "").strip() or None,
        "candidate_start_year_replacement_reference": _coerce_mapping(
            candidate_entry.get("start_year_replacement_reference")
        ),
    }


def _best_slot_context_candidate(
    candidate_summaries: Sequence[dict[str, Any]],
    *,
    group: str,
) -> dict[str, Any] | None:
    matching = [
        summary
        for summary in candidate_summaries
        if isinstance(summary, dict) and str(summary.get("candidate_group") or "").strip() == group
    ]
    if not matching:
        return None
    return min(
        matching,
        key=lambda summary: (
            float(summary.get("weighted_mean_absolute_rank_error") or 0.0),
            int(summary.get("worst_absolute_benchmark_error_regression") or 0),
            abs(float(summary.get("of_alpha") or 0.0) - float(summary.get("control_of_alpha") or 0.0))
            + abs(float(summary.get("p_alpha") or 0.0) - float(summary.get("control_p_alpha") or 0.0)),
            str(summary.get("candidate_id") or ""),
        ),
    )


def _slot_context_recommendation_from_candidates(
    candidate_summaries: Sequence[dict[str, Any]],
) -> str:
    of_best = _best_slot_context_candidate(candidate_summaries, group="of_only")
    p_best = _best_slot_context_candidate(candidate_summaries, group="p_only")
    combined_best = _best_slot_context_candidate(candidate_summaries, group="combined")
    single_family_best = min(
        [summary for summary in (of_best, p_best) if isinstance(summary, dict)],
        key=lambda summary: (
            float(summary.get("weighted_mean_absolute_rank_error") or 0.0),
            int(summary.get("worst_absolute_benchmark_error_regression") or 0),
            str(summary.get("candidate_id") or ""),
        ),
        default=None,
    )

    if (
        isinstance(combined_best, dict)
        and bool(combined_best.get("passes_combined_guard"))
        and (
            single_family_best is None
            or float(combined_best.get("weighted_mean_absolute_rank_error") or 0.0)
            < float(single_family_best.get("weighted_mean_absolute_rank_error") or 0.0)
        )
    ):
        return "recommend_combined_slot_context_pilot"

    passing_single_family = [
        summary
        for summary in (of_best, p_best)
        if isinstance(summary, dict) and (bool(summary.get("passes_of_guard")) or bool(summary.get("passes_p_guard")))
    ]
    if not passing_single_family:
        return "recommend_no_slot_context_change_yet"
    best_single_family = min(
        passing_single_family,
        key=lambda summary: (
            float(summary.get("weighted_mean_absolute_rank_error") or 0.0),
            int(summary.get("worst_absolute_benchmark_error_regression") or 0),
            str(summary.get("candidate_id") or ""),
        ),
    )
    if str(best_single_family.get("candidate_group") or "").strip() == "of_only":
        return "recommend_of_split_alpha_pilot"
    if str(best_single_family.get("candidate_group") or "").strip() == "p_only":
        return "recommend_p_split_alpha_pilot"
    return "recommend_no_slot_context_change_yet"


def summarize_slot_context_candidate(
    *,
    candidate_id: str,
    candidate_review: dict[str, Any],
    control_review: dict[str, Any],
    of_alpha: float,
    p_alpha: float,
    control_of_alpha: float,
    control_p_alpha: float,
    tracked_players: Sequence[str] | None = None,
    of_target_players: Sequence[str] | None = None,
    p_target_players: Sequence[str] | None = None,
    explained_hitter_controls: Sequence[str] | None = None,
    pitcher_controls: Sequence[str] | None = None,
) -> dict[str, Any]:
    tracked_order = [
        str(player).strip()
        for player in (tracked_players or DEFAULT_SLOT_CONTEXT_MEMO_TARGET_PLAYERS)
        if str(player).strip()
    ]
    control_entries = _review_entries_by_player(control_review)
    candidate_entries = _review_entries_by_player(candidate_review)
    player_deltas = [
        _slot_context_player_delta(
            player=player,
            control_entry=control_entries.get(player),
            candidate_entry=candidate_entries.get(player),
        )
        for player in tracked_order
    ]
    delta_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in player_deltas
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    control_wmae = float(control_review.get("weighted_mean_absolute_rank_error") or 0.0)
    candidate_wmae = float(candidate_review.get("weighted_mean_absolute_rank_error") or 0.0)
    weighted_mae_improvement_pct = (
        round((control_wmae - candidate_wmae) / control_wmae, 4)
        if control_wmae > 0.0
        else 0.0
    )
    of_targets = tuple(str(player).strip() for player in (of_target_players or SLOT_CONTEXT_OF_TARGET_PLAYERS))
    p_targets = tuple(str(player).strip() for player in (p_target_players or SLOT_CONTEXT_P_TARGET_PLAYERS))
    hitter_controls = tuple(
        str(player).strip() for player in (explained_hitter_controls or SLOT_CONTEXT_EXPLAINED_HITTER_CONTROL_PLAYERS)
    )
    pitcher_control_players = tuple(
        str(player).strip() for player in (pitcher_controls or SLOT_CONTEXT_PITCHER_CONTROL_PLAYERS)
    )

    of_target_improvement_count = sum(
        int(delta_by_player[player].get("dynasty_rank_change_vs_control") or 0) >= 8
        for player in of_targets
        if isinstance(delta_by_player.get(player), dict)
    )
    p_target_improvement_count = sum(
        int(delta_by_player[player].get("dynasty_rank_change_vs_control") or 0) >= 8
        for player in p_targets
        if isinstance(delta_by_player.get(player), dict)
    )
    of_start_year_improvement_count = sum(
        int(delta_by_player[player].get("start_year_rank_change_vs_control") or 0) > 0
        for player in of_targets
        if isinstance(delta_by_player.get(player), dict)
    )
    p_start_year_improvement_count = sum(
        int(delta_by_player[player].get("start_year_rank_change_vs_control") or 0) > 0
        for player in p_targets
        if isinstance(delta_by_player.get(player), dict)
    )
    worst_explained_hitter_control_regression = max(
        (
            -int(delta_by_player[player].get("dynasty_rank_change_vs_control") or 0)
            for player in hitter_controls
            if isinstance(delta_by_player.get(player), dict)
        ),
        default=0,
    )
    worst_pitcher_control_regression = max(
        (
            -int(delta_by_player[player].get("dynasty_rank_change_vs_control") or 0)
            for player in pitcher_control_players
            if isinstance(delta_by_player.get(player), dict)
        ),
        default=0,
    )
    worst_absolute_benchmark_error_regression = max(
        (
            int(entry.get("absolute_benchmark_error_change_vs_control") or 0)
            for entry in player_deltas
            if isinstance(entry, dict)
        ),
        default=0,
    )
    candidate_group = _slot_context_candidate_group(
        control_of_alpha=control_of_alpha,
        control_p_alpha=control_p_alpha,
        candidate_of_alpha=of_alpha,
        candidate_p_alpha=p_alpha,
    )
    passes_of_guard = (
        candidate_group == "of_only"
        and weighted_mae_improvement_pct >= 0.05
        and of_target_improvement_count >= 4
        and worst_explained_hitter_control_regression <= 6
    )
    passes_p_guard = (
        candidate_group == "p_only"
        and weighted_mae_improvement_pct >= 0.02
        and p_target_improvement_count >= 2
        and worst_pitcher_control_regression <= 4
    )
    return {
        "candidate_id": str(candidate_id).strip() or "candidate",
        "candidate_group": candidate_group,
        "of_alpha": round(float(of_alpha), 4),
        "p_alpha": round(float(p_alpha), 4),
        "control_of_alpha": round(float(control_of_alpha), 4),
        "control_p_alpha": round(float(control_p_alpha), 4),
        "weighted_mean_absolute_rank_error": round(candidate_wmae, 4),
        "control_weighted_mean_absolute_rank_error": round(control_wmae, 4),
        "weighted_mae_improvement_pct": weighted_mae_improvement_pct,
        "of_target_improvement_count": of_target_improvement_count,
        "p_target_improvement_count": p_target_improvement_count,
        "of_start_year_improvement_count": of_start_year_improvement_count,
        "p_start_year_improvement_count": p_start_year_improvement_count,
        "worst_explained_hitter_control_regression": worst_explained_hitter_control_regression,
        "worst_pitcher_control_regression": worst_pitcher_control_regression,
        "worst_absolute_benchmark_error_regression": worst_absolute_benchmark_error_regression,
        "passes_of_guard": passes_of_guard,
        "passes_p_guard": passes_p_guard,
        "player_deltas": player_deltas,
    }


def review_slot_context_candidates(
    *,
    control_review: dict[str, Any],
    candidate_reviews: Mapping[str, dict[str, Any]],
    tracked_players: Sequence[str] | None = None,
    of_target_players: Sequence[str] | None = None,
    p_target_players: Sequence[str] | None = None,
    explained_hitter_controls: Sequence[str] | None = None,
    pitcher_controls: Sequence[str] | None = None,
) -> dict[str, Any]:
    control_of_alpha = 0.33
    control_p_alpha = 0.33
    control_settings = _coerce_mapping(control_review.get("settings_snapshot"))
    control_override_map = _coerce_mapping(control_settings.get("replacement_depth_blend_alpha_by_slot"))
    control_of_alpha = float(
        _coerce_float(control_override_map.get("OF"))
        or _coerce_float(control_settings.get("replacement_depth_blend_alpha"))
        or 0.33
    )
    control_p_alpha = float(
        _coerce_float(control_override_map.get("P"))
        or _coerce_float(control_settings.get("replacement_depth_blend_alpha"))
        or 0.33
    )

    candidate_summaries: list[dict[str, Any]] = []
    for candidate_id, candidate_review in candidate_reviews.items():
        if not isinstance(candidate_review, dict):
            continue
        settings_snapshot = _coerce_mapping(candidate_review.get("settings_snapshot"))
        override_map = _coerce_mapping(settings_snapshot.get("replacement_depth_blend_alpha_by_slot"))
        of_alpha = float(
            _coerce_float(override_map.get("OF"))
            or _coerce_float(settings_snapshot.get("replacement_depth_blend_alpha"))
            or control_of_alpha
        )
        p_alpha = float(
            _coerce_float(override_map.get("P"))
            or _coerce_float(settings_snapshot.get("replacement_depth_blend_alpha"))
            or control_p_alpha
        )
        candidate_summaries.append(
            summarize_slot_context_candidate(
                candidate_id=candidate_id,
                candidate_review=candidate_review,
                control_review=control_review,
                of_alpha=of_alpha,
                p_alpha=p_alpha,
                control_of_alpha=control_of_alpha,
                control_p_alpha=control_p_alpha,
                tracked_players=tracked_players,
                of_target_players=of_target_players,
                p_target_players=p_target_players,
                explained_hitter_controls=explained_hitter_controls,
                pitcher_controls=pitcher_controls,
            )
        )

    best_single_family = min(
        [
            summary
            for summary in candidate_summaries
            if str(summary.get("candidate_group") or "").strip() in {"of_only", "p_only"}
        ],
        key=lambda summary: (
            float(summary.get("weighted_mean_absolute_rank_error") or 0.0),
            int(summary.get("worst_absolute_benchmark_error_regression") or 0),
            str(summary.get("candidate_id") or ""),
        ),
        default=None,
    )
    for summary in candidate_summaries:
        if not isinstance(summary, dict):
            continue
        passes_combined_guard = (
            str(summary.get("candidate_group") or "").strip() == "combined"
            and float(summary.get("weighted_mae_improvement_pct") or 0.0) >= 0.05
            and int(summary.get("of_target_improvement_count") or 0) >= 4
            and int(summary.get("p_target_improvement_count") or 0) >= 2
            and int(summary.get("worst_explained_hitter_control_regression") or 0) <= 6
            and int(summary.get("worst_pitcher_control_regression") or 0) <= 4
            and (
                best_single_family is None
                or float(summary.get("weighted_mean_absolute_rank_error") or 0.0)
                < float(best_single_family.get("weighted_mean_absolute_rank_error") or 0.0)
            )
        )
        summary["passes_combined_guard"] = passes_combined_guard

    recommendation = _slot_context_recommendation_from_candidates(candidate_summaries)
    return {
        "profile_id": str(control_review.get("profile_id") or "standard_roto").strip() or "standard_roto",
        "projection_data_version": str(control_review.get("projection_data_version") or "").strip() or None,
        "methodology_fingerprint": str(control_review.get("methodology_fingerprint") or "").strip() or None,
        "settings_snapshot": control_settings,
        "control_weighted_mean_absolute_rank_error": float(
            control_review.get("weighted_mean_absolute_rank_error") or 0.0
        ),
        "control_of_alpha": round(control_of_alpha, 4),
        "control_p_alpha": round(control_p_alpha, 4),
        "target_players": [
            str(player).strip()
            for player in (tracked_players or DEFAULT_SLOT_CONTEXT_MEMO_TARGET_PLAYERS)
            if str(player).strip()
        ],
        "candidate_summaries": sorted(
            candidate_summaries,
            key=lambda summary: (
                float(summary.get("weighted_mean_absolute_rank_error") or 0.0),
                int(summary.get("worst_absolute_benchmark_error_regression") or 0),
                str(summary.get("candidate_id") or ""),
            ),
        ),
        "recommendation": recommendation,
    }
