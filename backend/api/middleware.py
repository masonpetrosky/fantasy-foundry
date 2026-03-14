from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse, Response

CallNext = Callable[[Request], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class MiddlewareConfig:
    app_build_id: str
    api_no_cache_headers: dict[str, str]
    cors_allow_origins: tuple[str, ...]
    refresh_data_if_needed: Callable[[], None]
    current_data_version: Callable[[], str]
    client_identity_resolver: Callable[[Request | None], str]
    canonical_host: str
    environment: str


def _normalized_host(raw_value: str | None) -> str:
    text = str(raw_value or "").strip().lower()
    if not text:
        return ""
    if "," in text:
        text = text.split(",", 1)[0].strip()
    if "://" in text:
        parsed = urlparse(text)
        text = str(parsed.hostname or "").strip().lower()
    text = text.rstrip(".")
    if ":" in text and not text.startswith("["):
        host, port = text.rsplit(":", 1)
        if port.isdigit():
            text = host
    return text


def register_middlewares(app: FastAPI, *, config: MiddlewareConfig) -> None:
    request_logger = logging.getLogger("fantasy_foundry.http")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.cors_allow_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000,
    )

    canonical_host_clean = str(config.canonical_host or "").strip().lower().rstrip(".")
    www_canonical_host = f"www.{canonical_host_clean}" if canonical_host_clean else ""

    @app.middleware("http")
    async def redirect_www_to_canonical_host(request: Request, call_next: CallNext):
        if not canonical_host_clean:
            return await call_next(request)

        forwarded_host = _normalized_host(request.headers.get("x-forwarded-host"))
        request_host = forwarded_host or _normalized_host(str(request.url.hostname or ""))
        if request_host != www_canonical_host:
            return await call_next(request)

        forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
        target_scheme = forwarded_proto if forwarded_proto in {"http", "https"} else request.url.scheme
        return RedirectResponse(
            url=str(request.url.replace(scheme=target_scheme, netloc=canonical_host_clean)),
            status_code=308,
        )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next: CallNext):
        request_id = str(request.headers.get("x-request-id") or "").strip() or uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers.setdefault("X-Request-Id", request_id)
        return response

    @app.middleware("http")
    async def attach_build_header(request: Request, call_next: CallNext):
        if request.url.path.startswith("/api/"):
            config.refresh_data_if_needed()
        response = await call_next(request)
        response.headers.setdefault("X-App-Build", config.app_build_id)
        response.headers.setdefault("X-Data-Version", config.current_data_version())
        if request.url.path.startswith("/api/"):
            for header, value in config.api_no_cache_headers.items():
                response.headers.setdefault(header, value)
        return response

    @app.middleware("http")
    async def attach_security_headers(request: Request, call_next: CallNext):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            (
                "default-src 'self'; "
                "img-src 'self' data: https:; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' data: https://fonts.gstatic.com; "
                "script-src 'self' https://www.googletagmanager.com; "
                "connect-src 'self' https://*.supabase.co https://www.google-analytics.com https://*.google-analytics.com https://*.analytics.google.com https://*.ingest.sentry.io; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "object-src 'none'; "
                "form-action 'self'"
            ),
        )
        forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").split(",", 1)[0].strip().lower()
        request_scheme = forwarded_proto if forwarded_proto in {"http", "https"} else request.url.scheme
        if str(config.environment).strip().lower() == "production" and request_scheme == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")
        return response

    @app.middleware("http")
    async def handle_head_requests(request: Request, call_next: CallNext):
        """Convert HEAD to GET, run normally, return headers without body."""
        if request.method != "HEAD":
            return await call_next(request)
        request.scope["method"] = "GET"
        response = await call_next(request)
        headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")
        }
        if hasattr(response, "body_iterator"):
            async for _ in response.body_iterator:
                pass
        return Response(
            status_code=response.status_code,
            headers=headers,
            background=response.background,
        )

    @app.middleware("http")
    async def inject_rate_limit_headers(request: Request, call_next: CallNext):
        response = await call_next(request)
        limit = getattr(request.state, "rate_limit_limit", None)
        if limit is not None:
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(
                getattr(request.state, "rate_limit_remaining", 0),
            )
            response.headers["X-RateLimit-Reset"] = str(
                getattr(request.state, "rate_limit_reset", 0),
            )
        return response

    max_body_bytes = 1_048_576  # 1 MB

    @app.middleware("http")
    async def enforce_request_body_size_limit(request: Request, call_next: CallNext):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > max_body_bytes:
                    return Response(
                        status_code=413,
                        content='{"detail":"Request body too large."}',
                        media_type="application/json",
                    )
            except (ValueError, TypeError):
                pass
        return await call_next(request)

    @app.middleware("http")
    async def log_api_request(request: Request, call_next: CallNext):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        route_group = request.url.path.split("/", 3)[2] if request.url.path.count("/") >= 2 else "unknown"
        request_id = str(getattr(request.state, "request_id", "")).strip() or str(
            request.headers.get("x-request-id") or ""
        ).strip()
        if not request_id:
            request_id = "unknown"

        started = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 1)
            status_code = response.status_code if response is not None else 500
            request_logger.info(
                "api_request request_id=%s method=%s path=%s route_group=%s status=%s duration_ms=%s client_identity=%s",
                request_id,
                request.method,
                request.url.path,
                route_group,
                status_code,
                duration_ms,
                config.client_identity_resolver(request),
            )
