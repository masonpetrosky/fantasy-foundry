from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Literal, Optional

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
from backend.services.projections import profile_ops, query_ops
from backend.services.projections.filters import (
    career_group_key,
    coerce_record_year,
    merge_position_value,
    normalize_filter_value,
    normalize_player_keys_filter,
    parse_player_keys_filter,
    position_sort_key,
    position_tokens,
    projection_merge_key,
    row_overlay_lookup_key,
    row_player_filter_keys,
    row_team_value,
    value_col_sort_key,
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

            # StatDynasty_* columns are attached by the dynasty lookup
            try:
                lookup_by_entity, _, _, _ = ctx.dynasty_helpers.get_default_dynasty_lookup()
                sample = next(iter(lookup_by_entity.values()), None)
                if sample and isinstance(sample, dict):
                    cols.update(k for k in sample if isinstance(k, str) and k.startswith("StatDynasty_"))
            except (KeyError, StopIteration, TypeError):
                pass

            return frozenset(cols)

        self._cached_projection_rows = cached_projection_rows
        self._cached_all_projection_rows = cached_all_projection_rows
        self._projection_sortable_columns_for_dataset = projection_sortable_columns_for_dataset

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Delegating helpers (thin wrappers around extracted module functions)
    # ------------------------------------------------------------------

    def _coerce_record_year(self, value: object) -> int | None:
        return coerce_record_year(value)

    def _position_tokens(self, value: object) -> set[str]:
        return position_tokens(value, split_re=self._ctx.position_token_split_re)

    def _normalize_player_keys_filter(self, value: str | None) -> str:
        return normalize_player_keys_filter(value)

    def _parse_player_keys_filter(self, value: str | None) -> set[str] | None:
        return parse_player_keys_filter(value)

    def _row_player_filter_keys(self, row: dict) -> set[str]:
        return row_player_filter_keys(
            row,
            player_key_col=self._ctx.player_key_col,
            player_entity_key_col=self._ctx.player_entity_key_col,
        )

    @staticmethod
    def _normalize_filter_value(value: str | None) -> str:
        return normalize_filter_value(value)

    @staticmethod
    def _value_col_sort_key(col: str) -> tuple[int, int | str]:
        return value_col_sort_key(col)

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
        return position_sort_key(token, position_display_order=self._ctx.position_display_order)

    @staticmethod
    def _row_team_value(row: dict) -> str:
        return row_team_value(row)

    def _projection_merge_key(self, row: dict) -> tuple[str, object, str]:
        return projection_merge_key(
            row,
            player_entity_key_col=self._ctx.player_entity_key_col,
            player_key_col=self._ctx.player_key_col,
        )

    def _merge_position_value(self, hit_pos: object, pit_pos: object) -> str | None:
        return merge_position_value(
            hit_pos,
            pit_pos,
            split_re=self._ctx.position_token_split_re,
            position_display_order=self._ctx.position_display_order,
        )

    def _career_group_key(self, row: dict) -> str:
        return career_group_key(
            row,
            player_key_col=self._ctx.player_key_col,
            player_entity_key_col=self._ctx.player_entity_key_col,
            normalize_player_key_fn=self._ctx.normalize_player_key,
        )

    def _row_overlay_lookup_key(self, row: dict) -> str:
        return row_overlay_lookup_key(
            row,
            player_entity_key_col=self._ctx.player_entity_key_col,
            player_key_col=self._ctx.player_key_col,
        )

    # ------------------------------------------------------------------
    # Aggregation / merge / sort / overlay (still delegate to core_*)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Public: filter_records
    # ------------------------------------------------------------------

    def filter_records(
        self,
        records: list[dict],
        player: str | None,
        team: str | None,
        years: set[int] | None,
        pos: str | None,
        player_keys: set[str] | None = None,
    ) -> list[dict]:
        return query_ops.filter_records(self, records, player, team, years, pos, player_keys)

    # ------------------------------------------------------------------
    # Private: row fetching
    # ------------------------------------------------------------------

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
        return query_ops.get_projection_rows(
            self,
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
            sort_col=sort_col,
            sort_dir=sort_dir,
        )

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
        return query_ops.get_all_projection_rows(
            self,
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
            sort_col=sort_col,
            sort_dir=sort_dir,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        return query_ops.projection_response(
            self,
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

    def projection_profile(
        self,
        *,
        player_id: str,
        dataset: ProjectionDataset = "all",
        include_dynasty: bool = True,
        calculator_job_id: str | None = None,
    ) -> dict[str, Any]:
        return profile_ops.projection_profile(
            self,
            player_id=player_id,
            dataset=dataset,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
        )

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
        return profile_ops.projection_compare(
            self,
            player_keys=player_keys,
            dataset=dataset,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
            career_totals=career_totals,
            year=year,
            years=years,
            dynasty_years=dynasty_years,
        )

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
        return query_ops.export_projections(
            self,
            dataset,
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
