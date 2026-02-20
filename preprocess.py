"""
Preprocess the Excel projections file into JSON for fast API serving.

Run this whenever you update 'Dynasty Baseball Projections.xlsx':
    python preprocess.py

Optional:
    python preprocess.py --skip-dynasty-cache
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
EXCEL_PATH = DATA_DIR / "Dynasty Baseball Projections.xlsx"
DYNASTY_LOOKUP_CACHE_PATH = DATA_DIR / "dynasty_lookup.json"
HIT_RATE_COLS = {"AVG", "OPS"}
PIT_RATE_COLS = {"ERA", "WHIP"}
PLAYER_KEY_COL = "PlayerKey"
PLAYER_ENTITY_KEY_COL = "PlayerEntityKey"
PLAYER_KEY_PATTERN = re.compile(r"[^a-z0-9]+")


def _pick_first_existing_column(df: pd.DataFrame, names: Iterable[str]) -> str | None:
    for name in names:
        if name in df.columns:
            return name
    return None


def _clean_text_values(series: pd.Series) -> list[str]:
    unique_by_key: dict[str, str] = {}
    for value in series.dropna():
        text = str(value).strip()
        if not text:
            continue
        key = text.lower()
        if key not in unique_by_key:
            unique_by_key[key] = text
    return sorted(unique_by_key.values(), key=lambda v: v.lower())


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
        numeric = float(value)
        if pd.notna(numeric) and numeric.is_integer():
            return str(int(numeric))
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _team_column_for_dataframe(df: pd.DataFrame) -> str | None:
    return _pick_first_existing_column(df, ["Team", "MLBTeam"])


def add_player_keys(bat: pd.DataFrame, pit: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    bat_out = bat.copy()
    pit_out = pit.copy()

    def _prepare(df: pd.DataFrame, *, team_col: str | None) -> pd.DataFrame:
        out = df.copy()
        if "Player" in out.columns:
            out["_player_key"] = out["Player"].map(_normalize_player_key)
        else:
            out["_player_key"] = "unknown-player"
        out["_year_key"] = out["Year"].map(_normalize_year_key) if "Year" in out.columns else ""
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
        pkey = str(row.get("_player_key", "")).strip()
        ykey = str(row.get("_year_key", "")).strip()
        team = str(row.get("_team_key", "")).strip()
        if not pkey or not team:
            continue
        teams_by_player_year.setdefault((pkey, ykey), set()).add(team)

    ambiguous_players = {
        player_key
        for (player_key, _), teams in teams_by_player_year.items()
        if len(teams) > 1
    }

    def _finalize(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        out[PLAYER_KEY_COL] = out["_player_key"].map(lambda value: str(value).strip() or "unknown-player")
        entity_values: list[str] = []
        for _, row in out.iterrows():
            player_key = str(row.get(PLAYER_KEY_COL, "")).strip() or "unknown-player"
            if player_key in ambiguous_players:
                team_key = str(row.get("_team_key", "")).strip().lower() or "unknown"
                entity_values.append(f"{player_key}__{team_key}")
            else:
                entity_values.append(player_key)
        out[PLAYER_ENTITY_KEY_COL] = entity_values
        return out.drop(columns=["_player_key", "_year_key", "_team_key"], errors="ignore")

    return _finalize(bat_prepared), _finalize(pit_prepared)


def _extract_years(df: pd.DataFrame) -> set[int]:
    if "Year" not in df.columns:
        return set()

    numeric = pd.to_numeric(df["Year"], errors="coerce")
    whole = numeric.dropna()
    if whole.empty:
        return set()

    whole = whole[whole.mod(1).eq(0)]
    return set(whole.astype(int).tolist())


def _unique_player_count(df: pd.DataFrame) -> int:
    if "Player" not in df.columns:
        return 0
    return int(df["Player"].dropna().nunique())


def build_meta(bat: pd.DataFrame, pit: pd.DataFrame) -> dict:
    bat_team_col = _pick_first_existing_column(bat, ["Team", "MLBTeam"])
    pit_team_col = _pick_first_existing_column(pit, ["Team", "MLBTeam"])

    teams: list[str] = []
    if bat_team_col:
        teams.extend(_clean_text_values(bat[bat_team_col]))
    if pit_team_col:
        teams.extend(_clean_text_values(pit[pit_team_col]))
    teams = _clean_text_values(pd.Series(teams, dtype="string"))

    bat_positions = _clean_text_values(bat["Pos"]) if "Pos" in bat.columns else []
    pit_positions = _clean_text_values(pit["Pos"]) if "Pos" in pit.columns else []
    years = sorted(_extract_years(bat) | _extract_years(pit))

    return {
        "teams": teams,
        "years": years,
        "bat_positions": bat_positions,
        "pit_positions": pit_positions,
        "total_hitters": _unique_player_count(bat),
        "total_pitchers": _unique_player_count(pit),
    }


def convert_datetime_columns_for_json(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == "datetime64[ns]" or "date" in col.lower():
            out[col] = out[col].astype(str)
    return out


def round_float_columns(df: pd.DataFrame, *, rate_cols: set[str]) -> pd.DataFrame:
    out = df.copy()
    for col in out.select_dtypes(include="float").columns:
        out[col] = out[col].round(3 if col in rate_cols else 1)
    return out


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Regenerate projection JSON files and optional dynasty lookup cache.",
    )
    parser.add_argument(
        "--skip-dynasty-cache",
        action="store_true",
        help="Skip generation of data/dynasty_lookup.json (faster preprocess, slower first projections load).",
    )
    return parser.parse_args()


def _build_dynasty_lookup_cache() -> tuple[int, int]:
    import backend.app as backend_app

    # Ensure app globals match the freshly-written JSON snapshots.
    backend_app._refresh_data_if_needed()
    backend_app._get_default_dynasty_lookup.cache_clear()
    strict_required = bool(getattr(backend_app, "REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP", False))
    setattr(backend_app, "REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP", False)
    try:
        lookup_by_entity, lookup_by_player_key, ambiguous_player_keys, year_cols = backend_app._get_default_dynasty_lookup()
    finally:
        setattr(backend_app, "REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP", strict_required)
    cache_data_version = backend_app._current_data_version()
    payload = {
        "format_version": 1,
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "cache_data_version": cache_data_version,
        # Legacy compatibility key: retained for older deployments/tests.
        "data_version": cache_data_version,
        "lookup_by_entity": lookup_by_entity,
        "lookup_by_player_key": lookup_by_player_key,
        "ambiguous_player_keys": sorted(str(key) for key in ambiguous_player_keys if str(key).strip()),
        "year_cols": [str(col) for col in year_cols if isinstance(col, str)],
    }

    with DYNASTY_LOOKUP_CACHE_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)

    return len(lookup_by_entity), len(lookup_by_player_key)


def main():
    args = _parse_args()
    print(f"Reading {EXCEL_PATH} ...")
    bat = pd.read_excel(EXCEL_PATH, sheet_name="Bat")
    pit = pd.read_excel(EXCEL_PATH, sheet_name="Pitch")

    # Convert datetime columns to strings for JSON serialization
    bat = convert_datetime_columns_for_json(bat)
    pit = convert_datetime_columns_for_json(pit)

    # Attach deterministic player identity keys for robust downstream joins.
    bat, pit = add_player_keys(bat, pit)

    # Round floats for cleaner JSON
    bat = round_float_columns(bat, rate_cols=HIT_RATE_COLS)
    pit = round_float_columns(pit, rate_cols=PIT_RATE_COLS)

    # Write data JSON files
    bat.to_json(DATA_DIR / "bat.json", orient="records")
    pit.to_json(DATA_DIR / "pitch.json", orient="records")

    # Write metadata for frontend filters
    meta = build_meta(bat, pit)
    with open(DATA_DIR / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    built_dynasty_cache = False
    if args.skip_dynasty_cache:
        print("  Dynasty lookup cache: skipped (--skip-dynasty-cache)")
    else:
        print("Building default dynasty lookup cache (this may take a while) ...")
        try:
            entity_count, player_key_count = _build_dynasty_lookup_cache()
            built_dynasty_cache = True
            print(
                "  Dynasty lookup cache: "
                f"{DYNASTY_LOOKUP_CACHE_PATH.name} ({entity_count} entity keys, {player_key_count} player-key fallbacks)"
            )
        except Exception as exc:
            print(f"  Error: failed to build dynasty lookup cache: {exc}")
            raise SystemExit(1) from exc

    print(f"  Hitters:  {len(bat):,} rows, {meta['total_hitters']} unique players")
    print(f"  Pitchers: {len(pit):,} rows, {meta['total_pitchers']} unique players")
    if meta["years"]:
        print(f"  Years:    {meta['years'][0]}–{meta['years'][-1]}")
    else:
        print("  Years:    n/a")
    output_files = ["bat.json", "pitch.json", "meta.json"]
    if built_dynasty_cache:
        output_files.append(DYNASTY_LOOKUP_CACHE_PATH.name)
    print(f"  Output:   {', '.join(output_files)}")
    print("Done!")


if __name__ == "__main__":
    main()
