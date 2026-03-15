from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import asynccontextmanager
from threading import Thread
from typing import Any

from fastapi import FastAPI, Request

from backend.api.error_handlers import register_exception_handlers
from backend.api.middleware import MiddlewareConfig, register_middlewares
from backend.core.metrics import MetricsCollector

_OPENAPI_TAGS = [
    {"name": "projections", "description": "Player projection queries, exports, profiles, and comparisons."},
    {"name": "calculate", "description": "Dynasty value calculator (sync, async jobs, exports)."},
    {"name": "status", "description": "Health checks, readiness probes, and operational metadata."},
    {"name": "fantrax", "description": "Fantrax league integration (roster import, settings)."},
    {"name": "billing", "description": "Stripe subscription management and webhooks."},
    {"name": "newsletter", "description": "Newsletter subscription via Buttondown."},
    {"name": "og-cards", "description": "Open Graph image card generation for social sharing."},
]

_APP_DESCRIPTION = (
    "Production MLB dynasty fantasy baseball API with 20-year projections (2026–2045), "
    "a Monte Carlo dynasty valuation calculator, and optional cloud sync.\n\n"
    "**Rate limiting:** Most endpoints enforce per-IP rate limits. "
    "When exceeded, the API returns `429 Too Many Requests` with `Retry-After` and "
    "`X-RateLimit-*` headers."
)


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
    docs_enabled: bool = True,
    metrics_collector: MetricsCollector | None = None,
    slow_request_threshold_seconds: float = 5.0,
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

    app = FastAPI(
        title=title,
        version=version,
        description=_APP_DESCRIPTION,
        openapi_tags=_OPENAPI_TAGS,
        lifespan=app_lifespan,
        docs_url="/api/docs" if docs_enabled else None,
        redoc_url="/api/redoc" if docs_enabled else None,
        openapi_url="/api/openapi.json" if docs_enabled else None,
    )
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
            slow_request_threshold_seconds=slow_request_threshold_seconds,
            metrics_collector=metrics_collector,
        ),
    )
    return app
