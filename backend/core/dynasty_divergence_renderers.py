"""Markdown renderers for dynasty divergence review artifacts."""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from backend.core.dynasty_divergence_deep_roto import deep_roto_recommendation
from backend.core.dynasty_divergence_shared import (
    AGGREGATION_TAIL_CLASSIFICATIONS,
    DEEP_ROTO_CLASSIFICATIONS,
    DEFAULT_AGGREGATION_MEMO_TARGET_PLAYERS,
    DEFAULT_ATTRIBUTION_MEMO_TARGET_PLAYERS,
    DEFAULT_DEEP_MEMO_TARGET_PLAYERS,
    DEFAULT_MEMO_TARGET_PLAYERS,
    DEFAULT_REFRESH_MEMO_TARGET_PLAYERS,
    DEFAULT_SLOT_CONTEXT_MEMO_TARGET_PLAYERS,
    TRIAGE_BUCKETS,
    _coerce_float,
    _coerce_int,
    _coerce_mapping,
    _serialize_settings_snapshot,
    aggregation_tail_recommendation,
    attribution_recommendation,
    projection_refresh_recommendation,
)


def _format_category_entries(entries: object) -> str:
    if not isinstance(entries, list):
        return "none"
    formatted: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        category = str(entry.get("category") or "").strip()
        value = _coerce_float(entry.get("value"))
        if not category or value is None:
            continue
        formatted.append(f"{category} ({value:+.2f})")
    return ", ".join(formatted) or "none"


def _format_guard_summary(summary: object) -> str:
    if not isinstance(summary, dict):
        return "none"
    mode = str(summary.get("mode") or "").strip() or "none"
    scale = _coerce_float(summary.get("positive_credit_scale"))
    share = _coerce_float(summary.get("workload_share"))
    if scale is None and share is None:
        return mode
    pieces = [mode]
    if share is not None:
        pieces.append(f"share={share:.3f}")
    if scale is not None:
        pieces.append(f"scale={scale:.3f}")
    return ", ".join(pieces)


def _format_bounds_summary(summary: object) -> str:
    if not isinstance(summary, dict) or not bool(summary.get("applied")):
        return "none"
    flags: list[str] = []
    if bool(summary.get("player_ip_min_fill_applied")):
        flags.append("player_ip_min_fill")
    if bool(summary.get("player_ip_max_trim_applied")):
        flags.append("player_ip_max_trim")
    if bool(summary.get("base_ip_min_fill_applied")):
        flags.append("base_ip_min_fill")
    if bool(summary.get("base_ip_max_trim_applied")):
        flags.append("base_ip_max_trim")
    return ", ".join(flags) or "applied"


def _format_reference_summary(reference: object) -> str:
    if not isinstance(reference, dict):
        return "none"
    slot = str(reference.get("slot") or "").strip() or "n/a"
    volume = _coerce_mapping(reference.get("volume"))
    ab = _coerce_float(volume.get("ab"))
    ip = _coerce_float(volume.get("ip"))
    pieces = [f"slot={slot}"]
    replacement_pool_depth = _coerce_int(reference.get("replacement_pool_depth"))
    if replacement_pool_depth is not None and replacement_pool_depth > 0:
        pieces.append(f"depth={replacement_pool_depth}")
    replacement_depth_mode = str(reference.get("replacement_depth_mode") or "").strip()
    if replacement_depth_mode:
        pieces.append(f"mode={replacement_depth_mode}")
    replacement_depth_blend_alpha = _coerce_float(reference.get("replacement_depth_blend_alpha"))
    if replacement_depth_blend_alpha is not None:
        pieces.append(f"blend_alpha={replacement_depth_blend_alpha:.2f}")
    slot_count_per_team = _coerce_int(reference.get("slot_count_per_team"))
    if slot_count_per_team is not None and slot_count_per_team > 0:
        pieces.append(f"slot_count={slot_count_per_team}")
    slot_capacity_league = _coerce_int(reference.get("slot_capacity_league"))
    if slot_capacity_league is not None and slot_capacity_league > 0:
        pieces.append(f"slot_capacity={slot_capacity_league}")
    if ab is not None and abs(ab) > 1e-9:
        pieces.append(f"ab={ab:.1f}")
    if ip is not None and abs(ip) > 1e-9:
        pieces.append(f"ip={ip:.1f}")
    return ", ".join(pieces)


def _format_projection_top_stat_deltas(entries: object) -> str:
    if not isinstance(entries, list):
        return "none"
    parts: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        stat = str(entry.get("stat") or "").strip()
        delta = _coerce_float(entry.get("delta"))
        if not stat or delta is None:
            continue
        parts.append(f"{stat} ({delta:+.3f})")
    return ", ".join(parts) or "none"


def _format_projection_stat_snapshot(stats: object) -> str:
    if not isinstance(stats, dict):
        return "none"
    ordered_fields = (
        "AB",
        "R",
        "HR",
        "RBI",
        "SB",
        "AVG",
        "OPS",
        "IP",
        "W",
        "K",
        "ERA",
        "WHIP",
        "QS",
        "SV",
    )
    parts: list[str] = []
    for field in ordered_fields:
        value = _coerce_float(stats.get(field))
        if value is None:
            continue
        if field in {"AVG", "OPS", "ERA", "WHIP"}:
            parts.append(f"{field}={value:.3f}")
        else:
            parts.append(f"{field}={value:.1f}")
    return ", ".join(parts) or "none"


def _format_optional_rank_delta(value: object) -> str:
    parsed = _coerce_int(value)
    return str(parsed) if parsed is not None else "n/a"


def _format_attribution_cohort_summary(summary: object) -> str:
    if not isinstance(summary, dict):
        return "none"

    def _value(key: str) -> object:
        value = summary.get(key)
        return value if value is not None else "n/a"

    pieces = [
        f"count={int(summary.get('player_count') or 0)}",
        f"raw_rank={_value('median_raw_start_year_rank')}",
        f"replacement_rank={_value('median_start_year_rank')}",
        f"dynasty_rank={_value('median_model_rank')}",
        f"raw_to_replacement={_value('median_raw_to_replacement_penalty')}",
        f"replacement_to_dynasty={_value('median_replacement_to_dynasty_penalty')}",
    ]
    return ", ".join(pieces)


