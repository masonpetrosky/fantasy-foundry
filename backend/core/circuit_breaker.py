"""Simple circuit breaker for external service calls."""

from __future__ import annotations

import threading
import time
from enum import Enum
from typing import Optional


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Thread-safe circuit breaker with configurable thresholds.

    Usage::

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        if not cb.allow_request():
            raise ExternalServiceError("Circuit open")
        try:
            result = call_external_service()
            cb.record_success()
        except Exception:
            cb.record_failure()
            raise
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "",
    ) -> None:
        self._failure_threshold = max(failure_threshold, 1)
        self._recovery_timeout = max(recovery_timeout, 0.0)
        self._name = name
        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._success_count_half_open = 0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            return self._evaluate_state()

    @property
    def name(self) -> str:
        return self._name

    def _evaluate_state(self) -> CircuitState:
        """Evaluate current state, transitioning OPEN -> HALF_OPEN if timeout elapsed."""
        if self._state == CircuitState.OPEN and self._last_failure_time is not None:
            if time.monotonic() - self._last_failure_time >= self._recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._success_count_half_open = 0
        return self._state

    def allow_request(self) -> bool:
        """Return True if a request should be allowed through."""
        with self._lock:
            state = self._evaluate_state()
            return state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def record_success(self) -> None:
        """Record a successful external call."""
        with self._lock:
            state = self._evaluate_state()
            if state == CircuitState.HALF_OPEN:
                self._success_count_half_open += 1
                if self._success_count_half_open >= 1:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._last_failure_time = None
            elif state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed external call."""
        with self._lock:
            state = self._evaluate_state()
            if state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._last_failure_time = time.monotonic()
            elif state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self._failure_threshold:
                    self._state = CircuitState.OPEN
                    self._last_failure_time = time.monotonic()

    def reset(self) -> None:
        """Manually reset to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._success_count_half_open = 0
