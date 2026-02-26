from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from backend.api.models import (
    ErrorResponse,
    ProjectionCompareResponse,
    ProjectionListResponse,
    ProjectionProfileResponse,
)

ProjectionResponseHandler = Callable[..., dict[str, Any]]
ProjectionExportHandler = Callable[..., Any]
ProjectionProfileHandler = Callable[..., dict[str, Any]]
ProjectionCompareHandler = Callable[..., dict[str, Any]]


class ProjectionListQueryParams(BaseModel):
    player: str | None = None
    team: str | None = None
    player_keys: str | None = None
    year: int | None = None
    years: str | None = None
    pos: str | None = None
    dynasty_years: str | None = None
    career_totals: bool = False
    include_dynasty: bool = True
    calculator_job_id: str | None = None
    sort_col: str | None = None
    sort_dir: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=200, ge=1, le=5000)
    offset: int = Field(default=0, ge=0)


class ProjectionExportQueryParams(BaseModel):
    player: str | None = None
    team: str | None = None
    player_keys: str | None = None
    year: int | None = None
    years: str | None = None
    pos: str | None = None
    dynasty_years: str | None = None
    career_totals: bool = False
    include_dynasty: bool = True
    calculator_job_id: str | None = None
    sort_col: str | None = None
    sort_dir: Literal["asc", "desc"] = "desc"
    columns: str | None = None


PROJECTION_ERROR_RESPONSES = {
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


def build_projections_router(
    *,
    projection_response_handler: ProjectionResponseHandler,
    projection_export_handler: ProjectionExportHandler,
    projection_profile_handler: ProjectionProfileHandler,
    projection_compare_handler: ProjectionCompareHandler,
) -> APIRouter:
    """Create projections query/export routes with injected handlers."""
    router = APIRouter(tags=["projections"])

    @router.get("/api/projections/all", response_model=ProjectionListResponse, responses=PROJECTION_ERROR_RESPONSES)
    def get_all_projections(
        request: Request,
        query: Annotated[ProjectionListQueryParams, Depends()],
    ):
        return projection_response_handler(
            "all",
            player=query.player,
            team=query.team,
            player_keys=query.player_keys,
            year=query.year,
            years=query.years,
            pos=query.pos,
            dynasty_years=query.dynasty_years,
            career_totals=query.career_totals,
            include_dynasty=query.include_dynasty,
            calculator_job_id=query.calculator_job_id,
            sort_col=query.sort_col,
            sort_dir=query.sort_dir,
            limit=query.limit,
            offset=query.offset,
            request=request,
        )

    @router.get("/api/projections/bat", response_model=ProjectionListResponse, responses=PROJECTION_ERROR_RESPONSES)
    def get_bat_projections(
        request: Request,
        query: Annotated[ProjectionListQueryParams, Depends()],
    ):
        return projection_response_handler(
            "bat",
            player=query.player,
            team=query.team,
            player_keys=query.player_keys,
            year=query.year,
            years=query.years,
            pos=query.pos,
            dynasty_years=query.dynasty_years,
            career_totals=query.career_totals,
            include_dynasty=query.include_dynasty,
            calculator_job_id=query.calculator_job_id,
            sort_col=query.sort_col,
            sort_dir=query.sort_dir,
            limit=query.limit,
            offset=query.offset,
            request=request,
        )

    @router.get("/api/projections/pitch", response_model=ProjectionListResponse, responses=PROJECTION_ERROR_RESPONSES)
    def get_pitch_projections(
        request: Request,
        query: Annotated[ProjectionListQueryParams, Depends()],
    ):
        return projection_response_handler(
            "pitch",
            player=query.player,
            team=query.team,
            player_keys=query.player_keys,
            year=query.year,
            years=query.years,
            pos=query.pos,
            dynasty_years=query.dynasty_years,
            career_totals=query.career_totals,
            include_dynasty=query.include_dynasty,
            calculator_job_id=query.calculator_job_id,
            sort_col=query.sort_col,
            sort_dir=query.sort_dir,
            limit=query.limit,
            offset=query.offset,
            request=request,
        )

    @router.get("/api/projections/player/{player_id}", response_model=ProjectionListResponse, responses=PROJECTION_ERROR_RESPONSES)
    def get_player_projection_series(
        request: Request,
        player_id: str,
        dataset: Literal["all", "bat", "pitch"] = "all",
        include_dynasty: bool = True,
        calculator_job_id: str | None = None,
    ):
        return projection_response_handler(
            dataset,
            player=None,
            team=None,
            player_keys=player_id,
            year=None,
            years=None,
            pos=None,
            dynasty_years=None,
            career_totals=False,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
            sort_col="Year",
            sort_dir="asc",
            limit=5000,
            offset=0,
            request=request,
        )

    @router.get(
        "/api/projections/profile/{player_id}",
        response_model=ProjectionProfileResponse,
        responses=PROJECTION_ERROR_RESPONSES,
    )
    def get_projection_profile(
        request: Request,
        player_id: str,
        dataset: Literal["all", "bat", "pitch"] = "all",
        include_dynasty: bool = True,
        calculator_job_id: str | None = None,
    ):
        return projection_profile_handler(
            request=request,
            player_id=player_id,
            dataset=dataset,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
        )

    @router.get(
        "/api/projections/compare",
        response_model=ProjectionCompareResponse,
        responses=PROJECTION_ERROR_RESPONSES,
    )
    def compare_projection_profiles(
        request: Request,
        player_keys: str = Query(..., min_length=1),
        dataset: Literal["all", "bat", "pitch"] = "all",
        include_dynasty: bool = True,
        calculator_job_id: str | None = None,
        career_totals: bool = True,
        year: int | None = None,
        years: str | None = None,
        dynasty_years: str | None = None,
    ):
        return projection_compare_handler(
            request=request,
            player_keys=player_keys,
            dataset=dataset,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
            career_totals=career_totals,
            year=year,
            years=years,
            dynasty_years=dynasty_years,
        )

    @router.get("/api/projections/export/{dataset}")
    def export_projections(
        request: Request,
        dataset: Literal["all", "bat", "pitch"],
        query: Annotated[ProjectionExportQueryParams, Depends()],
        file_format: Literal["csv", "xlsx"] = Query(default="csv", alias="format"),
    ):
        return projection_export_handler(
            dataset=dataset,
            file_format=file_format,
            player=query.player,
            team=query.team,
            player_keys=query.player_keys,
            year=query.year,
            years=query.years,
            pos=query.pos,
            dynasty_years=query.dynasty_years,
            career_totals=query.career_totals,
            include_dynasty=query.include_dynasty,
            calculator_job_id=query.calculator_job_id,
            sort_col=query.sort_col,
            sort_dir=query.sort_dir,
            columns=query.columns,
            request=request,
        )

    return router
