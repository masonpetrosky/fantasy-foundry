"""Position parsing and slot-eligibility helpers."""

from __future__ import annotations

import re
from typing import Set

import pandas as pd

POSITION_SPLIT_RE = re.compile(r"[\s\/,;|+\-]+")


def _normalize_position_tokens(pos_str: str) -> Set[str]:
    """Split a raw position field into normalized uppercase tokens."""
    if pd.isna(pos_str):
        return set()

    normalized = POSITION_SPLIT_RE.sub("/", str(pos_str).upper())
    return {p.strip() for p in normalized.split("/") if p.strip()}


def parse_hit_positions(pos_str: str) -> Set[str]:
    tokens = _normalize_position_tokens(pos_str)
    if not tokens:
        return set()

    aliases = {
        "LF": "OF",
        "CF": "OF",
        "RF": "OF",
        "DH": "UT",
        "UTIL": "UT",
        "U": "UT",
    }
    return {aliases.get(token, token) for token in tokens}


def eligible_hit_slots(pos_set: Set[str]) -> Set[str]:
    """
    Common roto eligibility mapping:
      - UT for any hitter
      - CI if 1B or 3B
      - MI if 2B or SS
    """
    if not pos_set:
        return set()

    slots: Set[str] = {"UT"}
    if "C" in pos_set:
        slots.add("C")
    if "1B" in pos_set:
        slots.update({"1B", "CI"})
    if "3B" in pos_set:
        slots.update({"3B", "CI"})
    if "2B" in pos_set:
        slots.update({"2B", "MI"})
    if "SS" in pos_set:
        slots.update({"SS", "MI"})
    if "OF" in pos_set:
        slots.add("OF")
    if "CI" in pos_set:
        slots.add("CI")
    if "MI" in pos_set:
        slots.add("MI")
    return slots


def parse_pit_positions(pos_str: str) -> Set[str]:
    tokens = _normalize_position_tokens(pos_str)
    if not tokens:
        return set()

    aliases = {
        "RHP": "SP",
        "LHP": "SP",
    }
    return {aliases.get(token, token) for token in tokens}


def eligible_pit_slots(pos_set: Set[str]) -> Set[str]:
    """
    Common setup uses SP/RP/P slots.
    Pitchers are always eligible for P and role-matched slots when available.
    """
    if not pos_set:
        return set()
    slots: Set[str] = {"P"}
    if "SP" in pos_set:
        slots.add("SP")
    if "RP" in pos_set:
        slots.add("RP")
    return slots


__all__ = [
    "parse_hit_positions",
    "eligible_hit_slots",
    "parse_pit_positions",
    "eligible_pit_slots",
]
