from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request

from backend.api.models import ErrorResponse, HealthResponse, MetaResponse, OpsResponse, ReadyResponse, VersionResponse

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
) -> APIRouter:
    """Create metadata/version/health routes using injected handler callables."""
    router = APIRouter(tags=["status"])

    @router.get(
        "/api/meta",
        response_model=MetaResponse,
        responses={304: {"description": "Not Modified"}, 500: {"model": ErrorResponse}},
    )
    def get_meta(request: Request):
        return meta_handler(request)

    @router.get(
        "/api/version",
        response_model=VersionResponse,
        responses={304: {"description": "Not Modified"}, 500: {"model": ErrorResponse}},
    )
    def get_version(request: Request):
        return version_handler(request)

    @router.get("/api/health", response_model=HealthResponse, responses={500: {"model": ErrorResponse}})
    def get_health():
        return health_handler()

    @router.get("/api/ready", response_model=ReadyResponse, responses={503: {"model": ErrorResponse}})
    def get_ready():
        return ready_handler()

    @router.get("/api/ops", response_model=OpsResponse, responses={500: {"model": ErrorResponse}})
    def get_ops():
        return ops_handler()

    return router
