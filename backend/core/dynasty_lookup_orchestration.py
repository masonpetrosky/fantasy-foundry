"""Dynasty lookup and projection year-filter orchestration helpers."""

from __future__ import annotations

import logging
import re
from typing import Any, Callable

import pandas as pd

logger = logging.getLogger(__name__)

DynastyLookup = tuple[dict[str, dict], dict[str, dict], set[str], list[str]]
YEAR_RANGE_TOKEN_RE = re.compile(r"^(\d{4})\s*-\s*(\d{4})$")


def default_dynasty_lookup(
    *,
    inspect_precomputed_default_dynasty_lookup: Callable[[], Any],
    require_precomputed_dynasty_lookup: bool,
    required_lookup_error_factory: Callable[[str], Exception],
    default_calculation_cache_params: Callable[[], dict[str, Any]],
    calculate_common_dynasty_frame_cached: Callable[..., Any],
    roto_category_settings_from_dict: Callable[[dict[str, Any]], dict[str, Any]],
    value_col_sort_key: Callable[[str], tuple[int, int | str]],
    normalize_team_key: Callable[[object], str],
    normalize_player_key: Callable[[object], str],
    bat_data: list[dict],
    pit_data: list[dict],
    player_key_col: str,
    player_entity_key_col: str,
) -> DynastyLookup:
    inspection = inspect_precomputed_default_dynasty_lookup()
    if inspection.status == "ready" and inspection.lookup is not None:
        return inspection.lookup

    if require_precomputed_dynasty_lookup and inspection.status != "disabled":
        found_version = inspection.found_version or "missing"
        raise required_lookup_error_factory(
            "Precomputed dynasty lookup cache is not ready "
            f"(status={inspection.status}, expected={inspection.expected_version}, found={found_version}). "
            "Run `python preprocess.py` and deploy the regenerated `data/dynasty_lookup.json`."
        )

    try:
        params = default_calculation_cache_params()
        out = calculate_common_dynasty_frame_cached(
            teams=int(params["teams"]),
            sims=int(params["sims"]),
            horizon=int(params["horizon"]),
            discount=float(params["discount"]),
            hit_c=int(params["hit_c"]),
            hit_1b=int(params["hit_1b"]),
            hit_2b=int(params["hit_2b"]),
            hit_3b=int(params["hit_3b"]),
            hit_ss=int(params["hit_ss"]),
            hit_ci=int(params["hit_ci"]),
            hit_mi=int(params["hit_mi"]),
            hit_of=int(params["hit_of"]),
            hit_ut=int(params["hit_ut"]),
            pit_p=int(params["pit_p"]),
            pit_sp=int(params["pit_sp"]),
            pit_rp=int(params["pit_rp"]),
            bench=int(params["bench"]),
            minors=int(params["minors"]),
            ir=int(params["ir"]),
            ip_min=float(params["ip_min"]),
            ip_max=params["ip_max"],
            two_way=str(params["two_way"]),
            start_year=int(params["start_year"]),
            sgp_denominator_mode=str(params.get("sgp_denominator_mode", "classic")),
            sgp_winsor_low_pct=float(params.get("sgp_winsor_low_pct", 0.10)),
            sgp_winsor_high_pct=float(params.get("sgp_winsor_high_pct", 0.90)),
            sgp_epsilon_counting=float(params.get("sgp_epsilon_counting", 0.15)),
            sgp_epsilon_ratio=float(params.get("sgp_epsilon_ratio", 0.0015)),
            enable_playing_time_reliability=bool(params.get("enable_playing_time_reliability", False)),
            enable_age_risk_adjustment=bool(params.get("enable_age_risk_adjustment", False)),
            enable_replacement_blend=bool(params.get("enable_replacement_blend", False)),
            replacement_blend_alpha=float(params.get("replacement_blend_alpha", 0.70)),
            **roto_category_settings_from_dict(params),
        ).copy(deep=True)

        year_cols = sorted(
            [col for col in out.columns if isinstance(col, str) and col.startswith("Value_")],
            key=value_col_sort_key,
        )
        keep_cols = [col for col in ["Player", "Team", "DynastyValue"] + year_cols if col in out.columns]
        df = out[keep_cols].copy()

        for col in df.select_dtypes(include="float").columns:
            df[col] = df[col].round(2)

        lookup_candidates_by_name: dict[str, list[dict[str, object]]] = {}
        for row in df.to_dict(orient="records"):
            player = str(row.get("Player", "")).strip()
            if not player:
                continue

            cleaned: dict = {}
            for key, value in row.items():
                if key in {"Player", "Team"}:
                    continue
                cleaned[key] = None if pd.isna(value) else value
            team_key = normalize_team_key(row.get("Team")).lower()
            lookup_candidates_by_name.setdefault(player, []).append(
                {
                    "team_key": team_key,
                    "values": cleaned,
                }
            )

        combined_records = list(bat_data) + list(pit_data)
        entities_by_player_key: dict[str, set[str]] = {}
        for record in combined_records:
            player_name = str(record.get("Player", "")).strip()
            player_key = str(record.get(player_key_col) or "").strip() or normalize_player_key(player_name)
            entity_key = str(record.get(player_entity_key_col) or "").strip() or player_key
            if player_key:
                entities_by_player_key.setdefault(player_key, set()).add(entity_key)

        ambiguous_player_keys = {
            player_key
            for player_key, entity_keys in entities_by_player_key.items()
            if len(entity_keys) > 1
        }

        def candidate_values_for_record(
            record: dict,
            candidates: list[dict[str, object]],
            *,
            require_team_match: bool,
        ) -> dict | None:
            if not candidates:
                return None

            record_team_key = normalize_team_key(record.get("Team") or record.get("MLBTeam")).lower()
            if require_team_match:
                if record_team_key:
                    team_matches = [candidate for candidate in candidates if str(candidate.get("team_key") or "") == record_team_key]
                    if len(team_matches) == 1:
                        return team_matches[0].get("values") if isinstance(team_matches[0].get("values"), dict) else None
                    return None
                return (
                    candidates[0].get("values")
                    if len(candidates) == 1 and isinstance(candidates[0].get("values"), dict)
                    else None
                )

            if record_team_key:
                team_matches = [candidate for candidate in candidates if str(candidate.get("team_key") or "") == record_team_key]
                if len(team_matches) == 1:
                    return team_matches[0].get("values") if isinstance(team_matches[0].get("values"), dict) else None
            return candidates[0].get("values") if len(candidates) == 1 and isinstance(candidates[0].get("values"), dict) else None

        lookup_by_entity: dict[str, dict] = {}
        lookup_by_player_key: dict[str, dict] = {}
        for record in combined_records:
            player_name = str(record.get("Player", "")).strip()
            if not player_name:
                continue

            player_key = str(record.get(player_key_col) or "").strip() or normalize_player_key(player_name)
            entity_key = str(record.get(player_entity_key_col) or "").strip() or player_key
            player_values = candidate_values_for_record(
                record,
                lookup_candidates_by_name.get(player_name, []),
                require_team_match=player_key in ambiguous_player_keys,
            )
            if player_values is None:
                continue

            if player_key not in ambiguous_player_keys:
                lookup_by_player_key.setdefault(player_key, player_values)
            lookup_by_entity.setdefault(entity_key, player_values)

        return lookup_by_entity, lookup_by_player_key, ambiguous_player_keys, year_cols
    except Exception:
        logger.exception("Failed to build default dynasty lookup")
        return {}, {}, set(), []


