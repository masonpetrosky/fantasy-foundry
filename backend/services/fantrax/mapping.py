"""Player matching and settings mapping between Fantrax and Fantasy Foundry."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from backend.services.fantrax.models import (
    LeagueInfo,
    LeagueSuggestedSettings,
    MatchedPlayer,
    MatchedRoster,
    RosterPlayer,
)

# Fantrax stat name → FF roto category key
_FANTRAX_ROTO_HIT_MAP: dict[str, str] = {
    "R": "roto_hit_r",
    "Runs": "roto_hit_r",
    "RBI": "roto_hit_rbi",
    "HR": "roto_hit_hr",
    "Home Runs": "roto_hit_hr",
    "SB": "roto_hit_sb",
    "Stolen Bases": "roto_hit_sb",
    "AVG": "roto_hit_avg",
    "Batting Average": "roto_hit_avg",
    "OBP": "roto_hit_obp",
    "On-Base Percentage": "roto_hit_obp",
    "SLG": "roto_hit_slg",
    "Slugging Percentage": "roto_hit_slg",
    "OPS": "roto_hit_ops",
    "H": "roto_hit_h",
    "Hits": "roto_hit_h",
    "BB": "roto_hit_bb",
    "Walks": "roto_hit_bb",
    "2B": "roto_hit_2b",
    "Doubles": "roto_hit_2b",
    "TB": "roto_hit_tb",
    "Total Bases": "roto_hit_tb",
}

_FANTRAX_ROTO_PIT_MAP: dict[str, str] = {
    "W": "roto_pit_w",
    "Wins": "roto_pit_w",
    "K": "roto_pit_k",
    "SO": "roto_pit_k",
    "Strikeouts": "roto_pit_k",
    "SV": "roto_pit_sv",
    "Saves": "roto_pit_sv",
    "ERA": "roto_pit_era",
    "Earned Run Average": "roto_pit_era",
    "WHIP": "roto_pit_whip",
    "QS": "roto_pit_qs",
    "Quality Starts": "roto_pit_qs",
    "SVH": "roto_pit_svh",
    "SV+H": "roto_pit_svh",
    "Saves + Holds": "roto_pit_svh",
}

_ALL_ROTO_KEYS = {
    "roto_hit_r",
    "roto_hit_rbi",
    "roto_hit_hr",
    "roto_hit_sb",
    "roto_hit_avg",
    "roto_hit_obp",
    "roto_hit_slg",
    "roto_hit_ops",
    "roto_hit_h",
    "roto_hit_bb",
    "roto_hit_2b",
    "roto_hit_tb",
    "roto_pit_w",
    "roto_pit_k",
    "roto_pit_sv",
    "roto_pit_era",
    "roto_pit_whip",
    "roto_pit_qs",
    "roto_pit_qa3",
    "roto_pit_svh",
}

# Fantrax position → FF slot key
_FANTRAX_SLOT_MAP: dict[str, str] = {
    "C": "hit_c",
    "1B": "hit_1b",
    "2B": "hit_2b",
    "3B": "hit_3b",
    "SS": "hit_ss",
    "CI": "hit_ci",
    "MI": "hit_mi",
    "OF": "hit_of",
    "UT": "hit_ut",
    "UTIL": "hit_ut",
    "DH": "hit_ut",
    "P": "pit_p",
    "SP": "pit_sp",
    "RP": "pit_rp",
}

_NAME_SUFFIX_RE = re.compile(
    r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", re.IGNORECASE
)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_name(name: str) -> str:
    """Normalize a player name for matching."""
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    text = text.replace(".", "").replace("'", "").replace("-", " ")
    text = _WHITESPACE_RE.sub(" ", text)
    return text


def _normalize_name_no_suffix(name: str) -> str:
    """Normalize a player name and strip common suffixes."""
    normalized = _normalize_name(name)
    return _NAME_SUFFIX_RE.sub("", normalized).strip()


def _normalize_team(team: str) -> str:
    """Normalize a team abbreviation."""
    return team.strip().upper()


def build_player_lookup(
    player_summary_index: dict[str, dict[str, Any]],
) -> tuple[dict[tuple[str, str], str], dict[str, list[str]]]:
    """Build lookup indices from the FF player summary index.

    Returns:
        (name_team_index, name_only_index)
        - name_team_index: (normalized_name, team) -> entity_key
        - name_only_index: normalized_name -> [entity_keys]
    """
    name_team_index: dict[tuple[str, str], str] = {}
    name_only_index: dict[str, list[str]] = {}

    for entity_key, info in player_summary_index.items():
        raw_name = str(info.get("name", ""))
        raw_team = str(info.get("team", ""))

        norm_name = _normalize_name(raw_name)
        norm_team = _normalize_team(raw_team)

        if norm_name:
            name_team_index[(norm_name, norm_team)] = entity_key
            name_only_index.setdefault(norm_name, []).append(entity_key)

            no_suffix = _normalize_name_no_suffix(raw_name)
            if no_suffix != norm_name:
                name_team_index.setdefault((no_suffix, norm_team), entity_key)
                name_only_index.setdefault(no_suffix, []).append(entity_key)

    return name_team_index, name_only_index


def match_player(
    player: RosterPlayer,
    name_team_index: dict[tuple[str, str], str],
    name_only_index: dict[str, list[str]],
) -> MatchedPlayer:
    """Match a single Fantrax player to a FF entity key."""
    norm_name = _normalize_name(player.name)
    norm_team = _normalize_team(player.team)

    # Try exact name + team match
    entity_key = name_team_index.get((norm_name, norm_team))
    if entity_key:
        return MatchedPlayer(
            fantrax_id=player.fantrax_id,
            name=player.name,
            position=player.position,
            team=player.team,
            player_entity_key=entity_key,
            match_method="name_team",
        )

    # Try name without suffix + team
    no_suffix = _normalize_name_no_suffix(player.name)
    if no_suffix != norm_name:
        entity_key = name_team_index.get((no_suffix, norm_team))
        if entity_key:
            return MatchedPlayer(
                fantrax_id=player.fantrax_id,
                name=player.name,
                position=player.position,
                team=player.team,
                player_entity_key=entity_key,
                match_method="name_no_suffix_team",
            )

    # Try name-only match (only if unique)
    candidates = name_only_index.get(norm_name, [])
    if len(candidates) == 1:
        return MatchedPlayer(
            fantrax_id=player.fantrax_id,
            name=player.name,
            position=player.position,
            team=player.team,
            player_entity_key=candidates[0],
            match_method="name_only",
        )

    if no_suffix != norm_name:
        candidates = name_only_index.get(no_suffix, [])
        if len(candidates) == 1:
            return MatchedPlayer(
                fantrax_id=player.fantrax_id,
                name=player.name,
                position=player.position,
                team=player.team,
                player_entity_key=candidates[0],
                match_method="name_no_suffix_only",
            )

    return MatchedPlayer(
        fantrax_id=player.fantrax_id,
        name=player.name,
        position=player.position,
        team=player.team,
        player_entity_key=None,
        match_method="none",
    )


def match_roster(
    team_id: str,
    team_name: str,
    players: list[RosterPlayer],
    name_team_index: dict[tuple[str, str], str],
    name_only_index: dict[str, list[str]],
) -> MatchedRoster:
    """Match all players on a roster to FF entity keys."""
    matched_players = [
        match_player(p, name_team_index, name_only_index) for p in players
    ]
    matched_count = sum(1 for p in matched_players if p.player_entity_key)
    return MatchedRoster(
        team_id=team_id,
        team_name=team_name,
        players=matched_players,
        matched_count=matched_count,
        total_count=len(matched_players),
    )


def map_scoring_categories(
    fantrax_categories: list[str],
) -> dict[str, bool]:
    """Map Fantrax scoring category names to FF roto category settings."""
    result: dict[str, bool] = {key: False for key in _ALL_ROTO_KEYS}

    for cat in fantrax_categories:
        cat_upper = cat.strip()
        ff_key = _FANTRAX_ROTO_HIT_MAP.get(cat_upper) or _FANTRAX_ROTO_PIT_MAP.get(
            cat_upper
        )
        if ff_key:
            result[ff_key] = True

    return result


def map_roster_slots(fantrax_positions: list[str]) -> dict[str, int]:
    """Map Fantrax roster positions to FF calculator slot counts."""
    slot_counts: dict[str, int] = {
        "hit_c": 0,
        "hit_1b": 0,
        "hit_2b": 0,
        "hit_3b": 0,
        "hit_ss": 0,
        "hit_ci": 0,
        "hit_mi": 0,
        "hit_of": 0,
        "hit_ut": 0,
        "pit_p": 0,
        "pit_sp": 0,
        "pit_rp": 0,
    }

    for pos in fantrax_positions:
        ff_key = _FANTRAX_SLOT_MAP.get(pos.strip().upper())
        if ff_key:
            slot_counts[ff_key] += 1

    return slot_counts


def build_suggested_settings(league: LeagueInfo) -> LeagueSuggestedSettings:
    """Build calculator settings from Fantrax league configuration."""
    return LeagueSuggestedSettings(
        teams=league.team_count or 12,
        scoring_mode=league.scoring_type or "roto",
        roto_categories=map_scoring_categories(league.scoring_categories),
        roster_slots=map_roster_slots(league.roster_positions),
    )
