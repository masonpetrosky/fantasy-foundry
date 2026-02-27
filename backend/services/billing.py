"""Supabase write layer for subscription management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def resolve_supabase_user_id(
    *,
    supabase_url: str,
    supabase_service_role_key: str,
    email: str,
) -> str | None:
    """Look up a Supabase auth user ID by email. Returns None if not found."""
    if not email:
        return None
    headers = {
        "apikey": supabase_service_role_key,
        "Authorization": f"Bearer {supabase_service_role_key}",
    }
    try:
        page = 1
        while True:
            url = f"{supabase_url}/auth/v1/admin/users?page={page}&per_page=50"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            users = data.get("users", []) if isinstance(data, dict) else data
            if not users:
                break
            for user in users:
                if str(user.get("email", "")).lower() == email.lower():
                    return str(user["id"])
            page += 1
    except Exception:
        logger.warning("Could not resolve Supabase user_id for email=%s", email, exc_info=True)
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
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
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
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(url, json={"status": "canceled"}, headers=headers)
        resp.raise_for_status()
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
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        rows = resp.json()
    if rows and len(rows) > 0:
        return {"status": rows[0].get("status", "none"), "active": rows[0].get("status") == "active"}
    return {"status": "none", "active": False}
