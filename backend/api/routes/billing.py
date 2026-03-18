"""Stripe billing routes for premium tier subscriptions."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CheckoutRequest(BaseModel):
    price_lookup_key: str
    success_url: str
    cancel_url: str
    user_email: str = ""


def build_billing_router(
    *,
    stripe_secret_key: str,
    stripe_webhook_secret: str,
    stripe_monthly_price_id: str,
    stripe_annual_price_id: str,
    on_checkout_completed: Callable[[dict[str, Any]], Awaitable[None]],
    on_subscription_updated: Callable[[dict[str, Any]], Awaitable[None]],
    on_subscription_deleted: Callable[[dict[str, Any]], Awaitable[None]],
    get_subscription_status: Callable[[str], Awaitable[dict[str, Any]]],
) -> APIRouter:
    """Create billing routes (Stripe checkout + webhooks + status)."""
    import stripe

    stripe.api_key = stripe_secret_key

    price_map = {
        "monthly": stripe_monthly_price_id,
        "annual": stripe_annual_price_id,
    }

    router = APIRouter(tags=["billing"])

    @router.post("/api/billing/create-checkout-session", summary="Create Stripe checkout session")
    async def create_checkout_session(body: CheckoutRequest) -> JSONResponse:
        price_id = price_map.get(body.price_lookup_key, "")
        if not price_id:
            raise HTTPException(status_code=400, detail="Invalid price_lookup_key. Use 'monthly' or 'annual'.")

        try:
            session_kwargs: dict[str, Any] = {
                "mode": "subscription",
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": body.success_url,
                "cancel_url": body.cancel_url,
            }
            if body.user_email.strip():
                session_kwargs["customer_email"] = body.user_email.strip()

            session = stripe.checkout.Session.create(**session_kwargs)
        except stripe.InvalidRequestError as exc:
            logger.warning("Stripe checkout invalid request: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid checkout request.")
        except stripe.AuthenticationError as exc:
            logger.error("Stripe authentication error: %s", exc)
            raise HTTPException(status_code=502, detail="Payment service configuration error.")
        except stripe.StripeError as exc:
            logger.error("Stripe checkout error: %s", exc)
            raise HTTPException(status_code=502, detail="Failed to create checkout session.")

        return JSONResponse({"checkout_url": session.url})

    @router.post("/api/billing/webhook", summary="Handle Stripe webhook event")
    async def stripe_webhook(request: Request) -> JSONResponse:
        body = await request.body()
        sig_header = request.headers.get("stripe-signature", "")
        if not sig_header:
            raise HTTPException(status_code=400, detail="Missing Stripe signature.")

        try:
            event = stripe.Webhook.construct_event(body, sig_header, stripe_webhook_secret)
        except stripe.SignatureVerificationError:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature.")
        except (ValueError, KeyError) as exc:
            logger.exception("Stripe webhook payload parsing failed: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid payload.")

        event_type = event.get("type", "")
        event_object = event.get("data", {}).get("object", {})
        logger.info("Stripe webhook event: %s", event_type)

        if event_type == "checkout.session.completed":
            await on_checkout_completed(event_object)
        elif event_type == "customer.subscription.updated":
            await on_subscription_updated(event_object)
        elif event_type == "customer.subscription.deleted":
            await on_subscription_deleted(event_object)

        return JSONResponse({"received": True})

    @router.get("/api/billing/subscription-status", summary="Check subscription status")
    async def subscription_status(email: str = "") -> JSONResponse:
        email = email.strip()
        if not email:
            raise HTTPException(status_code=400, detail="email query parameter required.")
        result = await get_subscription_status(email)
        return JSONResponse(result)

    return router
