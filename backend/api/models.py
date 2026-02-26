from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    request_id: str
    detail: Any | None = None

    model_config = ConfigDict(extra="allow")


class ProjectionRow(BaseModel):
    model_config = ConfigDict(extra="allow")


class ProjectionListResponse(BaseModel):
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
    data: list[ProjectionRow]


class ProjectionMatchedPlayer(BaseModel):
    player_entity_key: str | None = None
    player_key: str | None = None
    player: str | None = None
    team: str | None = None
    pos: str | None = None

    model_config = ConfigDict(extra="allow")


class ProjectionProfileResponse(BaseModel):
    player_id: str
    dataset: Literal["all", "bat", "pitch"]
    include_dynasty: bool
    series_total: int = Field(ge=0)
    career_totals_total: int = Field(ge=0)
    matched_players: list[ProjectionMatchedPlayer]
    series: list[ProjectionRow]
    career_totals: list[ProjectionRow]

    model_config = ConfigDict(extra="allow")


class ProjectionCompareResponse(BaseModel):
    dataset: Literal["all", "bat", "pitch"]
    include_dynasty: bool
    career_totals: bool
    requested_player_keys: list[str]
    matched_player_keys: list[str]
    total: int = Field(ge=0)
    data: list[ProjectionRow]

    model_config = ConfigDict(extra="allow")


class MetaResponse(BaseModel):
    calculator_guardrails: dict[str, Any]
    projection_freshness: dict[str, Any]
    last_projection_update: str | None = None
    projection_window_start: int | None = None
    projection_window_end: int | None = None

    model_config = ConfigDict(extra="allow")


class VersionResponse(BaseModel):
    build_id: str
    commit_sha: str | None = None
    built_at: str | None = None
    data_version: str
    projection_freshness: dict[str, Any]

    model_config = ConfigDict(extra="allow")


class HealthResponse(BaseModel):
    status: Literal["ok"]
    build_id: str
    projection_rows: dict[str, int]
    jobs: dict[str, int]
    dynasty_lookup_cache: dict[str, Any]
    result_cache: dict[str, Any]
    calculator_prewarm: dict[str, Any]
    timestamp: str

    model_config = ConfigDict(extra="allow")


class ReadyResponse(BaseModel):
    status: Literal["ready"]
    build_id: str
    data_version: str
    timestamp: str
    checks: dict[str, Any]

    model_config = ConfigDict(extra="allow")


class OpsResponse(BaseModel):
    status: Literal["ok"]
    build: dict[str, Any]
    data: dict[str, Any]
    runtime: dict[str, Any]
    rate_limits: dict[str, Any]
    queues: dict[str, Any]
    timestamp: str

    model_config = ConfigDict(extra="allow")