def _format_tail_preview(preview: object) -> str:
    if not isinstance(preview, list):
        return "none"
    parts: list[str] = []
    for entry in preview:
        if not isinstance(entry, dict):
            continue
        year = entry.get("year")
        adjusted = _coerce_float(entry.get("adjusted_year_value_before_discount"))
        discounted = _coerce_float(entry.get("discounted_contribution"))
        projected_ab = _coerce_float(entry.get("projected_ab"))
        projected_ip = _coerce_float(entry.get("projected_ip"))
        near_zero = bool(entry.get("near_zero_playing_time"))
        pieces = [str(year or "n/a")]
        if adjusted is not None:
            pieces.append(f"adj={adjusted:.2f}")
        if discounted is not None:
            pieces.append(f"disc={discounted:.2f}")
        if projected_ab is not None:
            pieces.append(f"ab={projected_ab:.1f}")
        if projected_ip is not None:
            pieces.append(f"ip={projected_ip:.1f}")
        if near_zero:
            pieces.append("near_zero")
        parts.append(" ".join(pieces))
    return "; ".join(parts) or "none"


def _format_aggregation_comp_tail_summaries(comps: object) -> str:
    if not isinstance(comps, list):
        return "none"
    parts: list[str] = []
    for comp in comps:
        if not isinstance(comp, dict):
            continue
        player = str(comp.get("player") or "").strip()
        if not player:
            continue
        parts.append(
            (
                f"{player} (rank {comp.get('model_rank') or 'n/a'}, start {comp.get('start_year_rank') or 'n/a'}, "
                f"positive_years {comp.get('positive_year_count') or 'n/a'}, "
                f"first_near_zero {comp.get('first_near_zero_year') or 'n/a'}, "
                f"tail_share {float(comp.get('tail_share_after_year_3') or 0.0):.4f})"
            )
        )
    return "; ".join(parts) or "none"


def render_dynasty_divergence_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Default Dynasty Divergence Review",
        "",
        f"- Profile id: `{str(review.get('profile_id') or 'standard_roto').strip() or 'standard_roto'}`",
        f"- Tracked benchmark players: {int(review.get('benchmark_player_count') or 0)}",
        f"- Review threshold: abs rank delta >= {int(review.get('delta_threshold') or 0)}",
    ]
    settings_snapshot = _serialize_settings_snapshot(review.get("settings_snapshot"))
    lines.append(f"- Settings snapshot: `{settings_snapshot}`")
    projection_data_version = str(review.get("projection_data_version") or "").strip()
    if projection_data_version:
        lines.append(f"- Projection data version: `{projection_data_version}`")
    methodology_fingerprint = str(review.get("methodology_fingerprint") or "").strip()
    if methodology_fingerprint:
        lines.append(f"- Methodology fingerprint: `{methodology_fingerprint}`")
    if bool(review.get("has_previous_projection_snapshot")):
        previous_projection_source = str(review.get("previous_projection_source") or "").strip() or "available"
        lines.append(f"- Previous projection snapshot: `{previous_projection_source}`")
    else:
        lines.append("- Previous projection snapshot: unavailable")
    lines.extend(
        [
            f"- Weighted mean absolute rank error: {float(review.get('weighted_mean_absolute_rank_error') or 0.0):.4f}",
            f"- Explained: {int((review.get('classification_counts') or {}).get('explained') or 0)}",
            f"- Suspect model gaps: {int((review.get('classification_counts') or {}).get('suspect_model_gap') or 0)}",
            f"- Needs manual review: {int((review.get('classification_counts') or {}).get('needs_manual_review') or 0)}",
            f"- Aggregation gaps: {int((review.get('triage_counts') or {}).get('aggregation_gap') or 0)}",
            f"- Raw-value gaps: {int((review.get('triage_counts') or {}).get('raw_value_gap') or 0)}",
            f"- Mixed gaps: {int((review.get('triage_counts') or {}).get('mixed_gap') or 0)}",
            "",
            "## Review Candidates",
        ]
    )
    review_candidates = review.get("review_candidates")
    review_candidates = review_candidates if isinstance(review_candidates, list) else []
    if not review_candidates:
        lines.append("")
        lines.append("No review candidates.")
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "",
            "| Player | Model Rank | Benchmark Rank | Delta | Start Rank | Best Slot | Bucket | Proj Type | Gap Label | Drivers |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for entry in review_candidates:
        if not isinstance(entry, dict):
            continue
        summary = entry.get("driver_summary")
        summary = summary if isinstance(summary, dict) else {}
        drivers = ", ".join(summary.get("driver_reasons") or []) or "none"
        delta = entry.get("rank_delta")
        delta_text = str(delta) if delta is not None else "n/a"
        lines.append(
            f"| {entry.get('player') or ''} | {entry.get('model_rank') or 'n/a'} | "
            f"{entry.get('benchmark_rank') or 'n/a'} | {delta_text} | "
            f"{entry.get('start_year_rank') or 'n/a'} | {entry.get('start_year_best_slot') or 'n/a'} | "
            f"{entry.get('triage_bucket') or 'n/a'} | {entry.get('projection_delta_type') or 'n/a'} | "
            f"{entry.get('suspect_gap_refresh_label') or 'n/a'} | {drivers} |"
        )
    slot_mover_summaries = review.get("slot_mover_summaries")
    slot_mover_summaries = slot_mover_summaries if isinstance(slot_mover_summaries, dict) else {}
    for slot_label, slot_title in (("OF", "OF Movers"), ("P", "P Movers")):
        movers = slot_mover_summaries.get(slot_label)
        movers = movers if isinstance(movers, list) else []
        lines.extend(["", f"## {slot_title}", ""])
        if not movers:
            lines.append("No movers with previous-snapshot deltas for this slot context.")
            continue
        for mover in movers:
            if not isinstance(mover, dict):
                continue
            lines.append(
                (
                    f"- {mover.get('player') or 'n/a'}: delta "
                    f"{float(mover.get('projection_composite_delta') or 0.0):+.3f}, "
                    f"type `{mover.get('projection_delta_type') or 'n/a'}`, "
                    f"model rank {mover.get('model_rank') or 'n/a'}, "
                    f"top stat shifts {_format_projection_top_stat_deltas(mover.get('projection_top_stat_deltas'))}."
                )
            )
    return "\n".join(lines) + "\n"


