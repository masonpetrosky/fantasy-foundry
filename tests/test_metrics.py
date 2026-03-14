"""Tests for the lightweight metrics collector."""

import threading

from backend.core.metrics import MetricsCollector


def test_empty_snapshot():
    mc = MetricsCollector()
    snap = mc.snapshot()
    assert snap["requests"]["total"] == 0
    assert snap["latency_ms"]["p50"] is None


def test_record_request_counts():
    mc = MetricsCollector()
    mc.record_request(status_code=200, duration_seconds=0.05, route_group="projections")
    mc.record_request(status_code=429, duration_seconds=0.01, route_group="calculate")
    mc.record_request(status_code=500, duration_seconds=0.1, route_group="calculate")

    snap = mc.snapshot()
    assert snap["requests"]["total"] == 3
    assert snap["requests"]["errors_4xx"] == 1
    assert snap["requests"]["errors_5xx"] == 1
    assert snap["requests"]["rate_limited"] == 1
    assert snap["status_codes"] == {200: 1, 429: 1, 500: 1}
    assert snap["routes"]["projections"] == 1
    assert snap["routes"]["calculate"] == 2


def test_latency_percentiles():
    mc = MetricsCollector()
    for i in range(100):
        mc.record_request(status_code=200, duration_seconds=(i + 1) / 1000.0)

    snap = mc.snapshot()
    assert snap["latency_ms"]["p50"] is not None
    assert snap["latency_ms"]["p50"] > 0
    assert snap["latency_ms"]["p99"] >= snap["latency_ms"]["p50"]


def test_slow_request_tracking():
    mc = MetricsCollector()
    mc.record_request(status_code=200, duration_seconds=6.0, route_group="calculate")
    mc.record_request(status_code=200, duration_seconds=0.1, route_group="projections")

    snap = mc.snapshot()
    assert snap["requests"]["slow"] == 1


def test_ring_buffer_bounds():
    mc = MetricsCollector(latency_buffer_size=10)
    for i in range(50):
        mc.record_request(status_code=200, duration_seconds=0.01)

    snap = mc.snapshot()
    assert snap["requests"]["total"] == 50
    # Latency buffer only keeps last 10
    assert snap["latency_ms"]["p50"] is not None


def test_thread_safety():
    mc = MetricsCollector()

    def record_many():
        for _ in range(100):
            mc.record_request(status_code=200, duration_seconds=0.01)

    threads = [threading.Thread(target=record_many) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    snap = mc.snapshot()
    assert snap["requests"]["total"] == 400


def test_uptime_positive():
    mc = MetricsCollector()
    snap = mc.snapshot()
    assert snap["uptime_seconds"] >= 0
