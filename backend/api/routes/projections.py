from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, Optional

from fastapi import APIRouter, Query


ProjectionResponseHandler = Callable[..., dict[str, Any]]
ProjectionExportHandler = Callable[..., Any]


def build_projections_router(
    *,
    projection_response_handler: ProjectionResponseHandler,
    projection_export_handler: ProjectionExportHandler,
) -> APIRouter:
    """Create projections query/export routes with injected handlers."""
    router = APIRouter(tags=["projections"])

    @router.get("/api/projections/all")
    def get_all_projections(
        player: Optional[str] = None,
        team: Optional[str] = None,
        player_keys: Optional[str] = None,
        year: Optional[int] = None,
        years: Optional[str] = None,
        pos: Optional[str] = None,
        dynasty_years: Optional[str] = None,
        career_totals: bool = False,
        include_dynasty: bool = True,
        sort_col: Optional[str] = None,
        sort_dir: Literal["asc", "desc"] = "desc",
        limit: int = Query(default=200, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
    ):
        return projection_response_handler(
            "all",
            player=player,
            team=team,
            player_keys=player_keys,
            year=year,
            years=years,
            pos=pos,
            dynasty_years=dynasty_years,
            career_totals=career_totals,
            include_dynasty=include_dynasty,
            sort_col=sort_col,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    @router.get("/api/projections/bat")
    def get_bat_projections(
        player: Optional[str] = None,
        team: Optional[str] = None,
        player_keys: Optional[str] = None,
        year: Optional[int] = None,
        years: Optional[str] = None,
        pos: Optional[str] = None,
        dynasty_years: Optional[str] = None,
        career_totals: bool = False,
        include_dynasty: bool = True,
        sort_col: Optional[str] = None,
        sort_dir: Literal["asc", "desc"] = "desc",
        limit: int = Query(default=200, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
    ):
        return projection_response_handler(
            "bat",
            player=player,
            team=team,
            player_keys=player_keys,
            year=year,
            years=years,
            pos=pos,
            dynasty_years=dynasty_years,
            career_totals=career_totals,
            include_dynasty=include_dynasty,
            sort_col=sort_col,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    @router.get("/api/projections/pitch")
    def get_pitch_projections(
        player: Optional[str] = None,
        team: Optional[str] = None,
        player_keys: Optional[str] = None,
        year: Optional[int] = None,
        years: Optional[str] = None,
        pos: Optional[str] = None,
        dynasty_years: Optional[str] = None,
        career_totals: bool = False,
        include_dynasty: bool = True,
        sort_col: Optional[str] = None,
        sort_dir: Literal["asc", "desc"] = "desc",
        limit: int = Query(default=200, ge=1, le=5000),
        offset: int = Query(default=0, ge=0),
    ):
        return projection_response_handler(
            "pitch",
            player=player,
            team=team,
            player_keys=player_keys,
            year=year,
            years=years,
            pos=pos,
            dynasty_years=dynasty_years,
            career_totals=career_totals,
            include_dynasty=include_dynasty,
            sort_col=sort_col,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    @router.get("/api/projections/export/{dataset}")
    def export_projections(
        dataset: Literal["all", "bat", "pitch"],
        file_format: Literal["csv", "xlsx"] = Query(default="csv", alias="format"),
        player: Optional[str] = None,
        team: Optional[str] = None,
        player_keys: Optional[str] = None,
        year: Optional[int] = None,
        years: Optional[str] = None,
        pos: Optional[str] = None,
        dynasty_years: Optional[str] = None,
        career_totals: bool = False,
        include_dynasty: bool = True,
        sort_col: Optional[str] = None,
        sort_dir: Literal["asc", "desc"] = "desc",
    ):
        return projection_export_handler(
            dataset=dataset,
            file_format=file_format,
            player=player,
            team=team,
            player_keys=player_keys,
            year=year,
            years=years,
            pos=pos,
            dynasty_years=dynasty_years,
            career_totals=career_totals,
            include_dynasty=include_dynasty,
            sort_col=sort_col,
            sort_dir=sort_dir,
        )

    return router