def render_dynasty_divergence_memo_markdown(
    review: dict[str, Any],
    *,
    target_players: Sequence[str] | None = None,
) -> str:
    target_order = [
        str(player).strip() for player in (target_players or DEFAULT_MEMO_TARGET_PLAYERS) if str(player).strip()
    ]
    entries = review.get("entries")
    entries = entries if isinstance(entries, list) else []
    entry_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    triage_summaries = review.get("triage_summaries")
    triage_summaries = triage_summaries if isinstance(triage_summaries, dict) else {}

    lines = [
        "# Default Dynasty Divergence Memo",
        "",
        f"- Profile id: `{str(review.get('profile_id') or 'standard_roto').strip() or 'standard_roto'}`",
        f"- Tracked benchmark players: {int(review.get('benchmark_player_count') or 0)}",
        f"- Settings snapshot: `{_serialize_settings_snapshot(review.get('settings_snapshot'))}`",
        (
            f"- Projection data version: `{str(review.get('projection_data_version') or '').strip()}`"
            if str(review.get("projection_data_version") or "").strip()
            else "- Projection data version: unavailable"
        ),
        (
            f"- Methodology fingerprint: `{str(review.get('methodology_fingerprint') or '').strip()}`"
            if str(review.get("methodology_fingerprint") or "").strip()
            else "- Methodology fingerprint: unavailable"
        ),
        (
            f"- Previous projection snapshot: `{str(review.get('previous_projection_source') or '').strip() or 'available'}`"
            if bool(review.get("has_previous_projection_snapshot"))
            else "- Previous projection snapshot: unavailable"
        ),
        f"- Weighted mean absolute rank error: {float(review.get('weighted_mean_absolute_rank_error') or 0.0):.4f}",
        f"- Suspect model gaps: {int((review.get('classification_counts') or {}).get('suspect_model_gap') or 0)}",
        f"- Aggregation gaps: {int((review.get('triage_counts') or {}).get('aggregation_gap') or 0)}",
        f"- Raw-value gaps: {int((review.get('triage_counts') or {}).get('raw_value_gap') or 0)}",
        f"- Mixed gaps: {int((review.get('triage_counts') or {}).get('mixed_gap') or 0)}",
        (
            f"- Attribution counts: projection `{int((review.get('attribution_counts') or {}).get('projection_shape_gap') or 0)}`, "
            f"roto conversion `{int((review.get('attribution_counts') or {}).get('roto_conversion_gap') or 0)}`, "
            f"aggregation `{int((review.get('attribution_counts') or {}).get('dynasty_aggregation_gap') or 0)}`, "
            f"mixed `{int((review.get('attribution_counts') or {}).get('mixed_gap') or 0)}`."
        ),
        "",
        "## Target Players",
        "",
    ]

    for player in target_order:
        entry = entry_by_player.get(player)
        if not isinstance(entry, dict):
            lines.extend([f"### {player}", "", "Not present in the current frozen benchmark fixture.", ""])
            continue
        bucket = str(entry.get("triage_bucket") or "unbucketed")
        model_comps = entry.get("model_comps_above")
        model_comps = model_comps if isinstance(model_comps, list) else []
        comps_text = ", ".join(
            f"{comp.get('player')} ({comp.get('model_rank')})"
            for comp in model_comps
            if isinstance(comp, dict) and str(comp.get("player") or "").strip()
        ) or "none"
        top_discounted_years = entry.get("top_discounted_years")
        top_discounted_years = top_discounted_years if isinstance(top_discounted_years, list) else []
        top_years_text = ", ".join(
            f"{year_entry.get('year')} ({float(year_entry.get('discounted_contribution') or 0.0):.2f})"
            for year_entry in top_discounted_years
            if isinstance(year_entry, dict)
        ) or "none"
        drivers = ", ".join(((entry.get("driver_summary") or {}).get("driver_reasons") or [])) or "none"
        lines.extend(
            [
                f"### {player}",
                "",
                (
                    f"- Benchmark rank {entry.get('benchmark_rank')}, model rank {entry.get('model_rank')}, "
                    f"delta {entry.get('rank_delta')}, start-year rank {entry.get('start_year_rank')}, bucket `{bucket}`."
                ),
                (
                    f"- Start-year best slot `{entry.get('start_year_best_slot') or 'n/a'}`. "
                    f"Primary raw-value cause `{entry.get('raw_value_gap_cause') or 'mixed'}`."
                ),
                (
                    f"- Raw start-year rank {entry.get('raw_start_year_rank') or 'n/a'}, raw value "
                    f"{float(entry.get('raw_start_year_value') or 0.0):.2f}, raw best slot "
                    f"`{entry.get('raw_start_year_best_slot') or 'n/a'}`. Attribution "
                    f"`{entry.get('attribution_class') or 'mixed_gap'}`."
                ),
                (
                    f"- Layer deltas: raw->replacement {_format_optional_rank_delta(entry.get('raw_to_replacement_rank_delta'))}, "
                    f"replacement->dynasty {_format_optional_rank_delta(entry.get('replacement_to_dynasty_rank_delta'))}."
                ),
                (
                    f"- Projection delta "
                    f"{float(entry.get('projection_composite_delta') or 0.0):+.3f} "
                    f"(`{entry.get('projection_delta_type') or 'missing_previous_snapshot'}`), "
                    f"top changed stats: {_format_projection_top_stat_deltas(entry.get('projection_top_stat_deltas'))}."
                ),
                (
                    f"- Start-year projection snapshot: "
                    f"{_format_projection_stat_snapshot(entry.get('start_year_projection_stats'))}."
                ),
                f"- Refresh label: `{entry.get('suspect_gap_refresh_label') or 'n/a'}`.",
                (
                    f"- Start-year value {float(entry.get('start_year_value') or 0.0):.2f}, discounted 3-year total "
                    f"{float(entry.get('discounted_three_year_total') or 0.0):.2f}, discounted full-horizon total "
                    f"{float(entry.get('discounted_full_total') or 0.0):.2f}."
                ),
                (
                    f"- Positive years {int(entry.get('positive_year_count') or 0)}, last positive year "
                    f"{entry.get('last_positive_year') or 'n/a'}, top discounted seasons: {top_years_text}."
                ),
                (
                    f"- Raw start-year positive categories: "
                    f"{_format_category_entries(entry.get('raw_start_year_top_positive_categories'))}. "
                    f"Raw start-year negative categories: "
                    f"{_format_category_entries(entry.get('raw_start_year_top_negative_categories'))}."
                ),
                (
                    f"- Start-year positive categories: {_format_category_entries(entry.get('start_year_top_positive_categories'))}. "
                    f"Start-year negative categories: {_format_category_entries(entry.get('start_year_top_negative_categories'))}."
                ),
                (
                    f"- Slot baseline reference: {_format_reference_summary(entry.get('start_year_slot_baseline_reference'))}. "
                    f"Replacement reference: {_format_reference_summary(entry.get('start_year_replacement_reference'))}."
                ),
                f"- Start-year guard summary: {_format_guard_summary(entry.get('start_year_guard_summary'))}.",
                f"- Start-year bounds summary: {_format_bounds_summary(entry.get('start_year_bounds_summary'))}.",
                f"- Players immediately above in model rank: {comps_text}.",
                f"- Explanation drivers: {drivers}.",
                "",
            ]
        )

    lines.extend(["## Bucket Summaries", ""])
    for bucket in TRIAGE_BUCKETS:
        summary = triage_summaries.get(bucket)
        summary = summary if isinstance(summary, dict) else {}
        lines.extend([f"- `{bucket}`: {summary.get('summary') or 'No summary available.'}"])
    lines.append("")
    return "\n".join(lines) + "\n"


