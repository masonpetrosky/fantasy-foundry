"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int, minimum: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _get_float(name: str, default: float, minimum: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(minimum, value)


def _parse_cors_allow_origins(raw: str | None) -> tuple[str, ...]:
    text = str(raw or "").strip()
    if not text:
        return ("*",)
    origins = tuple(token.strip() for token in text.split(",") if token.strip())
    return origins or ("*",)


@dataclass(frozen=True)
class AppSettings:
    calculator_job_ttl_seconds: int
    calculator_job_max_entries: int
    calculator_job_workers: int
    enable_startup_calc_prewarm: bool
    calculator_request_timeout_seconds: int
    calculator_sync_rate_limit_per_minute: int
    calculator_job_create_rate_limit_per_minute: int
    calculator_job_status_rate_limit_per_minute: int
    calculator_max_active_jobs_per_ip: int
    calc_result_cache_ttl_seconds: int
    calc_result_cache_max_entries: int
    require_precomputed_dynasty_lookup: bool
    trust_x_forwarded_for: bool
    trusted_proxy_cidrs_raw: str
    redis_url: str
    rate_limit_bucket_cleanup_interval_seconds: float
    cors_allow_origins: tuple[str, ...]


def load_settings_from_env() -> AppSettings:
    """Build immutable runtime settings from environment variables."""

    return AppSettings(
        calculator_job_ttl_seconds=_get_int("FF_CALC_JOB_TTL_SECONDS", default=1800, minimum=60),
        calculator_job_max_entries=_get_int("FF_CALC_JOB_MAX_ENTRIES", default=256, minimum=10),
        calculator_job_workers=_get_int("FF_CALC_JOB_WORKERS", default=2, minimum=1),
        enable_startup_calc_prewarm=_get_bool("FF_PREWARM_DEFAULT_CALC", default=True),
        calculator_request_timeout_seconds=_get_int("FF_CALC_REQUEST_TIMEOUT_SECONDS", default=600, minimum=60),
        calculator_sync_rate_limit_per_minute=_get_int("FF_CALC_SYNC_RATE_LIMIT_PER_MINUTE", default=30, minimum=1),
        calculator_job_create_rate_limit_per_minute=_get_int(
            "FF_CALC_JOB_CREATE_RATE_LIMIT_PER_MINUTE", default=15, minimum=1
        ),
        calculator_job_status_rate_limit_per_minute=_get_int(
            "FF_CALC_JOB_STATUS_RATE_LIMIT_PER_MINUTE", default=240, minimum=1
        ),
        calculator_max_active_jobs_per_ip=_get_int("FF_CALC_MAX_ACTIVE_JOBS_PER_IP", default=2, minimum=1),
        calc_result_cache_ttl_seconds=_get_int("FF_CALC_RESULT_CACHE_TTL_SECONDS", default=1800, minimum=30),
        calc_result_cache_max_entries=_get_int("FF_CALC_RESULT_CACHE_MAX_ENTRIES", default=256, minimum=10),
        require_precomputed_dynasty_lookup=_get_bool("FF_REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP", default=True),
        trust_x_forwarded_for=_get_bool("FF_TRUST_X_FORWARDED_FOR", default=False),
        trusted_proxy_cidrs_raw=str(os.getenv("FF_TRUSTED_PROXY_CIDRS", "")).strip(),
        redis_url=str(os.getenv("FF_REDIS_URL", "")).strip(),
        rate_limit_bucket_cleanup_interval_seconds=_get_float(
            "FF_RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS", default=60.0, minimum=5.0
        ),
        cors_allow_origins=_parse_cors_allow_origins(os.getenv("FF_CORS_ALLOW_ORIGINS")),
    )
