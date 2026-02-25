"""Projection runtime-boundary helpers owned by the projections service layer."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import HTTPException

from backend.core.data_refresh import (
    reload_projection_data as core_reload_projection_data,
)
from backend.core.dynasty_lookup_orchestration import (
    attach_dynasty_values as core_attach_dynasty_values,
)
from backend.core.dynasty_lookup_orchestration import (
    parse_dynasty_years as core_parse_dynasty_years,
)
from backend.core.dynasty_lookup_orchestration import (
    resolve_projection_year_filter as core_resolve_projection_year_filter,
)

DynastyLookup = tuple[dict[str, dict], dict[str, dict], set[str], list[str]]


@dataclass(slots=True)
class ProjectionRateLimits:
    read_per_minute: int
    export_per_minute: int


@dataclass(slots=True)
class ProjectionDynastyHelpers:
    year_range_token_re: re.Pattern[str]
    get_default_dynasty_lookup: Callable[[], DynastyLookup]
    normalize_player_key: Callable[[object], str]
    player_key_col: str
    player_entity_key_col: str
    lookup_required_error_type: type[Exception]

    def parse_dynasty_years(self, raw: str | None, *, valid_years: list[int] | None = None) -> list[int]:
        return core_parse_dynasty_years(
            raw,
            valid_years=valid_years,
            year_range_token_re=self.year_range_token_re,
        )

    def resolve_projection_year_filter(
        self,
        year: int | None,
        years: str | None,
        *,
        valid_years: list[int] | None = None,
    ) -> set[int] | None:
        return core_resolve_projection_year_filter(
            year,
            years,
            valid_years=valid_years,
            parse_dynasty_years_fn=lambda raw: self.parse_dynasty_years(raw, valid_years=valid_years),
        )

    def attach_dynasty_values(self, rows: list[dict], dynasty_years: list[int] | None = None) -> list[dict]:
        try:
            return core_attach_dynasty_values(
                rows,
                dynasty_years=dynasty_years,
                get_default_dynasty_lookup=self.get_default_dynasty_lookup,
                normalize_player_key=self.normalize_player_key,
                player_key_col=self.player_key_col,
                player_entity_key_col=self.player_entity_key_col,
            )
        except self.lookup_required_error_type as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


def reload_projection_data(
    *,
    load_json: Callable[[str], Any],
    with_player_identity_keys: Callable[[list[dict], list[dict]], tuple[list[dict], list[dict]]],
    average_recent_projection_rows: Callable[..., list[dict]],
    projection_freshness_payload: Callable[[list[dict], list[dict]], dict[str, Any]],
) -> tuple[dict, list[dict], list[dict], list[dict], list[dict], dict[str, Any]]:
    return core_reload_projection_data(
        load_json=load_json,
        with_player_identity_keys=with_player_identity_keys,
        average_recent_projection_rows=average_recent_projection_rows,
        projection_freshness_payload=projection_freshness_payload,
    )