def render_aggregation_gap_memo_markdown(
    review: dict[str, Any],
    *,
    target_players: Sequence[str] | None = None,
) -> str:
    target_order = [
        str(player).strip()
        for player in (target_players or DEFAULT_AGGREGATION_MEMO_TARGET_PLAYERS)
        if str(player).strip()
    ]
    entries = review.get("entries")
    entries = entries if isinstance(entries, list) else []
    entry_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    target_entries = [entry_by_player[player] for player in target_order if player in entry_by_player]
    recommendation = aggregation_tail_recommendation(entries, target_players=target_order)

    lines = [
        "# Default Dynasty Aggregation-Gap Memo",
        "",
        f"- Profile id: `{str(review.get('profile_id') or 'standard_roto').strip() or 'standard_roto'}`",
        f"- Tracked benchmark players: {int(review.get('benchmark_player_count') or 0)}",
        f"- Settings snapshot: `{_serialize_settings_snapshot(review.get('settings_snapshot'))}`",
        (
            f"- Projection data version: `{str(review.get('projection_data_version') or '').strip()}`"
            if str(review.get("projection_data_version") or "").strip()
            else "- Projection data version: unavailable"
        ),
        (
            f"- Methodology fingerprint: `{str(review.get('methodology_fingerprint') or '').strip()}`"
            if str(review.get("methodology_fingerprint") or "").strip()
            else "- Methodology fingerprint: unavailable"
        ),
        f"- Weighted mean absolute rank error: {float(review.get('weighted_mean_absolute_rank_error') or 0.0):.4f}",
        f"- Aggregation gaps: {int((review.get('triage_counts') or {}).get('aggregation_gap') or 0)}",
        f"- Recommendation: `{recommendation}`",
        "",
        "## Target Players",
        "",
    ]

    for player in target_order:
        entry = entry_by_player.get(player)
        if not isinstance(entry, dict):
            lines.extend([f"### {player}", "", "Not present in the current frozen benchmark fixture.", ""])
            continue
        diagnosis = str(entry.get("aggregation_tail_classification") or "mixed")
        lines.extend(
            [
                f"### {player}",
                "",
                (
                    f"- Benchmark rank {entry.get('benchmark_rank')}, model rank {entry.get('model_rank')}, "
                    f"start-year rank {entry.get('start_year_rank')}, diagnosis `{diagnosis}`."
                ),
                (
                    f"- Projection delta {float(entry.get('projection_composite_delta') or 0.0):+.3f} "
                    f"(`{entry.get('projection_delta_type') or 'missing_previous_snapshot'}`), "
                    f"top changed stats: {_format_projection_top_stat_deltas(entry.get('projection_top_stat_deltas'))}."
                ),
                (
                    f"- Discounted 3-year total {float(entry.get('discounted_three_year_total') or 0.0):.2f}, "
                    f"discounted full-horizon total {float(entry.get('discounted_full_total') or 0.0):.2f}."
                ),
                (
                    f"- Positive years {int(entry.get('positive_year_count') or 0)}, last positive year "
                    f"{entry.get('last_positive_year') or 'n/a'}, first near-zero year "
                    f"{entry.get('first_near_zero_year') or 'n/a'}."
                ),
                (
                    f"- First non-positive adjusted year {entry.get('first_non_positive_adjusted_year') or 'n/a'}, "
                    f"positive-year span {entry.get('positive_year_span') or 0}, "
                    f"tail after year 3 {float(entry.get('tail_value_after_year_3') or 0.0):.2f} "
                    f"(share {float(entry.get('tail_share_after_year_3') or 0.0):.4f})."
                ),
                f"- Tail preview: {_format_tail_preview(entry.get('tail_preview'))}.",
                (
                    f"- Players immediately above in model rank: "
                    f"{_format_aggregation_comp_tail_summaries(entry.get('model_comps_above'))}."
                ),
                (
                    f"- Median comp positive-year count: "
                    f"{entry.get('aggregation_comp_positive_year_count_median') or 'n/a'}."
                ),
                "",
            ]
        )

    classification_counts = Counter(
        str(entry.get("aggregation_tail_classification") or "").strip()
        for entry in target_entries
        if str(entry.get("aggregation_tail_classification") or "").strip()
    )
    summary_bits = [
        f"{int(classification_counts.get(label, 0))} `{label}`"
        for label in AGGREGATION_TAIL_CLASSIFICATIONS
        if int(classification_counts.get(label, 0)) > 0
    ]
    summary_text = ", ".join(summary_bits) or "no classified targets"
    lines.extend(
        [
            "## Root Cause Summary",
            "",
            f"- Target classification mix: {summary_text}.",
        ]
    )
    if recommendation == "recommend_tail_pilot":
        lines.append(
            "- All tracked aggregation targets classify as `comp_horizon_gap`, so the next milestone should be a bounded established-MLB hitter tail-smoothing pilot."
        )
    else:
        lines.append(
            "- The target set does not reduce to one clean shared aggregation mechanism yet, so no methodology change is recommended from this diagnostic pass."
        )
    lines.extend(["", "## Recommendation", "", f"- `{recommendation}`", ""])
    return "\n".join(lines)


