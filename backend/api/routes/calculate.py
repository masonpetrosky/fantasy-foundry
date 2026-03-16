from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Path, Request
from pydantic import BaseModel

from backend.api.models import ErrorResponse

CalculateRequestModel = type[BaseModel]
CalculateExportRequestModel = type[BaseModel]
CalculateSyncHandler = Callable[[Any, Request], Any]
CalculateExportHandler = Callable[[Any, Request], Any]
CalculateJobCreateHandler = Callable[[Any, Request], Any]
CalculateJobReadHandler = Callable[[str, Request], Any]
CalculateJobCancelHandler = Callable[[str, Request], Any]
CalculateAuthorizeHandler = Callable[[Request], Any]

CALCULATE_ERROR_RESPONSES = {
    422: {"model": ErrorResponse, "description": "Validation error in calculator settings"},
    429: {"model": ErrorResponse, "description": "Rate limit exceeded — see Retry-After header"},
    500: {"model": ErrorResponse},
}


def build_calculate_router(
    *,
    calculate_request_model: CalculateRequestModel,
    calculate_export_request_model: CalculateExportRequestModel,
    calculate_handler: CalculateSyncHandler,
    calculate_export_handler: CalculateExportHandler,
    calculate_job_create_handler: CalculateJobCreateHandler,
    calculate_job_read_handler: CalculateJobReadHandler,
    calculate_job_cancel_handler: CalculateJobCancelHandler,
    calculate_authorize_handler: CalculateAuthorizeHandler | None = None,
) -> APIRouter:
    """Create calculator sync/export/job routes using injected handlers."""
    dependencies = [Depends(calculate_authorize_handler)] if calculate_authorize_handler is not None else []
    router = APIRouter(tags=["calculate"], dependencies=dependencies)

    @router.post("/api/calculate", summary="Run dynasty value calculation", responses=CALCULATE_ERROR_RESPONSES)
    def calculate_dynasty_values(req: calculate_request_model, request: Request):  # type: ignore[valid-type]
        """Run the Monte Carlo dynasty valuation calculator synchronously and return results."""
        return calculate_handler(req, request)

    @router.post("/api/calculate/export", summary="Export calculation results", responses=CALCULATE_ERROR_RESPONSES)
    def export_calculate_dynasty_values(req: calculate_export_request_model, request: Request):  # type: ignore[valid-type]
        """Run the calculator and return results as a downloadable CSV/XLSX file."""
        return calculate_export_handler(req, request)

    @router.post(
        "/api/calculate/jobs",
        status_code=202,
        summary="Create async calculation job",
        responses=CALCULATE_ERROR_RESPONSES,
    )
    def create_calculate_dynasty_job(req: calculate_request_model, request: Request):  # type: ignore[valid-type]
        """Submit a calculator job for asynchronous processing. Returns a job ID for polling."""
        return calculate_job_create_handler(req, request)

    @router.get(
        "/api/calculate/jobs/{job_id}",
        summary="Get calculation job status",
        responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    def get_calculate_dynasty_job(job_id: str = Path(max_length=100), *, request: Request):
        """Poll the status of an async calculator job by ID."""
        return calculate_job_read_handler(job_id, request)

    @router.delete(
        "/api/calculate/jobs/{job_id}",
        summary="Cancel calculation job",
        responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    def cancel_calculate_dynasty_job(job_id: str = Path(max_length=100), *, request: Request):
        """Cancel a running async calculator job by ID."""
        return calculate_job_cancel_handler(job_id, request)

    return router
