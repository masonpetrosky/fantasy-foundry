"""
FastAPI backend for Dynasty Baseball Projections.

Endpoints:
  GET  /api/meta             → filter options (teams, years, positions)
  GET  /api/projections/bat  → hitter projections (filterable)
  GET  /api/projections/pitch → pitcher projections (filterable)
  POST /api/calculate        → run dynasty value calculator with custom settings
"""

from __future__ import annotations

import json
import re
import sys
import traceback
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Literal, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
EXCEL_PATH = DATA_DIR / "Dynasty Baseball Projections.xlsx"
BACKEND_MODULE_DIR = BASE_DIR / "backend"

# ---------------------------------------------------------------------------
# Load pre-processed JSON data once at startup
# ---------------------------------------------------------------------------
def load_json(name: str):
    p = DATA_DIR / name
    with open(p) as f:
        return json.load(f)


PROJECTION_DATE_COLS = ["ProjectionDate", "Date", "Updated", "LastUpdated", "Timestamp", "Created", "AsOf"]
DERIVED_HIT_RATE_COLS = {"AVG", "OPS"}
DERIVED_PIT_RATE_COLS = {"ERA", "WHIP"}
TEAM_COL_CANDIDATES = ("Team", "MLBTeam")
YEAR_RANGE_TOKEN_RE = re.compile(r"^(\d{4})\s*-\s*(\d{4})$")
POSITION_TOKEN_SPLIT_RE = re.compile(r"[,\s/]+")