def render_projection_refresh_memo_markdown(
    review: dict[str, Any],
    *,
    target_players: Sequence[str] | None = None,
    recommendation_override: str | None = None,
) -> str:
    target_order = [
        str(player).strip()
        for player in (target_players or DEFAULT_REFRESH_MEMO_TARGET_PLAYERS)
        if str(player).strip()
    ]
    entries = review.get("entries")
    entries = entries if isinstance(entries, list) else []
    entry_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    recommendation = projection_refresh_recommendation(
        entries,
        target_players=target_order,
        recommendation_override=recommendation_override,
    )
    slot_mover_summaries = review.get("slot_mover_summaries")
    slot_mover_summaries = slot_mover_summaries if isinstance(slot_mover_summaries, dict) else {}

    lines = [
        "# Default Dynasty Projection Refresh Memo",
        "",
        f"- Profile id: `{str(review.get('profile_id') or 'standard_roto').strip() or 'standard_roto'}`",
        f"- Tracked benchmark players: {int(review.get('benchmark_player_count') or 0)}",
        f"- Settings snapshot: `{_serialize_settings_snapshot(review.get('settings_snapshot'))}`",
        (
            f"- Projection data version: `{str(review.get('projection_data_version') or '').strip()}`"
            if str(review.get("projection_data_version") or "").strip()
            else "- Projection data version: unavailable"
        ),
        (
            f"- Methodology fingerprint: `{str(review.get('methodology_fingerprint') or '').strip()}`"
            if str(review.get("methodology_fingerprint") or "").strip()
            else "- Methodology fingerprint: unavailable"
        ),
        (
            f"- Previous projection snapshot: `{str(review.get('previous_projection_source') or '').strip() or 'available'}`"
            if bool(review.get("has_previous_projection_snapshot"))
            else "- Previous projection snapshot: unavailable"
        ),
        f"- Weighted mean absolute rank error: {float(review.get('weighted_mean_absolute_rank_error') or 0.0):.4f}",
        f"- Suspect model gaps: {int((review.get('classification_counts') or {}).get('suspect_model_gap') or 0)}",
        f"- Aggregation gaps: {int((review.get('triage_counts') or {}).get('aggregation_gap') or 0)}",
        f"- Raw-value gaps: {int((review.get('triage_counts') or {}).get('raw_value_gap') or 0)}",
        "",
        "## Target Players",
        "",
    ]

    for player in target_order:
        entry = entry_by_player.get(player)
        if not isinstance(entry, dict):
            lines.extend([f"### {player}", "", "Not present in the current frozen benchmark fixture.", ""])
            continue
        lines.extend(
            [
                f"### {player}",
                "",
                (
                    f"- Benchmark rank {entry.get('benchmark_rank')}, model rank {entry.get('model_rank')}, "
                    f"start-year rank {entry.get('start_year_rank')}, bucket `{entry.get('triage_bucket') or 'n/a'}`, "
                    f"classification `{entry.get('classification') or 'n/a'}`."
                ),
                (
                    f"- Projection delta {float(entry.get('projection_composite_delta') or 0.0):+.3f} "
                    f"(`{entry.get('projection_delta_type') or 'missing_previous_snapshot'}`); "
                    f"top changed stats: {_format_projection_top_stat_deltas(entry.get('projection_top_stat_deltas'))}."
                ),
                f"- Refresh label: `{entry.get('suspect_gap_refresh_label') or 'n/a'}`.",
                "",
            ]
        )

    for slot_label, slot_title in (("OF", "OF Slot Movers"), ("P", "P Slot Movers")):
        movers = slot_mover_summaries.get(slot_label)
        movers = movers if isinstance(movers, list) else []
        lines.extend([f"## {slot_title}", ""])
        if not movers:
            lines.extend(["No movers with previous-snapshot delta data for this slot group.", ""])
            continue
        for mover in movers:
            if not isinstance(mover, dict):
                continue
            lines.append(
                (
                    f"- {mover.get('player') or 'n/a'}: delta "
                    f"{float(mover.get('projection_composite_delta') or 0.0):+.3f}, "
                    f"type `{mover.get('projection_delta_type') or 'n/a'}`, "
                    f"model rank {mover.get('model_rank') or 'n/a'}, "
                    f"top stat shifts {_format_projection_top_stat_deltas(mover.get('projection_top_stat_deltas'))}."
                )
            )
        lines.append("")

    lines.extend(["## Recommendation", "", f"- `{recommendation}`", ""])
    return "\n".join(lines)


