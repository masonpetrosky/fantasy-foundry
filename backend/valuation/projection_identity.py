"""Projection identity and disambiguation helpers."""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd

PROJECTION_DATE_COLS = ["ProjectionDate", "Date", "Updated", "LastUpdated", "Timestamp", "Created", "AsOf"]
PLAYER_KEY_COL = "PlayerKey"
PLAYER_ENTITY_KEY_COL = "PlayerEntityKey"
PLAYER_KEY_PATTERN = re.compile(r"[^a-z0-9]+")


def _find_projection_date_col(df: pd.DataFrame) -> Optional[str]:
    for col in PROJECTION_DATE_COLS:
        if col in df.columns:
            return col
    return None


def _normalize_player_key(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown-player"
    key = PLAYER_KEY_PATTERN.sub("-", text).strip("-")
    return key or "unknown-player"


def _normalize_team_key(value: object) -> str:
    return str(value or "").strip().upper()


def _normalize_year_key(value: object) -> str:
    if value is None or value == "":
        return ""
    try:
        numeric = float(value)  # type: ignore[arg-type]
        if pd.notna(numeric) and numeric.is_integer():
            return str(int(numeric))
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _team_column_for_dataframe(df: pd.DataFrame) -> Optional[str]:
    for col in ("Team", "MLBTeam"):
        if col in df.columns:
            return col
    return None


def _add_player_identity_keys(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    bat_out = bat.copy()
    pit_out = pit.copy()

    def _prepare(df: pd.DataFrame, *, team_col: Optional[str]) -> pd.DataFrame:
        out = df.copy()

        if PLAYER_KEY_COL in out.columns:
            existing_keys = out[PLAYER_KEY_COL].astype("string").fillna("").str.strip()
        else:
            existing_keys = pd.Series("", index=out.index, dtype="string")
        normalized_keys = out.get("Player", pd.Series("", index=out.index)).map(_normalize_player_key)
        out["_player_key"] = existing_keys.where(existing_keys != "", normalized_keys)

        if "Year" in out.columns:
            out["_year_key"] = out["Year"].map(_normalize_year_key)
        else:
            out["_year_key"] = ""

        if team_col and team_col in out.columns:
            out["_team_key"] = out[team_col].map(_normalize_team_key)
        else:
            out["_team_key"] = ""

        return out

    bat_prepared = _prepare(bat_out, team_col=_team_column_for_dataframe(bat_out))
    pit_prepared = _prepare(pit_out, team_col=_team_column_for_dataframe(pit_out))
    combined = pd.concat([bat_prepared, pit_prepared], ignore_index=True, sort=False)

    teams_by_player_year: dict[tuple[str, str], set[str]] = {}
    for _, row in combined.iterrows():
        player_key = str(row.get("_player_key", "")).strip()
        year_key = str(row.get("_year_key", "")).strip()
        team_key = str(row.get("_team_key", "")).strip()
        if not player_key or not team_key:
            continue
        teams_by_player_year.setdefault((player_key, year_key), set()).add(team_key)

    ambiguous_players = {
        player_key
        for (player_key, _), teams in teams_by_player_year.items()
        if len(teams) > 1
    }

    def _finalize(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out[PLAYER_KEY_COL] = out["_player_key"].map(lambda value: str(value).strip() or "unknown-player")

        if PLAYER_ENTITY_KEY_COL in out.columns:
            existing_entities = out[PLAYER_ENTITY_KEY_COL].astype("string").fillna("").str.strip()
        else:
            existing_entities = pd.Series("", index=out.index, dtype="string")

        entity_values: list[str] = []
        for idx, row in out.iterrows():
            existing_entity = str(existing_entities.loc[idx]).strip()
            if existing_entity:
                entity_values.append(existing_entity)
                continue

            player_key = str(row.get(PLAYER_KEY_COL, "")).strip() or "unknown-player"
            if player_key in ambiguous_players:
                team_key = str(row.get("_team_key", "")).strip().lower() or "unknown"
                entity_values.append(f"{player_key}__{team_key}")
            else:
                entity_values.append(player_key)

        out[PLAYER_ENTITY_KEY_COL] = entity_values
        return out.drop(columns=["_player_key", "_year_key", "_team_key"], errors="ignore")

    return _finalize(bat_prepared), _finalize(pit_prepared)


def _build_player_identity_lookup(bat: pd.DataFrame, pit: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for frame in (bat, pit):
        if frame.empty or PLAYER_ENTITY_KEY_COL not in frame.columns:
            continue
        subset = frame[[PLAYER_ENTITY_KEY_COL, PLAYER_KEY_COL, "Player"]].copy()
        subset[PLAYER_ENTITY_KEY_COL] = subset[PLAYER_ENTITY_KEY_COL].astype("string").fillna("").str.strip()
        subset[PLAYER_KEY_COL] = subset[PLAYER_KEY_COL].astype("string").fillna("").str.strip()
        subset["Player"] = subset["Player"].astype("string").fillna("").str.strip()
        parts.append(subset)

    if not parts:
        return pd.DataFrame(columns=[PLAYER_ENTITY_KEY_COL, PLAYER_KEY_COL, "Player"])

    merged = pd.concat(parts, ignore_index=True).dropna(subset=[PLAYER_ENTITY_KEY_COL])
    merged = merged[merged[PLAYER_ENTITY_KEY_COL] != ""]
    merged = merged.drop_duplicates(subset=[PLAYER_ENTITY_KEY_COL], keep="first").reset_index(drop=True)
    merged[PLAYER_KEY_COL] = merged.apply(
        lambda row: (
            str(row.get(PLAYER_KEY_COL) or "").strip()
            or str(row.get(PLAYER_ENTITY_KEY_COL) or "").split("__", 1)[0]
            or _normalize_player_key(row.get("Player"))
        ),
        axis=1,
    )
    return merged[[PLAYER_ENTITY_KEY_COL, PLAYER_KEY_COL, "Player"]]


def _attach_identity_columns_to_output(out: pd.DataFrame, identity_lookup: pd.DataFrame) -> pd.DataFrame:
    if "Player" not in out.columns:
        return out

    result = out.rename(columns={"Player": PLAYER_ENTITY_KEY_COL}).copy()
    if identity_lookup.empty:
        result["Player"] = result[PLAYER_ENTITY_KEY_COL]
        result[PLAYER_KEY_COL] = result[PLAYER_ENTITY_KEY_COL].astype("string").str.split("__").str[0]
    else:
        result = result.merge(identity_lookup, on=PLAYER_ENTITY_KEY_COL, how="left")
        result["Player"] = result["Player"].fillna(result[PLAYER_ENTITY_KEY_COL])
        result[PLAYER_KEY_COL] = result[PLAYER_KEY_COL].fillna(
            result[PLAYER_ENTITY_KEY_COL].astype("string").str.split("__").str[0]
        )

    front = ["Player", PLAYER_KEY_COL, PLAYER_ENTITY_KEY_COL]
    rest = [c for c in result.columns if c not in front]
    return result[front + rest]
