"""Projection data preprocessing helpers shared by startup and refresh paths."""

from __future__ import annotations

import re
from typing import Callable

import pandas as pd


def pick_first_existing_col(df: pd.DataFrame, candidates: list[str] | tuple[str, ...]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def find_projection_date_col(df: pd.DataFrame, *, projection_date_cols: list[str]) -> str | None:
    return pick_first_existing_col(df, projection_date_cols)


def parse_projection_dates(values: pd.Series) -> pd.Series:
    """Parse mixed-format date strings safely."""
    text = values.astype("string").str.strip()
    try:
        parsed = pd.to_datetime(text, errors="coerce", format="mixed")
    except TypeError:
        parsed = pd.to_datetime(text, errors="coerce")

    missing = parsed.isna() & text.notna() & (text != "")
    if missing.any():
        reparsed = text[missing].map(lambda value: pd.to_datetime(value, errors="coerce"))
        parsed.loc[missing] = reparsed
    return parsed


def coerce_iso_date_text(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None

    token = text[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", token):
        return token

    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return None
    try:
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        return None


def normalize_player_key(value: object, *, player_key_pattern: re.Pattern[str]) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown-player"
    key = player_key_pattern.sub("-", text).strip("-")
    return key or "unknown-player"


def normalize_team_key(value: object) -> str:
    return str(value or "").strip().upper()


def normalize_year_key(value: object) -> str:
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value).strip()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ""
        try:
            parsed = float(text)
        except ValueError:
            return text
        return str(int(parsed)) if parsed.is_integer() else text
    return str(value or "").strip()


def with_player_identity_keys(
    bat_records: list[dict],
    pit_records: list[dict],
    *,
    player_key_col: str,
    player_entity_key_col: str,
    normalize_player_key_fn: Callable[[object], str],
    normalize_team_key_fn: Callable[[object], str],
    normalize_year_key_fn: Callable[[object], str],
) -> tuple[list[dict], list[dict]]:
    combined = list(bat_records) + list(pit_records)
    if not combined:
        return bat_records, pit_records

    teams_by_player_year: dict[tuple[str, str], set[str]] = {}
    for record in combined:
        player_key = str(record.get(player_key_col) or "").strip() or normalize_player_key_fn(record.get("Player"))
        year_key = normalize_year_key_fn(record.get("Year"))
        team_key = normalize_team_key_fn(record.get("Team") or record.get("MLBTeam"))
        if not team_key:
            continue
        teams_by_player_year.setdefault((player_key, year_key), set()).add(team_key)

    ambiguous_player_keys = {
        player_key
        for (player_key, _), teams in teams_by_player_year.items()
        if len(teams) > 1
    }

    def apply_identity_keys(records: list[dict]) -> list[dict]:
        out: list[dict] = []
        for record in records:
            row = dict(record)
            player_key = str(row.get(player_key_col) or "").strip() or normalize_player_key_fn(row.get("Player"))
            row[player_key_col] = player_key

            entity_key = str(row.get(player_entity_key_col) or "").strip()
            if not entity_key:
                if player_key in ambiguous_player_keys:
                    team_key = normalize_team_key_fn(row.get("Team") or row.get("MLBTeam")).lower() or "unknown"
                    entity_key = f"{player_key}__{team_key}"
                else:
                    entity_key = player_key
            row[player_entity_key_col] = entity_key
            out.append(row)
        return out

    return apply_identity_keys(bat_records), apply_identity_keys(pit_records)


def average_recent_projection_rows(
    records: list[dict],
    *,
    is_hitter: bool,
    team_col_candidates: tuple[str, ...],
    projection_date_cols: list[str],
    derived_hit_rate_cols: set[str],
    derived_pit_rate_cols: set[str],
) -> list[dict]:
    """Collapse duplicate projection rows by keeping only the most recent date.

    Rows are grouped by (Player, Year) and disambiguated by team only when a
    given name/year has multiple non-empty teams. This avoids merging distinct
    players who share the same name while preserving normal update averaging.
    """
    if not records:
        return records

    df = pd.DataFrame.from_records(records)
    group_cols_base = ["Player", "Year"]
    if any(col not in df.columns for col in group_cols_base):
        return records

    df = df.copy()
    group_cols = list(group_cols_base)
    internal_group_cols: list[str] = []

    team_col = pick_first_existing_col(df, team_col_candidates)
    if team_col:
        team_values = df[team_col].astype("string").fillna("").str.strip()
        team_nonempty = team_values.where(team_values != "", pd.NA)
        team_counts = team_nonempty.groupby([df[col] for col in group_cols_base], dropna=False).transform("nunique")
        if team_counts.gt(1).any():
            # Split only ambiguous name/year groups so same-name different-team
            # players are not merged into one averaged row.
            df["_entity_team"] = team_values.where(team_counts > 1, "")
            group_cols.append("_entity_team")
            internal_group_cols.append("_entity_team")

    df["_projection_order"] = range(len(df))

    date_col = find_projection_date_col(df, projection_date_cols=projection_date_cols)
    if date_col:
        df["_projection_date"] = parse_projection_dates(df[date_col])
        df["_sort_key"] = df["_projection_date"].fillna(pd.Timestamp.min)
    else:
        df["_projection_date"] = pd.NaT
        df["_sort_key"] = df["_projection_order"]

    excluded = {"Age"} | (derived_hit_rate_cols if is_hitter else derived_pit_rate_cols)
    stat_cols = [
        col
        for col in df.columns
        if col not in group_cols
        and col not in excluded
        and pd.api.types.is_numeric_dtype(df[col])
    ]

    df = df.sort_values(["_sort_key", "_projection_order"], ascending=False)
    max_dates = df.groupby(group_cols, sort=False)["_sort_key"].transform("max")
    recent = df[df["_sort_key"] == max_dates].copy()
    recent["OldestProjectionDate"] = recent["_projection_date"]

    meta_cols = [
        col
        for col in recent.columns
        if col not in stat_cols
        and col not in group_cols
        and col
        not in {
            "_projection_order",
            "_projection_date",
            "_sort_key",
            "OldestProjectionDate",
        }
    ]

    agg = {col: "mean" for col in stat_cols}
    agg["OldestProjectionDate"] = "min"
    for col in meta_cols:
        agg[col] = "first"

    out = (
        recent.sort_values(["_sort_key", "_projection_order"], ascending=False)
        .groupby(group_cols, as_index=False, sort=False)
        .agg(agg)
    )
    if internal_group_cols:
        out = out.drop(columns=internal_group_cols, errors="ignore")

    front = ["Player", "Year", "OldestProjectionDate"]
    out = out[[col for col in front if col in out.columns] + [col for col in out.columns if col not in front]]

    if is_hitter:
        if "H" in out.columns and "AB" in out.columns:
            h = out["H"].astype(float)
            ab = out["AB"].astype(float)
            out["AVG"] = (h / ab).where(ab > 0, 0.0)

        needed = {"H", "2B", "3B", "HR", "BB", "HBP", "AB", "SF"}
        if needed.issubset(out.columns):
            h = out["H"].astype(float)
            b2 = out["2B"].astype(float)
            b3 = out["3B"].astype(float)
            hr = out["HR"].astype(float)
            bb = out["BB"].astype(float)
            hbp = out["HBP"].astype(float)
            ab = out["AB"].astype(float)
            sf = out["SF"].astype(float)

            tb = h + b2 + 2.0 * b3 + 3.0 * hr
            obp_den = ab + bb + hbp + sf
            obp = ((h + bb + hbp) / obp_den).where(obp_den > 0, 0.0)
            slg = (tb / ab).where(ab > 0, 0.0)
            out["TB"] = tb
            out["OBP"] = obp
            out["SLG"] = slg
            out["OPS"] = obp + slg
    else:
        if "SVH" not in out.columns:
            if "SV" in out.columns and "HLD" in out.columns:
                out["SVH"] = out["SV"].astype(float).fillna(0.0) + out["HLD"].astype(float).fillna(0.0)
            elif "SV" in out.columns:
                out["SVH"] = out["SV"].astype(float).fillna(0.0)
        if "QS" not in out.columns:
            if "QA3" in out.columns:
                out["QS"] = out["QA3"].astype(float).fillna(0.0)
            else:
                out["QS"] = 0.0
        if "QA3" not in out.columns:
            if "QS" in out.columns:
                out["QA3"] = out["QS"].astype(float).fillna(0.0)
            else:
                out["QA3"] = 0.0
        if "ER" in out.columns and "IP" in out.columns:
            er = out["ER"].astype(float)
            ip = out["IP"].astype(float)
            out["ERA"] = ((9.0 * er) / ip).where(ip > 0)
        if "H" in out.columns and "BB" in out.columns and "IP" in out.columns:
            h = out["H"].astype(float)
            bb = out["BB"].astype(float)
            ip = out["IP"].astype(float)
            out["WHIP"] = ((h + bb) / ip).where(ip > 0)

    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].dt.strftime("%Y-%m-%d")

    records_out = out.to_dict(orient="records")
    for row in records_out:
        for key, value in row.items():
            try:
                if pd.isna(value):
                    row[key] = None
            except TypeError:
                continue

    return records_out
