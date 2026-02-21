"""Adapters for runtime rate-limiting, Redis job tracking, and result-cache IO."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException, Request

from backend.core import runtime_infra as core_runtime_infra


@dataclass(slots=True)
class RuntimeCacheJobHelperConfig:
    redis_url: str
    redis_lib: Any | None
    redis_client_state: Any
    logger: Any
    redis_rate_limit_prefix: str
    redis_result_prefix: str
    redis_job_prefix: str
    redis_job_cancel_prefix: str
    redis_active_jobs_prefix: str
    redis_job_client_prefix: str
    calculator_job_ttl_seconds: int
    calc_result_cache_ttl_seconds: int
    request_rate_limit_lock: Any
    request_rate_limit_buckets: dict[tuple[str, str], deque[float]]
    rate_limit_bucket_cleanup_interval_seconds: float
    request_rate_limit_last_sweep_ts_getter: Callable[[], float]
    request_rate_limit_last_sweep_ts_setter: Callable[[float], None]
    calc_result_cache_max_entries_getter: Callable[[], int]
    calc_result_cache_lock: Any
    calc_result_cache: dict[str, tuple[float, dict]]
    calc_result_cache_order: deque[str]
    calculator_jobs: dict[str, dict]
    calculate_api_key_identities_getter: Callable[[], dict[str, str]]
    extract_calculate_api_key: Callable[[Request | None], str | None]
    client_ip: Callable[[Request | None], str]
    require_calculate_auth_getter: Callable[[], bool]
    calculation_job_public_payload_fn: Callable[[dict], dict]
    redis_client_getter: Callable[[], Any | None] | None = None


class RuntimeCacheJobHelpers:
    def __init__(self, config: RuntimeCacheJobHelperConfig):
        self._config = config

    def calculate_rate_limit_identity(self, request: Request | None) -> str:
        return core_runtime_infra.calculate_rate_limit_identity(
            request,
            extract_calculate_api_key=self._config.extract_calculate_api_key,
            calculate_api_key_identities=self._config.calculate_api_key_identities_getter(),
            client_ip=self._config.client_ip,
        )

    def authorize_calculate_request(self, request: Request) -> None:
        core_runtime_infra.authorize_calculate_request(
            request,
            extract_calculate_api_key=self._config.extract_calculate_api_key,
            calculate_api_key_identities=self._config.calculate_api_key_identities_getter(),
            client_ip=self._config.client_ip,
            require_calculate_auth=self._config.require_calculate_auth_getter(),
        )

    def prune_rate_limit_bucket(self, bucket: deque[float], *, window_start: float) -> None:
        core_runtime_infra.prune_rate_limit_bucket(bucket, window_start=window_start)

    def cleanup_rate_limit_buckets_locked(self, *, now: float, window_start: float) -> None:
        updated_sweep_ts = core_runtime_infra.cleanup_rate_limit_buckets_locked(
            rate_limit_buckets=self._config.request_rate_limit_buckets,
            now=now,
            window_start=window_start,
            cleanup_interval_seconds=self._config.rate_limit_bucket_cleanup_interval_seconds,
            last_sweep_ts=self._config.request_rate_limit_last_sweep_ts_getter(),
        )
        self._config.request_rate_limit_last_sweep_ts_setter(updated_sweep_ts)

    def rate_limit_exceeded(self, action: str) -> HTTPException:
        return core_runtime_infra.rate_limit_exceeded(action)

    def enforce_rate_limit(self, request: Request, *, action: str, limit_per_minute: int) -> None:
        core_runtime_infra.enforce_rate_limit(
            request,
            action=action,
            limit_per_minute=limit_per_minute,
            redis_rate_limit_prefix=self._config.redis_rate_limit_prefix,
            redis_client_getter=self.redis_client,
            calculate_rate_limit_identity=self.calculate_rate_limit_identity,
            request_rate_limit_lock=self._config.request_rate_limit_lock,
            request_rate_limit_buckets=self._config.request_rate_limit_buckets,
            cleanup_rate_limit_buckets_locked=lambda now, window_start: self.cleanup_rate_limit_buckets_locked(
                now=now, window_start=window_start
            ),
            prune_rate_limit_bucket=lambda bucket, window_start: self.prune_rate_limit_bucket(
                bucket, window_start=window_start
            ),
            rate_limit_exceeded=self.rate_limit_exceeded,
            logger=self._config.logger,
        )

    def rate_limit_bucket_count(self) -> int:
        return core_runtime_infra.rate_limit_bucket_count(
            request_rate_limit_lock=self._config.request_rate_limit_lock,
            request_rate_limit_buckets=self._config.request_rate_limit_buckets,
        )

    def redis_client(self) -> Any | None:
        if self._config.redis_client_getter is not None:
            return self._config.redis_client_getter()
        return core_runtime_infra.get_redis_client(
            redis_url=self._config.redis_url,
            redis_lib=self._config.redis_lib,
            state=self._config.redis_client_state,
            logger=self._config.logger,
        )

    def redis_active_jobs_key(self, client_ip: str) -> str:
        return core_runtime_infra.redis_active_jobs_key(
            redis_active_jobs_prefix=self._config.redis_active_jobs_prefix,
            client_ip=client_ip,
        )

    def redis_job_client_key(self, job_id: str) -> str:
        return core_runtime_infra.redis_job_client_key(
            redis_job_client_prefix=self._config.redis_job_client_prefix,
            job_id=job_id,
        )

    def redis_job_cancel_key(self, job_id: str) -> str:
        return core_runtime_infra.redis_job_cancel_key(
            redis_job_cancel_prefix=self._config.redis_job_cancel_prefix,
            job_id=job_id,
        )

    def track_active_job(self, job_id: str, client_ip: str) -> None:
        core_runtime_infra.track_active_job(
            job_id,
            client_ip,
            redis_client_getter=self.redis_client,
            redis_active_jobs_prefix=self._config.redis_active_jobs_prefix,
            redis_job_client_prefix=self._config.redis_job_client_prefix,
            calculator_job_ttl_seconds=self._config.calculator_job_ttl_seconds,
            logger=self._config.logger,
        )

    def job_client_ip(self, job_id: str) -> str | None:
        return core_runtime_infra.job_client_ip(
            job_id,
            redis_client_getter=self.redis_client,
            redis_job_client_prefix=self._config.redis_job_client_prefix,
            logger=self._config.logger,
        )

    def untrack_active_job(self, job_id: str, client_ip: str | None = None) -> None:
        core_runtime_infra.untrack_active_job(
            job_id,
            client_ip,
            redis_client_getter=self.redis_client,
            redis_active_jobs_prefix=self._config.redis_active_jobs_prefix,
            redis_job_client_prefix=self._config.redis_job_client_prefix,
            job_client_ip_resolver=self.job_client_ip,
            logger=self._config.logger,
        )

    def set_job_cancel_requested(self, job_id: str) -> None:
        core_runtime_infra.set_job_cancel_requested(
            job_id,
            redis_client_getter=self.redis_client,
            redis_job_cancel_prefix=self._config.redis_job_cancel_prefix,
            calculator_job_ttl_seconds=self._config.calculator_job_ttl_seconds,
            logger=self._config.logger,
        )

    def clear_job_cancel_requested(self, job_id: str) -> None:
        core_runtime_infra.clear_job_cancel_requested(
            job_id,
            redis_client_getter=self.redis_client,
            redis_job_cancel_prefix=self._config.redis_job_cancel_prefix,
            logger=self._config.logger,
        )

    def job_cancel_requested(self, job_id: str) -> bool:
        return core_runtime_infra.job_cancel_requested(
            job_id,
            redis_client_getter=self.redis_client,
            redis_job_cancel_prefix=self._config.redis_job_cancel_prefix,
            logger=self._config.logger,
        )

    def active_jobs_for_ip(self, client_ip: str) -> int:
        return core_runtime_infra.active_jobs_for_ip(
            client_ip,
            redis_client_getter=self.redis_client,
            redis_active_jobs_prefix=self._config.redis_active_jobs_prefix,
            redis_job_client_prefix=self._config.redis_job_client_prefix,
            calculator_jobs=self._config.calculator_jobs,
            logger=self._config.logger,
        )

    def cleanup_local_result_cache(self, now_ts: float | None = None) -> None:
        core_runtime_infra.cleanup_local_result_cache(
            self._config.calc_result_cache,
            self._config.calc_result_cache_order,
            max_entries=self._config.calc_result_cache_max_entries_getter(),
            now_ts=now_ts,
        )

    def touch_local_result_cache_key(self, cache_key: str) -> None:
        core_runtime_infra.touch_local_result_cache_key(self._config.calc_result_cache_order, cache_key)

    def result_cache_get(self, cache_key: str) -> dict | None:
        return core_runtime_infra.result_cache_get(
            cache_key,
            redis_client_getter=self.redis_client,
            redis_result_prefix=self._config.redis_result_prefix,
            logger=self._config.logger,
            local_cache=self._config.calc_result_cache,
            local_cache_lock=self._config.calc_result_cache_lock,
            cleanup_local_result_cache_fn=self.cleanup_local_result_cache,
            touch_local_result_cache_key_fn=self.touch_local_result_cache_key,
        )

    def result_cache_set(self, cache_key: str, payload: dict) -> None:
        core_runtime_infra.result_cache_set(
            cache_key,
            payload,
            redis_client_getter=self.redis_client,
            redis_result_prefix=self._config.redis_result_prefix,
            cache_ttl_seconds=self._config.calc_result_cache_ttl_seconds,
            logger=self._config.logger,
            local_cache=self._config.calc_result_cache,
            local_cache_lock=self._config.calc_result_cache_lock,
            touch_local_result_cache_key_fn=self.touch_local_result_cache_key,
            cleanup_local_result_cache_fn=self.cleanup_local_result_cache,
        )

    def cache_calculation_job_snapshot(self, job: dict) -> None:
        core_runtime_infra.cache_calculation_job_snapshot(
            job,
            redis_client_getter=self.redis_client,
            redis_job_prefix=self._config.redis_job_prefix,
            job_ttl_seconds=self._config.calculator_job_ttl_seconds,
            logger=self._config.logger,
            calculation_job_public_payload_fn=self._config.calculation_job_public_payload_fn,
        )

    def cached_calculation_job_snapshot(self, job_id: str) -> dict | None:
        return core_runtime_infra.cached_calculation_job_snapshot(
            job_id,
            redis_client_getter=self.redis_client,
            redis_job_prefix=self._config.redis_job_prefix,
            logger=self._config.logger,
        )


def build_runtime_cache_job_helpers(config: RuntimeCacheJobHelperConfig) -> RuntimeCacheJobHelpers:
    return RuntimeCacheJobHelpers(config)
