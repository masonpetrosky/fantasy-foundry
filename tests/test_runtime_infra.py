import types
import unittest
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException

from backend.core import runtime_infra


class _Logger:
    def __init__(self) -> None:
        self.warning_calls = 0
        self.info_calls = 0

    def warning(self, _message: str, exc_info: bool = False) -> None:
        _ = exc_info
        self.warning_calls += 1

    def info(self, _message: str) -> None:
        self.info_calls += 1


class _RedisPipeline:
    def __init__(self, redis: "_FakeRedis") -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple]] = []

    def sadd(self, key: str, *values: str):
        self._ops.append(("sadd", (key, *values)))
        return self

    def expire(self, key: str, ttl: int):
        self._ops.append(("expire", (key, ttl)))
        return self

    def setex(self, key: str, ttl: int, value: str):
        self._ops.append(("setex", (key, ttl, value)))
        return self

    def srem(self, key: str, *values: str):
        self._ops.append(("srem", (key, *values)))
        return self

    def delete(self, key: str):
        self._ops.append(("delete", (key,)))
        return self

    def exists(self, key: str):
        self._ops.append(("exists", (key,)))
        return self

    def execute(self):
        results = []
        for op, args in self._ops:
            method = getattr(self._redis, op)
            results.append(method(*args))
        self._ops.clear()
        return results


class _FakeRedis:
    def __init__(self) -> None:
        self.strings: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.counters: dict[str, int] = {}

    def incr(self, key: str) -> int:
        self.counters[key] = self.counters.get(key, 0) + 1
        return self.counters[key]

    def expire(self, _key: str, _ttl: int) -> int:
        return 1

    def setex(self, key: str, _ttl: int, value: str) -> int:
        self.strings[key] = value
        return 1

    def get(self, key: str):
        return self.strings.get(key)

    def delete(self, key: str) -> int:
        removed = 0
        if key in self.strings:
            self.strings.pop(key, None)
            removed += 1
        if key in self.sets:
            self.sets.pop(key, None)
            removed += 1
        return removed

    def exists(self, key: str) -> int:
        return int(key in self.strings)

    def sadd(self, key: str, *values: str) -> int:
        bucket = self.sets.setdefault(key, set())
        before = len(bucket)
        bucket.update(values)
        return len(bucket) - before

    def srem(self, key: str, *values: str) -> int:
        bucket = self.sets.setdefault(key, set())
        removed = 0
        for value in values:
            if value in bucket:
                bucket.remove(value)
                removed += 1
        return removed

    def smembers(self, key: str):
        return set(self.sets.get(key, set()))

    def pipeline(self, transaction: bool = False):
        _ = transaction
        return _RedisPipeline(self)


class _FailingRedis(_FakeRedis):
    def incr(self, key: str) -> int:
        _ = key
        raise ConnectionError("boom")

    def smembers(self, key: str):
        _ = key
        raise ConnectionError("boom")


class _RedisLibSuccess:
    class Redis:
        @staticmethod
        def from_url(_url: str, decode_responses: bool = False):
            _ = decode_responses
            return _RedisLibSuccessClient()


class _RedisLibSuccessClient:
    def ping(self) -> None:
        return None


class _RedisLibFailure:
    class Redis:
        @staticmethod
        def from_url(_url: str, decode_responses: bool = False):
            _ = decode_responses
            return _RedisLibFailureClient()


class _RedisLibFailureClient:
    def ping(self) -> None:
        raise ConnectionError("unavailable")


