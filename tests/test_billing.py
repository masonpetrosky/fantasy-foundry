"""Tests for billing routes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def billing_app():
    on_checkout = AsyncMock()
    on_updated = AsyncMock()
    on_deleted = AsyncMock()
    get_status = AsyncMock(return_value={"status": "active", "active": True})

    mock_stripe = MagicMock()
    mock_stripe.api_key = ""
    mock_stripe.StripeError = Exception
    mock_stripe.SignatureVerificationError = Exception

    with patch.dict("sys.modules", {"stripe": mock_stripe}):
        from backend.api.routes.billing import build_billing_router

        app = FastAPI()
        router = build_billing_router(
            stripe_secret_key="sk_test_xxx",
            stripe_webhook_secret="whsec_xxx",
            stripe_monthly_price_id="price_monthly",
            stripe_annual_price_id="price_annual",
            on_checkout_completed=on_checkout,
            on_subscription_updated=on_updated,
            on_subscription_deleted=on_deleted,
            get_subscription_status=get_status,
        )
        app.include_router(router)

    return app, mock_stripe, on_checkout, on_updated, on_deleted, get_status


def test_create_checkout_session(billing_app):
    app, mock_stripe, *_ = billing_app
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/test"
    mock_stripe.checkout.Session.create.return_value = mock_session

    client = TestClient(app)
    resp = client.post("/api/billing/create-checkout-session", json={
        "price_lookup_key": "monthly",
        "success_url": "https://example.com/success",
        "cancel_url": "https://example.com/cancel",
    })
    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test"


def test_create_checkout_invalid_key(billing_app):
    app, *_ = billing_app
    client = TestClient(app)
    resp = client.post("/api/billing/create-checkout-session", json={
        "price_lookup_key": "invalid",
        "success_url": "https://example.com/success",
        "cancel_url": "https://example.com/cancel",
    })
    assert resp.status_code == 400


def test_webhook_missing_signature(billing_app):
    app, *_ = billing_app
    client = TestClient(app)
    resp = client.post("/api/billing/webhook", content=b"{}")
    assert resp.status_code == 400


def test_webhook_checkout_completed(billing_app):
    app, mock_stripe, on_checkout, *_ = billing_app
    event = {
        "type": "checkout.session.completed",
        "data": {"object": {"customer_email": "test@example.com", "subscription": "sub_123"}},
    }
    mock_stripe.Webhook.construct_event.return_value = event

    client = TestClient(app)
    resp = client.post(
        "/api/billing/webhook",
        content=b'{}',
        headers={"stripe-signature": "t=1,v1=abc"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"received": True}
    on_checkout.assert_awaited_once()


def test_subscription_status(billing_app):
    app, *_ = billing_app
    get_status = billing_app[5]
    client = TestClient(app)
    resp = client.get("/api/billing/subscription-status?email=test@example.com")
    assert resp.status_code == 200
    assert resp.json()["active"] is True
    get_status.assert_awaited_once_with("test@example.com")


def test_subscription_status_missing_email(billing_app):
    app, *_ = billing_app
    client = TestClient(app)
    resp = client.get("/api/billing/subscription-status")
    assert resp.status_code == 400
