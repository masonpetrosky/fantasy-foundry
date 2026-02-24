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

import logging
import json
import ipaddress
import os
import re
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
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse

from backend.api.dependencies import (
    build_calculator_service,
)
from backend.api.app_factory import create_app
from backend.api.routes import (
    build_calculate_router,
    build_frontend_assets_router,
    build_projections_router,
    build_status_router,
)
from backend.core.jobs import (
    calculation_job_public_payload as core_calculation_job_public_payload,
    cleanup_calculation_jobs as core_cleanup_calculation_jobs,
    mark_job_cancelled_locked as core_mark_job_cancelled_locked,
)
from backend.core.data_refresh import (
    LookupInspectionResult,
    coerce_serialized_dynasty_lookup_map as core_coerce_serialized_dynasty_lookup_map,
    compute_content_data_version as core_compute_content_data_version,
    compute_data_signature as core_compute_data_signature,
    dynasty_lookup_payload_version as core_dynasty_lookup_payload_version,
    hash_file_into as core_hash_file_into,
    inspect_precomputed_default_dynasty_lookup as core_inspect_precomputed_default_dynasty_lookup,
    path_signature as core_path_signature,
    refresh_data_if_needed as core_refresh_data_if_needed,
    reload_projection_data as core_reload_projection_data,
    stable_data_version_path_label as core_stable_data_version_path_label,
)
from backend.core.dynasty_lookup_orchestration import (
    attach_dynasty_values as core_attach_dynasty_values,
    default_dynasty_lookup as core_default_dynasty_lookup,
    parse_dynasty_years as core_parse_dynasty_years,
    player_identity_by_name as core_player_identity_by_name,
    resolve_projection_year_filter as core_resolve_projection_year_filter,
)
from backend.core.export_utils import (
    clean_records_for_json as core_clean_records_for_json,
    default_calculator_export_columns as core_default_calculator_export_columns,
    flatten_explanations_for_export as core_flatten_explanations_for_export,
    tabular_export_response as core_tabular_export_response,
)
from backend.core.calculator_helpers import (
    build_calculation_explanations as core_build_calculation_explanations,
    calculator_guardrails_payload as core_calculator_guardrails_payload,
    coerce_bool as core_coerce_bool,
    default_calculation_cache_params as core_default_calculation_cache_params,
    is_user_fixable_calculation_error as core_is_user_fixable_calculation_error,
    numeric_or_zero as core_numeric_or_zero,
    playable_pool_counts_by_year as core_playable_pool_counts_by_year,
    roto_category_settings_from_dict as core_roto_category_settings_from_dict,
    selected_roto_categories as core_selected_roto_categories,
    start_year_roto_stats_by_entity as core_start_year_roto_stats_by_entity,
)
from backend.core.common_calculator import calculate_common_dynasty_frame as core_calculate_common_dynasty_frame
from backend.core.points_calculator import (
    PointsCalculatorContext,
    calculate_hitter_points_breakdown as core_calculate_hitter_points_breakdown,
    calculate_pitcher_points_breakdown as core_calculate_pitcher_points_breakdown,
    calculate_points_dynasty_frame as core_calculate_points_dynasty_frame,
    coerce_minor_eligible as core_coerce_minor_eligible,
    points_hitter_eligible_slots as core_points_hitter_eligible_slots,
    points_pitcher_eligible_slots as core_points_pitcher_eligible_slots,
    points_player_identity as core_points_player_identity,
    points_slot_replacement as core_points_slot_replacement,
    projection_identity_key as core_projection_identity_key,
    stat_or_zero as core_stat_or_zero,
    valuation_years as core_valuation_years,
)
from backend.core.runtime_projection_helpers import (
    POSITION_DISPLAY_ORDER,
    POSITION_TOKEN_SPLIT_RE,
    as_float as _as_float,
    average_recent_projection_rows as _average_recent_projection_rows,
    coerce_meta_years as _coerce_meta_years,
    coerce_numeric as _coerce_numeric,
    coerce_record_year as _coerce_record_year,
    merge_position_value as _merge_position_value,
    normalize_player_key as _normalize_player_key,
    normalize_team_key as _normalize_team_key,
    position_tokens as _position_tokens,
    projection_freshness_payload as _projection_freshness_payload,
    row_team_value as _row_team_value,
    value_col_sort_key as _value_col_sort_key,
    with_player_identity_keys as _with_player_identity_keys,
)
from backend.core.runtime_cache_job_helpers import (
    RuntimeCacheJobHelperConfig,
    build_runtime_cache_job_helpers,
)
from backend.core.runtime_endpoint_handlers import (
    RuntimeEndpointHandlerConfig,
    build_runtime_endpoint_handlers,
)
from backend.core.runtime_orchestration_helpers import build_runtime_orchestration_helpers
from backend.core.networking import (
    client_ip as core_client_ip,
    forwarded_for_chain as core_forwarded_for_chain,
    parse_ip_text as core_parse_ip_text,
    trusted_proxy_ip as core_trusted_proxy_ip,
)
from backend.core.runtime_security import (
    extract_calculate_api_key as core_extract_calculate_api_key,
    load_trusted_proxy_networks as core_load_trusted_proxy_networks,
    parse_calculate_api_key_identities as core_parse_calculate_api_key_identities,
)
from backend.core import runtime_infra as core_runtime_infra
from backend.core.result_cache import (
    calc_result_cache_key as core_calc_result_cache_key,
)
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
from backend.services.projections import ProjectionService, ProjectionServiceContext

try:  # pragma: no cover - optional dependency
    import redis as redis_lib  # type: ignore
except Exception:  # pragma: no cover - exercised only when redis is unavailable
    redis_lib = None  # type: ignore[assignment]

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


def _build_id() -> str:
    if DEPLOY_COMMIT_SHA:
        return DEPLOY_COMMIT_SHA[:12]
    try:
        return str(INDEX_PATH.stat().st_mtime_ns)
    except OSError:
        return "unknown"


def _build_timestamp_iso() -> str | None:
    try:
        ts = INDEX_PATH.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


APP_BUILD_ID = _build_id()
APP_BUILD_AT = _build_timestamp_iso()
INDEX_BUILD_TOKEN = "__APP_BUILD_ID__"
API_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

