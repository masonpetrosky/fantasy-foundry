"""
FastAPI backend for Dynasty Baseball Projections.

Endpoints:
  GET  /api/meta             → filter options (teams, years, positions)
  GET  /api/projections/bat  → hitter projections (filterable)
  GET  /api/projections/pit  → pitcher projections (filterable)
  GET  /api/calculate        → run dynasty value calculator with custom settings
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
EXCEL_PATH = DATA_DIR / "Dynasty Baseball Projections.xlsx"

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


def _find_projection_date_col(df: pd.DataFrame) -> str | None:
    for col in PROJECTION_DATE_COLS:
        if col in df.columns:
            return col
    return None


def _average_recent_projection_rows(
    records: list[dict],
    *,
    max_entries: int = 3,
    is_hitter: bool,
) -> list[dict]:
    """Collapse duplicate (Player, Year) rows by averaging the most recent projections."""
    if not records:
        return records
    if max_entries < 1:
        raise ValueError("max_entries must be >= 1")

    df = pd.DataFrame.from_records(records)
    group_cols = ["Player", "Year"]
    if any(col not in df.columns for col in group_cols):
        return records

    df = df.copy()
    df["_projection_order"] = range(len(df))

    date_col = _find_projection_date_col(df)
    if date_col:
        df["_projection_date"] = pd.to_datetime(df[date_col], errors="coerce")
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

    meta_cols = [
        c
        for c in recent.columns
        if c not in stat_cols
        and c not in group_cols
        and c not in {"_projection_order", "_projection_date", "_sort_key"}
    ]

    agg = {c: "mean" for c in stat_cols}
    for c in meta_cols:
        agg[c] = "first"

    out = (
        recent.sort_values(["_sort_key", "_projection_order"], ascending=False)
        .groupby(group_cols, as_index=False, sort=False)
        .agg(agg)
    )

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

    return out.to_dict(orient="records")


META = load_json("meta.json")
BAT_DATA_RAW = load_json("bat.json")
PIT_DATA_RAW = load_json("pitch.json")
BAT_DATA = _average_recent_projection_rows(BAT_DATA_RAW, max_entries=3, is_hitter=True)
PIT_DATA = _average_recent_projection_rows(PIT_DATA_RAW, max_entries=3, is_hitter=False)

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


# ---------------------------------------------------------------------------
# API: Metadata
# ---------------------------------------------------------------------------
@app.get("/api/meta")
def get_meta():
    return META


# ---------------------------------------------------------------------------
# API: Projections
# ---------------------------------------------------------------------------
def filter_records(records, player: str | None, team: str | None, year: int | None, pos: str | None):
    out = records
    if player:
        q = player.lower()
        out = [r for r in out if q in r.get("Player", "").lower()]
    if team:
        out = [r for r in out if r.get("Team", "") == team or r.get("MLBTeam", "") == team]
    if year:
        out = [r for r in out if r.get("Year") == year]
    if pos:
        out = [r for r in out if pos.upper() in str(r.get("Pos", "")).upper()]
    return out


@app.get("/api/projections/bat")
def get_bat_projections(
    player: Optional[str] = None,
    team: Optional[str] = None,
    year: Optional[int] = None,
    pos: Optional[str] = None,
    limit: int = Query(default=200, le=5000),
    offset: int = 0,
):
    filtered = filter_records(BAT_DATA, player, team, year, pos)
    total = len(filtered)
    page = filtered[offset : offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "data": page}


@app.get("/api/projections/pitch")
def get_pitch_projections(
    player: Optional[str] = None,
    team: Optional[str] = None,
    year: Optional[int] = None,
    pos: Optional[str] = None,
    limit: int = Query(default=200, le=5000),
    offset: int = 0,
):
    filtered = filter_records(PIT_DATA, player, team, year, pos)
    total = len(filtered)
    page = filtered[offset : offset + limit]
    return {"total": total, "offset": offset, "limit": limit, "data": page}


# ---------------------------------------------------------------------------
# API: Dynasty Value Calculator
# ---------------------------------------------------------------------------
class CalculateRequest(BaseModel):
    mode: str = "common"  # "common" or "league"
    teams: int = 12
    sims: int = 100
    horizon: int = 10
    discount: float = 0.85
    bench: int = 6
    minors: int = 0
    ip_min: float = 0.0
    ip_max: Optional[float] = None
    start_year: int = 2026
    recent_projections: int = 3


@app.post("/api/calculate")
def calculate_dynasty_values(req: CalculateRequest):
    """Run the dynasty value calculator and return results as JSON."""
    try:
        # Import the calculation module
        sys.path.insert(0, str(BASE_DIR / "backend"))
        from dynasty_roto_values import (
            CommonDynastyRotoSettings,
            calculate_common_dynasty_values,
            validate_ip_bounds,
        )

        validate_ip_bounds(req.ip_min, req.ip_max)

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

        out, bat_detail, pit_detail = calculate_common_dynasty_values(
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
