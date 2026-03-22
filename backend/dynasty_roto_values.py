"""Legacy compatibility surface for dynasty valuation helpers and CLI."""

from __future__ import annotations

import importlib

try:
    from backend.valuation import assignment as _assignment
    from backend.valuation import common_math_compat as _common_math_compat
    from backend.valuation import dynasty_aggregation as _dynasty_aggregation
    from backend.valuation import minor_eligibility_compat as _minor_elig_compat
    from backend.valuation import models as _models
    from backend.valuation import positions as _positions
    from backend.valuation import projection_compat as _projection_compat
    from backend.valuation import year_context as _year_context
except ImportError:
    from valuation import assignment as _assignment  # type: ignore[no-redef]
    from valuation import common_math_compat as _common_math_compat  # type: ignore[no-redef]
    from valuation import dynasty_aggregation as _dynasty_aggregation  # type: ignore[no-redef]
    from valuation import minor_eligibility_compat as _minor_elig_compat  # type: ignore[no-redef]
    from valuation import models as _models  # type: ignore[no-redef]
    from valuation import positions as _positions  # type: ignore[no-redef]
    from valuation import projection_compat as _projection_compat  # type: ignore[no-redef]
    from valuation import year_context as _year_context  # type: ignore[no-redef]


HAVE_SCIPY = _assignment.HAVE_SCIPY
assign_players_to_slots = _assignment.assign_players_to_slots
assign_players_to_slots_with_vacancy_fill = _assignment.assign_players_to_slots_with_vacancy_fill
build_slot_list = _assignment.build_slot_list
build_team_slot_template = _assignment.build_team_slot_template
expand_slot_counts = _assignment.expand_slot_counts
validate_assigned_slots = _assignment.validate_assigned_slots

HIT_CATS = _models.HIT_CATS
HIT_COMPONENT_COLS = _models.HIT_COMPONENT_COLS
PIT_CATS = _models.PIT_CATS
PIT_COMPONENT_COLS = _models.PIT_COMPONENT_COLS
CommonDynastyRotoSettings = _models.CommonDynastyRotoSettings
CommonYearContext = _year_context.CommonYearContext

eligible_hit_slots = _positions.eligible_hit_slots
eligible_pit_slots = _positions.eligible_pit_slots
parse_hit_positions = _positions.parse_hit_positions
parse_pit_positions = _positions.parse_pit_positions

PROJECTION_DATE_COLS = _projection_compat.PROJECTION_DATE_COLS
PLAYER_KEY_COL = _projection_compat.PLAYER_KEY_COL
PLAYER_ENTITY_KEY_COL = _projection_compat.PLAYER_ENTITY_KEY_COL
PLAYER_KEY_PATTERN = _projection_compat.PLAYER_KEY_PATTERN
DERIVED_HIT_RATE_COLS = _projection_compat.DERIVED_HIT_RATE_COLS
DERIVED_PIT_RATE_COLS = _projection_compat.DERIVED_PIT_RATE_COLS
COMMON_COLUMN_ALIASES = _projection_compat.COMMON_COLUMN_ALIASES

_find_projection_date_col = _projection_compat._find_projection_date_col
_normalize_player_key = _projection_compat._normalize_player_key
_normalize_team_key = _projection_compat._normalize_team_key
_normalize_year_key = _projection_compat._normalize_year_key
_team_column_for_dataframe = _projection_compat._team_column_for_dataframe
_add_player_identity_keys = _projection_compat._add_player_identity_keys
_build_player_identity_lookup = _projection_compat._build_player_identity_lookup
_attach_identity_columns_to_output = _projection_compat._attach_identity_columns_to_output
average_recent_projections = _projection_compat.average_recent_projections
projection_meta_for_start_year = _projection_compat.projection_meta_for_start_year
numeric_stat_cols_for_recent_avg = _projection_compat.numeric_stat_cols_for_recent_avg
reorder_detail_columns = _projection_compat.reorder_detail_columns
recompute_common_rates_hit = _projection_compat.recompute_common_rates_hit
recompute_common_rates_pit = _projection_compat.recompute_common_rates_pit
require_cols = _projection_compat.require_cols
normalize_input_schema = _projection_compat.normalize_input_schema
_xlsx_apply_header_style = _projection_compat._xlsx_apply_header_style
_xlsx_set_freeze_filters_and_view = _projection_compat._xlsx_set_freeze_filters_and_view
_xlsx_add_table = _projection_compat._xlsx_add_table
_xlsx_set_column_widths = _projection_compat._xlsx_set_column_widths
_xlsx_apply_number_formats = _projection_compat._xlsx_apply_number_formats
_xlsx_add_value_color_scale = _projection_compat._xlsx_add_value_color_scale
_xlsx_format_player_values = _projection_compat._xlsx_format_player_values
_xlsx_format_detail_sheet = _projection_compat._xlsx_format_detail_sheet

