"""
FastAPI backend for Dynasty Baseball Projections.

Endpoints:
  GET  /api/meta             → filter options (teams, years, positions)
  GET  /api/projections/all  → merged hitter+pitcher projections (filterable)
  GET  /api/projections/bat  → hitter projections (filterable)
  GET  /api/projections/pitch → pitcher projections (filterable)
  POST /api/calculate        → run dynasty value calculator with custom settings
  DELETE /api/calculate/jobs/{job_id} → cancel an async calculator job
"""

from __future__ import annotations

import ipaddress
import json
import logging
import os
import sys
import time
import traceback
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Literal

import pandas as pd
from fastapi import Request
from fastapi.responses import StreamingResponse

from backend.api.app_factory import create_app
from backend.api.dependencies import (
    build_calculator_service,
)
from backend.api.routes import (
    build_billing_router,
    build_calculate_router,
    build_frontend_assets_router,
    build_newsletter_router,
    build_projections_router,
    build_status_router,
)
from backend.core import runtime_infra as core_runtime_infra
from backend.core import runtime_state_helpers as core_runtime_state_helpers
from backend.core.calculator_helpers import (
    build_calculation_explanations as core_build_calculation_explanations,
)
from backend.core.calculator_helpers import (
    calculator_guardrails_payload as core_calculator_guardrails_payload,
)
from backend.core.calculator_helpers import (
    coerce_bool as core_coerce_bool,
)
from backend.core.calculator_helpers import (
    default_calculation_cache_params as core_default_calculation_cache_params,
)
from backend.core.calculator_helpers import (
    is_user_fixable_calculation_error as core_is_user_fixable_calculation_error,
)
from backend.core.calculator_helpers import (
    numeric_or_zero as core_numeric_or_zero,
)
from backend.core.calculator_helpers import (
    playable_pool_counts_by_year as core_playable_pool_counts_by_year,
)
from backend.core.calculator_helpers import (
    roto_category_settings_from_dict as core_roto_category_settings_from_dict,
)
from backend.core.calculator_helpers import (
    selected_roto_categories as core_selected_roto_categories,
)
from backend.core.calculator_helpers import (
    start_year_roto_stats_by_entity as core_start_year_roto_stats_by_entity,
)
from backend.core.common_calculator import calculate_common_dynasty_frame as core_calculate_common_dynasty_frame
from backend.core.data_refresh import (
    coerce_serialized_dynasty_lookup_map as core_coerce_serialized_dynasty_lookup_map,
)
from backend.core.data_refresh import (
    compute_content_data_version as core_compute_content_data_version,
)
from backend.core.data_refresh import (
    compute_data_signature as core_compute_data_signature,
)
from backend.core.data_refresh import (
    dynasty_lookup_payload_version as core_dynasty_lookup_payload_version,
)
from backend.core.data_refresh import (
    hash_file_into as core_hash_file_into,
)
from backend.core.data_refresh import (
    inspect_precomputed_default_dynasty_lookup as core_inspect_precomputed_default_dynasty_lookup,
)
from backend.core.data_refresh import (
    path_signature as core_path_signature,
)
from backend.core.data_refresh import (
    refresh_data_if_needed as core_refresh_data_if_needed,
)
from backend.core.data_refresh import (
    stable_data_version_path_label as core_stable_data_version_path_label,
)
from backend.core.dynasty_lookup_orchestration import (
    default_dynasty_lookup as core_default_dynasty_lookup,
)
from backend.core.dynasty_lookup_orchestration import (
    player_identity_by_name as core_player_identity_by_name,
)
from backend.core.export_utils import (
    clean_records_for_json as core_clean_records_for_json,
)
from backend.core.export_utils import (
    default_calculator_export_columns as core_default_calculator_export_columns,
)
from backend.core.export_utils import (
    flatten_explanations_for_export as core_flatten_explanations_for_export,
)
from backend.core.export_utils import (
    tabular_export_response as core_tabular_export_response,
)
from backend.core.jobs import (
    calculation_job_public_payload as core_calculation_job_public_payload,
)
from backend.core.jobs import (
    cleanup_calculation_jobs as core_cleanup_calculation_jobs,
)
from backend.core.jobs import (
    mark_job_cancelled_locked as core_mark_job_cancelled_locked,
)
from backend.core.league_calculator import calculate_league_dynasty_frame as core_calculate_league_dynasty_frame
from backend.core.networking import (
    client_ip as core_client_ip,
)
from backend.core.networking import (
    forwarded_for_chain as core_forwarded_for_chain,
)
from backend.core.networking import (
    parse_ip_text as core_parse_ip_text,
)
from backend.core.networking import (
    trusted_proxy_ip as core_trusted_proxy_ip,
)
from backend.core.points_calculator import (
    PointsCalculatorContext,
)
from backend.core.points_calculator import (
    calculate_hitter_points_breakdown as core_calculate_hitter_points_breakdown,
)
from backend.core.points_calculator import (
    calculate_pitcher_points_breakdown as core_calculate_pitcher_points_breakdown,
)
from backend.core.points_calculator import (
    calculate_points_dynasty_frame as core_calculate_points_dynasty_frame,
)
from backend.core.points_calculator import (
    coerce_minor_eligible as core_coerce_minor_eligible,
)
from backend.core.points_calculator import (
    points_hitter_eligible_slots as core_points_hitter_eligible_slots,
)
from backend.core.points_calculator import (
    points_pitcher_eligible_slots as core_points_pitcher_eligible_slots,
)
from backend.core.points_calculator import (
    points_player_identity as core_points_player_identity,
)
from backend.core.points_calculator import (
    points_slot_replacement as core_points_slot_replacement,
)
from backend.core.points_calculator import (
    projection_identity_key as core_projection_identity_key,
)
from backend.core.points_calculator import (
    stat_or_zero as core_stat_or_zero,
)
from backend.core.points_calculator import (
    valuation_years as core_valuation_years,
)
from backend.core.result_cache import (
    calc_result_cache_key as core_calc_result_cache_key,
)
from backend.core.runtime_bootstrap import apply_runtime_aliases, build_runtime_bootstrap
from backend.core.runtime_cache_job_helpers import (
    RuntimeCacheJobHelperConfig,
    build_runtime_cache_job_helpers,
)
from backend.core.runtime_config import (
    ALL_TAB_HITTER_STAT_COLS,
    ALL_TAB_PITCH_STAT_COLS,
    API_NO_CACHE_HEADERS,
    CALC_JOB_CANCELLED_ERROR,
    CALC_JOB_CANCELLED_STATUS,
    INDEX_BUILD_TOKEN,
    PROJECTION_QUERY_CACHE_MAXSIZE,
    PROJECTION_TEXT_SORT_COLS,
    REDIS_ACTIVE_JOBS_PREFIX,
    REDIS_JOB_CANCEL_PREFIX,
    REDIS_JOB_CLIENT_PREFIX,
    REDIS_JOB_PREFIX,
    REDIS_RATE_LIMIT_PREFIX,
    REDIS_RESULT_PREFIX,
    YEAR_RANGE_TOKEN_RE,
    build_app_build_metadata,
)
from backend.core.runtime_defaults import (
    COMMON_DEFAULT_IR_SLOTS,
    COMMON_DEFAULT_MINOR_SLOTS,
    COMMON_HITTER_SLOT_DEFAULTS,
    COMMON_HITTER_STARTER_SLOTS_PER_TEAM,
    COMMON_PITCHER_SLOT_DEFAULTS,
    COMMON_PITCHER_STARTER_SLOTS_PER_TEAM,
    DEFAULT_POINTS_SCORING,
    EXPORT_DATE_COLS,
    EXPORT_HEADER_LABEL_OVERRIDES,
    EXPORT_INTEGER_COLS,
    EXPORT_THREE_DECIMAL_COLS,
    EXPORT_TWO_DECIMAL_COLS,
    EXPORT_WHOLE_NUMBER_COLS,
    POINTS_HITTER_SLOT_DEFAULTS,
    POINTS_PITCHER_SLOT_DEFAULTS,
)
from backend.core.runtime_facade import (
    apply_runtime_facade_aliases,
    build_runtime_facade_alias_map,
)
from backend.core.runtime_projection_helpers import (
    POSITION_DISPLAY_ORDER,
    POSITION_TOKEN_SPLIT_RE,
)
from backend.core.runtime_projection_helpers import (
    as_float as _as_float,
)
from backend.core.runtime_projection_helpers import (
    average_recent_projection_rows as _average_recent_projection_rows,
)
from backend.core.runtime_projection_helpers import (
    coerce_meta_years as _coerce_meta_years,
)
from backend.core.runtime_projection_helpers import (
    coerce_numeric as _coerce_numeric,
)
from backend.core.runtime_projection_helpers import (
    coerce_record_year as _coerce_record_year,
)
from backend.core.runtime_projection_helpers import (
    merge_position_value as _merge_position_value,
)
from backend.core.runtime_projection_helpers import (
    normalize_player_key as _normalize_player_key,
)
from backend.core.runtime_projection_helpers import (
    normalize_team_key as _normalize_team_key,
)
from backend.core.runtime_projection_helpers import (
    position_tokens as _position_tokens,
)
from backend.core.runtime_projection_helpers import (
    projection_freshness_payload as _projection_freshness_payload,
)
from backend.core.runtime_projection_helpers import (
    row_team_value as _row_team_value,
)
from backend.core.runtime_projection_helpers import (
    value_col_sort_key as _value_col_sort_key,
)
from backend.core.runtime_projection_helpers import (
    with_player_identity_keys as _with_player_identity_keys,
)
from backend.core.runtime_security import (
    extract_calculate_api_key as core_extract_calculate_api_key,
)
from backend.core.runtime_security import (
    load_trusted_proxy_networks as core_load_trusted_proxy_networks,
)
from backend.core.runtime_security import (
    parse_calculate_api_key_identities as core_parse_calculate_api_key_identities,
)
from backend.core.runtime_startup import build_runtime_startup_artifacts
from backend.core.settings import load_settings_from_env
from backend.domain.constants import (
    CALCULATOR_RESULT_POINTS_EXPORT_ORDER,
    CALCULATOR_RESULT_STAT_EXPORT_ORDER,
    PLAYER_ENTITY_KEY_COL,
    PLAYER_KEY_COL,
    ROTO_CATEGORY_FIELD_DEFAULTS,
    ROTO_HITTER_CATEGORY_FIELDS,
    ROTO_PITCHER_CATEGORY_FIELDS,
)
from backend.services.calculator import CalculatorService
from backend.services.projections import (
    ProjectionDynastyHelpers,
    ProjectionRateLimits,
)
from backend.services.projections import (
    reload_projection_data as service_reload_projection_data,
)

