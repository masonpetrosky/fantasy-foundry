"""State-driven helper implementations extracted from backend.runtime."""

from __future__ import annotations

from typing import Any

import pandas as pd

from backend.core.runtime_state_protocols import RuntimeStateHelpersState


def validate_runtime_configuration(*, state: RuntimeStateHelpersState) -> None:
    if state.APP_ENVIRONMENT != "production":
        return

    errors: list[str] = []
    if "*" in set(state.CORS_ALLOW_ORIGINS):
        errors.append("FF_CORS_ALLOW_ORIGINS must not contain '*' when FF_ENV=production.")
    if state.TRUST_X_FORWARDED_FOR and not state.TRUSTED_PROXY_NETWORKS:
        errors.append(
            "FF_TRUST_X_FORWARDED_FOR=1 requires explicit FF_TRUSTED_PROXY_CIDRS when FF_ENV=production."
        )
    if state.REQUIRE_CALCULATE_AUTH and not state.CALCULATE_API_KEY_IDENTITIES:
        errors.append(
            "FF_REQUIRE_CALCULATE_AUTH=1 requires FF_CALCULATE_API_KEYS to be configured when FF_ENV=production."
        )

    if errors:
        raise RuntimeError("Invalid production runtime configuration:\n- " + "\n- ".join(errors))


def inspect_precomputed_default_dynasty_lookup(*, state: RuntimeStateHelpersState) -> Any:
    pytest_current_test = bool(state.os.getenv("PYTEST_CURRENT_TEST"))
    e2e_enabled = str(state.os.getenv("FF_RUN_E2E", "")).strip().lower() in {"1", "true", "yes", "on"}
    inspection = state.core_inspect_precomputed_default_dynasty_lookup(
        current_data_version=state._current_data_version(),
        current_methodology_fingerprint=state._default_dynasty_methodology_fingerprint(),
        dynasty_lookup_cache_path=state.DYNASTY_LOOKUP_CACHE_PATH,
        pytest_current_test=pytest_current_test and not e2e_enabled,
        value_col_sort_key=state._value_col_sort_key,
    )
    return state.DynastyLookupCacheInspection(
        status=inspection.status,
        expected_version=inspection.expected_version,
        found_version=inspection.found_version,
        expected_methodology_fingerprint=inspection.expected_methodology_fingerprint,
        found_methodology_fingerprint=inspection.found_methodology_fingerprint,
        lookup=inspection.lookup,
        error=inspection.error,
    )


def load_precomputed_default_dynasty_lookup(
    *,
    state: RuntimeStateHelpersState,
) -> tuple[dict[str, dict], dict[str, dict], set[str], list[str]] | None:
    inspection = state._inspect_precomputed_default_dynasty_lookup()
    if inspection.status == "ready" and inspection.lookup is not None:
        return inspection.lookup
    if inspection.status == "invalid" and inspection.error:
        state.CALC_LOGGER.warning(inspection.error)
    return None


def calculate_common_dynasty_frame_cached(
    *,
    state: RuntimeStateHelpersState,
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
    roto_category_settings: dict[str, bool],
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
) -> pd.DataFrame:
    return state.core_calculate_common_dynasty_frame(
        ensure_backend_module_path_fn=state._ensure_backend_module_path,
        excel_path=state.EXCEL_PATH,
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
        roto_hitter_fields=state.ROTO_HITTER_CATEGORY_FIELDS,
        roto_pitcher_fields=state.ROTO_PITCHER_CATEGORY_FIELDS,
        coerce_bool_fn=state._coerce_bool,
    )


