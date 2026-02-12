"""
FastAPI backend for Dynasty Baseball Projections.

Endpoints:
  GET  /api/meta             → filter options (teams, years, positions)
  GET  /api/projections/all  → merged hitter+pitcher projections (filterable)
  GET  /api/projections/bat  → hitter projections (filterable)
  GET  /api/projections/pitch → pitcher projections (filterable)
  POST /api/calculate        → run dynasty value calculator with custom settings
"""

from __future__ import annotations

import logging
import json
import math
import os
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import cmp_to_key, lru_cache
from pathlib import Path
from threading import Lock, Thread
from typing import Literal, Optional
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
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
INDEX_PATH = FRONTEND_DIR / "index.html"
DEPLOY_COMMIT_SHA = os.getenv("RAILWAY_GIT_COMMIT_SHA", "").strip()


def _build_id() -> str:
    if DEPLOY_COMMIT_SHA:
        return DEPLOY_COMMIT_SHA[:12]
    try:
        return str(INDEX_PATH.stat().st_mtime_ns)
    except OSError:
        return "unknown"


def _build_timestamp_iso() -> str | None:
    try:
        ts = INDEX_PATH.stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


APP_BUILD_ID = _build_id()
APP_BUILD_AT = _build_timestamp_iso()
INDEX_BUILD_TOKEN = "__APP_BUILD_ID__"

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
PROJECTION_QUERY_CACHE_MAXSIZE = 256
POSITION_DISPLAY_ORDER = ("C", "1B", "2B", "3B", "SS", "OF", "DH", "UT", "SP", "RP")
ALL_TAB_HITTER_STAT_COLS = ("G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "BB", "SO", "AVG", "OPS")
ALL_TAB_PITCH_STAT_COLS = ("GS", "IP", "W", "L", "K", "SV", "SVH", "ERA", "WHIP", "ER")
PROJECTION_TEXT_SORT_COLS = {"Player", "Team", "Pos", "Type"}
PLAYER_KEY_COL = "PlayerKey"
PLAYER_ENTITY_KEY_COL = "PlayerEntityKey"
PLAYER_KEY_PATTERN = re.compile(r"[^a-z0-9]+")
COMMON_HITTER_STARTER_SLOTS_PER_TEAM = 13
COMMON_PITCHER_STARTER_SLOTS_PER_TEAM = 9
CALCULATOR_JOB_TTL_SECONDS = max(60, int(os.getenv("FF_CALC_JOB_TTL_SECONDS", "1800")))
CALCULATOR_JOB_MAX_ENTRIES = max(10, int(os.getenv("FF_CALC_JOB_MAX_ENTRIES", "256")))
CALCULATOR_JOB_WORKERS = max(1, int(os.getenv("FF_CALC_JOB_WORKERS", "2")))
ENABLE_STARTUP_CALC_PREWARM = os.getenv("FF_PREWARM_DEFAULT_CALC", "1").strip().lower() not in {"0", "false", "no"}
CALCULATOR_REQUEST_TIMEOUT_SECONDS = max(60, int(os.getenv("FF_CALC_REQUEST_TIMEOUT_SECONDS", "600")))
CALC_LOGGER = logging.getLogger("fantasy_foundry.calculate")


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


def _normalize_player_key(value: object) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return "unknown-player"
    key = PLAYER_KEY_PATTERN.sub("-", text).strip("-")
    return key or "unknown-player"


def _normalize_team_key(value: object) -> str:
    return str(value or "").strip().upper()


def _normalize_year_key(value: object) -> str:
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


def _with_player_identity_keys(
    bat_records: list[dict],
    pit_records: list[dict],
) -> tuple[list[dict], list[dict]]:
    combined = list(bat_records) + list(pit_records)
    if not combined:
        return bat_records, pit_records

    teams_by_player_year: dict[tuple[str, str], set[str]] = {}
    for record in combined:
        player_key = str(record.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(record.get("Player"))
        year_key = _normalize_year_key(record.get("Year"))
        team_key = _normalize_team_key(record.get("Team") or record.get("MLBTeam"))
        if not team_key:
            continue
        teams_by_player_year.setdefault((player_key, year_key), set()).add(team_key)

    ambiguous_player_keys = {
        player_key
        for (player_key, _), teams in teams_by_player_year.items()
        if len(teams) > 1
    }

    def _apply(records: list[dict]) -> list[dict]:
        out: list[dict] = []
        for record in records:
            row = dict(record)
            player_key = str(row.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(row.get("Player"))
            row[PLAYER_KEY_COL] = player_key

            entity_key = str(row.get(PLAYER_ENTITY_KEY_COL) or "").strip()
            if not entity_key:
                if player_key in ambiguous_player_keys:
                    team_key = _normalize_team_key(row.get("Team") or row.get("MLBTeam")).lower() or "unknown"
                    entity_key = f"{player_key}__{team_key}"
                else:
                    entity_key = player_key
            row[PLAYER_ENTITY_KEY_COL] = entity_key
            out.append(row)
        return out

    return _apply(bat_records), _apply(pit_records)


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
BAT_DATA_RAW, PIT_DATA_RAW = _with_player_identity_keys(BAT_DATA_RAW, PIT_DATA_RAW)
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
CALCULATOR_JOB_EXECUTOR = ThreadPoolExecutor(max_workers=CALCULATOR_JOB_WORKERS)
CALCULATOR_JOB_LOCK = Lock()
CALCULATOR_JOBS: dict[str, dict] = {}
CALCULATOR_PREWARM_LOCK = Lock()
CALCULATOR_PREWARM_STATE = {
    "status": "idle",
    "started_at": None,
    "completed_at": None,
    "duration_ms": None,
    "error": None,
}


def _reload_projection_data() -> None:
    global META, BAT_DATA_RAW, PIT_DATA_RAW, BAT_DATA, PIT_DATA
    META = load_json("meta.json")
    BAT_DATA_RAW = load_json("bat.json")
    PIT_DATA_RAW = load_json("pitch.json")
    BAT_DATA_RAW, PIT_DATA_RAW = _with_player_identity_keys(BAT_DATA_RAW, PIT_DATA_RAW)
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


@lru_cache(maxsize=16)
def _calculate_common_dynasty_frame_cached(
    teams: int,
    sims: int,
    horizon: int,
    discount: float,
    bench: int,
    minors: int,
    ip_min: float,
    ip_max: float | None,
    start_year: int,
    recent_projections: int,
) -> pd.DataFrame:
    _ensure_backend_module_path()
    from dynasty_roto_values import CommonDynastyRotoSettings, calculate_common_dynasty_values

    lg = CommonDynastyRotoSettings(
        n_teams=teams,
        sims_for_sgp=sims,
        horizon_years=horizon,
        discount=discount,
        bench_slots=bench,
        minor_slots=minors,
        ip_min=ip_min,
        ip_max=ip_max,
        two_way="sum",
    )

    out = calculate_common_dynasty_values(
        str(EXCEL_PATH),
        lg,
        start_year=start_year,
        verbose=False,
        return_details=False,
        seed=0,
        recent_projections=recent_projections,
    )
    return out


def _is_user_fixable_calculation_error(message: str) -> bool:
    normalized = message.lower()
    return (
        "not enough players" in normalized
        or "no valuation years available" in normalized
    )


def _clean_records_for_json(records: list[dict]) -> list[dict]:
    for row in records:
        for key, value in row.items():
            if value is None:
                continue

            if isinstance(value, (int, float)) and not isinstance(value, bool):
                if not math.isfinite(float(value)):
                    row[key] = None
                continue

            try:
                if pd.isna(value):
                    row[key] = None
            except (TypeError, ValueError):
                continue
    return records


def _as_float(value: object) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isfinite(parsed):
        return parsed
    return None


@lru_cache(maxsize=1)
def _playable_pool_counts_by_year() -> dict[str, dict[str, int]]:
    by_year: dict[int, dict[str, int]] = {}

    for row in BAT_DATA:
        year = _coerce_record_year(row.get("Year"))
        if year is None:
            continue
        ab = _as_float(row.get("AB"))
        if ab is None or ab <= 0:
            continue
        bucket = by_year.setdefault(year, {"hitters": 0, "pitchers": 0})
        bucket["hitters"] += 1

    for row in PIT_DATA:
        year = _coerce_record_year(row.get("Year"))
        if year is None:
            continue
        ip = _as_float(row.get("IP"))
        if ip is None or ip <= 0:
            continue
        bucket = by_year.setdefault(year, {"hitters": 0, "pitchers": 0})
        bucket["pitchers"] += 1

    return {str(year): counts for year, counts in sorted(by_year.items())}


def _default_calculation_cache_params() -> dict[str, int | float | None]:
    years = _coerce_meta_years(META)
    start_year = years[0] if years else 2026
    horizon = len(years) if years else 10
    return {
        "teams": 12,
        "sims": 300,
        "horizon": horizon,
        "discount": 0.85,
        "bench": 6,
        "minors": 0,
        "ip_min": 0.0,
        "ip_max": None,
        "start_year": start_year,
        "recent_projections": 3,
    }


def _calculator_guardrails_payload() -> dict:
    return {
        "hitters_per_team": COMMON_HITTER_STARTER_SLOTS_PER_TEAM,
        "pitchers_per_team": COMMON_PITCHER_STARTER_SLOTS_PER_TEAM,
        "playable_by_year": _playable_pool_counts_by_year(),
        "job_timeout_seconds": CALCULATOR_REQUEST_TIMEOUT_SECONDS,
    }


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _cleanup_calculation_jobs(now_ts: float | None = None) -> None:
    current = time.time() if now_ts is None else now_ts
    expired_ids: list[str] = []
    completed: list[tuple[str, float]] = []

    for job_id, job in CALCULATOR_JOBS.items():
        status = str(job.get("status") or "").lower()
        created_ts = float(job.get("created_ts") or current)
        age = current - created_ts
        if status in {"completed", "failed"} and age > CALCULATOR_JOB_TTL_SECONDS:
            expired_ids.append(job_id)
        elif status in {"completed", "failed"}:
            completed.append((job_id, created_ts))

    for job_id in expired_ids:
        CALCULATOR_JOBS.pop(job_id, None)

    if len(CALCULATOR_JOBS) <= CALCULATOR_JOB_MAX_ENTRIES:
        return

    completed.sort(key=lambda item: item[1])
    while len(CALCULATOR_JOBS) > CALCULATOR_JOB_MAX_ENTRIES and completed:
        job_id, _ = completed.pop(0)
        CALCULATOR_JOBS.pop(job_id, None)


def _calculation_job_public_payload(job: dict) -> dict:
    payload = {
        "job_id": job["job_id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "settings": job.get("settings"),
    }
    if job["status"] == "completed":
        payload["result"] = job.get("result")
    elif job["status"] == "failed":
        payload["error"] = job.get("error")
    return payload


def _prewarm_default_calculation_caches() -> None:
    with CALCULATOR_PREWARM_LOCK:
        CALCULATOR_PREWARM_STATE.update(
            {
                "status": "running",
                "started_at": _iso_now(),
                "completed_at": None,
                "duration_ms": None,
                "error": None,
            }
        )

    started = time.perf_counter()
    try:
        _refresh_data_if_needed()
        params = _default_calculation_cache_params()
        ip_max = params["ip_max"]
        _calculate_common_dynasty_frame_cached(
            teams=int(params["teams"]),
            sims=int(params["sims"]),
            horizon=int(params["horizon"]),
            discount=float(params["discount"]),
            bench=int(params["bench"]),
            minors=int(params["minors"]),
            ip_min=float(params["ip_min"]),
            ip_max=float(ip_max) if ip_max is not None else None,
            start_year=int(params["start_year"]),
            recent_projections=int(params["recent_projections"]),
        )
        _get_default_dynasty_lookup()

        duration_ms = round((time.perf_counter() - started) * 1000.0, 1)
        with CALCULATOR_PREWARM_LOCK:
            CALCULATOR_PREWARM_STATE.update(
                {
                    "status": "ready",
                    "completed_at": _iso_now(),
                    "duration_ms": duration_ms,
                    "error": None,
                }
            )
        CALC_LOGGER.info("calculator prewarm completed duration_ms=%s", duration_ms)
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 1)
        with CALCULATOR_PREWARM_LOCK:
            CALCULATOR_PREWARM_STATE.update(
                {
                    "status": "failed",
                    "completed_at": _iso_now(),
                    "duration_ms": duration_ms,
                    "error": str(exc),
                }
            )
        CALC_LOGGER.exception("calculator prewarm failed")


@lru_cache(maxsize=1)
def _get_default_dynasty_lookup() -> tuple[dict[str, dict], dict[str, dict], set[str], list[str]]:
    """Cached default dynasty values keyed by PlayerEntityKey first, then unique PlayerKey."""
    try:
        years = _coerce_meta_years(META)
        start_year = years[0] if years else 2026
        horizon = len(years) if years else 10

        out = _calculate_common_dynasty_frame_cached(
            teams=12,
            sims=300,
            horizon=horizon,
            discount=0.85,
            bench=6,
            minors=0,
            ip_min=0.0,
            ip_max=None,
            start_year=start_year,
            recent_projections=3,
        ).copy(deep=True)

        year_cols = sorted(
            [c for c in out.columns if isinstance(c, str) and c.startswith("Value_")],
            key=_value_col_sort_key,
        )
        keep_cols = [c for c in ["Player", "DynastyValue"] + year_cols if c in out.columns]
        df = out[keep_cols].copy()

        for col in df.select_dtypes(include="float").columns:
            df[col] = df[col].round(2)

        lookup_by_name: dict[str, dict] = {}
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
            lookup_by_name[str(player).strip()] = cleaned

        combined_records = list(BAT_DATA) + list(PIT_DATA)
        entities_by_player_key: dict[str, set[str]] = {}
        name_by_player_key: dict[str, set[str]] = {}
        for record in combined_records:
            player_name = str(record.get("Player", "")).strip()
            player_key = str(record.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(player_name)
            entity_key = str(record.get(PLAYER_ENTITY_KEY_COL) or "").strip() or player_key
            if player_key:
                name_by_player_key.setdefault(player_key, set()).add(player_name)
                entities_by_player_key.setdefault(player_key, set()).add(entity_key)

        ambiguous_player_keys = {
            player_key
            for player_key, entity_keys in entities_by_player_key.items()
            if len(entity_keys) > 1
        }

        lookup_by_entity: dict[str, dict] = {}
        lookup_by_player_key: dict[str, dict] = {}
        for record in combined_records:
            player_name = str(record.get("Player", "")).strip()
            if not player_name:
                continue
            player_values = lookup_by_name.get(player_name)
            if player_values is None:
                continue

            player_key = str(record.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(player_name)
            entity_key = str(record.get(PLAYER_ENTITY_KEY_COL) or "").strip() or player_key
            if player_key not in ambiguous_player_keys:
                lookup_by_player_key.setdefault(player_key, player_values)
                lookup_by_entity.setdefault(entity_key, player_values)

        return lookup_by_entity, lookup_by_player_key, ambiguous_player_keys, year_cols
    except Exception:
        traceback.print_exc()
        return {}, {}, set(), []


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

    lookup_by_entity, lookup_by_player_key, ambiguous_player_keys, available_year_cols = _get_default_dynasty_lookup()
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
        player_key = str(enriched.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(player_name)
        entity_key = str(enriched.get(PLAYER_ENTITY_KEY_COL) or "").strip() or player_key
        enriched[PLAYER_KEY_COL] = player_key
        enriched[PLAYER_ENTITY_KEY_COL] = entity_key

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


@lru_cache(maxsize=1)
def _player_identity_by_name() -> dict[str, tuple[str, str | None]]:
    identities: dict[str, dict[str, set[str]]] = {}
    for record in list(BAT_DATA) + list(PIT_DATA):
        player_name = str(record.get("Player", "")).strip()
        if not player_name:
            continue
        player_key = str(record.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(player_name)
        entity_key = str(record.get(PLAYER_ENTITY_KEY_COL) or "").strip() or player_key
        bucket = identities.setdefault(player_name, {"player_keys": set(), "entity_keys": set()})
        bucket["player_keys"].add(player_key)
        bucket["entity_keys"].add(entity_key)

    out: dict[str, tuple[str, str | None]] = {}
    for player_name, bucket in identities.items():
        player_keys = bucket["player_keys"]
        entity_keys = bucket["entity_keys"]
        resolved_player_key = next(iter(player_keys)) if len(player_keys) == 1 else _normalize_player_key(player_name)
        resolved_entity_key = next(iter(entity_keys)) if len(entity_keys) == 1 else None
        out[player_name] = (resolved_player_key, resolved_entity_key)
    return out


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

        _cached_projection_rows.cache_clear()
        _cached_all_projection_rows.cache_clear()
        _projection_sortable_columns_for_dataset.cache_clear()
        _calculate_common_dynasty_frame_cached.cache_clear()
        _playable_pool_counts_by_year.cache_clear()
        _get_default_dynasty_lookup.cache_clear()
        _player_identity_by_name.cache_clear()
        _DATA_SOURCE_SIGNATURE = current_signature

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
@asynccontextmanager
async def app_lifespan(_: FastAPI):
    if not os.getenv("PYTEST_CURRENT_TEST") and ENABLE_STARTUP_CALC_PREWARM:
        Thread(target=_prewarm_default_calculation_caches, name="ff-calc-prewarm", daemon=True).start()
    try:
        yield
    finally:
        CALCULATOR_JOB_EXECUTOR.shutdown(wait=False, cancel_futures=True)


app = FastAPI(title="Dynasty Baseball Projections", version="1.0.0", lifespan=app_lifespan)

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


@app.middleware("http")
async def attach_build_header(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-App-Build", APP_BUILD_ID)
    return response

# ---------------------------------------------------------------------------
# API: Metadata
# ---------------------------------------------------------------------------
@app.get("/api/meta")
def get_meta():
    _refresh_data_if_needed()
    payload = dict(META)
    payload["calculator_guardrails"] = _calculator_guardrails_payload()
    with CALCULATOR_PREWARM_LOCK:
        payload["calculator_prewarm"] = dict(CALCULATOR_PREWARM_STATE)
    return payload


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


def _normalize_filter_value(value: str | None) -> str:
    return (value or "").strip()


def _position_sort_key(token: str) -> tuple[int, str]:
    order_map = {pos: idx for idx, pos in enumerate(POSITION_DISPLAY_ORDER)}
    return (order_map.get(token, len(order_map)), token)


def _row_team_value(row: dict) -> str:
    return str(row.get("Team") or row.get("MLBTeam") or "").strip()


def _projection_merge_key(row: dict) -> tuple[str, object, str]:
    player = str(row.get(PLAYER_ENTITY_KEY_COL) or row.get(PLAYER_KEY_COL) or row.get("Player", "")).strip()
    parsed_year = _coerce_record_year(row.get("Year"))
    merge_year: object = parsed_year if parsed_year is not None else str(row.get("Year", "")).strip()
    team = _row_team_value(row).upper()
    return player, merge_year, team


def _merge_position_value(hit_pos: object, pit_pos: object) -> str | None:
    tokens = _position_tokens(hit_pos) | _position_tokens(pit_pos)
    if tokens:
        return "/".join(sorted(tokens, key=_position_sort_key))
    hit_text = str(hit_pos or "").strip()
    if hit_text:
        return hit_text
    pit_text = str(pit_pos or "").strip()
    return pit_text or None


def _max_projection_count(*values: object) -> int | None:
    counts: list[int] = []
    for value in values:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if pd.isna(parsed):
            continue
        counts.append(int(round(parsed)))
    return max(counts) if counts else None


def _oldest_projection_date(*values: object) -> str | None:
    oldest_ts: pd.Timestamp | None = None
    oldest_text: str | None = None

    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            continue
        if oldest_ts is None or parsed < oldest_ts:
            oldest_ts = parsed
            oldest_text = text

    if oldest_text is not None:
        return oldest_text

    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return None


def _normalize_sort_dir(value: str | None) -> Literal["asc", "desc"]:
    return "asc" if str(value or "").strip().lower() == "asc" else "desc"


@lru_cache(maxsize=4)
def _projection_sortable_columns_for_dataset(dataset: Literal["all", "bat", "pitch"]) -> frozenset[str]:
    if dataset == "bat":
        base_records = BAT_DATA
    elif dataset == "pitch":
        base_records = PIT_DATA
    else:
        base_records = list(BAT_DATA) + list(PIT_DATA)

    cols: set[str] = {
        "Player",
        "Team",
        "Pos",
        "Year",
        "Age",
        "ProjectionsUsed",
        "OldestProjectionDate",
        "DynastyValue",
        "DynastyMatchStatus",
        PLAYER_KEY_COL,
        PLAYER_ENTITY_KEY_COL,
    }
    if dataset == "all":
        cols.update({"Type", "PitH", "PitHR", "PitBB"})

    for record in base_records:
        cols.update(record.keys())

    for year in _coerce_meta_years(META):
        cols.add(f"Value_{year}")

    return frozenset(cols)


def _validate_sort_col(sort_col: str | None, *, dataset: Literal["all", "bat", "pitch"]) -> str | None:
    normalized = _normalize_filter_value(sort_col)
    if not normalized:
        return None
    allowed = _projection_sortable_columns_for_dataset(dataset)
    if normalized not in allowed:
        sample = ", ".join(sorted(list(allowed))[:20])
        raise HTTPException(
            status_code=422,
            detail=f"sort_col '{normalized}' is not supported for {dataset}. Example valid columns: {sample}",
        )
    return normalized


def _sort_projection_rows(rows: list[dict], sort_col: str | None, sort_dir: str | None) -> list[dict]:
    col = str(sort_col or "").strip()
    if not col:
        return rows

    direction = _normalize_sort_dir(sort_dir)

    text_cols = PROJECTION_TEXT_SORT_COLS | {PLAYER_KEY_COL, PLAYER_ENTITY_KEY_COL, "DynastyMatchStatus"}

    def _cmp_for_col(a: dict, b: dict, compare_col: str, compare_dir: Literal["asc", "desc"]) -> int:
        av = a.get(compare_col)
        bv = b.get(compare_col)

        if compare_col == "OldestProjectionDate":
            av_ts = pd.to_datetime(av, errors="coerce")
            bv_ts = pd.to_datetime(bv, errors="coerce")
            av_num = float(av_ts.value) if not pd.isna(av_ts) else float("-inf")
            bv_num = float(bv_ts.value) if not pd.isna(bv_ts) else float("-inf")
            if av_num == bv_num:
                return 0
            cmp = -1 if av_num < bv_num else 1
            return cmp if compare_dir == "asc" else -cmp

        if compare_col in text_cols:
            av_text = str(av or "").strip()
            bv_text = str(bv or "").strip()
            if not av_text and not bv_text:
                return 0
            if not av_text:
                return 1
            if not bv_text:
                return -1
            av_norm = av_text.casefold()
            bv_norm = bv_text.casefold()
            if av_norm == bv_norm:
                return 0
            cmp = -1 if av_norm < bv_norm else 1
            return cmp if compare_dir == "asc" else -cmp

        try:
            av_num = float(av)
        except (TypeError, ValueError):
            av_num = float("-inf")
        try:
            bv_num = float(bv)
        except (TypeError, ValueError):
            bv_num = float("-inf")
        if pd.isna(av_num):
            av_num = float("-inf")
        if pd.isna(bv_num):
            bv_num = float("-inf")
        if av_num == bv_num:
            return 0
        cmp = -1 if av_num < bv_num else 1
        return cmp if compare_dir == "asc" else -cmp

    def _cmp(a: dict, b: dict) -> int:
        primary = _cmp_for_col(a, b, col, direction)
        if primary != 0:
            return primary

        # Deterministic tie-breakers keep page boundaries stable across requests.
        for tie_col in (PLAYER_ENTITY_KEY_COL, "Player", "Year", "Team"):
            tie_result = _cmp_for_col(a, b, tie_col, "asc")
            if tie_result != 0:
                return tie_result
        return 0

    return sorted(rows, key=cmp_to_key(_cmp))


def _merge_all_projection_rows(hit_rows: list[dict], pit_rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, object, str], dict[str, dict | None]] = {}
    ordered_keys: list[tuple[str, object, str]] = []

    for side, rows in (("H", hit_rows), ("P", pit_rows)):
        for row in rows:
            key = _projection_merge_key(row)
            if key not in grouped:
                grouped[key] = {"hit": None, "pit": None}
                ordered_keys.append(key)
            if side == "H":
                grouped[key]["hit"] = row
            else:
                grouped[key]["pit"] = row

    merged_rows: list[dict] = []
    for key in ordered_keys:
        bucket = grouped[key]
        hit = bucket.get("hit")
        pit = bucket.get("pit")

        source = hit or pit or {}
        merged = dict(source)

        merged["Type"] = "H/P" if hit and pit else ("H" if hit else "P")
        merged["Team"] = _row_team_value(hit or {}) or _row_team_value(pit or {})
        merged["Pos"] = _merge_position_value((hit or {}).get("Pos"), (pit or {}).get("Pos"))
        merged["Age"] = (hit or {}).get("Age")
        if merged["Age"] is None:
            merged["Age"] = (pit or {}).get("Age")

        max_used = _max_projection_count((hit or {}).get("ProjectionsUsed"), (pit or {}).get("ProjectionsUsed"))
        if max_used is not None:
            merged["ProjectionsUsed"] = max_used
        merged["OldestProjectionDate"] = _oldest_projection_date(
            (hit or {}).get("OldestProjectionDate"),
            (pit or {}).get("OldestProjectionDate"),
        )

        # In the all-rows view, unprefixed hitting fields always represent hitter stats.
        for col in ALL_TAB_HITTER_STAT_COLS:
            merged[col] = (hit or {}).get(col)

        # Pitching fields are kept separately, including prefixed collision stats.
        for col in ALL_TAB_PITCH_STAT_COLS:
            merged[col] = (pit or {}).get(col)
        merged["PitH"] = (pit or {}).get("H")
        merged["PitHR"] = (pit or {}).get("HR")
        merged["PitBB"] = (pit or {}).get("BB")

        merged_rows.append(merged)

    return merged_rows


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


@lru_cache(maxsize=PROJECTION_QUERY_CACHE_MAXSIZE)
def _cached_projection_rows(
    dataset: Literal["bat", "pitch"],
    player: str,
    team: str,
    year: int | None,
    years: str,
    pos: str,
    include_dynasty: bool,
    dynasty_years: str,
    sort_col: str,
    sort_dir: str,
) -> tuple[dict, ...]:
    valid_years = _coerce_meta_years(META)
    requested_years = _resolve_projection_year_filter(year, years or None, valid_years=valid_years)
    records = BAT_DATA if dataset == "bat" else PIT_DATA
    filtered = filter_records(
        records,
        player or None,
        team or None,
        requested_years,
        pos or None,
    )
    if include_dynasty:
        filtered = _attach_dynasty_values(
            filtered,
            _parse_dynasty_years(dynasty_years or None, valid_years=valid_years),
        )
    filtered = _sort_projection_rows(filtered, sort_col or None, sort_dir or None)
    return tuple(filtered)


@lru_cache(maxsize=PROJECTION_QUERY_CACHE_MAXSIZE)
def _cached_all_projection_rows(
    player: str,
    team: str,
    year: int | None,
    years: str,
    pos: str,
    include_dynasty: bool,
    dynasty_years: str,
    sort_col: str,
    sort_dir: str,
) -> tuple[dict, ...]:
    valid_years = _coerce_meta_years(META)
    requested_years = _resolve_projection_year_filter(year, years or None, valid_years=valid_years)
    hit_filtered = filter_records(
        BAT_DATA,
        player or None,
        team or None,
        requested_years,
        None,
    )
    pit_filtered = filter_records(
        PIT_DATA,
        player or None,
        team or None,
        requested_years,
        None,
    )
    merged = _merge_all_projection_rows(hit_filtered, pit_filtered)
    if pos:
        requested_positions = _position_tokens(pos)
        if requested_positions:
            merged = [
                row
                for row in merged
                if requested_positions.intersection(_position_tokens(row.get("Pos", "")))
            ]
    if include_dynasty:
        merged = _attach_dynasty_values(
            merged,
            _parse_dynasty_years(dynasty_years or None, valid_years=valid_years),
        )
    merged = _sort_projection_rows(merged, sort_col or None, sort_dir or None)
    return tuple(merged)


def _get_projection_rows(
    dataset: Literal["bat", "pitch"],
    *,
    player: str | None,
    team: str | None,
    year: int | None,
    years: str | None,
    pos: str | None,
    include_dynasty: bool,
    dynasty_years: str | None,
    sort_col: str | None,
    sort_dir: str | None,
) -> tuple[dict, ...]:
    return _cached_projection_rows(
        dataset,
        _normalize_filter_value(player),
        _normalize_filter_value(team),
        year,
        _normalize_filter_value(years),
        _normalize_filter_value(pos),
        include_dynasty,
        _normalize_filter_value(dynasty_years),
        _normalize_filter_value(sort_col),
        _normalize_sort_dir(sort_dir),
    )


def _get_all_projection_rows(
    *,
    player: str | None,
    team: str | None,
    year: int | None,
    years: str | None,
    pos: str | None,
    include_dynasty: bool,
    dynasty_years: str | None,
    sort_col: str | None,
    sort_dir: str | None,
) -> tuple[dict, ...]:
    return _cached_all_projection_rows(
        _normalize_filter_value(player),
        _normalize_filter_value(team),
        year,
        _normalize_filter_value(years),
        _normalize_filter_value(pos),
        include_dynasty,
        _normalize_filter_value(dynasty_years),
        _normalize_filter_value(sort_col),
        _normalize_sort_dir(sort_dir),
    )


@app.get("/api/version")
def get_version():
    return JSONResponse(
        {
            "build_id": APP_BUILD_ID,
            "commit_sha": DEPLOY_COMMIT_SHA or None,
            "built_at": APP_BUILD_AT,
        },
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/api/projections/all")
def get_all_projections(
    player: Optional[str] = None,
    team: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[str] = None,
    pos: Optional[str] = None,
    dynasty_years: Optional[str] = None,
    include_dynasty: bool = True,
    sort_col: Optional[str] = None,
    sort_dir: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
):
    _refresh_data_if_needed()
    validated_sort_col = _validate_sort_col(sort_col, dataset="all")
    filtered = _get_all_projection_rows(
        player=player,
        team=team,
        year=year,
        years=years,
        pos=pos,
        include_dynasty=include_dynasty,
        dynasty_years=dynasty_years,
        sort_col=validated_sort_col,
        sort_dir=sort_dir,
    )
    total = len(filtered)
    page = list(filtered[offset : offset + limit])
    return {"total": total, "offset": offset, "limit": limit, "data": page}


@app.get("/api/projections/bat")
def get_bat_projections(
    player: Optional[str] = None,
    team: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[str] = None,
    pos: Optional[str] = None,
    dynasty_years: Optional[str] = None,
    include_dynasty: bool = True,
    sort_col: Optional[str] = None,
    sort_dir: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
):
    _refresh_data_if_needed()
    validated_sort_col = _validate_sort_col(sort_col, dataset="bat")
    filtered = _get_projection_rows(
        "bat",
        player=player,
        team=team,
        year=year,
        years=years,
        pos=pos,
        include_dynasty=include_dynasty,
        dynasty_years=dynasty_years,
        sort_col=validated_sort_col,
        sort_dir=sort_dir,
    )
    total = len(filtered)
    page = list(filtered[offset : offset + limit])
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
    sort_col: Optional[str] = None,
    sort_dir: Literal["asc", "desc"] = "desc",
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
):
    _refresh_data_if_needed()
    validated_sort_col = _validate_sort_col(sort_col, dataset="pitch")
    filtered = _get_projection_rows(
        "pitch",
        player=player,
        team=team,
        year=year,
        years=years,
        pos=pos,
        include_dynasty=include_dynasty,
        dynasty_years=dynasty_years,
        sort_col=validated_sort_col,
        sort_dir=sort_dir,
    )
    total = len(filtered)
    page = list(filtered[offset : offset + limit])
    return {"total": total, "offset": offset, "limit": limit, "data": page}


# ---------------------------------------------------------------------------
# API: Dynasty Value Calculator
# ---------------------------------------------------------------------------
class CalculateRequest(BaseModel):
    mode: Literal["common"] = "common"
    teams: int = Field(default=12, ge=2, le=30)
    sims: int = Field(default=300, ge=1, le=5000)
    horizon: int = Field(default=20, ge=1, le=20)
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


def _run_calculate_request(req: CalculateRequest, *, source: str) -> dict:
    started = time.perf_counter()
    settings = req.model_dump()
    cache_before = _calculate_common_dynasty_frame_cached.cache_info()
    status_code = 200

    try:
        _refresh_data_if_needed()
        valid_years = _coerce_meta_years(META)
        if valid_years and req.start_year not in set(valid_years):
            raise HTTPException(
                status_code=422,
                detail=f"start_year must be one of the available projection years: {valid_years}",
            )

        try:
            out = _calculate_common_dynasty_frame_cached(
                teams=req.teams,
                sims=req.sims,
                horizon=req.horizon,
                discount=req.discount,
                bench=req.bench,
                minors=req.minors,
                ip_min=req.ip_min,
                ip_max=req.ip_max,
                start_year=req.start_year,
                recent_projections=req.recent_projections,
            ).copy(deep=True)
        except ValueError as calc_error:
            message = str(calc_error)
            if _is_user_fixable_calculation_error(message):
                raise HTTPException(status_code=422, detail=message) from calc_error
            raise

        identity_by_name = _player_identity_by_name()
        out[PLAYER_KEY_COL] = out["Player"].map(
            lambda player: identity_by_name.get(str(player or "").strip(), (_normalize_player_key(player), None))[0]
        )
        out[PLAYER_ENTITY_KEY_COL] = out["Player"].map(
            lambda player: identity_by_name.get(str(player or "").strip(), (_normalize_player_key(player), None))[1]
        )
        out["DynastyMatchStatus"] = out[PLAYER_ENTITY_KEY_COL].map(
            lambda value: "matched" if value else "no_unique_match"
        )

        # Select output columns
        year_cols = [c for c in out.columns if c.startswith("Value_")]
        cols = [
            "Player", PLAYER_KEY_COL, PLAYER_ENTITY_KEY_COL, "DynastyMatchStatus", "Team", "Pos", "Age",
            "DynastyValue", "RawDynastyValue",
            "minor_eligible",
        ] + year_cols

        available_cols = [c for c in cols if c in out.columns]
        df = out[available_cols].copy()

        # Round for JSON
        for c in df.select_dtypes(include="float").columns:
            df[c] = df[c].round(2)

        records = df.to_dict(orient="records")
        records = _clean_records_for_json(records)

        return {
            "total": len(records),
            "settings": settings,
            "data": records,
        }

    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:
        status_code = 500
        CALC_LOGGER.exception("calculator request failed source=%s", source)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 1)
        cache_after = _calculate_common_dynasty_frame_cached.cache_info()
        cache_event = "none"
        if cache_after.hits > cache_before.hits:
            cache_event = "hit"
        elif cache_after.misses > cache_before.misses:
            cache_event = "miss"

        CALC_LOGGER.info(
            "calculator source=%s status=%s duration_ms=%s cache=%s settings=%s",
            source,
            status_code,
            duration_ms,
            cache_event,
            json.dumps(settings, sort_keys=True),
        )


def _run_calculation_job(job_id: str, req_payload: dict) -> None:
    with CALCULATOR_JOB_LOCK:
        job = CALCULATOR_JOBS.get(job_id)
        if job is None:
            return
        job["status"] = "running"
        job["started_at"] = _iso_now()
        job["updated_at"] = job["started_at"]

    try:
        req = CalculateRequest(**req_payload)
        result = _run_calculate_request(req, source="job")
        with CALCULATOR_JOB_LOCK:
            job = CALCULATOR_JOBS.get(job_id)
            if job is None:
                return
            now = _iso_now()
            job["status"] = "completed"
            job["result"] = result
            job["completed_at"] = now
            job["updated_at"] = now
            job["error"] = None
    except HTTPException as exc:
        with CALCULATOR_JOB_LOCK:
            job = CALCULATOR_JOBS.get(job_id)
            if job is None:
                return
            now = _iso_now()
            job["status"] = "failed"
            job["error"] = {"status_code": exc.status_code, "detail": exc.detail}
            job["completed_at"] = now
            job["updated_at"] = now
            job["result"] = None
    except Exception as exc:
        CALC_LOGGER.exception("calculator job crashed job_id=%s", job_id)
        with CALCULATOR_JOB_LOCK:
            job = CALCULATOR_JOBS.get(job_id)
            if job is None:
                return
            now = _iso_now()
            job["status"] = "failed"
            job["error"] = {"status_code": 500, "detail": str(exc)}
            job["completed_at"] = now
            job["updated_at"] = now
            job["result"] = None
    finally:
        with CALCULATOR_JOB_LOCK:
            _cleanup_calculation_jobs()


@app.post("/api/calculate")
def calculate_dynasty_values(req: CalculateRequest):
    """Run the dynasty value calculator and return results as JSON."""
    return _run_calculate_request(req, source="sync")


@app.post("/api/calculate/jobs", status_code=202)
def create_calculate_dynasty_job(req: CalculateRequest):
    created_at = _iso_now()
    payload = req.model_dump()
    job_id = uuid4().hex
    job = {
        "job_id": job_id,
        "status": "queued",
        "created_at": created_at,
        "started_at": None,
        "completed_at": None,
        "updated_at": created_at,
        "created_ts": time.time(),
        "settings": payload,
        "result": None,
        "error": None,
    }

    with CALCULATOR_JOB_LOCK:
        _cleanup_calculation_jobs(job["created_ts"])
        CALCULATOR_JOBS[job_id] = job

    try:
        CALCULATOR_JOB_EXECUTOR.submit(_run_calculation_job, job_id, payload)
    except RuntimeError as exc:
        with CALCULATOR_JOB_LOCK:
            CALCULATOR_JOBS.pop(job_id, None)
        raise HTTPException(status_code=503, detail="Calculation worker is unavailable.") from exc
    CALC_LOGGER.info("calculator job queued job_id=%s settings=%s", job_id, json.dumps(payload, sort_keys=True))

    return _calculation_job_public_payload(job)


@app.get("/api/calculate/jobs/{job_id}")
def get_calculate_dynasty_job(job_id: str):
    with CALCULATOR_JOB_LOCK:
        _cleanup_calculation_jobs()
        job = CALCULATOR_JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Calculation job not found or expired.")
        return _calculation_job_public_payload(job)


# ---------------------------------------------------------------------------
# Serve frontend
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    INDEX_CACHE_HEADERS = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0",
        "X-App-Build": APP_BUILD_ID,
    }

    @app.get("/")
    def serve_index():
        try:
            html = INDEX_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(status_code=500, detail="Frontend index.html is unavailable") from exc

        if INDEX_BUILD_TOKEN in html:
            html = html.replace(INDEX_BUILD_TOKEN, APP_BUILD_ID)

        return HTMLResponse(content=html, headers=INDEX_CACHE_HEADERS)

    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
