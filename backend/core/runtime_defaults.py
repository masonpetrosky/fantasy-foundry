"""Shared runtime defaults and export formatting constants."""

from __future__ import annotations

EXPORT_HEADER_LABEL_OVERRIDES = {
    "Type": "Side",
    "OldestProjectionDate": "Oldest Proj Date",
    "DynastyValue": "Dynasty Value",
    "RawDynastyValue": "Raw Dynasty Value",
    "YearValue": "Year Value",
    "DiscountFactor": "Discount Factor",
    "DiscountedContribution": "Discounted Contribution",
    "HittingPoints": "Hitting Points",
    "PitchingPoints": "Pitching Points",
    "SelectedPoints": "Selected Points",
    "SelectedSide": "Selected Side",
    "HittingBestSlot": "Hitting Best Slot",
    "PitchingBestSlot": "Pitching Best Slot",
    "HittingValue": "Hitting Value",
    "PitchingValue": "Pitching Value",
    "HittingAssignmentSlot": "Hitting Assignment Slot",
    "PitchingAssignmentSlot": "Pitching Assignment Slot",
    "HittingAssignmentValue": "Hitting Assignment Value",
    "PitchingAssignmentValue": "Pitching Assignment Value",
    "HittingAssignmentReplacement": "Hitting Assignment Replacement",
    "PitchingAssignmentReplacement": "Pitching Assignment Replacement",
    "KeepDropValue": "Keep/Drop Value",
    "KeepDropHoldValue": "Keep/Drop Hold Value",
    "KeepDropKeep": "Keep/Drop Keep",
    "HittingRulePoints": "Hitting Rule Points",
    "PitchingRulePoints": "Pitching Rule Points",
    "Years": "Years",
    "PitH": "P H",
    "PitHR": "P HR",
    "PitBB": "P BB",
}

EXPORT_THREE_DECIMAL_COLS = {"AVG", "OBP", "SLG", "OPS"}

EXPORT_TWO_DECIMAL_COLS = {
    "DynastyValue",
    "RawDynastyValue",
    "YearValue",
    "DiscountFactor",
    "DiscountedContribution",
    "HittingPoints",
    "PitchingPoints",
    "SelectedPoints",
    "HittingValue",
    "PitchingValue",
    "HittingAssignmentValue",
    "PitchingAssignmentValue",
    "HittingAssignmentReplacement",
    "PitchingAssignmentReplacement",
    "KeepDropValue",
    "KeepDropHoldValue",
    "ERA",
    "WHIP",
}

EXPORT_WHOLE_NUMBER_COLS = {
    "AB",
    "R",
    "HR",
    "RBI",
    "SB",
    "IP",
    "W",
    "K",
    "SVH",
    "QS",
    "QA3",
    "G",
    "H",
    "2B",
    "3B",
    "BB",
    "SO",
    "GS",
    "L",
    "PitBB",
    "SV",
    "PitH",
    "PitHR",
    "ER",
    "TB",
}

EXPORT_INTEGER_COLS = {"Rank", "Year", "Age"}
EXPORT_DATE_COLS = {"OldestProjectionDate"}

COMMON_HITTER_SLOT_DEFAULTS = {
    "C": 1,
    "1B": 1,
    "2B": 1,
    "3B": 1,
    "SS": 1,
    "CI": 1,
    "MI": 1,
    "OF": 5,
    "DH": 0,
    "UT": 1,
}
COMMON_PITCHER_SLOT_DEFAULTS = {
    "P": 9,
    "SP": 0,
    "RP": 0,
}
POINTS_HITTER_SLOT_DEFAULTS = {
    "C": 1,
    "1B": 1,
    "2B": 1,
    "3B": 1,
    "SS": 1,
    "CI": 0,
    "MI": 0,
    "OF": 3,
    "DH": 0,
    "UT": 1,
}
POINTS_PITCHER_SLOT_DEFAULTS = {
    "P": 2,
    "SP": 5,
    "RP": 2,
}
DEFAULT_POINTS_SCORING = {
    "pts_hit_1b": 1.0,
    "pts_hit_2b": 2.0,
    "pts_hit_3b": 3.0,
    "pts_hit_hr": 4.0,
    "pts_hit_r": 1.0,
    "pts_hit_rbi": 1.0,
    "pts_hit_sb": 1.0,
    "pts_hit_bb": 1.0,
    "pts_hit_hbp": 0.0,
    "pts_hit_so": -1.0,
    "pts_pit_ip": 3.0,
    "pts_pit_w": 5.0,
    "pts_pit_l": -5.0,
    "pts_pit_k": 1.0,
    "pts_pit_sv": 5.0,
    "pts_pit_hld": 0.0,
    "pts_pit_h": -1.0,
    "pts_pit_er": -2.0,
    "pts_pit_bb": -1.0,
    "pts_pit_hbp": 0.0,
}
COMMON_DEFAULT_IR_SLOTS = 0
COMMON_DEFAULT_MINOR_SLOTS = 0
COMMON_HITTER_STARTER_SLOTS_PER_TEAM = sum(COMMON_HITTER_SLOT_DEFAULTS.values())
COMMON_PITCHER_STARTER_SLOTS_PER_TEAM = sum(COMMON_PITCHER_SLOT_DEFAULTS.values())