def render_attribution_memo_markdown(
    review: dict[str, Any],
    *,
    target_players: Sequence[str] | None = None,
) -> str:
    target_order = [
        str(player).strip()
        for player in (target_players or DEFAULT_ATTRIBUTION_MEMO_TARGET_PLAYERS)
        if str(player).strip()
    ]
    entries = review.get("entries")
    entries = entries if isinstance(entries, list) else []
    entry_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    recommendation = attribution_recommendation(entries, target_players=target_order)
    attribution_cohort_summaries = review.get("attribution_cohort_summaries")
    attribution_cohort_summaries = (
        attribution_cohort_summaries if isinstance(attribution_cohort_summaries, dict) else {}
    )

    lines = [
        "# Default Dynasty Attribution Memo",
        "",
        f"- Profile id: `{str(review.get('profile_id') or 'standard_roto').strip() or 'standard_roto'}`",
        f"- Tracked benchmark players: {int(review.get('benchmark_player_count') or 0)}",
        f"- Settings snapshot: `{_serialize_settings_snapshot(review.get('settings_snapshot'))}`",
        (
            f"- Projection data version: `{str(review.get('projection_data_version') or '').strip()}`"
            if str(review.get("projection_data_version") or "").strip()
            else "- Projection data version: unavailable"
        ),
        (
            f"- Methodology fingerprint: `{str(review.get('methodology_fingerprint') or '').strip()}`"
            if str(review.get("methodology_fingerprint") or "").strip()
            else "- Methodology fingerprint: unavailable"
        ),
        f"- Weighted mean absolute rank error: {float(review.get('weighted_mean_absolute_rank_error') or 0.0):.4f}",
        (
            f"- Attribution counts: projection `{int((review.get('attribution_counts') or {}).get('projection_shape_gap') or 0)}`, "
            f"roto conversion `{int((review.get('attribution_counts') or {}).get('roto_conversion_gap') or 0)}`, "
            f"aggregation `{int((review.get('attribution_counts') or {}).get('dynasty_aggregation_gap') or 0)}`, "
            f"mixed `{int((review.get('attribution_counts') or {}).get('mixed_gap') or 0)}`."
        ),
        f"- Recommendation: `{recommendation}`",
        "",
        "## Target Players",
        "",
    ]

    for player in target_order:
        entry = entry_by_player.get(player)
        if not isinstance(entry, dict):
            lines.extend([f"### {player}", "", "Not present in the current frozen benchmark fixture.", ""])
            continue
        model_comps = entry.get("model_comps_above")
        model_comps = model_comps if isinstance(model_comps, list) else []
        comps_text = ", ".join(
            f"{comp.get('player')} ({comp.get('model_rank')})"
            for comp in model_comps
            if isinstance(comp, dict) and str(comp.get("player") or "").strip()
        ) or "none"
        lines.extend(
            [
                f"### {player}",
                "",
                (
                    f"- Benchmark rank {entry.get('benchmark_rank')}, raw start-year rank "
                    f"{entry.get('raw_start_year_rank') or 'n/a'} / value {float(entry.get('raw_start_year_value') or 0.0):.2f}, "
                    f"replacement start-year rank {entry.get('start_year_rank') or 'n/a'} / value "
                    f"{float(entry.get('start_year_value') or 0.0):.2f}, dynasty rank {entry.get('model_rank') or 'n/a'} / value "
                    f"{float(entry.get('dynasty_value') or 0.0):.2f}."
                ),
                (
                    f"- Raw best slot `{entry.get('raw_start_year_best_slot') or 'n/a'}`, replacement best slot "
                    f"`{entry.get('start_year_best_slot') or 'n/a'}`, attribution `{entry.get('attribution_class') or 'mixed_gap'}`."
                ),
                (
                    f"- Rank penalties: raw->replacement {_format_optional_rank_delta(entry.get('raw_to_replacement_rank_delta'))}, "
                    f"replacement->dynasty {_format_optional_rank_delta(entry.get('replacement_to_dynasty_rank_delta'))}."
                ),
                (
                    f"- Raw top positive categories: "
                    f"{_format_category_entries(entry.get('raw_start_year_top_positive_categories'))}. "
                    f"Raw top negative categories: "
                    f"{_format_category_entries(entry.get('raw_start_year_top_negative_categories'))}."
                ),
                (
                    f"- Replacement top positive categories: "
                    f"{_format_category_entries(entry.get('start_year_top_positive_categories'))}. "
                    f"Replacement top negative categories: "
                    f"{_format_category_entries(entry.get('start_year_top_negative_categories'))}."
                ),
                (
                    f"- Start-year projection snapshot: "
                    f"{_format_projection_stat_snapshot(entry.get('start_year_projection_stats'))}."
                ),
                (
                    f"- Projection delta {float(entry.get('projection_composite_delta') or 0.0):+.3f} "
                    f"(`{entry.get('projection_delta_type') or 'missing_previous_snapshot'}`); "
                    f"top changed stats: {_format_projection_top_stat_deltas(entry.get('projection_top_stat_deltas'))}."
                ),
                f"- Players immediately above in model rank: {comps_text}.",
                "",
            ]
        )

    lines.extend(
        [
            "## Cohort Summaries",
            "",
            f"- OF targets: {_format_attribution_cohort_summary(attribution_cohort_summaries.get('of_targets'))}.",
            f"- OF controls: {_format_attribution_cohort_summary(attribution_cohort_summaries.get('of_controls'))}.",
            f"- P targets: {_format_attribution_cohort_summary(attribution_cohort_summaries.get('p_targets'))}.",
            f"- P controls: {_format_attribution_cohort_summary(attribution_cohort_summaries.get('p_controls'))}.",
            "",
            "## Recommendation",
            "",
            f"- `{recommendation}`",
            "",
        ]
    )
    if recommendation == "recommend_projection_input_reaudit":
        lines.append(
            "- Next pass should target workbook and projection-shape validation before any valuation-methodology pilot."
        )
    elif recommendation == "recommend_roto_conversion_followup":
        lines.append("- Next pass should target one-year roto conversion, slot baselines, and category/replacement logic.")
    elif recommendation == "recommend_aggregation_followup":
        lines.append(
            "- Next pass should target dynasty aggregation for established MLB hitters rather than one-year conversion."
        )
    else:
        lines.append("- No live methodology pilot is recommended until a cleaner repeated mechanism emerges.")
    lines.append("")
    return "\n".join(lines)