# ---------------------------------------------------------------------------
# Load pre-processed JSON data once at startup
# ---------------------------------------------------------------------------
def load_json(name: str):
    p = DATA_DIR / name
    with open(p) as f:
        return json.load(f)


YEAR_RANGE_TOKEN_RE = re.compile(r"^(\d{4})\s*-\s*(\d{4})$")
PROJECTION_QUERY_CACHE_MAXSIZE = 256
ALL_TAB_HITTER_STAT_COLS = ("G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "BB", "SO", "AVG", "OBP", "OPS")
ALL_TAB_PITCH_STAT_COLS = ("GS", "IP", "W", "QS", "QA3", "L", "K", "SV", "SVH", "ERA", "WHIP", "ER")
PROJECTION_TEXT_SORT_COLS = {"Player", "Team", "Pos", "Type", "Years"}
EXPORT_INTERNAL_COLUMN_BLOCKLIST = {
    PLAYER_KEY_COL,
    PLAYER_ENTITY_KEY_COL,
    "DynastyMatchStatus",
    "RawDynastyValue",
    "minor_eligible",
}
EXPORT_HEADER_LABEL_OVERRIDES = {
    "Type": "Side",
    "ProjectionsUsed": "Proj Count",
    "OldestProjectionDate": "Oldest Proj Date",
    "DynastyValue": "Dynasty Value",
    "RawDynastyValue": "Raw Dynasty Value",
    "YearValue": "Year Value",
    "DiscountFactor": "Discount Factor",
    "DiscountedContribution": "Discounted Contribution",
    "HittingPoints": "Hitting Points",
    "PitchingPoints": "Pitching Points",
    "SelectedPoints": "Selected Points",
    "SelectedSide": "Selected Side",
    "HittingBestSlot": "Hitting Best Slot",
    "PitchingBestSlot": "Pitching Best Slot",
    "HittingValue": "Hitting Value",
    "PitchingValue": "Pitching Value",
    "HittingAssignmentSlot": "Hitting Assignment Slot",
    "PitchingAssignmentSlot": "Pitching Assignment Slot",
    "HittingAssignmentValue": "Hitting Assignment Value",
    "PitchingAssignmentValue": "Pitching Assignment Value",
    "HittingAssignmentReplacement": "Hitting Assignment Replacement",
    "PitchingAssignmentReplacement": "Pitching Assignment Replacement",
    "KeepDropValue": "Keep/Drop Value",
    "KeepDropHoldValue": "Keep/Drop Hold Value",
    "KeepDropKeep": "Keep/Drop Keep",
    "HittingRulePoints": "Hitting Rule Points",
    "PitchingRulePoints": "Pitching Rule Points",
    "Years": "Years",
    "PitH": "P H",
    "PitHR": "P HR",
    "PitBB": "P BB",
}
EXPORT_THREE_DECIMAL_COLS = {"AVG", "OBP", "SLG", "OPS"}
EXPORT_TWO_DECIMAL_COLS = {
    "DynastyValue",
    "RawDynastyValue",
    "YearValue",
    "DiscountFactor",
    "DiscountedContribution",
    "HittingPoints",
    "PitchingPoints",
    "SelectedPoints",
    "HittingValue",
    "PitchingValue",
    "HittingAssignmentValue",
    "PitchingAssignmentValue",
    "HittingAssignmentReplacement",
    "PitchingAssignmentReplacement",
    "KeepDropValue",
    "KeepDropHoldValue",
    "ERA",
    "WHIP",
}
EXPORT_WHOLE_NUMBER_COLS = {
    "AB",
    "R",
    "HR",
    "RBI",
    "SB",
    "IP",
    "W",
    "K",
    "SVH",
    "QS",
    "QA3",
    "G",
    "H",
    "2B",
    "3B",
    "BB",
    "SO",
    "GS",
    "L",
    "PitBB",
    "SV",
    "PitH",
    "PitHR",
    "ER",
    "TB",
}
EXPORT_INTEGER_COLS = {"Rank", "Year", "Age", "ProjectionsUsed"}
EXPORT_DATE_COLS = {"OldestProjectionDate"}
COMMON_HITTER_SLOT_DEFAULTS = {
    "C": 1,
    "1B": 1,
    "2B": 1,
    "3B": 1,
    "SS": 1,
    "CI": 1,
    "MI": 1,
    "OF": 5,
    "UT": 1,
}
COMMON_PITCHER_SLOT_DEFAULTS = {
    "P": 9,
    "SP": 0,
    "RP": 0,
}
POINTS_HITTER_SLOT_DEFAULTS = {
    "C": 1,
    "1B": 1,
    "2B": 1,
    "3B": 1,
    "SS": 1,
    "CI": 0,
    "MI": 0,
    "OF": 3,
    "UT": 1,
}
POINTS_PITCHER_SLOT_DEFAULTS = {
    "P": 2,
    "SP": 5,
    "RP": 2,
}
DEFAULT_POINTS_SCORING = {
    "pts_hit_1b": 1.0,
    "pts_hit_2b": 2.0,
    "pts_hit_3b": 3.0,
    "pts_hit_hr": 4.0,
    "pts_hit_r": 1.0,
    "pts_hit_rbi": 1.0,
    "pts_hit_sb": 1.0,
    "pts_hit_bb": 1.0,
    "pts_hit_so": -1.0,
    "pts_pit_ip": 3.0,
    "pts_pit_w": 5.0,
    "pts_pit_l": -5.0,
    "pts_pit_k": 1.0,
    "pts_pit_sv": 5.0,
    "pts_pit_svh": 0.0,
    "pts_pit_h": -1.0,
    "pts_pit_er": -2.0,
    "pts_pit_bb": -1.0,
}
COMMON_DEFAULT_IR_SLOTS = 0
COMMON_DEFAULT_MINOR_SLOTS = 0
COMMON_HITTER_STARTER_SLOTS_PER_TEAM = sum(COMMON_HITTER_SLOT_DEFAULTS.values())
COMMON_PITCHER_STARTER_SLOTS_PER_TEAM = sum(COMMON_PITCHER_SLOT_DEFAULTS.values())
SETTINGS = load_settings_from_env()
APP_ENVIRONMENT = SETTINGS.environment
CALCULATOR_JOB_TTL_SECONDS = SETTINGS.calculator_job_ttl_seconds
CALCULATOR_JOB_MAX_ENTRIES = SETTINGS.calculator_job_max_entries
CALCULATOR_JOB_WORKERS = SETTINGS.calculator_job_workers
ENABLE_STARTUP_CALC_PREWARM = SETTINGS.enable_startup_calc_prewarm
CALCULATOR_REQUEST_TIMEOUT_SECONDS = SETTINGS.calculator_request_timeout_seconds
CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE = SETTINGS.calculator_sync_rate_limit_per_minute
CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE = SETTINGS.calculator_job_create_rate_limit_per_minute
CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE = SETTINGS.calculator_job_status_rate_limit_per_minute
PROJECTION_RATE_LIMIT_PER_MINUTE = SETTINGS.projection_rate_limit_per_minute
PROJECTION_EXPORT_RATE_LIMIT_PER_MINUTE = SETTINGS.projection_export_rate_limit_per_minute
CALCULATOR_MAX_ACTIVE_JOBS_PER_IP = SETTINGS.calculator_max_active_jobs_per_ip
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
REDIS_RESULT_PREFIX = "ff:calc:result:"
REDIS_JOB_PREFIX = "ff:calc:job:"
REDIS_JOB_CANCEL_PREFIX = "ff:calc:job-cancel:"
REDIS_ACTIVE_JOBS_PREFIX = "ff:calc:active-jobs:"
REDIS_JOB_CLIENT_PREFIX = "ff:calc:job-client:"
REDIS_RATE_LIMIT_PREFIX = "ff:rate:"
CALC_LOGGER = logging.getLogger("fantasy_foundry.calculate")
CALC_JOB_CANCELLED_STATUS = "cancelled"
CALC_JOB_CANCELLED_ERROR = {"status_code": 499, "detail": "Calculation job cancelled by client."}
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


def _validate_runtime_configuration() -> None:
    if APP_ENVIRONMENT != "production":
        return

    errors: list[str] = []
    if "*" in set(CORS_ALLOW_ORIGINS):
        errors.append("FF_CORS_ALLOW_ORIGINS must not contain '*' when FF_ENV=production.")
    if TRUST_X_FORWARDED_FOR and not TRUSTED_PROXY_NETWORKS:
        errors.append(
            "FF_TRUST_X_FORWARDED_FOR=1 requires explicit FF_TRUSTED_PROXY_CIDRS when FF_ENV=production."
        )
    if REQUIRE_CALCULATE_AUTH and not CALCULATE_API_KEY_IDENTITIES:
        errors.append(
            "FF_REQUIRE_CALCULATE_AUTH=1 requires FF_CALCULATE_API_KEYS to be configured when FF_ENV=production."
        )

    if errors:
        raise RuntimeError("Invalid production runtime configuration:\n- " + "\n- ".join(errors))


def _extract_calculate_api_key(request: Request | None) -> str | None:
    return core_extract_calculate_api_key(request)


META = load_json("meta.json")
BAT_DATA_RAW = load_json("bat.json")
PIT_DATA_RAW = load_json("pitch.json")
BAT_DATA_RAW, PIT_DATA_RAW = _with_player_identity_keys(BAT_DATA_RAW, PIT_DATA_RAW)
BAT_DATA = _average_recent_projection_rows(BAT_DATA_RAW, max_entries=3, is_hitter=True)
PIT_DATA = _average_recent_projection_rows(PIT_DATA_RAW, max_entries=3, is_hitter=False)
PROJECTION_FRESHNESS = _projection_freshness_payload(BAT_DATA, PIT_DATA)
DATA_REFRESH_PATHS = (
    DATA_DIR / "meta.json",
    DATA_DIR / "bat.json",
    DATA_DIR / "pitch.json",
    EXCEL_PATH,
)
DATA_REFRESH_LOCK = Lock()


def _path_signature(path: Path) -> tuple[str, int | None, int | None]:
    return core_path_signature(path)


def _compute_data_signature() -> tuple[tuple[str, int | None, int | None], ...]:
    return core_compute_data_signature(DATA_REFRESH_PATHS)


def _stable_data_version_path_label(path: Path) -> str:
    return core_stable_data_version_path_label(path)


def _hash_file_into(path: Path, hasher: Any) -> None:
    core_hash_file_into(path, hasher)


def _compute_content_data_version(paths: tuple[Path, ...]) -> str:
    return core_compute_content_data_version(paths)


_DATA_SOURCE_SIGNATURE: tuple[tuple[str, int | None, int | None], ...] | None = _compute_data_signature()
_DATA_CONTENT_VERSION: str = _compute_content_data_version(DATA_REFRESH_PATHS)
CALCULATOR_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=CALCULATOR_JOB_WORKERS)
CALCULATOR_JOB_LOCK = Lock()
CALCULATOR_JOBS: dict[str, dict] = {}
CALCULATOR_PREWARM_LOCK = Lock()
CALCULATOR_PREWARM_STATE = {
    "status": "idle",
    "started_at": None,
    "completed_at": None,
    "duration_ms": None,
    "error": None,
}
REQUEST_RATE_LIMIT_LOCK = Lock()
REQUEST_RATE_LIMIT_BUCKETS: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_REQUEST_RATE_LIMIT_LAST_SWEEP_TS = 0.0
CALC_RESULT_CACHE_LOCK = Lock()
CALC_RESULT_CACHE: dict[str, tuple[float, dict]] = {}
CALC_RESULT_CACHE_ORDER: deque[str] = deque()
REDIS_CLIENT_STATE = core_runtime_infra.RedisClientState(lock=Lock())