def calculate_points_dynasty_frame_cached(
    *,
    state: RuntimeStateHelpersState,
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
    return state.core_calculate_points_dynasty_frame(
        ctx=state.PointsCalculatorContext(
            bat_data=state.BAT_DATA,
            pit_data=state.PIT_DATA,
            bat_data_raw=state.BAT_DATA_RAW,
            pit_data_raw=state.PIT_DATA_RAW,
            meta=state.META,
            average_recent_projection_rows=state._average_recent_projection_rows,
            coerce_meta_years=state._coerce_meta_years,
            valuation_years=state._valuation_years,
            coerce_record_year=state._coerce_record_year,
            points_player_identity=state._points_player_identity,
            normalize_player_key=state._normalize_player_key,
            player_key_col=state.PLAYER_KEY_COL,
            player_entity_key_col=state.PLAYER_ENTITY_KEY_COL,
            row_team_value=state._row_team_value,
            merge_position_value=state._merge_position_value,
            coerce_minor_eligible=state._coerce_minor_eligible,
            calculate_hitter_points_breakdown=state._calculate_hitter_points_breakdown,
            calculate_pitcher_points_breakdown=state._calculate_pitcher_points_breakdown,
            stat_or_zero=state._stat_or_zero,
            points_hitter_eligible_slots=state._points_hitter_eligible_slots,
            points_pitcher_eligible_slots=state._points_pitcher_eligible_slots,
            points_slot_replacement=state._points_slot_replacement,
        ),
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


def _prewarm_roto_config(*, state: RuntimeStateHelpersState, params: dict) -> None:
    """Prewarm a single roto calculator configuration."""
    ip_max = params["ip_max"]
    state._calculate_common_dynasty_frame_cached(
        teams=int(params["teams"]),
        sims=int(params["sims"]),
        horizon=int(params["horizon"]),
        discount=float(params["discount"]),
        hit_c=int(params["hit_c"]),
        hit_1b=int(params["hit_1b"]),
        hit_2b=int(params["hit_2b"]),
        hit_3b=int(params["hit_3b"]),
        hit_ss=int(params["hit_ss"]),
        hit_ci=int(params["hit_ci"]),
        hit_mi=int(params["hit_mi"]),
        hit_of=int(params["hit_of"]),
        hit_dh=int(params.get("hit_dh", 0)),
        hit_ut=int(params["hit_ut"]),
        pit_p=int(params["pit_p"]),
        pit_sp=int(params["pit_sp"]),
        pit_rp=int(params["pit_rp"]),
        bench=int(params["bench"]),
        minors=int(params["minors"]),
        ir=int(params["ir"]),
        ip_min=float(params["ip_min"]),
        ip_max=float(ip_max) if ip_max is not None else None,
        two_way=str(params["two_way"]),
        start_year=int(params["start_year"]),
        sgp_denominator_mode=str(params.get("sgp_denominator_mode", "classic")),
        sgp_winsor_low_pct=float(params.get("sgp_winsor_low_pct", 0.10)),
        sgp_winsor_high_pct=float(params.get("sgp_winsor_high_pct", 0.90)),
        sgp_epsilon_counting=float(params.get("sgp_epsilon_counting", 0.15)),
        sgp_epsilon_ratio=float(params.get("sgp_epsilon_ratio", 0.0015)),
        enable_playing_time_reliability=bool(params.get("enable_playing_time_reliability", False)),
        enable_age_risk_adjustment=bool(params.get("enable_age_risk_adjustment", False)),
        enable_prospect_risk_adjustment=bool(params.get("enable_prospect_risk_adjustment", True)),
        enable_bench_stash_relief=bool(params.get("enable_bench_stash_relief", False)),
        bench_negative_penalty=float(params.get("bench_negative_penalty", 0.55)),
        enable_ir_stash_relief=bool(params.get("enable_ir_stash_relief", False)),
        ir_negative_penalty=float(params.get("ir_negative_penalty", 0.20)),
        enable_replacement_blend=bool(params.get("enable_replacement_blend", True)),
        replacement_blend_alpha=float(params.get("replacement_blend_alpha", 0.40)),
        replacement_depth_mode=str(params.get("replacement_depth_mode", "blended_depth")),
        replacement_depth_blend_alpha=float(params.get("replacement_depth_blend_alpha", 0.33)),
        **state._roto_category_settings_from_dict(params),
    )


def _prewarm_points_config(*, state: RuntimeStateHelpersState, params: dict) -> None:
    """Prewarm a single points calculator configuration."""
    pts = state.DEFAULT_POINTS_SCORING
    state._calculate_points_dynasty_frame_cached(
        teams=int(params["teams"]),
        horizon=int(params["horizon"]),
        discount=float(params["discount"]),
        hit_c=int(params["hit_c"]),
        hit_1b=int(params["hit_1b"]),
        hit_2b=int(params["hit_2b"]),
        hit_3b=int(params["hit_3b"]),
        hit_ss=int(params["hit_ss"]),
        hit_ci=int(params["hit_ci"]),
        hit_mi=int(params["hit_mi"]),
        hit_of=int(params["hit_of"]),
        hit_dh=int(params.get("hit_dh", 0)),
        hit_ut=int(params["hit_ut"]),
        pit_p=int(params["pit_p"]),
        pit_sp=int(params["pit_sp"]),
        pit_rp=int(params["pit_rp"]),
        bench=int(params["bench"]),
        minors=int(params["minors"]),
        ir=int(params["ir"]),
        keeper_limit=params.get("keeper_limit"),
        two_way=str(params["two_way"]),
        points_valuation_mode=str(params.get("points_valuation_mode", "season_total")),
        weekly_starts_cap=params.get("weekly_starts_cap"),
        allow_same_day_starts_overflow=bool(params.get("allow_same_day_starts_overflow", False)),
        weekly_acquisition_cap=params.get("weekly_acquisition_cap"),
        start_year=int(params["start_year"]),
        **pts,
    )


def prewarm_default_calculation_caches(*, state: RuntimeStateHelpersState) -> None:
    from backend.core.calculator_helpers import PREWARM_CONFIGS

    with state.CALCULATOR_PREWARM_LOCK:
        state.CALCULATOR_PREWARM_STATE.update(
            {
                "status": "running",
                "started_at": state._iso_now(),
                "completed_at": None,
                "duration_ms": None,
                "error": None,
                "configs_total": 0,
                "configs_completed": 0,
            }
        )

    started = state.time.perf_counter()
    try:
        state._refresh_data_if_needed()
        base_params = state._default_calculation_cache_params()

        max_configs = min(state.PREWARM_CONFIG_COUNT, len(PREWARM_CONFIGS))
        configs_to_run = PREWARM_CONFIGS[:max_configs]

        with state.CALCULATOR_PREWARM_LOCK:
            state.CALCULATOR_PREWARM_STATE["configs_total"] = len(configs_to_run)

        for i, config in enumerate(configs_to_run):
            label = config.get("label", f"config-{i}")
            mode = config.get("mode", "roto")
            params = {**base_params}
            for k, v in config.items():
                if k not in ("label", "mode"):
                    params[k] = v

            state.CALC_LOGGER.info("prewarm [%d/%d] %s", i + 1, len(configs_to_run), label)
            if mode == "points":
                _prewarm_points_config(state=state, params=params)
            else:
                _prewarm_roto_config(state=state, params=params)

            with state.CALCULATOR_PREWARM_LOCK:
                state.CALCULATOR_PREWARM_STATE["configs_completed"] = i + 1

        # Also prewarm the default dynasty lookup
        state._get_default_dynasty_lookup()

        duration_ms = round((state.time.perf_counter() - started) * 1000.0, 1)
        with state.CALCULATOR_PREWARM_LOCK:
            state.CALCULATOR_PREWARM_STATE.update(
                {
                    "status": "ready",
                    "completed_at": state._iso_now(),
                    "duration_ms": duration_ms,
                    "error": None,
                }
            )
        state.CALC_LOGGER.info("calculator prewarm completed duration_ms=%s configs=%d", duration_ms, len(configs_to_run))
    except Exception as exc:  # noqa: BLE001 — prewarm is best-effort background task
        duration_ms = round((state.time.perf_counter() - started) * 1000.0, 1)
        with state.CALCULATOR_PREWARM_LOCK:
            state.CALCULATOR_PREWARM_STATE.update(
                {
                    "status": "failed",
                    "completed_at": state._iso_now(),
                    "duration_ms": duration_ms,
                    "error": str(exc),
                }
            )
        state.CALC_LOGGER.exception("calculator prewarm failed")


def calculator_overlay_values_for_job(
    *,
    state: RuntimeStateHelpersState,
    job_id: str | None,
) -> dict[str, dict[str, Any]]:
    normalized_job_id = str(job_id or "").strip()
    if not normalized_job_id:
        return {}

    with state.CALCULATOR_JOB_LOCK:
        live_job = state.CALCULATOR_JOBS.get(normalized_job_id)
    job_payload = live_job if isinstance(live_job, dict) else state._cached_calculation_job_snapshot(normalized_job_id)
    if not isinstance(job_payload, dict):
        return {}
    if str(job_payload.get("status") or "").lower() != "completed":
        return {}

    result = job_payload.get("result")
    rows = result.get("data") if isinstance(result, dict) else None
    if not isinstance(rows, list):
        return {}

    overlay_by_player_key: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue

        overlay: dict[str, Any] = {}
        dynasty_value = row.get("DynastyValue")
        if dynasty_value is not None and dynasty_value != "":
            overlay["DynastyValue"] = dynasty_value
        for col, value in row.items():
            if not str(col).startswith("Value_"):
                continue
            if value is None or value == "":
                continue
            overlay[str(col)] = value
        if not overlay:
            continue

        entity_key = str(row.get(state.PLAYER_ENTITY_KEY_COL) or "").strip().lower()
        player_key = str(row.get(state.PLAYER_KEY_COL) or "").strip().lower()
        if entity_key:
            overlay_by_player_key[entity_key] = overlay
        elif player_key:
            overlay_by_player_key[player_key] = overlay

    return overlay_by_player_key


def calculator_service_from_globals(*, state: RuntimeStateHelpersState) -> Any:
    return state.build_calculator_service(
        refresh_data_if_needed=state._refresh_data_if_needed,
        coerce_meta_years=state._coerce_meta_years,
        get_meta=lambda: state.META,
        calc_result_cache_key=state._calc_result_cache_key,
        result_cache_get=state._result_cache_get,
        result_cache_set=state._result_cache_set,
        calculate_common_dynasty_frame_cached=state._calculate_common_dynasty_frame_cached,
        calculate_points_dynasty_frame_cached=state._calculate_points_dynasty_frame_cached,
        roto_category_settings_from_dict=state._roto_category_settings_from_dict,
        is_user_fixable_calculation_error=state._is_user_fixable_calculation_error,
        player_identity_by_name=state._player_identity_by_name,
        normalize_player_key=state._normalize_player_key,
        player_key_col=state.PLAYER_KEY_COL,
        player_entity_key_col=state.PLAYER_ENTITY_KEY_COL,
        selected_roto_categories=state._selected_roto_categories,
        start_year_roto_stats_by_entity=state._start_year_roto_stats_by_entity,
        projection_identity_key=state._projection_identity_key,
        build_calculation_explanations=state._build_calculation_explanations,
        clean_records_for_json=state._clean_records_for_json,
        flatten_explanations_for_export=state._flatten_explanations_for_export,
        tabular_export_response=state._tabular_export_response,
        calc_logger=state.CALC_LOGGER,
        enforce_rate_limit=state._enforce_rate_limit,
        sync_rate_limit_per_minute=state.CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE,
        sync_auth_rate_limit_per_minute=state.CALCULATOR_SYNC_AUTH_RATE_LIMIT_PER_MINUTE,
        job_create_rate_limit_per_minute=state.CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE,
        job_create_auth_rate_limit_per_minute=state.CALCULATOR_JOB_CREATE_AUTH_RATE_LIMIT_PER_MINUTE,
        job_status_rate_limit_per_minute=state.CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE,
        job_status_auth_rate_limit_per_minute=state.CALCULATOR_JOB_STATUS_AUTH_RATE_LIMIT_PER_MINUTE,
        client_ip=state._client_ip,
        iso_now=state._iso_now,
        active_jobs_for_ip=state._active_jobs_for_ip,
        calculator_max_active_jobs_per_ip=state.CALCULATOR_MAX_ACTIVE_JOBS_PER_IP,
        calculator_max_active_jobs_total=state.CALCULATOR_MAX_ACTIVE_JOBS_TOTAL,
        calculator_job_lock=state.CALCULATOR_JOB_LOCK,
        calculator_jobs=state.CALCULATOR_JOBS,
        cleanup_calculation_jobs=state._cleanup_calculation_jobs,
        cache_calculation_job_snapshot=state._cache_calculation_job_snapshot,
        cached_calculation_job_snapshot=state._cached_calculation_job_snapshot,
        calculation_job_public_payload=state._calculation_job_public_payload,
        mark_job_cancelled_locked=state._mark_job_cancelled_locked,
        calculator_job_executor=state.CALCULATOR_JOB_EXECUTOR,
        calc_job_cancelled_status=state.CALC_JOB_CANCELLED_STATUS,
    )


def log_precomputed_dynasty_lookup_cache_status(*, state: RuntimeStateHelpersState) -> None:
    inspection = state._inspect_precomputed_default_dynasty_lookup()
    state.CALC_LOGGER.info(
        "dynasty lookup cache status=%s require_precomputed=%s expected=%s found=%s methodology_expected=%s methodology_found=%s",
        inspection.status,
        state.REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP,
        inspection.expected_version,
        inspection.found_version or "missing",
        inspection.expected_methodology_fingerprint or "n/a",
        inspection.found_methodology_fingerprint or "missing",
    )
    if inspection.error:
        state.CALC_LOGGER.warning("dynasty lookup cache error: %s", inspection.error)
