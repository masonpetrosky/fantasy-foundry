"""Helpers for reviewing default dynasty ranking divergences against a frozen benchmark."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

_NORMALIZE_PLAYER_RE = re.compile(r"[^a-z0-9]+")
DEFAULT_DYNASTY_BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "default_roto_consensus_2026-03-21.json"
)
DEFAULT_MEMO_TARGET_PLAYERS: tuple[str, ...] = (
    "Corbin Carroll",
    "Yordan Alvarez",
    "Kyle Tucker",
    "Yoshinobu Yamamoto",
    "Roman Anthony",
    "Fernando Tatis Jr.",
    "Wyatt Langford",
    "Bryan Woo",
    "Pete Crow-Armstrong",
)
DEFAULT_AGGREGATION_MEMO_TARGET_PLAYERS: tuple[str, ...] = (
    "Aaron Judge",
    "Ronald Acuna Jr.",
    "Jose Ramirez",
)
DEFAULT_REFRESH_MEMO_TARGET_PLAYERS: tuple[str, ...] = (
    "Corbin Carroll",
    "Yordan Alvarez",
    "Kyle Tucker",
    "Yoshinobu Yamamoto",
    "Roman Anthony",
    "Fernando Tatis Jr.",
    "Wyatt Langford",
    "Bryan Woo",
    "Pete Crow-Armstrong",
    "Aaron Judge",
    "Ronald Acuna Jr.",
    "Jose Ramirez",
)
DEFAULT_ATTRIBUTION_MEMO_TARGET_PLAYERS: tuple[str, ...] = (
    "Yordan Alvarez",
    "Kyle Tucker",
    "Fernando Tatis Jr.",
    "Aaron Judge",
    "Ronald Acuna Jr.",
    "Jose Ramirez",
    "Yoshinobu Yamamoto",
    "Bryan Woo",
)
DEFAULT_ATTRIBUTION_EXPLAINED_CONTROL_PLAYERS: tuple[str, ...] = (
    "Corbin Carroll",
    "Roman Anthony",
    "Wyatt Langford",
    "Pete Crow-Armstrong",
    "Juan Soto",
    "Julio Rodriguez",
    "Paul Skenes",
    "Tarik Skubal",
)
ATTRIBUTION_OF_TARGET_PLAYERS: tuple[str, ...] = (
    "Yordan Alvarez",
    "Kyle Tucker",
    "Fernando Tatis Jr.",
    "Aaron Judge",
    "Ronald Acuna Jr.",
)
ATTRIBUTION_OF_CONTROL_PLAYERS: tuple[str, ...] = (
    "Corbin Carroll",
    "Roman Anthony",
    "Wyatt Langford",
    "Pete Crow-Armstrong",
    "Juan Soto",
    "Julio Rodriguez",
)
ATTRIBUTION_P_TARGET_PLAYERS: tuple[str, ...] = (
    "Yoshinobu Yamamoto",
    "Bryan Woo",
)
ATTRIBUTION_P_CONTROL_PLAYERS: tuple[str, ...] = (
    "Paul Skenes",
    "Tarik Skubal",
)
DEFAULT_SLOT_CONTEXT_MEMO_TARGET_PLAYERS: tuple[str, ...] = (
    "Yordan Alvarez",
    "Kyle Tucker",
    "Fernando Tatis Jr.",
    "Aaron Judge",
    "Ronald Acuna Jr.",
    "Yoshinobu Yamamoto",
    "Bryan Woo",
    "Jose Ramirez",
    "Corbin Carroll",
    "Roman Anthony",
    "Wyatt Langford",
    "Pete Crow-Armstrong",
    "Juan Soto",
    "Julio Rodriguez",
    "Paul Skenes",
    "Tarik Skubal",
)
SLOT_CONTEXT_OF_TARGET_PLAYERS: tuple[str, ...] = (
    "Yordan Alvarez",
    "Kyle Tucker",
    "Fernando Tatis Jr.",
    "Aaron Judge",
    "Ronald Acuna Jr.",
)
SLOT_CONTEXT_P_TARGET_PLAYERS: tuple[str, ...] = (
    "Yoshinobu Yamamoto",
    "Bryan Woo",
)
SLOT_CONTEXT_NEGATIVE_CONTROL_PLAYERS: tuple[str, ...] = ("Jose Ramirez",)
SLOT_CONTEXT_EXPLAINED_CONTROL_PLAYERS: tuple[str, ...] = (
    "Corbin Carroll",
    "Roman Anthony",
    "Wyatt Langford",
    "Pete Crow-Armstrong",
    "Juan Soto",
    "Julio Rodriguez",
    "Paul Skenes",
    "Tarik Skubal",
)
SLOT_CONTEXT_EXPLAINED_HITTER_CONTROL_PLAYERS: tuple[str, ...] = (
    "Corbin Carroll",
    "Roman Anthony",
    "Wyatt Langford",
    "Pete Crow-Armstrong",
    "Juan Soto",
    "Julio Rodriguez",
)
SLOT_CONTEXT_PITCHER_CONTROL_PLAYERS: tuple[str, ...] = (
    "Paul Skenes",
    "Tarik Skubal",
)
SLOT_CONTEXT_RECOMMENDATIONS: tuple[str, ...] = (
    "recommend_of_split_alpha_pilot",
    "recommend_p_split_alpha_pilot",
    "recommend_combined_slot_context_pilot",
    "recommend_no_slot_context_change_yet",
)
TRIAGE_BUCKETS: tuple[str, ...] = ("aggregation_gap", "raw_value_gap", "mixed_gap")
RAW_VALUE_CAUSES: tuple[str, ...] = (
    "slot_replacement_context",
    "projected_volume",
    "guard_attenuation",
    "pitching_bounds",
    "mixed",
)
AGGREGATION_TAIL_CLASSIFICATIONS: tuple[str, ...] = ("short_positive_tail", "comp_horizon_gap", "mixed")
AGGREGATION_TAIL_RECOMMENDATIONS: tuple[str, ...] = (
    "recommend_tail_pilot",
    "recommend_no_methodology_change_yet",
)
PROJECTION_DELTA_TYPES: tuple[str, ...] = (
    "material_riser",
    "material_faller",
    "stable",
    "missing_previous_snapshot",
)
SUSPECT_GAP_LABELS: tuple[str, ...] = (
    "stable_model_gap",
    "player_projection_shift",
    "manual_review",
)
REFRESH_RECOMMENDATIONS: tuple[str, ...] = (
    "recommend_resume_model_gap_work",
    "recommend_refresh_specific_reaudit",
    "recommend_default_revalidation",
)
ATTRIBUTION_CLASSES: tuple[str, ...] = (
    "projection_shape_gap",
    "roto_conversion_gap",
    "dynasty_aggregation_gap",
    "mixed_gap",
)
ATTRIBUTION_RECOMMENDATIONS: tuple[str, ...] = (
    "recommend_projection_input_reaudit",
    "recommend_roto_conversion_followup",
    "recommend_aggregation_followup",
    "recommend_no_change_yet",
)
AUDIT_PROFILE_IDS: tuple[str, ...] = (
    "standard_roto",
    "deep_roto",
    "points_season_total",
    "points_weekly_h2h",
    "points_daily_h2h",
)
DEFAULT_DEEP_MEMO_TARGET_PLAYERS: tuple[str, ...] = (
    "Roman Anthony",
    "Ethan Salas",
    "Cal Raleigh",
    "Mason Miller",
    "Jurickson Profar",
    "Eugenio Suarez",
    "Aaron Judge",
    "Ronald Acuna Jr.",
)
DEEP_ROTO_CLASSIFICATIONS: tuple[str, ...] = (
    "deep_replacement_context",
    "forced_roster_centering",
    "stash_economics",
    "category_mix",
    "aggregation_tail",
)
DEEP_ROTO_RECOMMENDATIONS: tuple[str, ...] = (
    "recommend_deep_roto_methodology_followup",
    "recommend_no_deep_specific_change_yet",
)


def normalize_player_name(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return _NORMALIZE_PLAYER_RE.sub("-", text).strip("-")


def load_dynasty_benchmark(path: str | Path | None = None) -> list[dict[str, Any]]:
    benchmark_path = Path(path or DEFAULT_DYNASTY_BENCHMARK_PATH).expanduser().resolve()
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Benchmark fixture {benchmark_path} must be a JSON array.")

    out: list[dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        player = str(entry.get("player") or "").strip()
        benchmark_rank = entry.get("benchmark_rank")
        try:
            rank_value = int(benchmark_rank)
        except (TypeError, ValueError):
            continue
        if not player or rank_value <= 0:
            continue
        out.append(
            {
                "player": player,
                "player_key": normalize_player_name(player),
                "benchmark_rank": rank_value,
                "source": str(entry.get("source") or "").strip() or None,
                "notes": str(entry.get("notes") or "").strip() or None,
            }
        )
    return out


def _coerce_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_category_entries(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _coerce_mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _category_sgp_mapping_from_row(row: object) -> dict[str, float]:
    if not isinstance(row, dict):
        return {}
    out: dict[str, float] = {}
    for raw_key, raw_value in row.items():
        key = str(raw_key or "").strip()
        if not key.startswith("SGP_"):
            continue
        value = _coerce_float(raw_value)
        if value is None:
            continue
        out[key[4:]] = round(float(value), 4)
    return out


def _top_category_entries_from_mapping(
    category_sgp: Mapping[str, object] | None,
    *,
    positive: bool,
    limit: int = 3,
) -> list[dict[str, Any]]:
    entries: list[tuple[str, float]] = []
    for raw_category, raw_value in dict(category_sgp or {}).items():
        category = str(raw_category or "").strip()
        value = _coerce_float(raw_value)
        if not category or value is None:
            continue
        if positive and value <= 0.0:
            continue
        if not positive and value >= 0.0:
            continue
        entries.append((category, float(value)))
    sorted_entries = sorted(
        entries,
        key=(lambda item: (-item[1], item[0])) if positive else (lambda item: (item[1], item[0])),
    )[:limit]
    return [{"category": category, "value": round(value, 4)} for category, value in sorted_entries]


def _projection_stat_snapshot(stats: object) -> dict[str, float]:
    if not isinstance(stats, dict):
        return {}
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
    out: dict[str, float] = {}
    for field in ordered_fields:
        value = _coerce_float(stats.get(field))
        if value is None:
            continue
        out[field] = round(float(value), 4)
    return out


def _serialize_settings_snapshot(settings_snapshot: object) -> str:
    if not isinstance(settings_snapshot, dict):
        return "{}"
    serialized = {
        str(key): value
        for key, value in sorted(settings_snapshot.items(), key=lambda item: str(item[0]))
    }
    return json.dumps(serialized, sort_keys=True, separators=(",", ":"))


def _projection_top_stat_deltas(
    projection_delta_detail: dict[str, Any] | None,
    *,
    limit: int = 3,
) -> list[dict[str, Any]]:
    if not isinstance(projection_delta_detail, dict):
        return []
    deltas = projection_delta_detail.get("deltas")
    deltas = deltas if isinstance(deltas, dict) else {}
    ranked = sorted(
        (
            (str(stat), float(delta))
            for stat, delta in deltas.items()
            if _coerce_float(delta) is not None
        ),
        key=lambda item: (-abs(item[1]), item[0]),
    )
    return [
        {"stat": stat, "delta": round(delta, 3)}
        for stat, delta in ranked[:limit]
    ]


def classify_projection_delta(
    *,
    projection_delta_detail: dict[str, Any] | None,
    has_previous_projection_snapshot: bool,
) -> str:
    if not has_previous_projection_snapshot or not isinstance(projection_delta_detail, dict):
        return "missing_previous_snapshot"
    composite_delta = _coerce_float(projection_delta_detail.get("composite_delta"))
    if composite_delta is None:
        return "missing_previous_snapshot"
    if composite_delta >= 10.0:
        return "material_riser"
    if composite_delta <= -10.0:
        return "material_faller"
    return "stable"


def classify_suspect_gap_refresh_label(
    *,
    classification: str | None,
    projection_delta_type: str | None,
) -> str | None:
    if str(classification or "").strip() != "suspect_model_gap":
        return None
    normalized = str(projection_delta_type or "").strip()
    if normalized == "stable":
        return "stable_model_gap"
    if normalized in {"material_riser", "material_faller"}:
        return "player_projection_shift"
    return "manual_review"


def _per_year_entries(explanation: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(explanation, dict):
        return []
    per_year = explanation.get("per_year")
    return [entry for entry in per_year if isinstance(entry, dict)] if isinstance(per_year, list) else []


def _positive_year_value(entry: dict[str, Any]) -> float:
    adjusted_value = _coerce_float(entry.get("adjusted_year_value_before_discount"))
    if adjusted_value is not None:
        return adjusted_value
    return float(_coerce_float(entry.get("year_value")) or 0.0)


def _adjusted_year_value(entry: dict[str, Any]) -> float | None:
    adjusted_value = _coerce_float(entry.get("adjusted_year_value_before_discount"))
    if adjusted_value is not None:
        return adjusted_value
    return _coerce_float(entry.get("year_value"))


def _top_discounted_years(per_year: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    contributions: list[tuple[int | str, float]] = []
    for idx, entry in enumerate(per_year):
        year = entry.get("year")
        discounted = float(_coerce_float(entry.get("discounted_contribution")) or 0.0)
        contributions.append((year if isinstance(year, (int, str)) else idx, discounted))
    return [
        {"year": year, "discounted_contribution": round(value, 4)}
        for year, value in sorted(contributions, key=lambda item: abs(item[1]), reverse=True)[:3]
    ]


def _tail_preview(per_year: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    for entry in per_year[:6]:
        if not isinstance(entry, dict):
            continue
        preview_entry: dict[str, Any] = {
            "year": entry.get("year"),
            "near_zero_playing_time": bool(entry.get("near_zero_playing_time")),
        }
        adjusted = _adjusted_year_value(entry)
        if adjusted is not None:
            preview_entry["adjusted_year_value_before_discount"] = round(adjusted, 4)
        discounted = _coerce_float(entry.get("discounted_contribution"))
        if discounted is not None:
            preview_entry["discounted_contribution"] = round(discounted, 4)
        projected_ab = _coerce_float(entry.get("projected_ab"))
        if projected_ab is not None:
            preview_entry["projected_ab"] = round(projected_ab, 4)
        projected_ip = _coerce_float(entry.get("projected_ip"))
        if projected_ip is not None:
            preview_entry["projected_ip"] = round(projected_ip, 4)
        preview.append(preview_entry)
    return preview


def explanation_review_metrics(explanation: dict[str, Any] | None) -> dict[str, Any]:
    per_year = _per_year_entries(explanation)
    explanation = explanation if isinstance(explanation, dict) else {}
    if not per_year:
        return {
            "start_year": None,
            "start_year_value": None,
            "discounted_three_year_total": 0.0,
            "discounted_full_total": 0.0,
            "positive_year_count": 0,
            "last_positive_year": None,
            "first_near_zero_year": None,
            "first_non_positive_adjusted_year": None,
            "positive_year_span": 0,
            "tail_value_after_year_3": 0.0,
            "tail_share_after_year_3": None,
            "tail_preview": [],
            "top_discounted_years": [],
            "start_year_best_slot": str(explanation.get("start_year_best_slot") or "").strip() or None,
            "start_year_category_sgp": _coerce_mapping(explanation.get("start_year_category_sgp")),
            "start_year_top_positive_categories": _coerce_category_entries(
                explanation.get("start_year_top_positive_categories")
            ),
            "start_year_top_negative_categories": _coerce_category_entries(
                explanation.get("start_year_top_negative_categories")
            ),
            "start_year_slot_baseline_reference": _coerce_mapping(
                explanation.get("start_year_slot_baseline_reference")
            ),
            "start_year_replacement_reference": _coerce_mapping(
                explanation.get("start_year_replacement_reference")
            ),
            "start_year_replacement_pool_depth": _coerce_int(
                explanation.get("start_year_replacement_pool_depth")
            ),
            "start_year_replacement_depth_mode": str(
                explanation.get("start_year_replacement_depth_mode") or ""
            ).strip()
            or None,
            "start_year_replacement_depth_blend_alpha": _coerce_float(
                explanation.get("start_year_replacement_depth_blend_alpha")
            ),
            "start_year_slot_count_per_team": _coerce_int(explanation.get("start_year_slot_count_per_team")),
            "start_year_slot_capacity_league": _coerce_int(explanation.get("start_year_slot_capacity_league")),
            "start_year_guard_summary": _coerce_mapping(explanation.get("start_year_guard_summary")),
            "start_year_bounds_summary": _coerce_mapping(explanation.get("start_year_bounds_summary")),
        }

    start_year_token = per_year[0].get("year")
    start_year = start_year_token if isinstance(start_year_token, int) else _coerce_int(start_year_token)
    start_year_value = _coerce_float(per_year[0].get("year_value"))

    discounted_three_year_total = 0.0
    discounted_full_total = 0.0
    tail_value_after_year_3 = 0.0
    positive_year_count = 0
    last_positive_year: int | None = None
    first_near_zero_year: int | None = None
    first_non_positive_adjusted_year: int | None = None
    for idx, entry in enumerate(per_year):
        discounted = float(_coerce_float(entry.get("discounted_contribution")) or 0.0)
        discounted_full_total += discounted
        if idx < 3:
            discounted_three_year_total += discounted
        else:
            tail_value_after_year_3 += discounted
        year = entry.get("year")
        year_int = year if isinstance(year, int) else _coerce_int(year)
        if bool(entry.get("near_zero_playing_time")) and first_near_zero_year is None:
            first_near_zero_year = year_int
        adjusted_value = _adjusted_year_value(entry)
        if adjusted_value is not None and adjusted_value <= 0.0 and first_non_positive_adjusted_year is None:
            first_non_positive_adjusted_year = year_int
        if _positive_year_value(entry) > 0.0:
            positive_year_count += 1
            if year_int is not None:
                last_positive_year = year_int

    positive_year_span = (
        max(int(last_positive_year) - int(start_year) + 1, 0)
        if start_year is not None and last_positive_year is not None and positive_year_count > 0
        else 0
    )
    tail_share_after_year_3 = (
        round(tail_value_after_year_3 / discounted_full_total, 4)
        if discounted_full_total > 0.0
        else None
    )

    return {
        "start_year": start_year,
        "start_year_value": round(start_year_value, 4) if start_year_value is not None else None,
        "discounted_three_year_total": round(discounted_three_year_total, 4),
        "discounted_full_total": round(discounted_full_total, 4),
        "positive_year_count": positive_year_count,
        "last_positive_year": last_positive_year,
        "first_near_zero_year": first_near_zero_year,
        "first_non_positive_adjusted_year": first_non_positive_adjusted_year,
        "positive_year_span": positive_year_span,
        "tail_value_after_year_3": round(tail_value_after_year_3, 4),
        "tail_share_after_year_3": tail_share_after_year_3,
        "tail_preview": _tail_preview(per_year),
        "top_discounted_years": _top_discounted_years(per_year),
        "start_year_best_slot": str(explanation.get("start_year_best_slot") or "").strip() or None,
        "start_year_category_sgp": _coerce_mapping(explanation.get("start_year_category_sgp")),
        "start_year_top_positive_categories": _coerce_category_entries(
            explanation.get("start_year_top_positive_categories")
        ),
        "start_year_top_negative_categories": _coerce_category_entries(
            explanation.get("start_year_top_negative_categories")
        ),
        "start_year_slot_baseline_reference": _coerce_mapping(explanation.get("start_year_slot_baseline_reference")),
        "start_year_replacement_reference": _coerce_mapping(explanation.get("start_year_replacement_reference")),
        "start_year_replacement_pool_depth": _coerce_int(explanation.get("start_year_replacement_pool_depth")),
        "start_year_replacement_depth_mode": str(explanation.get("start_year_replacement_depth_mode") or "").strip()
        or None,
        "start_year_replacement_depth_blend_alpha": _coerce_float(
            explanation.get("start_year_replacement_depth_blend_alpha")
        ),
        "start_year_slot_count_per_team": _coerce_int(explanation.get("start_year_slot_count_per_team")),
        "start_year_slot_capacity_league": _coerce_int(explanation.get("start_year_slot_capacity_league")),
        "start_year_guard_summary": _coerce_mapping(explanation.get("start_year_guard_summary")),
        "start_year_bounds_summary": _coerce_mapping(explanation.get("start_year_bounds_summary")),
    }


def classify_raw_value_gap_cause(explanation: dict[str, Any] | None) -> str:
    if not isinstance(explanation, dict):
        return "mixed"

    bounds_summary = _coerce_mapping(explanation.get("start_year_bounds_summary"))
    if bool(bounds_summary.get("applied")):
        return "pitching_bounds"

    guard_summary = _coerce_mapping(explanation.get("start_year_guard_summary"))
    positive_credit_scale = _coerce_float(guard_summary.get("positive_credit_scale"))
    if positive_credit_scale is not None and positive_credit_scale < 0.999999:
        return "guard_attenuation"

    current_year_volume = _coerce_mapping(explanation.get("current_year_volume"))
    profile = str(explanation.get("profile") or "").strip().lower() or "unknown"
    if profile in {"hitter", "catcher", "two_way"} and float(current_year_volume.get("ab") or 0.0) <= 450.0:
        return "projected_volume"
    if profile in {"pitcher", "two_way"} and float(current_year_volume.get("ip") or 0.0) <= 140.0:
        return "projected_volume"

    if explanation.get("start_year_best_slot"):
        return "slot_replacement_context"
    return "mixed"


def weighted_mean_absolute_rank_error(entries: Iterable[dict[str, Any]]) -> float:
    weighted_total = 0.0
    total_weight = 0.0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        benchmark_rank = _coerce_int(entry.get("benchmark_rank"))
        abs_rank_delta = _coerce_float(entry.get("abs_rank_delta"))
        if benchmark_rank is None or abs_rank_delta is None:
            continue
        if benchmark_rank <= 15:
            weight = 3.0
        elif benchmark_rank <= 50:
            weight = 2.0
        else:
            weight = 1.0
        weighted_total += weight * abs_rank_delta
        total_weight += weight
    return round(weighted_total / total_weight, 4) if total_weight > 0.0 else 0.0


def summarize_divergence_drivers(explanation: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(explanation, dict):
        return {
            "driver_reasons": [],
            "late_discounted_share": None,
            "negative_adjusted_years": 0,
            "top_discounted_years": [],
        }

    per_year = _per_year_entries(explanation)

    contributions: list[tuple[int | str, float]] = []
    total_abs_discounted = 0.0
    late_abs_discounted = 0.0
    negative_adjusted_years = 0
    prospect_discount_applied = False
    age_discount_applied = False
    stash_relief_applied = False
    near_zero_playing_time = False
    start_year = None

    for idx, entry in enumerate(per_year):
        if not isinstance(entry, dict):
            continue
        year = entry.get("year")
        if idx == 0:
            start_year = year if isinstance(year, int) else None
        discounted = float(entry.get("discounted_contribution") or 0.0)
        total_abs_discounted += abs(discounted)
        if isinstance(year, int) and start_year is not None and year >= start_year + 4:
            late_abs_discounted += abs(discounted)
        contributions.append((year if isinstance(year, (int, str)) else idx, discounted))
        adjusted = _coerce_float(entry.get("adjusted_year_value_before_discount"))
        if adjusted is not None and adjusted < 0.0:
            negative_adjusted_years += 1
        if float(entry.get("prospect_risk_multiplier") or 1.0) < 0.999999:
            prospect_discount_applied = True
        if float(entry.get("age_risk_multiplier") or 1.0) < 0.999999:
            age_discount_applied = True
        if bool(entry.get("stash_adjustment_applied")):
            stash_relief_applied = True
        if bool(entry.get("near_zero_playing_time")):
            near_zero_playing_time = True

    late_discounted_share = (
        round(late_abs_discounted / total_abs_discounted, 4)
        if total_abs_discounted > 0.0
        else None
    )

    current_year_volume = explanation.get("current_year_volume")
    current_year_volume = current_year_volume if isinstance(current_year_volume, dict) else {}
    profile = str(explanation.get("profile") or "").strip().lower() or "unknown"
    reasons: list[str] = []
    if prospect_discount_applied:
        reasons.append("prospect_risk_discount")
    if age_discount_applied:
        reasons.append("age_risk_discount")
    if stash_relief_applied:
        reasons.append("stash_relief")
    if late_discounted_share is not None and late_discounted_share >= 0.45:
        reasons.append("long_horizon_weight")
    if profile in {"hitter", "catcher", "two_way"} and float(current_year_volume.get("ab") or 0.0) <= 350.0:
        reasons.append("light_start_year_ab")
    if profile in {"pitcher", "two_way"} and float(current_year_volume.get("ip") or 0.0) <= 120.0:
        reasons.append("light_start_year_ip")

    return {
        "driver_reasons": reasons,
        "late_discounted_share": late_discounted_share,
        "negative_adjusted_years": negative_adjusted_years,
        "near_zero_playing_time": near_zero_playing_time,
        "top_discounted_years": _top_discounted_years(per_year),
    }


def classify_divergence(
    *,
    model_rank: int | None,
    benchmark_rank: int | None,
    explanation: dict[str, Any] | None,
    delta_threshold: int,
) -> str:
    if model_rank is None or benchmark_rank is None:
        return "needs_manual_review"
    if not isinstance(explanation, dict):
        return "needs_manual_review"
    abs_delta = abs(int(model_rank) - int(benchmark_rank))
    if abs_delta < int(delta_threshold):
        return "explained"
    driver_summary = summarize_divergence_drivers(explanation)
    if driver_summary["driver_reasons"]:
        return "explained"
    return "suspect_model_gap"


def triage_bucket(
    *,
    abs_rank_delta: int | None,
    start_year_rank: int | None,
    delta_threshold: int,
) -> str | None:
    if abs_rank_delta is None or abs_rank_delta < int(delta_threshold) or start_year_rank is None:
        return None
    # Entries right on the split line are kept separate so they do not get
    # over-classified as pure one-year or pure aggregation issues.
    if 26 <= int(start_year_rank) <= 30:
        return "mixed_gap"
    if int(start_year_rank) <= 25:
        return "aggregation_gap"
    return "raw_value_gap"


def classify_aggregation_tail_gap(
    *,
    triage_bucket: str | None,
    start_year_rank: int | None,
    positive_year_count: int | None,
    tail_share_after_year_3: float | None,
    comp_positive_year_counts: Sequence[int | float | None],
) -> str | None:
    if str(triage_bucket or "").strip() != "aggregation_gap":
        return None
    if (
        start_year_rank is None
        or positive_year_count is None
        or int(start_year_rank) > 25
        or int(positive_year_count) > 5
        or tail_share_after_year_3 is None
        or float(tail_share_after_year_3) > 0.10
    ):
        return "mixed"
    median_comp_positive_year_count = _median_or_none(comp_positive_year_counts, digits=1)
    if (
        median_comp_positive_year_count is not None
        and median_comp_positive_year_count >= (float(positive_year_count) + 2.0)
    ):
        return "comp_horizon_gap"
    return "short_positive_tail"


def aggregation_tail_recommendation(
    entries: Iterable[dict[str, Any]],
    *,
    target_players: Sequence[str] | None = None,
) -> str:
    target_order = [
        str(player).strip()
        for player in (target_players or DEFAULT_AGGREGATION_MEMO_TARGET_PLAYERS)
        if str(player).strip()
    ]
    entry_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    if (
        target_order
        and all(
            str((entry_by_player.get(player) or {}).get("aggregation_tail_classification") or "").strip()
            == "comp_horizon_gap"
            for player in target_order
        )
    ):
        return "recommend_tail_pilot"
    return "recommend_no_methodology_change_yet"


def projection_refresh_recommendation(
    entries: Iterable[dict[str, Any]],
    *,
    target_players: Sequence[str] | None = None,
    recommendation_override: str | None = None,
) -> str:
    override = str(recommendation_override or "").strip()
    if override:
        return override

    target_order = [
        str(player).strip()
        for player in (target_players or DEFAULT_REFRESH_MEMO_TARGET_PLAYERS)
        if str(player).strip()
    ]
    entry_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    stable_model_gap_count = sum(
        1
        for player in target_order
        if str((entry_by_player.get(player) or {}).get("suspect_gap_refresh_label") or "").strip()
        == "stable_model_gap"
    )
    if stable_model_gap_count >= 7:
        return "recommend_resume_model_gap_work"
    return "recommend_refresh_specific_reaudit"


def classify_attribution_layer(
    *,
    benchmark_rank: int | None,
    raw_start_year_rank: int | None,
    start_year_rank: int | None,
    model_rank: int | None,
) -> str:
    if benchmark_rank is None:
        return "mixed_gap"
    if raw_start_year_rank is not None and int(raw_start_year_rank) > (int(benchmark_rank) + 10):
        return "projection_shape_gap"
    if (
        raw_start_year_rank is not None
        and int(raw_start_year_rank) <= (int(benchmark_rank) + 10)
        and start_year_rank is not None
        and int(start_year_rank) > (int(benchmark_rank) + 10)
    ):
        return "roto_conversion_gap"
    if (
        start_year_rank is not None
        and int(start_year_rank) <= (int(benchmark_rank) + 10)
        and model_rank is not None
        and int(model_rank) > (int(benchmark_rank) + 15)
    ):
        return "dynasty_aggregation_gap"
    return "mixed_gap"


def attribution_recommendation(
    entries: Iterable[dict[str, Any]],
    *,
    target_players: Sequence[str] | None = None,
) -> str:
    target_order = [
        str(player).strip()
        for player in (target_players or DEFAULT_ATTRIBUTION_MEMO_TARGET_PLAYERS)
        if str(player).strip()
    ]
    entry_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    counts = Counter(
        str((entry_by_player.get(player) or {}).get("attribution_class") or "").strip()
        for player in target_order
        if str((entry_by_player.get(player) or {}).get("attribution_class") or "").strip() in ATTRIBUTION_CLASSES
    )
    if int(counts.get("projection_shape_gap", 0)) >= 4:
        return "recommend_projection_input_reaudit"
    if int(counts.get("roto_conversion_gap", 0)) >= 4:
        return "recommend_roto_conversion_followup"
    if int(counts.get("dynasty_aggregation_gap", 0)) >= 4:
        return "recommend_aggregation_followup"
    return "recommend_no_change_yet"


def _median_or_none(values: Iterable[int | float | None], *, digits: int = 1) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return round(float(median(numeric)), digits)


def _summarize_attribution_cohort(
    entries: Iterable[dict[str, Any]],
    *,
    players: Sequence[str],
) -> dict[str, Any]:
    entry_by_player = {
        str(entry.get("player") or "").strip(): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "").strip()
    }
    cohort_entries = [entry_by_player[player] for player in players if player in entry_by_player]
    return {
        "players": [str(entry.get("player") or "").strip() for entry in cohort_entries],
        "player_count": len(cohort_entries),
        "median_raw_start_year_rank": _median_or_none(
            _coerce_int(entry.get("raw_start_year_rank")) for entry in cohort_entries
        ),
        "median_start_year_rank": _median_or_none(
            _coerce_int(entry.get("start_year_rank")) for entry in cohort_entries
        ),
        "median_model_rank": _median_or_none(_coerce_int(entry.get("model_rank")) for entry in cohort_entries),
        "median_raw_to_replacement_penalty": _median_or_none(
            _coerce_int(entry.get("raw_to_replacement_rank_delta")) for entry in cohort_entries
        ),
        "median_replacement_to_dynasty_penalty": _median_or_none(
            _coerce_int(entry.get("replacement_to_dynasty_rank_delta")) for entry in cohort_entries
        ),
    }


def _slot_projection_movers(
    ranked_model_entries: Sequence[dict[str, Any]],
    *,
    projection_delta_details: dict[str, dict[str, Any]],
    slots: set[str],
    has_previous_projection_snapshot: bool,
    limit: int = 5,
) -> list[dict[str, Any]]:
    movers: list[dict[str, Any]] = []
    for entry in ranked_model_entries:
        if not isinstance(entry, dict):
            continue
        best_slot = str(entry.get("start_year_best_slot") or "").strip()
        if best_slot not in slots:
            continue
        entity_key = str(entry.get("entity_key") or "").strip()
        player_key = str(entry.get("player_key") or "").strip()
        projection_delta_detail = projection_delta_details.get(entity_key) or projection_delta_details.get(player_key)
        if not isinstance(projection_delta_detail, dict):
            continue
        movers.append(
            {
                "player": entry.get("player"),
                "model_rank": entry.get("model_rank"),
                "start_year_rank": entry.get("start_year_rank"),
                "start_year_best_slot": best_slot,
                "projection_composite_delta": round(
                    float(_coerce_float(projection_delta_detail.get("composite_delta")) or 0.0),
                    3,
                ),
                "projection_delta_type": classify_projection_delta(
                    projection_delta_detail=projection_delta_detail,
                    has_previous_projection_snapshot=has_previous_projection_snapshot,
                ),
                "projection_top_stat_deltas": _projection_top_stat_deltas(projection_delta_detail),
            }
        )
    return sorted(
        movers,
        key=lambda entry: (
            -abs(float(entry.get("projection_composite_delta") or 0.0)),
            int(entry.get("model_rank") or 10**9),
            str(entry.get("player") or ""),
        ),
    )[:limit]


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
    projection_delta_detail_map = (
        projection_delta_details if isinstance(projection_delta_details, dict) else {}
    )
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
        key=lambda row: (
            -float(row.get("YearValue") or 0.0),
            str(row.get("Player") or ""),
        ),
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
        model_index.setdefault(
            normalize_player_name(player),
            model_entry,
        )
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
        model_entry = model_index.get(player_key)
        explanation = model_entry.get("explanation") if isinstance(model_entry, dict) else None
        benchmark_rank = int(benchmark.get("benchmark_rank")) if benchmark.get("benchmark_rank") is not None else None
        model_rank = int(model_entry["model_rank"]) if isinstance(model_entry, dict) else None
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
                "start_year_best_slot": (
                    model_entry.get("start_year_best_slot") if isinstance(model_entry, dict) else None
                ),
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
        "previous_projection_source": (
            str(previous_projection_source or "").strip() or None
        ),
        "weighted_mean_absolute_rank_error": weighted_mean_absolute_rank_error(entries),
        "classification_counts": classification_counts,
        "triage_counts": {bucket: int(triage_counts.get(bucket, 0)) for bucket in TRIAGE_BUCKETS},
        "attribution_counts": {
            label: int(attribution_counts.get(label, 0))
            for label in ATTRIBUTION_CLASSES
        },
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
        if isinstance(summary, dict)
        and (
            bool(summary.get("passes_of_guard"))
            or bool(summary.get("passes_p_guard"))
        )
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
    control_of_alpha = float(_coerce_float(control_override_map.get("OF")) or _coerce_float(control_settings.get("replacement_depth_blend_alpha")) or 0.33)
    control_p_alpha = float(_coerce_float(control_override_map.get("P")) or _coerce_float(control_settings.get("replacement_depth_blend_alpha")) or 0.33)

    candidate_summaries: list[dict[str, Any]] = []
    for candidate_id, candidate_review in candidate_reviews.items():
        if not isinstance(candidate_review, dict):
            continue
        settings_snapshot = _coerce_mapping(candidate_review.get("settings_snapshot"))
        override_map = _coerce_mapping(settings_snapshot.get("replacement_depth_blend_alpha_by_slot"))
        of_alpha = float(_coerce_float(override_map.get("OF")) or _coerce_float(settings_snapshot.get("replacement_depth_blend_alpha")) or control_of_alpha)
        p_alpha = float(_coerce_float(override_map.get("P")) or _coerce_float(settings_snapshot.get("replacement_depth_blend_alpha")) or control_p_alpha)
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
    return [
        {"category": category, "value": round(value, 4)}
        for category, value in ranked[:limit]
    ]


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
    target_order = [str(player).strip() for player in (target_players or DEFAULT_MEMO_TARGET_PLAYERS) if str(player).strip()]
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
                (
                    f"- Refresh label: `{entry.get('suspect_gap_refresh_label') or 'n/a'}`."
                ),
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
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            f"- `{recommendation}`",
            "",
        ]
    )
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
                (
                    f"- Refresh label: `{entry.get('suspect_gap_refresh_label') or 'n/a'}`."
                ),
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

    lines.extend(
        [
            "## Recommendation",
            "",
            f"- `{recommendation}`",
            "",
        ]
    )
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
        lines.append("- Next pass should target workbook and projection-shape validation before any valuation-methodology pilot.")
    elif recommendation == "recommend_roto_conversion_followup":
        lines.append("- Next pass should target one-year roto conversion, slot baselines, and category/replacement logic.")
    elif recommendation == "recommend_aggregation_followup":
        lines.append("- Next pass should target dynasty aggregation for established MLB hitters rather than one-year conversion.")
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
    lines.extend(
        [
            "## Recommendation",
            "",
            f"- `{recommendation}`",
            "",
        ]
    )
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