def _current_data_version() -> str:
    return _DATA_CONTENT_VERSION


def _coerce_serialized_dynasty_lookup_map(raw: object) -> dict[str, dict]:
    return core_coerce_serialized_dynasty_lookup_map(raw)


def _dynasty_lookup_payload_version(payload: dict[str, object]) -> str | None:
    return core_dynasty_lookup_payload_version(payload)


def _inspect_precomputed_default_dynasty_lookup() -> DynastyLookupCacheInspection:
    pytest_current_test = bool(os.getenv("PYTEST_CURRENT_TEST"))
    e2e_enabled = str(os.getenv("FF_RUN_E2E", "")).strip().lower() in {"1", "true", "yes", "on"}
    inspection: LookupInspectionResult = core_inspect_precomputed_default_dynasty_lookup(
        current_data_version=_current_data_version(),
        dynasty_lookup_cache_path=DYNASTY_LOOKUP_CACHE_PATH,
        pytest_current_test=pytest_current_test and not e2e_enabled,
        value_col_sort_key=_value_col_sort_key,
    )
    return DynastyLookupCacheInspection(
        status=inspection.status,
        expected_version=inspection.expected_version,
        found_version=inspection.found_version,
        lookup=inspection.lookup,
        error=inspection.error,
    )


def _load_precomputed_default_dynasty_lookup() -> tuple[dict[str, dict], dict[str, dict], set[str], list[str]] | None:
    inspection = _inspect_precomputed_default_dynasty_lookup()
    if inspection.status == "ready" and inspection.lookup is not None:
        return inspection.lookup
    if inspection.status == "invalid" and inspection.error:
        CALC_LOGGER.warning(inspection.error)
    return None


