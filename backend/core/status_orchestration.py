"""Status/health/version endpoint orchestration helpers."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response


@dataclass(slots=True)
class StatusOrchestrationContext:
    refresh_data_if_needed: Callable[[], None]
    meta_getter: Callable[[], dict[str, Any]]
    calculator_guardrails_payload: Callable[[], dict[str, Any]]
    projection_freshness_getter: Callable[[], dict[str, Any]]
    environment: str
    cors_allow_origins: tuple[str, ...]
    trust_x_forwarded_for: bool
    trusted_proxy_cidrs: tuple[str, ...]
    canonical_host: str
    require_calculate_auth: bool
    calculate_api_keys_configured: bool
    calculator_prewarm_lock: Any
    calculator_prewarm_state: dict[str, Any]
    api_no_cache_headers: dict[str, str]
    current_data_version: Callable[[], str]
    app_build_id: str
    deploy_commit_sha: str
    app_build_at: str | None
    inspect_precomputed_default_dynasty_lookup: Callable[[], Any]
    require_precomputed_dynasty_lookup: bool
    index_path: Any
    calculator_job_lock: Any
    cleanup_calculation_jobs: Callable[[float | None], None]
    calculator_jobs: dict[str, dict]
    calc_job_cancelled_status: str
    calc_result_cache_lock: Any
    cleanup_local_result_cache: Callable[[float | None], None]
    calc_result_cache: dict[str, tuple[float, dict]]
    rate_limit_bucket_count_getter: Callable[[], int]
    rate_limit_activity_snapshot_getter: Callable[[], dict[str, Any]]
    calculator_sync_rate_limit_per_minute: int
    calculator_sync_auth_rate_limit_per_minute: int
    calculator_job_create_rate_limit_per_minute: int
    calculator_job_create_auth_rate_limit_per_minute: int
    calculator_job_status_rate_limit_per_minute: int
    calculator_job_status_auth_rate_limit_per_minute: int
    calculator_request_timeout_seconds: int
    calculator_max_active_jobs_per_ip: int
    calculator_max_active_jobs_total: int
    projection_rate_limit_per_minute: int
    projection_export_rate_limit_per_minute: int
    redis_url: str
    redis_client_getter: Callable[[], Any] | None
    bat_data_getter: Callable[[], list[dict]]
    pit_data_getter: Callable[[], list[dict]]
    calculator_worker_available: Callable[[], bool]
    iso_now: Callable[[], str]


def build_meta_payload(*, ctx: StatusOrchestrationContext) -> dict[str, Any]:
    payload = dict(ctx.meta_getter())
    payload["calculator_guardrails"] = ctx.calculator_guardrails_payload()
    projection_freshness = dict(ctx.projection_freshness_getter())
    payload["projection_freshness"] = projection_freshness
    raw_years = payload.get("years", [])
    parsed_years = sorted(
        {int(value) for value in raw_years if isinstance(value, (int, str)) and str(value).isdigit()}
    ) if isinstance(raw_years, list) else []
    payload["projection_window_start"] = parsed_years[0] if parsed_years else None
    payload["projection_window_end"] = parsed_years[-1] if parsed_years else None
    newest_projection_date = str(projection_freshness.get("newest_projection_date") or "").strip()
    payload["last_projection_update"] = newest_projection_date or None
    with ctx.calculator_prewarm_lock:
        payload["calculator_prewarm"] = dict(ctx.calculator_prewarm_state)
    return payload


def build_version_payload(*, ctx: StatusOrchestrationContext) -> dict[str, Any]:
    return {
        "build_id": ctx.app_build_id,
        "commit_sha": ctx.deploy_commit_sha or None,
        "built_at": ctx.app_build_at,
        "data_version": ctx.current_data_version(),
        "projection_freshness": dict(ctx.projection_freshness_getter()),
    }


def payload_etag(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f'"{digest}"'


def etag_matches(if_none_match: str | None, current_etag: str) -> bool:
    token = str(if_none_match or "").strip()
    if not token:
        return False
    if token == "*":
        return True

    current = current_etag[2:].strip() if current_etag.startswith("W/") else current_etag.strip()
    for raw_candidate in token.split(","):
        candidate = raw_candidate.strip()
        if not candidate:
            continue
        if candidate == "*":
            return True
        candidate = candidate[2:].strip() if candidate.startswith("W/") else candidate
        if candidate == current:
            return True
    return False


def dynasty_lookup_cache_health_payload(*, ctx: StatusOrchestrationContext) -> dict[str, Any]:
    inspection = ctx.inspect_precomputed_default_dynasty_lookup()
    payload = {
        "status": inspection.status,
        "require_precomputed": ctx.require_precomputed_dynasty_lookup,
        "version_expected": inspection.expected_version,
        "version_found": inspection.found_version,
    }
    if inspection.error:
        payload["error"] = inspection.error
    return payload


def _job_status_counts_and_snapshot(*, ctx: StatusOrchestrationContext) -> tuple[dict[str, int], list[dict[str, Any]]]:
    with ctx.calculator_job_lock:
        ctx.cleanup_calculation_jobs(None)
        counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0, ctx.calc_job_cancelled_status: 0}
        job_snapshot: list[dict[str, Any]] = []
        for job in ctx.calculator_jobs.values():
            job_snapshot.append(dict(job))
            status = str(job.get("status") or "").strip().lower()
            if status in counts:
                counts[status] += 1
    return counts, job_snapshot


def _job_status_counts(*, ctx: StatusOrchestrationContext) -> dict[str, int]:
    counts, _ = _job_status_counts_and_snapshot(ctx=ctx)
    return counts


def _coerce_epoch_seconds(raw: Any) -> float | None:
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_timestamp_epoch_seconds(raw: Any) -> float | None:
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return float(parsed.timestamp())


def _queue_pressure_payload(
    *,
    ctx: StatusOrchestrationContext,
    job_status_counts: dict[str, int],
    job_snapshot: list[dict[str, Any]],
) -> dict[str, Any]:
    now_epoch = _parse_timestamp_epoch_seconds(ctx.iso_now())
    if now_epoch is None:
        now_epoch = time.time()

    active_total = int(job_status_counts.get("queued", 0)) + int(job_status_counts.get("running", 0))
    capacity_total = max(1, int(ctx.calculator_max_active_jobs_total))
    capacity_remaining = max(0, capacity_total - active_total)
    utilization_ratio = round(active_total / capacity_total, 4)
    saturation_state = "idle"
    if active_total >= capacity_total:
        saturation_state = "critical"
    elif utilization_ratio >= 0.8:
        saturation_state = "high"
    elif active_total > 0:
        saturation_state = "active"

    recent_window_seconds = 900.0
    queued_ages: list[float] = []
    running_ages: list[float] = []
    running_runtimes: list[float] = []
    terminal_queue_waits: list[float] = []
    terminal_runtimes: list[float] = []

    recent_jobs_created = 0
    recent_jobs_started = 0
    recent_jobs_completed = 0
    recent_jobs_failed = 0
    recent_jobs_cancelled = 0
    terminal_statuses = {"completed", "failed", ctx.calc_job_cancelled_status}

    for job in job_snapshot:
        status = str(job.get("status") or "").strip().lower()
        created_epoch = _coerce_epoch_seconds(job.get("created_ts")) or _parse_timestamp_epoch_seconds(job.get("created_at"))
        started_epoch = _parse_timestamp_epoch_seconds(job.get("started_at"))
        completed_epoch = _parse_timestamp_epoch_seconds(job.get("completed_at"))

        if created_epoch is not None and (now_epoch - created_epoch) <= recent_window_seconds:
            recent_jobs_created += 1
        if started_epoch is not None and (now_epoch - started_epoch) <= recent_window_seconds:
            recent_jobs_started += 1

        if status == "queued" and created_epoch is not None:
            queued_ages.append(max(0.0, now_epoch - created_epoch))
        elif status == "running":
            if created_epoch is not None:
                running_ages.append(max(0.0, now_epoch - created_epoch))
            if started_epoch is not None:
                running_runtimes.append(max(0.0, now_epoch - started_epoch))

        if status in terminal_statuses and completed_epoch is not None and (now_epoch - completed_epoch) <= recent_window_seconds:
            if status == "completed":
                recent_jobs_completed += 1
            elif status == "failed":
                recent_jobs_failed += 1
            elif status == ctx.calc_job_cancelled_status:
                recent_jobs_cancelled += 1
            if created_epoch is not None and started_epoch is not None:
                terminal_queue_waits.append(max(0.0, started_epoch - created_epoch))
            if started_epoch is not None:
                terminal_runtimes.append(max(0.0, completed_epoch - started_epoch))

    queued_oldest_age = round(max(queued_ages), 3) if queued_ages else None
    running_oldest_age = round(max(running_ages), 3) if running_ages else None
    running_longest_runtime = round(max(running_runtimes), 3) if running_runtimes else None
    avg_queue_wait = round(sum(terminal_queue_waits) / len(terminal_queue_waits), 3) if terminal_queue_waits else None
    avg_runtime = round(sum(terminal_runtimes) / len(terminal_runtimes), 3) if terminal_runtimes else None
    timeout_seconds = float(ctx.calculator_request_timeout_seconds)

    return {
        "active_jobs": active_total,
        "queued_jobs": int(job_status_counts.get("queued", 0)),
        "running_jobs": int(job_status_counts.get("running", 0)),
        "capacity_total": capacity_total,
        "capacity_remaining": capacity_remaining,
        "utilization_ratio": utilization_ratio,
        "saturation_state": saturation_state,
        "at_capacity": active_total >= capacity_total,
        "queued_oldest_age_seconds": queued_oldest_age,
        "running_oldest_age_seconds": running_oldest_age,
        "running_longest_runtime_seconds": running_longest_runtime,
        "recent_window_seconds": int(recent_window_seconds),
        "recent_jobs_created": recent_jobs_created,
        "recent_jobs_started": recent_jobs_started,
        "recent_jobs_completed": recent_jobs_completed,
        "recent_jobs_failed": recent_jobs_failed,
        "recent_jobs_cancelled": recent_jobs_cancelled,
        "recent_jobs_terminal": recent_jobs_completed + recent_jobs_failed + recent_jobs_cancelled,
        "avg_queue_wait_seconds_recent_terminal": avg_queue_wait,
        "avg_run_duration_seconds_recent_terminal": avg_runtime,
        "alerts": {
            "queue_wait_exceeds_request_timeout": bool(
                queued_oldest_age is not None and queued_oldest_age > timeout_seconds
            ),
            "runtime_exceeds_request_timeout": bool(
                running_longest_runtime is not None and running_longest_runtime > timeout_seconds
            ),
        },
    }


def _local_result_cache_entries(*, ctx: StatusOrchestrationContext) -> int:
    with ctx.calc_result_cache_lock:
        ctx.cleanup_local_result_cache(None)
        return len(ctx.calc_result_cache)


def _queue_capacity_summary(*, ctx: StatusOrchestrationContext, job_status_counts: dict[str, int]) -> dict[str, Any]:
    active_jobs = int(job_status_counts.get("queued", 0)) + int(job_status_counts.get("running", 0))
    max_active_jobs_total = max(1, int(ctx.calculator_max_active_jobs_total))
    return {
        "active_jobs": active_jobs,
        "max_active_jobs_total": max_active_jobs_total,
        "capacity_remaining": max(0, max_active_jobs_total - active_jobs),
        "at_capacity": active_jobs >= max_active_jobs_total,
    }


def get_meta(request: Request, *, ctx: StatusOrchestrationContext):
    ctx.refresh_data_if_needed()
    payload = build_meta_payload(ctx=ctx)
    headers = dict(ctx.api_no_cache_headers)
    etag = payload_etag(payload)
    headers["ETag"] = etag
    if etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(payload, headers=headers)


def get_version(request: Request, *, ctx: StatusOrchestrationContext):
    ctx.refresh_data_if_needed()
    payload = build_version_payload(ctx=ctx)
    headers = dict(ctx.api_no_cache_headers)
    etag = payload_etag(payload)
    headers["ETag"] = etag
    if etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(payload, headers=headers)


def _redis_health_payload(*, ctx: StatusOrchestrationContext) -> dict[str, Any]:
    """Check Redis connectivity and return a health payload."""
    configured = bool(ctx.redis_url)
    if not configured or ctx.redis_client_getter is None:
        return {"configured": configured, "connected": False}
    try:
        client = ctx.redis_client_getter()
        if client is None:
            return {"configured": True, "connected": False}
        client.ping()
        return {"configured": True, "connected": True}
    except Exception:
        return {"configured": True, "connected": False}


def get_health(*, ctx: StatusOrchestrationContext) -> dict[str, Any]:
    ctx.refresh_data_if_needed()
    job_status_counts = _job_status_counts(ctx=ctx)
    local_result_cache_entries = _local_result_cache_entries(ctx=ctx)
    queue_capacity_summary = _queue_capacity_summary(ctx=ctx, job_status_counts=job_status_counts)

    with ctx.calculator_prewarm_lock:
        prewarm = dict(ctx.calculator_prewarm_state)

    redis_health = _redis_health_payload(ctx=ctx)

    return {
        "status": "ok",
        "build_id": ctx.app_build_id,
        "projection_rows": {
            "bat": len(ctx.bat_data_getter()),
            "pitch": len(ctx.pit_data_getter()),
        },
        "jobs": {
            "total": len(ctx.calculator_jobs),
            **job_status_counts,
        },
        "queue_pressure": queue_capacity_summary,
        "dynasty_lookup_cache": dynasty_lookup_cache_health_payload(ctx=ctx),
        "result_cache": {
            "local_entries": local_result_cache_entries,
            "redis_configured": redis_health["configured"],
            "redis_connected": redis_health["connected"],
        },
        "calculator_prewarm": prewarm,
        "timestamp": ctx.iso_now(),
    }


def get_ops(*, ctx: StatusOrchestrationContext) -> dict[str, Any]:
    ctx.refresh_data_if_needed()
    job_status_counts, job_snapshot = _job_status_counts_and_snapshot(ctx=ctx)
    job_pressure = _queue_pressure_payload(
        ctx=ctx,
        job_status_counts=job_status_counts,
        job_snapshot=job_snapshot,
    )
    local_result_cache_entries = _local_result_cache_entries(ctx=ctx)

    return {
        "status": "ok",
        "build": {
            "build_id": ctx.app_build_id,
            "commit_sha": ctx.deploy_commit_sha or None,
            "built_at": ctx.app_build_at,
            "environment": ctx.environment,
        },
        "data": {
            "version": ctx.current_data_version(),
            "projection_freshness": dict(ctx.projection_freshness_getter()),
            "dynasty_lookup_cache": dynasty_lookup_cache_health_payload(ctx=ctx),
        },
        "runtime": {
            "cors_allow_origins": list(ctx.cors_allow_origins),
            "trust_x_forwarded_for": ctx.trust_x_forwarded_for,
            "trusted_proxy_cidrs": list(ctx.trusted_proxy_cidrs),
            "client_identity_source": "x_forwarded_for" if ctx.trust_x_forwarded_for else "remote_addr",
            "shared_remote_addr_identity_risk": bool(ctx.environment == "production" and not ctx.trust_x_forwarded_for),
            "canonical_host": ctx.canonical_host or None,
            "require_calculate_auth": ctx.require_calculate_auth,
            "calculate_api_keys_configured": ctx.calculate_api_keys_configured,
            "redis_configured": bool(ctx.redis_url),
            "rate_limit_backend": "redis" if ctx.redis_url else "local",
        },
        "rate_limits": {
            "calculate_sync_per_minute": ctx.calculator_sync_rate_limit_per_minute,
            "calculate_sync_authenticated_per_minute": ctx.calculator_sync_auth_rate_limit_per_minute,
            "calculate_job_create_per_minute": ctx.calculator_job_create_rate_limit_per_minute,
            "calculate_job_create_authenticated_per_minute": ctx.calculator_job_create_auth_rate_limit_per_minute,
            "calculate_job_status_per_minute": ctx.calculator_job_status_rate_limit_per_minute,
            "calculate_job_status_authenticated_per_minute": ctx.calculator_job_status_auth_rate_limit_per_minute,
            "calculate_request_timeout_seconds": ctx.calculator_request_timeout_seconds,
            "calculate_max_active_jobs_per_ip": ctx.calculator_max_active_jobs_per_ip,
            "calculate_max_active_jobs_total": ctx.calculator_max_active_jobs_total,
            "projections_read_per_minute": ctx.projection_rate_limit_per_minute,
            "projections_export_per_minute": ctx.projection_export_rate_limit_per_minute,
        },
        "queues": {
            "jobs": {"total": sum(job_status_counts.values()), **job_status_counts},
            "job_pressure": job_pressure,
            "local_rate_limit_buckets": ctx.rate_limit_bucket_count_getter(),
            "rate_limit_activity": ctx.rate_limit_activity_snapshot_getter(),
            "local_result_cache_entries": local_result_cache_entries,
        },
        "timestamp": ctx.iso_now(),
    }


def get_ready(*, ctx: StatusOrchestrationContext):
    ctx.refresh_data_if_needed()
    if not ctx.index_path.exists():
        raise HTTPException(
            status_code=503,
            detail="Frontend dist/index.html is unavailable. Build the frontend before serving readiness.",
        )

    inspection = ctx.inspect_precomputed_default_dynasty_lookup()
    if ctx.require_precomputed_dynasty_lookup and inspection.status != "ready":
        raise HTTPException(
            status_code=503,
            detail=(
                "Precomputed dynasty lookup cache is not ready "
                f"(status={inspection.status}, expected={inspection.expected_version}, "
                f"found={inspection.found_version or 'missing'})."
            ),
        )

    bat_rows = len(ctx.bat_data_getter())
    pit_rows = len(ctx.pit_data_getter())
    if bat_rows <= 0 and pit_rows <= 0:
        raise HTTPException(status_code=503, detail="Projection datasets are unavailable.")

    if not ctx.calculator_worker_available():
        raise HTTPException(status_code=503, detail="Calculation worker is unavailable.")

    job_status_counts = _job_status_counts(ctx=ctx)
    queue_capacity_summary = _queue_capacity_summary(ctx=ctx, job_status_counts=job_status_counts)

    redis_health = _redis_health_payload(ctx=ctx)

    return {
        "status": "ready",
        "build_id": ctx.app_build_id,
        "data_version": ctx.current_data_version(),
        "checks": {
            "frontend_dist": True,
            "dynasty_lookup_cache": inspection.status,
            "projection_rows": {"bat": bat_rows, "pitch": pit_rows},
            "calculator_worker": True,
            "queue_capacity": queue_capacity_summary,
            "redis": redis_health,
        },
        "timestamp": ctx.iso_now(),
    }