try:  # pragma: no cover - optional dependency
    import redis as redis_lib  # type: ignore
except Exception:  # pragma: no cover - exercised only when redis is unavailable
    redis_lib = None  # type: ignore[assignment]

# These names are consumed indirectly through `state=sys.modules[__name__]` by
# runtime_state_helpers during the incremental runtime decomposition.
_RUNTIME_STATE_EXPORTS = (
    time,
    build_calculator_service,
    core_inspect_precomputed_default_dynasty_lookup,
    core_calculate_common_dynasty_frame,
    core_calculate_league_dynasty_frame,
    PointsCalculatorContext,
    core_calculate_points_dynasty_frame,
    POSITION_DISPLAY_ORDER,
    POSITION_TOKEN_SPLIT_RE,
    PROJECTION_QUERY_CACHE_MAXSIZE,
    PROJECTION_TEXT_SORT_COLS,
    ALL_TAB_HITTER_STAT_COLS,
    ALL_TAB_PITCH_STAT_COLS,
    _merge_position_value,
    _row_team_value,
)
_RUNTIME_FACADE_EXPORTS = (
    traceback,
    defaultdict,
    ThreadPoolExecutor,
    datetime,
    timezone,
    lru_cache,
    Any,
    pd,
    Request,
    StreamingResponse,
    core_runtime_state_helpers,
    core_build_calculation_explanations,
    core_calculator_guardrails_payload,
    core_coerce_bool,
    core_default_calculation_cache_params,
    core_is_user_fixable_calculation_error,
    core_numeric_or_zero,
    core_playable_pool_counts_by_year,
    core_roto_category_settings_from_dict,
    core_selected_roto_categories,
    core_start_year_roto_stats_by_entity,
    core_coerce_serialized_dynasty_lookup_map,
    core_dynasty_lookup_payload_version,
    core_hash_file_into,
    core_path_signature,
    core_refresh_data_if_needed,
    core_stable_data_version_path_label,
    core_default_dynasty_lookup,
    core_player_identity_by_name,
    core_clean_records_for_json,
    core_default_calculator_export_columns,
    core_flatten_explanations_for_export,
    core_tabular_export_response,
    core_calculation_job_public_payload,
    core_cleanup_calculation_jobs,
    core_mark_job_cancelled_locked,
    core_client_ip,
    core_forwarded_for_chain,
    core_parse_ip_text,
    core_trusted_proxy_ip,
    core_calculate_hitter_points_breakdown,
    core_calculate_pitcher_points_breakdown,
    core_coerce_minor_eligible,
    core_points_hitter_eligible_slots,
    core_points_pitcher_eligible_slots,
    core_points_player_identity,
    core_points_slot_replacement,
    core_projection_identity_key,
    core_stat_or_zero,
    core_valuation_years,
    core_calc_result_cache_key,
    CALC_JOB_CANCELLED_ERROR,
    CALC_JOB_CANCELLED_STATUS,
    COMMON_DEFAULT_IR_SLOTS,
    COMMON_DEFAULT_MINOR_SLOTS,
    COMMON_HITTER_SLOT_DEFAULTS,
    COMMON_HITTER_STARTER_SLOTS_PER_TEAM,
    COMMON_PITCHER_SLOT_DEFAULTS,
    COMMON_PITCHER_STARTER_SLOTS_PER_TEAM,
    DEFAULT_POINTS_SCORING,
    EXPORT_DATE_COLS,
    EXPORT_HEADER_LABEL_OVERRIDES,
    EXPORT_INTEGER_COLS,
    EXPORT_THREE_DECIMAL_COLS,
    EXPORT_TWO_DECIMAL_COLS,
    EXPORT_WHOLE_NUMBER_COLS,
    POINTS_HITTER_SLOT_DEFAULTS,
    POINTS_PITCHER_SLOT_DEFAULTS,
    _as_float,
    _coerce_meta_years,
    _coerce_numeric,
    _coerce_record_year,
    _normalize_team_key,
    _position_tokens,
    _value_col_sort_key,
    core_extract_calculate_api_key,
    CALCULATOR_RESULT_POINTS_EXPORT_ORDER,
    CALCULATOR_RESULT_STAT_EXPORT_ORDER,
    ROTO_CATEGORY_FIELD_DEFAULTS,
    ROTO_HITTER_CATEGORY_FIELDS,
    ROTO_PITCHER_CATEGORY_FIELDS,
    CalculatorService,
    service_reload_projection_data,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
FRONTEND_DIST_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"
EXCEL_PATH = DATA_DIR / "Dynasty Baseball Projections.xlsx"
DYNASTY_LOOKUP_CACHE_PATH = DATA_DIR / "dynasty_lookup.json"
BACKEND_MODULE_DIR = BASE_DIR / "backend"
INDEX_PATH = FRONTEND_DIST_DIR / "index.html"
DEPLOY_COMMIT_SHA = os.getenv("RAILWAY_GIT_COMMIT_SHA", "").strip()
APP_BUILD_ID, APP_BUILD_AT = build_app_build_metadata(
    index_path=INDEX_PATH,
    deploy_commit_sha=DEPLOY_COMMIT_SHA,
)

# ---------------------------------------------------------------------------
# Load pre-processed JSON data once at startup
# ---------------------------------------------------------------------------
def load_json(name: str):
    p = DATA_DIR / name
    with open(p) as f:
        return json.load(f)


EXPORT_INTERNAL_COLUMN_BLOCKLIST = {
    PLAYER_KEY_COL,
    PLAYER_ENTITY_KEY_COL,
    "DynastyMatchStatus",
    "RawDynastyValue",
    "minor_eligible",
}
SETTINGS = load_settings_from_env()
if SETTINGS.environment == "production":
    from backend.core.structured_logging import configure_structured_logging
    configure_structured_logging()
_sentry_dsn = os.getenv("SENTRY_DSN_BACKEND", "").strip()
if _sentry_dsn:
    import sentry_sdk
    sentry_sdk.init(dsn=_sentry_dsn, traces_sample_rate=0.05, environment=SETTINGS.environment)
APP_ENVIRONMENT = SETTINGS.environment
CALCULATOR_JOB_TTL_SECONDS = SETTINGS.calculator_job_ttl_seconds
CALCULATOR_JOB_MAX_ENTRIES = SETTINGS.calculator_job_max_entries
CALCULATOR_JOB_WORKERS = SETTINGS.calculator_job_workers
ENABLE_STARTUP_CALC_PREWARM = SETTINGS.enable_startup_calc_prewarm
CALCULATOR_REQUEST_TIMEOUT_SECONDS = SETTINGS.calculator_request_timeout_seconds
CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE = SETTINGS.calculator_sync_rate_limit_per_minute
CALCULATOR_SYNC_AUTH_RATE_LIMIT_PER_MINUTE = SETTINGS.calculator_sync_auth_rate_limit_per_minute
CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE = SETTINGS.calculator_job_create_rate_limit_per_minute
CALCULATOR_JOB_CREATE_AUTH_RATE_LIMIT_PER_MINUTE = SETTINGS.calculator_job_create_auth_rate_limit_per_minute
CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE = SETTINGS.calculator_job_status_rate_limit_per_minute
CALCULATOR_JOB_STATUS_AUTH_RATE_LIMIT_PER_MINUTE = SETTINGS.calculator_job_status_auth_rate_limit_per_minute
PROJECTION_RATE_LIMITS = ProjectionRateLimits(
    read_per_minute=SETTINGS.projection_rate_limit_per_minute,
    export_per_minute=SETTINGS.projection_export_rate_limit_per_minute,
)
# Backward-compatible aliases retained for tests and compatibility imports.
PROJECTION_RATE_LIMIT_PER_MINUTE = PROJECTION_RATE_LIMITS.read_per_minute
PROJECTION_EXPORT_RATE_LIMIT_PER_MINUTE = PROJECTION_RATE_LIMITS.export_per_minute
CALCULATOR_MAX_ACTIVE_JOBS_PER_IP = SETTINGS.calculator_max_active_jobs_per_ip
CALCULATOR_MAX_ACTIVE_JOBS_TOTAL = SETTINGS.calculator_max_active_jobs_total
CALC_RESULT_CACHE_TTL_SECONDS = SETTINGS.calc_result_cache_ttl_seconds
CALC_RESULT_CACHE_MAX_ENTRIES = SETTINGS.calc_result_cache_max_entries
REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP = SETTINGS.require_precomputed_dynasty_lookup
TRUST_X_FORWARDED_FOR = SETTINGS.trust_x_forwarded_for
TRUSTED_PROXY_CIDRS_RAW = SETTINGS.trusted_proxy_cidrs_raw
REDIS_URL = SETTINGS.redis_url
REQUIRE_CALCULATE_AUTH = SETTINGS.require_calculate_auth
CALCULATE_API_KEYS_RAW = SETTINGS.calculate_api_keys_raw
CANONICAL_HOST = SETTINGS.canonical_host
CORS_ALLOW_ORIGINS = SETTINGS.cors_allow_origins
CALC_LOGGER = logging.getLogger("fantasy_foundry.calculate")
RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS = SETTINGS.rate_limit_bucket_cleanup_interval_seconds

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


class PrecomputedDynastyLookupRequiredError(RuntimeError):
    """Raised when strict mode blocks runtime dynasty lookup generation."""


@dataclass(frozen=True)
class DynastyLookupCacheInspection:
    status: Literal["ready", "missing", "stale", "invalid", "disabled"]
    expected_version: str
    found_version: str | None = None
    lookup: tuple[dict[str, dict], dict[str, dict], set[str], list[str]] | None = None
    error: str | None = None


TRUSTED_PROXY_NETWORKS = core_load_trusted_proxy_networks(TRUSTED_PROXY_CIDRS_RAW, logger=CALC_LOGGER)
CALCULATE_API_KEY_IDENTITIES = core_parse_calculate_api_key_identities(CALCULATE_API_KEYS_RAW)

META = load_json("meta.json")
BAT_DATA_RAW = load_json("bat.json")
PIT_DATA_RAW = load_json("pitch.json")
BAT_DATA_RAW, PIT_DATA_RAW = _with_player_identity_keys(BAT_DATA_RAW, PIT_DATA_RAW)
BAT_DATA = _average_recent_projection_rows(BAT_DATA_RAW, is_hitter=True)
PIT_DATA = _average_recent_projection_rows(PIT_DATA_RAW, is_hitter=False)
PROJECTION_FRESHNESS = _projection_freshness_payload(BAT_DATA, PIT_DATA)
DATA_REFRESH_PATHS = (
    DATA_DIR / "meta.json",
    DATA_DIR / "bat.json",
    DATA_DIR / "pitch.json",
    EXCEL_PATH,
)
RUNTIME_STARTUP = build_runtime_startup_artifacts(
    data_refresh_paths=DATA_REFRESH_PATHS,
    compute_data_signature_fn=core_compute_data_signature,
    compute_content_data_version_fn=core_compute_content_data_version,
    calculator_job_workers=CALCULATOR_JOB_WORKERS,
    redis_client_state_factory=lambda: core_runtime_infra.RedisClientState(lock=Lock()),
)
RUNTIME_STATE = RUNTIME_STARTUP.runtime_state
DATA_REFRESH_LOCK = RUNTIME_STATE.data_refresh_lock
_DATA_SOURCE_SIGNATURE: tuple[tuple[str, int | None, int | None], ...] | None = RUNTIME_STARTUP.data_source_signature
_DATA_CONTENT_VERSION: str = RUNTIME_STARTUP.data_content_version
RUNTIME_STATE.data_source_signature = _DATA_SOURCE_SIGNATURE
RUNTIME_STATE.data_content_version = _DATA_CONTENT_VERSION
CALCULATOR_JOB_EXECUTOR = RUNTIME_STATE.calculator_job_executor
CALCULATOR_JOB_LOCK = RUNTIME_STATE.calculator_job_lock
CALCULATOR_JOBS: dict[str, dict] = RUNTIME_STATE.calculator_jobs
CALCULATOR_PREWARM_LOCK = RUNTIME_STATE.calculator_prewarm_lock
CALCULATOR_PREWARM_STATE = RUNTIME_STATE.calculator_prewarm_state
REQUEST_RATE_LIMIT_LOCK = RUNTIME_STATE.request_rate_limit_lock
REQUEST_RATE_LIMIT_BUCKETS: dict[tuple[str, str], deque[float]] = RUNTIME_STATE.request_rate_limit_buckets
_REQUEST_RATE_LIMIT_LAST_SWEEP_TS = RUNTIME_STATE.request_rate_limit_last_sweep_ts
CALC_RESULT_CACHE_LOCK = RUNTIME_STATE.calc_result_cache_lock
CALC_RESULT_CACHE: dict[str, tuple[float, dict]] = RUNTIME_STATE.calc_result_cache
CALC_RESULT_CACHE_ORDER: deque[str] = RUNTIME_STATE.calc_result_cache_order
REDIS_CLIENT_STATE = RUNTIME_STATE.redis_client_state

RUNTIME_FACADE_ALIAS_MAP = build_runtime_facade_alias_map(state_module=sys.modules[__name__])
apply_runtime_facade_aliases(
    state_module=sys.modules[__name__],
    alias_map=RUNTIME_FACADE_ALIAS_MAP,
)
# Bind facade aliases explicitly so local wiring below resolves names without
# relying on dynamic setattr side effects.
_validate_runtime_configuration = RUNTIME_FACADE_ALIAS_MAP["_validate_runtime_configuration"]
_extract_calculate_api_key = RUNTIME_FACADE_ALIAS_MAP["_extract_calculate_api_key"]
_current_data_version = RUNTIME_FACADE_ALIAS_MAP["_current_data_version"]
_get_request_rate_limit_last_sweep_ts = RUNTIME_FACADE_ALIAS_MAP["_get_request_rate_limit_last_sweep_ts"]
_set_request_rate_limit_last_sweep_ts = RUNTIME_FACADE_ALIAS_MAP["_set_request_rate_limit_last_sweep_ts"]
_client_ip = RUNTIME_FACADE_ALIAS_MAP["_client_ip"]
_redis_client = RUNTIME_FACADE_ALIAS_MAP["_redis_client"]
_calculation_job_public_payload = RUNTIME_FACADE_ALIAS_MAP["_calculation_job_public_payload"]
_get_default_dynasty_lookup = RUNTIME_FACADE_ALIAS_MAP["_get_default_dynasty_lookup"]
_refresh_data_if_needed = RUNTIME_FACADE_ALIAS_MAP["_refresh_data_if_needed"]
_prewarm_default_calculation_caches = RUNTIME_FACADE_ALIAS_MAP["_prewarm_default_calculation_caches"]
_log_precomputed_dynasty_lookup_cache_status = RUNTIME_FACADE_ALIAS_MAP[
    "_log_precomputed_dynasty_lookup_cache_status"
]


RUNTIME_CACHE_JOB_HELPERS = build_runtime_cache_job_helpers(
    RuntimeCacheJobHelperConfig(
        redis_url=REDIS_URL,
        redis_lib=redis_lib,
        redis_client_state=REDIS_CLIENT_STATE,
        logger=CALC_LOGGER,
        redis_rate_limit_prefix=REDIS_RATE_LIMIT_PREFIX,
        redis_result_prefix=REDIS_RESULT_PREFIX,
        redis_job_prefix=REDIS_JOB_PREFIX,
        redis_job_cancel_prefix=REDIS_JOB_CANCEL_PREFIX,
        redis_active_jobs_prefix=REDIS_ACTIVE_JOBS_PREFIX,
        redis_job_client_prefix=REDIS_JOB_CLIENT_PREFIX,
        calculator_job_ttl_seconds=CALCULATOR_JOB_TTL_SECONDS,
        calc_result_cache_ttl_seconds=CALC_RESULT_CACHE_TTL_SECONDS,
        request_rate_limit_lock=REQUEST_RATE_LIMIT_LOCK,
        request_rate_limit_buckets=REQUEST_RATE_LIMIT_BUCKETS,
        rate_limit_bucket_cleanup_interval_seconds=RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS,
        request_rate_limit_last_sweep_ts_getter=_get_request_rate_limit_last_sweep_ts,
        request_rate_limit_last_sweep_ts_setter=_set_request_rate_limit_last_sweep_ts,
        calc_result_cache_max_entries_getter=lambda: CALC_RESULT_CACHE_MAX_ENTRIES,
        calc_result_cache_lock=CALC_RESULT_CACHE_LOCK,
        calc_result_cache=CALC_RESULT_CACHE,
        calc_result_cache_order=CALC_RESULT_CACHE_ORDER,
        calculator_jobs=CALCULATOR_JOBS,
        calculate_api_key_identities_getter=lambda: CALCULATE_API_KEY_IDENTITIES,
        extract_calculate_api_key=_extract_calculate_api_key,
        client_ip=_client_ip,
        require_calculate_auth_getter=lambda: REQUIRE_CALCULATE_AUTH,
        calculation_job_public_payload_fn=lambda job: _calculation_job_public_payload(job),
        redis_client_getter=lambda: _redis_client(),
    )
)

_calculate_rate_limit_identity = RUNTIME_CACHE_JOB_HELPERS.calculate_rate_limit_identity
_authorize_calculate_request = RUNTIME_CACHE_JOB_HELPERS.authorize_calculate_request
_prune_rate_limit_bucket = RUNTIME_CACHE_JOB_HELPERS.prune_rate_limit_bucket
_cleanup_rate_limit_buckets_locked = RUNTIME_CACHE_JOB_HELPERS.cleanup_rate_limit_buckets_locked
_rate_limit_exceeded = RUNTIME_CACHE_JOB_HELPERS.rate_limit_exceeded
_enforce_rate_limit = RUNTIME_CACHE_JOB_HELPERS.enforce_rate_limit
_rate_limit_bucket_count = RUNTIME_CACHE_JOB_HELPERS.rate_limit_bucket_count
_rate_limit_activity_snapshot = RUNTIME_CACHE_JOB_HELPERS.rate_limit_activity_snapshot
_redis_active_jobs_key = RUNTIME_CACHE_JOB_HELPERS.redis_active_jobs_key
_redis_job_client_key = RUNTIME_CACHE_JOB_HELPERS.redis_job_client_key
_redis_job_cancel_key = RUNTIME_CACHE_JOB_HELPERS.redis_job_cancel_key
_track_active_job = RUNTIME_CACHE_JOB_HELPERS.track_active_job
_job_client_ip = RUNTIME_CACHE_JOB_HELPERS.job_client_ip
_untrack_active_job = RUNTIME_CACHE_JOB_HELPERS.untrack_active_job
_set_job_cancel_requested = RUNTIME_CACHE_JOB_HELPERS.set_job_cancel_requested
_clear_job_cancel_requested = RUNTIME_CACHE_JOB_HELPERS.clear_job_cancel_requested
_job_cancel_requested = RUNTIME_CACHE_JOB_HELPERS.job_cancel_requested
_active_jobs_for_ip = RUNTIME_CACHE_JOB_HELPERS.active_jobs_for_ip
_cleanup_local_result_cache = RUNTIME_CACHE_JOB_HELPERS.cleanup_local_result_cache
_touch_local_result_cache_key = RUNTIME_CACHE_JOB_HELPERS.touch_local_result_cache_key
_result_cache_get = RUNTIME_CACHE_JOB_HELPERS.result_cache_get
_result_cache_set = RUNTIME_CACHE_JOB_HELPERS.result_cache_set
_cache_calculation_job_snapshot = RUNTIME_CACHE_JOB_HELPERS.cache_calculation_job_snapshot
_cached_calculation_job_snapshot = RUNTIME_CACHE_JOB_HELPERS.cached_calculation_job_snapshot


PROJECTION_DYNASTY_HELPERS = ProjectionDynastyHelpers(
    year_range_token_re=YEAR_RANGE_TOKEN_RE,
    get_default_dynasty_lookup=lambda: _get_default_dynasty_lookup(),
    normalize_player_key=_normalize_player_key,
    player_key_col=PLAYER_KEY_COL,
    player_entity_key_col=PLAYER_ENTITY_KEY_COL,
    lookup_required_error_type=PrecomputedDynastyLookupRequiredError,
)


def filter_records(*args, **kwargs):
    return PROJECTION_SERVICE.filter_records(*args, **kwargs)


RUNTIME_BOOTSTRAP = build_runtime_bootstrap(state_module=sys.modules[__name__])
PROJECTION_SERVICE = RUNTIME_BOOTSTRAP.projection_service
CALCULATOR_SERVICE = RUNTIME_BOOTSTRAP.calculator_service
RUNTIME_ORCHESTRATION_HELPERS = RUNTIME_BOOTSTRAP.runtime_orchestration_helpers
RUNTIME_ENDPOINT_HANDLERS = RUNTIME_BOOTSTRAP.runtime_endpoint_handlers
apply_runtime_aliases(state_module=sys.modules[__name__], artifacts=RUNTIME_BOOTSTRAP)
# Bind dynamically applied aliases explicitly so static analyzers and route
# wiring resolve names without relying on `setattr` side effects.
CalculateRequest = RUNTIME_BOOTSTRAP.alias_map["CalculateRequest"]
CalculateExportRequest = RUNTIME_BOOTSTRAP.alias_map["CalculateExportRequest"]
get_meta = RUNTIME_BOOTSTRAP.alias_map["get_meta"]
get_version = RUNTIME_BOOTSTRAP.alias_map["get_version"]
get_health = RUNTIME_BOOTSTRAP.alias_map["get_health"]
get_ready = RUNTIME_BOOTSTRAP.alias_map["get_ready"]
get_ops = RUNTIME_BOOTSTRAP.alias_map["get_ops"]
projection_response = RUNTIME_BOOTSTRAP.alias_map["projection_response"]
export_projections = RUNTIME_BOOTSTRAP.alias_map["export_projections"]
calculate_dynasty_values = RUNTIME_BOOTSTRAP.alias_map["calculate_dynasty_values"]
export_calculate_dynasty_values = RUNTIME_BOOTSTRAP.alias_map["export_calculate_dynasty_values"]
create_calculate_dynasty_job = RUNTIME_BOOTSTRAP.alias_map["create_calculate_dynasty_job"]
get_calculate_dynasty_job = RUNTIME_BOOTSTRAP.alias_map["get_calculate_dynasty_job"]
cancel_calculate_dynasty_job = RUNTIME_BOOTSTRAP.alias_map["cancel_calculate_dynasty_job"]

_log_precomputed_dynasty_lookup_cache_status()
_validate_runtime_configuration()

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = create_app(
    title="Dynasty Baseball Projections",
    version="1.0.0",
    app_build_id=APP_BUILD_ID,
    api_no_cache_headers=API_NO_CACHE_HEADERS,
    cors_allow_origins=CORS_ALLOW_ORIGINS,
    environment=APP_ENVIRONMENT,
    refresh_data_if_needed=_refresh_data_if_needed,
    current_data_version=_current_data_version,
    client_identity_resolver=_client_ip,
    canonical_host=CANONICAL_HOST,
    enable_startup_calc_prewarm=ENABLE_STARTUP_CALC_PREWARM,
    prewarm_default_calculation_caches=_prewarm_default_calculation_caches,
    calculator_job_executor=CALCULATOR_JOB_EXECUTOR,
)

# ---------------------------------------------------------------------------
# API: Metadata
# ---------------------------------------------------------------------------
# Endpoint handler aliases are bound by runtime bootstrap so route wiring below
# can continue to reference stable module-level names.


# Route registration is centralized into dedicated route modules so app.py keeps
# request business logic while routing declarations stay focused and composable.
app.include_router(
    build_status_router(
        meta_handler=get_meta,
        version_handler=get_version,
        health_handler=get_health,
        ready_handler=get_ready,
        ops_handler=get_ops,
    )
)
app.include_router(
    build_projections_router(
        projection_response_handler=projection_response,
        projection_export_handler=export_projections,
        projection_profile_handler=RUNTIME_ENDPOINT_HANDLERS.projection_profile,
        projection_compare_handler=RUNTIME_ENDPOINT_HANDLERS.projection_compare,
    )
)
app.include_router(
    build_calculate_router(
        calculate_request_model=CalculateRequest,
        calculate_export_request_model=CalculateExportRequest,
        calculate_handler=calculate_dynasty_values,
        calculate_export_handler=export_calculate_dynasty_values,
        calculate_job_create_handler=create_calculate_dynasty_job,
        calculate_job_read_handler=get_calculate_dynasty_job,
        calculate_job_cancel_handler=cancel_calculate_dynasty_job,
        calculate_authorize_handler=_authorize_calculate_request,
    )
)

# ---------------------------------------------------------------------------
# Billing (Stripe) — conditional on credentials
# ---------------------------------------------------------------------------
if SETTINGS.stripe_secret_key and SETTINGS.stripe_webhook_secret:
    import stripe

    from backend.services.billing import (
        get_subscription_status as _billing_get_status,
    )
    from backend.services.billing import (
        resolve_supabase_user_id as _billing_resolve_user_id,
    )
    from backend.services.billing import (
        revoke_subscription as _billing_revoke,
    )
    from backend.services.billing import (
        upsert_subscription as _billing_upsert,
    )

    stripe.api_key = SETTINGS.stripe_secret_key
    _supabase_url = SETTINGS.supabase_url
    _supabase_service_role_key = SETTINGS.supabase_service_role_key

    async def _on_checkout_completed(session):
        email = str(session.get("customer_email", "")).strip()
        sub_id = str(session.get("subscription", "")).strip()
        period_end = None
        if sub_id:
            try:
                sub_obj = stripe.Subscription.retrieve(sub_id)
                period_end = sub_obj.get("current_period_end")
            except Exception:
                logging.getLogger(__name__).warning("Could not retrieve subscription %s for period_end", sub_id, exc_info=True)
        user_id = await _billing_resolve_user_id(
            supabase_url=_supabase_url,
            supabase_service_role_key=_supabase_service_role_key,
            email=email,
        )
        await _billing_upsert(
            supabase_url=_supabase_url,
            supabase_service_role_key=_supabase_service_role_key,
            user_email=email,
            stripe_customer_id=str(session.get("customer", "")).strip(),
            stripe_subscription_id=sub_id,
            status="active",
            user_id=user_id,
            current_period_end=period_end,
        )

    async def _on_subscription_updated(subscription):
        customer_id = str(subscription.get("customer", "")).strip()
        customer_email = str(subscription.get("metadata", {}).get("email", "")).strip()
        if not customer_email and customer_id:
            try:
                customer = stripe.Customer.retrieve(customer_id)
                customer_email = str(getattr(customer, "email", "") or "").strip()
            except Exception:
                logging.getLogger(__name__).warning("Could not retrieve customer email for %s", customer_id)
        user_id = await _billing_resolve_user_id(
            supabase_url=_supabase_url,
            supabase_service_role_key=_supabase_service_role_key,
            email=customer_email,
        )
        await _billing_upsert(
            supabase_url=_supabase_url,
            supabase_service_role_key=_supabase_service_role_key,
            user_email=customer_email,
            stripe_customer_id=customer_id,
            stripe_subscription_id=str(subscription.get("id", "")).strip(),
            status=str(subscription.get("status", "")).strip(),
            user_id=user_id,
            current_period_end=subscription.get("current_period_end"),
        )

    async def _on_subscription_deleted(subscription):
        await _billing_revoke(
            supabase_url=_supabase_url,
            supabase_service_role_key=_supabase_service_role_key,
            stripe_subscription_id=str(subscription.get("id", "")).strip(),
        )

    async def _get_billing_status(email):
        return await _billing_get_status(
            supabase_url=_supabase_url,
            supabase_service_role_key=_supabase_service_role_key,
            user_email=email,
        )

    app.include_router(
        build_billing_router(
            stripe_secret_key=SETTINGS.stripe_secret_key,
            stripe_webhook_secret=SETTINGS.stripe_webhook_secret,
            stripe_monthly_price_id=SETTINGS.stripe_monthly_price_id,
            stripe_annual_price_id=SETTINGS.stripe_annual_price_id,
            on_checkout_completed=_on_checkout_completed,
            on_subscription_updated=_on_subscription_updated,
            on_subscription_deleted=_on_subscription_deleted,
            get_subscription_status=_get_billing_status,
        )
    )

# ---------------------------------------------------------------------------
# Newsletter (Buttondown) — conditional on API key
# ---------------------------------------------------------------------------
if SETTINGS.buttondown_api_key:
    app.include_router(
        build_newsletter_router(
            buttondown_api_key=SETTINGS.buttondown_api_key,
            enforce_rate_limit=_enforce_rate_limit,
            rate_limit_per_minute=10,
            client_ip_resolver=_client_ip,
        )
    )


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------
def _get_unique_player_entity_keys() -> list[str]:
    """Return deduplicated player entity keys from BAT_DATA + PIT_DATA for sitemap."""
    seen: set[str] = set()
    keys: list[str] = []
    for row in BAT_DATA + PIT_DATA:
        key = str(row.get("PlayerEntityKey", "")).strip()
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys

if FRONTEND_DIR.exists():
    app.include_router(
        build_frontend_assets_router(
            index_path=INDEX_PATH,
            assets_root=FRONTEND_DIST_ASSETS_DIR,
            app_build_id=APP_BUILD_ID,
            index_build_token=INDEX_BUILD_TOKEN,
            player_keys_getter=_get_unique_player_entity_keys,
        )
    )
