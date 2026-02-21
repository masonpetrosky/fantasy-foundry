"""Runtime endpoint handler adapters that compose orchestration contexts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from fastapi import Request

from backend.core.calculator_orchestration import (
    calculate_dynasty_values as core_calculate_dynasty_values,
)
from backend.core.calculator_orchestration import (
    cancel_calculate_dynasty_job as core_cancel_calculate_dynasty_job,
)
from backend.core.calculator_orchestration import (
    create_calculate_dynasty_job as core_create_calculate_dynasty_job,
)
from backend.core.calculator_orchestration import (
    export_calculate_dynasty_values as core_export_calculate_dynasty_values,
)
from backend.core.calculator_orchestration import (
    get_calculate_dynasty_job as core_get_calculate_dynasty_job,
)
from backend.core.calculator_orchestration import (
    run_calculation_job as core_run_calculation_job,
)
from backend.core.status_orchestration import (
    build_meta_payload as core_build_meta_payload,
)
from backend.core.status_orchestration import (
    build_version_payload as core_build_version_payload,
)
from backend.core.status_orchestration import (
    dynasty_lookup_cache_health_payload as core_dynasty_lookup_cache_health_payload,
)
from backend.core.status_orchestration import (
    etag_matches as core_etag_matches,
)
from backend.core.status_orchestration import get_health as core_get_health
from backend.core.status_orchestration import get_meta as core_get_meta
from backend.core.status_orchestration import get_ops as core_get_ops
from backend.core.status_orchestration import get_ready as core_get_ready
from backend.core.status_orchestration import get_version as core_get_version
from backend.core.status_orchestration import payload_etag as core_payload_etag


@dataclass(slots=True)
class RuntimeEndpointHandlerConfig:
    status_orchestration_context_getter: Callable[[], Any]
    calculator_orchestration_context_getter: Callable[[], Any]
    projection_service_getter: Callable[[], Any]
    run_calculate_request_getter: Callable[[], Callable[..., dict]]
    enforce_rate_limit_getter: Callable[[], Callable[..., None]]
    projection_rate_limit_per_minute_getter: Callable[[], int]
    projection_export_rate_limit_per_minute_getter: Callable[[], int]


class RuntimeEndpointHandlers:
    def __init__(self, config: RuntimeEndpointHandlerConfig):
        self._config = config

    def _status_orchestration_context(self) -> Any:
        return self._config.status_orchestration_context_getter()

    def _calculator_orchestration_context(self) -> Any:
        return self._config.calculator_orchestration_context_getter()

    def meta_payload(self) -> dict[str, Any]:
        return core_build_meta_payload(ctx=self._status_orchestration_context())

    def get_meta(self, request: Request):
        return core_get_meta(request, ctx=self._status_orchestration_context())

    def version_payload(self) -> dict[str, Any]:
        return core_build_version_payload(ctx=self._status_orchestration_context())

    def payload_etag(self, payload: dict[str, Any]) -> str:
        return core_payload_etag(payload)

    def etag_matches(self, if_none_match: str | None, current_etag: str) -> bool:
        return core_etag_matches(if_none_match, current_etag)

    def get_version(self, request: Request):
        return core_get_version(request, ctx=self._status_orchestration_context())

    def dynasty_lookup_cache_health_payload(self) -> dict[str, Any]:
        return core_dynasty_lookup_cache_health_payload(ctx=self._status_orchestration_context())

    def get_health(self):
        return core_get_health(ctx=self._status_orchestration_context())

    def get_ready(self):
        return core_get_ready(ctx=self._status_orchestration_context())

    def get_ops(self):
        return core_get_ops(ctx=self._status_orchestration_context())

    def run_calculation_job(self, job_id: str, req_payload: dict) -> None:
        core_run_calculation_job(
            job_id,
            req_payload,
            ctx=self._calculator_orchestration_context(),
            run_calculate_request=self._config.run_calculate_request_getter(),
        )

    def projection_response(
        self,
        dataset: Literal["all", "bat", "pitch"],
        *,
        request: Request,
        player: str | None,
        team: str | None,
        player_keys: str | None,
        year: int | None,
        years: str | None,
        pos: str | None,
        dynasty_years: str | None,
        career_totals: bool,
        include_dynasty: bool,
        calculator_job_id: str | None,
        sort_col: str | None,
        sort_dir: Literal["asc", "desc"],
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        self._config.enforce_rate_limit_getter()(
            request,
            action="proj-read",
            limit_per_minute=self._config.projection_rate_limit_per_minute_getter(),
        )
        return self._config.projection_service_getter().projection_response(
            dataset,
            player=player,
            team=team,
            player_keys=player_keys,
            year=year,
            years=years,
            pos=pos,
            dynasty_years=dynasty_years,
            career_totals=career_totals,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
            sort_col=sort_col,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    def export_projections(
        self,
        *,
        request: Request,
        dataset: Literal["all", "bat", "pitch"],
        file_format: Literal["csv", "xlsx"] = "csv",
        player: str | None = None,
        team: str | None = None,
        player_keys: str | None = None,
        year: int | None = None,
        years: str | None = None,
        pos: str | None = None,
        dynasty_years: str | None = None,
        career_totals: bool = False,
        include_dynasty: bool = True,
        calculator_job_id: str | None = None,
        sort_col: str | None = None,
        sort_dir: Literal["asc", "desc"] = "desc",
        columns: str | None = None,
    ):
        self._config.enforce_rate_limit_getter()(
            request,
            action="proj-export",
            limit_per_minute=self._config.projection_export_rate_limit_per_minute_getter(),
        )
        return self._config.projection_service_getter().export_projections(
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
            calculator_job_id=calculator_job_id,
            sort_col=sort_col,
            sort_dir=sort_dir,
            columns=columns,
        )

    def calculate_dynasty_values(self, req: Any, request: Request):
        return core_calculate_dynasty_values(
            req,
            request,
            ctx=self._calculator_orchestration_context(),
            run_calculate_request=self._config.run_calculate_request_getter(),
        )

    def export_calculate_dynasty_values(self, req: Any, request: Request):
        return core_export_calculate_dynasty_values(
            req,
            request,
            ctx=self._calculator_orchestration_context(),
            run_calculate_request=self._config.run_calculate_request_getter(),
        )

    def create_calculate_dynasty_job(self, req: Any, request: Request):
        return core_create_calculate_dynasty_job(
            req,
            request,
            ctx=self._calculator_orchestration_context(),
            run_calculation_job=self.run_calculation_job,
        )

    def get_calculate_dynasty_job(self, job_id: str, request: Request):
        return core_get_calculate_dynasty_job(
            job_id,
            request,
            ctx=self._calculator_orchestration_context(),
        )

    def cancel_calculate_dynasty_job(self, job_id: str, request: Request):
        return core_cancel_calculate_dynasty_job(
            job_id,
            request,
            ctx=self._calculator_orchestration_context(),
        )


def build_runtime_endpoint_handlers(config: RuntimeEndpointHandlerConfig) -> RuntimeEndpointHandlers:
    return RuntimeEndpointHandlers(config)
