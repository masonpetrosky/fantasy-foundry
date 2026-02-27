"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast
from urllib.parse import urlparse

APP_ENVIRONMENTS = {"development", "production"}


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


def _parse_environment(raw: str | None) -> Literal["development", "production"]:
    text = str(raw or "").strip().lower()
    if text in APP_ENVIRONMENTS:
        return cast(Literal["development", "production"], text)
    return "development"


def _parse_canonical_host(raw: str | None) -> str:
    text = str(raw or "").strip().lower()
    if not text:
        return ""

    if "://" in text:
        parsed = urlparse(text)
        text = str(parsed.hostname or "").strip().lower()

    text = text.strip().rstrip(".")
    if not text:
        return ""

    if ":" in text and not text.startswith("["):
        host, port = text.rsplit(":", 1)
        if port.isdigit():
            text = host

    return text


@dataclass(frozen=True)
class AppSettings:
    environment: Literal["development", "production"]
    calculator_job_ttl_seconds: int
    calculator_job_max_entries: int
    calculator_job_workers: int
    enable_startup_calc_prewarm: bool
    calculator_request_timeout_seconds: int
    calculator_sync_rate_limit_per_minute: int
    calculator_sync_auth_rate_limit_per_minute: int
    calculator_job_create_rate_limit_per_minute: int
    calculator_job_create_auth_rate_limit_per_minute: int
    calculator_job_status_rate_limit_per_minute: int
    calculator_job_status_auth_rate_limit_per_minute: int
    projection_rate_limit_per_minute: int
    projection_export_rate_limit_per_minute: int
    calculator_max_active_jobs_per_ip: int
    calculator_max_active_jobs_total: int
    calc_result_cache_ttl_seconds: int
    calc_result_cache_max_entries: int
    require_precomputed_dynasty_lookup: bool
    trust_x_forwarded_for: bool
    trusted_proxy_cidrs_raw: str
    redis_url: str
    require_calculate_auth: bool
    calculate_api_keys_raw: str
    canonical_host: str
    rate_limit_bucket_cleanup_interval_seconds: float
    cors_allow_origins: tuple[str, ...]
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_monthly_price_id: str
    stripe_annual_price_id: str
    buttondown_api_key: str
    supabase_url: str
    supabase_service_role_key: str


def load_settings_from_env() -> AppSettings:
    """Build immutable runtime settings from environment variables."""

    calculator_sync_rate_limit_per_minute = _get_int("FF_CALC_SYNC_RATE_LIMIT_PER_MINUTE", default=30, minimum=1)
    calculator_job_create_rate_limit_per_minute = _get_int(
        "FF_CALC_JOB_CREATE_RATE_LIMIT_PER_MINUTE", default=15, minimum=1
    )
    calculator_job_status_rate_limit_per_minute = _get_int(
        "FF_CALC_JOB_STATUS_RATE_LIMIT_PER_MINUTE", default=240, minimum=1
    )

    return AppSettings(
        environment=_parse_environment(os.getenv("FF_ENV")),
        calculator_job_ttl_seconds=_get_int("FF_CALC_JOB_TTL_SECONDS", default=1800, minimum=60),
        calculator_job_max_entries=_get_int("FF_CALC_JOB_MAX_ENTRIES", default=256, minimum=10),
        calculator_job_workers=_get_int("FF_CALC_JOB_WORKERS", default=2, minimum=1),
        enable_startup_calc_prewarm=_get_bool("FF_PREWARM_DEFAULT_CALC", default=True),
        calculator_request_timeout_seconds=_get_int("FF_CALC_REQUEST_TIMEOUT_SECONDS", default=600, minimum=60),
        calculator_sync_rate_limit_per_minute=calculator_sync_rate_limit_per_minute,
        calculator_sync_auth_rate_limit_per_minute=_get_int(
            "FF_CALC_SYNC_AUTH_RATE_LIMIT_PER_MINUTE",
            default=max(calculator_sync_rate_limit_per_minute, 60),
            minimum=1,
        ),
        calculator_job_create_rate_limit_per_minute=calculator_job_create_rate_limit_per_minute,
        calculator_job_create_auth_rate_limit_per_minute=_get_int(
            "FF_CALC_JOB_CREATE_AUTH_RATE_LIMIT_PER_MINUTE",
            default=max(calculator_job_create_rate_limit_per_minute, 30),
            minimum=1,
        ),
        calculator_job_status_rate_limit_per_minute=calculator_job_status_rate_limit_per_minute,
        calculator_job_status_auth_rate_limit_per_minute=_get_int(
            "FF_CALC_JOB_STATUS_AUTH_RATE_LIMIT_PER_MINUTE",
            default=max(calculator_job_status_rate_limit_per_minute, 360),
            minimum=1,
        ),
        projection_rate_limit_per_minute=_get_int("FF_PROJ_RATE_LIMIT_PER_MINUTE", default=120, minimum=1),
        projection_export_rate_limit_per_minute=_get_int("FF_EXPORT_RATE_LIMIT_PER_MINUTE", default=30, minimum=1),
        calculator_max_active_jobs_per_ip=_get_int("FF_CALC_MAX_ACTIVE_JOBS_PER_IP", default=2, minimum=1),
        calculator_max_active_jobs_total=_get_int("FF_CALC_MAX_ACTIVE_JOBS_TOTAL", default=24, minimum=1),
        calc_result_cache_ttl_seconds=_get_int("FF_CALC_RESULT_CACHE_TTL_SECONDS", default=1800, minimum=30),
        calc_result_cache_max_entries=_get_int("FF_CALC_RESULT_CACHE_MAX_ENTRIES", default=256, minimum=10),
        require_precomputed_dynasty_lookup=_get_bool("FF_REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP", default=True),
        trust_x_forwarded_for=_get_bool("FF_TRUST_X_FORWARDED_FOR", default=False),
        trusted_proxy_cidrs_raw=str(os.getenv("FF_TRUSTED_PROXY_CIDRS", "")).strip(),
        redis_url=str(os.getenv("FF_REDIS_URL", "")).strip(),
        require_calculate_auth=_get_bool("FF_REQUIRE_CALCULATE_AUTH", default=False),
        calculate_api_keys_raw=str(os.getenv("FF_CALCULATE_API_KEYS", "")).strip(),
        canonical_host=_parse_canonical_host(os.getenv("FF_CANONICAL_HOST")),
        rate_limit_bucket_cleanup_interval_seconds=_get_float(
            "FF_RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS", default=60.0, minimum=5.0
        ),
        cors_allow_origins=_parse_cors_allow_origins(os.getenv("FF_CORS_ALLOW_ORIGINS")),
        stripe_secret_key=str(os.getenv("STRIPE_SECRET_KEY", os.getenv("FF_STRIPE_SECRET_KEY", ""))).strip(),
        stripe_webhook_secret=str(
            os.getenv("STRIPE_WEBHOOK_SECRET", os.getenv("FF_STRIPE_WEBHOOK_SECRET", ""))
        ).strip(),
        stripe_monthly_price_id=str(os.getenv("STRIPE_MONTHLY_PRICE_ID", "")).strip(),
        stripe_annual_price_id=str(os.getenv("STRIPE_ANNUAL_PRICE_ID", "")).strip(),
        buttondown_api_key=str(os.getenv("BUTTONDOWN_API_KEY", "")).strip(),
        supabase_url=str(os.getenv("SUPABASE_URL", "")).strip(),
        supabase_service_role_key=str(os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")).strip(),
    )
