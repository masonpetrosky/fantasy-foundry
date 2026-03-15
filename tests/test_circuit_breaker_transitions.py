"""Tests for circuit breaker state transition edge cases."""

from __future__ import annotations

import time

from backend.core.circuit_breaker import CircuitBreaker, CircuitState


def test_full_lifecycle_closed_open_half_open_closed() -> None:
    """Verify the full state machine: CLOSED -> OPEN -> HALF_OPEN -> CLOSED."""
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)

    assert cb.state == CircuitState.CLOSED

    # Two failures should open the circuit
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False

    # Wait for recovery timeout to transition to HALF_OPEN
    time.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True

    # A success in HALF_OPEN should close the circuit
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True


def test_half_open_failure_reopens_and_resets_timer() -> None:
    """Verify that failure in HALF_OPEN reopens and requires another timeout."""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    time.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN

    # Failure in HALF_OPEN should reopen
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False

    # Should need to wait again for half-open
    assert cb.state == CircuitState.OPEN
    time.sleep(0.06)
    assert cb.state == CircuitState.HALF_OPEN


def test_multiple_successes_after_failures_reset_counter() -> None:
    """Verify that success in CLOSED state resets failure count."""
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)

    # Accumulate failures just below threshold
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED

    # Success resets
    cb.record_success()

    # Need 3 more failures to open
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_reset_clears_all_state() -> None:
    """Verify manual reset clears failure count and state."""
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.05)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN

    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True

    # Should need full failure_threshold again
    cb.record_failure()
    assert cb.state == CircuitState.OPEN


def test_minimum_failure_threshold_clamped() -> None:
    """Verify failure_threshold is clamped to at least 1."""
    cb = CircuitBreaker(failure_threshold=0, recovery_timeout=1.0)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
