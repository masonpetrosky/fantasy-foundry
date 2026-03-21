"""Bound runtime facade wrappers extracted from backend.runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Literal, Mapping

import pandas as pd
from fastapi import Request
from fastapi.responses import StreamingResponse

REQUIRED_RUNTIME_FACADE_ALIAS_KEYS = frozenset(
    {
        "_validate_runtime_configuration",
        "_extract_calculate_api_key",
        "_path_signature",
        "_compute_data_signature",
        "_stable_data_version_path_label",
        "_hash_file_into",
        "_compute_content_data_version",
        "_current_data_version",
        "_coerce_serialized_dynasty_lookup_map",
        "_dynasty_lookup_payload_version",
        "_inspect_precomputed_default_dynasty_lookup",
        "_load_precomputed_default_dynasty_lookup",
        "_reload_projection_data",
        "_parse_ip_text",
        "_trusted_proxy_ip",
        "_forwarded_for_chain",
        "_client_ip",
        "_calc_result_cache_key",
        "_redis_client",
        "_get_request_rate_limit_last_sweep_ts",
        "_set_request_rate_limit_last_sweep_ts",
        "_ensure_backend_module_path",
        "_calculate_common_dynasty_frame_cached",
        "_stat_or_zero",
        "_coerce_minor_eligible",
        "_projection_identity_key",
        "_coerce_bool",
        "_roto_category_settings_from_dict",
        "_selected_roto_categories",
        "_start_year_roto_stats_by_entity",
        "_valuation_years",
        "_calculate_hitter_points_breakdown",
        "_calculate_pitcher_points_breakdown",
        "_points_player_identity",
        "_points_hitter_eligible_slots",
        "_points_pitcher_eligible_slots",
        "_points_slot_replacement",
        "_calculate_points_dynasty_frame_cached",
        "_is_user_fixable_calculation_error",
        "_numeric_or_zero",
        "_build_calculation_explanations",
        "_clean_records_for_json",
        "_flatten_explanations_for_export",
        "_default_calculator_export_columns",
        "_tabular_export_response",
        "_playable_pool_counts_by_year",
        "_default_calculation_cache_params",
        "_default_dynasty_methodology_fingerprint",
        "_calculator_guardrails_payload",
        "_iso_now",
        "_mark_job_cancelled_locked",
        "_cleanup_calculation_jobs",
        "_calculation_job_public_payload",
        "_prewarm_default_calculation_caches",
        "_get_default_dynasty_lookup",
        "_parse_dynasty_years",
        "_resolve_projection_year_filter",
        "_attach_dynasty_values",
        "_player_identity_by_name",
        "_refresh_data_if_needed",
        "_clear_after_data_reload",
        "_calculator_overlay_values_for_job",
        "_calculator_service_from_globals",
        "_log_precomputed_dynasty_lookup_cache_status",
    }
)


def missing_runtime_facade_alias_keys(alias_map: Mapping[str, Any]) -> set[str]:
    return set(REQUIRED_RUNTIME_FACADE_ALIAS_KEYS) - set(alias_map.keys())


def unexpected_runtime_facade_alias_keys(alias_map: Mapping[str, Any]) -> set[str]:
    return set(alias_map.keys()) - set(REQUIRED_RUNTIME_FACADE_ALIAS_KEYS)


def validate_runtime_facade_alias_map(alias_map: Mapping[str, Any]) -> None:
    missing = missing_runtime_facade_alias_keys(alias_map)
    unexpected = unexpected_runtime_facade_alias_keys(alias_map)
    if not missing and not unexpected:
        return
    details: list[str] = []
    if missing:
        details.append(f"missing={sorted(missing)}")
    if unexpected:
        details.append(f"unexpected={sorted(unexpected)}")
    raise RuntimeError("Invalid runtime facade alias map contract: " + "; ".join(details))


def build_runtime_facade_alias_map(*, state_module: Any) -> dict[str, Any]:
    def _validate_runtime_configuration() -> None:
        state_module.core_runtime_state_helpers.validate_runtime_configuration(state=state_module)

    def _extract_calculate_api_key(request: Request | None) -> str | None:
        return state_module.core_extract_calculate_api_key(request)

    def _path_signature(path: Any) -> tuple[str, int | None, int | None]:
        return state_module.core_path_signature(path)

    def _compute_data_signature() -> tuple[tuple[str, int | None, int | None], ...]:
        return state_module.core_compute_data_signature(state_module.DATA_REFRESH_PATHS)

    def _stable_data_version_path_label(path: Any) -> str:
        return state_module.core_stable_data_version_path_label(path)

    def _hash_file_into(path: Any, hasher: Any) -> None:
        state_module.core_hash_file_into(path, hasher)

    def _compute_content_data_version(paths: tuple[Any, ...]) -> str:
        return state_module.core_compute_content_data_version(paths)

    def _current_data_version() -> str:
        return state_module._DATA_CONTENT_VERSION

    def _coerce_serialized_dynasty_lookup_map(raw: object) -> dict[str, dict]:
        return state_module.core_coerce_serialized_dynasty_lookup_map(raw)

    def _dynasty_lookup_payload_version(payload: dict[str, object]) -> str | None:
        return state_module.core_dynasty_lookup_payload_version(payload)

    def _inspect_precomputed_default_dynasty_lookup() -> Any:
        return state_module.core_runtime_state_helpers.inspect_precomputed_default_dynasty_lookup(state=state_module)

    def _load_precomputed_default_dynasty_lookup() -> tuple[dict[str, dict], dict[str, dict], set[str], list[str]] | None:
        return state_module.core_runtime_state_helpers.load_precomputed_default_dynasty_lookup(state=state_module)

    def _reload_projection_data() -> None:
        (
            state_module.META,
            state_module.BAT_DATA_RAW,
            state_module.PIT_DATA_RAW,
            state_module.BAT_DATA,
            state_module.PIT_DATA,
            state_module.PROJECTION_FRESHNESS,
        ) = state_module.service_reload_projection_data(
            load_json=state_module.load_json,
            with_player_identity_keys=state_module._with_player_identity_keys,
            average_recent_projection_rows=state_module._average_recent_projection_rows,
            projection_freshness_payload=state_module._projection_freshness_payload,
        )

    def _parse_ip_text(raw: str | None) -> Any:
        return state_module.core_parse_ip_text(raw)

    def _trusted_proxy_ip(addr: Any) -> bool:
        return state_module.core_trusted_proxy_ip(
            addr,
            trusted_proxy_networks=state_module.TRUSTED_PROXY_NETWORKS,
            trust_x_forwarded_for=state_module.TRUST_X_FORWARDED_FOR,
        )

    def _forwarded_for_chain(header_value: str | None) -> list[Any]:
        return state_module.core_forwarded_for_chain(header_value)

    def _client_ip(request: Request | None) -> str:
        return state_module.core_client_ip(
            request,
            trust_x_forwarded_for=state_module.TRUST_X_FORWARDED_FOR,
            trusted_proxy_networks=state_module.TRUSTED_PROXY_NETWORKS,
        )

    def _calc_result_cache_key(settings: dict[str, Any]) -> str:
        return state_module.core_calc_result_cache_key(settings)

    def _redis_client() -> Any | None:
        return state_module.core_runtime_infra.get_redis_client(
            redis_url=state_module.REDIS_URL,
            redis_lib=state_module.redis_lib,
            state=state_module.REDIS_CLIENT_STATE,
            logger=state_module.CALC_LOGGER,
        )

    def _get_request_rate_limit_last_sweep_ts() -> float:
        # Keep module-level variable as the source of truth for compatibility
        # with existing tests and patching patterns.
        return float(state_module._REQUEST_RATE_LIMIT_LAST_SWEEP_TS)

    def _set_request_rate_limit_last_sweep_ts(value: float) -> None:
        runtime_state = getattr(state_module, "RUNTIME_STATE", None)
        if runtime_state is not None:
            runtime_state.request_rate_limit_last_sweep_ts = float(value)
        state_module._REQUEST_RATE_LIMIT_LAST_SWEEP_TS = float(value)

    def _ensure_backend_module_path() -> None:
        backend_path = str(state_module.BACKEND_MODULE_DIR)
        if backend_path not in state_module.sys.path:
            state_module.sys.path.insert(0, backend_path)

    @lru_cache(maxsize=16)
    def _calculate_common_dynasty_frame_cached(
        teams: int,
        sims: int,
        horizon: int,
        discount: float,
        hit_c: int,
        hit_1b: int,
        hit_2b: int,
        hit_3b: int,
        hit_ss: int,
        hit_ci: int,
        hit_mi: int,
        hit_of: int,
        hit_ut: int,
        pit_p: int,
        pit_sp: int,
        pit_rp: int,
        bench: int,
        minors: int,
        ir: int,
        ip_min: float,
        ip_max: float | None,
        two_way: str,
        start_year: int,
        sgp_denominator_mode: str = "classic",
        sgp_winsor_low_pct: float = 0.10,
        sgp_winsor_high_pct: float = 0.90,
        sgp_epsilon_counting: float = 0.15,
        sgp_epsilon_ratio: float = 0.0015,
        enable_playing_time_reliability: bool = False,
        enable_age_risk_adjustment: bool = False,
        enable_prospect_risk_adjustment: bool = True,
        enable_bench_stash_relief: bool = False,
        bench_negative_penalty: float = 0.55,
        enable_ir_stash_relief: bool = False,
        ir_negative_penalty: float = 0.20,
        enable_replacement_blend: bool = True,
        replacement_blend_alpha: float = 0.40,
        replacement_depth_mode: str = "blended_depth",
        replacement_depth_blend_alpha: float = 0.33,
        replacement_depth_blend_alpha_by_slot_json: str = "",
        hit_dh: int = 0,
        **roto_category_settings: bool,
    ) -> pd.DataFrame:
        return state_module.core_runtime_state_helpers.calculate_common_dynasty_frame_cached(
            state=state_module,
            teams=teams,
            sims=sims,
            horizon=horizon,
            discount=discount,
            hit_c=hit_c,
            hit_1b=hit_1b,
            hit_2b=hit_2b,
            hit_3b=hit_3b,
            hit_ss=hit_ss,
            hit_ci=hit_ci,
            hit_mi=hit_mi,
            hit_of=hit_of,
            hit_dh=hit_dh,
            hit_ut=hit_ut,
            pit_p=pit_p,
            pit_sp=pit_sp,
            pit_rp=pit_rp,
            bench=bench,
            minors=minors,
            ir=ir,
            ip_min=ip_min,
            ip_max=ip_max,
            two_way=two_way,
            start_year=start_year,
            sgp_denominator_mode=sgp_denominator_mode,
            sgp_winsor_low_pct=sgp_winsor_low_pct,
            sgp_winsor_high_pct=sgp_winsor_high_pct,
            sgp_epsilon_counting=sgp_epsilon_counting,
            sgp_epsilon_ratio=sgp_epsilon_ratio,
            enable_playing_time_reliability=enable_playing_time_reliability,
            enable_age_risk_adjustment=enable_age_risk_adjustment,
            enable_prospect_risk_adjustment=enable_prospect_risk_adjustment,
            enable_bench_stash_relief=enable_bench_stash_relief,
            bench_negative_penalty=bench_negative_penalty,
            enable_ir_stash_relief=enable_ir_stash_relief,
            ir_negative_penalty=ir_negative_penalty,
            enable_replacement_blend=enable_replacement_blend,
            replacement_blend_alpha=replacement_blend_alpha,
            replacement_depth_mode=replacement_depth_mode,
            replacement_depth_blend_alpha=replacement_depth_blend_alpha,
            replacement_depth_blend_alpha_by_slot_json=replacement_depth_blend_alpha_by_slot_json,
            roto_category_settings=roto_category_settings,
        )

    def _stat_or_zero(row: dict | None, key: str) -> float:
        return state_module.core_stat_or_zero(row, key, as_float_fn=state_module._as_float)

    def _coerce_minor_eligible(value: object) -> bool:
        return state_module.core_coerce_minor_eligible(value)

    def _projection_identity_key(row: dict | pd.Series) -> str:
        return state_module.core_projection_identity_key(
            row,
            player_entity_key_col=state_module.PLAYER_ENTITY_KEY_COL,
            player_key_col=state_module.PLAYER_KEY_COL,
            normalize_player_key_fn=state_module._normalize_player_key,
        )

    def _coerce_bool(value: object, *, default: bool = False) -> bool:
        return state_module.core_coerce_bool(value, default=default)

    def _roto_category_settings_from_dict(source: dict[str, Any] | None) -> dict[str, bool]:
        return state_module.core_roto_category_settings_from_dict(
            source,
            coerce_bool_fn=_coerce_bool,
            defaults=state_module.ROTO_CATEGORY_FIELD_DEFAULTS,
        )

    def _selected_roto_categories(settings: dict[str, Any]) -> tuple[list[str], list[str]]:
        return state_module.core_selected_roto_categories(
            settings,
            roto_category_settings_from_dict_fn=_roto_category_settings_from_dict,
            hitter_fields=state_module.ROTO_HITTER_CATEGORY_FIELDS,
            pitcher_fields=state_module.ROTO_PITCHER_CATEGORY_FIELDS,
        )

    @lru_cache(maxsize=64)
    def _start_year_roto_stats_by_entity(
        *,
        start_year: int,
    ) -> dict[str, dict[str, float]]:
        return state_module.core_start_year_roto_stats_by_entity(
            start_year=start_year,
            bat_data=state_module.BAT_DATA,
            pit_data=state_module.PIT_DATA,
            coerce_record_year_fn=state_module._coerce_record_year,
            projection_identity_key_fn=_projection_identity_key,
            coerce_numeric_fn=state_module._coerce_numeric,
            roto_hitter_fields=state_module.ROTO_HITTER_CATEGORY_FIELDS,
            roto_pitcher_fields=state_module.ROTO_PITCHER_CATEGORY_FIELDS,
        )

    def _valuation_years(start_year: int, horizon: int, valid_years: list[int]) -> list[int]:
        return state_module.core_valuation_years(start_year, horizon, valid_years)

    def _calculate_hitter_points_breakdown(row: dict | None, scoring: dict[str, float]) -> dict:
        return state_module.core_calculate_hitter_points_breakdown(
            row,
            scoring,
            stat_or_zero_fn=_stat_or_zero,
        )

    def _calculate_pitcher_points_breakdown(row: dict | None, scoring: dict[str, float]) -> dict:
        return state_module.core_calculate_pitcher_points_breakdown(
            row,
            scoring,
            stat_or_zero_fn=_stat_or_zero,
        )

    def _points_player_identity(row: dict) -> str:
        return state_module.core_points_player_identity(
            row,
            player_entity_key_col=state_module.PLAYER_ENTITY_KEY_COL,
            player_key_col=state_module.PLAYER_KEY_COL,
            normalize_player_key_fn=state_module._normalize_player_key,
        )

    def _points_hitter_eligible_slots(pos_value: object) -> set[str]:
        return state_module.core_points_hitter_eligible_slots(
            pos_value,
            position_tokens_fn=state_module._position_tokens,
        )

    def _points_pitcher_eligible_slots(pos_value: object) -> set[str]:
        return state_module.core_points_pitcher_eligible_slots(
            pos_value,
            position_tokens_fn=state_module._position_tokens,
        )

    def _points_slot_replacement(
        entries: list[dict[str, object]],
        *,
        active_slots: set[str],
        rostered_player_ids: set[str],
        n_replacement: int,
    ) -> dict[str, float]:
        return state_module.core_points_slot_replacement(
            entries,
            active_slots=active_slots,
            rostered_player_ids=rostered_player_ids,
            n_replacement=n_replacement,
            as_float_fn=state_module._as_float,
        )

    @lru_cache(maxsize=16)
    def _calculate_points_dynasty_frame_cached(
        teams: int,
        horizon: int,
        discount: float,
        hit_c: int,
        hit_1b: int,
        hit_2b: int,
        hit_3b: int,
        hit_ss: int,
        hit_ci: int,
        hit_mi: int,
        hit_of: int,
        hit_ut: int,
        pit_p: int,
        pit_sp: int,
        pit_rp: int,
        bench: int,
        minors: int,
        ir: int,
        keeper_limit: int | None,
        two_way: str,
        points_valuation_mode: str,
        weekly_starts_cap: int | None,
        allow_same_day_starts_overflow: bool,
        weekly_acquisition_cap: int | None,
        start_year: int,
        pts_hit_1b: float,
        pts_hit_2b: float,
        pts_hit_3b: float,
        pts_hit_hr: float,
        pts_hit_r: float,
        pts_hit_rbi: float,
        pts_hit_sb: float,
        pts_hit_bb: float,
        pts_hit_hbp: float,
        pts_hit_so: float,
        pts_pit_ip: float,
        pts_pit_w: float,
        pts_pit_l: float,
        pts_pit_k: float,
        pts_pit_sv: float,
        pts_pit_hld: float,
        pts_pit_h: float,
        pts_pit_er: float,
        pts_pit_bb: float,
        pts_pit_hbp: float,
        ip_max: float | None = None,
        enable_prospect_risk_adjustment: bool = True,
        enable_bench_stash_relief: bool = False,
        bench_negative_penalty: float = 0.55,
        enable_ir_stash_relief: bool = False,
        ir_negative_penalty: float = 0.20,
        hit_dh: int = 0,
    ) -> pd.DataFrame:
        return state_module.core_runtime_state_helpers.calculate_points_dynasty_frame_cached(
            state=state_module,
            teams=teams,
            horizon=horizon,
            discount=discount,
            hit_c=hit_c,
            hit_1b=hit_1b,
            hit_2b=hit_2b,
            hit_3b=hit_3b,
            hit_ss=hit_ss,
            hit_ci=hit_ci,
            hit_mi=hit_mi,
            hit_of=hit_of,
            hit_dh=hit_dh,
            hit_ut=hit_ut,
            pit_p=pit_p,
            pit_sp=pit_sp,
            pit_rp=pit_rp,
            bench=bench,
            minors=minors,
            ir=ir,
            keeper_limit=keeper_limit,
            two_way=two_way,
            points_valuation_mode=points_valuation_mode,
            ip_max=ip_max,
            weekly_starts_cap=weekly_starts_cap,
            allow_same_day_starts_overflow=allow_same_day_starts_overflow,
            weekly_acquisition_cap=weekly_acquisition_cap,
            enable_prospect_risk_adjustment=enable_prospect_risk_adjustment,
            enable_bench_stash_relief=enable_bench_stash_relief,
            bench_negative_penalty=bench_negative_penalty,
            enable_ir_stash_relief=enable_ir_stash_relief,
            ir_negative_penalty=ir_negative_penalty,
            start_year=start_year,
            pts_hit_1b=pts_hit_1b,
            pts_hit_2b=pts_hit_2b,
            pts_hit_3b=pts_hit_3b,
            pts_hit_hr=pts_hit_hr,
            pts_hit_r=pts_hit_r,
            pts_hit_rbi=pts_hit_rbi,
            pts_hit_sb=pts_hit_sb,
            pts_hit_bb=pts_hit_bb,
            pts_hit_hbp=pts_hit_hbp,
            pts_hit_so=pts_hit_so,
            pts_pit_ip=pts_pit_ip,
            pts_pit_w=pts_pit_w,
            pts_pit_l=pts_pit_l,
            pts_pit_k=pts_pit_k,
            pts_pit_sv=pts_pit_sv,
            pts_pit_hld=pts_pit_hld,
            pts_pit_h=pts_pit_h,
            pts_pit_er=pts_pit_er,
            pts_pit_bb=pts_pit_bb,
            pts_pit_hbp=pts_pit_hbp,
        )

    def _is_user_fixable_calculation_error(message: str) -> bool:
        return state_module.core_is_user_fixable_calculation_error(message)

    def _numeric_or_zero(value: object) -> float:
        return state_module.core_numeric_or_zero(value, as_float_fn=state_module._as_float)

    def _build_calculation_explanations(out: pd.DataFrame, *, settings: dict[str, Any]) -> dict[str, dict]:
        return state_module.core_build_calculation_explanations(
            out,
            settings=settings,
            player_key_col=state_module.PLAYER_KEY_COL,
            player_entity_key_col=state_module.PLAYER_ENTITY_KEY_COL,
            normalize_player_key_fn=state_module._normalize_player_key,
            numeric_or_zero_fn=_numeric_or_zero,
            value_col_sort_key_fn=state_module._value_col_sort_key,
        )

    def _clean_records_for_json(records: list[dict]) -> list[dict]:
        return state_module.core_clean_records_for_json(records)

    def _flatten_explanations_for_export(explanations: dict[str, dict]) -> list[dict]:
        return state_module.core_flatten_explanations_for_export(explanations)

    def _default_calculator_export_columns(rows: list[dict]) -> list[str]:
        return state_module.core_default_calculator_export_columns(
            rows,
            calculator_result_stat_export_order=state_module.CALCULATOR_RESULT_STAT_EXPORT_ORDER,
            calculator_result_points_export_order=state_module.CALCULATOR_RESULT_POINTS_EXPORT_ORDER,
            value_col_sort_key=state_module._value_col_sort_key,
        )

    def _tabular_export_response(
        rows: list[dict],
        *,
        filename_base: str,
        file_format: Literal["csv", "xlsx"],
        explain_rows: list[dict] | None = None,
        selected_columns: list[str] | tuple[str, ...] | set[str] | str | None = None,
        default_columns: list[str] | tuple[str, ...] | set[str] | str | None = None,
        required_columns: list[str] | tuple[str, ...] | set[str] | str | None = None,
        disallowed_columns: list[str] | tuple[str, ...] | set[str] | str | None = None,
    ) -> StreamingResponse:
        return state_module.core_tabular_export_response(
            rows,
            filename_base=filename_base,
            file_format=file_format,
            explain_rows=explain_rows,
            selected_columns=selected_columns,
            default_columns=default_columns,
            required_columns=required_columns,
            disallowed_columns=disallowed_columns,
            export_date_cols=state_module.EXPORT_DATE_COLS,
            export_header_label_overrides=state_module.EXPORT_HEADER_LABEL_OVERRIDES,
            export_three_decimal_cols=state_module.EXPORT_THREE_DECIMAL_COLS,
            export_two_decimal_cols=state_module.EXPORT_TWO_DECIMAL_COLS,
            export_whole_number_cols=state_module.EXPORT_WHOLE_NUMBER_COLS,
            export_integer_cols=state_module.EXPORT_INTEGER_COLS,
        )

    @lru_cache(maxsize=1)
    def _playable_pool_counts_by_year() -> dict[str, dict[str, int]]:
        return state_module.core_playable_pool_counts_by_year(
            bat_data=state_module.BAT_DATA,
            pit_data=state_module.PIT_DATA,
            coerce_record_year_fn=state_module._coerce_record_year,
            as_float_fn=state_module._as_float,
        )

    def _default_calculation_cache_params() -> dict[str, int | float | str | None]:
        return state_module.core_default_calculation_cache_params(
            meta=state_module.META,
            coerce_meta_years_fn=state_module._coerce_meta_years,
            common_hitter_slot_defaults=state_module.COMMON_HITTER_SLOT_DEFAULTS,
            common_pitcher_slot_defaults=state_module.COMMON_PITCHER_SLOT_DEFAULTS,
            common_default_minor_slots=state_module.COMMON_DEFAULT_MINOR_SLOTS,
            common_default_ir_slots=state_module.COMMON_DEFAULT_IR_SLOTS,
            roto_category_field_defaults=state_module.ROTO_CATEGORY_FIELD_DEFAULTS,
        )

    def _default_dynasty_methodology_fingerprint() -> str:
        return state_module.core_default_dynasty_methodology_fingerprint(
            default_params=_default_calculation_cache_params(),
        )

    def _calculator_guardrails_payload() -> dict:
        return state_module.core_calculator_guardrails_payload(
            common_hitter_starter_slots_per_team=state_module.COMMON_HITTER_STARTER_SLOTS_PER_TEAM,
            common_pitcher_starter_slots_per_team=state_module.COMMON_PITCHER_STARTER_SLOTS_PER_TEAM,
            common_hitter_slot_defaults=state_module.COMMON_HITTER_SLOT_DEFAULTS,
            common_pitcher_slot_defaults=state_module.COMMON_PITCHER_SLOT_DEFAULTS,
            points_hitter_slot_defaults=state_module.POINTS_HITTER_SLOT_DEFAULTS,
            points_pitcher_slot_defaults=state_module.POINTS_PITCHER_SLOT_DEFAULTS,
            default_points_scoring=state_module.DEFAULT_POINTS_SCORING,
            roto_hitter_fields=state_module.ROTO_HITTER_CATEGORY_FIELDS,
            roto_pitcher_fields=state_module.ROTO_PITCHER_CATEGORY_FIELDS,
            common_default_minor_slots=state_module.COMMON_DEFAULT_MINOR_SLOTS,
            common_default_ir_slots=state_module.COMMON_DEFAULT_IR_SLOTS,
            playable_by_year=_playable_pool_counts_by_year(),
            calculator_request_timeout_seconds=state_module.CALCULATOR_REQUEST_TIMEOUT_SECONDS,
            trusted_proxy_networks=state_module.TRUSTED_PROXY_NETWORKS,
            trust_x_forwarded_for=state_module.TRUST_X_FORWARDED_FOR,
            rate_limit_bucket_cleanup_interval_seconds=state_module.RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS,
            calculator_sync_rate_limit_per_minute=state_module.CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE,
            calculator_sync_auth_rate_limit_per_minute=state_module.CALCULATOR_SYNC_AUTH_RATE_LIMIT_PER_MINUTE,
            calculator_job_create_rate_limit_per_minute=state_module.CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE,
            calculator_job_create_auth_rate_limit_per_minute=state_module.CALCULATOR_JOB_CREATE_AUTH_RATE_LIMIT_PER_MINUTE,
            calculator_job_status_rate_limit_per_minute=state_module.CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE,
            calculator_job_status_auth_rate_limit_per_minute=state_module.CALCULATOR_JOB_STATUS_AUTH_RATE_LIMIT_PER_MINUTE,
            projection_rate_limit_per_minute=state_module.PROJECTION_RATE_LIMITS.read_per_minute,
            projection_export_rate_limit_per_minute=state_module.PROJECTION_RATE_LIMITS.export_per_minute,
            calculator_max_active_jobs_per_ip=state_module.CALCULATOR_MAX_ACTIVE_JOBS_PER_IP,
            calculator_max_active_jobs_total=state_module.CALCULATOR_MAX_ACTIVE_JOBS_TOTAL,
        )

    def _iso_now() -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    def _mark_job_cancelled_locked(job: dict, *, now: str | None = None) -> None:
        timestamp = now or _iso_now()
        state_module.core_mark_job_cancelled_locked(
            job,
            now=timestamp,
            cancelled_status=state_module.CALC_JOB_CANCELLED_STATUS,
            cancelled_error=state_module.CALC_JOB_CANCELLED_ERROR,
        )

    def _cleanup_calculation_jobs(now_ts: float | None = None) -> None:
        state_module.core_cleanup_calculation_jobs(
            state_module.CALCULATOR_JOBS,
            now_ts=now_ts,
            job_ttl_seconds=state_module.CALCULATOR_JOB_TTL_SECONDS,
            job_max_entries=state_module.CALCULATOR_JOB_MAX_ENTRIES,
            cancelled_status=state_module.CALC_JOB_CANCELLED_STATUS,
        )

    def _calculation_job_public_payload(job: dict) -> dict:
        return state_module.core_calculation_job_public_payload(
            job,
            calculator_jobs=state_module.CALCULATOR_JOBS,
            cancelled_status=state_module.CALC_JOB_CANCELLED_STATUS,
        )

    def _prewarm_default_calculation_caches() -> None:
        state_module.core_runtime_state_helpers.prewarm_default_calculation_caches(state=state_module)

    @lru_cache(maxsize=2)
    def _get_default_dynasty_lookup(
        *, prefer_precomputed: bool = True,
    ) -> tuple[dict[str, dict], dict[str, dict], set[str], list[str]]:
        return state_module.core_default_dynasty_lookup(
            inspect_precomputed_default_dynasty_lookup=state_module._inspect_precomputed_default_dynasty_lookup,
            require_precomputed_dynasty_lookup=state_module.REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP,
            prefer_precomputed=prefer_precomputed,
            required_lookup_error_factory=state_module.PrecomputedDynastyLookupRequiredError,
            default_calculation_cache_params=state_module._default_calculation_cache_params,
            calculate_common_dynasty_frame_cached=state_module._calculate_common_dynasty_frame_cached,
            roto_category_settings_from_dict=state_module._roto_category_settings_from_dict,
            value_col_sort_key=state_module._value_col_sort_key,
            normalize_team_key=state_module._normalize_team_key,
            normalize_player_key=state_module._normalize_player_key,
            bat_data=state_module.BAT_DATA,
            pit_data=state_module.PIT_DATA,
            player_key_col=state_module.PLAYER_KEY_COL,
            player_entity_key_col=state_module.PLAYER_ENTITY_KEY_COL,
        )

    def _parse_dynasty_years(raw: str | None, *, valid_years: list[int] | None = None) -> list[int]:
        return state_module.PROJECTION_DYNASTY_HELPERS.parse_dynasty_years(raw, valid_years=valid_years)

    def _resolve_projection_year_filter(
        year: int | None,
        years: str | None,
        *,
        valid_years: list[int] | None = None,
    ) -> set[int] | None:
        return state_module.PROJECTION_DYNASTY_HELPERS.resolve_projection_year_filter(
            year,
            years,
            valid_years=valid_years,
        )

    def _attach_dynasty_values(rows: list[dict], dynasty_years: list[int] | None = None) -> list[dict]:
        return state_module.PROJECTION_DYNASTY_HELPERS.attach_dynasty_values(rows, dynasty_years=dynasty_years)

    @lru_cache(maxsize=1)
    def _player_identity_by_name() -> dict[str, tuple[str, str | None]]:
        return state_module.core_player_identity_by_name(
            bat_data=state_module.BAT_DATA,
            pit_data=state_module.PIT_DATA,
            player_key_col=state_module.PLAYER_KEY_COL,
            player_entity_key_col=state_module.PLAYER_ENTITY_KEY_COL,
            normalize_player_key=state_module._normalize_player_key,
        )

    def _refresh_data_if_needed() -> None:
        result = state_module.core_refresh_data_if_needed(
            data_refresh_lock=state_module.DATA_REFRESH_LOCK,
            data_refresh_paths=state_module.DATA_REFRESH_PATHS,
            current_data_source_signature=state_module._DATA_SOURCE_SIGNATURE,
            compute_data_signature_fn=state_module.core_compute_data_signature,
            reload_projection_data_fn=_reload_projection_data,
            on_reload_exception=state_module.traceback.print_exc,
            clear_after_reload=_clear_after_data_reload,
            compute_content_data_version_fn=state_module.core_compute_content_data_version,
        )
        if result is None:
            return
        signature, content_version = result
        state_module._DATA_SOURCE_SIGNATURE = signature
        state_module._DATA_CONTENT_VERSION = content_version
        runtime_state = getattr(state_module, "RUNTIME_STATE", None)
        if runtime_state is not None:
            runtime_state.data_source_signature = signature
            runtime_state.data_content_version = content_version

    def _clear_after_data_reload() -> None:
        if hasattr(state_module, "PROJECTION_SERVICE"):
            state_module.PROJECTION_SERVICE.clear_caches()
        _calculate_common_dynasty_frame_cached.cache_clear()
        _calculate_points_dynasty_frame_cached.cache_clear()
        _playable_pool_counts_by_year.cache_clear()
        _get_default_dynasty_lookup.cache_clear()
        _player_identity_by_name.cache_clear()
        _start_year_roto_stats_by_entity.cache_clear()
        with state_module.CALC_RESULT_CACHE_LOCK:
            state_module.CALC_RESULT_CACHE.clear()
            state_module.CALC_RESULT_CACHE_ORDER.clear()

    def _calculator_overlay_values_for_job(job_id: str | None) -> dict[str, dict[str, Any]]:
        return state_module.core_runtime_state_helpers.calculator_overlay_values_for_job(
            state=state_module,
            job_id=job_id,
        )

    def _calculator_service_from_globals() -> Any:
        return state_module.core_runtime_state_helpers.calculator_service_from_globals(state=state_module)

    def _log_precomputed_dynasty_lookup_cache_status() -> None:
        state_module.core_runtime_state_helpers.log_precomputed_dynasty_lookup_cache_status(state=state_module)

    alias_map = {
        "_validate_runtime_configuration": _validate_runtime_configuration,
        "_extract_calculate_api_key": _extract_calculate_api_key,
        "_path_signature": _path_signature,
        "_compute_data_signature": _compute_data_signature,
        "_stable_data_version_path_label": _stable_data_version_path_label,
        "_hash_file_into": _hash_file_into,
        "_compute_content_data_version": _compute_content_data_version,
        "_current_data_version": _current_data_version,
        "_coerce_serialized_dynasty_lookup_map": _coerce_serialized_dynasty_lookup_map,
        "_dynasty_lookup_payload_version": _dynasty_lookup_payload_version,
        "_inspect_precomputed_default_dynasty_lookup": _inspect_precomputed_default_dynasty_lookup,
        "_load_precomputed_default_dynasty_lookup": _load_precomputed_default_dynasty_lookup,
        "_reload_projection_data": _reload_projection_data,
        "_parse_ip_text": _parse_ip_text,
        "_trusted_proxy_ip": _trusted_proxy_ip,
        "_forwarded_for_chain": _forwarded_for_chain,
        "_client_ip": _client_ip,
        "_calc_result_cache_key": _calc_result_cache_key,
        "_redis_client": _redis_client,
        "_get_request_rate_limit_last_sweep_ts": _get_request_rate_limit_last_sweep_ts,
        "_set_request_rate_limit_last_sweep_ts": _set_request_rate_limit_last_sweep_ts,
        "_ensure_backend_module_path": _ensure_backend_module_path,
        "_calculate_common_dynasty_frame_cached": _calculate_common_dynasty_frame_cached,
        "_stat_or_zero": _stat_or_zero,
        "_coerce_minor_eligible": _coerce_minor_eligible,
        "_projection_identity_key": _projection_identity_key,
        "_coerce_bool": _coerce_bool,
        "_roto_category_settings_from_dict": _roto_category_settings_from_dict,
        "_selected_roto_categories": _selected_roto_categories,
        "_start_year_roto_stats_by_entity": _start_year_roto_stats_by_entity,
        "_valuation_years": _valuation_years,
        "_calculate_hitter_points_breakdown": _calculate_hitter_points_breakdown,
        "_calculate_pitcher_points_breakdown": _calculate_pitcher_points_breakdown,
        "_points_player_identity": _points_player_identity,
        "_points_hitter_eligible_slots": _points_hitter_eligible_slots,
        "_points_pitcher_eligible_slots": _points_pitcher_eligible_slots,
        "_points_slot_replacement": _points_slot_replacement,
        "_calculate_points_dynasty_frame_cached": _calculate_points_dynasty_frame_cached,
        "_is_user_fixable_calculation_error": _is_user_fixable_calculation_error,
        "_numeric_or_zero": _numeric_or_zero,
        "_build_calculation_explanations": _build_calculation_explanations,
        "_clean_records_for_json": _clean_records_for_json,
        "_flatten_explanations_for_export": _flatten_explanations_for_export,
        "_default_calculator_export_columns": _default_calculator_export_columns,
        "_tabular_export_response": _tabular_export_response,
        "_playable_pool_counts_by_year": _playable_pool_counts_by_year,
        "_default_calculation_cache_params": _default_calculation_cache_params,
        "_default_dynasty_methodology_fingerprint": _default_dynasty_methodology_fingerprint,
        "_calculator_guardrails_payload": _calculator_guardrails_payload,
        "_iso_now": _iso_now,
        "_mark_job_cancelled_locked": _mark_job_cancelled_locked,
        "_cleanup_calculation_jobs": _cleanup_calculation_jobs,
        "_calculation_job_public_payload": _calculation_job_public_payload,
        "_prewarm_default_calculation_caches": _prewarm_default_calculation_caches,
        "_get_default_dynasty_lookup": _get_default_dynasty_lookup,
        "_parse_dynasty_years": _parse_dynasty_years,
        "_resolve_projection_year_filter": _resolve_projection_year_filter,
        "_attach_dynasty_values": _attach_dynasty_values,
        "_player_identity_by_name": _player_identity_by_name,
        "_refresh_data_if_needed": _refresh_data_if_needed,
        "_clear_after_data_reload": _clear_after_data_reload,
        "_calculator_overlay_values_for_job": _calculator_overlay_values_for_job,
        "_calculator_service_from_globals": _calculator_service_from_globals,
        "_log_precomputed_dynasty_lookup_cache_status": _log_precomputed_dynasty_lookup_cache_status,
    }
    validate_runtime_facade_alias_map(alias_map)
    return alias_map


def apply_runtime_facade_aliases(*, state_module: Any, alias_map: Mapping[str, Any]) -> None:
    for name, value in alias_map.items():
        setattr(state_module, name, value)
