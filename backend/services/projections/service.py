from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Literal, Optional

from fastapi import HTTPException

from backend.core.projections_aggregation import (
    aggregate_all_projection_career_rows as core_aggregate_all_projection_career_rows,
)
from backend.core.projections_aggregation import (
    aggregate_projection_career_rows as core_aggregate_projection_career_rows,
)
from backend.core.projections_aggregation import (
    merge_all_projection_rows as core_merge_all_projection_rows,
)
from backend.core.projections_export import (
    apply_calculator_overlay_values as core_apply_calculator_overlay_values,
)
from backend.core.projections_export import (
    default_projection_export_columns as core_default_projection_export_columns,
)
from backend.core.projections_export import (
    normalize_sort_dir as core_normalize_sort_dir,
)
from backend.core.projections_export import (
    parse_export_columns as core_parse_export_columns,
)
from backend.core.projections_export import (
    sort_projection_rows as core_sort_projection_rows,
)
from backend.core.projections_export import (
    validate_sort_col as core_validate_sort_col,
)
from backend.services.projections.runtime_boundaries import (
    ProjectionDynastyHelpers,
    ProjectionRateLimits,
)

ProjectionDataset = Literal["all", "bat", "pitch"]
PROJECTION_HITTER_CORE_EXPORT_COLS: tuple[str, ...] = ("AB", "R", "HR", "RBI", "SB", "AVG", "OPS")
PROJECTION_PITCHER_CORE_EXPORT_COLS: tuple[str, ...] = ("IP", "W", "K", "SV", "ERA", "WHIP", "QS", "QA3")


@dataclass
class ProjectionServiceContext:
    refresh_data_if_needed: Callable[[], None]
    get_bat_data: Callable[[], list[dict]]
    get_pit_data: Callable[[], list[dict]]
    get_meta: Callable[[], dict[str, Any]]
    normalize_player_key: Callable[[object], str]
    dynasty_helpers: ProjectionDynastyHelpers
    coerce_meta_years: Callable[[dict[str, Any] | None], list[int]]
    tabular_export_response: Callable[..., Any]
    calculator_overlay_values_for_job: Callable[[str | None], dict[str, dict[str, Any]]]
    player_key_col: str
    player_entity_key_col: str
    position_token_split_re: re.Pattern[str]
    position_display_order: tuple[str, ...]
    projection_text_sort_cols: set[str]
    all_tab_hitter_stat_cols: tuple[str, ...]
    all_tab_pitch_stat_cols: tuple[str, ...]
    projection_query_cache_maxsize: int
    rate_limits: ProjectionRateLimits
    filter_records: Callable[..., Any] | None = None

    def parse_dynasty_years(self, raw: str | None, *, valid_years: list[int] | None = None) -> list[int]:
        return self.dynasty_helpers.parse_dynasty_years(raw, valid_years=valid_years)

    def resolve_projection_year_filter(
        self,
        year: int | None,
        years: str | None,
        *,
        valid_years: list[int] | None = None,
    ) -> set[int] | None:
        return self.dynasty_helpers.resolve_projection_year_filter(
            year,
            years,
            valid_years=valid_years,
        )

    def attach_dynasty_values(self, rows: list[dict], dynasty_years: list[int] | None = None) -> list[dict]:
        return self.dynasty_helpers.attach_dynasty_values(rows, dynasty_years=dynasty_years)


