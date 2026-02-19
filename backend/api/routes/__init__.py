"""Route registration helpers for FastAPI endpoints."""

from .calculate import build_calculate_router
from .frontend_assets import build_frontend_assets_router
from .projections import build_projections_router
from .status import build_status_router

__all__ = [
    "build_calculate_router",
    "build_frontend_assets_router",
    "build_projections_router",
    "build_status_router",
]
