from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Standardized error envelope returned by all 4xx/5xx responses."""

    error_code: str = Field(description="Machine-readable error category (e.g. 'validation_error', 'rate_limited')")
    message: str = Field(description="Human-readable error summary")
    request_id: str = Field(description="Unique request identifier for tracing")
    detail: Any | None = Field(default=None, description="Additional error context (field errors for 422, etc.)")

    model_config = ConfigDict(extra="allow")


class ProjectionRow(BaseModel):
    """A single player projection row with dynamic stat columns."""

    model_config = ConfigDict(extra="allow")


class ProjectionListResponse(BaseModel):
    """Paginated list of player projections."""

    total: int = Field(ge=0, description="Total matching rows before pagination")
    offset: int = Field(ge=0, description="Number of rows skipped")
    limit: int = Field(ge=1, description="Maximum rows returned per page")
    data: list[ProjectionRow] = Field(description="Projection rows for the current page")


class ProjectionMatchedPlayer(BaseModel):
    """Identity summary for a matched player in profile/compare responses."""

    player_entity_key: str | None = Field(default=None, description="Disambiguated player entity key")
    player_key: str | None = Field(default=None, description="Normalized player name key")
    player: str | None = Field(default=None, description="Display name")
    team: str | None = Field(default=None, description="MLB team abbreviation")
    pos: str | None = Field(default=None, description="Position eligibility (e.g. 'SS/2B')")

    model_config = ConfigDict(extra="allow")


class ProjectionProfileResponse(BaseModel):
    """Full player profile with year-by-year series and career totals."""

    player_id: str = Field(description="Requested player key or entity key")
    dataset: Literal["all", "bat", "pitch"] = Field(description="Projection dataset queried")
    include_dynasty: bool = Field(description="Whether dynasty values are attached")
    series_total: int = Field(ge=0, description="Total year-by-year projection rows")
    career_totals_total: int = Field(ge=0, description="Total career summary rows")
    matched_players: list[ProjectionMatchedPlayer] = Field(description="Players matched by the player_id")
    series: list[ProjectionRow] = Field(description="Year-by-year projection rows")
    career_totals: list[ProjectionRow] = Field(description="Career total aggregation rows")

    model_config = ConfigDict(extra="allow")


class ProjectionCompareResponse(BaseModel):
    """Side-by-side comparison of multiple players."""

    dataset: Literal["all", "bat", "pitch"] = Field(description="Projection dataset queried")
    include_dynasty: bool = Field(description="Whether dynasty values are attached")
    career_totals: bool = Field(description="Whether rows are career aggregations")
    requested_player_keys: list[str] = Field(description="Player keys requested for comparison")
    matched_player_keys: list[str] = Field(description="Player keys actually found in projections")
    total: int = Field(ge=0, description="Total rows in comparison")
    data: list[ProjectionRow] = Field(description="Projection rows for compared players")

    model_config = ConfigDict(extra="allow")


class MetaResponse(BaseModel):
    """Application metadata including calculator guardrails and projection freshness."""

    calculator_guardrails: dict[str, Any] = Field(description="Calculator input bounds and defaults")
    projection_freshness: dict[str, Any] = Field(description="Projection data age and update timestamps")
    last_projection_update: str | None = Field(default=None, description="ISO date of newest projection data")
    projection_window_start: int | None = Field(default=None, description="First projection year available")
    projection_window_end: int | None = Field(default=None, description="Last projection year available")

    model_config = ConfigDict(extra="allow")


class VersionResponse(BaseModel):
    """Build and data version information."""

    build_id: str = Field(description="Application build identifier")
    commit_sha: str | None = Field(default=None, description="Git commit SHA of the deployed build")
    built_at: str | None = Field(default=None, description="ISO timestamp of when the build was created")
    data_version: str = Field(description="Content hash of loaded projection data files")
    projection_freshness: dict[str, Any] = Field(description="Projection data age and update timestamps")

    model_config = ConfigDict(extra="allow")


class HealthResponse(BaseModel):
    """Detailed health check with subsystem status."""

    status: Literal["ok"] = Field(description="Overall health status")
    build_id: str = Field(description="Application build identifier")
    projection_rows: dict[str, int] = Field(description="Row counts by dataset (bat, pitch)")
    jobs: dict[str, int] = Field(description="Calculator job counts by status")
    dynasty_lookup_cache: dict[str, Any] = Field(description="Precomputed dynasty lookup cache status")
    result_cache: dict[str, Any] = Field(description="Calculator result cache status (local + Redis)")
    calculator_prewarm: dict[str, Any] = Field(description="Calculator prewarm status")
    timestamp: str = Field(description="ISO timestamp of the health check")

    model_config = ConfigDict(extra="allow")


class ReadyResponse(BaseModel):
    """Readiness probe confirming all subsystems are operational."""

    status: Literal["ready"] = Field(description="Readiness status")
    build_id: str = Field(description="Application build identifier")
    data_version: str = Field(description="Content hash of loaded projection data files")
    timestamp: str = Field(description="ISO timestamp of the readiness check")
    checks: dict[str, Any] = Field(description="Individual subsystem check results")

    model_config = ConfigDict(extra="allow")


class OpsResponse(BaseModel):
    """Operational dashboard with detailed runtime, rate limit, and queue metrics."""

    status: Literal["ok"] = Field(description="Overall operational status")
    build: dict[str, Any] = Field(description="Build and deployment metadata")
    data: dict[str, Any] = Field(description="Data version and freshness details")
    runtime: dict[str, Any] = Field(description="Runtime configuration (CORS, auth, proxy, Redis)")
    rate_limits: dict[str, Any] = Field(description="Configured rate limit thresholds")
    queues: dict[str, Any] = Field(description="Job queue pressure and cache metrics")
    timestamp: str = Field(description="ISO timestamp of the ops snapshot")

    model_config = ConfigDict(extra="allow")
