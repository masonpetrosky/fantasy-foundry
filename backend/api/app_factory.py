from __future__ import annotations

import os
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
    refresh_data_if_needed: Callable[[], None],
    current_data_version: Callable[[], str],
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000,
    )

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

    return app
