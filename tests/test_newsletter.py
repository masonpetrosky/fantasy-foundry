"""Tests for newsletter subscription endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routes.newsletter import build_newsletter_router


@pytest.fixture()
def newsletter_app():
    enforce_rate_limit = MagicMock()
    client_ip_resolver = MagicMock(return_value="127.0.0.1")

    app = FastAPI()
    router = build_newsletter_router(
        buttondown_api_key="test-key",
        enforce_rate_limit=enforce_rate_limit,
        rate_limit_per_minute=10,
        client_ip_resolver=client_ip_resolver,
    )
    app.include_router(router)
    return app, enforce_rate_limit


def test_subscribe_success(newsletter_app):
    app, _ = newsletter_app
    mock_resp = MagicMock()
    mock_resp.status_code = 201

    with patch("backend.api.routes.newsletter.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = TestClient(app)
        resp = client.post("/api/newsletter/subscribe", json={"email": "test@example.com"})

    assert resp.status_code == 200
    assert resp.json()["subscribed"] is True


def test_subscribe_already_subscribed(newsletter_app):
    app, _ = newsletter_app
    mock_resp = MagicMock()
    mock_resp.status_code = 409

    with patch("backend.api.routes.newsletter.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = TestClient(app)
        resp = client.post("/api/newsletter/subscribe", json={"email": "test@example.com"})

    assert resp.status_code == 200
    assert resp.json()["already_subscribed"] is True


def test_subscribe_invalid_email(newsletter_app):
    app, _ = newsletter_app
    client = TestClient(app)
    resp = client.post("/api/newsletter/subscribe", json={"email": "not-an-email"})
    assert resp.status_code == 422


def test_subscribe_api_error(newsletter_app):
    app, _ = newsletter_app
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"

    with patch("backend.api.routes.newsletter.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        client = TestClient(app)
        resp = client.post("/api/newsletter/subscribe", json={"email": "test@example.com"})

    assert resp.status_code == 502