def _pick_first_existing_col(df: pd.DataFrame, candidates: list[str] | tuple[str, ...]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _find_projection_date_col(df: pd.DataFrame) -> str | None:
    return _pick_first_existing_col(df, PROJECTION_DATE_COLS)


def _parse_projection_dates(values: pd.Series) -> pd.Series:
    """Parse mixed-format date strings safely."""
    text = values.astype("string").str.strip()
    try:
        parsed = pd.to_datetime(text, errors="coerce", format="mixed")
    except TypeError:
        parsed = pd.to_datetime(text, errors="coerce")

    missing = parsed.isna() & text.notna() & (text != "")
    if missing.any():
        reparsed = text[missing].map(lambda v: pd.to_datetime(v, errors="coerce"))
        parsed.loc[missing] = reparsed
    return parsed


def _average_recent_projection_rows(
    records: list[dict],
    *,
    max_entries: int = 3,
    is_hitter: bool,
) -> list[dict]:
    """Collapse duplicate projection rows by averaging recent entries.

    Rows are grouped by (Player, Year) and disambiguated by team only when a
    given name/year has multiple non-empty teams. This avoids merging distinct
    players who share the same name while preserving normal update averaging.
    """
    if not records:
        return records
    if max_entries < 1:
        raise ValueError("max_entries must be >= 1")

    df = pd.DataFrame.from_records(records)
    group_cols_base = ["Player", "Year"]
    if any(col not in df.columns for col in group_cols_base):
        return records

    df = df.copy()
    group_cols = list(group_cols_base)
    internal_group_cols: list[str] = []

    team_col = _pick_first_existing_col(df, TEAM_COL_CANDIDATES)
    if team_col:
        team_values = df[team_col].astype("string").fillna("").str.strip()
        team_nonempty = team_values.where(team_values != "", pd.NA)
        team_counts = team_nonempty.groupby([df[c] for c in group_cols_base], dropna=False).transform("nunique")
        if team_counts.gt(1).any():
            # Split only ambiguous name/year groups so same-name different-team
            # players are not merged into one averaged row.
            df["_entity_team"] = team_values.where(team_counts > 1, "")
            group_cols.append("_entity_team")
            internal_group_cols.append("_entity_team")

    df["_projection_order"] = range(len(df))

    date_col = _find_projection_date_col(df)
    if date_col:
        df["_projection_date"] = _parse_projection_dates(df[date_col])
        df["_sort_key"] = df["_projection_date"].fillna(pd.Timestamp.min)
    else:
        df["_projection_date"] = pd.NaT
        df["_sort_key"] = df["_projection_order"]

    excluded = {"Age"} | (DERIVED_HIT_RATE_COLS if is_hitter else DERIVED_PIT_RATE_COLS)
    stat_cols = [
        c
        for c in df.columns
        if c not in group_cols
        and c not in excluded
        and pd.api.types.is_numeric_dtype(df[c])
    ]

    recent = (
        df.sort_values(["_sort_key", "_projection_order"], ascending=False)
        .groupby(group_cols, as_index=False, sort=False)
        .head(max_entries)
    )
    recent["ProjectionsUsed"] = 1
    recent["OldestProjectionDate"] = recent["_projection_date"]

    meta_cols = [
        c
        for c in recent.columns
        if c not in stat_cols
        and c not in group_cols
        and c
        not in {
            "_projection_order",
            "_projection_date",
            "_sort_key",
            "ProjectionsUsed",
            "OldestProjectionDate",
        }
    ]

    agg = {c: "mean" for c in stat_cols}
    agg["ProjectionsUsed"] = "sum"
    agg["OldestProjectionDate"] = "min"
    for c in meta_cols:
        agg[c] = "first"

    out = (
        recent.sort_values(["_sort_key", "_projection_order"], ascending=False)
        .groupby(group_cols, as_index=False, sort=False)
        .agg(agg)
    )
    if internal_group_cols:
        out = out.drop(columns=internal_group_cols, errors="ignore")

    front = ["Player", "Year", "ProjectionsUsed", "OldestProjectionDate"]
    out = out[[c for c in front if c in out.columns] + [c for c in out.columns if c not in front]]

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
            out["OPS"] = obp + slg
    else:
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


META = load_json("meta.json")
BAT_DATA_RAW = load_json("bat.json")
PIT_DATA_RAW = load_json("pitch.json")
BAT_DATA = _average_recent_projection_rows(BAT_DATA_RAW, max_entries=3, is_hitter=True)
PIT_DATA = _average_recent_projection_rows(PIT_DATA_RAW, max_entries=3, is_hitter=False)
DATA_REFRESH_PATHS = (
    DATA_DIR / "meta.json",
    DATA_DIR / "bat.json",
    DATA_DIR / "pitch.json",
    EXCEL_PATH,
)
DATA_REFRESH_LOCK = Lock()


def _path_signature(path: Path) -> tuple[str, int | None, int | None]:
    try:
        stat = path.stat()
        return (str(path), stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError:
        return (str(path), None, None)


def _compute_data_signature() -> tuple[tuple[str, int | None, int | None], ...]:
    return tuple(_path_signature(path) for path in DATA_REFRESH_PATHS)


_DATA_SOURCE_SIGNATURE: tuple[tuple[str, int | None, int | None], ...] | None = _compute_data_signature()


def _reload_projection_data() -> None:
    global META, BAT_DATA_RAW, PIT_DATA_RAW, BAT_DATA, PIT_DATA
    META = load_json("meta.json")
    BAT_DATA_RAW = load_json("bat.json")
    PIT_DATA_RAW = load_json("pitch.json")
    BAT_DATA = _average_recent_projection_rows(BAT_DATA_RAW, max_entries=3, is_hitter=True)
    PIT_DATA = _average_recent_projection_rows(PIT_DATA_RAW, max_entries=3, is_hitter=False)


def _coerce_meta_years(meta: dict) -> list[int]:
    years: list[int] = []
    for value in meta.get("years", []):
        try:
            years.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(years))


def _value_col_sort_key(col: str) -> tuple[int, int | str]:
    suffix = col.split("_", 1)[1] if "_" in col else col
    return (0, int(suffix)) if suffix.isdigit() else (1, suffix)


def _ensure_backend_module_path() -> None:
    backend_path = str(BACKEND_MODULE_DIR)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)


