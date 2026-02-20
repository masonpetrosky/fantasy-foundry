"""Status/health/version endpoint orchestration helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response


@dataclass(slots=True)
class StatusOrchestrationContext:
    refresh_data_if_needed: Callable[[], None]
    meta_getter: Callable[[], dict[str, Any]]
    calculator_guardrails_payload: Callable[[], dict[str, Any]]
    projection_freshness_getter: Callable[[], dict[str, Any]]
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
    redis_url: str
    bat_data_getter: Callable[[], list[dict]]
    pit_data_getter: Callable[[], list[dict]]
    iso_now: Callable[[], str]


def build_meta_payload(*, ctx: StatusOrchestrationContext) -> dict[str, Any]:
    payload = dict(ctx.meta_getter())
    payload["calculator_guardrails"] = ctx.calculator_guardrails_payload()
    payload["projection_freshness"] = dict(ctx.projection_freshness_getter())
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


def get_health(*, ctx: StatusOrchestrationContext) -> dict[str, Any]:
    ctx.refresh_data_if_needed()

    with ctx.calculator_job_lock:
        ctx.cleanup_calculation_jobs(None)
        job_status_counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0, ctx.calc_job_cancelled_status: 0}
        for job in ctx.calculator_jobs.values():
            status = str(job.get("status") or "").strip().lower()
            if status in job_status_counts:
                job_status_counts[status] += 1

    with ctx.calc_result_cache_lock:
        ctx.cleanup_local_result_cache(None)
        local_result_cache_entries = len(ctx.calc_result_cache)

    with ctx.calculator_prewarm_lock:
        prewarm = dict(ctx.calculator_prewarm_state)

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
        "dynasty_lookup_cache": dynasty_lookup_cache_health_payload(ctx=ctx),
        "result_cache": {
            "local_entries": local_result_cache_entries,
            "redis_configured": bool(ctx.redis_url),
        },
        "calculator_prewarm": prewarm,
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

    return {
        "status": "ready",
        "build_id": ctx.app_build_id,
        "data_version": ctx.current_data_version(),
        "timestamp": ctx.iso_now(),
    }
