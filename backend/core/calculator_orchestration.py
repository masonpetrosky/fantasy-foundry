"""Calculator endpoint/job orchestration helpers."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from fastapi import HTTPException, Request

CalculateRequestModel = type
RunCalculateRequest = Callable[[Any], dict]
RunCalculationJob = Callable[[str, dict], None]


@dataclass(slots=True)
class CalculatorOrchestrationContext:
    calculate_request_model: CalculateRequestModel
    enforce_rate_limit: Callable[..., None]
    sync_rate_limit_per_minute: int
    sync_auth_rate_limit_per_minute: int
    job_create_rate_limit_per_minute: int
    job_create_auth_rate_limit_per_minute: int
    job_status_rate_limit_per_minute: int
    job_status_auth_rate_limit_per_minute: int
    flatten_explanations_for_export: Callable[[dict[str, Any]], list[dict]]
    tabular_export_response: Callable[..., Any]
    default_calculator_export_columns: Callable[[list[dict]], list[str]]
    export_internal_column_blocklist: set[str]
    calc_result_cache_key: Callable[[dict[str, Any]], str]
    result_cache_get: Callable[[str], dict | None]
    client_ip: Callable[[Request | None], str]
    iso_now: Callable[[], str]
    active_jobs_for_ip: Callable[[str], int]
    calculator_max_active_jobs_per_ip: int
    calculator_max_active_jobs_total: int
    calculator_job_lock: Any
    calculator_jobs: dict[str, dict]
    cleanup_calculation_jobs: Callable[[float | None], None]
    cache_calculation_job_snapshot: Callable[[dict], None]
    cached_calculation_job_snapshot: Callable[[str], dict | None]
    calculation_job_public_payload: Callable[[dict], dict]
    mark_job_cancelled_locked: Callable[[dict], None]
    calculator_job_executor: Any
    calc_job_cancelled_status: str
    calc_logger: Any
    track_active_job: Callable[[str, str], None]
    untrack_active_job: Callable[[str, str | None], None]
    set_job_cancel_requested: Callable[[str], None]
    clear_job_cancel_requested: Callable[[str], None]
    job_cancel_requested: Callable[[str], bool]


def _request_is_calculate_api_key_authenticated(request: Request | Any | None) -> bool:
    state = getattr(request, "state", None)
    return bool(getattr(state, "calc_api_key_authenticated", False))


def _effective_rate_limit(
    request: Request | Any | None,
    *,
    anonymous_limit: int,
    authenticated_limit: int,
) -> int:
    if _request_is_calculate_api_key_authenticated(request):
        return max(1, int(authenticated_limit))
    return max(1, int(anonymous_limit))


def _active_job_total(calculator_jobs: dict[str, dict[str, Any]]) -> int:
    return sum(
        1
        for job in calculator_jobs.values()
        if str(job.get("status") or "").lower() in {"queued", "running"}
    )


def run_calculation_job(
    job_id: str,
    req_payload: dict,
    *,
    ctx: CalculatorOrchestrationContext,
    run_calculate_request: Callable[..., dict],
) -> None:
    terminal_client_ip: str | None = None
    with ctx.calculator_job_lock:
        job = ctx.calculator_jobs.get(job_id)
        if job is None:
            return
        terminal_client_ip = str(job.get("client_ip") or "").strip() or None
        cancelled = bool(job.get("cancel_requested")) or ctx.job_cancel_requested(job_id)
        if str(job.get("status") or "").lower() == ctx.calc_job_cancelled_status or cancelled:
            job["cancel_requested"] = True
            ctx.mark_job_cancelled_locked(job)
            ctx.cache_calculation_job_snapshot(job)
            ctx.clear_job_cancel_requested(job_id)
            ctx.untrack_active_job(job_id, terminal_client_ip)
            return
        job["status"] = "running"
        job["started_at"] = ctx.iso_now()
        job["updated_at"] = job["started_at"]
        job["error"] = None
        ctx.cache_calculation_job_snapshot(job)

    try:
        req = ctx.calculate_request_model(**req_payload)
        result = run_calculate_request(req, source="job")
        with ctx.calculator_job_lock:
            job = ctx.calculator_jobs.get(job_id)
            if job is None:
                return
            cancelled = bool(job.get("cancel_requested")) or ctx.job_cancel_requested(job_id)
            if str(job.get("status") or "").lower() == ctx.calc_job_cancelled_status or cancelled:
                job["cancel_requested"] = True
                ctx.mark_job_cancelled_locked(job)
                ctx.cache_calculation_job_snapshot(job)
                return
            now = ctx.iso_now()
            job["status"] = "completed"
            job["result"] = result
            job["completed_at"] = now
            job["updated_at"] = now
            job["error"] = None
            ctx.cache_calculation_job_snapshot(job)
    except HTTPException as exc:
        with ctx.calculator_job_lock:
            job = ctx.calculator_jobs.get(job_id)
            if job is None:
                return
            cancelled = bool(job.get("cancel_requested")) or ctx.job_cancel_requested(job_id)
            if str(job.get("status") or "").lower() == ctx.calc_job_cancelled_status or cancelled:
                job["cancel_requested"] = True
                ctx.mark_job_cancelled_locked(job)
                ctx.cache_calculation_job_snapshot(job)
                return
            now = ctx.iso_now()
            job["status"] = "failed"
            job["error"] = {"status_code": exc.status_code, "detail": exc.detail}
            job["completed_at"] = now
            job["updated_at"] = now
            job["result"] = None
            ctx.cache_calculation_job_snapshot(job)
    except Exception:
        ctx.calc_logger.exception("calculator job crashed job_id=%s", job_id)
        with ctx.calculator_job_lock:
            job = ctx.calculator_jobs.get(job_id)
            if job is None:
                return
            cancelled = bool(job.get("cancel_requested")) or ctx.job_cancel_requested(job_id)
            if str(job.get("status") or "").lower() == ctx.calc_job_cancelled_status or cancelled:
                job["cancel_requested"] = True
                ctx.mark_job_cancelled_locked(job)
                ctx.cache_calculation_job_snapshot(job)
                return
            now = ctx.iso_now()
            job["status"] = "failed"
            job["error"] = {"status_code": 500, "detail": "Internal calculator error."}
            job["completed_at"] = now
            job["updated_at"] = now
            job["result"] = None
            ctx.cache_calculation_job_snapshot(job)
    finally:
        with ctx.calculator_job_lock:
            ctx.cleanup_calculation_jobs(None)
        ctx.clear_job_cancel_requested(job_id)
        ctx.untrack_active_job(job_id, terminal_client_ip)


def calculate_dynasty_values(
    req: Any,
    request: Request,
    *,
    ctx: CalculatorOrchestrationContext,
    run_calculate_request: Callable[..., dict],
):
    ctx.enforce_rate_limit(
        request,
        action="calc-sync",
        limit_per_minute=_effective_rate_limit(
            request,
            anonymous_limit=ctx.sync_rate_limit_per_minute,
            authenticated_limit=ctx.sync_auth_rate_limit_per_minute,
        ),
    )
    return run_calculate_request(req, source="sync")


def export_calculate_dynasty_values(
    req: Any,
    request: Request,
    *,
    ctx: CalculatorOrchestrationContext,
    run_calculate_request: Callable[..., dict],
):
    ctx.enforce_rate_limit(
        request,
        action="calc-sync",
        limit_per_minute=_effective_rate_limit(
            request,
            anonymous_limit=ctx.sync_rate_limit_per_minute,
            authenticated_limit=ctx.sync_auth_rate_limit_per_minute,
        ),
    )
    payload = req.model_dump()
    export_format = str(payload.pop("format", "csv")).strip().lower()
    include_explanations = bool(payload.pop("include_explanations", False))
    requested_export_columns = payload.pop("export_columns", None)
    calc_req = ctx.calculate_request_model(**payload)
    result = run_calculate_request(calc_req, source="sync-export")
    result_rows = list(result.get("data", []))
    explain_rows = ctx.flatten_explanations_for_export(result.get("explanations", {})) if include_explanations else None
    return ctx.tabular_export_response(
        result_rows,
        filename_base=f"dynasty-rankings-{calc_req.scoring_mode}",
        file_format="xlsx" if export_format == "xlsx" else "csv",
        explain_rows=explain_rows,
        selected_columns=requested_export_columns,
        default_columns=ctx.default_calculator_export_columns(result_rows),
        required_columns=["Player", "DynastyValue"],
        disallowed_columns=ctx.export_internal_column_blocklist,
    )


def create_calculate_dynasty_job(
    req: Any,
    request: Request,
    *,
    ctx: CalculatorOrchestrationContext,
    run_calculation_job: RunCalculationJob,
):
    ctx.enforce_rate_limit(
        request,
        action="calc-job-create",
        limit_per_minute=_effective_rate_limit(
            request,
            anonymous_limit=ctx.job_create_rate_limit_per_minute,
            authenticated_limit=ctx.job_create_auth_rate_limit_per_minute,
        ),
    )
    client_ip = ctx.client_ip(request)
    created_at = ctx.iso_now()
    payload = req.model_dump()
    cache_key = ctx.calc_result_cache_key(payload)
    cached_result = ctx.result_cache_get(cache_key)
    job_id = uuid4().hex
    job = {
        "job_id": job_id,
        "status": "completed" if cached_result is not None else "queued",
        "created_at": created_at,
        "started_at": created_at if cached_result is not None else None,
        "completed_at": created_at if cached_result is not None else None,
        "updated_at": created_at,
        "created_ts": time.time(),
        "client_ip": client_ip,
        "settings": payload,
        "result": cached_result,
        "error": None,
        "cancel_requested": False,
        "future": None,
    }

    with ctx.calculator_job_lock:
        ctx.cleanup_calculation_jobs(job["created_ts"])
        if cached_result is None:
            active_total = _active_job_total(ctx.calculator_jobs)
            if active_total >= ctx.calculator_max_active_jobs_total:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Calculation queue is full right now. "
                        "Wait for active jobs to finish and retry."
                    ),
                )
            active_for_ip = ctx.active_jobs_for_ip(client_ip)
            if active_for_ip >= ctx.calculator_max_active_jobs_per_ip:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Too many active calculation jobs for this client IP. "
                        "Wait for an existing job to finish and retry."
                    ),
                )
        ctx.calculator_jobs[job_id] = job
        if cached_result is None:
            ctx.track_active_job(job_id, client_ip)
        ctx.cache_calculation_job_snapshot(job)
        response_payload = ctx.calculation_job_public_payload(job)

    if cached_result is None:
        ctx.clear_job_cancel_requested(job_id)
        try:
            future = ctx.calculator_job_executor.submit(run_calculation_job, job_id, payload)
        except RuntimeError as exc:
            with ctx.calculator_job_lock:
                ctx.calculator_jobs.pop(job_id, None)
            ctx.untrack_active_job(job_id, client_ip)
            raise HTTPException(status_code=503, detail="Calculation worker is unavailable.") from exc
        with ctx.calculator_job_lock:
            live_job = ctx.calculator_jobs.get(job_id)
            if live_job is not None:
                live_job["future"] = future
        ctx.calc_logger.info("calculator job queued job_id=%s settings=%s", job_id, json.dumps(payload, sort_keys=True))
    else:
        ctx.calc_logger.info("calculator job cache-hit job_id=%s settings=%s", job_id, json.dumps(payload, sort_keys=True))

    return response_payload


def get_calculate_dynasty_job(
    job_id: str,
    request: Request,
    *,
    ctx: CalculatorOrchestrationContext,
):
    ctx.enforce_rate_limit(
        request,
        action="calc-job-status",
        limit_per_minute=_effective_rate_limit(
            request,
            anonymous_limit=ctx.job_status_rate_limit_per_minute,
            authenticated_limit=ctx.job_status_auth_rate_limit_per_minute,
        ),
    )
    with ctx.calculator_job_lock:
        ctx.cleanup_calculation_jobs(None)
        job = ctx.calculator_jobs.get(job_id)
        if job is None:
            cached_job = ctx.cached_calculation_job_snapshot(job_id)
            if cached_job is not None:
                return cached_job
            raise HTTPException(status_code=404, detail="Calculation job not found or expired.")
        return ctx.calculation_job_public_payload(job)


def cancel_calculate_dynasty_job(
    job_id: str,
    request: Request,
    *,
    ctx: CalculatorOrchestrationContext,
):
    ctx.enforce_rate_limit(
        request,
        action="calc-job-status",
        limit_per_minute=_effective_rate_limit(
            request,
            anonymous_limit=ctx.job_status_rate_limit_per_minute,
            authenticated_limit=ctx.job_status_auth_rate_limit_per_minute,
        ),
    )
    with ctx.calculator_job_lock:
        ctx.cleanup_calculation_jobs(None)
        job = ctx.calculator_jobs.get(job_id)
        if job is None:
            cached_job = ctx.cached_calculation_job_snapshot(job_id)
            if cached_job is not None:
                status = str(cached_job.get("status") or "").lower()
                if status in {"queued", "running"}:
                    ctx.set_job_cancel_requested(job_id)
                    synthetic = dict(cached_job)
                    synthetic["cancel_requested"] = True
                    synthetic["updated_at"] = ctx.iso_now()
                    synthetic.setdefault("created_at", ctx.iso_now())
                    synthetic["job_id"] = str(cached_job.get("job_id") or job_id)
                    ctx.mark_job_cancelled_locked(synthetic)
                    ctx.cache_calculation_job_snapshot(synthetic)
                    ctx.untrack_active_job(job_id, None)
                    return ctx.calculation_job_public_payload(synthetic)
                return cached_job
            raise HTTPException(status_code=404, detail="Calculation job not found or expired.")

        status = str(job.get("status") or "").lower()
        if status not in {"queued", "running"}:
            return ctx.calculation_job_public_payload(job)

        ctx.set_job_cancel_requested(job_id)
        job["cancel_requested"] = True
        future = job.get("future")
        cancel_future = getattr(future, "cancel", None)
        if callable(cancel_future):
            try:
                cancel_future()
            except Exception:
                pass
        ctx.mark_job_cancelled_locked(job)
        ctx.cache_calculation_job_snapshot(job)
        ctx.untrack_active_job(job_id, str(job.get("client_ip") or "").strip() or None)
        return ctx.calculation_job_public_payload(job)
