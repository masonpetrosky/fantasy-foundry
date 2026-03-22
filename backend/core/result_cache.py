"""Calculator result-cache helpers."""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from typing import Any, Callable

from backend.core.export_utils import clean_value_for_json

# Bump this version whenever calculation logic changes in a way that
# invalidates cached results.  Previous versions:
#   v1 — initial roto-only valuation
#   v2 — added points mode scoring
#   v3 — points mode per-slot replacement-level valuation
CALC_CACHE_VERSION = "v3"


def calc_result_cache_key(settings: dict[str, Any]) -> str:
    canonical = json.dumps(settings, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{CALC_CACHE_VERSION}:{digest}"


def cleanup_local_result_cache(
    local_cache: dict[str, tuple[float, dict]],
    local_cache_order: deque[str],
    *,
    max_entries: int,
    now_ts: float | None = None,
) -> None:
    now = time.time() if now_ts is None else now_ts
    expired = [key for key, (expires_at, _payload) in local_cache.items() if expires_at <= now]
    for key in expired:
        local_cache.pop(key, None)

    if local_cache_order:
        seen: set[str] = set()
        deduped: deque[str] = deque()
        for key in local_cache_order:
            if key in local_cache and key not in seen:
                deduped.append(key)
                seen.add(key)
        local_cache_order.clear()
        local_cache_order.extend(deduped)

    while len(local_cache) > max_entries and local_cache_order:
        oldest = local_cache_order.popleft()
        local_cache.pop(oldest, None)


def touch_local_result_cache_key(local_cache_order: deque[str], cache_key: str) -> None:
    try:
        local_cache_order.remove(cache_key)
    except ValueError:
        pass
    local_cache_order.append(cache_key)


def result_cache_get(
    cache_key: str,
    *,
    redis_client: Any | None,
    redis_result_prefix: str,
    logger: Any,
    local_cache: dict[str, tuple[float, dict]],
    local_cache_lock: Any,
    cleanup_local_result_cache_fn: Callable[[float | None], None],
    touch_local_result_cache_key_fn: Callable[[str], None],
) -> dict | None:
    if redis_client is not None:
        try:
            raw = redis_client.get(f"{redis_result_prefix}{cache_key}")
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
        except (ConnectionError, TimeoutError, OSError, ValueError):
            logger.warning("failed to read calculator result cache from redis", exc_info=True)

    now = time.time()
    with local_cache_lock:
        cleanup_local_result_cache_fn(now)
        cached = local_cache.get(cache_key)
        if not cached:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            local_cache.pop(cache_key, None)
            return None
        touch_local_result_cache_key_fn(cache_key)
        return dict(payload)


def result_cache_set(
    cache_key: str,
    payload: dict,
    *,
    redis_client: Any | None,
    redis_result_prefix: str,
    cache_ttl_seconds: int,
    logger: Any,
    local_cache: dict[str, tuple[float, dict]],
    local_cache_lock: Any,
    touch_local_result_cache_key_fn: Callable[[str], None],
    cleanup_local_result_cache_fn: Callable[[float | None], None],
) -> None:
    cleaned_payload = clean_value_for_json(payload)
    if not isinstance(cleaned_payload, dict):
        raise TypeError("calculator result cache payload must remain a dict")

    if redis_client is not None:
        try:
            redis_client.setex(
                f"{redis_result_prefix}{cache_key}",
                cache_ttl_seconds,
                json.dumps(cleaned_payload, separators=(",", ":"), sort_keys=True),
            )
        except (ConnectionError, TimeoutError, OSError, TypeError, ValueError):
            logger.warning(
                "failed to write calculator result cache to redis cache_key=%s",
                cache_key,
                exc_info=True,
            )

    expires_at = time.time() + cache_ttl_seconds
    with local_cache_lock:
        local_cache[cache_key] = (expires_at, dict(cleaned_payload))
        touch_local_result_cache_key_fn(cache_key)
        cleanup_local_result_cache_fn(None)


def _serializable_job_dict(job: dict) -> dict:
    """Return a copy of *job* with non-serializable fields removed."""
    return {k: v for k, v in job.items() if k != "future"}


def cache_calculation_job_snapshot(
    job: dict,
    *,
    redis_client: Any | None,
    redis_job_prefix: str,
    job_ttl_seconds: int,
    logger: Any,
    calculation_job_public_payload_fn: Callable[[dict], dict],
) -> None:
    if redis_client is None:
        return
    serializable_job = clean_value_for_json(_serializable_job_dict(job))
    if not isinstance(serializable_job, dict):
        raise TypeError("calculator job snapshot payload must remain a dict")
    try:
        redis_client.setex(
            f"{redis_job_prefix}{job['job_id']}",
            job_ttl_seconds,
            json.dumps(serializable_job, separators=(",", ":"), sort_keys=True),
        )
    except (ConnectionError, TimeoutError, OSError, TypeError, ValueError):
        logger.warning(
            "failed to cache calculator job metadata in redis job_id=%s",
            job.get("job_id"),
            exc_info=True,
        )


def cached_calculation_job_snapshot(
    job_id: str,
    *,
    redis_client: Any | None,
    redis_job_prefix: str,
    logger: Any,
) -> dict | None:
    if redis_client is None:
        return None
    try:
        raw = redis_client.get(f"{redis_job_prefix}{job_id}")
    except (ConnectionError, TimeoutError, OSError):
        logger.warning("failed to read calculator job payload from redis", exc_info=True)
        return None
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
