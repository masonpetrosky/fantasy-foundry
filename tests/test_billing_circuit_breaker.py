"""Tests for billing service circuit breaker behavior with 4xx vs 5xx errors."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.core.circuit_breaker import CircuitState


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """Reset the module-level circuit breaker before each test."""
    from backend.services import billing

    billing._supabase_cb.reset()
    yield
    billing._supabase_cb.reset()


def _make_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    """Create an httpx.HTTPStatusError with the given status code."""
    response = httpx.Response(status_code=status_code)
    return httpx.HTTPStatusError(
        message=f"HTTP {status_code}",
        request=httpx.Request("POST", "https://example.com"),
        response=response,
    )


def _make_mock_client_post(status_code: int) -> AsyncMock:
    """Create a mock async client that raises HTTPStatusError on post."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = _make_http_status_error(status_code)

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
    mock_cm.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
    mock_cm.__aenter__.return_value.patch = AsyncMock(return_value=mock_response)
    return mock_cm


def test_upsert_4xx_does_not_trigger_circuit_breaker() -> None:
    """A 4xx error from Supabase should NOT trip the circuit breaker."""
    from backend.services.billing import _supabase_cb, upsert_subscription

    mock_client = _make_mock_client_post(400)

    with patch("backend.services.billing.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.get_event_loop().run_until_complete(
                upsert_subscription(
                    supabase_url="https://test.supabase.co",
                    supabase_service_role_key="test-key",
                    user_email="test@example.com",
                    stripe_customer_id="cus_test",
                    stripe_subscription_id="sub_test",
                    status="active",
                )
            )

    # Circuit breaker should still be closed after 4xx
    assert _supabase_cb.state == CircuitState.CLOSED


def test_upsert_5xx_does_trigger_circuit_breaker() -> None:
    """A 5xx error from Supabase should trip the circuit breaker."""
    from backend.services.billing import _supabase_cb, upsert_subscription

    mock_client = _make_mock_client_post(500)

    # Trip the breaker (threshold=3)
    for _ in range(3):
        with patch("backend.services.billing.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.get_event_loop().run_until_complete(
                    upsert_subscription(
                        supabase_url="https://test.supabase.co",
                        supabase_service_role_key="test-key",
                        user_email="test@example.com",
                        stripe_customer_id="cus_test",
                        stripe_subscription_id="sub_test",
                        status="active",
                    )
                )

    assert _supabase_cb.state == CircuitState.OPEN


def test_get_subscription_status_4xx_no_circuit_break() -> None:
    """get_subscription_status with 4xx should not affect circuit breaker."""
    from backend.services.billing import _supabase_cb, get_subscription_status

    mock_client = _make_mock_client_post(404)

    with patch("backend.services.billing.httpx.AsyncClient", return_value=mock_client):
        result = asyncio.get_event_loop().run_until_complete(
            get_subscription_status(
                supabase_url="https://test.supabase.co",
                supabase_service_role_key="test-key",
                user_email="test@example.com",
            )
        )

    assert result == {"status": "none", "active": False}
    assert _supabase_cb.state == CircuitState.CLOSED


def test_revoke_os_error_triggers_circuit_breaker() -> None:
    """OSError (network error) should always trigger circuit breaker."""
    from backend.services.billing import _supabase_cb, revoke_subscription

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value.patch = AsyncMock(side_effect=OSError("Connection refused"))

    for _ in range(3):
        with patch("backend.services.billing.httpx.AsyncClient", return_value=mock_cm):
            with pytest.raises(OSError):
                asyncio.get_event_loop().run_until_complete(
                    revoke_subscription(
                        supabase_url="https://test.supabase.co",
                        supabase_service_role_key="test-key",
                        stripe_subscription_id="sub_test",
                    )
                )

    assert _supabase_cb.state == CircuitState.OPEN
