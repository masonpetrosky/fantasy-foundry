"""Lightweight in-process metrics collector.

Zero-dependency, thread-safe counters and latency histograms with fixed-size
ring buffers to bound memory usage.  Exposes a snapshot method suitable for
returning as JSON from a ``/api/metrics`` endpoint.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any


class MetricsCollector:
    """Thread-safe request metrics collector with ring-buffer histograms."""

    def __init__(self, *, latency_buffer_size: int = 1000) -> None:
        self._lock = threading.Lock()
        self._start_time = time.monotonic()

        # Counters
        self._request_count: int = 0
        self._error_count_4xx: int = 0
        self._error_count_5xx: int = 0
        self._rate_limit_count: int = 0

        # Status code breakdown
        self._status_counts: dict[int, int] = {}

        # Route group breakdown
        self._route_counts: dict[str, int] = {}

        # Latency ring buffer (stores seconds)
        self._latency_buffer: deque[float] = deque(maxlen=latency_buffer_size)

        # Slow request threshold (seconds)
        self._slow_request_threshold: float = 5.0
        self._slow_request_count: int = 0

    def record_request(
        self,
        *,
        status_code: int,
        duration_seconds: float,
        route_group: str = "unknown",
    ) -> None:
        """Record a completed API request."""
        with self._lock:
            self._request_count += 1
            self._latency_buffer.append(duration_seconds)

            self._status_counts[status_code] = self._status_counts.get(status_code, 0) + 1
            self._route_counts[route_group] = self._route_counts.get(route_group, 0) + 1

            if 400 <= status_code < 500:
                self._error_count_4xx += 1
                if status_code == 429:
                    self._rate_limit_count += 1
            elif status_code >= 500:
                self._error_count_5xx += 1

            if duration_seconds >= self._slow_request_threshold:
                self._slow_request_count += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable metrics snapshot."""
        with self._lock:
            latencies = sorted(self._latency_buffer)
            percentiles = _compute_percentiles(latencies)

            return {
                "uptime_seconds": round(time.monotonic() - self._start_time, 1),
                "requests": {
                    "total": self._request_count,
                    "errors_4xx": self._error_count_4xx,
                    "errors_5xx": self._error_count_5xx,
                    "rate_limited": self._rate_limit_count,
                    "slow": self._slow_request_count,
                },
                "latency_ms": percentiles,
                "status_codes": dict(self._status_counts),
                "routes": dict(self._route_counts),
            }


def _compute_percentiles(sorted_values: list[float]) -> dict[str, float | None]:
    """Compute p50, p95, p99 from a sorted list of latency values (seconds -> ms)."""
    n = len(sorted_values)
    if n == 0:
        return {"p50": None, "p95": None, "p99": None}

    def _pct(p: float) -> float:
        idx = int(p * n)
        idx = min(idx, n - 1)
        return round(sorted_values[idx] * 1000.0, 2)

    return {"p50": _pct(0.5), "p95": _pct(0.95), "p99": _pct(0.99)}