class RuntimeInfraTests(unittest.TestCase):
    def test_get_redis_client_initializes_once_and_caches_client(self) -> None:
        logger = _Logger()
        state = runtime_infra.RedisClientState(lock=Lock())

        first = runtime_infra.get_redis_client(
            redis_url="redis://local",
            redis_lib=_RedisLibSuccess,
            state=state,
            logger=logger,
        )
        second = runtime_infra.get_redis_client(
            redis_url="redis://local",
            redis_lib=_RedisLibSuccess,
            state=state,
            logger=logger,
        )

        self.assertIsNotNone(first)
        self.assertIs(first, second)
        self.assertTrue(state.init_attempted)
        self.assertEqual(logger.info_calls, 1)

    def test_get_redis_client_returns_none_when_ping_fails(self) -> None:
        logger = _Logger()
        state = runtime_infra.RedisClientState(lock=Lock())

        client = runtime_infra.get_redis_client(
            redis_url="redis://local",
            redis_lib=_RedisLibFailure,
            state=state,
            logger=logger,
        )

        self.assertIsNone(client)
        self.assertTrue(state.init_attempted)
        self.assertGreaterEqual(logger.warning_calls, 1)

    def test_get_redis_client_short_circuits_when_url_or_lib_missing(self) -> None:
        logger = _Logger()
        state = runtime_infra.RedisClientState(lock=Lock())

        missing_url = runtime_infra.get_redis_client(
            redis_url="",
            redis_lib=_RedisLibSuccess,
            state=state,
            logger=logger,
        )
        missing_lib = runtime_infra.get_redis_client(
            redis_url="redis://local",
            redis_lib=None,
            state=state,
            logger=logger,
        )

        self.assertIsNone(missing_url)
        self.assertIsNone(missing_lib)
        self.assertFalse(state.init_attempted)

    def test_calculate_rate_limit_identity_prefers_request_state(self) -> None:
        request = types.SimpleNamespace(state=types.SimpleNamespace(calc_rate_limit_identity="api_key:abc"))
        identity = runtime_infra.calculate_rate_limit_identity(
            request,
            extract_calculate_api_key=lambda _request: None,
            calculate_api_key_identities={"key": "api_key:key"},
            client_ip=lambda _request: "198.51.100.1",
        )
        self.assertEqual(identity, "api_key:abc")

    def test_calculate_rate_limit_identity_uses_api_key_map(self) -> None:
        request = types.SimpleNamespace(state=types.SimpleNamespace())
        identity = runtime_infra.calculate_rate_limit_identity(
            request,
            extract_calculate_api_key=lambda _request: "key",
            calculate_api_key_identities={"key": "api_key:key"},
            client_ip=lambda _request: "198.51.100.2",
        )
        self.assertEqual(identity, "api_key:key")

    def test_authorize_calculate_request_sets_identity_for_valid_key(self) -> None:
        request = types.SimpleNamespace(state=types.SimpleNamespace())
        runtime_infra.authorize_calculate_request(
            request,
            extract_calculate_api_key=lambda _request: "key",
            calculate_api_key_identities={"key": "api_key:key"},
            client_ip=lambda _request: "198.51.100.3",
            require_calculate_auth=True,
        )
        self.assertEqual(request.state.calc_rate_limit_identity, "api_key:key")
        self.assertTrue(request.state.calc_api_key_authenticated)

    def test_authorize_calculate_request_rejects_missing_keys_when_required(self) -> None:
        request = types.SimpleNamespace(state=types.SimpleNamespace())
        with self.assertRaises(HTTPException) as ctx:
            runtime_infra.authorize_calculate_request(
                request,
                extract_calculate_api_key=lambda _request: None,
                calculate_api_key_identities={},
                client_ip=lambda _request: "198.51.100.4",
                require_calculate_auth=True,
            )
        self.assertEqual(ctx.exception.status_code, 503)

    def test_authorize_calculate_request_rejects_invalid_key_when_required(self) -> None:
        request = types.SimpleNamespace(state=types.SimpleNamespace())
        with self.assertRaises(HTTPException) as ctx:
            runtime_infra.authorize_calculate_request(
                request,
                extract_calculate_api_key=lambda _request: "bad",
                calculate_api_key_identities={"good": "api_key:good"},
                client_ip=lambda _request: "198.51.100.5",
                require_calculate_auth=True,
            )
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(request.state.calc_rate_limit_identity, "ip:198.51.100.5")
        self.assertFalse(request.state.calc_api_key_authenticated)

    def test_enforce_rate_limit_redis_path_blocks_after_limit(self) -> None:
        redis = _FakeRedis()
        logger = _Logger()
        request = types.SimpleNamespace(state=types.SimpleNamespace())
        buckets = defaultdict(deque)
        lock = Lock()
        last_sweep = {"value": 0.0}

        def cleanup(now: float, window_start: float) -> None:
            last_sweep["value"] = runtime_infra.cleanup_rate_limit_buckets_locked(
                rate_limit_buckets=buckets,
                now=now,
                window_start=window_start,
                cleanup_interval_seconds=60.0,
                last_sweep_ts=last_sweep["value"],
            )

        runtime_infra.enforce_rate_limit(
            request,
            action="calc-sync",
            limit_per_minute=1,
            redis_rate_limit_prefix="ff:rl:",
            redis_client_getter=lambda: redis,
            calculate_rate_limit_identity=lambda _request: "ip:198.51.100.6",
            request_rate_limit_lock=lock,
            request_rate_limit_buckets=buckets,
            cleanup_rate_limit_buckets_locked=cleanup,
            prune_rate_limit_bucket=lambda bucket, window_start: runtime_infra.prune_rate_limit_bucket(
                bucket, window_start=window_start
            ),
            rate_limit_exceeded=runtime_infra.rate_limit_exceeded,
            logger=logger,
        )

        with self.assertRaises(HTTPException) as ctx:
            runtime_infra.enforce_rate_limit(
                request,
                action="calc-sync",
                limit_per_minute=1,
                redis_rate_limit_prefix="ff:rl:",
                redis_client_getter=lambda: redis,
                calculate_rate_limit_identity=lambda _request: "ip:198.51.100.6",
                request_rate_limit_lock=lock,
                request_rate_limit_buckets=buckets,
                cleanup_rate_limit_buckets_locked=cleanup,
                prune_rate_limit_bucket=lambda bucket, window_start: runtime_infra.prune_rate_limit_bucket(
                    bucket, window_start=window_start
                ),
                rate_limit_exceeded=runtime_infra.rate_limit_exceeded,
                logger=logger,
            )
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertEqual(logger.warning_calls, 0)

    def test_enforce_rate_limit_falls_back_to_local_when_redis_fails(self) -> None:
        redis = _FailingRedis()
        logger = _Logger()
        request = types.SimpleNamespace(state=types.SimpleNamespace())
        buckets = defaultdict(deque)
        lock = Lock()
        last_sweep = {"value": 0.0}

        def cleanup(now: float, window_start: float) -> None:
            last_sweep["value"] = runtime_infra.cleanup_rate_limit_buckets_locked(
                rate_limit_buckets=buckets,
                now=now,
                window_start=window_start,
                cleanup_interval_seconds=60.0,
                last_sweep_ts=last_sweep["value"],
            )

        runtime_infra.enforce_rate_limit(
            request,
            action="proj-read",
            limit_per_minute=1,
            redis_rate_limit_prefix="ff:rl:",
            redis_client_getter=lambda: redis,
            calculate_rate_limit_identity=lambda _request: "ip:198.51.100.7",
            request_rate_limit_lock=lock,
            request_rate_limit_buckets=buckets,
            cleanup_rate_limit_buckets_locked=cleanup,
            prune_rate_limit_bucket=lambda bucket, window_start: runtime_infra.prune_rate_limit_bucket(
                bucket, window_start=window_start
            ),
            rate_limit_exceeded=runtime_infra.rate_limit_exceeded,
            logger=logger,
        )

        with self.assertRaises(HTTPException):
            runtime_infra.enforce_rate_limit(
                request,
                action="proj-read",
                limit_per_minute=1,
                redis_rate_limit_prefix="ff:rl:",
                redis_client_getter=lambda: redis,
                calculate_rate_limit_identity=lambda _request: "ip:198.51.100.7",
                request_rate_limit_lock=lock,
                request_rate_limit_buckets=buckets,
                cleanup_rate_limit_buckets_locked=cleanup,
                prune_rate_limit_bucket=lambda bucket, window_start: runtime_infra.prune_rate_limit_bucket(
                    bucket, window_start=window_start
                ),
                rate_limit_exceeded=runtime_infra.rate_limit_exceeded,
                logger=logger,
            )
        self.assertGreaterEqual(logger.warning_calls, 1)

    def test_enforce_rate_limit_reports_decisions_with_callback(self) -> None:
        redis = _FakeRedis()
        logger = _Logger()
        request = types.SimpleNamespace(state=types.SimpleNamespace())
        buckets = defaultdict(deque)
        lock = Lock()
        events: list[dict[str, object]] = []

        runtime_infra.enforce_rate_limit(
            request,
            action="calc-sync",
            limit_per_minute=1,
            redis_rate_limit_prefix="ff:rl:",
            redis_client_getter=lambda: redis,
            calculate_rate_limit_identity=lambda _request: "ip:198.51.100.12",
            request_rate_limit_lock=lock,
            request_rate_limit_buckets=buckets,
            cleanup_rate_limit_buckets_locked=lambda _now, _window_start: None,
            prune_rate_limit_bucket=lambda bucket, window_start: runtime_infra.prune_rate_limit_bucket(
                bucket, window_start=window_start
            ),
            rate_limit_exceeded=runtime_infra.rate_limit_exceeded,
            logger=logger,
            on_decision=events.append,
        )

        with self.assertRaises(HTTPException):
            runtime_infra.enforce_rate_limit(
                request,
                action="calc-sync",
                limit_per_minute=1,
                redis_rate_limit_prefix="ff:rl:",
                redis_client_getter=lambda: redis,
                calculate_rate_limit_identity=lambda _request: "ip:198.51.100.12",
                request_rate_limit_lock=lock,
                request_rate_limit_buckets=buckets,
                cleanup_rate_limit_buckets_locked=lambda _now, _window_start: None,
                prune_rate_limit_bucket=lambda bucket, window_start: runtime_infra.prune_rate_limit_bucket(
                    bucket, window_start=window_start
                ),
                rate_limit_exceeded=runtime_infra.rate_limit_exceeded,
                logger=logger,
                on_decision=events.append,
            )

        self.assertEqual(events[0]["source"], "redis")
        self.assertEqual(events[0]["outcome"], "allowed")
        self.assertEqual(events[1]["source"], "redis")
        self.assertEqual(events[1]["outcome"], "blocked")

    def test_enforce_rate_limit_reports_fallback_and_local_decisions(self) -> None:
        redis = _FailingRedis()
        logger = _Logger()
        request = types.SimpleNamespace(state=types.SimpleNamespace())
        buckets = defaultdict(deque)
        lock = Lock()
        events: list[dict[str, object]] = []

        runtime_infra.enforce_rate_limit(
            request,
            action="proj-read",
            limit_per_minute=1,
            redis_rate_limit_prefix="ff:rl:",
            redis_client_getter=lambda: redis,
            calculate_rate_limit_identity=lambda _request: "ip:198.51.100.13",
            request_rate_limit_lock=lock,
            request_rate_limit_buckets=buckets,
            cleanup_rate_limit_buckets_locked=lambda _now, _window_start: None,
            prune_rate_limit_bucket=lambda bucket, window_start: runtime_infra.prune_rate_limit_bucket(
                bucket, window_start=window_start
            ),
            rate_limit_exceeded=runtime_infra.rate_limit_exceeded,
            logger=logger,
            on_decision=events.append,
        )

        with self.assertRaises(HTTPException):
            runtime_infra.enforce_rate_limit(
                request,
                action="proj-read",
                limit_per_minute=1,
                redis_rate_limit_prefix="ff:rl:",
                redis_client_getter=lambda: redis,
                calculate_rate_limit_identity=lambda _request: "ip:198.51.100.13",
                request_rate_limit_lock=lock,
                request_rate_limit_buckets=buckets,
                cleanup_rate_limit_buckets_locked=lambda _now, _window_start: None,
                prune_rate_limit_bucket=lambda bucket, window_start: runtime_infra.prune_rate_limit_bucket(
                    bucket, window_start=window_start
                ),
                rate_limit_exceeded=runtime_infra.rate_limit_exceeded,
                logger=logger,
                on_decision=events.append,
            )

        sources_and_outcomes = {(event["source"], event["outcome"]) for event in events}
        self.assertIn(("redis", "fallback"), sources_and_outcomes)
        self.assertIn(("local", "allowed"), sources_and_outcomes)
        self.assertIn(("local", "blocked"), sources_and_outcomes)

    def test_enforce_rate_limit_reports_disabled_decision(self) -> None:
        logger = _Logger()
        request = types.SimpleNamespace(state=types.SimpleNamespace())
        events: list[dict[str, object]] = []

        runtime_infra.enforce_rate_limit(
            request,
            action="proj-read",
            limit_per_minute=0,
            redis_rate_limit_prefix="ff:rl:",
            redis_client_getter=lambda: None,
            calculate_rate_limit_identity=lambda _request: "ip:198.51.100.14",
            request_rate_limit_lock=Lock(),
            request_rate_limit_buckets=defaultdict(deque),
            cleanup_rate_limit_buckets_locked=lambda _now, _window_start: None,
            prune_rate_limit_bucket=lambda _bucket, _window_start: None,
            rate_limit_exceeded=runtime_infra.rate_limit_exceeded,
            logger=logger,
            on_decision=events.append,
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "proj-read")
        self.assertEqual(events[0]["identity"], "ip:198.51.100.14")
        self.assertEqual(events[0]["source"], "disabled")
        self.assertEqual(events[0]["outcome"], "disabled")
        self.assertEqual(events[0]["limit_per_minute"], 0)
        self.assertIsInstance(events[0]["timestamp_epoch_s"], float)

    def test_track_untrack_and_cancel_markers_round_trip(self) -> None:
        redis = _FakeRedis()
        logger = _Logger()

        runtime_infra.track_active_job(
            "job-1",
            "198.51.100.8",
            redis_client_getter=lambda: redis,
            redis_active_jobs_prefix="ff:active:",
            redis_job_client_prefix="ff:client:",
            calculator_job_ttl_seconds=60,
            logger=logger,
        )
        self.assertIn("job-1", redis.smembers("ff:active:198.51.100.8"))
        self.assertEqual(redis.get("ff:client:job-1"), "198.51.100.8")

        runtime_infra.set_job_cancel_requested(
            "job-1",
            redis_client_getter=lambda: redis,
            redis_job_cancel_prefix="ff:cancel:",
            calculator_job_ttl_seconds=60,
            logger=logger,
        )
        self.assertTrue(
            runtime_infra.job_cancel_requested(
                "job-1",
                redis_client_getter=lambda: redis,
                redis_job_cancel_prefix="ff:cancel:",
                logger=logger,
            )
        )

        runtime_infra.clear_job_cancel_requested(
            "job-1",
            redis_client_getter=lambda: redis,
            redis_job_cancel_prefix="ff:cancel:",
            logger=logger,
        )
        self.assertFalse(
            runtime_infra.job_cancel_requested(
                "job-1",
                redis_client_getter=lambda: redis,
                redis_job_cancel_prefix="ff:cancel:",
                logger=logger,
            )
        )

        runtime_infra.untrack_active_job(
            "job-1",
            None,
            redis_client_getter=lambda: redis,
            redis_active_jobs_prefix="ff:active:",
            redis_job_client_prefix="ff:client:",
            job_client_ip_resolver=lambda job_id: runtime_infra.job_client_ip(
                job_id,
                redis_client_getter=lambda: redis,
                redis_job_client_prefix="ff:client:",
                logger=logger,
            ),
            logger=logger,
        )
        self.assertNotIn("job-1", redis.smembers("ff:active:198.51.100.8"))

    def test_active_jobs_for_ip_removes_stale_ids(self) -> None:
        redis = _FakeRedis()
        logger = _Logger()
        redis.sadd("ff:active:198.51.100.9", "job-live", "job-stale")
        redis.setex("ff:client:job-live", 60, "198.51.100.9")

        live_count = runtime_infra.active_jobs_for_ip(
            "198.51.100.9",
            redis_client_getter=lambda: redis,
            redis_active_jobs_prefix="ff:active:",
            redis_job_client_prefix="ff:client:",
            calculator_jobs={},
            logger=logger,
        )
        self.assertEqual(live_count, 1)
        self.assertEqual(redis.smembers("ff:active:198.51.100.9"), {"job-live"})

    def test_active_jobs_for_ip_falls_back_to_local_on_redis_error(self) -> None:
        redis = _FailingRedis()
        logger = _Logger()
        local_jobs = {
            "queued": {"job_id": "queued", "client_ip": "198.51.100.10", "status": "queued"},
            "running": {"job_id": "running", "client_ip": "198.51.100.10", "status": "running"},
            "done": {"job_id": "done", "client_ip": "198.51.100.10", "status": "completed"},
        }
        live_count = runtime_infra.active_jobs_for_ip(
            "198.51.100.10",
            redis_client_getter=lambda: redis,
            redis_active_jobs_prefix="ff:active:",
            redis_job_client_prefix="ff:client:",
            calculator_jobs=local_jobs,
            logger=logger,
        )
        self.assertEqual(live_count, 2)
        self.assertGreaterEqual(logger.warning_calls, 1)

    def test_result_cache_get_set_and_job_snapshot_round_trip(self) -> None:
        redis = _FakeRedis()
        logger = _Logger()
        local_cache: dict[str, tuple[float, dict]] = {}
        local_cache_order: deque[str] = deque()
        local_lock = Lock()

        def cleanup(now_ts: float | None) -> None:
            runtime_infra.cleanup_local_result_cache(
                local_cache,
                local_cache_order,
                max_entries=16,
                now_ts=now_ts,
            )

        def touch(cache_key: str) -> None:
            runtime_infra.touch_local_result_cache_key(local_cache_order, cache_key)

        runtime_infra.result_cache_set(
            "cache-key",
            {"value": 7},
            redis_client_getter=lambda: redis,
            redis_result_prefix="ff:result:",
            cache_ttl_seconds=60,
            logger=logger,
            local_cache=local_cache,
            local_cache_lock=local_lock,
            touch_local_result_cache_key_fn=touch,
            cleanup_local_result_cache_fn=cleanup,
        )
        cached = runtime_infra.result_cache_get(
            "cache-key",
            redis_client_getter=lambda: redis,
            redis_result_prefix="ff:result:",
            logger=logger,
            local_cache=local_cache,
            local_cache_lock=local_lock,
            cleanup_local_result_cache_fn=cleanup,
            touch_local_result_cache_key_fn=touch,
        )
        self.assertEqual(cached, {"value": 7})

        runtime_infra.cache_calculation_job_snapshot(
            {"job_id": "job-cache", "status": "completed", "result": {"value": 1}},
            redis_client_getter=lambda: redis,
            redis_job_prefix="ff:job:",
            job_ttl_seconds=60,
            logger=logger,
            calculation_job_public_payload_fn=lambda job: {"job_id": job["job_id"], "status": job["status"]},
        )
        snapshot = runtime_infra.cached_calculation_job_snapshot(
            "job-cache",
            redis_client_getter=lambda: redis,
            redis_job_prefix="ff:job:",
            logger=logger,
        )
        self.assertEqual(snapshot, {"job_id": "job-cache", "status": "completed"})