def _reload_projection_data() -> None:
    global META, BAT_DATA_RAW, PIT_DATA_RAW, BAT_DATA, PIT_DATA, PROJECTION_FRESHNESS
    (
        META,
        BAT_DATA_RAW,
        PIT_DATA_RAW,
        BAT_DATA,
        PIT_DATA,
        PROJECTION_FRESHNESS,
    ) = core_reload_projection_data(
        load_json=load_json,
        with_player_identity_keys=_with_player_identity_keys,
        average_recent_projection_rows=_average_recent_projection_rows,
        projection_freshness_payload=_projection_freshness_payload,
    )


def _parse_ip_text(raw: str | None) -> IPAddress | None:
    return core_parse_ip_text(raw)


def _trusted_proxy_ip(addr: IPAddress) -> bool:
    return core_trusted_proxy_ip(
        addr,
        trusted_proxy_networks=TRUSTED_PROXY_NETWORKS,
        trust_x_forwarded_for=TRUST_X_FORWARDED_FOR,
    )


def _forwarded_for_chain(header_value: str | None) -> list[IPAddress]:
    return core_forwarded_for_chain(header_value)


def _client_ip(request: Request | None) -> str:
    return core_client_ip(
        request,
        trust_x_forwarded_for=TRUST_X_FORWARDED_FOR,
        trusted_proxy_networks=TRUSTED_PROXY_NETWORKS,
    )


def _calc_result_cache_key(settings: dict[str, Any]) -> str:
    return core_calc_result_cache_key(settings)


def _redis_client() -> Any | None:
    return core_runtime_infra.get_redis_client(
        redis_url=REDIS_URL,
        redis_lib=redis_lib,
        state=REDIS_CLIENT_STATE,
        logger=CALC_LOGGER,
    )


def _get_request_rate_limit_last_sweep_ts() -> float:
    return _REQUEST_RATE_LIMIT_LAST_SWEEP_TS


def _set_request_rate_limit_last_sweep_ts(value: float) -> None:
    global _REQUEST_RATE_LIMIT_LAST_SWEEP_TS
    _REQUEST_RATE_LIMIT_LAST_SWEEP_TS = value


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


def _ensure_backend_module_path() -> None:
    backend_path = str(BACKEND_MODULE_DIR)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)


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
    recent_projections: int,
    **roto_category_settings: bool,
) -> pd.DataFrame:
    return core_calculate_common_dynasty_frame(
        ensure_backend_module_path_fn=_ensure_backend_module_path,
        excel_path=EXCEL_PATH,
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
        recent_projections=recent_projections,
        roto_category_settings=roto_category_settings,
        roto_hitter_fields=ROTO_HITTER_CATEGORY_FIELDS,
        roto_pitcher_fields=ROTO_PITCHER_CATEGORY_FIELDS,
        coerce_bool_fn=_coerce_bool,
    )


def _stat_or_zero(row: dict | None, key: str) -> float:
    return core_stat_or_zero(row, key, as_float_fn=_as_float)


def _coerce_minor_eligible(value: object) -> bool:
    return core_coerce_minor_eligible(value)


def _projection_identity_key(row: dict | pd.Series) -> str:
    return core_projection_identity_key(
        row,
        player_entity_key_col=PLAYER_ENTITY_KEY_COL,
        player_key_col=PLAYER_KEY_COL,
        normalize_player_key_fn=_normalize_player_key,
    )


def _coerce_bool(value: object, *, default: bool = False) -> bool:
    return core_coerce_bool(value, default=default)


def _roto_category_settings_from_dict(source: dict[str, Any] | None) -> dict[str, bool]:
    return core_roto_category_settings_from_dict(
        source,
        coerce_bool_fn=lambda value, default=False: _coerce_bool(value, default=default),
        defaults=ROTO_CATEGORY_FIELD_DEFAULTS,
    )


def _selected_roto_categories(settings: dict[str, Any]) -> tuple[list[str], list[str]]:
    return core_selected_roto_categories(
        settings,
        roto_category_settings_from_dict_fn=_roto_category_settings_from_dict,
        hitter_fields=ROTO_HITTER_CATEGORY_FIELDS,
        pitcher_fields=ROTO_PITCHER_CATEGORY_FIELDS,
    )


@lru_cache(maxsize=64)
def _start_year_roto_stats_by_entity(
    *,
    start_year: int,
    recent_projections: int,
) -> dict[str, dict[str, float]]:
    return core_start_year_roto_stats_by_entity(
        start_year=start_year,
        recent_projections=recent_projections,
        bat_data=BAT_DATA,
        pit_data=PIT_DATA,
        bat_data_raw=BAT_DATA_RAW,
        pit_data_raw=PIT_DATA_RAW,
        average_recent_projection_rows_fn=_average_recent_projection_rows,
        coerce_record_year_fn=_coerce_record_year,
        projection_identity_key_fn=_projection_identity_key,
        coerce_numeric_fn=_coerce_numeric,
        roto_hitter_fields=ROTO_HITTER_CATEGORY_FIELDS,
        roto_pitcher_fields=ROTO_PITCHER_CATEGORY_FIELDS,
    )


def _valuation_years(start_year: int, horizon: int, valid_years: list[int]) -> list[int]:
    return core_valuation_years(start_year, horizon, valid_years)


def _calculate_hitter_points_breakdown(row: dict | None, scoring: dict[str, float]) -> dict:
    return core_calculate_hitter_points_breakdown(row, scoring, stat_or_zero_fn=_stat_or_zero)


