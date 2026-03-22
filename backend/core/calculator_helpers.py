"""Shared calculator helper functions for guards, categories, stats, and explanations."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping

import pandas as pd

DEFAULT_DYNASTY_METHODOLOGY_VERSION = "2026-03-22"
HIDDEN_DYNASTY_BENCH_STASH_MIN_BENCH_SLOTS = 10
HIDDEN_DYNASTY_IR_STASH_MIN_IR_SLOTS = 4
HIDDEN_DYNASTY_BENCH_NEGATIVE_PENALTY = 0.55
HIDDEN_DYNASTY_IR_NEGATIVE_PENALTY = 0.20


def default_dynasty_methodology_fingerprint(
    *,
    default_params: Mapping[str, Any],
    methodology_version: str = DEFAULT_DYNASTY_METHODOLOGY_VERSION,
) -> str:
    payload = {
        "methodology_version": str(methodology_version).strip(),
        "default_params": {
            str(key): default_params[key]
            for key in sorted(default_params.keys(), key=str)
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:12]


def coerce_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _coerce_non_negative_int(value: object, *, default: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return int(default)
    return max(parsed, 0)


def _coerce_float(value: object, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def resolve_hidden_dynasty_modeling_settings(
    *,
    bench_slots: object,
    ir_slots: object,
    source: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    bench = _coerce_non_negative_int(bench_slots)
    ir = _coerce_non_negative_int(ir_slots)
    resolved: dict[str, Any] = {
        "enable_prospect_risk_adjustment": True,
        "enable_bench_stash_relief": bench >= HIDDEN_DYNASTY_BENCH_STASH_MIN_BENCH_SLOTS,
        "bench_negative_penalty": HIDDEN_DYNASTY_BENCH_NEGATIVE_PENALTY,
        "enable_ir_stash_relief": ir >= HIDDEN_DYNASTY_IR_STASH_MIN_IR_SLOTS,
        "ir_negative_penalty": HIDDEN_DYNASTY_IR_NEGATIVE_PENALTY,
    }
    if not isinstance(source, Mapping):
        return resolved

    if "enable_prospect_risk_adjustment" in source:
        resolved["enable_prospect_risk_adjustment"] = coerce_bool(
            source.get("enable_prospect_risk_adjustment"),
            default=bool(resolved["enable_prospect_risk_adjustment"]),
        )
    if "enable_bench_stash_relief" in source:
        resolved["enable_bench_stash_relief"] = coerce_bool(
            source.get("enable_bench_stash_relief"),
            default=bool(resolved["enable_bench_stash_relief"]),
        )
    if "bench_negative_penalty" in source:
        resolved["bench_negative_penalty"] = _coerce_float(
            source.get("bench_negative_penalty"),
            default=HIDDEN_DYNASTY_BENCH_NEGATIVE_PENALTY,
        )
    if "enable_ir_stash_relief" in source:
        resolved["enable_ir_stash_relief"] = coerce_bool(
            source.get("enable_ir_stash_relief"),
            default=bool(resolved["enable_ir_stash_relief"]),
        )
    if "ir_negative_penalty" in source:
        resolved["ir_negative_penalty"] = _coerce_float(
            source.get("ir_negative_penalty"),
            default=HIDDEN_DYNASTY_IR_NEGATIVE_PENALTY,
        )
    return resolved


def with_resolved_hidden_dynasty_modeling_settings(settings: Mapping[str, Any] | None) -> dict[str, Any]:
    normalized = dict(settings or {})
    normalized.update(
        resolve_hidden_dynasty_modeling_settings(
            bench_slots=normalized.get("bench"),
            ir_slots=normalized.get("ir"),
            source=normalized,
        )
    )
    return normalized


def roto_category_settings_from_dict(
    source: dict[str, Any] | None,
    *,
    coerce_bool_fn: Callable[[object], bool],
    defaults: dict[str, bool],
) -> dict[str, bool]:
    settings = source if isinstance(source, dict) else {}
    return {
        field_key: coerce_bool_fn(settings.get(field_key), default=default_value)  # type: ignore[call-arg]
        for field_key, default_value in defaults.items()
    }


def selected_roto_categories(
    settings: dict[str, Any],
    *,
    roto_category_settings_from_dict_fn: Callable[[dict[str, Any] | None], dict[str, bool]],
    hitter_fields: tuple[tuple[str, str, bool], ...],
    pitcher_fields: tuple[tuple[str, str, bool], ...],
) -> tuple[list[str], list[str]]:
    resolved_settings = roto_category_settings_from_dict_fn(settings)
    hitter = [
        stat_col
        for field_key, stat_col, _default_value in hitter_fields
        if resolved_settings.get(field_key, False)
    ]
    pitcher = [
        stat_col
        for field_key, stat_col, _default_value in pitcher_fields
        if resolved_settings.get(field_key, False)
    ]
    return hitter, pitcher


def start_year_roto_stats_by_entity(
    *,
    start_year: int,
    bat_data: list[dict],
    pit_data: list[dict],
    coerce_record_year_fn: Callable[[object], int | None],
    projection_identity_key_fn: Callable[[dict | pd.Series], str],
    coerce_numeric_fn: Callable[[object], float | None],
    roto_hitter_fields: tuple[tuple[str, str, bool], ...],
    roto_pitcher_fields: tuple[tuple[str, str, bool], ...],
) -> dict[str, dict[str, float]]:
    bat_rows = bat_data
    pit_rows = pit_data

    stats_by_entity: dict[str, dict[str, float]] = {}

    def merge_rows(rows: list[dict], stat_cols: tuple[str, ...] | list[str]) -> None:
        for row in rows:
            year = coerce_record_year_fn(row.get("Year"))
            if year != int(start_year):
                continue
            entity_key = projection_identity_key_fn(row)
            if not entity_key:
                continue
            entry = stats_by_entity.setdefault(entity_key, {})
            for stat_col in stat_cols:
                stat_value = coerce_numeric_fn(row.get(stat_col))
                if stat_value is None:
                    continue
                entry[stat_col] = float(stat_value)

    merge_rows(bat_rows, tuple(stat_col for _field_key, stat_col, _default in roto_hitter_fields))
    merge_rows(pit_rows, tuple(stat_col for _field_key, stat_col, _default in roto_pitcher_fields))
    return stats_by_entity


def is_user_fixable_calculation_error(message: str) -> bool:
    normalized = message.lower()
    return (
        "not enough players" in normalized
        or "no valuation years available" in normalized
        or "cannot fill slot" in normalized
        or "to fill required slots" in normalized
    )


def numeric_or_zero(value: object, *, as_float_fn: Callable[[object], float | None]) -> float:
    parsed = as_float_fn(value)
    return float(parsed) if parsed is not None else 0.0


def _round_numeric_mapping(
    value: object,
    *,
    numeric_or_zero_fn: Callable[[object], float],
    decimals: int = 4,
) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, float] = {}
    for key, raw in value.items():
        out[str(key)] = round(numeric_or_zero_fn(raw), decimals)
    return out


def _top_category_entries(category_sgp: dict[str, float], *, positive: bool, limit: int = 3) -> list[dict[str, float | str]]:
    filtered = [
        (str(category), float(value))
        for category, value in category_sgp.items()
        if (float(value) > 0.0 if positive else float(value) < 0.0)
    ]
    sorted_items = sorted(filtered, key=lambda item: item[1], reverse=positive)[:limit]
    return [{"category": category, "value": round(value, 4)} for category, value in sorted_items]


def build_calculation_explanations(
    out: pd.DataFrame,
    *,
    settings: dict[str, Any],
    player_key_col: str,
    player_entity_key_col: str,
    normalize_player_key_fn: Callable[[object], str],
    numeric_or_zero_fn: Callable[[object], float],
    value_col_sort_key_fn: Callable[[str], tuple[int, int | str]],
) -> dict[str, dict]:
    scoring_mode = str(settings.get("scoring_mode") or "roto").strip().lower() or "roto"
    discount = numeric_or_zero_fn(settings.get("discount")) or 1.0
    year_cols = sorted(
        [col for col in out.columns if isinstance(col, str) and col.startswith("Value_")],
        key=value_col_sort_key_fn,
    )
    explanations: dict[str, dict] = {}

    for _, row in out.iterrows():
        row_data = row.to_dict()
        player = str(row_data.get("Player") or "").strip()
        player_key = str(row_data.get(player_key_col) or "").strip() or normalize_player_key_fn(player)
        entity_key = str(row_data.get(player_entity_key_col) or "").strip() or player_key
        explain_key = entity_key or player_key
        points_by_year = row_data.get("_ExplainPointsByYear")
        points_by_year = points_by_year if isinstance(points_by_year, dict) else {}
        roto_by_year = row_data.get("_ExplainRotoByYear")
        roto_by_year = roto_by_year if isinstance(roto_by_year, dict) else {}

        def _rounded_detail(detail: dict[str, Any], key: str, decimals: int = 4) -> float | None:
            if key not in detail:
                return None
            raw_value = detail.get(key)
            if raw_value is None:
                return None
            return round(numeric_or_zero_fn(raw_value), decimals)

        per_year: list[dict] = []
        start_year_fields: dict[str, Any] = {}
        for idx, year_col in enumerate(year_cols):
            suffix = year_col.split("_", 1)[1] if "_" in year_col else year_col
            year_token: int | str = int(suffix) if str(suffix).isdigit() else suffix
            year_value = numeric_or_zero_fn(row_data.get(year_col))
            discount_factor = float(discount) ** idx
            discounted = year_value * discount_factor
            roto_detail = roto_by_year.get(str(year_token)) if scoring_mode == "roto" else None
            if scoring_mode == "points":
                points_detail = points_by_year.get(str(year_token))
                if isinstance(points_detail, dict):
                    detail_discount_factor = points_detail.get("discount_factor")
                    if detail_discount_factor is not None:
                        discount_factor = numeric_or_zero_fn(detail_discount_factor)
                    detail_discounted = points_detail.get("discounted_contribution")
                    if detail_discounted is not None:
                        discounted = numeric_or_zero_fn(detail_discounted)
            elif isinstance(roto_detail, dict):
                detail_discount_factor = roto_detail.get("discount_factor")
                if detail_discount_factor is not None:
                    discount_factor = numeric_or_zero_fn(detail_discount_factor)
                detail_discounted = roto_detail.get("discounted_contribution")
                if detail_discounted is not None:
                    discounted = numeric_or_zero_fn(detail_discounted)

            year_entry: dict[str, Any] = {
                "year": year_token,
                "year_value": round(year_value, 4),
                "discount_factor": round(discount_factor, 6),
                "discounted_contribution": round(discounted, 4),
            }
            if scoring_mode == "points":
                points_detail = points_by_year.get(str(year_token))
                if isinstance(points_detail, dict):
                    year_entry["points"] = points_detail
            elif isinstance(roto_detail, dict):
                adjusted_year_value = _rounded_detail(roto_detail, "adjusted_year_value")
                if adjusted_year_value is not None:
                    year_entry["adjusted_year_value_before_discount"] = adjusted_year_value
                raw_year_value = _rounded_detail(roto_detail, "raw_year_value")
                if raw_year_value is not None:
                    year_entry["raw_year_value"] = raw_year_value
                after_risk_value = _rounded_detail(roto_detail, "after_risk_value")
                if after_risk_value is not None:
                    year_entry["after_risk_value"] = after_risk_value
                age_risk_multiplier = _rounded_detail(roto_detail, "age_risk_multiplier", 6)
                if age_risk_multiplier is not None:
                    year_entry["age_risk_multiplier"] = age_risk_multiplier
                prospect_risk_multiplier = _rounded_detail(roto_detail, "prospect_risk_multiplier", 6)
                if prospect_risk_multiplier is not None:
                    year_entry["prospect_risk_multiplier"] = prospect_risk_multiplier
                keep_drop_value = _rounded_detail(roto_detail, "keep_drop_value")
                if keep_drop_value is not None:
                    year_entry["keep_drop_value"] = keep_drop_value
                keep_drop_hold_value = _rounded_detail(roto_detail, "keep_drop_hold_value")
                if keep_drop_hold_value is not None:
                    year_entry["keep_drop_hold_value"] = keep_drop_hold_value
                if "keep_drop_keep" in roto_detail:
                    year_entry["keep_drop_keep"] = bool(roto_detail.get("keep_drop_keep"))
                for bool_key in (
                    "minor_eligible",
                    "near_zero_playing_time",
                    "can_minor_stash",
                    "can_ir_stash",
                    "can_bench_stash",
                    "stash_adjustment_applied",
                ):
                    if bool_key in roto_detail:
                        year_entry[bool_key] = bool(roto_detail.get(bool_key))
                projected_ab = _rounded_detail(roto_detail, "projected_ab")
                if projected_ab is not None:
                    year_entry["projected_ab"] = projected_ab
                projected_ip = _rounded_detail(roto_detail, "projected_ip")
                if projected_ip is not None:
                    year_entry["projected_ip"] = projected_ip
                ir_negative_penalty = _rounded_detail(roto_detail, "ir_negative_penalty", 6)
                if ir_negative_penalty is not None:
                    year_entry["ir_negative_penalty"] = ir_negative_penalty
                bench_negative_penalty = _rounded_detail(roto_detail, "bench_negative_penalty", 6)
                if bench_negative_penalty is not None:
                    year_entry["bench_negative_penalty"] = bench_negative_penalty
                stash_mode = str(roto_detail.get("stash_mode") or "").strip()
                if stash_mode:
                    year_entry["stash_mode"] = stash_mode
                best_slot = str(roto_detail.get("best_slot") or "").strip()
                if best_slot:
                    year_entry["best_slot"] = best_slot
                replacement_value_diagnostics = roto_detail.get("replacement_value_diagnostics")
                if isinstance(replacement_value_diagnostics, dict):
                    category_sgp = _round_numeric_mapping(
                        replacement_value_diagnostics.get("category_sgp"),
                        numeric_or_zero_fn=numeric_or_zero_fn,
                    )
                    if category_sgp:
                        year_entry["category_sgp"] = category_sgp
                    slot_baseline_reference = replacement_value_diagnostics.get("slot_baseline_reference")
                    if isinstance(slot_baseline_reference, dict):
                        year_entry["slot_baseline_reference"] = {
                            **{
                                key: value
                                for key, value in slot_baseline_reference.items()
                                if key not in {"volume", "components"}
                            },
                            "volume": _round_numeric_mapping(
                                slot_baseline_reference.get("volume"),
                                numeric_or_zero_fn=numeric_or_zero_fn,
                            ),
                            "components": _round_numeric_mapping(
                                slot_baseline_reference.get("components"),
                                numeric_or_zero_fn=numeric_or_zero_fn,
                            ),
                        }
                    replacement_reference = replacement_value_diagnostics.get("replacement_reference")
                    if isinstance(replacement_reference, dict):
                        year_entry["replacement_reference"] = {
                            **{
                                key: value
                                for key, value in replacement_reference.items()
                                if key not in {"volume", "components"}
                            },
                            "volume": _round_numeric_mapping(
                                replacement_reference.get("volume"),
                                numeric_or_zero_fn=numeric_or_zero_fn,
                            ),
                            "components": _round_numeric_mapping(
                                replacement_reference.get("components"),
                                numeric_or_zero_fn=numeric_or_zero_fn,
                            ),
                        }
                        pool_depth = replacement_reference.get("replacement_pool_depth")
                        if pool_depth is not None:
                            try:
                                year_entry["replacement_pool_depth"] = int(pool_depth)
                            except (TypeError, ValueError):
                                pass
                        depth_mode = str(replacement_reference.get("replacement_depth_mode") or "").strip()
                        if depth_mode:
                            year_entry["replacement_depth_mode"] = depth_mode
                        depth_blend_alpha = replacement_reference.get("replacement_depth_blend_alpha")
                        if depth_blend_alpha is not None:
                            rounded_blend_alpha = _rounded_detail(
                                {"value": depth_blend_alpha},
                                "value",
                                4,
                            )
                            if rounded_blend_alpha is not None:
                                year_entry["replacement_depth_blend_alpha"] = rounded_blend_alpha
                        slot_count_per_team = replacement_reference.get("slot_count_per_team")
                        if slot_count_per_team is not None:
                            try:
                                year_entry["slot_count_per_team"] = int(slot_count_per_team)
                            except (TypeError, ValueError):
                                pass
                        slot_capacity_league = replacement_reference.get("slot_capacity_league")
                        if slot_capacity_league is not None:
                            try:
                                year_entry["slot_capacity_league"] = int(slot_capacity_league)
                            except (TypeError, ValueError):
                                pass
                    guard_summary = replacement_value_diagnostics.get("guard")
                    if isinstance(guard_summary, dict):
                        year_entry["guard"] = {
                            "mode": str(guard_summary.get("mode") or "").strip() or "none",
                            "player_volume": _rounded_detail({"value": guard_summary.get("player_volume")}, "value"),
                            "slot_volume_reference": _rounded_detail(
                                {"value": guard_summary.get("slot_volume_reference")},
                                "value",
                            ),
                            "workload_share": _rounded_detail(
                                {"value": guard_summary.get("workload_share")},
                                "value",
                                6,
                            ),
                            "positive_credit_scale": _rounded_detail(
                                {"value": guard_summary.get("positive_credit_scale")},
                                "value",
                                6,
                            ),
                            "pre_guard_category_delta": _round_numeric_mapping(
                                guard_summary.get("pre_guard_category_delta"),
                                numeric_or_zero_fn=numeric_or_zero_fn,
                            ),
                            "post_guard_category_delta": _round_numeric_mapping(
                                guard_summary.get("post_guard_category_delta"),
                                numeric_or_zero_fn=numeric_or_zero_fn,
                            ),
                        }
                    bounds_summary = replacement_value_diagnostics.get("bounds")
                    if isinstance(bounds_summary, dict):
                        year_entry["bounds"] = {
                            "applied": bool(bounds_summary.get("applied")),
                            "base_ip_min_fill_applied": bool(bounds_summary.get("base_ip_min_fill_applied")),
                            "base_ip_max_trim_applied": bool(bounds_summary.get("base_ip_max_trim_applied")),
                            "player_ip_min_fill_applied": bool(bounds_summary.get("player_ip_min_fill_applied")),
                            "player_ip_max_trim_applied": bool(bounds_summary.get("player_ip_max_trim_applied")),
                            "base_raw_totals": _round_numeric_mapping(
                                bounds_summary.get("base_raw_totals"),
                                numeric_or_zero_fn=numeric_or_zero_fn,
                            ),
                            "base_bounded_totals": _round_numeric_mapping(
                                bounds_summary.get("base_bounded_totals"),
                                numeric_or_zero_fn=numeric_or_zero_fn,
                            ),
                            "player_raw_totals": _round_numeric_mapping(
                                bounds_summary.get("player_raw_totals"),
                                numeric_or_zero_fn=numeric_or_zero_fn,
                            ),
                            "player_bounded_totals": _round_numeric_mapping(
                                bounds_summary.get("player_bounded_totals"),
                                numeric_or_zero_fn=numeric_or_zero_fn,
                            ),
                        }
                    if idx == 0:
                        if best_slot:
                            start_year_fields["start_year_best_slot"] = best_slot
                        if category_sgp:
                            start_year_fields["start_year_category_sgp"] = category_sgp
                            start_year_fields["start_year_top_positive_categories"] = _top_category_entries(
                                category_sgp,
                                positive=True,
                            )
                            start_year_fields["start_year_top_negative_categories"] = _top_category_entries(
                                category_sgp,
                                positive=False,
                            )
                        if "slot_baseline_reference" in year_entry:
                            start_year_fields["start_year_slot_baseline_reference"] = year_entry["slot_baseline_reference"]
                        if "replacement_reference" in year_entry:
                            start_year_fields["start_year_replacement_reference"] = year_entry["replacement_reference"]
                        for field_name in (
                            "replacement_pool_depth",
                            "replacement_depth_mode",
                            "replacement_depth_blend_alpha",
                            "slot_count_per_team",
                            "slot_capacity_league",
                        ):
                            if field_name in year_entry:
                                start_year_fields[f"start_year_{field_name}"] = year_entry[field_name]
                        if "guard" in year_entry:
                            start_year_fields["start_year_guard_summary"] = year_entry["guard"]
                        if "bounds" in year_entry:
                            start_year_fields["start_year_bounds_summary"] = year_entry["bounds"]
            per_year.append(year_entry)

        explanation_entry: dict[str, Any] = {
            "player": player,
            "team": str(row_data.get("Team") or "").strip() or None,
            "pos": str(row_data.get("Pos") or "").strip() or None,
            "mode": scoring_mode,
            "dynasty_value": round(numeric_or_zero_fn(row_data.get("DynastyValue")), 4),
            "raw_dynasty_value": round(numeric_or_zero_fn(row_data.get("RawDynastyValue")), 4),
            "per_year": per_year,
        }
        profile = str(row_data.get("_ExplainPlayerProfile") or "").strip()
        if profile:
            explanation_entry["profile"] = profile
        current_year_volume = row_data.get("_ExplainCurrentYearVolume")
        if isinstance(current_year_volume, dict):
            explanation_entry["current_year_volume"] = {
                "ab": round(numeric_or_zero_fn(current_year_volume.get("ab")), 4),
                "ip": round(numeric_or_zero_fn(current_year_volume.get("ip")), 4),
            }
        risk_flags = row_data.get("_ExplainRiskFlags")
        if isinstance(risk_flags, dict):
            explanation_entry["risk_flags"] = {
                str(key): bool(value)
                for key, value in risk_flags.items()
                if str(key).strip()
            }
        centering_fields_present = any(
            key in row_data
            for key in (
                "CenteringMode",
                "ForcedRosterFallbackApplied",
                "CenteringScore",
                "CenteringBaselineValue",
                "CenteringScoreBaselineValue",
                "ForcedRosterValue",
            )
        )
        if centering_fields_present:
            centering_mode = str(row_data.get("CenteringMode") or "standard").strip() or "standard"
            centering_fallback_value = row_data.get("ForcedRosterFallbackApplied")
            centering_fallback_applied = False if pd.isna(centering_fallback_value) else bool(centering_fallback_value)
            centering_score = numeric_or_zero_fn(
                row_data.get("CenteringScore") if "CenteringScore" in row_data else row_data.get("RawDynastyValue")
            )
            centering_baseline_value = numeric_or_zero_fn(
                row_data.get("CenteringScoreBaselineValue")
                if "CenteringScoreBaselineValue" in row_data
                else row_data.get("CenteringBaselineValue")
            )
            centering: dict[str, Any] = {
                "mode": centering_mode,
                "fallback_applied": centering_fallback_applied,
                "score": round(centering_score, 4),
                "baseline_value": round(centering_baseline_value, 4),
            }
            if "CenteringBaselineValue" in row_data:
                centering["raw_baseline_value"] = round(numeric_or_zero_fn(row_data.get("CenteringBaselineValue")), 4)
            if "ForcedRosterValue" in row_data:
                centering["forced_roster_value"] = round(numeric_or_zero_fn(row_data.get("ForcedRosterValue")), 4)
            minor_slot_cost_value = row_data.get("MinorSlotCostValue")
            if "MinorSlotCostValue" in row_data and not pd.isna(minor_slot_cost_value):
                centering["minor_slot_cost_value"] = round(numeric_or_zero_fn(minor_slot_cost_value), 4)
            minor_eta_offset = row_data.get("MinorEtaOffset")
            if "MinorEtaOffset" in row_data and not pd.isna(minor_eta_offset):
                centering["minor_eta_offset"] = int(round(numeric_or_zero_fn(minor_eta_offset)))
            minor_projected_volume_score = row_data.get("MinorProjectedVolumeScore")
            if "MinorProjectedVolumeScore" in row_data and not pd.isna(minor_projected_volume_score):
                centering["minor_projected_volume_score"] = round(numeric_or_zero_fn(minor_projected_volume_score), 4)
            explanation_entry["centering"] = centering
        if scoring_mode == "roto":
            stat_dynasty = {
                col[len("StatDynasty_"):]: round(numeric_or_zero_fn(row_data.get(col)), 4)
                for col in row_data
                if isinstance(col, str) and col.startswith("StatDynasty_")
            }
            if stat_dynasty:
                explanation_entry["stat_dynasty_contributions"] = stat_dynasty
        explanation_entry.update(start_year_fields)
        explanations[explain_key] = explanation_entry

    return explanations


def playable_pool_counts_by_year(
    *,
    bat_data: list[dict],
    pit_data: list[dict],
    coerce_record_year_fn: Callable[[object], int | None],
    as_float_fn: Callable[[object], float | None],
) -> dict[str, dict[str, int]]:
    by_year: dict[int, dict[str, int]] = {}

    for row in bat_data:
        year = coerce_record_year_fn(row.get("Year"))
        if year is None:
            continue
        ab = as_float_fn(row.get("AB"))
        if ab is None or ab <= 0:
            continue
        bucket = by_year.setdefault(year, {"hitters": 0, "pitchers": 0})
        bucket["hitters"] += 1

    for row in pit_data:
        year = coerce_record_year_fn(row.get("Year"))
        if year is None:
            continue
        ip = as_float_fn(row.get("IP"))
        if ip is None or ip <= 0:
            continue
        bucket = by_year.setdefault(year, {"hitters": 0, "pitchers": 0})
        bucket["pitchers"] += 1

    return {str(year): counts for year, counts in sorted(by_year.items())}


def default_calculation_cache_params(
    *,
    meta: dict,
    coerce_meta_years_fn: Callable[[dict], list[int]],
    common_hitter_slot_defaults: dict[str, int],
    common_pitcher_slot_defaults: dict[str, int],
    common_default_minor_slots: int,
    common_default_ir_slots: int,
    roto_category_field_defaults: dict[str, bool],
) -> dict[str, int | float | str | None]:
    years = coerce_meta_years_fn(meta)
    start_year = years[0] if years else 2026
    horizon = len(years) if years else 10
    params: dict[str, int | float | str | None] = {
        "teams": 12,
        "sims": 300,
        "horizon": horizon,
        "discount": 0.94,
        "hit_c": common_hitter_slot_defaults["C"],
        "hit_1b": common_hitter_slot_defaults["1B"],
        "hit_2b": common_hitter_slot_defaults["2B"],
        "hit_3b": common_hitter_slot_defaults["3B"],
        "hit_ss": common_hitter_slot_defaults["SS"],
        "hit_ci": common_hitter_slot_defaults["CI"],
        "hit_mi": common_hitter_slot_defaults["MI"],
        "hit_of": common_hitter_slot_defaults["OF"],
        "hit_dh": common_hitter_slot_defaults["DH"],
        "hit_ut": common_hitter_slot_defaults["UT"],
        "pit_p": common_pitcher_slot_defaults["P"],
        "pit_sp": common_pitcher_slot_defaults["SP"],
        "pit_rp": common_pitcher_slot_defaults["RP"],
        "bench": 6,
        "minors": common_default_minor_slots,
        "ir": common_default_ir_slots,
        "ip_min": 0.0,
        "ip_max": None,
        "two_way": "sum",
        "start_year": start_year,
        "sgp_denominator_mode": "classic",
        "sgp_winsor_low_pct": 0.10,
        "sgp_winsor_high_pct": 0.90,
        "sgp_epsilon_counting": 0.15,
        "sgp_epsilon_ratio": 0.0015,
        "enable_playing_time_reliability": False,
        "enable_age_risk_adjustment": False,
        "enable_replacement_blend": True,
        "replacement_blend_alpha": 0.40,
        "replacement_depth_mode": "blended_depth",
        "replacement_depth_blend_alpha": 0.33,
    }
    params.update(roto_category_field_defaults)
    return with_resolved_hidden_dynasty_modeling_settings(params)


def calculator_guardrails_payload(
    *,
    common_hitter_starter_slots_per_team: int,
    common_pitcher_starter_slots_per_team: int,
    common_hitter_slot_defaults: dict[str, int],
    common_pitcher_slot_defaults: dict[str, int],
    points_hitter_slot_defaults: dict[str, int],
    points_pitcher_slot_defaults: dict[str, int],
    default_points_scoring: dict[str, float],
    roto_hitter_fields: tuple[tuple[str, str, bool], ...],
    roto_pitcher_fields: tuple[tuple[str, str, bool], ...],
    common_default_minor_slots: int,
    common_default_ir_slots: int,
    playable_by_year: dict[str, dict[str, int]],
    calculator_request_timeout_seconds: int,
    trusted_proxy_networks: tuple[object, ...],
    trust_x_forwarded_for: bool,
    rate_limit_bucket_cleanup_interval_seconds: float,
    calculator_sync_rate_limit_per_minute: int,
    calculator_sync_auth_rate_limit_per_minute: int,
    calculator_job_create_rate_limit_per_minute: int,
    calculator_job_create_auth_rate_limit_per_minute: int,
    calculator_job_status_rate_limit_per_minute: int,
    calculator_job_status_auth_rate_limit_per_minute: int,
    projection_rate_limit_per_minute: int,
    projection_export_rate_limit_per_minute: int,
    calculator_max_active_jobs_per_ip: int,
    calculator_max_active_jobs_total: int,
) -> dict:
    return {
        "hitters_per_team": common_hitter_starter_slots_per_team,
        "pitchers_per_team": common_pitcher_starter_slots_per_team,
        "default_hitter_slots": common_hitter_slot_defaults.copy(),
        "default_pitcher_slots": common_pitcher_slot_defaults.copy(),
        "default_points_hitter_slots": points_hitter_slot_defaults.copy(),
        "default_points_pitcher_slots": points_pitcher_slot_defaults.copy(),
        "default_points_scoring": default_points_scoring.copy(),
        "default_roto_hitter_categories": [label for _key, label, _default in roto_hitter_fields],
        "default_roto_pitcher_categories": [label for _key, label, _default in roto_pitcher_fields],
        "default_minors_slots": common_default_minor_slots,
        "default_ir_slots": common_default_ir_slots,
        "playable_by_year": playable_by_year,
        "job_timeout_seconds": calculator_request_timeout_seconds,
        "rate_limit_identity_mode": (
            "trusted_proxy_cidrs"
            if trusted_proxy_networks
            else ("trust_all_x_forwarded_for" if trust_x_forwarded_for else "remote_addr_only")
        ),
        "trust_x_forwarded_for": trust_x_forwarded_for,
        "trusted_proxy_cidrs": [str(network) for network in trusted_proxy_networks],
        "rate_limit_bucket_cleanup_interval_seconds": rate_limit_bucket_cleanup_interval_seconds,
        "rate_limit_sync_per_minute": calculator_sync_rate_limit_per_minute,
        "rate_limit_sync_authenticated_per_minute": calculator_sync_auth_rate_limit_per_minute,
        "rate_limit_job_create_per_minute": calculator_job_create_rate_limit_per_minute,
        "rate_limit_job_create_authenticated_per_minute": calculator_job_create_auth_rate_limit_per_minute,
        "rate_limit_job_status_per_minute": calculator_job_status_rate_limit_per_minute,
        "rate_limit_job_status_authenticated_per_minute": calculator_job_status_auth_rate_limit_per_minute,
        "rate_limit_projections_per_minute": projection_rate_limit_per_minute,
        "rate_limit_projection_exports_per_minute": projection_export_rate_limit_per_minute,
        "max_active_jobs_per_ip": calculator_max_active_jobs_per_ip,
        "max_active_jobs_total": calculator_max_active_jobs_total,
    }


# ---------------------------------------------------------------------------
# Prewarm configurations — popular league setups to cache at startup
# ---------------------------------------------------------------------------
# Each entry overrides the default params produced by default_calculation_cache_params.
# "mode" is "roto" or "points".  Only non-default fields need to be specified.
PREWARM_CONFIGS: list[dict[str, Any]] = [
    # 1) 12-team 5x5 roto (the default — already computed by the base prewarm)
    {"label": "12T-5x5-roto"},
    # 2) 10-team 5x5 roto
    {"label": "10T-5x5-roto", "teams": 10},
    # 3) 14-team 5x5 roto
    {"label": "14T-5x5-roto", "teams": 14},
    # 4) 12-team points
    {"label": "12T-points", "mode": "points"},
    # 5) 12-team deep 6x6 roto (OPS + QA3/SVH with hidden stash realism)
    {
        "label": "12T-deep-dynasty-roto",
        "hit_c": 2,
        "hit_1b": 1,
        "hit_2b": 1,
        "hit_3b": 1,
        "hit_ss": 1,
        "hit_ci": 1,
        "hit_mi": 1,
        "hit_of": 5,
        "hit_dh": 0,
        "hit_ut": 2,
        "pit_p": 3,
        "pit_sp": 3,
        "pit_rp": 3,
        "bench": 14,
        "minors": 20,
        "ir": 8,
        "ip_min": 1000.0,
        "ip_max": 1500.0,
        "roto_hit_ops": True,
        "roto_hit_avg": True,
        "roto_pit_sv": False,
        "roto_pit_qa3": True,
        "roto_pit_svh": True,
    },
]
