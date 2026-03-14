"""Export-related helpers extracted from ProjectionService."""

from __future__ import annotations

from typing import Any, Callable, Literal

from backend.core.projections_export import (
    apply_calculator_overlay_values as core_apply_calculator_overlay_values,
)
from backend.core.projections_export import (
    parse_export_columns as core_parse_export_columns,
)
from backend.core.projections_export import (
    default_projection_export_columns as core_default_projection_export_columns,
)

from backend.services.projections.filters import (
    normalize_filter_value,
    row_overlay_lookup_key,
    value_col_sort_key,
)

ProjectionDataset = Literal["all", "bat", "pitch"]
PROJECTION_HITTER_CORE_EXPORT_COLS: tuple[str, ...] = ("AB", "R", "HR", "RBI", "SB", "AVG", "OPS")
PROJECTION_PITCHER_CORE_EXPORT_COLS: tuple[str, ...] = ("IP", "W", "K", "SV", "ERA", "WHIP", "QS", "QA3")


def parse_export_columns(value: str | None) -> list[str]:
    """Parse user-specified export columns string."""
    return core_parse_export_columns(value)


def default_projection_export_columns(
    rows: list[dict],
    *,
    dataset: ProjectionDataset,
    career_totals: bool,
) -> list[str]:
    """Compute the default ordered list of columns for projection export."""
    return core_default_projection_export_columns(
        rows,
        dataset=dataset,
        career_totals=career_totals,
        hitter_core_export_cols=PROJECTION_HITTER_CORE_EXPORT_COLS,
        pitcher_core_export_cols=PROJECTION_PITCHER_CORE_EXPORT_COLS,
        value_col_sort_key_fn=value_col_sort_key,
    )


def apply_calculator_overlay_values(
    rows: list[dict],
    *,
    include_dynasty: bool,
    calculator_job_id: str | None,
    calculator_overlay_values_for_job_fn: Callable[[str | None], dict[str, dict[str, Any]]],
    player_entity_key_col: str,
    player_key_col: str,
) -> list[dict]:
    """Attach calculator overlay values to projection rows."""
    return core_apply_calculator_overlay_values(
        rows,
        include_dynasty=include_dynasty,
        calculator_job_id=calculator_job_id,
        normalize_filter_value_fn=normalize_filter_value,
        calculator_overlay_values_for_job_fn=calculator_overlay_values_for_job_fn,
        row_overlay_lookup_key_fn=lambda row: row_overlay_lookup_key(
            row,
            player_entity_key_col=player_entity_key_col,
            player_key_col=player_key_col,
        ),
    )
