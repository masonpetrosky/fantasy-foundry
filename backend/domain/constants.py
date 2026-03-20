"""Shared domain constants used across backend modules."""

from __future__ import annotations

PLAYER_KEY_COL = "PlayerKey"
PLAYER_ENTITY_KEY_COL = "PlayerEntityKey"

CALCULATOR_RESULT_STAT_EXPORT_ORDER: tuple[str, ...] = (
    "R",
    "RBI",
    "HR",
    "SB",
    "AVG",
    "OBP",
    "SLG",
    "OPS",
    "H",
    "BB",
    "2B",
    "TB",
    "W",
    "K",
    "SV",
    "ERA",
    "WHIP",
    "QS",
    "QA3",
    "SVH",
)
CALCULATOR_RESULT_POINTS_EXPORT_ORDER: tuple[str, ...] = (
    "HittingPoints",
    "PitchingPoints",
    "SelectedPoints",
    "HittingBestSlot",
    "PitchingBestSlot",
    "HittingValue",
    "PitchingValue",
    "HittingAssignmentSlot",
    "PitchingAssignmentSlot",
    "HittingAssignmentValue",
    "PitchingAssignmentValue",
    "KeepDropValue",
    "KeepDropHoldValue",
    "KeepDropKeep",
)

ROTO_HITTER_CATEGORY_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("roto_hit_r", "R", True),
    ("roto_hit_rbi", "RBI", True),
    ("roto_hit_hr", "HR", True),
    ("roto_hit_sb", "SB", True),
    ("roto_hit_avg", "AVG", True),
    ("roto_hit_obp", "OBP", False),
    ("roto_hit_slg", "SLG", False),
    ("roto_hit_ops", "OPS", False),
    ("roto_hit_h", "H", False),
    ("roto_hit_bb", "BB", False),
    ("roto_hit_2b", "2B", False),
    ("roto_hit_tb", "TB", False),
)
ROTO_PITCHER_CATEGORY_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("roto_pit_w", "W", True),
    ("roto_pit_k", "K", True),
    ("roto_pit_sv", "SV", True),
    ("roto_pit_era", "ERA", True),
    ("roto_pit_whip", "WHIP", True),
    ("roto_pit_qs", "QS", False),
    ("roto_pit_qa3", "QA3", False),
    ("roto_pit_svh", "SVH", False),
)
ROTO_CATEGORY_FIELD_DEFAULTS: dict[str, bool] = {
    field_key: bool(default)
    for field_key, _stat_col, default in (
        *ROTO_HITTER_CATEGORY_FIELDS,
        *ROTO_PITCHER_CATEGORY_FIELDS,
    )
}