def parse_dynasty_years(
    raw: str | None,
    *,
    valid_years: list[int] | None = None,
    year_range_token_re: re.Pattern[str] = YEAR_RANGE_TOKEN_RE,
) -> list[int]:
    if not raw:
        return []

    years: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue

        range_match = year_range_token_re.fullmatch(token)
        if range_match:
            start, end = (int(range_match.group(1)), int(range_match.group(2)))
            low, high = sorted((start, end))
            years.extend(range(low, high + 1))
            continue

        try:
            years.append(int(token))
        except ValueError:
            continue

    parsed = sorted(set(years))
    if valid_years:
        valid = set(valid_years)
        parsed = [year for year in parsed if year in valid]
    return parsed


def resolve_projection_year_filter(
    year: int | None,
    years: str | None,
    *,
    valid_years: list[int] | None = None,
    parse_dynasty_years_fn: Callable[[str | None], list[int]] | None = None,
) -> set[int] | None:
    years_specified = bool(years and years.strip())
    parsed_years: set[int] | None = None
    if years_specified:
        if parse_dynasty_years_fn is None:
            parsed_years = set(parse_dynasty_years(years, valid_years=valid_years))
        else:
            parsed_years = set(parse_dynasty_years_fn(years))

    if year is None and parsed_years is None:
        return None
    if parsed_years is None:
        return {year} if year is not None else set()
    if year is not None:
        parsed_years.intersection_update({year})
    return parsed_years


