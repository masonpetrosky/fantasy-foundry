from __future__ import annotations

import logging
import os
import time
from uuid import uuid4
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from threading import Thread
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware


CallNext = Callable[[Request], Awaitable[Any]]


def create_app(
    *,
    title: str,
    version: str,
    app_build_id: str,
    api_no_cache_headers: dict[str, str],
    cors_allow_origins: list[str] | tuple[str, ...],
    refresh_data_if_needed: Callable[[], None],
    current_data_version: Callable[[], str],
    client_identity_resolver: Callable[[Request | None], str],
    enable_startup_calc_prewarm: bool,
    prewarm_default_calculation_caches: Callable[[], None],
    calculator_job_executor: Any,
) -> FastAPI:
    """Create the FastAPI app with shared middleware and lifecycle behavior."""

    @asynccontextmanager
    async def app_lifespan(_: FastAPI):
        if not os.getenv("PYTEST_CURRENT_TEST") and enable_startup_calc_prewarm:
            Thread(target=prewarm_default_calculation_caches, name="ff-calc-prewarm", daemon=True).start()
        try:
            yield
        finally:
            calculator_job_executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title=title, version=version, lifespan=app_lifespan)
    request_logger = logging.getLogger("fantasy_foundry.http")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_allow_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000,
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
            refresh_data_if_needed()
        response = await call_next(request)
        response.headers.setdefault("X-App-Build", app_build_id)
        response.headers.setdefault("X-Data-Version", current_data_version())
        if request.url.path.startswith("/api/"):
            for header, value in api_no_cache_headers.items():
                response.headers.setdefault(header, value)
        return response

    @app.middleware("http")
    async def attach_security_headers(request: Request, call_next: CallNext):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        return response

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
                client_identity_resolver(request),
            )

    return app
