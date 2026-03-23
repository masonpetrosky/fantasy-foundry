from __future__ import annotations

from typing import Any, Literal

ProjectionDataset = Literal["all", "bat", "pitch"]


def filter_records(
    service: Any,
    records: list[dict],
    player: str | None,
    team: str | None,
    years: set[int] | None,
    pos: str | None,
    player_keys: set[str] | None = None,
) -> list[dict]:
    out = records
    if player:
        q = player.strip().lower()
        out = [r for r in out if q in str(r.get("Player", "")).lower()]
    if team:
        team_normalized = team.strip().lower()
        out = [
            r
            for r in out
            if str(r.get("Team", "")).strip().lower() == team_normalized
            or str(r.get("MLBTeam", "")).strip().lower() == team_normalized
        ]
    if years is not None:
        out = [r for r in out if service._coerce_record_year(r.get("Year")) in years]
    if pos:
        requested_positions = service._position_tokens(pos)
        if requested_positions:
            out = [
                r for r in out if requested_positions.intersection(service._position_tokens(r.get("Pos", "")))
            ]
    if player_keys:
        out = [r for r in out if player_keys.intersection(service._row_player_filter_keys(r))]
    return out


def get_projection_rows(
    service: Any,
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
    cached_rows = service._cached_projection_rows(
        dataset,
        service._normalize_filter_value(player),
        service._normalize_filter_value(team),
        service._normalize_player_keys_filter(player_keys),
        year,
        service._normalize_filter_value(years),
        service._normalize_filter_value(pos),
        include_dynasty,
        service._normalize_filter_value(dynasty_years),
        career_totals,
    )
    with_overlay = service._apply_calculator_overlay_values(
        list(cached_rows),
        include_dynasty=include_dynasty,
        calculator_job_id=calculator_job_id,
    )
    sorted_rows = service._sort_projection_rows(
        with_overlay,
        service._normalize_filter_value(sort_col),
        service._normalize_sort_dir(sort_dir),
    )
    return tuple(sorted_rows)


def get_all_projection_rows(
    service: Any,
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
    cached_rows = service._cached_all_projection_rows(
        service._normalize_filter_value(player),
        service._normalize_filter_value(team),
        service._normalize_player_keys_filter(player_keys),
        year,
        service._normalize_filter_value(years),
        service._normalize_filter_value(pos),
        include_dynasty,
        service._normalize_filter_value(dynasty_years),
        career_totals,
    )
    with_overlay = service._apply_calculator_overlay_values(
        list(cached_rows),
        include_dynasty=include_dynasty,
        calculator_job_id=calculator_job_id,
    )
    sorted_rows = service._sort_projection_rows(
        with_overlay,
        service._normalize_filter_value(sort_col),
        service._normalize_sort_dir(sort_dir),
    )
    return tuple(sorted_rows)


def projection_response(
    service: Any,
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
    service._ctx.refresh_data_if_needed()
    validated_sort_col = service._validate_sort_col(sort_col, dataset=dataset)
    if dataset == "all":
        filtered = get_all_projection_rows(
            service,
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
            sort_col=validated_sort_col,
            sort_dir=sort_dir,
        )
    else:
        filtered = get_projection_rows(
            service,
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
            sort_col=validated_sort_col,
            sort_dir=sort_dir,
        )
    total = len(filtered)
    page = list(filtered[offset : offset + limit])
    return {"total": total, "offset": offset, "limit": limit, "data": page}


def export_projections(
    service: Any,
    dataset: ProjectionDataset,
    file_format: Literal["csv", "xlsx"] = "csv",
    player: str | None = None,
    team: str | None = None,
    player_keys: str | None = None,
    year: int | None = None,
    years: str | None = None,
    pos: str | None = None,
    dynasty_years: str | None = None,
    career_totals: bool = False,
    include_dynasty: bool = True,
    calculator_job_id: str | None = None,
    sort_col: str | None = None,
    sort_dir: Literal["asc", "desc"] = "desc",
    columns: str | None = None,
):
    service._ctx.refresh_data_if_needed()
    validated_sort_col = service._validate_sort_col(sort_col, dataset=dataset)
    if dataset == "all":
        rows = list(
            get_all_projection_rows(
                service,
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
                sort_col=validated_sort_col,
                sort_dir=sort_dir,
            )
        )
    else:
        rows = list(
            get_projection_rows(
                service,
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
                sort_col=validated_sort_col,
                sort_dir=sort_dir,
            )
        )

    requested_export_columns = service._parse_export_columns(columns)
    default_export_columns = service._default_projection_export_columns(
        rows,
        dataset=dataset,
        career_totals=career_totals,
    )
    return service._ctx.tabular_export_response(
        rows,
        filename_base=f"projections-{dataset}",
        file_format=file_format,
        selected_columns=requested_export_columns,
        default_columns=default_export_columns,
        required_columns=["Player"],
        disallowed_columns=[
            service._ctx.player_key_col,
            service._ctx.player_entity_key_col,
            "DynastyMatchStatus",
            "RawDynastyValue",
            "minor_eligible",
        ],
        export_header_label_overrides={"SelectedPoints": "Points"},
    )
