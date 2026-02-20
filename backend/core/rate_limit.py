"""In-memory rate limiting helpers."""

from __future__ import annotations

from collections import deque


def prune_rate_limit_bucket(bucket: deque[float], *, window_start: float) -> None:
    while bucket and bucket[0] < window_start:
        bucket.popleft()


def cleanup_rate_limit_buckets_locked(
    *,
    rate_limit_buckets: dict[tuple[str, str], deque[float]],
    now: float,
    window_start: float,
    cleanup_interval_seconds: float,
    last_sweep_ts: float,
) -> float:
    if now - last_sweep_ts < cleanup_interval_seconds:
        return last_sweep_ts

    for key, bucket in list(rate_limit_buckets.items()):
        prune_rate_limit_bucket(bucket, window_start=window_start)
        if not bucket:
            rate_limit_buckets.pop(key, None)
    return now
