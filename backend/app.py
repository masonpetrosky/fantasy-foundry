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
import hashlib
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
    build_calculator_orchestration_context,
    build_calculator_service,
    build_status_orchestration_context,
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
    as_float as core_as_float,
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
from backend.core.projection_utils import (
    coerce_numeric as core_coerce_numeric,
    coerce_record_year as core_coerce_record_year,
    max_projection_count as core_max_projection_count,
    merge_position_value as core_merge_position_value,
    oldest_projection_date as core_oldest_projection_date,
    position_sort_key as core_position_sort_key,
    position_tokens as core_position_tokens,
    row_team_value as core_row_team_value,
)
from backend.core.projection_preprocessing import (
    average_recent_projection_rows as core_average_recent_projection_rows,
    coerce_iso_date_text as core_coerce_iso_date_text,
    find_projection_date_col as core_find_projection_date_col,
    normalize_player_key as core_normalize_player_key,
    normalize_team_key as core_normalize_team_key,
    normalize_year_key as core_normalize_year_key,
    parse_projection_dates as core_parse_projection_dates,
    pick_first_existing_col as core_pick_first_existing_col,
    with_player_identity_keys as core_with_player_identity_keys,
)
from backend.core.calculator_orchestration import (
    CalculatorOrchestrationContext,
    calculate_dynasty_values as core_calculate_dynasty_values,
    cancel_calculate_dynasty_job as core_cancel_calculate_dynasty_job,
    create_calculate_dynasty_job as core_create_calculate_dynasty_job,
    export_calculate_dynasty_values as core_export_calculate_dynasty_values,
    get_calculate_dynasty_job as core_get_calculate_dynasty_job,
    run_calculation_job as core_run_calculation_job,
)
from backend.core.status_orchestration import (
    StatusOrchestrationContext,
    build_meta_payload as core_build_meta_payload,
    build_version_payload as core_build_version_payload,
    dynasty_lookup_cache_health_payload as core_dynasty_lookup_cache_health_payload,
    etag_matches as core_etag_matches,
    get_health as core_get_health,
    get_meta as core_get_meta,
    get_ops as core_get_ops,
    get_ready as core_get_ready,
    get_version as core_get_version,
    payload_etag as core_payload_etag,
)
from backend.core.networking import (
    client_ip as core_client_ip,
    forwarded_for_chain as core_forwarded_for_chain,
    parse_ip_text as core_parse_ip_text,
    trusted_proxy_ip as core_trusted_proxy_ip,
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


PROJECTION_DATE_COLS = ["ProjectionDate", "Date", "Updated", "LastUpdated", "Timestamp", "Created", "AsOf"]
DERIVED_HIT_RATE_COLS = {"AVG", "OBP", "SLG", "OPS"}
DERIVED_PIT_RATE_COLS = {"ERA", "WHIP"}
TEAM_COL_CANDIDATES = ("Team", "MLBTeam")
YEAR_RANGE_TOKEN_RE = re.compile(r"^(\d{4})\s*-\s*(\d{4})$")
POSITION_TOKEN_SPLIT_RE = re.compile(r"[,\s/]+")
PROJECTION_QUERY_CACHE_MAXSIZE = 256
POSITION_DISPLAY_ORDER = ("C", "1B", "2B", "3B", "SS", "OF", "DH", "UT", "SP", "RP")
ALL_TAB_HITTER_STAT_COLS = ("G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "BB", "SO", "AVG", "OBP", "OPS")
ALL_TAB_PITCH_STAT_COLS = ("GS", "IP", "W", "QS", "QA3", "L", "K", "SV", "SVH", "ERA", "WHIP", "ER")
PROJECTION_TEXT_SORT_COLS = {"Player", "Team", "Pos", "Type", "Years"}
PLAYER_KEY_PATTERN = re.compile(r"[^a-z0-9]+")
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
    "HittingBestSlot": "Hitting Best Slot",
    "PitchingBestSlot": "Pitching Best Slot",
    "HittingValue": "Hitting Value",
    "PitchingValue": "Pitching Value",
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


def _load_trusted_proxy_networks(raw: str) -> tuple[IPNetwork, ...]:
    networks: list[IPNetwork] = []
    for token in raw.split(","):
        candidate = token.strip()
        if not candidate:
            continue
        try:
            if "/" in candidate:
                network = ipaddress.ip_network(candidate, strict=False)
            else:
                addr = ipaddress.ip_address(candidate)
                suffix = "32" if isinstance(addr, ipaddress.IPv4Address) else "128"
                network = ipaddress.ip_network(f"{addr}/{suffix}", strict=False)
        except ValueError:
            CALC_LOGGER.warning("ignoring invalid FF_TRUSTED_PROXY_CIDRS token: %s", candidate)
            continue
        networks.append(network)
    return tuple(networks)


TRUSTED_PROXY_NETWORKS = _load_trusted_proxy_networks(TRUSTED_PROXY_CIDRS_RAW)


def _parse_calculate_api_key_identities(raw: str) -> dict[str, str]:
    identities: dict[str, str] = {}
    for token in re.split(r"[\s,]+", raw.strip()):
        api_key = token.strip()
        if not api_key:
            continue
        digest = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:12]
        identities[api_key] = f"api_key:{digest}"
    return identities


CALCULATE_API_KEY_IDENTITIES = _parse_calculate_api_key_identities(CALCULATE_API_KEYS_RAW)


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
    if request is None:
        return None
    direct = str(request.headers.get("x-api-key") or "").strip()
    if direct:
        return direct
    auth_header = str(request.headers.get("authorization") or "").strip()
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        return token or None
    return None


def _pick_first_existing_col(df: pd.DataFrame, candidates: list[str] | tuple[str, ...]) -> str | None:
    return core_pick_first_existing_col(df, candidates)


def _find_projection_date_col(df: pd.DataFrame) -> str | None:
    return core_find_projection_date_col(df, projection_date_cols=PROJECTION_DATE_COLS)


def _parse_projection_dates(values: pd.Series) -> pd.Series:
    return core_parse_projection_dates(values)


def _coerce_iso_date_text(value: object) -> str | None:
    return core_coerce_iso_date_text(value)


def _normalize_player_key(value: object) -> str:
    return core_normalize_player_key(value, player_key_pattern=PLAYER_KEY_PATTERN)


def _normalize_team_key(value: object) -> str:
    return core_normalize_team_key(value)


def _normalize_year_key(value: object) -> str:
    return core_normalize_year_key(value)


def _with_player_identity_keys(
    bat_records: list[dict],
    pit_records: list[dict],
) -> tuple[list[dict], list[dict]]:
    return core_with_player_identity_keys(
        bat_records,
        pit_records,
        player_key_col=PLAYER_KEY_COL,
        player_entity_key_col=PLAYER_ENTITY_KEY_COL,
        normalize_player_key_fn=_normalize_player_key,
        normalize_team_key_fn=_normalize_team_key,
        normalize_year_key_fn=_normalize_year_key,
    )


def _average_recent_projection_rows(
    records: list[dict],
    *,
    max_entries: int = 3,
    is_hitter: bool,
) -> list[dict]:
    return core_average_recent_projection_rows(
        records,
        max_entries=max_entries,
        is_hitter=is_hitter,
        team_col_candidates=TEAM_COL_CANDIDATES,
        projection_date_cols=PROJECTION_DATE_COLS,
        derived_hit_rate_cols=DERIVED_HIT_RATE_COLS,
        derived_pit_rate_cols=DERIVED_PIT_RATE_COLS,
    )


def _projection_freshness_payload(
    bat_rows: list[dict],
    pit_rows: list[dict],
) -> dict[str, object]:
    oldest_date: str | None = None
    newest_date: str | None = None
    rows_with_projection_date = 0
    total_rows = len(bat_rows) + len(pit_rows)

    for row in [*bat_rows, *pit_rows]:
        date_text = _coerce_iso_date_text(row.get("OldestProjectionDate"))
        if not date_text:
            continue
        rows_with_projection_date += 1
        if oldest_date is None or date_text < oldest_date:
            oldest_date = date_text
        if newest_date is None or date_text > newest_date:
            newest_date = date_text

    coverage = (rows_with_projection_date / total_rows * 100.0) if total_rows else 0.0
    return {
        "oldest_projection_date": oldest_date,
        "newest_projection_date": newest_date,
        "rows_with_projection_date": rows_with_projection_date,
        "total_rows": total_rows,
        "date_coverage_pct": round(coverage, 1),
    }


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


def _coerce_meta_years(meta: dict) -> list[int]:
    years: list[int] = []
    for value in meta.get("years", []):
        try:
            years.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(years))