@lru_cache(maxsize=1)
def _get_default_dynasty_lookup() -> tuple[dict[str, dict], list[str]]:
    """Cached default dynasty values keyed by player name."""
    try:
        _ensure_backend_module_path()
        from dynasty_roto_values import CommonDynastyRotoSettings, calculate_common_dynasty_values

        years = _coerce_meta_years(META)
        start_year = years[0] if years else 2026
        horizon = len(years) if years else 10

        lg = CommonDynastyRotoSettings(
            n_teams=12,
            sims_for_sgp=100,
            horizon_years=horizon,
            discount=0.85,
            bench_slots=6,
            minor_slots=0,
            ip_min=0.0,
            ip_max=None,
        )

        out = calculate_common_dynasty_values(
            str(EXCEL_PATH),
            lg,
            start_year=start_year,
            verbose=False,
            return_details=False,
            seed=0,
            recent_projections=3,
        )

        year_cols = sorted(
            [c for c in out.columns if isinstance(c, str) and c.startswith("Value_")],
            key=_value_col_sort_key,
        )
        keep_cols = [c for c in ["Player", "DynastyValue"] + year_cols if c in out.columns]
        df = out[keep_cols].copy()

        for col in df.select_dtypes(include="float").columns:
            df[col] = df[col].round(2)

        lookup: dict[str, dict] = {}
        for row in df.to_dict(orient="records"):
            player = row.pop("Player", None)
            if not player:
                continue

            cleaned: dict = {}
            for key, value in row.items():
                if pd.isna(value):
                    cleaned[key] = None
                else:
                    cleaned[key] = value
            lookup[player] = cleaned

        return lookup, year_cols
    except Exception:
        traceback.print_exc()
        return {}, []


def _parse_dynasty_years(raw: str | None, *, valid_years: list[int] | None = None) -> list[int]:
    if not raw:
        return []

    years: list[int] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue

        range_match = YEAR_RANGE_TOKEN_RE.fullmatch(token)
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


def _resolve_projection_year_filter(
    year: int | None,
    years: str | None,
    *,
    valid_years: list[int] | None = None,
) -> set[int] | None:
    years_specified = bool(years and years.strip())
    parsed_years: set[int] | None = None
    if years_specified:
        parsed_years = set(_parse_dynasty_years(years, valid_years=valid_years))

    if year is None and parsed_years is None:
        return None

    if parsed_years is None:
        return {year} if year is not None else set()

    if year is not None:
        parsed_years.intersection_update({year})

    return parsed_years


def _attach_dynasty_values(rows: list[dict], dynasty_years: list[int] | None = None) -> list[dict]:
    if not rows:
        return rows

    lookup, available_year_cols = _get_default_dynasty_lookup()
    if not lookup:
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
        player_values = lookup.get(str(row.get("Player", "")), {})
        for col in cols:
            enriched[col] = player_values.get(col)
        enriched_rows.append(enriched)

    return enriched_rows


def _refresh_data_if_needed() -> None:
    global _DATA_SOURCE_SIGNATURE
    current_signature = _compute_data_signature()
    if current_signature == _DATA_SOURCE_SIGNATURE:
        return

    with DATA_REFRESH_LOCK:
        current_signature = _compute_data_signature()
        if current_signature == _DATA_SOURCE_SIGNATURE:
            return

        try:
            _reload_projection_data()
        except Exception:
            traceback.print_exc()
            return

        _get_default_dynasty_lookup.cache_clear()
        _DATA_SOURCE_SIGNATURE = current_signature

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Dynasty Baseball Projections", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    GZipMiddleware,
    minimum_size=1000,
)


# ---------------------------------------------------------------------------
# API: Metadata
# ---------------------------------------------------------------------------
@app.get("/api/meta")
def get_meta():
    _refresh_data_if_needed()
    return META