def render_slot_context_memo_markdown(
    review: dict[str, Any],
    *,
    target_players: Sequence[str] | None = None,
) -> str:
    target_order = [
        str(player).strip()
        for player in (target_players or DEFAULT_SLOT_CONTEXT_MEMO_TARGET_PLAYERS)
        if str(player).strip()
    ]
    candidate_summaries = review.get("candidate_summaries")
    candidate_summaries = candidate_summaries if isinstance(candidate_summaries, list) else []
    candidate_labels = {
        str(summary.get("candidate_id") or "").strip(): (
            f"OF={float(summary.get('of_alpha') or 0.0):.2f}, P={float(summary.get('p_alpha') or 0.0):.2f}"
        )
        for summary in candidate_summaries
        if isinstance(summary, dict) and str(summary.get("candidate_id") or "").strip()
    }
    player_by_candidate: dict[str, dict[str, dict[str, Any]]] = {}
    for summary in candidate_summaries:
        if not isinstance(summary, dict):
            continue
        candidate_id = str(summary.get("candidate_id") or "").strip()
        player_deltas = summary.get("player_deltas")
        player_deltas = player_deltas if isinstance(player_deltas, list) else []
        player_by_candidate[candidate_id] = {
            str(entry.get("player") or "").strip(): entry
            for entry in player_deltas
            if isinstance(entry, dict) and str(entry.get("player") or "").strip()
        }

    lines = [
        "# Default Dynasty Slot-Context Memo",
        "",
        f"- Profile id: `{str(review.get('profile_id') or 'standard_roto').strip() or 'standard_roto'}`",
        f"- Settings snapshot: `{_serialize_settings_snapshot(review.get('settings_snapshot'))}`",
        (
            f"- Projection data version: `{str(review.get('projection_data_version') or '').strip()}`"
            if str(review.get("projection_data_version") or "").strip()
            else "- Projection data version: unavailable"
        ),
        (
            f"- Methodology fingerprint: `{str(review.get('methodology_fingerprint') or '').strip()}`"
            if str(review.get("methodology_fingerprint") or "").strip()
            else "- Methodology fingerprint: unavailable"
        ),
        f"- Control weighted MAE: {float(review.get('control_weighted_mean_absolute_rank_error') or 0.0):.4f}",
        (
            f"- Control slot alphas: OF={float(review.get('control_of_alpha') or 0.0):.2f}, "
            f"P={float(review.get('control_p_alpha') or 0.0):.2f}"
        ),
        "",
        "## Candidate Matrix",
        "",
        "| Candidate | Group | OF Alpha | P Alpha | WMAE | WMAE vs Control | OF +8 | P +8 | Worst Hitter Control Reg | Worst Pitcher Control Reg | Recommendation Guards |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for summary in candidate_summaries:
        if not isinstance(summary, dict):
            continue
        guard_bits: list[str] = []
        if bool(summary.get("passes_of_guard")):
            guard_bits.append("OF")
        if bool(summary.get("passes_p_guard")):
            guard_bits.append("P")
        if bool(summary.get("passes_combined_guard")):
            guard_bits.append("Combined")
        lines.append(
            f"| {summary.get('candidate_id') or 'n/a'} | {summary.get('candidate_group') or 'n/a'} | "
            f"{float(summary.get('of_alpha') or 0.0):.2f} | {float(summary.get('p_alpha') or 0.0):.2f} | "
            f"{float(summary.get('weighted_mean_absolute_rank_error') or 0.0):.4f} | "
            f"{float(summary.get('weighted_mae_improvement_pct') or 0.0):+.2%} | "
            f"{int(summary.get('of_target_improvement_count') or 0)} | "
            f"{int(summary.get('p_target_improvement_count') or 0)} | "
            f"{int(summary.get('worst_explained_hitter_control_regression') or 0)} | "
            f"{int(summary.get('worst_pitcher_control_regression') or 0)} | "
            f"{', '.join(guard_bits) or 'none'} |"
        )

    lines.extend(["", "## Target Players", ""])
    for player in target_order:
        lines.extend([f"### {player}", ""])
        found_any = False
        for candidate_id, candidate_label in candidate_labels.items():
            player_entry = player_by_candidate.get(candidate_id, {}).get(player)
            if not isinstance(player_entry, dict):
                continue
            found_any = True
            lines.extend(
                [
                    (
                        f"- {candidate_id} (`{candidate_label}`): dynasty rank "
                        f"{player_entry.get('candidate_model_rank') or 'n/a'} "
                        f"(benchmark error change {int(player_entry.get('absolute_benchmark_error_change_vs_control') or 0):+d}), "
                        f"start-year rank {player_entry.get('candidate_start_year_rank') or 'n/a'} "
                        f"(change {int(player_entry.get('start_year_rank_change_vs_control') or 0):+d}), "
                        f"start-year value change {float(player_entry.get('start_year_value_change_vs_control') or 0.0):+.4f}."
                    ),
                    (
                        f"  3-year total change {float(player_entry.get('discounted_three_year_total_change_vs_control') or 0.0):+.4f}, "
                        f"full-horizon change {float(player_entry.get('discounted_full_total_change_vs_control') or 0.0):+.4f}, "
                        f"replacement reference {_format_reference_summary(player_entry.get('candidate_start_year_replacement_reference'))}."
                    ),
                ]
            )
        if not found_any:
            lines.append("Not present in the current candidate review set.")
        lines.append("")

    recommendation = str(review.get("recommendation") or "recommend_no_slot_context_change_yet").strip()
    lines.extend(["## Recommendation", "", f"- `{recommendation}`", ""])
    return "\n".join(lines)


def render_deep_roto_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Deep Dynasty Roto Audit Review",
        "",
        f"- Profile id: `{str(review.get('profile_id') or 'deep_roto').strip() or 'deep_roto'}`",
        f"- Comparison profile: `{str(review.get('comparison_profile_id') or 'standard_roto').strip() or 'standard_roto'}`",
        f"- Settings snapshot: `{_serialize_settings_snapshot(review.get('settings_snapshot'))}`",
    ]
    projection_data_version = str(review.get("projection_data_version") or "").strip()
    if projection_data_version:
        lines.append(f"- Projection data version: `{projection_data_version}`")
    methodology_fingerprint = str(review.get("methodology_fingerprint") or "").strip()
    if methodology_fingerprint:
        lines.append(f"- Methodology fingerprint: `{methodology_fingerprint}`")
    diagnostics_summary = review.get("valuation_diagnostics_summary")
    diagnostics_summary = diagnostics_summary if isinstance(diagnostics_summary, dict) else {}
    lines.extend(
        [
            f"- Centering mode: `{diagnostics_summary.get('CenteringMode') or 'n/a'}`",
            f"- Forced-roster fallback applied: `{bool(diagnostics_summary.get('ForcedRosterFallbackApplied'))}`",
            f"- Residual minor-slot cost applied: `{bool(diagnostics_summary.get('ResidualMinorSlotCostApplied'))}`",
            f"- Deep zero-baseline warning: `{bool(diagnostics_summary.get('deep_roster_zero_baseline_warning'))}`",
            f"- Recommendation: `{str(review.get('recommendation') or 'recommend_no_deep_specific_change_yet')}`",
            "",
            "## Review Candidates",
            "",
            "| Player | Std Rank | Deep Rank | Delta | Classification | Deep Slot | Top Categories |",
            "| --- | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    review_candidates = review.get("review_candidates")
    review_candidates = review_candidates if isinstance(review_candidates, list) else []
    for entry in review_candidates:
        if not isinstance(entry, dict):
            continue
        lines.append(
            f"| {entry.get('player') or ''} | {entry.get('standard_rank') or 'n/a'} | "
            f"{entry.get('deep_rank') or 'n/a'} | {entry.get('rank_delta_vs_standard') or 0:+d} | "
            f"{entry.get('deep_change_classification') or 'n/a'} | {entry.get('deep_start_year_best_slot') or 'n/a'} | "
            f"{_format_category_entries(entry.get('deep_top_positive_categories'))} |"
        )
    return "\n".join(lines) + "\n"


def render_deep_roto_memo_markdown(
    review: dict[str, Any],
    *,
    target_players: Sequence[str] | None = None,
) -> str:
    target_order = [
        str(player).strip()
        for player in (target_players or DEFAULT_DEEP_MEMO_TARGET_PLAYERS)
        if str(player).strip()
    ]
    entries = review.get("entries")
    entries = entries if isinstance(entries, list) else []
    entry_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    recommendation = deep_roto_recommendation(entries, target_players=target_order)
    classification_counts = Counter(
        str(entry.get("deep_change_classification") or "").strip()
        for entry in entries
        if str(entry.get("deep_change_classification") or "").strip() in DEEP_ROTO_CLASSIFICATIONS
    )
    lines = [
        "# Deep Dynasty Roto Audit Memo",
        "",
        f"- Profile id: `{str(review.get('profile_id') or 'deep_roto').strip() or 'deep_roto'}`",
        f"- Comparison profile: `{str(review.get('comparison_profile_id') or 'standard_roto').strip() or 'standard_roto'}`",
        f"- Settings snapshot: `{_serialize_settings_snapshot(review.get('settings_snapshot'))}`",
        (
            f"- Projection data version: `{str(review.get('projection_data_version') or '').strip()}`"
            if str(review.get("projection_data_version") or "").strip()
            else "- Projection data version: unavailable"
        ),
        (
            f"- Methodology fingerprint: `{str(review.get('methodology_fingerprint') or '').strip()}`"
            if str(review.get("methodology_fingerprint") or "").strip()
            else "- Methodology fingerprint: unavailable"
        ),
        f"- Recommendation: `{recommendation}`",
        "",
        "## Target Players",
        "",
    ]
    for player in target_order:
        entry = entry_by_player.get(player)
        if not isinstance(entry, dict):
            lines.extend([f"### {player}", "", "Player not present in the current projection snapshot.", ""])
            continue
        deep_centering = _coerce_mapping(entry.get("deep_centering"))
        lines.extend(
            [
                f"### {player}",
                "",
                (
                    f"- Standard rank {entry.get('standard_rank')}, deep rank {entry.get('deep_rank')}, "
                    f"delta {int(_coerce_int(entry.get('rank_delta_vs_standard')) or 0):+d}, "
                    f"classification `{entry.get('deep_change_classification') or 'n/a'}`."
                ),
                (
                    f"- Start-year slot standard `{entry.get('standard_start_year_best_slot') or 'n/a'}` vs deep "
                    f"`{entry.get('deep_start_year_best_slot') or 'n/a'}`."
                ),
                (
                    f"- Deep centering: mode `{deep_centering.get('mode') or 'standard'}`, "
                    f"fallback `{bool(deep_centering.get('fallback_applied'))}`, "
                    f"forced-roster value {float(_coerce_float(deep_centering.get('forced_roster_value')) or 0.0):.2f}."
                ),
                (
                    f"- Replacement reference: {_format_reference_summary(entry.get('deep_replacement_reference'))}. "
                    f"Baseline reference: {_format_reference_summary(entry.get('deep_slot_baseline_reference'))}."
                ),
                (
                    f"- Start-year positives: {_format_category_entries(entry.get('deep_top_positive_categories'))}. "
                    f"Start-year negatives: {_format_category_entries(entry.get('deep_top_negative_categories'))}."
                ),
                (
                    f"- Top dynasty stat contributions: {_format_category_entries(entry.get('deep_top_stat_contributions'))}. "
                    f"Tail share after year 3: {float(entry.get('deep_tail_share_after_year_3') or 0.0):.4f}."
                ),
                "",
            ]
        )
    summary_bits = [
        f"{int(classification_counts.get(label, 0))} `{label}`"
        for label in DEEP_ROTO_CLASSIFICATIONS
        if int(classification_counts.get(label, 0)) > 0
    ]
    lines.extend(
        [
            "## Root Cause Summary",
            "",
            f"- Classification mix: {', '.join(summary_bits) or 'no classified targets'}.",
            "",
            "## Recommendation",
            "",
            f"- `{recommendation}`",
            "",
        ]
    )
    return "\n".join(lines)