def attach_dynasty_values(
    rows: list[dict],
    *,
    dynasty_years: list[int] | None = None,
    get_default_dynasty_lookup: Callable[[], DynastyLookup],
    normalize_player_key: Callable[[object], str],
    player_key_col: str,
    player_entity_key_col: str,
) -> list[dict]:
    if not rows:
        return rows

    lookup_by_entity, lookup_by_player_key, ambiguous_player_keys, available_year_cols = get_default_dynasty_lookup()
    if not lookup_by_entity and not lookup_by_player_key:
        return rows

    if dynasty_years:
        requested_year_cols = [f"Value_{year}" for year in dynasty_years]
        year_cols = [col for col in requested_year_cols if col in available_year_cols]
    else:
        year_cols = available_year_cols

    cols = ["DynastyValue"] + year_cols
    enriched_rows: list[dict] = []
    for row in rows:
        enriched = dict(row)
        player_name = str(row.get("Player", "")).strip()
        player_key = str(enriched.get(player_key_col) or "").strip() or normalize_player_key(player_name)
        entity_key = str(enriched.get(player_entity_key_col) or "").strip() or player_key
        enriched[player_key_col] = player_key
        enriched[player_entity_key_col] = entity_key

        player_values = lookup_by_entity.get(entity_key)
        if player_values is None and player_key not in ambiguous_player_keys:
            player_values = lookup_by_player_key.get(player_key)

        if player_values is None:
            match_status = "no_unique_match" if player_key in ambiguous_player_keys else "missing"
            player_values = {}
        else:
            match_status = "matched"

        for col in cols:
            enriched[col] = player_values.get(col)
        enriched["DynastyMatchStatus"] = match_status
        enriched_rows.append(enriched)

    return enriched_rows


def player_identity_by_name(
    *,
    bat_data: list[dict],
    pit_data: list[dict],
    player_key_col: str,
    player_entity_key_col: str,
    normalize_player_key: Callable[[object], str],
) -> dict[str, tuple[str, str | None]]:
    identities: dict[str, dict[str, set[str]]] = {}
    for record in list(bat_data) + list(pit_data):
        player_name = str(record.get("Player", "")).strip()
        if not player_name:
            continue

        player_key = str(record.get(player_key_col) or "").strip() or normalize_player_key(player_name)
        entity_key = str(record.get(player_entity_key_col) or "").strip() or player_key
        bucket = identities.setdefault(player_name, {"player_keys": set(), "entity_keys": set()})
        bucket["player_keys"].add(player_key)
        bucket["entity_keys"].add(entity_key)

    out: dict[str, tuple[str, str | None]] = {}
    for player_name, bucket in identities.items():
        player_keys = bucket["player_keys"]
        entity_keys = bucket["entity_keys"]
        resolved_player_key = next(iter(player_keys)) if len(player_keys) == 1 else normalize_player_key(player_name)
        resolved_entity_key = next(iter(entity_keys)) if len(entity_keys) == 1 else None
        out[player_name] = (resolved_player_key, resolved_entity_key)
    return out
