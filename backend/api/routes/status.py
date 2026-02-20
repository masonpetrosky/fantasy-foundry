from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request


MetaHandler = Callable[[Request], Any]
VersionHandler = Callable[[Request], Any]
HealthHandler = Callable[[], Any]
ReadyHandler = Callable[[], Any]


def build_status_router(
    *,
    meta_handler: MetaHandler,
    version_handler: VersionHandler,
    health_handler: HealthHandler,
    ready_handler: ReadyHandler,
) -> APIRouter:
    """Create metadata/version/health routes using injected handler callables."""
    router = APIRouter(tags=["status"])

    @router.get("/api/meta")
    def get_meta(request: Request):
        return meta_handler(request)

    @router.get("/api/version")
    def get_version(request: Request):
        return version_handler(request)

    @router.get("/api/health")
    def get_health():
        return health_handler()

    @router.get("/api/ready")
    def get_ready():
        return ready_handler()

    return router