COMMON_REVERSED_PITCH_CATS = _common_math_compat.COMMON_REVERSED_PITCH_CATS
zscore = _common_math_compat.zscore
_active_common_hit_categories = _common_math_compat._active_common_hit_categories
_active_common_pitch_categories = _common_math_compat._active_common_pitch_categories
initial_hitter_weight = _common_math_compat.initial_hitter_weight
initial_pitcher_weight = _common_math_compat.initial_pitcher_weight
team_avg = _common_math_compat.team_avg
team_obp = _common_math_compat.team_obp
team_ops = _common_math_compat.team_ops
team_era = _common_math_compat.team_era
team_whip = _common_math_compat.team_whip
common_hit_category_totals = _common_math_compat.common_hit_category_totals
common_pitch_category_totals = _common_math_compat.common_pitch_category_totals
common_replacement_pitcher_rates = _common_math_compat.common_replacement_pitcher_rates
common_apply_pitching_bounds = _common_math_compat.common_apply_pitching_bounds
_coerce_non_negative_float = _common_math_compat._coerce_non_negative_float
_low_volume_positive_credit_scale = _common_math_compat._low_volume_positive_credit_scale
_apply_low_volume_non_ratio_positive_guard = _common_math_compat._apply_low_volume_non_ratio_positive_guard
_apply_low_volume_ratio_guard = _common_math_compat._apply_low_volume_ratio_guard
_mean_adjacent_rank_gap = _common_math_compat._mean_adjacent_rank_gap
simulate_sgp_hit = _common_math_compat.simulate_sgp_hit
simulate_sgp_pit = _common_math_compat.simulate_sgp_pit
compute_year_context = _common_math_compat.compute_year_context
compute_year_player_values = _common_math_compat.compute_year_player_values
compute_replacement_baselines = _common_math_compat.compute_replacement_baselines
compute_year_player_values_vs_replacement = _common_math_compat.compute_year_player_values_vs_replacement
combine_two_way = _common_math_compat.combine_two_way

BENCH_STASH_MIN_PENALTY = _minor_elig_compat.BENCH_STASH_MIN_PENALTY
BENCH_STASH_MAX_PENALTY = _minor_elig_compat.BENCH_STASH_MAX_PENALTY
BENCH_STASH_PENALTY_GAMMA = _minor_elig_compat.BENCH_STASH_PENALTY_GAMMA
_infer_minor_eligibility_by_year = _minor_elig_compat._infer_minor_eligibility_by_year
infer_minor_eligible = _minor_elig_compat.infer_minor_eligible
_non_vacant_player_names = _minor_elig_compat._non_vacant_player_names
_players_with_playing_time = _minor_elig_compat._players_with_playing_time
_select_mlb_roster_with_active_floor = _minor_elig_compat._select_mlb_roster_with_active_floor
_estimate_bench_negative_penalty = _minor_elig_compat._estimate_bench_negative_penalty
_bench_stash_round_penalty = _minor_elig_compat._bench_stash_round_penalty
_build_bench_stash_penalty_map = _minor_elig_compat._build_bench_stash_penalty_map
_apply_negative_value_stash_rules = _minor_elig_compat._apply_negative_value_stash_rules
_fillna_bool = _minor_elig_compat._fillna_bool
_normalize_minor_eligibility = _minor_elig_compat._normalize_minor_eligibility
minor_eligibility_by_year_from_input = _minor_elig_compat.minor_eligibility_by_year_from_input
minor_eligibility_from_input = _minor_elig_compat.minor_eligibility_from_input
_resolve_minor_eligibility_by_year = _minor_elig_compat._resolve_minor_eligibility_by_year

dynasty_keep_or_drop_value = _dynasty_aggregation.dynasty_keep_or_drop_value


def calculate_common_dynasty_values(
    excel_path: str,
    lg: CommonDynastyRotoSettings,
    start_year: int | None = None,
    years: list[int] | None = None,
    verbose: bool = True,
    return_details: bool = False,
    seed: int = 0,
):
    """Compatibility wrapper delegating to extracted common orchestration."""
    module_name = "backend.valuation.common_orchestration"
    try:  # pragma: no branch
        orchestration_module = importlib.import_module(module_name)
    except ImportError:  # pragma: no cover - direct script execution fallback
        orchestration_module = importlib.import_module("valuation.common_orchestration")
    return orchestration_module.calculate_common_dynasty_values(
        excel_path,
        lg,
        start_year=start_year,
        years=years,
        verbose=verbose,
        return_details=return_details,
        seed=seed,
    )


def main() -> None:
    module_name = "backend.valuation.cli"
    try:  # pragma: no branch
        cli_module = importlib.import_module(module_name)
    except ImportError:  # pragma: no cover - direct script execution fallback
        cli_module = importlib.import_module("valuation.cli")
    cli_module.main()


if __name__ == "__main__":
    main()
