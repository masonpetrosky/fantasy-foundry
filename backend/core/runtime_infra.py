"""Runtime helpers for rate limiting, Redis job tracking, and result cache IO."""

from __future__ import annotations

import hmac
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

from backend.core.jobs import active_jobs_for_ip as core_active_jobs_for_ip
from backend.core.rate_limit import (
    cleanup_rate_limit_buckets_locked as core_cleanup_rate_limit_buckets_locked,
)
from backend.core.rate_limit import (
    prune_rate_limit_bucket as core_prune_rate_limit_bucket,
)
from backend.core.result_cache import (
    cache_calculation_job_snapshot as core_cache_calculation_job_snapshot,
)
from backend.core.result_cache import (
    cached_calculation_job_snapshot as core_cached_calculation_job_snapshot,
)
from backend.core.result_cache import (
    cleanup_local_result_cache as core_cleanup_local_result_cache,
)
from backend.core.result_cache import (
    result_cache_get as core_result_cache_get,
)
from backend.core.result_cache import (
    result_cache_set as core_result_cache_set,
)
from backend.core.result_cache import (
    touch_local_result_cache_key as core_touch_local_result_cache_key,
)


@dataclass(slots=True)
class RedisClientState:
    lock: Any
    client: Any | None = None
    init_attempted: bool = False


def get_redis_client(
    *,
    redis_url: str,
    redis_lib: Any | None,
    state: RedisClientState,
    logger: Any,
) -> Any | None:
    if not redis_url or redis_lib is None:
        return None
    if state.init_attempted:
        return state.client
    with state.lock:
        if state.init_attempted:
            return state.client
        state.init_attempted = True
        try:
            client = redis_lib.Redis.from_url(redis_url, decode_responses=True)
            client.ping()
            state.client = client
            logger.info("redis cache enabled for calculator results/jobs")
        except (ConnectionError, TimeoutError, OSError):
            state.client = None
            logger.warning("redis cache unavailable; falling back to in-memory calculator cache")
        return state.client


def calculate_rate_limit_identity(
    request: Request | None,
    *,
    extract_calculate_api_key: Callable[[Request | None], str | None],
    calculate_api_key_identities: dict[str, str],
    client_ip: Callable[[Request | None], str],
) -> str:
    if request is None:
        return "ip:unknown"
    state_identity = getattr(request.state, "calc_rate_limit_identity", None)
    if state_identity:
        return str(state_identity)
    api_key = extract_calculate_api_key(request)
    if api_key:
        matched_identity = _match_api_key(api_key, calculate_api_key_identities)
        if matched_identity is not None:
            return matched_identity
    return f"ip:{client_ip(request)}"


def _match_api_key(api_key: str, identities: dict[str, str]) -> str | None:
    """Return the identity for a matching API key using constant-time comparison."""
    matched: str | None = None
    for known_key, identity in identities.items():
        if hmac.compare_digest(api_key, known_key):
            matched = identity
    return matched


def authorize_calculate_request(
    request: Request,
    *,
    extract_calculate_api_key: Callable[[Request | None], str | None],
    calculate_api_key_identities: dict[str, str],
    client_ip: Callable[[Request | None], str],
    require_calculate_auth: bool,
) -> None:
    api_key = extract_calculate_api_key(request)
    matched_identity = _match_api_key(api_key, calculate_api_key_identities) if api_key else None
    if matched_identity is not None:
        request.state.calc_rate_limit_identity = matched_identity
        request.state.calc_api_key_authenticated = True
        return

    request.state.calc_rate_limit_identity = f"ip:{client_ip(request)}"
    request.state.calc_api_key_authenticated = False
    if not require_calculate_auth:
        return
    if not calculate_api_key_identities:
        raise HTTPException(
            status_code=503,
            detail="Calculator authentication is enabled but FF_CALCULATE_API_KEYS is not configured.",
        )
    raise HTTPException(status_code=401, detail="Missing or invalid API key for calculator endpoints.")


def prune_rate_limit_bucket(bucket: deque[float], *, window_start: float) -> None:
    core_prune_rate_limit_bucket(bucket, window_start=window_start)


def cleanup_rate_limit_buckets_locked(
    *,
    rate_limit_buckets: dict[tuple[str, str], deque[float]],
    now: float,
    window_start: float,
    cleanup_interval_seconds: float,
    last_sweep_ts: float,
) -> float:
    return core_cleanup_rate_limit_buckets_locked(
        rate_limit_buckets=rate_limit_buckets,
        now=now,
        window_start=window_start,
        cleanup_interval_seconds=cleanup_interval_seconds,
        last_sweep_ts=last_sweep_ts,
    )


