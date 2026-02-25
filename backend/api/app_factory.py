from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from threading import Thread
from typing import Any

from fastapi import FastAPI, Request

from backend.api.error_handlers import register_exception_handlers
from backend.api.middleware import MiddlewareConfig, register_middlewares


def create_app(
    *,
    title: str,
    version: str,
    app_build_id: str,
    api_no_cache_headers: dict[str, str],
    cors_allow_origins: list[str] | tuple[str, ...],
    environment: str,
    refresh_data_if_needed: Callable[[], None],
    current_data_version: Callable[[], str],
    client_identity_resolver: Callable[[Request | None], str],
    canonical_host: str,
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
    register_exception_handlers(app)
    register_middlewares(
        app,
        config=MiddlewareConfig(
            app_build_id=app_build_id,
            api_no_cache_headers=dict(api_no_cache_headers),
            cors_allow_origins=tuple(cors_allow_origins),
            refresh_data_if_needed=refresh_data_if_needed,
            current_data_version=current_data_version,
            client_identity_resolver=client_identity_resolver,
            canonical_host=canonical_host,
            environment=environment,
        ),
    )
    return app
