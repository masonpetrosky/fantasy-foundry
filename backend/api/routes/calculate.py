from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel


CalculateRequestModel = type[BaseModel]
CalculateExportRequestModel = type[BaseModel]
CalculateSyncHandler = Callable[[Any, Request], Any]
CalculateExportHandler = Callable[[Any, Request], Any]
CalculateJobCreateHandler = Callable[[Any, Request], Any]
CalculateJobReadHandler = Callable[[str, Request], Any]
CalculateJobCancelHandler = Callable[[str, Request], Any]


def build_calculate_router(
    *,
    calculate_request_model: CalculateRequestModel,
    calculate_export_request_model: CalculateExportRequestModel,
    calculate_handler: CalculateSyncHandler,
    calculate_export_handler: CalculateExportHandler,
    calculate_job_create_handler: CalculateJobCreateHandler,
    calculate_job_read_handler: CalculateJobReadHandler,
    calculate_job_cancel_handler: CalculateJobCancelHandler,
) -> APIRouter:
    """Create calculator sync/export/job routes using injected handlers."""
    router = APIRouter(tags=["calculate"])

    @router.post("/api/calculate")
    def calculate_dynasty_values(req: calculate_request_model, request: Request):
        return calculate_handler(req, request)

    @router.post("/api/calculate/export")
    def export_calculate_dynasty_values(req: calculate_export_request_model, request: Request):
        return calculate_export_handler(req, request)

    @router.post("/api/calculate/jobs", status_code=202)
    def create_calculate_dynasty_job(req: calculate_request_model, request: Request):
        return calculate_job_create_handler(req, request)

    @router.get("/api/calculate/jobs/{job_id}")
    def get_calculate_dynasty_job(job_id: str, request: Request):
        return calculate_job_read_handler(job_id, request)

    @router.delete("/api/calculate/jobs/{job_id}")
    def cancel_calculate_dynasty_job(job_id: str, request: Request):
        return calculate_job_cancel_handler(job_id, request)

    return router