def _value_col_sort_key(col: str) -> tuple[int, int | str]:
    suffix = col.split("_", 1)[1] if "_" in col else col
    return (0, int(suffix)) if suffix.isdigit() else (1, suffix)


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


def _calculate_rate_limit_identity(request: Request | None) -> str:
    return core_runtime_infra.calculate_rate_limit_identity(
        request,
        extract_calculate_api_key=_extract_calculate_api_key,
        calculate_api_key_identities=CALCULATE_API_KEY_IDENTITIES,
        client_ip=_client_ip,
    )


def _authorize_calculate_request(request: Request) -> None:
    core_runtime_infra.authorize_calculate_request(
        request,
        extract_calculate_api_key=_extract_calculate_api_key,
        calculate_api_key_identities=CALCULATE_API_KEY_IDENTITIES,
        client_ip=_client_ip,
        require_calculate_auth=REQUIRE_CALCULATE_AUTH,
    )


def _prune_rate_limit_bucket(bucket: deque[float], *, window_start: float) -> None:
    core_runtime_infra.prune_rate_limit_bucket(bucket, window_start=window_start)


def _cleanup_rate_limit_buckets_locked(*, now: float, window_start: float) -> None:
    global _REQUEST_RATE_LIMIT_LAST_SWEEP_TS
    _REQUEST_RATE_LIMIT_LAST_SWEEP_TS = core_runtime_infra.cleanup_rate_limit_buckets_locked(
        rate_limit_buckets=REQUEST_RATE_LIMIT_BUCKETS,
        now=now,
        window_start=window_start,
        cleanup_interval_seconds=RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS,
        last_sweep_ts=_REQUEST_RATE_LIMIT_LAST_SWEEP_TS,
    )


