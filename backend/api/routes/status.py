from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.models import ErrorResponse, HealthResponse, MetaResponse, OpsResponse, ReadyResponse, VersionResponse
from backend.core.metrics import MetricsCollector

MetaHandler = Callable[[Request], Any]
VersionHandler = Callable[[Request], Any]
HealthHandler = Callable[[], Any]
ReadyHandler = Callable[[], Any]
OpsHandler = Callable[[], Any]


def build_status_router(
    *,
    meta_handler: MetaHandler,
    version_handler: VersionHandler,
    health_handler: HealthHandler,
    ready_handler: ReadyHandler,
    ops_handler: OpsHandler,
    metrics_collector: MetricsCollector | None = None,
) -> APIRouter:
    """Create metadata/version/health routes using injected handler callables."""
    router = APIRouter(tags=["status"])

    @router.get(
        "/api/meta",
        summary="Get application metadata",
        response_model=MetaResponse,
        responses={304: {"description": "Not Modified"}, 500: {"model": ErrorResponse}},
    )
    def get_meta(request: Request):
        return meta_handler(request)

    @router.get(
        "/api/version",
        summary="Get build and data version",
        response_model=VersionResponse,
        responses={304: {"description": "Not Modified"}, 500: {"model": ErrorResponse}},
    )
    def get_version(request: Request):
        return version_handler(request)

    @router.get("/api/health", summary="Health check", response_model=HealthResponse, responses={500: {"model": ErrorResponse}})
    def get_health():
        return health_handler()

    @router.get("/api/ready", summary="Readiness probe", response_model=ReadyResponse, responses={503: {"model": ErrorResponse}})
    def get_ready():
        return ready_handler()

    @router.get("/api/ops", summary="Operational dashboard", response_model=OpsResponse, responses={500: {"model": ErrorResponse}})
    def get_ops():
        return ops_handler()

    if metrics_collector is not None:

        @router.get("/api/metrics", summary="Request metrics snapshot", tags=["status"])
        def get_metrics():
            """Return request count, latency percentiles, error rates, and route breakdowns."""
            return JSONResponse(metrics_collector.snapshot())

    return router
