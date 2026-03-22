from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException

ProjectionDataset = Literal["all", "bat", "pitch"]


def projection_profile(
    service: Any,
    *,
    player_id: str,
    dataset: ProjectionDataset = "all",
    include_dynasty: bool = True,
    calculator_job_id: str | None = None,
) -> dict[str, Any]:
    normalized_player_id = service._normalize_filter_value(player_id)
    if not normalized_player_id:
        raise HTTPException(status_code=422, detail="player_id is required.")

    series = service.projection_response(
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
    career_totals = service.projection_response(
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
        player_entity_key = str(row.get(service._ctx.player_entity_key_col) or "").strip()
        player_key = str(row.get(service._ctx.player_key_col) or "").strip()
        identity_key = player_entity_key or player_key
        if not identity_key or identity_key in seen_keys:
            continue
        seen_keys.add(identity_key)
        matched_players.append(
            {
                "player_entity_key": player_entity_key or None,
                "player_key": player_key or None,
                "player": str(row.get("Player") or "").strip() or None,
                "team": service._row_team_value(row) or None,
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
    service: Any,
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
    requested_player_keys = service._parse_player_keys_filter(player_keys)
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
    response = service.projection_response(
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
            str(row.get(service._ctx.player_entity_key_col) or row.get(service._ctx.player_key_col) or "").strip()
            for row in response.get("data", [])
            if str(row.get(service._ctx.player_entity_key_col) or row.get(service._ctx.player_key_col) or "").strip()
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
