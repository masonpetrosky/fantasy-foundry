"""Shared helpers for reviewing dynasty ranking divergences."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence, cast

_NORMALIZE_PLAYER_RE = re.compile(r"[^a-z0-9]+")
DEFAULT_DYNASTY_BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "default_roto_consensus_2026-03-21.json"
)
IMPORTED_SHALLOW_DYNASTY_BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "imported_shallow_roto_chatgpt_2026-03-22.json"
)
IMPORTED_DEEP_DYNASTY_BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "imported_deep_roto_chatgpt_2026-03-22.json"
)
IMPORTED_KEEPER_POINTS_BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "benchmarks" / "imported_keeper_weekly_points_chatgpt_2026-03-22.json"
)
BENCHMARK_PATHS_BY_PROFILE_ID: dict[str, Path] = {
    "standard_roto": DEFAULT_DYNASTY_BENCHMARK_PATH,
    "shallow_roto_imported": IMPORTED_SHALLOW_DYNASTY_BENCHMARK_PATH,
    "deep_roto_imported": IMPORTED_DEEP_DYNASTY_BENCHMARK_PATH,
    "keeper_points_imported": IMPORTED_KEEPER_POINTS_BENCHMARK_PATH,
}
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
    "shallow_roto_imported",
    "deep_roto_imported",
    "keeper_points_imported",
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


def load_dynasty_benchmark(
    path: str | Path | None = None,
    *,
    profile_id: str = "standard_roto",
) -> list[dict[str, Any]]:
    default_path = BENCHMARK_PATHS_BY_PROFILE_ID.get(
        str(profile_id or "").strip() or "standard_roto",
        DEFAULT_DYNASTY_BENCHMARK_PATH,
    )
    benchmark_path = Path(path or default_path).expanduser().resolve()
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
            rank_value = int(cast(Any, benchmark_rank))
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
        return float(cast(Any, value))
    except (TypeError, ValueError):
        return None


def _coerce_int(value: object) -> int | None:
    try:
        return int(cast(Any, value))
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
    return [{"stat": stat, "delta": round(delta, 3)} for stat, delta in ranked[:limit]]


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
