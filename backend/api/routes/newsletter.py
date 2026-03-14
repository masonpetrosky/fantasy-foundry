"""Newsletter subscription endpoint proxying to Buttondown API."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

logger = logging.getLogger(__name__)

BUTTONDOWN_API_URL = "https://api.buttondown.email/v1/subscribers"


class SubscribeRequest(BaseModel):
    email: EmailStr


def build_newsletter_router(
    *,
    buttondown_api_key: str,
    enforce_rate_limit: object,
    rate_limit_per_minute: int = 10,
    client_ip_resolver: object,
) -> APIRouter:
    """Create newsletter subscription route."""
    router = APIRouter(tags=["newsletter"])

    @router.post("/api/newsletter/subscribe", summary="Subscribe to newsletter")
    async def subscribe(body: SubscribeRequest, request: Request) -> JSONResponse:
        client_ip = client_ip_resolver(request)
        enforce_rate_limit(client_ip, "newsletter", rate_limit_per_minute)

        headers = {
            "Authorization": f"Token {buttondown_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"email_address": body.email, "type": "regular"}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(BUTTONDOWN_API_URL, json=payload, headers=headers)

        if resp.status_code == 409:
            return JSONResponse({"subscribed": True, "already_subscribed": True})
        if resp.status_code >= 400:
            logger.error("Buttondown API error: status=%s body=%s", resp.status_code, resp.text[:200])
            raise HTTPException(status_code=502, detail="Newsletter subscription failed.")

        return JSONResponse({"subscribed": True})

    return router
