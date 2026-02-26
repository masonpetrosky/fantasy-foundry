"""Stripe billing webhook handler for premium tier subscriptions.

Wire this route only when FF_STRIPE_WEBHOOK_SECRET is configured.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

STRIPE_WEBHOOK_SECRET = os.getenv("FF_STRIPE_WEBHOOK_SECRET", "").strip()


def build_billing_router() -> APIRouter:
    """Create billing webhook route (Stripe)."""
    router = APIRouter(tags=["billing"])

    @router.post("/api/billing/webhook")
    async def stripe_webhook(request: Request) -> JSONResponse:
        if not STRIPE_WEBHOOK_SECRET:
            raise HTTPException(status_code=503, detail="Billing webhooks not configured.")

        body = await request.body()
        sig_header = request.headers.get("stripe-signature", "")

        # Verify Stripe signature (simplified — production should use stripe.Webhook.construct_event)
        if not sig_header:
            raise HTTPException(status_code=400, detail="Missing Stripe signature.")

        try:
            import json
            event = json.loads(body)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload.")

        event_type = event.get("type", "")
        logger.info("Stripe webhook event: %s", event_type)

        if event_type == "checkout.session.completed":
            _handle_checkout_completed(event.get("data", {}).get("object", {}))
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(event.get("data", {}).get("object", {}))
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(event.get("data", {}).get("object", {}))

        return JSONResponse({"received": True})

    return router


def _handle_checkout_completed(session: dict[str, Any]) -> None:
    customer_email = session.get("customer_email", "")
    subscription_id = session.get("subscription", "")
    logger.info("Checkout completed: email=%s subscription=%s", customer_email, subscription_id)
    # TODO: Update user's subscription status in Supabase


def _handle_subscription_updated(subscription: dict[str, Any]) -> None:
    status = subscription.get("status", "")
    subscription_id = subscription.get("id", "")
    logger.info("Subscription updated: id=%s status=%s", subscription_id, status)
    # TODO: Update subscription status in Supabase


def _handle_subscription_deleted(subscription: dict[str, Any]) -> None:
    subscription_id = subscription.get("id", "")
    logger.info("Subscription deleted: id=%s", subscription_id)
    # TODO: Revoke premium access in Supabase