def _calculate_pitcher_points_breakdown(row: dict | None, scoring: dict[str, float]) -> dict:
    return core_calculate_pitcher_points_breakdown(row, scoring, stat_or_zero_fn=_stat_or_zero)


def _points_player_identity(row: dict) -> str:
    return core_points_player_identity(
        row,
        player_entity_key_col=PLAYER_ENTITY_KEY_COL,
        player_key_col=PLAYER_KEY_COL,
        normalize_player_key_fn=_normalize_player_key,
    )


def _points_hitter_eligible_slots(pos_value: object) -> set[str]:
    return core_points_hitter_eligible_slots(pos_value, position_tokens_fn=_position_tokens)


def _points_pitcher_eligible_slots(pos_value: object) -> set[str]:
    return core_points_pitcher_eligible_slots(pos_value, position_tokens_fn=_position_tokens)


def _points_slot_replacement(
    entries: list[dict[str, object]],
    *,
    active_slots: set[str],
    rostered_player_ids: set[str],
    n_replacement: int,
) -> dict[str, float]:
    return core_points_slot_replacement(
        entries,
        active_slots=active_slots,
        rostered_player_ids=rostered_player_ids,
        n_replacement=n_replacement,
        as_float_fn=_as_float,
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
    two_way: str,
    start_year: int,
    recent_projections: int,
    pts_hit_1b: float,
    pts_hit_2b: float,
    pts_hit_3b: float,
    pts_hit_hr: float,
    pts_hit_r: float,
    pts_hit_rbi: float,
    pts_hit_sb: float,
    pts_hit_bb: float,
    pts_hit_so: float,
    pts_pit_ip: float,
    pts_pit_w: float,
    pts_pit_l: float,
    pts_pit_k: float,
    pts_pit_sv: float,
    pts_pit_svh: float,
    pts_pit_h: float,
    pts_pit_er: float,
    pts_pit_bb: float,
) -> pd.DataFrame:
    return core_calculate_points_dynasty_frame(
        ctx=PointsCalculatorContext(
            bat_data=BAT_DATA,
            pit_data=PIT_DATA,
            bat_data_raw=BAT_DATA_RAW,
            pit_data_raw=PIT_DATA_RAW,
            meta=META,
            average_recent_projection_rows=_average_recent_projection_rows,
            coerce_meta_years=_coerce_meta_years,
            valuation_years=_valuation_years,
            coerce_record_year=_coerce_record_year,
            points_player_identity=_points_player_identity,
            normalize_player_key=_normalize_player_key,
            player_key_col=PLAYER_KEY_COL,
            player_entity_key_col=PLAYER_ENTITY_KEY_COL,
            row_team_value=_row_team_value,
            merge_position_value=_merge_position_value,
            coerce_minor_eligible=_coerce_minor_eligible,
            calculate_hitter_points_breakdown=_calculate_hitter_points_breakdown,
            calculate_pitcher_points_breakdown=_calculate_pitcher_points_breakdown,
            stat_or_zero=_stat_or_zero,
            points_hitter_eligible_slots=_points_hitter_eligible_slots,
            points_pitcher_eligible_slots=_points_pitcher_eligible_slots,
            points_slot_replacement=_points_slot_replacement,
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
        hit_ut=hit_ut,
        pit_p=pit_p,
        pit_sp=pit_sp,
        pit_rp=pit_rp,
        bench=bench,
        minors=minors,
        ir=ir,
        two_way=two_way,
        start_year=start_year,
        recent_projections=recent_projections,
        pts_hit_1b=pts_hit_1b,
        pts_hit_2b=pts_hit_2b,
        pts_hit_3b=pts_hit_3b,
        pts_hit_hr=pts_hit_hr,
        pts_hit_r=pts_hit_r,
        pts_hit_rbi=pts_hit_rbi,
        pts_hit_sb=pts_hit_sb,
        pts_hit_bb=pts_hit_bb,
        pts_hit_so=pts_hit_so,
        pts_pit_ip=pts_pit_ip,
        pts_pit_w=pts_pit_w,
        pts_pit_l=pts_pit_l,
        pts_pit_k=pts_pit_k,
        pts_pit_sv=pts_pit_sv,
        pts_pit_svh=pts_pit_svh,
        pts_pit_h=pts_pit_h,
        pts_pit_er=pts_pit_er,
        pts_pit_bb=pts_pit_bb,
    )


def _is_user_fixable_calculation_error(message: str) -> bool:
    return core_is_user_fixable_calculation_error(message)


def _numeric_or_zero(value: object) -> float:
    return core_numeric_or_zero(value, as_float_fn=_as_float)


def _build_calculation_explanations(out: pd.DataFrame, *, settings: dict[str, Any]) -> dict[str, dict]:
    return core_build_calculation_explanations(
        out,
        settings=settings,
        player_key_col=PLAYER_KEY_COL,
        player_entity_key_col=PLAYER_ENTITY_KEY_COL,
        normalize_player_key_fn=_normalize_player_key,
        numeric_or_zero_fn=_numeric_or_zero,
        value_col_sort_key_fn=_value_col_sort_key,
    )


def _clean_records_for_json(records: list[dict]) -> list[dict]:
    return core_clean_records_for_json(records)


def _flatten_explanations_for_export(explanations: dict[str, dict]) -> list[dict]:
    return core_flatten_explanations_for_export(explanations)


def _default_calculator_export_columns(rows: list[dict]) -> list[str]:
    return core_default_calculator_export_columns(
        rows,
        calculator_result_stat_export_order=CALCULATOR_RESULT_STAT_EXPORT_ORDER,
        calculator_result_points_export_order=CALCULATOR_RESULT_POINTS_EXPORT_ORDER,
        value_col_sort_key=_value_col_sort_key,
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
    return core_tabular_export_response(
        rows,
        filename_base=filename_base,
        file_format=file_format,
        explain_rows=explain_rows,
        selected_columns=selected_columns,
        default_columns=default_columns,
        required_columns=required_columns,
        disallowed_columns=disallowed_columns,
        export_date_cols=EXPORT_DATE_COLS,
        export_header_label_overrides=EXPORT_HEADER_LABEL_OVERRIDES,
        export_three_decimal_cols=EXPORT_THREE_DECIMAL_COLS,
        export_two_decimal_cols=EXPORT_TWO_DECIMAL_COLS,
        export_whole_number_cols=EXPORT_WHOLE_NUMBER_COLS,
        export_integer_cols=EXPORT_INTEGER_COLS,
    )


@lru_cache(maxsize=1)
def _playable_pool_counts_by_year() -> dict[str, dict[str, int]]:
    return core_playable_pool_counts_by_year(
        bat_data=BAT_DATA,
        pit_data=PIT_DATA,
        coerce_record_year_fn=_coerce_record_year,
        as_float_fn=_as_float,
    )


def _default_calculation_cache_params() -> dict[str, int | float | str | None]:
    return core_default_calculation_cache_params(
        meta=META,
        coerce_meta_years_fn=_coerce_meta_years,
        common_hitter_slot_defaults=COMMON_HITTER_SLOT_DEFAULTS,
        common_pitcher_slot_defaults=COMMON_PITCHER_SLOT_DEFAULTS,
        common_default_minor_slots=COMMON_DEFAULT_MINOR_SLOTS,
        common_default_ir_slots=COMMON_DEFAULT_IR_SLOTS,
        roto_category_field_defaults=ROTO_CATEGORY_FIELD_DEFAULTS,
    )


def _calculator_guardrails_payload() -> dict:
    return core_calculator_guardrails_payload(
        common_hitter_starter_slots_per_team=COMMON_HITTER_STARTER_SLOTS_PER_TEAM,
        common_pitcher_starter_slots_per_team=COMMON_PITCHER_STARTER_SLOTS_PER_TEAM,
        common_hitter_slot_defaults=COMMON_HITTER_SLOT_DEFAULTS,
        common_pitcher_slot_defaults=COMMON_PITCHER_SLOT_DEFAULTS,
        points_hitter_slot_defaults=POINTS_HITTER_SLOT_DEFAULTS,
        points_pitcher_slot_defaults=POINTS_PITCHER_SLOT_DEFAULTS,
        default_points_scoring=DEFAULT_POINTS_SCORING,
        roto_hitter_fields=ROTO_HITTER_CATEGORY_FIELDS,
        roto_pitcher_fields=ROTO_PITCHER_CATEGORY_FIELDS,
        common_default_minor_slots=COMMON_DEFAULT_MINOR_SLOTS,
        common_default_ir_slots=COMMON_DEFAULT_IR_SLOTS,
        playable_by_year=_playable_pool_counts_by_year(),
        calculator_request_timeout_seconds=CALCULATOR_REQUEST_TIMEOUT_SECONDS,
        trusted_proxy_networks=TRUSTED_PROXY_NETWORKS,
        trust_x_forwarded_for=TRUST_X_FORWARDED_FOR,
        rate_limit_bucket_cleanup_interval_seconds=RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS,
        calculator_sync_rate_limit_per_minute=CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE,
        calculator_job_create_rate_limit_per_minute=CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE,
        calculator_job_status_rate_limit_per_minute=CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE,
        projection_rate_limit_per_minute=PROJECTION_RATE_LIMIT_PER_MINUTE,
        projection_export_rate_limit_per_minute=PROJECTION_EXPORT_RATE_LIMIT_PER_MINUTE,
        calculator_max_active_jobs_per_ip=CALCULATOR_MAX_ACTIVE_JOBS_PER_IP,
    )


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _mark_job_cancelled_locked(job: dict, *, now: str | None = None) -> None:
    timestamp = now or _iso_now()
    core_mark_job_cancelled_locked(
        job,
        now=timestamp,
        cancelled_status=CALC_JOB_CANCELLED_STATUS,
        cancelled_error=CALC_JOB_CANCELLED_ERROR,
    )


def _cleanup_calculation_jobs(now_ts: float | None = None) -> None:
    core_cleanup_calculation_jobs(
        CALCULATOR_JOBS,
        now_ts=now_ts,
        job_ttl_seconds=CALCULATOR_JOB_TTL_SECONDS,
        job_max_entries=CALCULATOR_JOB_MAX_ENTRIES,
        cancelled_status=CALC_JOB_CANCELLED_STATUS,
    )


def _calculation_job_public_payload(job: dict) -> dict:
    return core_calculation_job_public_payload(
        job,
        calculator_jobs=CALCULATOR_JOBS,
        cancelled_status=CALC_JOB_CANCELLED_STATUS,
    )


def _prewarm_default_calculation_caches() -> None:
    with CALCULATOR_PREWARM_LOCK:
        CALCULATOR_PREWARM_STATE.update(
            {
                "status": "running",
                "started_at": _iso_now(),
                "completed_at": None,
                "duration_ms": None,
                "error": None,
            }
        )

    started = time.perf_counter()
    try:
        _refresh_data_if_needed()
        params = _default_calculation_cache_params()
        ip_max = params["ip_max"]
        _calculate_common_dynasty_frame_cached(
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
            recent_projections=int(params["recent_projections"]),
            **_roto_category_settings_from_dict(params),
        )
        _get_default_dynasty_lookup()

        duration_ms = round((time.perf_counter() - started) * 1000.0, 1)
        with CALCULATOR_PREWARM_LOCK:
            CALCULATOR_PREWARM_STATE.update(
                {
                    "status": "ready",
                    "completed_at": _iso_now(),
                    "duration_ms": duration_ms,
                    "error": None,
                }
            )
        CALC_LOGGER.info("calculator prewarm completed duration_ms=%s", duration_ms)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 1)
        with CALCULATOR_PREWARM_LOCK:
            CALCULATOR_PREWARM_STATE.update(
                {
                    "status": "failed",
                    "completed_at": _iso_now(),
                    "duration_ms": duration_ms,
                    "error": str(exc),
                }
            )
        CALC_LOGGER.exception("calculator prewarm failed")


@lru_cache(maxsize=1)
def _get_default_dynasty_lookup() -> tuple[dict[str, dict], dict[str, dict], set[str], list[str]]:
    return core_default_dynasty_lookup(
        inspect_precomputed_default_dynasty_lookup=_inspect_precomputed_default_dynasty_lookup,
        require_precomputed_dynasty_lookup=REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP,
        required_lookup_error_factory=PrecomputedDynastyLookupRequiredError,
        default_calculation_cache_params=_default_calculation_cache_params,
        calculate_common_dynasty_frame_cached=_calculate_common_dynasty_frame_cached,
        roto_category_settings_from_dict=_roto_category_settings_from_dict,
        value_col_sort_key=_value_col_sort_key,
        normalize_team_key=_normalize_team_key,
        normalize_player_key=_normalize_player_key,
        bat_data=BAT_DATA,
        pit_data=PIT_DATA,
        player_key_col=PLAYER_KEY_COL,
        player_entity_key_col=PLAYER_ENTITY_KEY_COL,
    )


def _parse_dynasty_years(raw: str | None, *, valid_years: list[int] | None = None) -> list[int]:
    return core_parse_dynasty_years(raw, valid_years=valid_years, year_range_token_re=YEAR_RANGE_TOKEN_RE)


def _resolve_projection_year_filter(
    year: int | None,
    years: str | None,
    *,
    valid_years: list[int] | None = None,
) -> set[int] | None:
    return core_resolve_projection_year_filter(
        year,
        years,
        valid_years=valid_years,
        parse_dynasty_years_fn=lambda raw: _parse_dynasty_years(raw, valid_years=valid_years),
    )


def _attach_dynasty_values(rows: list[dict], dynasty_years: list[int] | None = None) -> list[dict]:
    try:
        return core_attach_dynasty_values(
            rows,
            dynasty_years=dynasty_years,
            get_default_dynasty_lookup=_get_default_dynasty_lookup,
            normalize_player_key=_normalize_player_key,
            player_key_col=PLAYER_KEY_COL,
            player_entity_key_col=PLAYER_ENTITY_KEY_COL,
        )
    except PrecomputedDynastyLookupRequiredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@lru_cache(maxsize=1)
def _player_identity_by_name() -> dict[str, tuple[str, str | None]]:
    return core_player_identity_by_name(
        bat_data=BAT_DATA,
        pit_data=PIT_DATA,
        player_key_col=PLAYER_KEY_COL,
        player_entity_key_col=PLAYER_ENTITY_KEY_COL,
        normalize_player_key=_normalize_player_key,
    )


def _refresh_data_if_needed() -> None:
    global _DATA_SOURCE_SIGNATURE, _DATA_CONTENT_VERSION
    result = core_refresh_data_if_needed(
        data_refresh_lock=DATA_REFRESH_LOCK,
        data_refresh_paths=DATA_REFRESH_PATHS,
        current_data_source_signature=_DATA_SOURCE_SIGNATURE,
        compute_data_signature_fn=core_compute_data_signature,
        reload_projection_data_fn=_reload_projection_data,
        on_reload_exception=traceback.print_exc,
        clear_after_reload=_clear_after_data_reload,
        compute_content_data_version_fn=core_compute_content_data_version,
    )
    if result is None:
        return

    signature, content_version = result
    _DATA_SOURCE_SIGNATURE = signature
    _DATA_CONTENT_VERSION = content_version


def _clear_after_data_reload() -> None:
    if "PROJECTION_SERVICE" in globals():
        PROJECTION_SERVICE.clear_caches()
    _calculate_common_dynasty_frame_cached.cache_clear()
    _calculate_points_dynasty_frame_cached.cache_clear()
    _playable_pool_counts_by_year.cache_clear()
    _get_default_dynasty_lookup.cache_clear()
    _player_identity_by_name.cache_clear()
    _start_year_roto_stats_by_entity.cache_clear()
    with CALC_RESULT_CACHE_LOCK:
        CALC_RESULT_CACHE.clear()
        CALC_RESULT_CACHE_ORDER.clear()


def _calculator_overlay_values_for_job(job_id: str | None) -> dict[str, dict[str, Any]]:
    normalized_job_id = str(job_id or "").strip()
    if not normalized_job_id:
        return {}

    with CALCULATOR_JOB_LOCK:
        live_job = CALCULATOR_JOBS.get(normalized_job_id)
    job_payload = live_job if isinstance(live_job, dict) else _cached_calculation_job_snapshot(normalized_job_id)
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

        entity_key = str(row.get(PLAYER_ENTITY_KEY_COL) or "").strip().lower()
        player_key = str(row.get(PLAYER_KEY_COL) or "").strip().lower()
        if entity_key:
            overlay_by_player_key[entity_key] = overlay
        elif player_key:
            overlay_by_player_key[player_key] = overlay

    return overlay_by_player_key


PROJECTION_SERVICE = ProjectionService(
    ProjectionServiceContext(
        refresh_data_if_needed=_refresh_data_if_needed,
        get_bat_data=lambda: BAT_DATA,
        get_pit_data=lambda: PIT_DATA,
        get_meta=lambda: META,
        normalize_player_key=_normalize_player_key,
        resolve_projection_year_filter=_resolve_projection_year_filter,
        parse_dynasty_years=_parse_dynasty_years,
        attach_dynasty_values=_attach_dynasty_values,
        coerce_meta_years=_coerce_meta_years,
        tabular_export_response=_tabular_export_response,
        calculator_overlay_values_for_job=_calculator_overlay_values_for_job,
        player_key_col=PLAYER_KEY_COL,
        player_entity_key_col=PLAYER_ENTITY_KEY_COL,
        position_token_split_re=POSITION_TOKEN_SPLIT_RE,
        position_display_order=POSITION_DISPLAY_ORDER,
        projection_text_sort_cols=PROJECTION_TEXT_SORT_COLS,
        all_tab_hitter_stat_cols=ALL_TAB_HITTER_STAT_COLS,
        all_tab_pitch_stat_cols=ALL_TAB_PITCH_STAT_COLS,
        projection_query_cache_maxsize=PROJECTION_QUERY_CACHE_MAXSIZE,
        filter_records=lambda *args, **kwargs: filter_records(*args, **kwargs),
    )
)
def _calculator_service_from_globals() -> CalculatorService:
    return build_calculator_service(
        refresh_data_if_needed=_refresh_data_if_needed,
        coerce_meta_years=_coerce_meta_years,
        get_meta=lambda: META,
        calc_result_cache_key=_calc_result_cache_key,
        result_cache_get=_result_cache_get,
        result_cache_set=_result_cache_set,
        calculate_common_dynasty_frame_cached=_calculate_common_dynasty_frame_cached,
        calculate_points_dynasty_frame_cached=_calculate_points_dynasty_frame_cached,
        roto_category_settings_from_dict=_roto_category_settings_from_dict,
        is_user_fixable_calculation_error=_is_user_fixable_calculation_error,
        player_identity_by_name=_player_identity_by_name,
        normalize_player_key=_normalize_player_key,
        player_key_col=PLAYER_KEY_COL,
        player_entity_key_col=PLAYER_ENTITY_KEY_COL,
        selected_roto_categories=_selected_roto_categories,
        start_year_roto_stats_by_entity=_start_year_roto_stats_by_entity,
        projection_identity_key=_projection_identity_key,
        build_calculation_explanations=_build_calculation_explanations,
        clean_records_for_json=_clean_records_for_json,
        flatten_explanations_for_export=_flatten_explanations_for_export,
        tabular_export_response=_tabular_export_response,
        calc_logger=CALC_LOGGER,
        enforce_rate_limit=_enforce_rate_limit,
        sync_rate_limit_per_minute=CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE,
        job_create_rate_limit_per_minute=CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE,
        job_status_rate_limit_per_minute=CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE,
        client_ip=_client_ip,
        iso_now=_iso_now,
        active_jobs_for_ip=_active_jobs_for_ip,
        calculator_max_active_jobs_per_ip=CALCULATOR_MAX_ACTIVE_JOBS_PER_IP,
        calculator_job_lock=CALCULATOR_JOB_LOCK,
        calculator_jobs=CALCULATOR_JOBS,
        cleanup_calculation_jobs=_cleanup_calculation_jobs,
        cache_calculation_job_snapshot=_cache_calculation_job_snapshot,
        cached_calculation_job_snapshot=_cached_calculation_job_snapshot,
        calculation_job_public_payload=_calculation_job_public_payload,
        mark_job_cancelled_locked=_mark_job_cancelled_locked,
        calculator_job_executor=CALCULATOR_JOB_EXECUTOR,
        calc_job_cancelled_status=CALC_JOB_CANCELLED_STATUS,
    )


CALCULATOR_SERVICE = _calculator_service_from_globals()

# Backward-compatible module-level aliases used by tests and internal patches.
CalculateRequest = CALCULATOR_SERVICE.calculate_request_model
CalculateExportRequest = CALCULATOR_SERVICE.calculate_export_request_model
_cached_projection_rows = PROJECTION_SERVICE._cached_projection_rows
_cached_all_projection_rows = PROJECTION_SERVICE._cached_all_projection_rows
_projection_sortable_columns_for_dataset = PROJECTION_SERVICE._projection_sortable_columns_for_dataset


def filter_records(*args, **kwargs):
    return PROJECTION_SERVICE.filter_records(*args, **kwargs)


def _log_precomputed_dynasty_lookup_cache_status() -> None:
    inspection = _inspect_precomputed_default_dynasty_lookup()
    CALC_LOGGER.info(
        "dynasty lookup cache status=%s require_precomputed=%s expected=%s found=%s",
        inspection.status,
        REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP,
        inspection.expected_version,
        inspection.found_version or "missing",
    )
    if inspection.error:
        CALC_LOGGER.warning("dynasty lookup cache error: %s", inspection.error)


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
RUNTIME_ORCHESTRATION_HELPERS = build_runtime_orchestration_helpers(state=sys.modules[__name__])
_status_orchestration_context = RUNTIME_ORCHESTRATION_HELPERS.status_orchestration_context
_calculator_orchestration_context = RUNTIME_ORCHESTRATION_HELPERS.calculator_orchestration_context


def _run_calculate_request(req: CalculateRequest, *, source: str) -> dict:
    return _calculator_service_from_globals()._run_calculate_request(req, source=source)


RUNTIME_ENDPOINT_HANDLERS = build_runtime_endpoint_handlers(
    RuntimeEndpointHandlerConfig(
        status_orchestration_context_getter=lambda: _status_orchestration_context(),
        calculator_orchestration_context_getter=lambda: _calculator_orchestration_context(),
        projection_service_getter=lambda: PROJECTION_SERVICE,
        run_calculate_request_getter=lambda: _run_calculate_request,
        enforce_rate_limit_getter=lambda: _enforce_rate_limit,
        projection_rate_limit_per_minute_getter=lambda: PROJECTION_RATE_LIMIT_PER_MINUTE,
        projection_export_rate_limit_per_minute_getter=lambda: PROJECTION_EXPORT_RATE_LIMIT_PER_MINUTE,
    )
)

_meta_payload = RUNTIME_ENDPOINT_HANDLERS.meta_payload
get_meta = RUNTIME_ENDPOINT_HANDLERS.get_meta
_version_payload = RUNTIME_ENDPOINT_HANDLERS.version_payload
_payload_etag = RUNTIME_ENDPOINT_HANDLERS.payload_etag
_etag_matches = RUNTIME_ENDPOINT_HANDLERS.etag_matches
get_version = RUNTIME_ENDPOINT_HANDLERS.get_version
_dynasty_lookup_cache_health_payload = RUNTIME_ENDPOINT_HANDLERS.dynasty_lookup_cache_health_payload
get_health = RUNTIME_ENDPOINT_HANDLERS.get_health
get_ready = RUNTIME_ENDPOINT_HANDLERS.get_ready
get_ops = RUNTIME_ENDPOINT_HANDLERS.get_ops
_run_calculation_job = RUNTIME_ENDPOINT_HANDLERS.run_calculation_job
projection_response = RUNTIME_ENDPOINT_HANDLERS.projection_response
export_projections = RUNTIME_ENDPOINT_HANDLERS.export_projections
calculate_dynasty_values = RUNTIME_ENDPOINT_HANDLERS.calculate_dynasty_values
export_calculate_dynasty_values = RUNTIME_ENDPOINT_HANDLERS.export_calculate_dynasty_values
create_calculate_dynasty_job = RUNTIME_ENDPOINT_HANDLERS.create_calculate_dynasty_job
get_calculate_dynasty_job = RUNTIME_ENDPOINT_HANDLERS.get_calculate_dynasty_job
cancel_calculate_dynasty_job = RUNTIME_ENDPOINT_HANDLERS.cancel_calculate_dynasty_job


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
# Serve frontend
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.include_router(
        build_frontend_assets_router(
            index_path=INDEX_PATH,
            assets_root=FRONTEND_DIST_ASSETS_DIR,
            app_build_id=APP_BUILD_ID,
            index_build_token=INDEX_BUILD_TOKEN,
        )
    )