class ProjectionService:
    """Projection query pipeline with cached filtering/sorting/aggregation."""

    def __init__(self, ctx: ProjectionServiceContext):
        self._ctx = ctx

        @lru_cache(maxsize=ctx.projection_query_cache_maxsize)
        def cached_projection_rows(
            dataset: Literal["bat", "pitch"],
            player: str,
            team: str,
            player_keys: str,
            year: int | None,
            years: str,
            pos: str,
            include_dynasty: bool,
            dynasty_years: str,
            career_totals: bool,
        ) -> tuple[dict, ...]:
            valid_years = ctx.coerce_meta_years(ctx.get_meta())
            requested_years = ctx.resolve_projection_year_filter(
                year,
                years or None,
                valid_years=valid_years,
            )
            records = ctx.get_bat_data() if dataset == "bat" else ctx.get_pit_data()
            filter_impl = ctx.filter_records or self.filter_records
            filtered = filter_impl(
                records,
                player or None,
                team or None,
                requested_years,
                pos or None,
                self._parse_player_keys_filter(player_keys),
            )
            if career_totals:
                filtered = self._aggregate_projection_career_rows(filtered, is_hitter=(dataset == "bat"))
            if include_dynasty:
                filtered = ctx.attach_dynasty_values(
                    filtered,
                    ctx.parse_dynasty_years(dynasty_years or None, valid_years=valid_years),
                )
            return tuple(filtered)

        @lru_cache(maxsize=ctx.projection_query_cache_maxsize)
        def cached_all_projection_rows(
            player: str,
            team: str,
            player_keys: str,
            year: int | None,
            years: str,
            pos: str,
            include_dynasty: bool,
            dynasty_years: str,
            career_totals: bool,
        ) -> tuple[dict, ...]:
            valid_years = ctx.coerce_meta_years(ctx.get_meta())
            requested_years = ctx.resolve_projection_year_filter(
                year,
                years or None,
                valid_years=valid_years,
            )
            player_key_filter = self._parse_player_keys_filter(player_keys)
            filter_impl = ctx.filter_records or self.filter_records
            hit_filtered = filter_impl(
                ctx.get_bat_data(),
                player or None,
                team or None,
                requested_years,
                None,
                player_key_filter,
            )
            pit_filtered = filter_impl(
                ctx.get_pit_data(),
                player or None,
                team or None,
                requested_years,
                None,
                player_key_filter,
            )
            merged = (
                self._aggregate_all_projection_career_rows(hit_filtered, pit_filtered)
                if career_totals
                else self._merge_all_projection_rows(hit_filtered, pit_filtered)
            )
            if pos:
                requested_positions = self._position_tokens(pos)
                if requested_positions:
                    merged = [
                        row
                        for row in merged
                        if requested_positions.intersection(self._position_tokens(row.get("Pos", "")))
                    ]
            if include_dynasty:
                merged = ctx.attach_dynasty_values(
                    merged,
                    ctx.parse_dynasty_years(dynasty_years or None, valid_years=valid_years),
                )
            return tuple(merged)

        @lru_cache(maxsize=4)
        def projection_sortable_columns_for_dataset(dataset: ProjectionDataset) -> frozenset[str]:
            if dataset == "bat":
                base_records = ctx.get_bat_data()
            elif dataset == "pitch":
                base_records = ctx.get_pit_data()
            else:
                base_records = list(ctx.get_bat_data()) + list(ctx.get_pit_data())

            cols: set[str] = {
                "Player",
                "Team",
                "Pos",
                "Year",
                "Years",
                "YearStart",
                "YearEnd",
                "Age",
                "ProjectionsUsed",
                "OldestProjectionDate",
                "DynastyValue",
                "DynastyMatchStatus",
                ctx.player_key_col,
                ctx.player_entity_key_col,
            }
            if dataset == "all":
                cols.update({"Type", "PitH", "PitHR", "PitBB"})

            for record in base_records:
                cols.update(record.keys())

            for year in ctx.coerce_meta_years(ctx.get_meta()):
                cols.add(f"Value_{year}")

            return frozenset(cols)

        self._cached_projection_rows = cached_projection_rows
        self._cached_all_projection_rows = cached_all_projection_rows
        self._projection_sortable_columns_for_dataset = projection_sortable_columns_for_dataset

    def clear_caches(self) -> None:
        self._cached_projection_rows.cache_clear()
        self._cached_all_projection_rows.cache_clear()
        self._projection_sortable_columns_for_dataset.cache_clear()

    @property
    def projection_rate_limit_per_minute(self) -> int:
        return self._ctx.rate_limits.read_per_minute

    @property
    def projection_export_rate_limit_per_minute(self) -> int:
        return self._ctx.rate_limits.export_per_minute

    def parse_dynasty_years(self, raw: str | None, *, valid_years: list[int] | None = None) -> list[int]:
        return self._ctx.dynasty_helpers.parse_dynasty_years(raw, valid_years=valid_years)

    def resolve_projection_year_filter(
        self,
        year: int | None,
        years: str | None,
        *,
        valid_years: list[int] | None = None,
    ) -> set[int] | None:
        return self._ctx.dynasty_helpers.resolve_projection_year_filter(
            year,
            years,
            valid_years=valid_years,
        )

    def attach_dynasty_values(self, rows: list[dict], dynasty_years: list[int] | None = None) -> list[dict]:
        return self._ctx.dynasty_helpers.attach_dynasty_values(rows, dynasty_years=dynasty_years)

    def _coerce_record_year(self, value: object) -> int | None:
        """Normalize JSON year values from int/float/string to int for robust filtering."""
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else None
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                parsed = float(text)
            except ValueError:
                return None
            return int(parsed) if parsed.is_integer() else None
        return None

    def _position_tokens(self, value: object) -> set[str]:
        text = str(value or "").strip().upper()
        if not text:
            return set()
        return {token for token in self._ctx.position_token_split_re.split(text) if token}

    def _normalize_player_keys_filter(self, value: str | None) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        tokens = sorted({token.strip().lower() for token in re.split(r"[\s,]+", text) if token.strip()})
        return ",".join(tokens)

    def _parse_player_keys_filter(self, value: str | None) -> set[str] | None:
        normalized = self._normalize_player_keys_filter(value)
        if not normalized:
            return None
        return {token for token in normalized.split(",") if token}

    def _row_player_filter_keys(self, row: dict) -> set[str]:
        keys: set[str] = set()
        entity_key = str(row.get(self._ctx.player_entity_key_col) or "").strip().lower()
        if entity_key:
            keys.add(entity_key)
        player_key = str(row.get(self._ctx.player_key_col) or "").strip().lower()
        if player_key:
            keys.add(player_key)
        return keys

    @staticmethod
    def _normalize_filter_value(value: str | None) -> str:
        return (value or "").strip()

    @staticmethod
    def _value_col_sort_key(col: str) -> tuple[int, int | str]:
        suffix = col.split("_", 1)[1] if "_" in col else col
        return (0, int(suffix)) if str(suffix).isdigit() else (1, suffix)

    def _parse_export_columns(self, value: str | None) -> list[str]:
        return core_parse_export_columns(value)

    def _default_projection_export_columns(
        self,
        rows: list[dict],
        *,
        dataset: ProjectionDataset,
        career_totals: bool,
    ) -> list[str]:
        return core_default_projection_export_columns(
            rows,
            dataset=dataset,
            career_totals=career_totals,
            hitter_core_export_cols=PROJECTION_HITTER_CORE_EXPORT_COLS,
            pitcher_core_export_cols=PROJECTION_PITCHER_CORE_EXPORT_COLS,
            value_col_sort_key_fn=self._value_col_sort_key,
        )

    def _position_sort_key(self, token: str) -> tuple[int, str]:
        order_map = {pos: idx for idx, pos in enumerate(self._ctx.position_display_order)}
        return (order_map.get(token, len(order_map)), token)

    @staticmethod
    def _row_team_value(row: dict) -> str:
        return str(row.get("Team") or row.get("MLBTeam") or "").strip()

    def _projection_merge_key(self, row: dict) -> tuple[str, object, str]:
        player = str(
            row.get(self._ctx.player_entity_key_col)
            or row.get(self._ctx.player_key_col)
            or row.get("Player", "")
        ).strip()
        parsed_year = self._coerce_record_year(row.get("Year"))
        merge_year: object = parsed_year if parsed_year is not None else str(row.get("Year", "")).strip()
        team = self._row_team_value(row).upper()
        return player, merge_year, team

    def _merge_position_value(self, hit_pos: object, pit_pos: object) -> str | None:
        tokens = self._position_tokens(hit_pos) | self._position_tokens(pit_pos)
        if tokens:
            return "/".join(sorted(tokens, key=self._position_sort_key))
        hit_text = str(hit_pos or "").strip()
        if hit_text:
            return hit_text
        pit_text = str(pit_pos or "").strip()
        return pit_text or None

    def _career_group_key(self, row: dict) -> str:
        player_name = str(row.get("Player", "")).strip()
        player_key = str(row.get(self._ctx.player_key_col) or "").strip() or self._ctx.normalize_player_key(player_name)
        return str(row.get(self._ctx.player_entity_key_col) or "").strip() or player_key

    def _aggregate_projection_career_rows(self, rows: list[dict], *, is_hitter: bool) -> list[dict]:
        return core_aggregate_projection_career_rows(
            rows,
            is_hitter=is_hitter,
            career_group_key_fn=self._career_group_key,
            row_team_value_fn=self._row_team_value,
            normalize_player_key_fn=self._ctx.normalize_player_key,
            player_key_col=self._ctx.player_key_col,
            player_entity_key_col=self._ctx.player_entity_key_col,
            position_tokens_fn=self._position_tokens,
            position_sort_key_fn=self._position_sort_key,
            coerce_record_year_fn=self._coerce_record_year,
        )

    def _aggregate_all_projection_career_rows(self, hit_rows: list[dict], pit_rows: list[dict]) -> list[dict]:
        return core_aggregate_all_projection_career_rows(
            hit_rows,
            pit_rows,
            aggregate_projection_career_rows_fn=lambda rows, is_hitter: self._aggregate_projection_career_rows(
                rows,
                is_hitter=is_hitter,
            ),
            career_group_key_fn=self._career_group_key,
            row_team_value_fn=self._row_team_value,
            merge_position_value_fn=self._merge_position_value,
            coerce_record_year_fn=self._coerce_record_year,
            all_tab_hitter_stat_cols=self._ctx.all_tab_hitter_stat_cols,
            all_tab_pitch_stat_cols=self._ctx.all_tab_pitch_stat_cols,
        )

    @staticmethod
    def _normalize_sort_dir(value: str | None) -> Literal["asc", "desc"]:
        return core_normalize_sort_dir(value)

    def _validate_sort_col(self, sort_col: str | None, *, dataset: ProjectionDataset) -> str | None:
        return core_validate_sort_col(
            sort_col,
            dataset=dataset,
            normalize_filter_value_fn=self._normalize_filter_value,
            sortable_columns_for_dataset_fn=self._projection_sortable_columns_for_dataset,
        )

    def _row_overlay_lookup_key(self, row: dict) -> str:
        entity_key = str(row.get(self._ctx.player_entity_key_col) or "").strip().lower()
        if entity_key:
            return entity_key
        return str(row.get(self._ctx.player_key_col) or "").strip().lower()

    def _apply_calculator_overlay_values(
        self,
        rows: list[dict],
        *,
        include_dynasty: bool,
        calculator_job_id: str | None,
    ) -> list[dict]:
        return core_apply_calculator_overlay_values(
            rows,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
            normalize_filter_value_fn=self._normalize_filter_value,
            calculator_overlay_values_for_job_fn=self._ctx.calculator_overlay_values_for_job,
            row_overlay_lookup_key_fn=self._row_overlay_lookup_key,
        )

    def _sort_projection_rows(self, rows: list[dict], sort_col: str | None, sort_dir: str | None) -> list[dict]:
        return core_sort_projection_rows(
            rows,
            sort_col=sort_col,
            sort_dir=sort_dir,
            projection_text_sort_cols=self._ctx.projection_text_sort_cols,
            player_key_col=self._ctx.player_key_col,
            player_entity_key_col=self._ctx.player_entity_key_col,
        )

    def _merge_all_projection_rows(self, hit_rows: list[dict], pit_rows: list[dict]) -> list[dict]:
        return core_merge_all_projection_rows(
            hit_rows,
            pit_rows,
            projection_merge_key_fn=self._projection_merge_key,
            row_team_value_fn=self._row_team_value,
            merge_position_value_fn=self._merge_position_value,
            all_tab_hitter_stat_cols=self._ctx.all_tab_hitter_stat_cols,
            all_tab_pitch_stat_cols=self._ctx.all_tab_pitch_stat_cols,
        )

    def filter_records(
        self,
        records: list[dict],
        player: str | None,
        team: str | None,
        years: set[int] | None,
        pos: str | None,
        player_keys: set[str] | None = None,
    ) -> list[dict]:
        out = records
        if player:
            q = player.strip().lower()
            out = [r for r in out if q in str(r.get("Player", "")).lower()]
        if team:
            team_normalized = team.strip().lower()
            out = [
                r
                for r in out
                if str(r.get("Team", "")).strip().lower() == team_normalized
                or str(r.get("MLBTeam", "")).strip().lower() == team_normalized
            ]
        if years is not None:
            out = [r for r in out if self._coerce_record_year(r.get("Year")) in years]
        if pos:
            requested_positions = self._position_tokens(pos)
            if requested_positions:
                out = [
                    r for r in out if requested_positions.intersection(self._position_tokens(r.get("Pos", "")))
                ]
        if player_keys:
            out = [r for r in out if player_keys.intersection(self._row_player_filter_keys(r))]
        return out

    def _get_projection_rows(
        self,
        dataset: Literal["bat", "pitch"],
        *,
        player: str | None,
        team: str | None,
        player_keys: str | None,
        year: int | None,
        years: str | None,
        pos: str | None,
        include_dynasty: bool,
        dynasty_years: str | None,
        calculator_job_id: str | None,
        career_totals: bool,
        sort_col: str | None,
        sort_dir: str | None,
    ) -> tuple[dict, ...]:
        cached_rows = self._cached_projection_rows(
            dataset,
            self._normalize_filter_value(player),
            self._normalize_filter_value(team),
            self._normalize_player_keys_filter(player_keys),
            year,
            self._normalize_filter_value(years),
            self._normalize_filter_value(pos),
            include_dynasty,
            self._normalize_filter_value(dynasty_years),
            career_totals,
        )
        with_overlay = self._apply_calculator_overlay_values(
            list(cached_rows),
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
        )
        sorted_rows = self._sort_projection_rows(
            with_overlay,
            self._normalize_filter_value(sort_col),
            self._normalize_sort_dir(sort_dir),
        )
        return tuple(sorted_rows)

    def _get_all_projection_rows(
        self,
        *,
        player: str | None,
        team: str | None,
        player_keys: str | None,
        year: int | None,
        years: str | None,
        pos: str | None,
        include_dynasty: bool,
        dynasty_years: str | None,
        calculator_job_id: str | None,
        career_totals: bool,
        sort_col: str | None,
        sort_dir: str | None,
    ) -> tuple[dict, ...]:
        cached_rows = self._cached_all_projection_rows(
            self._normalize_filter_value(player),
            self._normalize_filter_value(team),
            self._normalize_player_keys_filter(player_keys),
            year,
            self._normalize_filter_value(years),
            self._normalize_filter_value(pos),
            include_dynasty,
            self._normalize_filter_value(dynasty_years),
            career_totals,
        )
        with_overlay = self._apply_calculator_overlay_values(
            list(cached_rows),
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
        )
        sorted_rows = self._sort_projection_rows(
            with_overlay,
            self._normalize_filter_value(sort_col),
            self._normalize_sort_dir(sort_dir),
        )
        return tuple(sorted_rows)

    def projection_response(
        self,
        dataset: ProjectionDataset,
        *,
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
        sort_dir: str,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        self._ctx.refresh_data_if_needed()
        validated_sort_col = self._validate_sort_col(sort_col, dataset=dataset)
        if dataset == "all":
            filtered = self._get_all_projection_rows(
                player=player,
                team=team,
                player_keys=player_keys,
                year=year,
                years=years,
                pos=pos,
                include_dynasty=include_dynasty,
                dynasty_years=dynasty_years,
                calculator_job_id=calculator_job_id,
                career_totals=career_totals,
                sort_col=validated_sort_col,
                sort_dir=sort_dir,
            )
        else:
            filtered = self._get_projection_rows(
                dataset,
                player=player,
                team=team,
                player_keys=player_keys,
                year=year,
                years=years,
                pos=pos,
                include_dynasty=include_dynasty,
                dynasty_years=dynasty_years,
                calculator_job_id=calculator_job_id,
                career_totals=career_totals,
                sort_col=validated_sort_col,
                sort_dir=sort_dir,
            )
        total = len(filtered)
        page = list(filtered[offset : offset + limit])
        return {"total": total, "offset": offset, "limit": limit, "data": page}

    def projection_profile(
        self,
        *,
        player_id: str,
        dataset: ProjectionDataset = "all",
        include_dynasty: bool = True,
        calculator_job_id: str | None = None,
    ) -> dict[str, Any]:
        normalized_player_id = self._normalize_filter_value(player_id)
        if not normalized_player_id:
            raise HTTPException(status_code=422, detail="player_id is required.")

        series = self.projection_response(
            dataset,
            player=None,
            team=None,
            player_keys=normalized_player_id,
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
        )
        career_totals = self.projection_response(
            dataset,
            player=None,
            team=None,
            player_keys=normalized_player_id,
            year=None,
            years=None,
            pos=None,
            dynasty_years=None,
            career_totals=True,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
            sort_col="DynastyValue",
            sort_dir="desc",
            limit=5000,
            offset=0,
        )

        matched_players: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for row in career_totals.get("data", []):
            player_entity_key = str(row.get(self._ctx.player_entity_key_col) or "").strip()
            player_key = str(row.get(self._ctx.player_key_col) or "").strip()
            identity_key = player_entity_key or player_key
            if not identity_key or identity_key in seen_keys:
                continue
            seen_keys.add(identity_key)
            matched_players.append(
                {
                    "player_entity_key": player_entity_key or None,
                    "player_key": player_key or None,
                    "player": str(row.get("Player") or "").strip() or None,
                    "team": self._row_team_value(row) or None,
                    "pos": str(row.get("Pos") or "").strip() or None,
                }
            )

        return {
            "player_id": normalized_player_id,
            "dataset": dataset,
            "include_dynasty": bool(include_dynasty),
            "series_total": int(series.get("total", 0)),
            "career_totals_total": int(career_totals.get("total", 0)),
            "matched_players": matched_players,
            "series": list(series.get("data", [])),
            "career_totals": list(career_totals.get("data", [])),
        }

    def projection_compare(
        self,
        *,
        player_keys: str,
        dataset: ProjectionDataset = "all",
        include_dynasty: bool = True,
        calculator_job_id: str | None = None,
        career_totals: bool = True,
        year: int | None = None,
        years: str | None = None,
        dynasty_years: str | None = None,
    ) -> dict[str, Any]:
        requested_player_keys = self._parse_player_keys_filter(player_keys)
        if not requested_player_keys or len(requested_player_keys) < 2:
            raise HTTPException(
                status_code=422,
                detail="player_keys must include at least two PlayerKey or PlayerEntityKey values.",
            )
        normalized_player_keys = ",".join(sorted(requested_player_keys))
        resolved_year = None if career_totals else year
        resolved_years = None if career_totals else years
        sort_col = "DynastyValue" if career_totals else "Year"
        sort_dir = "desc" if career_totals else "asc"
        response = self.projection_response(
            dataset,
            player=None,
            team=None,
            player_keys=normalized_player_keys,
            year=resolved_year,
            years=resolved_years,
            pos=None,
            dynasty_years=dynasty_years,
            career_totals=career_totals,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
            sort_col=sort_col,
            sort_dir=sort_dir,
            limit=5000,
            offset=0,
        )
        matched_player_keys = sorted(
            {
                str(row.get(self._ctx.player_entity_key_col) or row.get(self._ctx.player_key_col) or "").strip()
                for row in response.get("data", [])
                if str(row.get(self._ctx.player_entity_key_col) or row.get(self._ctx.player_key_col) or "").strip()
            }
        )
        return {
            "dataset": dataset,
            "include_dynasty": bool(include_dynasty),
            "career_totals": bool(career_totals),
            "requested_player_keys": sorted(requested_player_keys),
            "matched_player_keys": matched_player_keys,
            "total": int(response.get("total", 0)),
            "data": list(response.get("data", [])),
        }

    def export_projections(
        self,
        dataset: ProjectionDataset,
        file_format: Literal["csv", "xlsx"] = "csv",
        player: Optional[str] = None,
        team: Optional[str] = None,
        player_keys: Optional[str] = None,
        year: Optional[int] = None,
        years: Optional[str] = None,
        pos: Optional[str] = None,
        dynasty_years: Optional[str] = None,
        career_totals: bool = False,
        include_dynasty: bool = True,
        calculator_job_id: Optional[str] = None,
        sort_col: Optional[str] = None,
        sort_dir: Literal["asc", "desc"] = "desc",
        columns: Optional[str] = None,
    ):
        self._ctx.refresh_data_if_needed()
        validated_sort_col = self._validate_sort_col(sort_col, dataset=dataset)
        if dataset == "all":
            rows = list(
                self._get_all_projection_rows(
                    player=player,
                    team=team,
                    player_keys=player_keys,
                    year=year,
                    years=years,
                    pos=pos,
                    include_dynasty=include_dynasty,
                    dynasty_years=dynasty_years,
                    calculator_job_id=calculator_job_id,
                    career_totals=career_totals,
                    sort_col=validated_sort_col,
                    sort_dir=sort_dir,
                )
            )
        else:
            rows = list(
                self._get_projection_rows(
                    dataset,
                    player=player,
                    team=team,
                    player_keys=player_keys,
                    year=year,
                    years=years,
                    pos=pos,
                    include_dynasty=include_dynasty,
                    dynasty_years=dynasty_years,
                    calculator_job_id=calculator_job_id,
                    career_totals=career_totals,
                    sort_col=validated_sort_col,
                    sort_dir=sort_dir,
                )
            )

        requested_export_columns = self._parse_export_columns(columns)
        default_export_columns = self._default_projection_export_columns(
            rows,
            dataset=dataset,
            career_totals=career_totals,
        )
        return self._ctx.tabular_export_response(
            rows,
            filename_base=f"projections-{dataset}",
            file_format=file_format,
            selected_columns=requested_export_columns,
            default_columns=default_export_columns,
            required_columns=["Player"],
            disallowed_columns=[
                self._ctx.player_key_col,
                self._ctx.player_entity_key_col,
                "DynastyMatchStatus",
                "RawDynastyValue",
                "minor_eligible",
            ],
        )
