from __future__ import annotations

import types
from collections import defaultdict, deque
from threading import Lock

import pytest
from fastapi import HTTPException

from backend.core.runtime_cache_job_helpers import (
    RuntimeCacheJobHelperConfig,
    build_runtime_cache_job_helpers,
)
from backend.core.runtime_infra import RedisClientState


class _Logger:
    def info(self, _message: str, *args: object) -> None:
        return None

    def warning(self, _message: str, *args: object, exc_info: bool = False) -> None:
        _ = exc_info
        return None


def _extract_api_key(request: object | None) -> str | None:
    if request is None:
        return None
    headers = getattr(request, "headers", {})
    key = str(headers.get("x-api-key") or "").strip()
    return key or None


def _build_helpers():
    auth_state = {"keys": {"alpha": "api_key:a"}, "required": False}
    sweep_state = {"value": 0.0}
    max_entries_state = {"value": 8}
    local_cache: dict[str, tuple[float, dict]] = {}
    local_cache_order: deque[str] = deque()
    rate_limit_buckets: dict[tuple[str, str], deque[float]] = defaultdict(deque)
    calculator_jobs: dict[str, dict] = {}

    helpers = build_runtime_cache_job_helpers(
        RuntimeCacheJobHelperConfig(
            redis_url="",
            redis_lib=None,
            redis_client_state=RedisClientState(lock=Lock()),
            logger=_Logger(),
            redis_rate_limit_prefix="ff:rate:",
            redis_result_prefix="ff:calc:result:",
            redis_job_prefix="ff:calc:job:",
            redis_job_cancel_prefix="ff:calc:job-cancel:",
            redis_active_jobs_prefix="ff:calc:active-jobs:",
            redis_job_client_prefix="ff:calc:job-client:",
            calculator_job_ttl_seconds=60,
            calc_result_cache_ttl_seconds=60,
            request_rate_limit_lock=Lock(),
            request_rate_limit_buckets=rate_limit_buckets,
            rate_limit_bucket_cleanup_interval_seconds=60.0,
            request_rate_limit_last_sweep_ts_getter=lambda: sweep_state["value"],
            request_rate_limit_last_sweep_ts_setter=lambda value: sweep_state.__setitem__("value", value),
            calc_result_cache_max_entries_getter=lambda: max_entries_state["value"],
            calc_result_cache_lock=Lock(),
            calc_result_cache=local_cache,
            calc_result_cache_order=local_cache_order,
            calculator_jobs=calculator_jobs,
            calculate_api_key_identities_getter=lambda: auth_state["keys"],
            extract_calculate_api_key=_extract_api_key,
            client_ip=lambda _request: "198.51.100.10",
            require_calculate_auth_getter=lambda: auth_state["required"],
            calculation_job_public_payload_fn=lambda job: dict(job),
        )
    )
    return helpers, auth_state, sweep_state, max_entries_state, rate_limit_buckets, local_cache, local_cache_order


def test_authorize_calculate_request_uses_dynamic_auth_config():
    helpers, auth_state, *_ = _build_helpers()

    request = types.SimpleNamespace(headers={"x-api-key": "alpha"}, state=types.SimpleNamespace())
    helpers.authorize_calculate_request(request)
    assert request.state.calc_rate_limit_identity == "api_key:a"
    assert request.state.calc_api_key_authenticated is True

    auth_state["keys"] = {}
    auth_state["required"] = True
    denied_request = types.SimpleNamespace(headers={"x-api-key": "alpha"}, state=types.SimpleNamespace())
    with pytest.raises(HTTPException) as exc:
        helpers.authorize_calculate_request(denied_request)
    assert exc.value.status_code == 503


def test_cleanup_rate_limit_buckets_updates_external_last_sweep_state():
    helpers, _, sweep_state, _, buckets, *_ = _build_helpers()
    buckets[("calc-sync", "old")] = deque([100.0])
    buckets[("calc-sync", "mixed")] = deque([939.0, 945.0])

    helpers.cleanup_rate_limit_buckets_locked(now=1000.0, window_start=940.0)

    assert ("calc-sync", "old") not in buckets
    assert list(buckets[("calc-sync", "mixed")]) == [945.0]
    assert sweep_state["value"] == 1000.0


def test_cleanup_local_result_cache_uses_dynamic_max_entries_getter():
    helpers, _, _, max_entries_state, _, local_cache, local_cache_order = _build_helpers()
    local_cache["a"] = (9999.0, {"value": "A"})
    local_cache["b"] = (9999.0, {"value": "B"})
    local_cache_order.extend(["a", "b"])
    max_entries_state["value"] = 1

    helpers.cleanup_local_result_cache(now_ts=0.0)

    assert list(local_cache.keys()) == ["b"]
    assert list(local_cache_order) == ["b"]


def test_rate_limit_activity_snapshot_tracks_local_allow_and_block() -> None:
    helpers, _, _, _, rate_limit_buckets, *_ = _build_helpers()
    request = types.SimpleNamespace(headers={}, state=types.SimpleNamespace())
    rate_limit_buckets[("calc-sync", "ip:198.51.100.10")] = deque()

    helpers.enforce_rate_limit(request, action="calc-sync", limit_per_minute=1)
    with pytest.raises(HTTPException):
        helpers.enforce_rate_limit(request, action="calc-sync", limit_per_minute=1)

    snapshot = helpers.rate_limit_activity_snapshot()
    assert snapshot["totals"]["allowed"] == 1
    assert snapshot["totals"]["blocked"] == 1
    assert snapshot["totals"]["local_allowed"] == 1
    assert snapshot["totals"]["local_blocked"] == 1
    assert snapshot["actions"]["calc-sync"]["allowed"] == 1
    assert snapshot["actions"]["calc-sync"]["blocked"] == 1
    assert snapshot["last_blocked"]["action"] == "calc-sync"
    assert snapshot["last_blocked"]["source"] == "local"


def test_rate_limit_activity_snapshot_tracks_disabled_limits() -> None:
    helpers, *_ = _build_helpers()
    request = types.SimpleNamespace(headers={}, state=types.SimpleNamespace())

    helpers.enforce_rate_limit(request, action="proj-read", limit_per_minute=0)

    snapshot = helpers.rate_limit_activity_snapshot()
    assert snapshot["totals"]["disabled"] == 1
    assert snapshot["actions"]["proj-read"]["disabled"] == 1
