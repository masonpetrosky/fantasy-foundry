"""Shared calculator helper functions for guards, categories, stats, and explanations."""

from __future__ import annotations

from typing import Any, Callable

import pandas as pd


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


def roto_category_settings_from_dict(
    source: dict[str, Any] | None,
    *,
    coerce_bool_fn: Callable[[object], bool],
    defaults: dict[str, bool],
) -> dict[str, bool]:
    settings = source if isinstance(source, dict) else {}
    return {
        field_key: coerce_bool_fn(settings.get(field_key), default=default_value)
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

        per_year: list[dict] = []
        for idx, year_col in enumerate(year_cols):
            suffix = year_col.split("_", 1)[1] if "_" in year_col else year_col
            year_token: int | str = int(suffix) if str(suffix).isdigit() else suffix
            year_value = numeric_or_zero_fn(row_data.get(year_col))
            discount_factor = float(discount) ** idx
            discounted = year_value * discount_factor
            if scoring_mode == "points":
                points_detail = points_by_year.get(str(year_token))
                if isinstance(points_detail, dict):
                    detail_discount_factor = points_detail.get("discount_factor")
                    if detail_discount_factor is not None:
                        discount_factor = numeric_or_zero_fn(detail_discount_factor)
                    detail_discounted = points_detail.get("discounted_contribution")
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
            per_year.append(year_entry)

        explanations[explain_key] = {
            "player": player,
            "team": str(row_data.get("Team") or "").strip() or None,
            "pos": str(row_data.get("Pos") or "").strip() or None,
            "mode": scoring_mode,
            "dynasty_value": round(numeric_or_zero_fn(row_data.get("DynastyValue")), 4),
            "raw_dynasty_value": round(numeric_or_zero_fn(row_data.get("RawDynastyValue")), 4),
            "per_year": per_year,
        }

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
        "enable_replacement_blend": False,
        "replacement_blend_alpha": 0.70,
    }
    params.update(roto_category_field_defaults)
    return params


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