def rate_limit_exceeded(action: str) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail=f"Rate limit exceeded for {action}. Try again in a minute.",
        headers={"Retry-After": "60"},
    )


def _store_rate_limit_state(
    request: Request,
    limit: int,
    used: int,
    reset_epoch: int,
) -> None:
    """Attach rate-limit metadata to the request so middleware can emit headers."""
    request.state.rate_limit_limit = int(limit)
    request.state.rate_limit_remaining = max(0, int(limit) - int(used))
    request.state.rate_limit_reset = int(reset_epoch)


def enforce_rate_limit(
    request: Request,
    *,
    action: str,
    limit_per_minute: int,
    redis_rate_limit_prefix: str,
    redis_client_getter: Callable[[], Any | None],
    calculate_rate_limit_identity: Callable[[Request | None], str],
    request_rate_limit_lock: Any,
    request_rate_limit_buckets: dict[tuple[str, str], deque[float]],
    cleanup_rate_limit_buckets_locked: Callable[[float, float], None],
    prune_rate_limit_bucket: Callable[[deque[float], float], None],
    rate_limit_exceeded: Callable[[str], HTTPException],
    logger: Any,
    on_decision: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    now = time.time()
    identity = calculate_rate_limit_identity(request)

    if limit_per_minute <= 0:
        if on_decision is not None:
            on_decision(
                {
                    "action": action,
                    "identity": identity,
                    "source": "disabled",
                    "outcome": "disabled",
                    "limit_per_minute": int(limit_per_minute),
                    "timestamp_epoch_s": float(now),
                }
            )
        return

    redis_client = redis_client_getter()
    if redis_client is not None:
        minute_window = int(now // 60)
        redis_key = f"{redis_rate_limit_prefix}{action}:{identity}:{minute_window}"
        try:
            count = int(redis_client.incr(redis_key))
            if count == 1:
                redis_client.expire(redis_key, 120)
            if count > limit_per_minute:
                if on_decision is not None:
                    on_decision(
                        {
                            "action": action,
                            "identity": identity,
                            "source": "redis",
                            "outcome": "blocked",
                            "limit_per_minute": int(limit_per_minute),
                            "observed_count": int(count),
                            "timestamp_epoch_s": float(now),
                        }
                    )
                raise rate_limit_exceeded(action)
            if on_decision is not None:
                on_decision(
                    {
                        "action": action,
                        "identity": identity,
                        "source": "redis",
                        "outcome": "allowed",
                        "limit_per_minute": int(limit_per_minute),
                        "observed_count": int(count),
                        "timestamp_epoch_s": float(now),
                    }
                )
            _store_rate_limit_state(request, limit_per_minute, int(count), minute_window * 60 + 60)
            return
        except HTTPException:
            raise
        except (ConnectionError, TimeoutError, OSError):
            if on_decision is not None:
                on_decision(
                    {
                        "action": action,
                        "identity": identity,
                        "source": "redis",
                        "outcome": "fallback",
                        "limit_per_minute": int(limit_per_minute),
                        "timestamp_epoch_s": float(now),
                    }
                )
            logger.warning("failed to enforce redis-backed rate limit; falling back to local buckets", exc_info=True)

    window_start = now - 60.0
    bucket_key = (action, identity)
    with request_rate_limit_lock:
        cleanup_rate_limit_buckets_locked(now, window_start)
        bucket = request_rate_limit_buckets[bucket_key]
        prune_rate_limit_bucket(bucket, window_start)
        if len(bucket) >= limit_per_minute:
            if on_decision is not None:
                on_decision(
                    {
                        "action": action,
                        "identity": identity,
                        "source": "local",
                        "outcome": "blocked",
                        "limit_per_minute": int(limit_per_minute),
                        "observed_count": int(len(bucket)),
                        "timestamp_epoch_s": float(now),
                    }
                )
            raise rate_limit_exceeded(action)
        bucket.append(now)
        _store_rate_limit_state(request, limit_per_minute, len(bucket), int(now) + 60)
        if on_decision is not None:
            on_decision(
                {
                    "action": action,
                    "identity": identity,
                    "source": "local",
                    "outcome": "allowed",
                    "limit_per_minute": int(limit_per_minute),
                    "observed_count": int(len(bucket)),
                    "timestamp_epoch_s": float(now),
                }
            )


def rate_limit_bucket_count(*, request_rate_limit_lock: Any, request_rate_limit_buckets: dict[tuple[str, str], deque[float]]) -> int:
    with request_rate_limit_lock:
        return len(request_rate_limit_buckets)


def redis_active_jobs_key(*, redis_active_jobs_prefix: str, client_ip: str) -> str:
    return f"{redis_active_jobs_prefix}{client_ip}"


def redis_job_client_key(*, redis_job_client_prefix: str, job_id: str) -> str:
    return f"{redis_job_client_prefix}{job_id}"


def redis_job_cancel_key(*, redis_job_cancel_prefix: str, job_id: str) -> str:
    return f"{redis_job_cancel_prefix}{job_id}"


def track_active_job(
    job_id: str,
    client_ip: str,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_active_jobs_prefix: str,
    redis_job_client_prefix: str,
    calculator_job_ttl_seconds: int,
    logger: Any,
) -> None:
    redis_client = redis_client_getter()
    if redis_client is None:
        return
    active_jobs_key = redis_active_jobs_key(redis_active_jobs_prefix=redis_active_jobs_prefix, client_ip=client_ip)
    job_client_key = redis_job_client_key(redis_job_client_prefix=redis_job_client_prefix, job_id=job_id)
    try:
        pipe = redis_client.pipeline(transaction=False)
        pipe.sadd(active_jobs_key, job_id)
        pipe.expire(active_jobs_key, calculator_job_ttl_seconds)
        pipe.setex(job_client_key, calculator_job_ttl_seconds, client_ip)
        pipe.execute()
    except (ConnectionError, TimeoutError, OSError):
        logger.warning("failed to track active calculator job in redis", exc_info=True)


def job_client_ip(
    job_id: str,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_job_client_prefix: str,
    logger: Any,
) -> str | None:
    redis_client = redis_client_getter()
    if redis_client is None:
        return None
    try:
        raw = redis_client.get(redis_job_client_key(redis_job_client_prefix=redis_job_client_prefix, job_id=job_id))
    except (ConnectionError, TimeoutError, OSError):
        logger.warning("failed to lookup calculator job client ip from redis", exc_info=True)
        return None
    client_ip = str(raw or "").strip()
    return client_ip or None


def untrack_active_job(
    job_id: str,
    client_ip: str | None = None,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_active_jobs_prefix: str,
    redis_job_client_prefix: str,
    job_client_ip_resolver: Callable[[str], str | None],
    logger: Any,
) -> None:
    redis_client = redis_client_getter()
    if redis_client is None:
        return
    resolved_client_ip = (client_ip or job_client_ip_resolver(job_id) or "").strip()
    if not resolved_client_ip:
        return
    active_jobs_key = redis_active_jobs_key(redis_active_jobs_prefix=redis_active_jobs_prefix, client_ip=resolved_client_ip)
    try:
        pipe = redis_client.pipeline(transaction=False)
        pipe.srem(active_jobs_key, job_id)
        pipe.delete(redis_job_client_key(redis_job_client_prefix=redis_job_client_prefix, job_id=job_id))
        pipe.execute()
    except (ConnectionError, TimeoutError, OSError):
        logger.warning("failed to untrack active calculator job in redis", exc_info=True)


def set_job_cancel_requested(
    job_id: str,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_job_cancel_prefix: str,
    calculator_job_ttl_seconds: int,
    logger: Any,
) -> None:
    redis_client = redis_client_getter()
    if redis_client is None:
        return
    try:
        redis_client.setex(
            redis_job_cancel_key(redis_job_cancel_prefix=redis_job_cancel_prefix, job_id=job_id),
            calculator_job_ttl_seconds,
            "1",
        )
    except (ConnectionError, TimeoutError, OSError):
        logger.warning("failed to store calculator job cancellation marker in redis", exc_info=True)


def clear_job_cancel_requested(
    job_id: str,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_job_cancel_prefix: str,
    logger: Any,
) -> None:
    redis_client = redis_client_getter()
    if redis_client is None:
        return
    try:
        redis_client.delete(redis_job_cancel_key(redis_job_cancel_prefix=redis_job_cancel_prefix, job_id=job_id))
    except (ConnectionError, TimeoutError, OSError):
        logger.warning("failed to clear calculator job cancellation marker in redis", exc_info=True)


def job_cancel_requested(
    job_id: str,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_job_cancel_prefix: str,
    logger: Any,
) -> bool:
    redis_client = redis_client_getter()
    if redis_client is None:
        return False
    try:
        return bool(redis_client.exists(redis_job_cancel_key(redis_job_cancel_prefix=redis_job_cancel_prefix, job_id=job_id)))
    except (ConnectionError, TimeoutError, OSError):
        logger.warning("failed to read calculator job cancellation marker in redis", exc_info=True)
        return False


def active_jobs_for_ip(
    client_ip: str,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_active_jobs_prefix: str,
    redis_job_client_prefix: str,
    calculator_jobs: dict[str, dict],
    logger: Any,
) -> int:
    redis_client = redis_client_getter()
    if redis_client is not None:
        try:
            active_jobs_key = redis_active_jobs_key(redis_active_jobs_prefix=redis_active_jobs_prefix, client_ip=client_ip)
            members = list(redis_client.smembers(active_jobs_key))
            if not members:
                return 0

            pipe = redis_client.pipeline(transaction=False)
            for job_id in members:
                pipe.exists(redis_job_client_key(redis_job_client_prefix=redis_job_client_prefix, job_id=str(job_id)))
            exists_flags = list(pipe.execute())

            live_count = 0
            stale_job_ids: list[str] = []
            for raw_job_id, is_live in zip(members, exists_flags, strict=False):
                job_id = str(raw_job_id)
                if bool(is_live):
                    live_count += 1
                else:
                    stale_job_ids.append(job_id)
            if stale_job_ids:
                redis_client.srem(active_jobs_key, *stale_job_ids)
            return live_count
        except (ConnectionError, TimeoutError, OSError):
            logger.warning("failed to count active calculator jobs in redis", exc_info=True)
    return core_active_jobs_for_ip(calculator_jobs, client_ip)


def cleanup_local_result_cache(
    local_cache: dict[str, tuple[float, dict]],
    local_cache_order: deque[str],
    *,
    max_entries: int,
    now_ts: float | None = None,
) -> None:
    core_cleanup_local_result_cache(
        local_cache,
        local_cache_order,
        max_entries=max_entries,
        now_ts=now_ts,
    )


def touch_local_result_cache_key(local_cache_order: deque[str], cache_key: str) -> None:
    core_touch_local_result_cache_key(local_cache_order, cache_key)


def result_cache_get(
    cache_key: str,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_result_prefix: str,
    logger: Any,
    local_cache: dict[str, tuple[float, dict]],
    local_cache_lock: Any,
    cleanup_local_result_cache_fn: Callable[[float | None], None],
    touch_local_result_cache_key_fn: Callable[[str], None],
) -> dict | None:
    return core_result_cache_get(
        cache_key,
        redis_client=redis_client_getter(),
        redis_result_prefix=redis_result_prefix,
        logger=logger,
        local_cache=local_cache,
        local_cache_lock=local_cache_lock,
        cleanup_local_result_cache_fn=cleanup_local_result_cache_fn,
        touch_local_result_cache_key_fn=touch_local_result_cache_key_fn,
    )


def result_cache_set(
    cache_key: str,
    payload: dict,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_result_prefix: str,
    cache_ttl_seconds: int,
    logger: Any,
    local_cache: dict[str, tuple[float, dict]],
    local_cache_lock: Any,
    touch_local_result_cache_key_fn: Callable[[str], None],
    cleanup_local_result_cache_fn: Callable[[float | None], None],
) -> None:
    core_result_cache_set(
        cache_key,
        payload,
        redis_client=redis_client_getter(),
        redis_result_prefix=redis_result_prefix,
        cache_ttl_seconds=cache_ttl_seconds,
        logger=logger,
        local_cache=local_cache,
        local_cache_lock=local_cache_lock,
        touch_local_result_cache_key_fn=touch_local_result_cache_key_fn,
        cleanup_local_result_cache_fn=cleanup_local_result_cache_fn,
    )


def cache_calculation_job_snapshot(
    job: dict,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_job_prefix: str,
    job_ttl_seconds: int,
    logger: Any,
    calculation_job_public_payload_fn: Callable[[dict], dict],
) -> None:
    core_cache_calculation_job_snapshot(
        job,
        redis_client=redis_client_getter(),
        redis_job_prefix=redis_job_prefix,
        job_ttl_seconds=job_ttl_seconds,
        logger=logger,
        calculation_job_public_payload_fn=calculation_job_public_payload_fn,
    )


def cached_calculation_job_snapshot(
    job_id: str,
    *,
    redis_client_getter: Callable[[], Any | None],
    redis_job_prefix: str,
    logger: Any,
) -> dict | None:
    return core_cached_calculation_job_snapshot(
        job_id,
        redis_client=redis_client_getter(),
        redis_job_prefix=redis_job_prefix,
        logger=logger,
    )
