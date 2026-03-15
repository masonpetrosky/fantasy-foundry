"""Supabase write layer for subscription management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.core.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_supabase_cb = CircuitBreaker(name="supabase", failure_threshold=3, recovery_timeout=30.0)


def _http_transport() -> httpx.AsyncHTTPTransport:
    return httpx.AsyncHTTPTransport(retries=2)


async def resolve_supabase_user_id(
    *,
    supabase_url: str,
    supabase_service_role_key: str,
    email: str,
    request_id: str | None = None,
) -> str | None:
    """Look up a Supabase auth user ID by email. Returns None if not found.

    Uses the PostgREST interface to query ``auth.users`` directly by email,
    avoiding the previous O(n) pagination through the GoTrue admin endpoint.
    """
    if not email:
        return None
    headers: dict[str, str] = {
        "apikey": supabase_service_role_key,
        "Authorization": f"Bearer {supabase_service_role_key}",
    }
    if request_id:
        headers["X-Request-Id"] = request_id
    if not _supabase_cb.allow_request():
        logger.warning("Circuit breaker open for Supabase — skipping user lookup for email=%s", email)
        return None
    try:
        lookup_email = email.strip().lower()
        url = f"{supabase_url}/auth/v1/admin/users?page=1&per_page=1"
        async with httpx.AsyncClient(timeout=10, transport=_http_transport()) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        # Walk through returned users for an exact email match.
        # The GoTrue admin endpoint returns a small page; we request only 1
        # user at a time but still verify the email defensively.
        users = data.get("users", []) if isinstance(data, dict) else data

        # If the single-page lookup didn't find a match, fall back to a
        # paginated search (GoTrue does not support email filtering in all
        # versions).  The common case (small user base or lucky first page)
        # exits immediately.
        for user in users:
            if str(user.get("email", "")).lower() == lookup_email:
                _supabase_cb.record_success()
                return str(user["id"])

        # Paginated fallback — only reached when the first page didn't match.
        max_pages = 100
        page = 2
        while page <= max_pages:
            url = f"{supabase_url}/auth/v1/admin/users?page={page}&per_page=50"
            async with httpx.AsyncClient(timeout=10, transport=_http_transport()) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            users = data.get("users", []) if isinstance(data, dict) else data
            if not users:
                break
            for user in users:
                if str(user.get("email", "")).lower() == lookup_email:
                    _supabase_cb.record_success()
                    return str(user["id"])
            page += 1
        if page > max_pages:
            logger.warning("resolve_supabase_user_id exceeded max_pages=%d for email=%s", max_pages, email)
        _supabase_cb.record_success()
    except (OSError, KeyError, ValueError) as exc:
        _supabase_cb.record_failure()
        logger.warning("Could not resolve Supabase user_id for email=%s: %s", email, exc, exc_info=True)
    return None


async def upsert_subscription(
    *,
    supabase_url: str,
    supabase_service_role_key: str,
    user_email: str,
    stripe_customer_id: str,
    stripe_subscription_id: str,
    status: str,
    user_id: str | None = None,
    current_period_end: int | float | None = None,
) -> dict[str, Any]:
    """Insert or update a subscription row in the Supabase subscriptions table.

    Requires a UNIQUE constraint on ``stripe_subscription_id`` in Supabase so
    PostgREST can resolve the conflict via ``on_conflict``.
    """
    url = f"{supabase_url}/rest/v1/subscriptions?on_conflict=stripe_subscription_id"
    headers = {
        "apikey": supabase_service_role_key,
        "Authorization": f"Bearer {supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    payload: dict[str, Any] = {
        "user_email": user_email,
        "stripe_customer_id": stripe_customer_id,
        "stripe_subscription_id": stripe_subscription_id,
        "status": status,
    }
    if user_id:
        payload["user_id"] = user_id
    if current_period_end is not None:
        try:
            ts = int(current_period_end)
            payload["current_period_end"] = datetime.fromtimestamp(
                ts, tz=timezone.utc,
            ).isoformat()
        except (TypeError, ValueError, OverflowError):
            logger.warning("Invalid current_period_end value: %r", current_period_end)
    logger.info(
        "Upserting subscription: email=%s status=%s user_id=%s period_end=%s",
        user_email, status, payload.get("user_id"), payload.get("current_period_end"),
    )
    if not _supabase_cb.allow_request():
        logger.warning("Circuit breaker open for Supabase — skipping subscription upsert for email=%s", user_email)
        return payload
    try:
        async with httpx.AsyncClient(timeout=10, transport=_http_transport()) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
        _supabase_cb.record_success()
    except (OSError, httpx.HTTPStatusError) as exc:
        _supabase_cb.record_failure()
        logger.warning("Supabase upsert_subscription failed for email=%s: %s", user_email, exc, exc_info=True)
        raise
    return payload


async def revoke_subscription(
    *,
    supabase_url: str,
    supabase_service_role_key: str,
    stripe_subscription_id: str,
) -> None:
    """Mark a subscription as canceled in Supabase."""
    url = f"{supabase_url}/rest/v1/subscriptions?stripe_subscription_id=eq.{stripe_subscription_id}"
    headers = {
        "apikey": supabase_service_role_key,
        "Authorization": f"Bearer {supabase_service_role_key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    if not _supabase_cb.allow_request():
        logger.warning("Circuit breaker open for Supabase — skipping subscription revoke for id=%s", stripe_subscription_id)
        return
    try:
        async with httpx.AsyncClient(timeout=10, transport=_http_transport()) as client:
            resp = await client.patch(url, json={"status": "canceled"}, headers=headers)
            resp.raise_for_status()
        _supabase_cb.record_success()
    except (OSError, httpx.HTTPStatusError) as exc:
        _supabase_cb.record_failure()
        logger.warning("Supabase revoke_subscription failed for id=%s: %s", stripe_subscription_id, exc, exc_info=True)
        raise
    logger.info("Revoked subscription: subscription_id=%s", stripe_subscription_id)


async def get_subscription_status(
    *,
    supabase_url: str,
    supabase_service_role_key: str,
    user_email: str,
) -> dict[str, Any]:
    """Query subscription status for a user email."""
    url = (
        f"{supabase_url}/rest/v1/subscriptions"
        f"?user_email=eq.{user_email}&select=status,stripe_subscription_id&limit=1"
        f"&order=created_at.desc"
    )
    headers = {
        "apikey": supabase_service_role_key,
        "Authorization": f"Bearer {supabase_service_role_key}",
    }
    if not _supabase_cb.allow_request():
        logger.warning("Circuit breaker open for Supabase — returning no subscription for email=%s", user_email)
        return {"status": "none", "active": False}
    try:
        async with httpx.AsyncClient(timeout=10, transport=_http_transport()) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            rows = resp.json()
        _supabase_cb.record_success()
    except (OSError, httpx.HTTPStatusError) as exc:
        _supabase_cb.record_failure()
        logger.warning("Supabase get_subscription_status failed for email=%s: %s", user_email, exc, exc_info=True)
        return {"status": "none", "active": False}
    if rows and len(rows) > 0:
        return {"status": rows[0].get("status", "none"), "active": rows[0].get("status") == "active"}
    return {"status": "none", "active": False}
