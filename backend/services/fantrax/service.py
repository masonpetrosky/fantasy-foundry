"""Fantrax league data fetching service."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

import httpx

from backend.services.fantrax.mapping import (
    extract_reserve_slot_counts,
    map_points_scoring,
)
from backend.services.fantrax.models import (
    LeagueInfo,
    RosterPlayer,
    TeamRoster,
)

logger = logging.getLogger(__name__)

FANTRAX_BASE_URL = "https://www.fantrax.com/fxea/general"
FANTRAX_ROSTERS_URL = f"{FANTRAX_BASE_URL}/getTeamRosters"
FANTRAX_STANDINGS_URL = f"{FANTRAX_BASE_URL}/getStandings"

# In-memory cache: league_id -> (timestamp, LeagueInfo)
_league_cache: dict[str, tuple[float, LeagueInfo]] = {}
_league_cache_lock = asyncio.Lock()
_CACHE_TTL_SECONDS = 900  # 15 minutes
_MAX_CACHE_ENTRIES = 50
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_POINTS_RULE_NAME_KEYS = {
    "name",
    "abbr",
    "abbreviation",
    "label",
    "shortname",
    "displayname",
    "stat",
    "category",
}
_POINTS_RULE_VALUE_KEYS = {
    "points",
    "value",
    "pointvalue",
    "pointsvalue",
    "score",
    "amount",
}
_POINTS_RULE_SCOPE_KEYS = {
    "group",
    "section",
    "type",
    "statgroup",
    "scoringgroup",
    "categorytype",
    "playertype",
}
_POSITION_COUNT_KEYS = {"count", "qty", "quantity", "slots", "slotcount", "number"}
_KEEPER_LIMIT_KEYS = {
    "keeperlimit",
    "maxkeepers",
    "numkeepers",
    "keepersperteam",
    "maxkeepersperteam",
}
_WEEKLY_STARTS_CAP_KEYS = {
    "weeklystartslimit",
    "weeklygamesstartedlimit",
    "gamesstartedlimit",
    "maxweeklygamesstarted",
    "maxgamesstartedperweek",
    "weeklypitchingstarts",
}
_SAME_DAY_OVERFLOW_KEYS = {
    "allowexceedstartlimitonlastday",
    "allowexceedstartsonlastday",
    "allowlastdaystartoverage",
    "applymaxgamesstartednextday",
    "enforcestartlimitnextday",
}
_WEEKLY_ACQUISITION_CAP_KEYS = {
    "weeklyacquisitionlimit",
    "weeklytransactionslimit",
    "weeklymoveslimit",
    "weeklyaddslimit",
    "maxweeklytransactions",
    "maxmovesperweek",
}


def _prune_cache() -> None:
    """Remove expired or excess cache entries (caller must hold _league_cache_lock)."""
    now = time.monotonic()
    expired = [k for k, (ts, _) in _league_cache.items() if now - ts > _CACHE_TTL_SECONDS]
    for k in expired:
        del _league_cache[k]
    if len(_league_cache) > _MAX_CACHE_ENTRIES:
        by_age = sorted(_league_cache.items(), key=lambda x: x[1][0])
        for k, _ in by_age[: len(_league_cache) - _MAX_CACHE_ENTRIES]:
            del _league_cache[k]


def _get_cached(league_id: str) -> LeagueInfo | None:
    """Read from cache (caller must hold _league_cache_lock)."""
    entry = _league_cache.get(league_id)
    if entry is None:
        return None
    ts, info = entry
    if time.monotonic() - ts > _CACHE_TTL_SECONDS:
        del _league_cache[league_id]
        return None
    return info


def _set_cached(league_id: str, info: LeagueInfo) -> None:
    """Write to cache (caller must hold _league_cache_lock)."""
    _prune_cache()
    _league_cache[league_id] = (time.monotonic(), info)


def _normalize_key(value: object) -> str:
    return _NON_ALNUM_RE.sub("", str(value or "").strip().lower())


def _coerce_number(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed


def _coerce_int(value: object) -> int | None:
    parsed = _coerce_number(value)
    if parsed is None or int(parsed) != parsed:
        return None
    return int(parsed)


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _scope_from_text(value: object) -> str | None:
    token = _normalize_key(value)
    if not token:
        return None
    if any(part in token for part in ("hit", "bat", "offens", "hitter")):
        return "hit"
    if any(part in token for part in ("pit", "pitch", "relief", "starter")):
        return "pit"
    return None


def _iter_nested_dicts(node: object):
    if isinstance(node, dict):
        yield node
        for child in node.values():
            yield from _iter_nested_dicts(child)
        return
    if isinstance(node, list):
        for child in node:
            yield from _iter_nested_dicts(child)


def _extract_optional_int_setting(
    data: dict[str, Any],
    candidate_keys: set[str],
    *,
    minimum: int,
) -> int | None:
    for node in _iter_nested_dicts(data):
        for raw_key, raw_value in node.items():
            if _normalize_key(raw_key) not in candidate_keys:
                continue
            parsed = _coerce_int(raw_value)
            if parsed is not None and parsed >= minimum:
                return parsed
    return None


def _extract_optional_bool_setting(
    data: dict[str, Any],
    candidate_keys: set[str],
) -> bool | None:
    for node in _iter_nested_dicts(data):
        for raw_key, raw_value in node.items():
            if _normalize_key(raw_key) not in candidate_keys:
                continue
            parsed = _coerce_bool(raw_value)
            if parsed is not None:
                return parsed
    return None


def _expand_roster_positions(raw_positions: object) -> list[str]:
    positions: list[str] = []
    if not isinstance(raw_positions, list):
        return positions

    for raw_pos in raw_positions:
        if isinstance(raw_pos, dict):
            code = str(
                raw_pos.get("code")
                or raw_pos.get("abbr")
                or raw_pos.get("abbreviation")
                or raw_pos.get("name")
                or ""
            ).strip()
            if not code:
                continue
            count = 1
            for raw_key, raw_value in raw_pos.items():
                if _normalize_key(raw_key) not in _POSITION_COUNT_KEYS:
                    continue
                parsed = _coerce_int(raw_value)
                if parsed is not None and parsed > 0:
                    count = parsed
                    break
            positions.extend([code] * count)
            continue
        if isinstance(raw_pos, str):
            positions.append(raw_pos)
    return positions


def _extract_points_rule_entries(data: dict[str, Any]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    seen: set[tuple[str, float, str | None]] = set()

    def walk(node: object, scope_hint: str | None = None) -> None:
        if isinstance(node, dict):
            resolved_scope = scope_hint
            for raw_key, raw_value in node.items():
                if _normalize_key(raw_key) in _POINTS_RULE_SCOPE_KEYS:
                    resolved_scope = _scope_from_text(raw_value) or resolved_scope

            name: str | None = None
            value: float | None = None
            for raw_key, raw_value in node.items():
                normalized_key = _normalize_key(raw_key)
                if normalized_key in _POINTS_RULE_NAME_KEYS and raw_value not in (None, ""):
                    name = str(raw_value)
                elif normalized_key in _POINTS_RULE_VALUE_KEYS:
                    parsed = _coerce_number(raw_value)
                    if parsed is not None:
                        value = parsed

            if name is not None and value is not None:
                dedupe_key = (name.strip(), float(value), resolved_scope)
                if dedupe_key not in seen:
                    seen.add(dedupe_key)
                    entries.append(
                        {
                            "name": name.strip(),
                            "value": float(value),
                            "scope": resolved_scope,
                        }
                    )

            for raw_key, child in node.items():
                child_scope = _scope_from_text(raw_key) or resolved_scope
                walk(child, child_scope)
            return

        if isinstance(node, list):
            for child in node:
                walk(child, scope_hint)

    walk(data)
    return entries


def _parse_rosters_response(data: dict[str, Any], league_id: str) -> list[TeamRoster]:
    """Parse the Fantrax getTeamRosters response."""
    teams: list[TeamRoster] = []
    rosters = data.get("rosters", {})
    if isinstance(rosters, dict):
        for team_id, team_data in rosters.items():
            team_name = str(team_data.get("teamName", team_id))
            players: list[RosterPlayer] = []
            player_list = team_data.get("rosterItems", [])
            if isinstance(player_list, list):
                for item in player_list:
                    if not isinstance(item, dict):
                        continue
                    players.append(
                        RosterPlayer(
                            fantrax_id=str(item.get("id", "")),
                            name=str(item.get("name", "")),
                            position=str(item.get("pos", item.get("position", ""))),
                            team=str(item.get("team", item.get("teamAbbrev", ""))),
                        )
                    )
            teams.append(
                TeamRoster(team_id=str(team_id), team_name=team_name, players=players)
            )
    return teams


def _parse_standings_response(
    data: dict[str, Any],
) -> tuple[str, str, list[str], list[str]]:
    """Parse standings response for league name, scoring type, categories, and positions.

    Returns (league_name, scoring_type, categories, positions).
    """
    league_name = str(data.get("leagueName", data.get("league", {}).get("name", "Fantrax League")))
    scoring_type = "roto"

    raw_type = str(data.get("scoringType", data.get("league", {}).get("scoringType", ""))).lower()
    if "point" in raw_type or "pts" in raw_type:
        scoring_type = "points"
    elif "roto" in raw_type or "rotisserie" in raw_type:
        scoring_type = "roto"

    categories: list[str] = []
    raw_cats = data.get("scoringCategories", data.get("categories", []))
    if isinstance(raw_cats, list):
        for cat in raw_cats:
            if isinstance(cat, dict):
                categories.append(str(cat.get("name", cat.get("abbr", ""))))
            elif isinstance(cat, str):
                categories.append(cat)

    raw_positions = data.get("rosterPositions", data.get("positions", []))
    positions = _expand_roster_positions(raw_positions)

    return league_name, scoring_type, categories, positions


async def fetch_league_info(league_id: str, *, request_id: str | None = None) -> LeagueInfo:
    """Fetch league info from Fantrax public API.

    Returns cached data if available and fresh.
    """
    async with _league_cache_lock:
        cached = _get_cached(league_id)
    if cached is not None:
        return cached

    league_name = "Fantrax League"
    scoring_type = "roto"
    categories: list[str] = []
    positions: list[str] = []
    teams: list[TeamRoster] = []
    points_scoring: dict[str, float] = {}
    bench: int | None = None
    minors: int | None = None
    ir: int | None = None
    keeper_limit: int | None = None
    weekly_starts_cap: int | None = None
    allow_same_day_starts_overflow = False
    weekly_acquisition_cap: int | None = None
    import_warnings: list[str] = []

    extra_headers: dict[str, str] = {}
    if request_id:
        extra_headers["X-Request-Id"] = request_id

    async with httpx.AsyncClient(timeout=15, headers=extra_headers) as client:
        # Fetch rosters
        try:
            roster_resp = await client.get(
                FANTRAX_ROSTERS_URL, params={"leagueId": league_id}
            )
            roster_resp.raise_for_status()
            roster_data = roster_resp.json()
            teams = _parse_rosters_response(roster_data, league_id)
            # Try to get league name from roster response
            if "leagueName" in roster_data:
                league_name = str(roster_data["leagueName"])
        except httpx.HTTPStatusError:
            logger.warning(
                "Fantrax roster API error for league %s: %s",
                league_id,
                roster_resp.status_code if "roster_resp" in dir() else "unknown",
            )
            raise
        except httpx.RequestError as exc:
            logger.warning("Fantrax roster API request error for league %s: %s", league_id, exc)
            raise

        # Fetch standings for league metadata
        try:
            standings_resp = await client.get(
                FANTRAX_STANDINGS_URL, params={"leagueId": league_id}
            )
            standings_resp.raise_for_status()
            standings_data = standings_resp.json()
            league_name, scoring_type, categories, positions = _parse_standings_response(
                standings_data
            )
            bench, minors, ir = extract_reserve_slot_counts(positions)
            keeper_limit = _extract_optional_int_setting(
                standings_data,
                _KEEPER_LIMIT_KEYS,
                minimum=1,
            )
            weekly_starts_cap = _extract_optional_int_setting(
                standings_data,
                _WEEKLY_STARTS_CAP_KEYS,
                minimum=1,
            )
            same_day_overflow = _extract_optional_bool_setting(
                standings_data,
                _SAME_DAY_OVERFLOW_KEYS,
            )
            allow_same_day_starts_overflow = bool(same_day_overflow)
            weekly_acquisition_cap = _extract_optional_int_setting(
                standings_data,
                _WEEKLY_ACQUISITION_CAP_KEYS,
                minimum=0,
            )
            if scoring_type == "points":
                points_scoring, rule_warnings = map_points_scoring(
                    _extract_points_rule_entries(standings_data)
                )
                import_warnings.extend(rule_warnings)
                if not points_scoring:
                    import_warnings.append(
                        "Fantrax did not expose usable points scoring weights, so points rules may need manual review."
                    )
                if weekly_starts_cap is None:
                    import_warnings.append(
                        "Fantrax did not expose a weekly pitcher-start cap, or the league may not use one."
                    )
                if weekly_acquisition_cap is None:
                    import_warnings.append(
                        "Fantrax did not expose a weekly acquisition cap, or the league may not use one."
                    )
                if weekly_starts_cap is not None and same_day_overflow is None:
                    import_warnings.append(
                        "Fantrax did not expose the final-day start-overflow rule, so review that weekly setting manually."
                    )
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.info(
                "Fantrax standings API unavailable for league %s (non-fatal): %s",
                league_id,
                exc,
            )

    info = LeagueInfo(
        league_id=league_id,
        league_name=league_name,
        teams=teams,
        team_count=len(teams),
        scoring_type=scoring_type,
        scoring_categories=categories,
        roster_positions=positions,
        points_scoring=points_scoring,
        bench=bench,
        minors=minors,
        ir=ir,
        keeper_limit=keeper_limit,
        points_valuation_mode=(
            "weekly_h2h"
            if scoring_type == "points"
            and (weekly_starts_cap is not None or weekly_acquisition_cap is not None)
            else "season_total"
        ),
        weekly_starts_cap=weekly_starts_cap,
        allow_same_day_starts_overflow=allow_same_day_starts_overflow,
        weekly_acquisition_cap=weekly_acquisition_cap,
        import_warnings=list(dict.fromkeys(import_warnings)),
    )
    async with _league_cache_lock:
        _set_cached(league_id, info)
    return info