def _rate_limit_exceeded(action: str) -> HTTPException:
    return core_runtime_infra.rate_limit_exceeded(action)


def _enforce_rate_limit(request: Request, *, action: str, limit_per_minute: int) -> None:
    core_runtime_infra.enforce_rate_limit(
        request,
        action=action,
        limit_per_minute=limit_per_minute,
        redis_rate_limit_prefix=REDIS_RATE_LIMIT_PREFIX,
        redis_client_getter=_redis_client,
        calculate_rate_limit_identity=_calculate_rate_limit_identity,
        request_rate_limit_lock=REQUEST_RATE_LIMIT_LOCK,
        request_rate_limit_buckets=REQUEST_RATE_LIMIT_BUCKETS,
        cleanup_rate_limit_buckets_locked=lambda now, window_start: _cleanup_rate_limit_buckets_locked(
            now=now, window_start=window_start
        ),
        prune_rate_limit_bucket=lambda bucket, window_start: _prune_rate_limit_bucket(bucket, window_start=window_start),
        rate_limit_exceeded=_rate_limit_exceeded,
        logger=CALC_LOGGER,
    )


def _rate_limit_bucket_count() -> int:
    return core_runtime_infra.rate_limit_bucket_count(
        request_rate_limit_lock=REQUEST_RATE_LIMIT_LOCK,
        request_rate_limit_buckets=REQUEST_RATE_LIMIT_BUCKETS,
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


def _redis_active_jobs_key(client_ip: str) -> str:
    return core_runtime_infra.redis_active_jobs_key(redis_active_jobs_prefix=REDIS_ACTIVE_JOBS_PREFIX, client_ip=client_ip)


def _redis_job_client_key(job_id: str) -> str:
    return core_runtime_infra.redis_job_client_key(redis_job_client_prefix=REDIS_JOB_CLIENT_PREFIX, job_id=job_id)


def _redis_job_cancel_key(job_id: str) -> str:
    return core_runtime_infra.redis_job_cancel_key(redis_job_cancel_prefix=REDIS_JOB_CANCEL_PREFIX, job_id=job_id)


def _track_active_job(job_id: str, client_ip: str) -> None:
    core_runtime_infra.track_active_job(
        job_id,
        client_ip,
        redis_client_getter=_redis_client,
        redis_active_jobs_prefix=REDIS_ACTIVE_JOBS_PREFIX,
        redis_job_client_prefix=REDIS_JOB_CLIENT_PREFIX,
        calculator_job_ttl_seconds=CALCULATOR_JOB_TTL_SECONDS,
        logger=CALC_LOGGER,
    )


def _job_client_ip(job_id: str) -> str | None:
    return core_runtime_infra.job_client_ip(
        job_id,
        redis_client_getter=_redis_client,
        redis_job_client_prefix=REDIS_JOB_CLIENT_PREFIX,
        logger=CALC_LOGGER,
    )


def _untrack_active_job(job_id: str, client_ip: str | None = None) -> None:
    core_runtime_infra.untrack_active_job(
        job_id,
        client_ip,
        redis_client_getter=_redis_client,
        redis_active_jobs_prefix=REDIS_ACTIVE_JOBS_PREFIX,
        redis_job_client_prefix=REDIS_JOB_CLIENT_PREFIX,
        job_client_ip_resolver=_job_client_ip,
        logger=CALC_LOGGER,
    )


def _set_job_cancel_requested(job_id: str) -> None:
    core_runtime_infra.set_job_cancel_requested(
        job_id,
        redis_client_getter=_redis_client,
        redis_job_cancel_prefix=REDIS_JOB_CANCEL_PREFIX,
        calculator_job_ttl_seconds=CALCULATOR_JOB_TTL_SECONDS,
        logger=CALC_LOGGER,
    )


def _clear_job_cancel_requested(job_id: str) -> None:
    core_runtime_infra.clear_job_cancel_requested(
        job_id,
        redis_client_getter=_redis_client,
        redis_job_cancel_prefix=REDIS_JOB_CANCEL_PREFIX,
        logger=CALC_LOGGER,
    )


def _job_cancel_requested(job_id: str) -> bool:
    return core_runtime_infra.job_cancel_requested(
        job_id,
        redis_client_getter=_redis_client,
        redis_job_cancel_prefix=REDIS_JOB_CANCEL_PREFIX,
        logger=CALC_LOGGER,
    )


def _active_jobs_for_ip(client_ip: str) -> int:
    return core_runtime_infra.active_jobs_for_ip(
        client_ip,
        redis_client_getter=_redis_client,
        redis_active_jobs_prefix=REDIS_ACTIVE_JOBS_PREFIX,
        redis_job_client_prefix=REDIS_JOB_CLIENT_PREFIX,
        calculator_jobs=CALCULATOR_JOBS,
        logger=CALC_LOGGER,
    )


def _cleanup_local_result_cache(now_ts: float | None = None) -> None:
    core_runtime_infra.cleanup_local_result_cache(
        CALC_RESULT_CACHE,
        CALC_RESULT_CACHE_ORDER,
        max_entries=CALC_RESULT_CACHE_MAX_ENTRIES,
        now_ts=now_ts,
    )


def _touch_local_result_cache_key(cache_key: str) -> None:
    core_runtime_infra.touch_local_result_cache_key(CALC_RESULT_CACHE_ORDER, cache_key)


def _result_cache_get(cache_key: str) -> dict | None:
    return core_runtime_infra.result_cache_get(
        cache_key,
        redis_client_getter=_redis_client,
        redis_result_prefix=REDIS_RESULT_PREFIX,
        logger=CALC_LOGGER,
        local_cache=CALC_RESULT_CACHE,
        local_cache_lock=CALC_RESULT_CACHE_LOCK,
        cleanup_local_result_cache_fn=_cleanup_local_result_cache,
        touch_local_result_cache_key_fn=_touch_local_result_cache_key,
    )


def _result_cache_set(cache_key: str, payload: dict) -> None:
    core_runtime_infra.result_cache_set(
        cache_key,
        payload,
        redis_client_getter=_redis_client,
        redis_result_prefix=REDIS_RESULT_PREFIX,
        cache_ttl_seconds=CALC_RESULT_CACHE_TTL_SECONDS,
        logger=CALC_LOGGER,
        local_cache=CALC_RESULT_CACHE,
        local_cache_lock=CALC_RESULT_CACHE_LOCK,
        touch_local_result_cache_key_fn=_touch_local_result_cache_key,
        cleanup_local_result_cache_fn=_cleanup_local_result_cache,
    )


def _cache_calculation_job_snapshot(job: dict) -> None:
    core_runtime_infra.cache_calculation_job_snapshot(
        job,
        redis_client_getter=_redis_client,
        redis_job_prefix=REDIS_JOB_PREFIX,
        job_ttl_seconds=CALCULATOR_JOB_TTL_SECONDS,
        logger=CALC_LOGGER,
        calculation_job_public_payload_fn=_calculation_job_public_payload,
    )


def _cached_calculation_job_snapshot(job_id: str) -> dict | None:
    return core_runtime_infra.cached_calculation_job_snapshot(
        job_id,
        redis_client_getter=_redis_client,
        redis_job_prefix=REDIS_JOB_PREFIX,
        logger=CALC_LOGGER,
    )


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


def _as_float(value: object) -> float | None:
    return core_as_float(value)


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
def _meta_payload() -> dict[str, Any]:
    return core_build_meta_payload(ctx=_status_orchestration_context())


def get_meta(request: Request):
    return core_get_meta(request, ctx=_status_orchestration_context())


# ---------------------------------------------------------------------------
# API: Projections
# ---------------------------------------------------------------------------
def _coerce_record_year(value: object) -> int | None:
    return core_coerce_record_year(value)


def _position_tokens(value: object) -> set[str]:
    return core_position_tokens(value, split_re=POSITION_TOKEN_SPLIT_RE)


def _position_sort_key(token: str) -> tuple[int, str]:
    return core_position_sort_key(token, display_order=POSITION_DISPLAY_ORDER)


def _row_team_value(row: dict) -> str:
    return core_row_team_value(row)


def _merge_position_value(hit_pos: object, pit_pos: object) -> str | None:
    return core_merge_position_value(
        hit_pos,
        pit_pos,
        split_re=POSITION_TOKEN_SPLIT_RE,
        display_order=POSITION_DISPLAY_ORDER,
    )


def _max_projection_count(*values: object) -> int | None:
    return core_max_projection_count(*values)


def _oldest_projection_date(*values: object) -> str | None:
    return core_oldest_projection_date(*values)


def _coerce_numeric(value: object) -> float | None:
    return core_coerce_numeric(value)


def _version_payload() -> dict[str, Any]:
    return core_build_version_payload(ctx=_status_orchestration_context())


def _payload_etag(payload: dict[str, Any]) -> str:
    return core_payload_etag(payload)


def _etag_matches(if_none_match: str | None, current_etag: str) -> bool:
    return core_etag_matches(if_none_match, current_etag)


def get_version(request: Request):
    return core_get_version(request, ctx=_status_orchestration_context())


def _dynasty_lookup_cache_health_payload() -> dict[str, Any]:
    return core_dynasty_lookup_cache_health_payload(ctx=_status_orchestration_context())


def get_health():
    return core_get_health(ctx=_status_orchestration_context())


def get_ready():
    return core_get_ready(ctx=_status_orchestration_context())


def get_ops():
    return core_get_ops(ctx=_status_orchestration_context())


def _status_orchestration_context() -> StatusOrchestrationContext:
    return build_status_orchestration_context(
        refresh_data_if_needed=_refresh_data_if_needed,
        meta_getter=lambda: META,
        calculator_guardrails_payload=_calculator_guardrails_payload,
        projection_freshness_getter=lambda: PROJECTION_FRESHNESS,
        environment=APP_ENVIRONMENT,
        cors_allow_origins=tuple(CORS_ALLOW_ORIGINS),
        trust_x_forwarded_for=TRUST_X_FORWARDED_FOR,
        trusted_proxy_cidrs=tuple(str(network) for network in TRUSTED_PROXY_NETWORKS),
        canonical_host=CANONICAL_HOST,
        require_calculate_auth=REQUIRE_CALCULATE_AUTH,
        calculate_api_keys_configured=bool(CALCULATE_API_KEY_IDENTITIES),
        calculator_prewarm_lock=CALCULATOR_PREWARM_LOCK,
        calculator_prewarm_state=CALCULATOR_PREWARM_STATE,
        api_no_cache_headers=API_NO_CACHE_HEADERS,
        current_data_version=_current_data_version,
        app_build_id=APP_BUILD_ID,
        deploy_commit_sha=DEPLOY_COMMIT_SHA,
        app_build_at=APP_BUILD_AT,
        inspect_precomputed_default_dynasty_lookup=_inspect_precomputed_default_dynasty_lookup,
        require_precomputed_dynasty_lookup=REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP,
        index_path=INDEX_PATH,
        calculator_job_lock=CALCULATOR_JOB_LOCK,
        cleanup_calculation_jobs=_cleanup_calculation_jobs,
        calculator_jobs=CALCULATOR_JOBS,
        calc_job_cancelled_status=CALC_JOB_CANCELLED_STATUS,
        calc_result_cache_lock=CALC_RESULT_CACHE_LOCK,
        cleanup_local_result_cache=_cleanup_local_result_cache,
        calc_result_cache=CALC_RESULT_CACHE,
        rate_limit_bucket_count_getter=_rate_limit_bucket_count,
        calculator_sync_rate_limit_per_minute=CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE,
        calculator_job_create_rate_limit_per_minute=CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE,
        calculator_job_status_rate_limit_per_minute=CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE,
        projection_rate_limit_per_minute=PROJECTION_RATE_LIMIT_PER_MINUTE,
        projection_export_rate_limit_per_minute=PROJECTION_EXPORT_RATE_LIMIT_PER_MINUTE,
        redis_url=REDIS_URL,
        bat_data_getter=lambda: BAT_DATA,
        pit_data_getter=lambda: PIT_DATA,
        iso_now=_iso_now,
    )


def _calculator_orchestration_context() -> CalculatorOrchestrationContext:
    return build_calculator_orchestration_context(
        calculate_request_model=CalculateRequest,
        enforce_rate_limit=_enforce_rate_limit,
        sync_rate_limit_per_minute=CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE,
        job_create_rate_limit_per_minute=CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE,
        job_status_rate_limit_per_minute=CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE,
        flatten_explanations_for_export=_flatten_explanations_for_export,
        tabular_export_response=_tabular_export_response,
        default_calculator_export_columns=_default_calculator_export_columns,
        export_internal_column_blocklist=EXPORT_INTERNAL_COLUMN_BLOCKLIST,
        calc_result_cache_key=_calc_result_cache_key,
        result_cache_get=_result_cache_get,
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
        calc_logger=CALC_LOGGER,
        track_active_job=_track_active_job,
        untrack_active_job=_untrack_active_job,
        set_job_cancel_requested=_set_job_cancel_requested,
        clear_job_cancel_requested=_clear_job_cancel_requested,
        job_cancel_requested=_job_cancel_requested,
    )


def _run_calculate_request(req: CalculateRequest, *, source: str) -> dict:
    return _calculator_service_from_globals()._run_calculate_request(req, source=source)


def _run_calculation_job(job_id: str, req_payload: dict) -> None:
    core_run_calculation_job(
        job_id,
        req_payload,
        ctx=_calculator_orchestration_context(),
        run_calculate_request=_run_calculate_request,
    )


def projection_response(
    dataset: Literal["all", "bat", "pitch"],
    *,
    request: Request,
    player: str | None,
    team: str | None,
    player_keys: str | None,
    year: int | None,
    years: str | None,
    pos: str | None,
    dynasty_years: str | None,
    career_totals: bool,
    include_dynasty: bool,
    calculator_job_id: str | None,
    sort_col: str | None,
    sort_dir: Literal["asc", "desc"],
    limit: int,
    offset: int,
) -> dict[str, Any]:
    _enforce_rate_limit(request, action="proj-read", limit_per_minute=PROJECTION_RATE_LIMIT_PER_MINUTE)
    return PROJECTION_SERVICE.projection_response(
        dataset,
        player=player,
        team=team,
        player_keys=player_keys,
        year=year,
        years=years,
        pos=pos,
        dynasty_years=dynasty_years,
        career_totals=career_totals,
        include_dynasty=include_dynasty,
        calculator_job_id=calculator_job_id,
        sort_col=sort_col,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )


def export_projections(
    *,
    request: Request,
    dataset: Literal["all", "bat", "pitch"],
    file_format: Literal["csv", "xlsx"] = "csv",
    player: str | None = None,
    team: str | None = None,
    player_keys: str | None = None,
    year: int | None = None,
    years: str | None = None,
    pos: str | None = None,
    dynasty_years: str | None = None,
    career_totals: bool = False,
    include_dynasty: bool = True,
    calculator_job_id: str | None = None,
    sort_col: str | None = None,
    sort_dir: Literal["asc", "desc"] = "desc",
    columns: str | None = None,
):
    _enforce_rate_limit(request, action="proj-export", limit_per_minute=PROJECTION_EXPORT_RATE_LIMIT_PER_MINUTE)
    return PROJECTION_SERVICE.export_projections(
        dataset=dataset,
        file_format=file_format,
        player=player,
        team=team,
        player_keys=player_keys,
        year=year,
        years=years,
        pos=pos,
        dynasty_years=dynasty_years,
        career_totals=career_totals,
        include_dynasty=include_dynasty,
        calculator_job_id=calculator_job_id,
        sort_col=sort_col,
        sort_dir=sort_dir,
        columns=columns,
    )


def calculate_dynasty_values(req: CalculateRequest, request: Request):
    return core_calculate_dynasty_values(
        req,
        request,
        ctx=_calculator_orchestration_context(),
        run_calculate_request=_run_calculate_request,
    )


def export_calculate_dynasty_values(req: CalculateExportRequest, request: Request):
    return core_export_calculate_dynasty_values(
        req,
        request,
        ctx=_calculator_orchestration_context(),
        run_calculate_request=_run_calculate_request,
    )


def create_calculate_dynasty_job(req: CalculateRequest, request: Request):
    return core_create_calculate_dynasty_job(
        req,
        request,
        ctx=_calculator_orchestration_context(),
        run_calculation_job=_run_calculation_job,
    )


def get_calculate_dynasty_job(job_id: str, request: Request):
    return core_get_calculate_dynasty_job(
        job_id,
        request,
        ctx=_calculator_orchestration_context(),
    )


def cancel_calculate_dynasty_job(job_id: str, request: Request):
    return core_cancel_calculate_dynasty_job(
        job_id,
        request,
        ctx=_calculator_orchestration_context(),
    )


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
