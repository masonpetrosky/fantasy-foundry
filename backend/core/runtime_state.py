"""Mutable runtime state containers for backend.runtime bootstrap."""

from __future__ import annotations

from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable


@dataclass(slots=True)
class RuntimeMutableState:
    data_source_signature: tuple[tuple[str, int | None, int | None], ...] | None
    data_content_version: str
    data_refresh_lock: Lock
    calculator_job_executor: ThreadPoolExecutor
    calculator_job_lock: Lock
    calculator_jobs: dict[str, dict]
    calculator_prewarm_lock: Lock
    calculator_prewarm_state: dict[str, Any]
    request_rate_limit_lock: Lock
    request_rate_limit_buckets: dict[tuple[str, str], deque[float]]
    request_rate_limit_last_sweep_ts: float
    calc_result_cache_lock: Lock
    calc_result_cache: dict[str, tuple[float, dict]]
    calc_result_cache_order: deque[str]
    redis_client_state: Any


def build_runtime_state(
    *,
    calculator_job_workers: int,
    redis_client_state_factory: Callable[[], Any],
) -> RuntimeMutableState:
    return RuntimeMutableState(
        data_source_signature=None,
        data_content_version="",
        data_refresh_lock=Lock(),
        calculator_job_executor=ThreadPoolExecutor(max_workers=calculator_job_workers),
        calculator_job_lock=Lock(),
        calculator_jobs={},
        calculator_prewarm_lock=Lock(),
        calculator_prewarm_state={
            "status": "idle",
            "started_at": None,
            "completed_at": None,
            "duration_ms": None,
            "error": None,
        },
        request_rate_limit_lock=Lock(),
        request_rate_limit_buckets=defaultdict(deque),
        request_rate_limit_last_sweep_ts=0.0,
        calc_result_cache_lock=Lock(),
        calc_result_cache={},
        calc_result_cache_order=deque(),
        redis_client_state=redis_client_state_factory(),
    )