# ---------------------------------------------------------------------------
# API: Projections
# ---------------------------------------------------------------------------
def _coerce_record_year(value: object) -> int | None:
    """Normalize JSON year values from int/float/string to int for robust filtering."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = float(text)
        except ValueError:
            return None
        return int(parsed) if parsed.is_integer() else None
    return None


def _position_tokens(value: object) -> set[str]:
    text = str(value or "").strip().upper()
    if not text:
        return set()
    return {token for token in POSITION_TOKEN_SPLIT_RE.split(text) if token}


def filter_records(
    records,
    player: str | None,
    team: str | None,
    years: set[int] | None,
    pos: str | None,
):
    out = records
    if player:
        q = player.strip().lower()
        out = [r for r in out if q in str(r.get("Player", "")).lower()]
    if team:
        team_normalized = team.strip().lower()
        out = [
            r for r in out
            if str(r.get("Team", "")).strip().lower() == team_normalized
            or str(r.get("MLBTeam", "")).strip().lower() == team_normalized
        ]
    if years is not None:
        out = [r for r in out if _coerce_record_year(r.get("Year")) in years]
    if pos:
        requested_positions = _position_tokens(pos)
        if requested_positions:
            out = [
                r for r in out
                if requested_positions.intersection(_position_tokens(r.get("Pos", "")))
            ]
    return out


@app.get("/api/projections/bat")
def get_bat_projections(
    player: Optional[str] = None,
    team: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[str] = None,
    pos: Optional[str] = None,
    dynasty_years: Optional[str] = None,
    include_dynasty: bool = True,
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
):
    _refresh_data_if_needed()
    valid_years = _coerce_meta_years(META)
    requested_years = _resolve_projection_year_filter(year, years, valid_years=valid_years)
    filtered = filter_records(BAT_DATA, player, team, requested_years, pos)
    total = len(filtered)
    page = filtered[offset : offset + limit]
    if include_dynasty:
        page = _attach_dynasty_values(page, _parse_dynasty_years(dynasty_years, valid_years=valid_years))
    return {"total": total, "offset": offset, "limit": limit, "data": page}


@app.get("/api/projections/pitch")
def get_pitch_projections(
    player: Optional[str] = None,
    team: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[str] = None,
    pos: Optional[str] = None,
    dynasty_years: Optional[str] = None,
    include_dynasty: bool = True,
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
):
    _refresh_data_if_needed()
    valid_years = _coerce_meta_years(META)
    requested_years = _resolve_projection_year_filter(year, years, valid_years=valid_years)
    filtered = filter_records(PIT_DATA, player, team, requested_years, pos)
    total = len(filtered)
    page = filtered[offset : offset + limit]
    if include_dynasty:
        page = _attach_dynasty_values(page, _parse_dynasty_years(dynasty_years, valid_years=valid_years))
    return {"total": total, "offset": offset, "limit": limit, "data": page}


# ---------------------------------------------------------------------------
# API: Dynasty Value Calculator
# ---------------------------------------------------------------------------
class CalculateRequest(BaseModel):
    mode: Literal["common"] = "common"
    teams: int = Field(default=12, ge=2, le=30)
    sims: int = Field(default=100, ge=1, le=5000)
    horizon: int = Field(default=10, ge=1, le=20)
    discount: float = Field(default=0.85, gt=0.0, le=1.0)
    bench: int = Field(default=6, ge=0, le=40)
    minors: int = Field(default=0, ge=0, le=60)
    ip_min: float = Field(default=0.0, ge=0.0)
    ip_max: Optional[float] = Field(default=None, ge=0.0)
    start_year: int = Field(default=2026, ge=1900)
    recent_projections: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_ip_bounds(self) -> "CalculateRequest":
        if self.ip_max is not None and self.ip_max < self.ip_min:
            raise ValueError("ip_max must be greater than or equal to ip_min")
        return self


@app.post("/api/calculate")
def calculate_dynasty_values(req: CalculateRequest):
    """Run the dynasty value calculator and return results as JSON."""
    try:
        _refresh_data_if_needed()
        valid_years = _coerce_meta_years(META)
        if valid_years and req.start_year not in set(valid_years):
            raise HTTPException(
                status_code=422,
                detail=f"start_year must be one of the available projection years: {valid_years}",
            )

        # Import the calculation module
        _ensure_backend_module_path()
        from dynasty_roto_values import (
            CommonDynastyRotoSettings,
            calculate_common_dynasty_values,
        )

        lg = CommonDynastyRotoSettings(
            n_teams=req.teams,
            sims_for_sgp=req.sims,
            horizon_years=req.horizon,
            discount=req.discount,
            bench_slots=req.bench,
            minor_slots=req.minors,
            ip_min=req.ip_min,
            ip_max=req.ip_max,
        )

        out, _, _ = calculate_common_dynasty_values(
            str(EXCEL_PATH),
            lg,
            start_year=req.start_year,
            verbose=False,
            return_details=True,
            seed=0,
            recent_projections=req.recent_projections,
        )

        # Select output columns
        year_cols = [c for c in out.columns if c.startswith("Value_")]
        cols = [
            "Player", "Team", "Pos", "Age",
            "DynastyValue", "RawDynastyValue",
            "minor_eligible",
        ] + year_cols

        available_cols = [c for c in cols if c in out.columns]
        df = out[available_cols].copy()

        # Round for JSON
        for c in df.select_dtypes(include="float").columns:
            df[c] = df[c].round(2)

        records = df.to_dict(orient="records")

        return {
            "total": len(records),
            "settings": req.model_dump(),
            "data": records,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    @app.get("/")
    def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
