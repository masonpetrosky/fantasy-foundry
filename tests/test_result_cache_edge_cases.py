"""Tests for result cache edge cases and failure modes."""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from threading import Lock
from unittest.mock import MagicMock

from backend.core.result_cache import (
    cache_calculation_job_snapshot,
    calc_result_cache_key,
    cleanup_local_result_cache,
    result_cache_get,
    result_cache_set,
    touch_local_result_cache_key,
)


def test_calc_result_cache_key_is_deterministic() -> None:
    settings = {"teams": 12, "mode": "roto"}
    key1 = calc_result_cache_key(settings)
    key2 = calc_result_cache_key(settings)
    assert key1 == key2
    assert key1.startswith("v3:")


def test_calc_result_cache_key_different_for_different_settings() -> None:
    key1 = calc_result_cache_key({"teams": 12})
    key2 = calc_result_cache_key({"teams": 14})
    assert key1 != key2


def test_cleanup_local_result_cache_removes_expired() -> None:
    now = time.time()
    cache: dict[str, tuple[float, dict]] = {
        "fresh": (now + 100, {"data": 1}),
        "expired": (now - 10, {"data": 2}),
    }
    order: deque[str] = deque(["expired", "fresh"])

    cleanup_local_result_cache(cache, order, max_entries=100, now_ts=now)

    assert "fresh" in cache
    assert "expired" not in cache
    assert list(order) == ["fresh"]


def test_cleanup_local_result_cache_evicts_oldest_when_over_max() -> None:
    now = time.time()
    cache: dict[str, tuple[float, dict]] = {
        "a": (now + 100, {}),
        "b": (now + 200, {}),
        "c": (now + 300, {}),
    }
    order: deque[str] = deque(["a", "b", "c"])

    cleanup_local_result_cache(cache, order, max_entries=2, now_ts=now)

    assert len(cache) <= 2
    assert "a" not in cache  # oldest evicted


def test_touch_local_result_cache_key_moves_to_end() -> None:
    order: deque[str] = deque(["a", "b", "c"])
    touch_local_result_cache_key(order, "a")
    assert list(order) == ["b", "c", "a"]


def test_touch_local_result_cache_key_new_key() -> None:
    order: deque[str] = deque(["a", "b"])
    touch_local_result_cache_key(order, "new")
    assert list(order) == ["a", "b", "new"]


def test_result_cache_get_redis_returns_non_dict() -> None:
    """When Redis returns a JSON array instead of dict, fall back to local cache."""
    mock_redis = MagicMock()
    mock_redis.get.return_value = json.dumps([1, 2, 3])

    logger = logging.getLogger("test")
    cache: dict[str, tuple[float, dict]] = {}
    lock = Lock()

    result = result_cache_get(
        "test_key",
        redis_client=mock_redis,
        redis_result_prefix="result:",
        logger=logger,
        local_cache=cache,
        local_cache_lock=lock,
        cleanup_local_result_cache_fn=lambda _: None,
        touch_local_result_cache_key_fn=lambda _: None,
    )
    assert result is None


def test_result_cache_get_redis_connection_error_falls_back() -> None:
    """When Redis raises ConnectionError, fall back to local cache."""
    mock_redis = MagicMock()
    mock_redis.get.side_effect = ConnectionError("Connection refused")

    now = time.time()
    cache: dict[str, tuple[float, dict]] = {
        "test_key": (now + 300, {"value": 42}),
    }
    lock = Lock()

    result = result_cache_get(
        "test_key",
        redis_client=mock_redis,
        redis_result_prefix="result:",
        logger=logging.getLogger("test"),
        local_cache=cache,
        local_cache_lock=lock,
        cleanup_local_result_cache_fn=lambda _: None,
        touch_local_result_cache_key_fn=lambda _: None,
    )
    assert result == {"value": 42}


def test_result_cache_get_redis_invalid_json_falls_back() -> None:
    """When Redis returns invalid JSON, fall back to local cache."""
    mock_redis = MagicMock()
    mock_redis.get.side_effect = ValueError("bad json")

    cache: dict[str, tuple[float, dict]] = {}
    lock = Lock()

    result = result_cache_get(
        "test_key",
        redis_client=mock_redis,
        redis_result_prefix="result:",
        logger=logging.getLogger("test"),
        local_cache=cache,
        local_cache_lock=lock,
        cleanup_local_result_cache_fn=lambda _: None,
        touch_local_result_cache_key_fn=lambda _: None,
    )
    assert result is None


def test_result_cache_get_expired_local_entry() -> None:
    """Expired local cache entries should return None and be removed."""
    now = time.time()
    cache: dict[str, tuple[float, dict]] = {
        "test_key": (now - 10, {"value": "stale"}),
    }
    lock = Lock()

    result = result_cache_get(
        "test_key",
        redis_client=None,
        redis_result_prefix="result:",
        logger=logging.getLogger("test"),
        local_cache=cache,
        local_cache_lock=lock,
        cleanup_local_result_cache_fn=lambda _: None,
        touch_local_result_cache_key_fn=lambda _: None,
    )
    assert result is None
    assert "test_key" not in cache


def test_result_cache_set_redis_write_failure_still_writes_local() -> None:
    """Redis write failure should not prevent local cache write."""
    mock_redis = MagicMock()
    mock_redis.setex.side_effect = ConnectionError("Connection refused")

    cache: dict[str, tuple[float, dict]] = {}
    lock = Lock()

    result_cache_set(
        "test_key",
        {"value": 99},
        redis_client=mock_redis,
        redis_result_prefix="result:",
        cache_ttl_seconds=300,
        logger=logging.getLogger("test"),
        local_cache=cache,
        local_cache_lock=lock,
        touch_local_result_cache_key_fn=lambda _: None,
        cleanup_local_result_cache_fn=lambda _: None,
    )
    assert "test_key" in cache
    assert cache["test_key"][1] == {"value": 99}


def test_result_cache_set_redis_serialization_failure_still_writes_local() -> None:
    """Redis serialization failures should not prevent local cache write."""
    mock_redis = MagicMock()
    mock_redis.setex.side_effect = ValueError("bad payload")

    cache: dict[str, tuple[float, dict]] = {}
    lock = Lock()

    result_cache_set(
        "test_key",
        {"value": 99},
        redis_client=mock_redis,
        redis_result_prefix="result:",
        cache_ttl_seconds=300,
        logger=logging.getLogger("test"),
        local_cache=cache,
        local_cache_lock=lock,
        touch_local_result_cache_key_fn=lambda _: None,
        cleanup_local_result_cache_fn=lambda _: None,
    )

    assert "test_key" in cache
    assert cache["test_key"][1] == {"value": 99}


def test_cache_calculation_job_snapshot_swallows_redis_serialization_failure() -> None:
    """Redis serialization failures should not escape the job snapshot helper."""
    mock_redis = MagicMock()
    mock_redis.setex.side_effect = TypeError("bad payload")

    cache_calculation_job_snapshot(
        {"job_id": "job-1", "status": "completed", "result": {"value": 1}},
        redis_client=mock_redis,
        redis_job_prefix="job:",
        job_ttl_seconds=300,
        logger=logging.getLogger("test"),
        calculation_job_public_payload_fn=lambda job: job,
    )
