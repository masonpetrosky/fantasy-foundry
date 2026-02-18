"""
FastAPI backend for Dynasty Baseball Projections.

Endpoints:
  GET  /api/meta             → filter options (teams, years, positions)
  GET  /api/projections/all  → merged hitter+pitcher projections (filterable)
  GET  /api/projections/bat  → hitter projections (filterable)
  GET  /api/projections/pitch → pitcher projections (filterable)
  POST /api/calculate        → run dynasty value calculator with custom settings
  DELETE /api/calculate/jobs/{job_id} → cancel an async calculator job
"""

from __future__ import annotations

import logging
import json
import math
import ipaddress
import os
import re
import sys
import time
import traceback
import hashlib
import io
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from functools import cmp_to_key, lru_cache
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Literal, Optional
from uuid import uuid4

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, Field, model_validator

try:  # pragma: no cover - optional dependency
    import redis as redis_lib  # type: ignore
except Exception:  # pragma: no cover - exercised only when redis is unavailable
    redis_lib = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
FRONTEND_DIST_ASSETS_DIR = FRONTEND_DIST_DIR / "assets"
EXCEL_PATH = DATA_DIR / "Dynasty Baseball Projections.xlsx"
DYNASTY_LOOKUP_CACHE_PATH = DATA_DIR / "dynasty_lookup.json"
BACKEND_MODULE_DIR = BASE_DIR / "backend"
INDEX_PATH = FRONTEND_DIST_DIR / "index.html"
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
API_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

# ---------------------------------------------------------------------------
# Load pre-processed JSON data once at startup
# ---------------------------------------------------------------------------
def load_json(name: str):
    p = DATA_DIR / name
    with open(p) as f:
        return json.load(f)


PROJECTION_DATE_COLS = ["ProjectionDate", "Date", "Updated", "LastUpdated", "Timestamp", "Created", "AsOf"]
DERIVED_HIT_RATE_COLS = {"AVG", "OBP", "SLG", "OPS"}
DERIVED_PIT_RATE_COLS = {"ERA", "WHIP"}
TEAM_COL_CANDIDATES = ("Team", "MLBTeam")
YEAR_RANGE_TOKEN_RE = re.compile(r"^(\d{4})\s*-\s*(\d{4})$")
POSITION_TOKEN_SPLIT_RE = re.compile(r"[,\s/]+")
PROJECTION_QUERY_CACHE_MAXSIZE = 256
POSITION_DISPLAY_ORDER = ("C", "1B", "2B", "3B", "SS", "OF", "DH", "UT", "SP", "RP")
ALL_TAB_HITTER_STAT_COLS = ("G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "BB", "SO", "AVG", "OBP", "OPS")
ALL_TAB_PITCH_STAT_COLS = ("GS", "IP", "W", "QS", "L", "K", "SV", "SVH", "ERA", "WHIP", "ER")
PROJECTION_TEXT_SORT_COLS = {"Player", "Team", "Pos", "Type", "Years"}
PLAYER_KEY_COL = "PlayerKey"
PLAYER_ENTITY_KEY_COL = "PlayerEntityKey"
PLAYER_KEY_PATTERN = re.compile(r"[^a-z0-9]+")
COMMON_HITTER_SLOT_DEFAULTS = {
    "C": 1,
    "1B": 1,
    "2B": 1,
    "3B": 1,
    "SS": 1,
    "CI": 1,
    "MI": 1,
    "OF": 5,
    "UT": 1,
}
COMMON_PITCHER_SLOT_DEFAULTS = {
    "P": 9,
    "SP": 0,
    "RP": 0,
}
POINTS_HITTER_SLOT_DEFAULTS = {
    "C": 1,
    "1B": 1,
    "2B": 1,
    "3B": 1,
    "SS": 1,
    "CI": 0,
    "MI": 0,
    "OF": 3,
    "UT": 1,
}
POINTS_PITCHER_SLOT_DEFAULTS = {
    "P": 2,
    "SP": 5,
    "RP": 2,
}
DEFAULT_POINTS_SCORING = {
    "pts_hit_1b": 1.0,
    "pts_hit_2b": 2.0,
    "pts_hit_3b": 3.0,
    "pts_hit_hr": 4.0,
    "pts_hit_r": 1.0,
    "pts_hit_rbi": 1.0,
    "pts_hit_sb": 1.0,
    "pts_hit_bb": 1.0,
    "pts_hit_so": -1.0,
    "pts_pit_ip": 3.0,
    "pts_pit_w": 5.0,
    "pts_pit_l": -5.0,
    "pts_pit_k": 1.0,
    "pts_pit_sv": 5.0,
    "pts_pit_svh": 0.0,
    "pts_pit_h": -1.0,
    "pts_pit_er": -2.0,
    "pts_pit_bb": -1.0,
}
ROTO_HITTER_CATEGORY_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("roto_hit_r", "R", True),
    ("roto_hit_rbi", "RBI", True),
    ("roto_hit_hr", "HR", True),
    ("roto_hit_sb", "SB", True),
    ("roto_hit_avg", "AVG", True),
    ("roto_hit_obp", "OBP", False),
    ("roto_hit_slg", "SLG", False),
    ("roto_hit_ops", "OPS", False),
    ("roto_hit_h", "H", False),
    ("roto_hit_bb", "BB", False),
    ("roto_hit_2b", "2B", False),
    ("roto_hit_tb", "TB", False),
)
ROTO_PITCHER_CATEGORY_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("roto_pit_w", "W", True),
    ("roto_pit_k", "K", True),
    ("roto_pit_sv", "SV", True),
    ("roto_pit_era", "ERA", True),
    ("roto_pit_whip", "WHIP", True),
    ("roto_pit_qs", "QS", False),
    ("roto_pit_svh", "SVH", False),
)
ROTO_CATEGORY_FIELD_DEFAULTS: dict[str, bool] = {
    field_key: bool(default)
    for field_key, _stat_col, default in (
        *ROTO_HITTER_CATEGORY_FIELDS,
        *ROTO_PITCHER_CATEGORY_FIELDS,
    )
}
COMMON_DEFAULT_IR_SLOTS = 0
COMMON_DEFAULT_MINOR_SLOTS = 0
COMMON_HITTER_STARTER_SLOTS_PER_TEAM = sum(COMMON_HITTER_SLOT_DEFAULTS.values())
COMMON_PITCHER_STARTER_SLOTS_PER_TEAM = sum(COMMON_PITCHER_SLOT_DEFAULTS.values())
CALCULATOR_JOB_TTL_SECONDS = max(60, int(os.getenv("FF_CALC_JOB_TTL_SECONDS", "1800")))
CALCULATOR_JOB_MAX_ENTRIES = max(10, int(os.getenv("FF_CALC_JOB_MAX_ENTRIES", "256")))
CALCULATOR_JOB_WORKERS = max(1, int(os.getenv("FF_CALC_JOB_WORKERS", "2")))
ENABLE_STARTUP_CALC_PREWARM = os.getenv("FF_PREWARM_DEFAULT_CALC", "1").strip().lower() not in {"0", "false", "no"}
CALCULATOR_REQUEST_TIMEOUT_SECONDS = max(60, int(os.getenv("FF_CALC_REQUEST_TIMEOUT_SECONDS", "600")))
CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE = max(1, int(os.getenv("FF_CALC_SYNC_RATE_LIMIT_PER_MINUTE", "30")))
CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE = max(1, int(os.getenv("FF_CALC_JOB_CREATE_RATE_LIMIT_PER_MINUTE", "15")))
CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE = max(1, int(os.getenv("FF_CALC_JOB_STATUS_RATE_LIMIT_PER_MINUTE", "240")))
CALCULATOR_MAX_ACTIVE_JOBS_PER_IP = max(1, int(os.getenv("FF_CALC_MAX_ACTIVE_JOBS_PER_IP", "2")))
CALC_RESULT_CACHE_TTL_SECONDS = max(30, int(os.getenv("FF_CALC_RESULT_CACHE_TTL_SECONDS", "1800")))
CALC_RESULT_CACHE_MAX_ENTRIES = max(10, int(os.getenv("FF_CALC_RESULT_CACHE_MAX_ENTRIES", "256")))
TRUST_X_FORWARDED_FOR = os.getenv("FF_TRUST_X_FORWARDED_FOR", "0").strip().lower() in {"1", "true", "yes", "on"}
TRUSTED_PROXY_CIDRS_RAW = os.getenv("FF_TRUSTED_PROXY_CIDRS", "").strip()
REDIS_URL = os.getenv("FF_REDIS_URL", "").strip()
REDIS_RESULT_PREFIX = "ff:calc:result:"
REDIS_JOB_PREFIX = "ff:calc:job:"
CALC_LOGGER = logging.getLogger("fantasy_foundry.calculate")
CALC_JOB_CANCELLED_STATUS = "cancelled"
CALC_JOB_CANCELLED_ERROR = {"status_code": 499, "detail": "Calculation job cancelled by client."}
try:
    RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS = max(
        5.0,
        float(os.getenv("FF_RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS", "60")),
    )
except ValueError:
    RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS = 60.0

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


def _load_trusted_proxy_networks(raw: str) -> tuple[IPNetwork, ...]:
    networks: list[IPNetwork] = []
    for token in raw.split(","):
        candidate = token.strip()
        if not candidate:
            continue
        try:
            if "/" in candidate:
                network = ipaddress.ip_network(candidate, strict=False)
            else:
                addr = ipaddress.ip_address(candidate)
                suffix = "32" if isinstance(addr, ipaddress.IPv4Address) else "128"
                network = ipaddress.ip_network(f"{addr}/{suffix}", strict=False)
        except ValueError:
            CALC_LOGGER.warning("ignoring invalid FF_TRUSTED_PROXY_CIDRS token: %s", candidate)
            continue
        networks.append(network)
    return tuple(networks)


TRUSTED_PROXY_NETWORKS = _load_trusted_proxy_networks(TRUSTED_PROXY_CIDRS_RAW)


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


def _coerce_iso_date_text(value: object) -> str | None:
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


def _projection_freshness_payload(
    bat_rows: list[dict],
    pit_rows: list[dict],
) -> dict[str, object]:
    oldest_date: str | None = None
    newest_date: str | None = None
    rows_with_projection_date = 0
    total_rows = len(bat_rows) + len(pit_rows)

    for row in [*bat_rows, *pit_rows]:
        date_text = _coerce_iso_date_text(row.get("OldestProjectionDate"))
        if not date_text:
            continue
        rows_with_projection_date += 1
        if oldest_date is None or date_text < oldest_date:
            oldest_date = date_text
        if newest_date is None or date_text > newest_date:
            newest_date = date_text

    coverage = (rows_with_projection_date / total_rows * 100.0) if total_rows else 0.0
    return {
        "oldest_projection_date": oldest_date,
        "newest_projection_date": newest_date,
        "rows_with_projection_date": rows_with_projection_date,
        "total_rows": total_rows,
        "date_coverage_pct": round(coverage, 1),
    }


META = load_json("meta.json")
BAT_DATA_RAW = load_json("bat.json")
PIT_DATA_RAW = load_json("pitch.json")
BAT_DATA_RAW, PIT_DATA_RAW = _with_player_identity_keys(BAT_DATA_RAW, PIT_DATA_RAW)
BAT_DATA = _average_recent_projection_rows(BAT_DATA_RAW, max_entries=3, is_hitter=True)
PIT_DATA = _average_recent_projection_rows(PIT_DATA_RAW, max_entries=3, is_hitter=False)
PROJECTION_FRESHNESS = _projection_freshness_payload(BAT_DATA, PIT_DATA)
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
REQUEST_RATE_LIMIT_LOCK = Lock()
REQUEST_RATE_LIMIT_BUCKETS: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_REQUEST_RATE_LIMIT_LAST_SWEEP_TS = 0.0
CALC_RESULT_CACHE_LOCK = Lock()
CALC_RESULT_CACHE: dict[str, tuple[float, dict]] = {}
CALC_RESULT_CACHE_ORDER: deque[str] = deque()
REDIS_CLIENT_LOCK = Lock()
REDIS_CLIENT: Any | None = None
REDIS_CLIENT_INIT_ATTEMPTED = False


def _data_signature_version(signature: tuple[tuple[str, int | None, int | None], ...] | None) -> str:
    payload = json.dumps(signature or (), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def _current_data_version() -> str:
    return _data_signature_version(_DATA_SOURCE_SIGNATURE)


def _coerce_serialized_dynasty_lookup_map(raw: object) -> dict[str, dict]:
    if not isinstance(raw, dict):
        return {}

    cleaned: dict[str, dict] = {}
    for raw_key, raw_values in raw.items():
        key = str(raw_key or "").strip()
        if not key or not isinstance(raw_values, dict):
            continue

        values: dict[str, object] = {}
        for raw_col, raw_value in raw_values.items():
            col = str(raw_col or "").strip()
            if not col:
                continue
            if raw_value is None:
                values[col] = None
                continue
            if isinstance(raw_value, bool):
                values[col] = bool(raw_value)
                continue
            if isinstance(raw_value, (int, float, str)):
                if isinstance(raw_value, float) and not math.isfinite(raw_value):
                    values[col] = None
                else:
                    values[col] = raw_value
                continue
            values[col] = str(raw_value)

        cleaned[key] = values

    return cleaned


def _load_precomputed_default_dynasty_lookup() -> tuple[dict[str, dict], dict[str, dict], set[str], list[str]] | None:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return None
    if not DYNASTY_LOOKUP_CACHE_PATH.exists():
        return None

    try:
        payload = json.loads(DYNASTY_LOOKUP_CACHE_PATH.read_text())
    except Exception:
        CALC_LOGGER.warning(
            "failed to parse precomputed dynasty lookup cache at %s",
            DYNASTY_LOOKUP_CACHE_PATH,
            exc_info=True,
        )
        return None

    if not isinstance(payload, dict):
        return None

    payload_data_version = str(payload.get("data_version") or "").strip()
    current_data_version = _current_data_version()
    if not payload_data_version or payload_data_version != current_data_version:
        return None

    lookup_by_entity = _coerce_serialized_dynasty_lookup_map(payload.get("lookup_by_entity"))
    lookup_by_player_key = _coerce_serialized_dynasty_lookup_map(payload.get("lookup_by_player_key"))
    if not lookup_by_entity and not lookup_by_player_key:
        return None

    raw_ambiguous = payload.get("ambiguous_player_keys")
    ambiguous_player_keys = {
        str(value or "").strip()
        for value in raw_ambiguous
        if str(value or "").strip()
    } if isinstance(raw_ambiguous, list) else set()

    raw_year_cols = payload.get("year_cols")
    year_cols = sorted(
        {
            str(col).strip()
            for col in raw_year_cols
            if isinstance(col, str) and str(col).strip().startswith("Value_")
        } if isinstance(raw_year_cols, list) else set(),
        key=_value_col_sort_key,
    )

    return lookup_by_entity, lookup_by_player_key, ambiguous_player_keys, year_cols


def _reload_projection_data() -> None:
    global META, BAT_DATA_RAW, PIT_DATA_RAW, BAT_DATA, PIT_DATA, PROJECTION_FRESHNESS
    META = load_json("meta.json")
    BAT_DATA_RAW = load_json("bat.json")
    PIT_DATA_RAW = load_json("pitch.json")
    BAT_DATA_RAW, PIT_DATA_RAW = _with_player_identity_keys(BAT_DATA_RAW, PIT_DATA_RAW)
    BAT_DATA = _average_recent_projection_rows(BAT_DATA_RAW, max_entries=3, is_hitter=True)
    PIT_DATA = _average_recent_projection_rows(PIT_DATA_RAW, max_entries=3, is_hitter=False)
    PROJECTION_FRESHNESS = _projection_freshness_payload(BAT_DATA, PIT_DATA)


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


def _parse_ip_text(raw: str | None) -> IPAddress | None:
    text = str(raw or "").strip().strip('"').strip("'")
    if not text:
        return None
    if text.lower().startswith("for="):
        text = text[4:].strip().strip('"').strip("'")
    if "%" in text:
        text = text.split("%", 1)[0]
    if text.startswith("[") and "]" in text:
        text = text[1:text.find("]")]
    elif text.count(":") == 1 and "." in text:
        host, port = text.rsplit(":", 1)
        if port.isdigit():
            text = host
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def _trusted_proxy_ip(addr: IPAddress) -> bool:
    if TRUSTED_PROXY_NETWORKS:
        return any(addr in network for network in TRUSTED_PROXY_NETWORKS)
    return TRUST_X_FORWARDED_FOR


def _forwarded_for_chain(header_value: str | None) -> list[IPAddress]:
    chain: list[IPAddress] = []
    for token in str(header_value or "").split(","):
        parsed = _parse_ip_text(token)
        if parsed is not None:
            chain.append(parsed)
    return chain


def _client_ip(request: Request | None) -> str:
    if request is None:
        return "unknown"
    peer_host = str(request.client.host) if request.client and request.client.host else ""
    peer_ip = _parse_ip_text(peer_host)
    forwarded_chain = _forwarded_for_chain(request.headers.get("x-forwarded-for"))

    if peer_ip is None:
        if forwarded_chain and TRUST_X_FORWARDED_FOR and not TRUSTED_PROXY_NETWORKS:
            return str(forwarded_chain[0])
        return peer_host or "unknown"
    if not forwarded_chain:
        return str(peer_ip)
    if not _trusted_proxy_ip(peer_ip):
        return str(peer_ip)

    # Walk from nearest to farthest hop and return the first untrusted client hop.
    for hop in reversed(forwarded_chain):
        if _trusted_proxy_ip(hop):
            continue
        return str(hop)
    return str(forwarded_chain[0])


def _prune_rate_limit_bucket(bucket: deque[float], *, window_start: float) -> None:
    while bucket and bucket[0] < window_start:
        bucket.popleft()


def _cleanup_rate_limit_buckets_locked(*, now: float, window_start: float) -> None:
    global _REQUEST_RATE_LIMIT_LAST_SWEEP_TS
    if now - _REQUEST_RATE_LIMIT_LAST_SWEEP_TS < RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS:
        return
    for key, bucket in list(REQUEST_RATE_LIMIT_BUCKETS.items()):
        _prune_rate_limit_bucket(bucket, window_start=window_start)
        if not bucket:
            REQUEST_RATE_LIMIT_BUCKETS.pop(key, None)
    _REQUEST_RATE_LIMIT_LAST_SWEEP_TS = now


def _enforce_rate_limit(request: Request, *, action: str, limit_per_minute: int) -> None:
    if limit_per_minute <= 0:
        return
    now = time.time()
    window_start = now - 60.0
    ip = _client_ip(request)
    bucket_key = (action, ip)
    with REQUEST_RATE_LIMIT_LOCK:
        _cleanup_rate_limit_buckets_locked(now=now, window_start=window_start)
        bucket = REQUEST_RATE_LIMIT_BUCKETS[bucket_key]
        _prune_rate_limit_bucket(bucket, window_start=window_start)
        if len(bucket) >= limit_per_minute:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {action}. Try again in a minute.",
            )
        bucket.append(now)


def _active_jobs_for_ip(client_ip: str) -> int:
    count = 0
    for job in CALCULATOR_JOBS.values():
        if str(job.get("client_ip") or "") != client_ip:
            continue
        status = str(job.get("status") or "").lower()
        if status in {"queued", "running"}:
            count += 1
    return count


def _calc_result_cache_key(settings: dict[str, Any]) -> str:
    canonical = json.dumps(settings, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    # v3: points mode now uses per-slot replacement-level valuation
    return f"v3:{digest}"


def _redis_client() -> Any | None:
    global REDIS_CLIENT, REDIS_CLIENT_INIT_ATTEMPTED
    if not REDIS_URL or redis_lib is None:
        return None
    if REDIS_CLIENT_INIT_ATTEMPTED:
        return REDIS_CLIENT
    with REDIS_CLIENT_LOCK:
        if REDIS_CLIENT_INIT_ATTEMPTED:
            return REDIS_CLIENT
        REDIS_CLIENT_INIT_ATTEMPTED = True
        try:
            client = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
            client.ping()
            REDIS_CLIENT = client
            CALC_LOGGER.info("redis cache enabled for calculator results/jobs")
        except Exception:
            REDIS_CLIENT = None
            CALC_LOGGER.warning("redis cache unavailable; falling back to in-memory calculator cache")
        return REDIS_CLIENT


def _cleanup_local_result_cache(now_ts: float | None = None) -> None:
    now = time.time() if now_ts is None else now_ts
    expired = [key for key, (expires_at, _payload) in CALC_RESULT_CACHE.items() if expires_at <= now]
    for key in expired:
        CALC_RESULT_CACHE.pop(key, None)

    if CALC_RESULT_CACHE_ORDER:
        seen: set[str] = set()
        deduped: deque[str] = deque()
        for key in CALC_RESULT_CACHE_ORDER:
            if key in CALC_RESULT_CACHE and key not in seen:
                deduped.append(key)
                seen.add(key)
        CALC_RESULT_CACHE_ORDER.clear()
        CALC_RESULT_CACHE_ORDER.extend(deduped)

    while len(CALC_RESULT_CACHE) > CALC_RESULT_CACHE_MAX_ENTRIES and CALC_RESULT_CACHE_ORDER:
        oldest = CALC_RESULT_CACHE_ORDER.popleft()
        CALC_RESULT_CACHE.pop(oldest, None)


def _touch_local_result_cache_key(cache_key: str) -> None:
    try:
        CALC_RESULT_CACHE_ORDER.remove(cache_key)
    except ValueError:
        pass
    CALC_RESULT_CACHE_ORDER.append(cache_key)


def _result_cache_get(cache_key: str) -> dict | None:
    redis_client = _redis_client()
    if redis_client is not None:
        try:
            raw = redis_client.get(f"{REDIS_RESULT_PREFIX}{cache_key}")
            if raw:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            CALC_LOGGER.warning("failed to read calculator result cache from redis", exc_info=True)

    now = time.time()
    with CALC_RESULT_CACHE_LOCK:
        _cleanup_local_result_cache(now)
        cached = CALC_RESULT_CACHE.get(cache_key)
        if not cached:
            return None
        expires_at, payload = cached
        if expires_at <= now:
            CALC_RESULT_CACHE.pop(cache_key, None)
            return None
        _touch_local_result_cache_key(cache_key)
        return dict(payload)


def _result_cache_set(cache_key: str, payload: dict) -> None:
    redis_client = _redis_client()
    if redis_client is not None:
        try:
            redis_client.setex(
                f"{REDIS_RESULT_PREFIX}{cache_key}",
                CALC_RESULT_CACHE_TTL_SECONDS,
                json.dumps(payload, separators=(",", ":"), sort_keys=True),
            )
        except Exception:
            CALC_LOGGER.warning("failed to write calculator result cache to redis", exc_info=True)

    expires_at = time.time() + CALC_RESULT_CACHE_TTL_SECONDS
    with CALC_RESULT_CACHE_LOCK:
        CALC_RESULT_CACHE[cache_key] = (expires_at, dict(payload))
        _touch_local_result_cache_key(cache_key)
        _cleanup_local_result_cache()


def _cache_calculation_job_snapshot(job: dict) -> None:
    redis_client = _redis_client()
    if redis_client is None:
        return
    try:
        redis_client.setex(
            f"{REDIS_JOB_PREFIX}{job['job_id']}",
            CALCULATOR_JOB_TTL_SECONDS,
            json.dumps(_calculation_job_public_payload(job), separators=(",", ":"), sort_keys=True),
        )
    except Exception:
        CALC_LOGGER.warning("failed to cache calculator job payload in redis", exc_info=True)


def _cached_calculation_job_snapshot(job_id: str) -> dict | None:
    redis_client = _redis_client()
    if redis_client is None:
        return None
    try:
        raw = redis_client.get(f"{REDIS_JOB_PREFIX}{job_id}")
    except Exception:
        CALC_LOGGER.warning("failed to read calculator job payload from redis", exc_info=True)
        return None
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


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
    hit_c: int,
    hit_1b: int,
    hit_2b: int,
    hit_3b: int,
    hit_ss: int,
    hit_ci: int,
    hit_mi: int,
    hit_of: int,
    hit_ut: int,
    pit_p: int,
    pit_sp: int,
    pit_rp: int,
    bench: int,
    minors: int,
    ir: int,
    ip_min: float,
    ip_max: float | None,
    two_way: str,
    start_year: int,
    recent_projections: int,
    **roto_category_settings: bool,
) -> pd.DataFrame:
    _ensure_backend_module_path()
    from dynasty_roto_values import CommonDynastyRotoSettings, calculate_common_dynasty_values

    hitter_categories = [
        stat_col
        for field_key, stat_col, default_value in ROTO_HITTER_CATEGORY_FIELDS
        if _coerce_bool(roto_category_settings.get(field_key), default=bool(default_value))
    ]
    pitcher_categories = [
        stat_col
        for field_key, stat_col, default_value in ROTO_PITCHER_CATEGORY_FIELDS
        if _coerce_bool(roto_category_settings.get(field_key), default=bool(default_value))
    ]

    lg = CommonDynastyRotoSettings(
        n_teams=teams,
        sims_for_sgp=sims,
        horizon_years=horizon,
        discount=discount,
        hitter_slots={
            "C": hit_c,
            "1B": hit_1b,
            "2B": hit_2b,
            "3B": hit_3b,
            "SS": hit_ss,
            "CI": hit_ci,
            "MI": hit_mi,
            "OF": hit_of,
            "UT": hit_ut,
        },
        pitcher_slots={
            "P": pit_p,
            "SP": pit_sp,
            "RP": pit_rp,
        },
        bench_slots=bench,
        minor_slots=minors,
        ir_slots=ir,
        ip_min=ip_min,
        ip_max=ip_max,
        two_way=two_way,
        hitter_categories=tuple(hitter_categories),
        pitcher_categories=tuple(pitcher_categories),
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
    out = _apply_projection_confidence_adjustments(
        out,
        start_year=start_year,
        recent_projections=recent_projections,
    )
    return out


def _stat_or_zero(row: dict | None, key: str) -> float:
    if not row:
        return 0.0
    value = _as_float(row.get(key))
    return value if value is not None else 0.0


def _coerce_minor_eligible(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value > 0
    text = str(value or "").strip().lower()
    return text in {"1", "true", "yes", "y"}


def _projection_identity_key(row: dict | pd.Series) -> str:
    entity_key = str(row.get(PLAYER_ENTITY_KEY_COL) or "").strip()
    if entity_key:
        return entity_key
    player_key = str(row.get(PLAYER_KEY_COL) or "").strip()
    if player_key:
        return player_key
    return _normalize_player_key(row.get("Player"))


def _coerce_bool(value: object, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value != 0
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _roto_category_settings_from_dict(source: dict[str, Any] | None) -> dict[str, bool]:
    settings = source if isinstance(source, dict) else {}
    return {
        field_key: _coerce_bool(settings.get(field_key), default=default_value)
        for field_key, default_value in ROTO_CATEGORY_FIELD_DEFAULTS.items()
    }


def _selected_roto_categories(settings: dict[str, Any]) -> tuple[list[str], list[str]]:
    resolved_settings = _roto_category_settings_from_dict(settings)
    hitter = [
        stat_col
        for field_key, stat_col, _default_value in ROTO_HITTER_CATEGORY_FIELDS
        if resolved_settings.get(field_key, False)
    ]
    pitcher = [
        stat_col
        for field_key, stat_col, _default_value in ROTO_PITCHER_CATEGORY_FIELDS
        if resolved_settings.get(field_key, False)
    ]
    return hitter, pitcher


@lru_cache(maxsize=64)
def _start_year_roto_stats_by_entity(
    *,
    start_year: int,
    recent_projections: int,
) -> dict[str, dict[str, float]]:
    if recent_projections == 3:
        bat_rows = BAT_DATA
        pit_rows = PIT_DATA
    else:
        bat_rows = _average_recent_projection_rows(BAT_DATA_RAW, max_entries=recent_projections, is_hitter=True)
        pit_rows = _average_recent_projection_rows(PIT_DATA_RAW, max_entries=recent_projections, is_hitter=False)

    stats_by_entity: dict[str, dict[str, float]] = {}

    def _merge_rows(rows: list[dict], stat_cols: tuple[str, ...] | list[str]) -> None:
        for row in rows:
            year = _coerce_record_year(row.get("Year"))
            if year != int(start_year):
                continue
            entity_key = _projection_identity_key(row)
            if not entity_key:
                continue
            entry = stats_by_entity.setdefault(entity_key, {})
            for stat_col in stat_cols:
                stat_value = _coerce_numeric(row.get(stat_col))
                if stat_value is None:
                    continue
                entry[stat_col] = float(stat_value)

    _merge_rows(bat_rows, tuple(stat_col for _field_key, stat_col, _default in ROTO_HITTER_CATEGORY_FIELDS))
    _merge_rows(pit_rows, tuple(stat_col for _field_key, stat_col, _default in ROTO_PITCHER_CATEGORY_FIELDS))
    return stats_by_entity


def _build_projection_confidence_context(*, start_year: int, recent_projections: int) -> dict[str, dict[str, object]]:
    if recent_projections == 3:
        bat_rows = BAT_DATA
        pit_rows = PIT_DATA
    else:
        bat_rows = _average_recent_projection_rows(BAT_DATA_RAW, max_entries=recent_projections, is_hitter=True)
        pit_rows = _average_recent_projection_rows(PIT_DATA_RAW, max_entries=recent_projections, is_hitter=False)

    context: dict[str, dict[str, object]] = {}

    def _merge_row(row: dict) -> None:
        year = _coerce_record_year(row.get("Year"))
        if year != int(start_year):
            return

        key = _projection_identity_key(row)
        if not key:
            return

        entry = context.setdefault(
            key,
            {
                "projections_used": None,
                "ab": 0.0,
                "ip": 0.0,
                "pos": None,
            },
        )

        merged_used = _max_projection_count(entry.get("projections_used"), row.get("ProjectionsUsed"))
        if merged_used is not None:
            entry["projections_used"] = int(merged_used)

        ab = _coerce_numeric(row.get("AB")) or 0.0
        ip = _coerce_numeric(row.get("IP")) or 0.0
        entry["ab"] = max(float(entry.get("ab") or 0.0), float(ab))
        entry["ip"] = max(float(entry.get("ip") or 0.0), float(ip))
        entry["pos"] = _merge_position_value(entry.get("pos"), row.get("Pos"))

    for row in bat_rows:
        _merge_row(row)
    for row in pit_rows:
        _merge_row(row)

    return context


def _hitter_playing_time_factor(ab: float) -> float:
    if ab <= 0:
        return 0.68
    if ab < 80:
        return 0.78
    if ab < 180:
        return 0.88
    if ab < 300:
        return 0.94
    return 1.0


def _pitcher_playing_time_factor(ip: float) -> float:
    if ip <= 0:
        return 0.68
    if ip < 30:
        return 0.78
    if ip < 80:
        return 0.88
    if ip < 120:
        return 0.94
    return 1.0


def _projection_playing_time_factor(*, ab: float, ip: float, pos: object) -> float:
    pos_tokens = _position_tokens(pos)
    has_pitcher_flag = bool(pos_tokens & {"P", "SP", "RP"})
    has_hitter_flag = bool(pos_tokens - {"P", "SP", "RP"})

    hit_factor = _hitter_playing_time_factor(ab)
    pit_factor = _pitcher_playing_time_factor(ip)

    has_hit_signal = ab > 0 or has_hitter_flag
    has_pit_signal = ip > 0 or has_pitcher_flag

    if has_hit_signal and has_pit_signal:
        return max(hit_factor, pit_factor)
    if has_pit_signal:
        return pit_factor
    if has_hit_signal:
        return hit_factor
    return 0.82


def _projection_confidence_multiplier(
    row: dict | pd.Series,
    *,
    context_entry: dict[str, object] | None,
    start_year: int,
) -> float:
    used = _coerce_numeric(row.get("ProjectionsUsed"))
    if used is None and context_entry:
        used = _coerce_numeric(context_entry.get("projections_used"))

    # If confidence signals are unavailable, preserve existing values.
    if used is None:
        return 1.0

    projections_used = int(round(used))
    if projections_used >= 3:
        source_factor = 1.0
    elif projections_used == 2:
        source_factor = 0.96
    else:
        source_factor = 0.90

    ab = float(_coerce_numeric((context_entry or {}).get("ab")) or 0.0)
    ip = float(_coerce_numeric((context_entry or {}).get("ip")) or 0.0)
    pos = (context_entry or {}).get("pos") or row.get("Pos")
    playing_time_factor = _projection_playing_time_factor(ab=ab, ip=ip, pos=pos)
    pos_tokens = _position_tokens(pos)
    is_pitcher = ip > 0 or bool(pos_tokens & {"P", "SP", "RP"})

    age = _coerce_numeric(row.get("Age"))
    minor_eligible = _coerce_minor_eligible(row.get("minor_eligible"))
    if minor_eligible and age is not None and age <= 23:
        age_factor = 0.92
    elif minor_eligible and age is not None and age <= 25:
        age_factor = 0.96
    else:
        age_factor = 1.0

    dynasty_value = _coerce_numeric(row.get("DynastyValue"))
    # Keep downside values mostly intact; only add a mild uplift for durable starters
    # who are often under-ranked by replacement-level centering.
    if dynasty_value is not None and dynasty_value <= 0:
        if is_pitcher and projections_used <= 1 and ip >= 120:
            return 0.92
        if is_pitcher and projections_used <= 1 and ip >= 90:
            return 0.96
        return 1.0

    multiplier = source_factor * playing_time_factor * age_factor
    return max(0.55, min(1.0, float(multiplier)))


def _apply_projection_confidence_adjustments(
    df: pd.DataFrame,
    *,
    start_year: int,
    recent_projections: int,
) -> pd.DataFrame:
    if df.empty or "DynastyValue" not in df.columns:
        return df

    value_cols = sorted(
        [col for col in df.columns if isinstance(col, str) and col.startswith("Value_")],
        key=_value_col_sort_key,
    )

    # Only adjust outputs when confidence inputs are actually available.
    if "ProjectionsUsed" not in df.columns and not value_cols:
        return df

    context = _build_projection_confidence_context(
        start_year=int(start_year),
        recent_projections=int(recent_projections),
    )

    out = df.copy(deep=True)
    for idx, row in out.iterrows():
        player_id = _projection_identity_key(row)
        context_entry = context.get(player_id)
        multiplier = _projection_confidence_multiplier(
            row,
            context_entry=context_entry,
            start_year=int(start_year),
        )
        if abs(multiplier - 1.0) < 1e-9:
            continue

        for col in value_cols:
            value = _coerce_numeric(row.get(col))
            if value is not None:
                out.at[idx, col] = float(value) * multiplier

        raw_value = _coerce_numeric(row.get("RawDynastyValue"))
        if raw_value is not None:
            out.at[idx, "RawDynastyValue"] = float(raw_value) * multiplier

        dynasty_value = _coerce_numeric(row.get("DynastyValue"))
        if dynasty_value is not None:
            out.at[idx, "DynastyValue"] = float(dynasty_value) * multiplier

    if "DynastyValue" in out.columns:
        out = out.sort_values(["DynastyValue", "Player"], ascending=[False, True], na_position="last")
    return out


def _valuation_years(start_year: int, horizon: int, valid_years: list[int]) -> list[int]:
    max_year = int(start_year) + max(int(horizon), 1) - 1
    years = [year for year in valid_years if start_year <= year <= max_year]
    if years:
        return years
    return [start_year + offset for offset in range(max(int(horizon), 1))]


def _calculate_hitter_points_breakdown(row: dict | None, scoring: dict[str, float]) -> dict:
    hits = _stat_or_zero(row, "H")
    doubles = _stat_or_zero(row, "2B")
    triples = _stat_or_zero(row, "3B")
    hr = _stat_or_zero(row, "HR")
    singles = max(0.0, hits - doubles - triples - hr)
    inputs = {
        "1B": singles,
        "2B": doubles,
        "3B": triples,
        "HR": hr,
        "R": _stat_or_zero(row, "R"),
        "RBI": _stat_or_zero(row, "RBI"),
        "SB": _stat_or_zero(row, "SB"),
        "BB": _stat_or_zero(row, "BB"),
        "SO": _stat_or_zero(row, "SO"),
    }
    rule_points = {
        "1B": inputs["1B"] * scoring["pts_hit_1b"],
        "2B": inputs["2B"] * scoring["pts_hit_2b"],
        "3B": inputs["3B"] * scoring["pts_hit_3b"],
        "HR": inputs["HR"] * scoring["pts_hit_hr"],
        "R": inputs["R"] * scoring["pts_hit_r"],
        "RBI": inputs["RBI"] * scoring["pts_hit_rbi"],
        "SB": inputs["SB"] * scoring["pts_hit_sb"],
        "BB": inputs["BB"] * scoring["pts_hit_bb"],
        "SO": inputs["SO"] * scoring["pts_hit_so"],
    }
    total_points = float(sum(rule_points.values()))
    return {
        "stats": {key: round(float(value), 4) for key, value in inputs.items()},
        "rule_points": {key: round(float(value), 4) for key, value in rule_points.items()},
        "total_points": round(total_points, 4),
    }


def _calculate_pitcher_points_breakdown(row: dict | None, scoring: dict[str, float]) -> dict:
    inputs = {
        "IP": _stat_or_zero(row, "IP"),
        "W": _stat_or_zero(row, "W"),
        "L": _stat_or_zero(row, "L"),
        "K": _stat_or_zero(row, "K"),
        "SV": _stat_or_zero(row, "SV"),
        "SVH": _stat_or_zero(row, "SVH"),
        "H": _stat_or_zero(row, "H"),
        "ER": _stat_or_zero(row, "ER"),
        "BB": _stat_or_zero(row, "BB"),
    }
    rule_points = {
        "IP": inputs["IP"] * scoring["pts_pit_ip"],
        "W": inputs["W"] * scoring["pts_pit_w"],
        "L": inputs["L"] * scoring["pts_pit_l"],
        "K": inputs["K"] * scoring["pts_pit_k"],
        "SV": inputs["SV"] * scoring["pts_pit_sv"],
        "SVH": inputs["SVH"] * scoring["pts_pit_svh"],
        "H": inputs["H"] * scoring["pts_pit_h"],
        "ER": inputs["ER"] * scoring["pts_pit_er"],
        "BB": inputs["BB"] * scoring["pts_pit_bb"],
    }
    total_points = float(sum(rule_points.values()))
    return {
        "stats": {key: round(float(value), 4) for key, value in inputs.items()},
        "rule_points": {key: round(float(value), 4) for key, value in rule_points.items()},
        "total_points": round(total_points, 4),
    }


def _points_player_identity(row: dict) -> str:
    entity_key = str(row.get(PLAYER_ENTITY_KEY_COL) or "").strip()
    if entity_key:
        return entity_key
    player_key = str(row.get(PLAYER_KEY_COL) or "").strip()
    if player_key:
        return player_key
    return _normalize_player_key(row.get("Player"))


def _points_hitter_eligible_slots(pos_value: object) -> set[str]:
    tokens = _position_tokens(pos_value)
    if not tokens:
        return set()

    aliases = {
        "LF": "OF",
        "CF": "OF",
        "RF": "OF",
        "DH": "UT",
        "UTIL": "UT",
        "U": "UT",
    }
    normalized = {aliases.get(token, token) for token in tokens}

    slots: set[str] = {"UT"}
    if "C" in normalized:
        slots.add("C")
    if "1B" in normalized:
        slots.update({"1B", "CI"})
    if "3B" in normalized:
        slots.update({"3B", "CI"})
    if "2B" in normalized:
        slots.update({"2B", "MI"})
    if "SS" in normalized:
        slots.update({"SS", "MI"})
    if "OF" in normalized:
        slots.add("OF")
    if "CI" in normalized:
        slots.add("CI")
    if "MI" in normalized:
        slots.add("MI")
    return slots


def _points_pitcher_eligible_slots(pos_value: object) -> set[str]:
    tokens = _position_tokens(pos_value)
    if not tokens:
        return set()

    aliases = {
        "RHP": "SP",
        "LHP": "SP",
    }
    normalized = {aliases.get(token, token) for token in tokens}

    slots: set[str] = {"P"}
    if "SP" in normalized:
        slots.add("SP")
    if "RP" in normalized:
        slots.add("RP")
    return slots


def _points_slot_replacement(
    entries: list[dict[str, object]],
    *,
    active_slots: set[str],
    rostered_player_ids: set[str],
    n_replacement: int,
) -> dict[str, float]:
    baselines: dict[str, float] = {}
    top_n = max(int(n_replacement), 1)

    for slot in sorted(active_slots):
        candidate_points: list[float] = []
        for entry in entries:
            player_id = str(entry.get("player_id") or "")
            if not player_id or player_id in rostered_player_ids:
                continue
            slots = entry.get("slots")
            if not isinstance(slots, set) or slot not in slots:
                continue
            points = _as_float(entry.get("points"))
            if points is None:
                continue
            candidate_points.append(points)

        if not candidate_points:
            baselines[slot] = 0.0
            continue

        candidate_points.sort(reverse=True)
        selected = candidate_points[:top_n]
        baselines[slot] = float(sum(selected) / len(selected))

    return baselines


@lru_cache(maxsize=16)
def _calculate_points_dynasty_frame_cached(
    teams: int,
    horizon: int,
    discount: float,
    hit_c: int,
    hit_1b: int,
    hit_2b: int,
    hit_3b: int,
    hit_ss: int,
    hit_ci: int,
    hit_mi: int,
    hit_of: int,
    hit_ut: int,
    pit_p: int,
    pit_sp: int,
    pit_rp: int,
    bench: int,
    minors: int,
    ir: int,
    two_way: str,
    start_year: int,
    recent_projections: int,
    pts_hit_1b: float,
    pts_hit_2b: float,
    pts_hit_3b: float,
    pts_hit_hr: float,
    pts_hit_r: float,
    pts_hit_rbi: float,
    pts_hit_sb: float,
    pts_hit_bb: float,
    pts_hit_so: float,
    pts_pit_ip: float,
    pts_pit_w: float,
    pts_pit_l: float,
    pts_pit_k: float,
    pts_pit_sv: float,
    pts_pit_svh: float,
    pts_pit_h: float,
    pts_pit_er: float,
    pts_pit_bb: float,
) -> pd.DataFrame:
    scoring = {
        "pts_hit_1b": float(pts_hit_1b),
        "pts_hit_2b": float(pts_hit_2b),
        "pts_hit_3b": float(pts_hit_3b),
        "pts_hit_hr": float(pts_hit_hr),
        "pts_hit_r": float(pts_hit_r),
        "pts_hit_rbi": float(pts_hit_rbi),
        "pts_hit_sb": float(pts_hit_sb),
        "pts_hit_bb": float(pts_hit_bb),
        "pts_hit_so": float(pts_hit_so),
        "pts_pit_ip": float(pts_pit_ip),
        "pts_pit_w": float(pts_pit_w),
        "pts_pit_l": float(pts_pit_l),
        "pts_pit_k": float(pts_pit_k),
        "pts_pit_sv": float(pts_pit_sv),
        "pts_pit_svh": float(pts_pit_svh),
        "pts_pit_h": float(pts_pit_h),
        "pts_pit_er": float(pts_pit_er),
        "pts_pit_bb": float(pts_pit_bb),
    }

    if recent_projections == 3:
        bat_rows = BAT_DATA
        pit_rows = PIT_DATA
    else:
        bat_rows = _average_recent_projection_rows(BAT_DATA_RAW, max_entries=recent_projections, is_hitter=True)
        pit_rows = _average_recent_projection_rows(PIT_DATA_RAW, max_entries=recent_projections, is_hitter=False)

    valid_years = _coerce_meta_years(META)
    valuation_years = _valuation_years(start_year, horizon, valid_years)
    year_set = set(valuation_years)

    if not valuation_years:
        raise ValueError("No valuation years available for selected start_year and horizon.")

    rows_by_player: dict[str, dict[int, dict[str, dict | None]]] = {}

    for row in bat_rows:
        year = _coerce_record_year(row.get("Year"))
        if year is None or year not in year_set:
            continue
        player_id = _points_player_identity(row)
        bucket = rows_by_player.setdefault(player_id, {})
        pair = bucket.setdefault(year, {"hit": None, "pit": None})
        pair["hit"] = row

    for row in pit_rows:
        year = _coerce_record_year(row.get("Year"))
        if year is None or year not in year_set:
            continue
        player_id = _points_player_identity(row)
        bucket = rows_by_player.setdefault(player_id, {})
        pair = bucket.setdefault(year, {"hit": None, "pit": None})
        pair["pit"] = row

    roster_slots_per_team = (
        hit_c
        + hit_1b
        + hit_2b
        + hit_3b
        + hit_ss
        + hit_ci
        + hit_mi
        + hit_of
        + hit_ut
        + pit_p
        + pit_sp
        + pit_rp
        + bench
        + minors
        + ir
    )
    replacement_rank = max(1, teams * max(1, roster_slots_per_team))
    hitter_slot_counts = {
        "C": int(hit_c),
        "1B": int(hit_1b),
        "2B": int(hit_2b),
        "3B": int(hit_3b),
        "SS": int(hit_ss),
        "CI": int(hit_ci),
        "MI": int(hit_mi),
        "OF": int(hit_of),
        "UT": int(hit_ut),
    }
    pitcher_slot_counts = {
        "P": int(pit_p),
        "SP": int(pit_sp),
        "RP": int(pit_rp),
    }
    active_hitter_slots = {slot for slot, count in hitter_slot_counts.items() if count > 0}
    active_pitcher_slots = {slot for slot, count in pitcher_slot_counts.items() if count > 0}
    n_replacement = max(int(teams), 1)
    freeze_replacement_baselines = True

    player_meta: dict[str, dict[str, object]] = {}
    per_player_year: dict[str, dict[int, dict[str, object]]] = {}
    year_hit_entries: dict[int, list[dict[str, object]]] = {}
    year_pit_entries: dict[int, list[dict[str, object]]] = {}
    player_raw_totals: dict[str, float] = {}

    for player_id, per_year in rows_by_player.items():
        if not per_year:
            continue

        start_pair = per_year.get(start_year)
        if start_pair and (start_pair.get("hit") or start_pair.get("pit")):
            meta_hit = start_pair.get("hit")
            meta_pit = start_pair.get("pit")
        else:
            first_year = min(per_year.keys())
            fallback_pair = per_year[first_year]
            meta_hit = fallback_pair.get("hit")
            meta_pit = fallback_pair.get("pit")

        meta_row = meta_hit or meta_pit or {}
        player_name = str(meta_row.get("Player") or "").strip()
        player_key = str(meta_row.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(player_name)
        entity_key = str(meta_row.get(PLAYER_ENTITY_KEY_COL) or "").strip() or player_key

        player_meta[player_id] = {
            "Player": player_name,
            "Team": _row_team_value(meta_hit or {}) or _row_team_value(meta_pit or {}),
            "Pos": _merge_position_value((meta_hit or {}).get("Pos"), (meta_pit or {}).get("Pos")),
            "Age": (meta_hit or {}).get("Age") if (meta_hit or {}).get("Age") is not None else (meta_pit or {}).get("Age"),
            "minor_eligible": _coerce_minor_eligible((meta_hit or {}).get("minor_eligible"))
            or _coerce_minor_eligible((meta_pit or {}).get("minor_eligible")),
            PLAYER_KEY_COL: player_key,
            PLAYER_ENTITY_KEY_COL: entity_key,
        }

        year_map: dict[int, dict[str, object]] = {}
        raw_total = 0.0

        for year_offset, year in enumerate(valuation_years):
            pair = per_year.get(year) or {"hit": None, "pit": None}
            hit_row = pair.get("hit")
            pit_row = pair.get("pit")

            hit_breakdown = _calculate_hitter_points_breakdown(hit_row, scoring)
            pit_breakdown = _calculate_pitcher_points_breakdown(pit_row, scoring)
            hit_points = float(hit_breakdown["total_points"])
            pit_points = float(pit_breakdown["total_points"])

            hit_slots = set()
            if isinstance(hit_row, dict) and _stat_or_zero(hit_row, "AB") > 0:
                hit_slots = _points_hitter_eligible_slots(hit_row.get("Pos")) & active_hitter_slots
            pit_slots = set()
            if isinstance(pit_row, dict) and _stat_or_zero(pit_row, "IP") > 0:
                pit_slots = _points_pitcher_eligible_slots(pit_row.get("Pos")) & active_pitcher_slots

            if hit_slots:
                year_hit_entries.setdefault(year, []).append(
                    {"player_id": player_id, "points": hit_points, "slots": set(hit_slots)}
                )
            if pit_slots:
                year_pit_entries.setdefault(year, []).append(
                    {"player_id": player_id, "points": pit_points, "slots": set(pit_slots)}
                )

            selected_raw_points = 0.0
            if hit_slots and pit_slots:
                selected_raw_points = hit_points + pit_points if two_way == "sum" else max(hit_points, pit_points)
            elif hit_slots:
                selected_raw_points = hit_points
            elif pit_slots:
                selected_raw_points = pit_points

            raw_total += selected_raw_points * (float(discount) ** year_offset)

            year_map[year] = {
                "hit_breakdown": hit_breakdown,
                "pit_breakdown": pit_breakdown,
                "hit_points": hit_points,
                "pit_points": pit_points,
                "hit_slots": set(hit_slots),
                "pit_slots": set(pit_slots),
                "selected_raw_points": float(selected_raw_points),
            }

        per_player_year[player_id] = year_map
        player_raw_totals[player_id] = float(raw_total)

    if not player_meta:
        empty_columns = [
            "Player",
            "Team",
            "Pos",
            "Age",
            "DynastyValue",
            "RawDynastyValue",
            "minor_eligible",
            PLAYER_KEY_COL,
            PLAYER_ENTITY_KEY_COL,
        ] + [f"Value_{year}" for year in valuation_years]
        return pd.DataFrame(columns=empty_columns)

    ranked_players = sorted(
        player_raw_totals.items(),
        key=lambda item: (-float(item[1]), str(item[0])),
    )
    rostered_player_ids = {player_id for player_id, _score in ranked_players[:replacement_rank]}

    year_hit_replacement: dict[int, dict[str, float]] = {}
    year_pit_replacement: dict[int, dict[str, float]] = {}
    if freeze_replacement_baselines:
        frozen_hit = _points_slot_replacement(
            year_hit_entries.get(start_year, []),
            active_slots=active_hitter_slots,
            rostered_player_ids=rostered_player_ids,
            n_replacement=n_replacement,
        )
        frozen_pit = _points_slot_replacement(
            year_pit_entries.get(start_year, []),
            active_slots=active_pitcher_slots,
            rostered_player_ids=rostered_player_ids,
            n_replacement=n_replacement,
        )
        for year in valuation_years:
            year_hit_replacement[year] = dict(frozen_hit)
            year_pit_replacement[year] = dict(frozen_pit)
    else:
        for year in valuation_years:
            year_hit_replacement[year] = _points_slot_replacement(
                year_hit_entries.get(year, []),
                active_slots=active_hitter_slots,
                rostered_player_ids=rostered_player_ids,
                n_replacement=n_replacement,
            )
            year_pit_replacement[year] = _points_slot_replacement(
                year_pit_entries.get(year, []),
                active_slots=active_pitcher_slots,
                rostered_player_ids=rostered_player_ids,
                n_replacement=n_replacement,
            )

    result_rows: list[dict] = []
    for player_id, meta in player_meta.items():
        row_out: dict[str, object] = dict(meta)
        row_out["_ExplainPointsByYear"] = {}

        raw_total = 0.0
        for year_offset, year in enumerate(valuation_years):
            info = per_player_year.get(player_id, {}).get(year, {})

            hit_points = float(info.get("hit_points", 0.0))
            pit_points = float(info.get("pit_points", 0.0))
            hit_slots = set(info.get("hit_slots", set()))
            pit_slots = set(info.get("pit_slots", set()))
            hit_breakdown = info.get("hit_breakdown") if isinstance(info.get("hit_breakdown"), dict) else _calculate_hitter_points_breakdown(None, scoring)
            pit_breakdown = info.get("pit_breakdown") if isinstance(info.get("pit_breakdown"), dict) else _calculate_pitcher_points_breakdown(None, scoring)

            hit_repl_map = year_hit_replacement.get(year, {})
            pit_repl_map = year_pit_replacement.get(year, {})

            hit_best_value: float | None = None
            hit_best_slot: str | None = None
            hit_best_replacement: float | None = None
            for slot in sorted(hit_slots):
                replacement_points = float(hit_repl_map.get(slot, 0.0))
                value = hit_points - replacement_points
                if hit_best_value is None or value > hit_best_value:
                    hit_best_value = float(value)
                    hit_best_slot = slot
                    hit_best_replacement = replacement_points

            pit_best_value: float | None = None
            pit_best_slot: str | None = None
            pit_best_replacement: float | None = None
            for slot in sorted(pit_slots):
                replacement_points = float(pit_repl_map.get(slot, 0.0))
                value = pit_points - replacement_points
                if pit_best_value is None or value > pit_best_value:
                    pit_best_value = float(value)
                    pit_best_slot = slot
                    pit_best_replacement = replacement_points

            selected_raw_points = 0.0
            if hit_best_value is not None and pit_best_value is not None:
                if two_way == "sum":
                    year_points = hit_best_value + pit_best_value
                    selected_raw_points = hit_points + pit_points
                elif hit_best_value >= pit_best_value:
                    year_points = hit_best_value
                    selected_raw_points = hit_points
                else:
                    year_points = pit_best_value
                    selected_raw_points = pit_points
            elif hit_best_value is not None:
                year_points = hit_best_value
                selected_raw_points = hit_points
            elif pit_best_value is not None:
                year_points = pit_best_value
                selected_raw_points = pit_points
            else:
                year_points = 0.0
                selected_raw_points = 0.0

            row_out[f"Value_{year}"] = year_points
            discount_factor = float(discount) ** year_offset
            discounted_value = year_points * discount_factor
            raw_total += discounted_value
            row_out["_ExplainPointsByYear"][str(year)] = {
                "hitting_points": round(hit_points, 4),
                "pitching_points": round(pit_points, 4),
                "hitting_replacement": round(float(hit_best_replacement), 4) if hit_best_replacement is not None else None,
                "pitching_replacement": round(float(pit_best_replacement), 4) if pit_best_replacement is not None else None,
                "hitting_best_slot": hit_best_slot,
                "pitching_best_slot": pit_best_slot,
                "hitting_value": round(float(hit_best_value), 4) if hit_best_value is not None else None,
                "pitching_value": round(float(pit_best_value), 4) if pit_best_value is not None else None,
                "selected_raw_points": round(float(selected_raw_points), 4),
                "selected_points": round(float(year_points), 4),
                "discount_factor": round(float(discount_factor), 6),
                "discounted_contribution": round(float(discounted_value), 4),
                "hitting": hit_breakdown,
                "pitching": pit_breakdown,
            }

        row_out["RawDynastyValue"] = float(raw_total)
        result_rows.append(row_out)

    if not result_rows:
        empty_columns = [
            "Player",
            "Team",
            "Pos",
            "Age",
            "DynastyValue",
            "RawDynastyValue",
            "minor_eligible",
            PLAYER_KEY_COL,
            PLAYER_ENTITY_KEY_COL,
        ] + [f"Value_{year}" for year in valuation_years]
        return pd.DataFrame(columns=empty_columns)

    sorted_raw_values = sorted((float(row["RawDynastyValue"]) for row in result_rows), reverse=True)
    cutoff_idx = min(replacement_rank - 1, len(sorted_raw_values) - 1)
    replacement_raw = sorted_raw_values[cutoff_idx]

    for row in result_rows:
        row["DynastyValue"] = float(row["RawDynastyValue"]) - replacement_raw

    df = pd.DataFrame.from_records(result_rows)
    df = _apply_projection_confidence_adjustments(
        df,
        start_year=start_year,
        recent_projections=recent_projections,
    )
    return df


def _is_user_fixable_calculation_error(message: str) -> bool:
    normalized = message.lower()
    return (
        "not enough players" in normalized
        or "no valuation years available" in normalized
        or "cannot fill slot" in normalized
        or "to fill required slots" in normalized
    )


def _numeric_or_zero(value: object) -> float:
    parsed = _as_float(value)
    return float(parsed) if parsed is not None else 0.0


def _build_calculation_explanations(out: pd.DataFrame, *, settings: dict[str, Any]) -> dict[str, dict]:
    scoring_mode = str(settings.get("scoring_mode") or "roto").strip().lower() or "roto"
    discount = _numeric_or_zero(settings.get("discount")) or 1.0
    year_cols = sorted(
        [col for col in out.columns if isinstance(col, str) and col.startswith("Value_")],
        key=_value_col_sort_key,
    )
    explanations: dict[str, dict] = {}

    for _, row in out.iterrows():
        row_data = row.to_dict()
        player = str(row_data.get("Player") or "").strip()
        player_key = str(row_data.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(player)
        entity_key = str(row_data.get(PLAYER_ENTITY_KEY_COL) or "").strip() or player_key
        explain_key = entity_key or player_key
        points_by_year = row_data.get("_ExplainPointsByYear")
        points_by_year = points_by_year if isinstance(points_by_year, dict) else {}

        per_year: list[dict] = []
        for idx, year_col in enumerate(year_cols):
            suffix = year_col.split("_", 1)[1] if "_" in year_col else year_col
            year_token: int | str = int(suffix) if str(suffix).isdigit() else suffix
            year_value = _numeric_or_zero(row_data.get(year_col))
            discount_factor = float(discount) ** idx
            discounted = year_value * discount_factor

            year_entry: dict[str, Any] = {
                "year": year_token,
                "year_value": round(year_value, 4),
                "discount_factor": round(discount_factor, 6),
                "discounted_contribution": round(discounted, 4),
            }
            if scoring_mode == "points":
                points_detail = points_by_year.get(str(year_token))
                if isinstance(points_detail, dict):
                    year_entry["points"] = points_detail
            per_year.append(year_entry)

        explanations[explain_key] = {
            "player": player,
            "team": str(row_data.get("Team") or "").strip() or None,
            "pos": str(row_data.get("Pos") or "").strip() or None,
            "mode": scoring_mode,
            "dynasty_value": round(_numeric_or_zero(row_data.get("DynastyValue")), 4),
            "raw_dynasty_value": round(_numeric_or_zero(row_data.get("RawDynastyValue")), 4),
            "per_year": per_year,
        }

    return explanations


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


def _flatten_explanations_for_export(explanations: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for player_id, detail in explanations.items():
        if not isinstance(detail, dict):
            continue
        per_year = detail.get("per_year")
        if not isinstance(per_year, list):
            continue
        for entry in per_year:
            if not isinstance(entry, dict):
                continue
            points = entry.get("points")
            points = points if isinstance(points, dict) else {}
            rows.append(
                {
                    "PlayerEntityKey": player_id,
                    "Player": detail.get("player"),
                    "Team": detail.get("team"),
                    "Pos": detail.get("pos"),
                    "Mode": detail.get("mode"),
                    "Year": entry.get("year"),
                    "YearValue": entry.get("year_value"),
                    "DiscountFactor": entry.get("discount_factor"),
                    "DiscountedContribution": entry.get("discounted_contribution"),
                    "HittingPoints": points.get("hitting_points"),
                    "PitchingPoints": points.get("pitching_points"),
                    "SelectedPoints": points.get("selected_points"),
                    "HittingRulePoints": json.dumps((points.get("hitting") or {}).get("rule_points", {}), sort_keys=True),
                    "PitchingRulePoints": json.dumps((points.get("pitching") or {}).get("rule_points", {}), sort_keys=True),
                }
            )
    return rows


def _tabular_export_response(
    rows: list[dict],
    *,
    filename_base: str,
    file_format: Literal["csv", "xlsx"],
    explain_rows: list[dict] | None = None,
) -> StreamingResponse:
    if file_format == "csv":
        df = pd.DataFrame.from_records(rows)
        payload = df.to_csv(index=False).encode("utf-8")
        content_type = "text/csv; charset=utf-8"
        extension = "csv"
    else:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame.from_records(rows).to_excel(writer, index=False, sheet_name="Data")
            if explain_rows:
                pd.DataFrame.from_records(explain_rows).to_excel(
                    writer,
                    index=False,
                    sheet_name="Explainability",
                )
        payload = output.getvalue()
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        extension = "xlsx"

    response = StreamingResponse(io.BytesIO(payload), media_type=content_type)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename_base}.{extension}"'
    return response


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


def _default_calculation_cache_params() -> dict[str, int | float | str | None]:
    years = _coerce_meta_years(META)
    start_year = years[0] if years else 2026
    horizon = len(years) if years else 10
    params: dict[str, int | float | str | None] = {
        "teams": 12,
        "sims": 300,
        "horizon": horizon,
        "discount": 0.94,
        "hit_c": COMMON_HITTER_SLOT_DEFAULTS["C"],
        "hit_1b": COMMON_HITTER_SLOT_DEFAULTS["1B"],
        "hit_2b": COMMON_HITTER_SLOT_DEFAULTS["2B"],
        "hit_3b": COMMON_HITTER_SLOT_DEFAULTS["3B"],
        "hit_ss": COMMON_HITTER_SLOT_DEFAULTS["SS"],
        "hit_ci": COMMON_HITTER_SLOT_DEFAULTS["CI"],
        "hit_mi": COMMON_HITTER_SLOT_DEFAULTS["MI"],
        "hit_of": COMMON_HITTER_SLOT_DEFAULTS["OF"],
        "hit_ut": COMMON_HITTER_SLOT_DEFAULTS["UT"],
        "pit_p": COMMON_PITCHER_SLOT_DEFAULTS["P"],
        "pit_sp": COMMON_PITCHER_SLOT_DEFAULTS["SP"],
        "pit_rp": COMMON_PITCHER_SLOT_DEFAULTS["RP"],
        "bench": 6,
        "minors": COMMON_DEFAULT_MINOR_SLOTS,
        "ir": COMMON_DEFAULT_IR_SLOTS,
        "ip_min": 0.0,
        "ip_max": None,
        "two_way": "sum",
        "start_year": start_year,
        "recent_projections": 3,
    }
    params.update(ROTO_CATEGORY_FIELD_DEFAULTS)
    return params


def _calculator_guardrails_payload() -> dict:
    return {
        "hitters_per_team": COMMON_HITTER_STARTER_SLOTS_PER_TEAM,
        "pitchers_per_team": COMMON_PITCHER_STARTER_SLOTS_PER_TEAM,
        "default_hitter_slots": COMMON_HITTER_SLOT_DEFAULTS.copy(),
        "default_pitcher_slots": COMMON_PITCHER_SLOT_DEFAULTS.copy(),
        "default_points_hitter_slots": POINTS_HITTER_SLOT_DEFAULTS.copy(),
        "default_points_pitcher_slots": POINTS_PITCHER_SLOT_DEFAULTS.copy(),
        "default_points_scoring": DEFAULT_POINTS_SCORING.copy(),
        "default_roto_hitter_categories": [label for _key, label, _default in ROTO_HITTER_CATEGORY_FIELDS],
        "default_roto_pitcher_categories": [label for _key, label, _default in ROTO_PITCHER_CATEGORY_FIELDS],
        "default_minors_slots": COMMON_DEFAULT_MINOR_SLOTS,
        "default_ir_slots": COMMON_DEFAULT_IR_SLOTS,
        "playable_by_year": _playable_pool_counts_by_year(),
        "job_timeout_seconds": CALCULATOR_REQUEST_TIMEOUT_SECONDS,
        "rate_limit_identity_mode": (
            "trusted_proxy_cidrs"
            if TRUSTED_PROXY_NETWORKS
            else ("trust_all_x_forwarded_for" if TRUST_X_FORWARDED_FOR else "remote_addr_only")
        ),
        "trust_x_forwarded_for": TRUST_X_FORWARDED_FOR,
        "trusted_proxy_cidrs": [str(network) for network in TRUSTED_PROXY_NETWORKS],
        "rate_limit_bucket_cleanup_interval_seconds": RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS,
        "rate_limit_sync_per_minute": CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE,
        "rate_limit_job_create_per_minute": CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE,
        "rate_limit_job_status_per_minute": CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE,
        "max_active_jobs_per_ip": CALCULATOR_MAX_ACTIVE_JOBS_PER_IP,
    }


def _iso_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _mark_job_cancelled_locked(job: dict, *, now: str | None = None) -> None:
    timestamp = now or _iso_now()
    job["status"] = CALC_JOB_CANCELLED_STATUS
    job["cancel_requested"] = True
    job["result"] = None
    job["error"] = dict(CALC_JOB_CANCELLED_ERROR)
    job["completed_at"] = job.get("completed_at") or timestamp
    job["updated_at"] = timestamp


def _cleanup_calculation_jobs(now_ts: float | None = None) -> None:
    current = time.time() if now_ts is None else now_ts
    expired_ids: list[str] = []
    completed: list[tuple[str, float]] = []

    for job_id, job in CALCULATOR_JOBS.items():
        status = str(job.get("status") or "").lower()
        created_ts = float(job.get("created_ts") or current)
        age = current - created_ts
        if status in {"completed", "failed", CALC_JOB_CANCELLED_STATUS} and age > CALCULATOR_JOB_TTL_SECONDS:
            expired_ids.append(job_id)
        elif status in {"completed", "failed", CALC_JOB_CANCELLED_STATUS}:
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
    status = str(job.get("status") or "").lower()
    payload = {
        "job_id": job["job_id"],
        "status": status,
        "created_at": job["created_at"],
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "settings": job.get("settings"),
    }
    if status == "completed":
        payload["result"] = job.get("result")
    elif status in {"failed", CALC_JOB_CANCELLED_STATUS}:
        payload["error"] = job.get("error")
    elif status == "queued":
        queued_jobs = [
            candidate
            for candidate in CALCULATOR_JOBS.values()
            if str(candidate.get("status") or "").lower() == "queued"
        ]
        queued_jobs.sort(key=lambda candidate: float(candidate.get("created_ts") or 0.0))
        payload["queued_jobs"] = len(queued_jobs)
        payload["running_jobs"] = sum(
            1
            for candidate in CALCULATOR_JOBS.values()
            if str(candidate.get("status") or "").lower() == "running"
        )
        payload["queue_position"] = None
        for idx, candidate in enumerate(queued_jobs, start=1):
            if str(candidate.get("job_id") or "") == str(job.get("job_id") or ""):
                payload["queue_position"] = idx
                break
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
            ip_max=float(ip_max) if ip_max is not None else None,
            two_way=str(params["two_way"]),
            start_year=int(params["start_year"]),
            recent_projections=int(params["recent_projections"]),
            **_roto_category_settings_from_dict(params),
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
    precomputed_lookup = _load_precomputed_default_dynasty_lookup()
    if precomputed_lookup is not None:
        return precomputed_lookup

    try:
        params = _default_calculation_cache_params()

        out = _calculate_common_dynasty_frame_cached(
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
            recent_projections=int(params["recent_projections"]),
            **_roto_category_settings_from_dict(params),
        ).copy(deep=True)

        year_cols = sorted(
            [c for c in out.columns if isinstance(c, str) and c.startswith("Value_")],
            key=_value_col_sort_key,
        )
        keep_cols = [c for c in ["Player", "Team", "DynastyValue"] + year_cols if c in out.columns]
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
                if pd.isna(value):
                    cleaned[key] = None
                else:
                    cleaned[key] = value
            team_key = _normalize_team_key(row.get("Team")).lower()
            lookup_candidates_by_name.setdefault(player, []).append(
                {
                    "team_key": team_key,
                    "values": cleaned,
                }
            )

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

        def _candidate_values_for_record(
            record: dict,
            candidates: list[dict[str, object]],
            *,
            require_team_match: bool,
        ) -> dict | None:
            if not candidates:
                return None

            record_team_key = _normalize_team_key(record.get("Team") or record.get("MLBTeam")).lower()
            if require_team_match:
                if record_team_key:
                    team_matches = [c for c in candidates if str(c.get("team_key") or "") == record_team_key]
                    if len(team_matches) == 1:
                        return team_matches[0].get("values") if isinstance(team_matches[0].get("values"), dict) else None
                    return None
                return candidates[0].get("values") if len(candidates) == 1 and isinstance(candidates[0].get("values"), dict) else None

            if record_team_key:
                team_matches = [c for c in candidates if str(c.get("team_key") or "") == record_team_key]
                if len(team_matches) == 1:
                    return team_matches[0].get("values") if isinstance(team_matches[0].get("values"), dict) else None
            return candidates[0].get("values") if len(candidates) == 1 and isinstance(candidates[0].get("values"), dict) else None

        lookup_by_entity: dict[str, dict] = {}
        lookup_by_player_key: dict[str, dict] = {}
        for record in combined_records:
            player_name = str(record.get("Player", "")).strip()
            if not player_name:
                continue

            player_key = str(record.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(player_name)
            entity_key = str(record.get(PLAYER_ENTITY_KEY_COL) or "").strip() or player_key
            player_values = _candidate_values_for_record(
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
        _calculate_points_dynasty_frame_cached.cache_clear()
        _playable_pool_counts_by_year.cache_clear()
        _get_default_dynasty_lookup.cache_clear()
        _player_identity_by_name.cache_clear()
        _start_year_roto_stats_by_entity.cache_clear()
        with CALC_RESULT_CACHE_LOCK:
            CALC_RESULT_CACHE.clear()
            CALC_RESULT_CACHE_ORDER.clear()
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
    if request.url.path.startswith("/api/"):
        _refresh_data_if_needed()
    response = await call_next(request)
    response.headers.setdefault("X-App-Build", APP_BUILD_ID)
    response.headers.setdefault("X-Data-Version", _current_data_version())
    if request.url.path.startswith("/api/"):
        for header, value in API_NO_CACHE_HEADERS.items():
            response.headers.setdefault(header, value)
    return response

# ---------------------------------------------------------------------------
# API: Metadata
# ---------------------------------------------------------------------------
def _meta_payload() -> dict[str, Any]:
    payload = dict(META)
    payload["calculator_guardrails"] = _calculator_guardrails_payload()
    payload["projection_freshness"] = dict(PROJECTION_FRESHNESS)
    with CALCULATOR_PREWARM_LOCK:
        payload["calculator_prewarm"] = dict(CALCULATOR_PREWARM_STATE)
    return payload


@app.get("/api/meta")
def get_meta(request: Request):
    _refresh_data_if_needed()
    payload = _meta_payload()
    headers = dict(API_NO_CACHE_HEADERS)
    etag = _payload_etag(payload)
    headers["ETag"] = etag
    if _etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(payload, headers=headers)


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


def _normalize_player_keys_filter(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    tokens = sorted({token.strip().lower() for token in re.split(r"[\s,]+", text) if token.strip()})
    return ",".join(tokens)


def _parse_player_keys_filter(value: str | None) -> set[str] | None:
    normalized = _normalize_player_keys_filter(value)
    if not normalized:
        return None
    return {token for token in normalized.split(",") if token}


def _row_player_filter_keys(row: dict) -> set[str]:
    keys: set[str] = set()
    entity_key = str(row.get(PLAYER_ENTITY_KEY_COL) or "").strip().lower()
    if entity_key:
        keys.add(entity_key)
    player_key = str(row.get(PLAYER_KEY_COL) or "").strip().lower()
    if player_key:
        keys.add(player_key)
    return keys


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


def _coerce_numeric(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _career_group_key(row: dict) -> str:
    player_name = str(row.get("Player", "")).strip()
    player_key = str(row.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(player_name)
    return str(row.get(PLAYER_ENTITY_KEY_COL) or "").strip() or player_key


def _rows_year_bounds(rows: list[dict]) -> tuple[int | None, int | None]:
    years: list[int] = []
    for row in rows:
        parsed = _coerce_record_year(row.get("Year"))
        if parsed is not None:
            years.append(parsed)
    if not years:
        return None, None
    return min(years), max(years)


def _format_year_span(start_year: int | None, end_year: int | None) -> str | None:
    if start_year is None or end_year is None:
        return None
    return str(start_year) if start_year == end_year else f"{start_year}-{end_year}"


def _sum_projection_counts(values: list[object]) -> int | None:
    total = 0
    found = False
    for value in values:
        parsed = _coerce_numeric(value)
        if parsed is None:
            continue
        total += int(round(parsed))
        found = True
    return total if found else None


def _weighted_rate(rows: list[dict], rate_col: str, weight_col: str) -> float | None:
    weighted_total = 0.0
    weight_total = 0.0
    for row in rows:
        rate = _coerce_numeric(row.get(rate_col))
        weight = _coerce_numeric(row.get(weight_col))
        if rate is None or weight is None or weight <= 0:
            continue
        weighted_total += rate * weight
        weight_total += weight
    if weight_total <= 0:
        return None
    return weighted_total / weight_total


def _aggregate_projection_career_rows(rows: list[dict], *, is_hitter: bool) -> list[dict]:
    if not rows:
        return []

    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(_career_group_key(row), []).append(row)

    excluded_from_sum = {
        "Player",
        "Team",
        "MLBTeam",
        "Pos",
        "Type",
        "Year",
        "Age",
        "ProjectionsUsed",
        "OldestProjectionDate",
        "DynastyValue",
        "DynastyMatchStatus",
        "Years",
        "YearStart",
        "YearEnd",
        PLAYER_KEY_COL,
        PLAYER_ENTITY_KEY_COL,
    }

    aggregated_rows: list[dict] = []
    for entity_key, player_rows in grouped.items():
        latest_row = player_rows[0]
        latest_year = _coerce_record_year(latest_row.get("Year"))
        for row in player_rows[1:]:
            row_year = _coerce_record_year(row.get("Year"))
            if row_year is None and latest_year is None:
                latest_row = row
                continue
            if row_year is None:
                continue
            if latest_year is None or row_year >= latest_year:
                latest_row = row
                latest_year = row_year

        aggregated = dict(latest_row)
        player_name = str(latest_row.get("Player", "")).strip()
        player_key = str(latest_row.get(PLAYER_KEY_COL) or "").strip() or _normalize_player_key(player_name)
        aggregated[PLAYER_KEY_COL] = player_key
        aggregated[PLAYER_ENTITY_KEY_COL] = entity_key or player_key

        team_value = _row_team_value(latest_row)
        if not team_value:
            for row in player_rows:
                team_value = _row_team_value(row)
                if team_value:
                    break
        if team_value:
            aggregated["Team"] = team_value

        position_tokens: set[str] = set()
        for row in player_rows:
            position_tokens.update(_position_tokens(row.get("Pos")))
        if position_tokens:
            aggregated["Pos"] = "/".join(sorted(position_tokens, key=_position_sort_key))

        ages = [age for age in (_coerce_numeric(row.get("Age")) for row in player_rows) if age is not None]
        if ages:
            aggregated["Age"] = int(round(min(ages)))

        year_start, year_end = _rows_year_bounds(player_rows)
        aggregated["Year"] = None
        aggregated["YearStart"] = year_start
        aggregated["YearEnd"] = year_end
        aggregated["Years"] = _format_year_span(year_start, year_end)

        # In career totals mode, ProjectionsUsed should represent the number of
        # projection queries behind each season snapshot (e.g., 1-3), not a sum
        # across every projected year.
        projection_count = _max_projection_count(*(row.get("ProjectionsUsed") for row in player_rows))
        if projection_count is not None:
            aggregated["ProjectionsUsed"] = projection_count
        aggregated["OldestProjectionDate"] = _oldest_projection_date(
            *(row.get("OldestProjectionDate") for row in player_rows)
        )

        stat_totals: dict[str, float] = {}
        for row in player_rows:
            for key, value in row.items():
                if key in excluded_from_sum or key.startswith("Value_"):
                    continue
                numeric = _coerce_numeric(value)
                if numeric is None:
                    continue
                stat_totals[key] = stat_totals.get(key, 0.0) + numeric

        for key, value in stat_totals.items():
            aggregated[key] = value

        if is_hitter:
            h = _coerce_numeric(aggregated.get("H"))
            ab = _coerce_numeric(aggregated.get("AB"))
            if h is not None and ab is not None and ab > 0:
                aggregated["AVG"] = h / ab
            else:
                weighted_avg = _weighted_rate(player_rows, "AVG", "AB")
                if weighted_avg is not None:
                    aggregated["AVG"] = weighted_avg

            b2 = _coerce_numeric(aggregated.get("2B"))
            b3 = _coerce_numeric(aggregated.get("3B"))
            hr = _coerce_numeric(aggregated.get("HR"))
            bb = _coerce_numeric(aggregated.get("BB"))
            hbp = _coerce_numeric(aggregated.get("HBP"))
            sf = _coerce_numeric(aggregated.get("SF"))
            if (
                h is not None
                and b2 is not None
                and b3 is not None
                and hr is not None
                and bb is not None
                and hbp is not None
                and ab is not None
                and sf is not None
                and ab > 0
            ):
                tb = h + b2 + 2.0 * b3 + 3.0 * hr
                obp_den = ab + bb + hbp + sf
                if obp_den > 0:
                    obp = (h + bb + hbp) / obp_den
                    slg = tb / ab
                    aggregated["OBP"] = obp
                    aggregated["OPS"] = obp + slg
                else:
                    weighted_obp = _weighted_rate(player_rows, "OBP", "AB")
                    if weighted_obp is not None:
                        aggregated["OBP"] = weighted_obp
            else:
                weighted_obp = _weighted_rate(player_rows, "OBP", "AB")
                if weighted_obp is not None:
                    aggregated["OBP"] = weighted_obp
                weighted_ops = _weighted_rate(player_rows, "OPS", "AB")
                if weighted_ops is not None:
                    aggregated["OPS"] = weighted_ops
        else:
            svh = _coerce_numeric(aggregated.get("SVH"))
            if svh is None:
                sv = _coerce_numeric(aggregated.get("SV"))
                hld = _coerce_numeric(aggregated.get("HLD"))
                if sv is not None and hld is not None:
                    aggregated["SVH"] = sv + hld
                elif sv is not None:
                    aggregated["SVH"] = sv

            qs = _coerce_numeric(aggregated.get("QS"))
            if qs is None:
                qa3 = _coerce_numeric(aggregated.get("QA3"))
                if qa3 is not None:
                    aggregated["QS"] = qa3

            er = _coerce_numeric(aggregated.get("ER"))
            ip = _coerce_numeric(aggregated.get("IP"))
            if er is not None and ip is not None and ip > 0:
                aggregated["ERA"] = (9.0 * er) / ip
            else:
                weighted_era = _weighted_rate(player_rows, "ERA", "IP")
                if weighted_era is not None:
                    aggregated["ERA"] = weighted_era

            h = _coerce_numeric(aggregated.get("H"))
            bb = _coerce_numeric(aggregated.get("BB"))
            if h is not None and bb is not None and ip is not None and ip > 0:
                aggregated["WHIP"] = (h + bb) / ip
            else:
                weighted_whip = _weighted_rate(player_rows, "WHIP", "IP")
                if weighted_whip is not None:
                    aggregated["WHIP"] = weighted_whip

        aggregated_rows.append(aggregated)

    return aggregated_rows


def _aggregate_all_projection_career_rows(hit_rows: list[dict], pit_rows: list[dict]) -> list[dict]:
    if not hit_rows and not pit_rows:
        return []

    hit_aggregated = _aggregate_projection_career_rows(hit_rows, is_hitter=True)
    pit_aggregated = _aggregate_projection_career_rows(pit_rows, is_hitter=False)

    hit_by_key = {_career_group_key(row): row for row in hit_aggregated}
    pit_by_key = {_career_group_key(row): row for row in pit_aggregated}

    ordered_keys: list[str] = []
    seen: set[str] = set()
    for row in list(hit_rows) + list(pit_rows):
        key = _career_group_key(row)
        if key in seen:
            continue
        seen.add(key)
        ordered_keys.append(key)
    if not ordered_keys:
        ordered_keys = list(dict.fromkeys(list(hit_by_key.keys()) + list(pit_by_key.keys())))

    merged_rows: list[dict] = []
    for key in ordered_keys:
        hit = hit_by_key.get(key)
        pit = pit_by_key.get(key)
        if not hit and not pit:
            continue

        source = hit or pit or {}
        merged = dict(source)

        merged["Type"] = "H/P" if hit and pit else ("H" if hit else "P")
        merged["Team"] = _row_team_value(hit or {}) or _row_team_value(pit or {})
        merged["Pos"] = _merge_position_value((hit or {}).get("Pos"), (pit or {}).get("Pos"))
        merged["Age"] = (hit or {}).get("Age")
        if merged["Age"] is None:
            merged["Age"] = (pit or {}).get("Age")

        year_start_candidates = [
            parsed
            for value in ((hit or {}).get("YearStart"), (pit or {}).get("YearStart"), (hit or {}).get("Year"), (pit or {}).get("Year"))
            if (parsed := _coerce_record_year(value)) is not None
        ]
        year_end_candidates = [
            parsed
            for value in ((hit or {}).get("YearEnd"), (pit or {}).get("YearEnd"), (hit or {}).get("Year"), (pit or {}).get("Year"))
            if (parsed := _coerce_record_year(value)) is not None
        ]
        year_start = min(year_start_candidates) if year_start_candidates else None
        year_end = max(year_end_candidates) if year_end_candidates else None
        merged["Year"] = None
        merged["YearStart"] = year_start
        merged["YearEnd"] = year_end
        merged["Years"] = _format_year_span(year_start, year_end)

        projection_total = _max_projection_count((hit or {}).get("ProjectionsUsed"), (pit or {}).get("ProjectionsUsed"))
        if projection_total is not None:
            merged["ProjectionsUsed"] = projection_total
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
        "Years",
        "YearStart",
        "YearEnd",
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
            av_missing = pd.isna(av_ts)
            bv_missing = pd.isna(bv_ts)
            if av_missing and bv_missing:
                return 0
            if av_missing:
                return 1
            if bv_missing:
                return -1
            av_num = float(av_ts.value)
            bv_num = float(bv_ts.value)
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
    player_keys: set[str] | None = None,
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
    if player_keys:
        out = [
            r for r in out
            if player_keys.intersection(_row_player_filter_keys(r))
        ]
    return out


@lru_cache(maxsize=PROJECTION_QUERY_CACHE_MAXSIZE)
def _cached_projection_rows(
    dataset: Literal["bat", "pitch"],
    player: str,
    team: str,
    player_keys: str,
    year: int | None,
    years: str,
    pos: str,
    include_dynasty: bool,
    dynasty_years: str,
    career_totals: bool,
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
        _parse_player_keys_filter(player_keys),
    )
    if career_totals:
        filtered = _aggregate_projection_career_rows(filtered, is_hitter=(dataset == "bat"))
    if include_dynasty:
        filtered = _attach_dynasty_values(
            filtered,
            _parse_dynasty_years(dynasty_years or None, valid_years=valid_years),
        )
    return tuple(filtered)


@lru_cache(maxsize=PROJECTION_QUERY_CACHE_MAXSIZE)
def _cached_all_projection_rows(
    player: str,
    team: str,
    player_keys: str,
    year: int | None,
    years: str,
    pos: str,
    include_dynasty: bool,
    dynasty_years: str,
    career_totals: bool,
) -> tuple[dict, ...]:
    valid_years = _coerce_meta_years(META)
    requested_years = _resolve_projection_year_filter(year, years or None, valid_years=valid_years)
    hit_filtered = filter_records(
        BAT_DATA,
        player or None,
        team or None,
        requested_years,
        None,
        _parse_player_keys_filter(player_keys),
    )
    pit_filtered = filter_records(
        PIT_DATA,
        player or None,
        team or None,
        requested_years,
        None,
        _parse_player_keys_filter(player_keys),
    )
    merged = (
        _aggregate_all_projection_career_rows(hit_filtered, pit_filtered)
        if career_totals
        else _merge_all_projection_rows(hit_filtered, pit_filtered)
    )
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
    return tuple(merged)


def _get_projection_rows(
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
    career_totals: bool,
    sort_col: str | None,
    sort_dir: str | None,
) -> tuple[dict, ...]:
    cached_rows = _cached_projection_rows(
        dataset,
        _normalize_filter_value(player),
        _normalize_filter_value(team),
        _normalize_player_keys_filter(player_keys),
        year,
        _normalize_filter_value(years),
        _normalize_filter_value(pos),
        include_dynasty,
        _normalize_filter_value(dynasty_years),
        career_totals,
    )
    sorted_rows = _sort_projection_rows(
        list(cached_rows),
        _normalize_filter_value(sort_col),
        _normalize_sort_dir(sort_dir),
    )
    return tuple(sorted_rows)


def _get_all_projection_rows(
    *,
    player: str | None,
    team: str | None,
    player_keys: str | None,
    year: int | None,
    years: str | None,
    pos: str | None,
    include_dynasty: bool,
    dynasty_years: str | None,
    career_totals: bool,
    sort_col: str | None,
    sort_dir: str | None,
) -> tuple[dict, ...]:
    cached_rows = _cached_all_projection_rows(
        _normalize_filter_value(player),
        _normalize_filter_value(team),
        _normalize_player_keys_filter(player_keys),
        year,
        _normalize_filter_value(years),
        _normalize_filter_value(pos),
        include_dynasty,
        _normalize_filter_value(dynasty_years),
        career_totals,
    )
    sorted_rows = _sort_projection_rows(
        list(cached_rows),
        _normalize_filter_value(sort_col),
        _normalize_sort_dir(sort_dir),
    )
    return tuple(sorted_rows)


def _version_payload() -> dict[str, Any]:
    return {
        "build_id": APP_BUILD_ID,
        "commit_sha": DEPLOY_COMMIT_SHA or None,
        "built_at": APP_BUILD_AT,
        "data_version": _current_data_version(),
        "projection_freshness": dict(PROJECTION_FRESHNESS),
    }


def _payload_etag(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f'"{digest}"'


def _etag_matches(if_none_match: str | None, current_etag: str) -> bool:
    token = str(if_none_match or "").strip()
    if not token:
        return False
    if token == "*":
        return True

    current = current_etag[2:].strip() if current_etag.startswith("W/") else current_etag.strip()
    for raw_candidate in token.split(","):
        candidate = raw_candidate.strip()
        if not candidate:
            continue
        if candidate == "*":
            return True
        candidate = candidate[2:].strip() if candidate.startswith("W/") else candidate
        if candidate == current:
            return True
    return False


@app.get("/api/version")
def get_version(request: Request):
    _refresh_data_if_needed()
    payload = _version_payload()
    headers = dict(API_NO_CACHE_HEADERS)
    etag = _payload_etag(payload)
    headers["ETag"] = etag
    if _etag_matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return JSONResponse(
        payload,
        headers=headers,
    )


@app.get("/api/health")
def get_health():
    _refresh_data_if_needed()

    with CALCULATOR_JOB_LOCK:
        _cleanup_calculation_jobs()
        job_status_counts = {"queued": 0, "running": 0, "completed": 0, "failed": 0, CALC_JOB_CANCELLED_STATUS: 0}
        for job in CALCULATOR_JOBS.values():
            status = str(job.get("status") or "").strip().lower()
            if status in job_status_counts:
                job_status_counts[status] += 1

    with CALC_RESULT_CACHE_LOCK:
        _cleanup_local_result_cache()
        local_result_cache_entries = len(CALC_RESULT_CACHE)

    with CALCULATOR_PREWARM_LOCK:
        prewarm = dict(CALCULATOR_PREWARM_STATE)

    return {
        "status": "ok",
        "build_id": APP_BUILD_ID,
        "projection_rows": {
            "bat": len(BAT_DATA),
            "pitch": len(PIT_DATA),
        },
        "jobs": {
            "total": len(CALCULATOR_JOBS),
            **job_status_counts,
        },
        "result_cache": {
            "local_entries": local_result_cache_entries,
            "redis_configured": bool(REDIS_URL),
        },
        "calculator_prewarm": prewarm,
        "timestamp": _iso_now(),
    }


@app.get("/api/projections/all")
def get_all_projections(
    player: Optional[str] = None,
    team: Optional[str] = None,
    player_keys: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[str] = None,
    pos: Optional[str] = None,
    dynasty_years: Optional[str] = None,
    career_totals: bool = False,
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
        player_keys=player_keys,
        year=year,
        years=years,
        pos=pos,
        include_dynasty=include_dynasty,
        dynasty_years=dynasty_years,
        career_totals=career_totals,
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
    player_keys: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[str] = None,
    pos: Optional[str] = None,
    dynasty_years: Optional[str] = None,
    career_totals: bool = False,
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
        player_keys=player_keys,
        year=year,
        years=years,
        pos=pos,
        include_dynasty=include_dynasty,
        dynasty_years=dynasty_years,
        career_totals=career_totals,
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
    player_keys: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[str] = None,
    pos: Optional[str] = None,
    dynasty_years: Optional[str] = None,
    career_totals: bool = False,
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
        player_keys=player_keys,
        year=year,
        years=years,
        pos=pos,
        include_dynasty=include_dynasty,
        dynasty_years=dynasty_years,
        career_totals=career_totals,
        sort_col=validated_sort_col,
        sort_dir=sort_dir,
    )
    total = len(filtered)
    page = list(filtered[offset : offset + limit])
    return {"total": total, "offset": offset, "limit": limit, "data": page}


@app.get("/api/projections/export/{dataset}")
def export_projections(
    dataset: Literal["all", "bat", "pitch"],
    file_format: Literal["csv", "xlsx"] = Query(default="csv", alias="format"),
    player: Optional[str] = None,
    team: Optional[str] = None,
    player_keys: Optional[str] = None,
    year: Optional[int] = None,
    years: Optional[str] = None,
    pos: Optional[str] = None,
    dynasty_years: Optional[str] = None,
    career_totals: bool = False,
    include_dynasty: bool = True,
    sort_col: Optional[str] = None,
    sort_dir: Literal["asc", "desc"] = "desc",
):
    _refresh_data_if_needed()
    validated_sort_col = _validate_sort_col(sort_col, dataset=dataset)
    if dataset == "all":
        rows = list(
            _get_all_projection_rows(
                player=player,
                team=team,
                player_keys=player_keys,
                year=year,
                years=years,
                pos=pos,
                include_dynasty=include_dynasty,
                dynasty_years=dynasty_years,
                career_totals=career_totals,
                sort_col=validated_sort_col,
                sort_dir=sort_dir,
            )
        )
    else:
        rows = list(
            _get_projection_rows(
                dataset,
                player=player,
                team=team,
                player_keys=player_keys,
                year=year,
                years=years,
                pos=pos,
                include_dynasty=include_dynasty,
                dynasty_years=dynasty_years,
                career_totals=career_totals,
                sort_col=validated_sort_col,
                sort_dir=sort_dir,
            )
        )

    return _tabular_export_response(
        rows,
        filename_base=f"projections-{dataset}",
        file_format=file_format,
    )


# ---------------------------------------------------------------------------
# API: Dynasty Value Calculator
# ---------------------------------------------------------------------------
class CalculateRequest(BaseModel):
    mode: Literal["common"] = "common"
    scoring_mode: Literal["roto", "points"] = "roto"
    two_way: Literal["sum", "max"] = "sum"
    teams: int = Field(default=12, ge=2, le=30)
    sims: int = Field(default=300, ge=1, le=5000)
    horizon: int = Field(default=20, ge=1, le=20)
    discount: float = Field(default=0.94, gt=0.0, le=1.0)
    hit_c: int = Field(default=COMMON_HITTER_SLOT_DEFAULTS["C"], ge=0, le=15)
    hit_1b: int = Field(default=COMMON_HITTER_SLOT_DEFAULTS["1B"], ge=0, le=15)
    hit_2b: int = Field(default=COMMON_HITTER_SLOT_DEFAULTS["2B"], ge=0, le=15)
    hit_3b: int = Field(default=COMMON_HITTER_SLOT_DEFAULTS["3B"], ge=0, le=15)
    hit_ss: int = Field(default=COMMON_HITTER_SLOT_DEFAULTS["SS"], ge=0, le=15)
    hit_ci: int = Field(default=COMMON_HITTER_SLOT_DEFAULTS["CI"], ge=0, le=15)
    hit_mi: int = Field(default=COMMON_HITTER_SLOT_DEFAULTS["MI"], ge=0, le=15)
    hit_of: int = Field(default=COMMON_HITTER_SLOT_DEFAULTS["OF"], ge=0, le=15)
    hit_ut: int = Field(default=COMMON_HITTER_SLOT_DEFAULTS["UT"], ge=0, le=15)
    pit_p: int = Field(default=COMMON_PITCHER_SLOT_DEFAULTS["P"], ge=0, le=15)
    pit_sp: int = Field(default=COMMON_PITCHER_SLOT_DEFAULTS["SP"], ge=0, le=15)
    pit_rp: int = Field(default=COMMON_PITCHER_SLOT_DEFAULTS["RP"], ge=0, le=15)
    bench: int = Field(default=6, ge=0, le=40)
    minors: int = Field(default=COMMON_DEFAULT_MINOR_SLOTS, ge=0, le=60)
    ir: int = Field(default=COMMON_DEFAULT_IR_SLOTS, ge=0, le=40)
    ip_min: float = Field(default=0.0, ge=0.0)
    ip_max: Optional[float] = Field(default=None, ge=0.0)
    start_year: int = Field(default=2026, ge=1900)
    recent_projections: int = Field(default=3, ge=1, le=10)
    roto_hit_r: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_r"]
    roto_hit_rbi: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_rbi"]
    roto_hit_hr: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_hr"]
    roto_hit_sb: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_sb"]
    roto_hit_avg: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_avg"]
    roto_hit_obp: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_obp"]
    roto_hit_slg: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_slg"]
    roto_hit_ops: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_ops"]
    roto_hit_h: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_h"]
    roto_hit_bb: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_bb"]
    roto_hit_2b: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_2b"]
    roto_hit_tb: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_hit_tb"]
    roto_pit_w: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_pit_w"]
    roto_pit_k: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_pit_k"]
    roto_pit_sv: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_pit_sv"]
    roto_pit_era: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_pit_era"]
    roto_pit_whip: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_pit_whip"]
    roto_pit_qs: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_pit_qs"]
    roto_pit_svh: bool = ROTO_CATEGORY_FIELD_DEFAULTS["roto_pit_svh"]
    pts_hit_1b: float = Field(default=DEFAULT_POINTS_SCORING["pts_hit_1b"], ge=-50.0, le=50.0)
    pts_hit_2b: float = Field(default=DEFAULT_POINTS_SCORING["pts_hit_2b"], ge=-50.0, le=50.0)
    pts_hit_3b: float = Field(default=DEFAULT_POINTS_SCORING["pts_hit_3b"], ge=-50.0, le=50.0)
    pts_hit_hr: float = Field(default=DEFAULT_POINTS_SCORING["pts_hit_hr"], ge=-50.0, le=50.0)
    pts_hit_r: float = Field(default=DEFAULT_POINTS_SCORING["pts_hit_r"], ge=-50.0, le=50.0)
    pts_hit_rbi: float = Field(default=DEFAULT_POINTS_SCORING["pts_hit_rbi"], ge=-50.0, le=50.0)
    pts_hit_sb: float = Field(default=DEFAULT_POINTS_SCORING["pts_hit_sb"], ge=-50.0, le=50.0)
    pts_hit_bb: float = Field(default=DEFAULT_POINTS_SCORING["pts_hit_bb"], ge=-50.0, le=50.0)
    pts_hit_so: float = Field(default=DEFAULT_POINTS_SCORING["pts_hit_so"], ge=-50.0, le=50.0)
    pts_pit_ip: float = Field(default=DEFAULT_POINTS_SCORING["pts_pit_ip"], ge=-50.0, le=50.0)
    pts_pit_w: float = Field(default=DEFAULT_POINTS_SCORING["pts_pit_w"], ge=-50.0, le=50.0)
    pts_pit_l: float = Field(default=DEFAULT_POINTS_SCORING["pts_pit_l"], ge=-50.0, le=50.0)
    pts_pit_k: float = Field(default=DEFAULT_POINTS_SCORING["pts_pit_k"], ge=-50.0, le=50.0)
    pts_pit_sv: float = Field(default=DEFAULT_POINTS_SCORING["pts_pit_sv"], ge=-50.0, le=50.0)
    pts_pit_svh: float = Field(default=DEFAULT_POINTS_SCORING["pts_pit_svh"], ge=-50.0, le=50.0)
    pts_pit_h: float = Field(default=DEFAULT_POINTS_SCORING["pts_pit_h"], ge=-50.0, le=50.0)
    pts_pit_er: float = Field(default=DEFAULT_POINTS_SCORING["pts_pit_er"], ge=-50.0, le=50.0)
    pts_pit_bb: float = Field(default=DEFAULT_POINTS_SCORING["pts_pit_bb"], ge=-50.0, le=50.0)

    @model_validator(mode="after")
    def validate_ip_bounds(self) -> "CalculateRequest":
        if self.ip_max is not None and self.ip_max < self.ip_min:
            raise ValueError("ip_max must be greater than or equal to ip_min")
        total_hitter_slots = (
            self.hit_c
            + self.hit_1b
            + self.hit_2b
            + self.hit_3b
            + self.hit_ss
            + self.hit_ci
            + self.hit_mi
            + self.hit_of
            + self.hit_ut
        )
        total_pitcher_slots = self.pit_p + self.pit_sp + self.pit_rp
        if total_hitter_slots <= 0:
            raise ValueError("At least one hitter slot must be greater than 0.")
        if total_pitcher_slots <= 0:
            raise ValueError("At least one pitcher slot must be greater than 0.")
        if self.scoring_mode == "roto":
            if not any(bool(getattr(self, field_key, False)) for field_key, _stat_col, _default in ROTO_HITTER_CATEGORY_FIELDS):
                raise ValueError("Roto scoring must include at least one hitting category.")
            if not any(bool(getattr(self, field_key, False)) for field_key, _stat_col, _default in ROTO_PITCHER_CATEGORY_FIELDS):
                raise ValueError("Roto scoring must include at least one pitching category.")
        if self.scoring_mode == "points":
            has_non_zero_rule = any(
                abs(value) > 1e-9
                for value in (
                    self.pts_hit_1b,
                    self.pts_hit_2b,
                    self.pts_hit_3b,
                    self.pts_hit_hr,
                    self.pts_hit_r,
                    self.pts_hit_rbi,
                    self.pts_hit_sb,
                    self.pts_hit_bb,
                    self.pts_hit_so,
                    self.pts_pit_ip,
                    self.pts_pit_w,
                    self.pts_pit_l,
                    self.pts_pit_k,
                    self.pts_pit_sv,
                    self.pts_pit_svh,
                    self.pts_pit_h,
                    self.pts_pit_er,
                    self.pts_pit_bb,
                )
            )
            if not has_non_zero_rule:
                raise ValueError("Points scoring must include at least one non-zero scoring rule.")
        return self


class CalculateExportRequest(CalculateRequest):
    format: Literal["csv", "xlsx"] = "csv"
    include_explanations: bool = False


def _run_calculate_request(req: CalculateRequest, *, source: str) -> dict:
    started = time.perf_counter()
    settings = req.model_dump()
    active_cache = _calculate_points_dynasty_frame_cached if req.scoring_mode == "points" else _calculate_common_dynasty_frame_cached
    cache_before = active_cache.cache_info()
    result_cache_key = _calc_result_cache_key(settings)
    result_cache_hit = False
    status_code = 200

    try:
        _refresh_data_if_needed()
        valid_years = _coerce_meta_years(META)
        if valid_years and req.start_year not in set(valid_years):
            raise HTTPException(
                status_code=422,
                detail=f"start_year must be one of the available projection years: {valid_years}",
            )

        cached_payload = _result_cache_get(result_cache_key)
        if cached_payload is not None:
            result_cache_hit = True
            return cached_payload

        try:
            if req.scoring_mode == "points":
                out = _calculate_points_dynasty_frame_cached(
                    teams=req.teams,
                    horizon=req.horizon,
                    discount=req.discount,
                    hit_c=req.hit_c,
                    hit_1b=req.hit_1b,
                    hit_2b=req.hit_2b,
                    hit_3b=req.hit_3b,
                    hit_ss=req.hit_ss,
                    hit_ci=req.hit_ci,
                    hit_mi=req.hit_mi,
                    hit_of=req.hit_of,
                    hit_ut=req.hit_ut,
                    pit_p=req.pit_p,
                    pit_sp=req.pit_sp,
                    pit_rp=req.pit_rp,
                    bench=req.bench,
                    minors=req.minors,
                    ir=req.ir,
                    two_way=req.two_way,
                    start_year=req.start_year,
                    recent_projections=req.recent_projections,
                    pts_hit_1b=req.pts_hit_1b,
                    pts_hit_2b=req.pts_hit_2b,
                    pts_hit_3b=req.pts_hit_3b,
                    pts_hit_hr=req.pts_hit_hr,
                    pts_hit_r=req.pts_hit_r,
                    pts_hit_rbi=req.pts_hit_rbi,
                    pts_hit_sb=req.pts_hit_sb,
                    pts_hit_bb=req.pts_hit_bb,
                    pts_hit_so=req.pts_hit_so,
                    pts_pit_ip=req.pts_pit_ip,
                    pts_pit_w=req.pts_pit_w,
                    pts_pit_l=req.pts_pit_l,
                    pts_pit_k=req.pts_pit_k,
                    pts_pit_sv=req.pts_pit_sv,
                    pts_pit_svh=req.pts_pit_svh,
                    pts_pit_h=req.pts_pit_h,
                    pts_pit_er=req.pts_pit_er,
                    pts_pit_bb=req.pts_pit_bb,
                ).copy(deep=True)
            else:
                out = _calculate_common_dynasty_frame_cached(
                    teams=req.teams,
                    sims=req.sims,
                    horizon=req.horizon,
                    discount=req.discount,
                    hit_c=req.hit_c,
                    hit_1b=req.hit_1b,
                    hit_2b=req.hit_2b,
                    hit_3b=req.hit_3b,
                    hit_ss=req.hit_ss,
                    hit_ci=req.hit_ci,
                    hit_mi=req.hit_mi,
                    hit_of=req.hit_of,
                    hit_ut=req.hit_ut,
                    pit_p=req.pit_p,
                    pit_sp=req.pit_sp,
                    pit_rp=req.pit_rp,
                    bench=req.bench,
                    minors=req.minors,
                    ir=req.ir,
                    ip_min=req.ip_min,
                    ip_max=req.ip_max,
                    two_way=req.two_way,
                    start_year=req.start_year,
                    recent_projections=req.recent_projections,
                    **_roto_category_settings_from_dict(settings),
                ).copy(deep=True)
        except ValueError as calc_error:
            message = str(calc_error)
            if _is_user_fixable_calculation_error(message):
                raise HTTPException(status_code=422, detail=message) from calc_error
            raise

        identity_by_name = _player_identity_by_name()
        if PLAYER_KEY_COL not in out.columns:
            out[PLAYER_KEY_COL] = None
        if PLAYER_ENTITY_KEY_COL not in out.columns:
            out[PLAYER_ENTITY_KEY_COL] = None

        def _resolve_player_key(row: pd.Series) -> str:
            player_name = str(row.get("Player") or "").strip()
            existing_key = str(row.get(PLAYER_KEY_COL) or "").strip()
            if existing_key:
                return existing_key
            mapped_key, _mapped_entity = identity_by_name.get(player_name, (_normalize_player_key(player_name), None))
            return mapped_key

        def _resolve_entity_key(row: pd.Series) -> str | None:
            player_name = str(row.get("Player") or "").strip()
            existing_entity = str(row.get(PLAYER_ENTITY_KEY_COL) or "").strip()
            if existing_entity:
                return existing_entity
            _mapped_key, mapped_entity = identity_by_name.get(player_name, (_normalize_player_key(player_name), None))
            return mapped_entity

        out[PLAYER_KEY_COL] = out.apply(_resolve_player_key, axis=1)
        out[PLAYER_ENTITY_KEY_COL] = out.apply(_resolve_entity_key, axis=1)
        out["DynastyMatchStatus"] = out[PLAYER_ENTITY_KEY_COL].map(
            lambda value: "matched" if value else "no_unique_match"
        )
        selected_roto_stat_cols: list[str] = []
        if req.scoring_mode == "roto":
            selected_hit_cats, selected_pit_cats = _selected_roto_categories(settings)
            selected_roto_stat_cols = selected_hit_cats + selected_pit_cats
            if selected_roto_stat_cols:
                stats_by_entity = _start_year_roto_stats_by_entity(
                    start_year=req.start_year,
                    recent_projections=req.recent_projections,
                )
                identity_keys = out.apply(_projection_identity_key, axis=1)
                for stat_col in selected_roto_stat_cols:
                    stat_lookup = {
                        key: values.get(stat_col)
                        for key, values in stats_by_entity.items()
                        if stat_col in values
                    }
                    out[stat_col] = identity_keys.map(stat_lookup)
        explanations = _build_calculation_explanations(out, settings=settings)

        # Select output columns
        year_cols = [c for c in out.columns if c.startswith("Value_")]
        cols = [
            "Player", PLAYER_KEY_COL, PLAYER_ENTITY_KEY_COL, "DynastyMatchStatus", "Team", "Pos", "Age",
        ] + selected_roto_stat_cols + [
            "DynastyValue", "RawDynastyValue",
            "minor_eligible",
        ] + year_cols

        available_cols = [c for c in cols if c in out.columns]
        df = out[available_cols].copy()

        # Round for JSON
        three_decimal_cols = {"AVG", "OBP", "SLG", "OPS"}
        for c in df.select_dtypes(include="float").columns:
            df[c] = df[c].round(3 if c in three_decimal_cols else 2)

        records = df.to_dict(orient="records")
        records = _clean_records_for_json(records)

        payload = {
            "total": len(records),
            "settings": settings,
            "data": records,
            "explanations": explanations,
        }
        _result_cache_set(result_cache_key, payload)
        return payload

    except HTTPException as exc:
        status_code = exc.status_code
        raise
    except Exception as exc:
        status_code = 500
        CALC_LOGGER.exception("calculator request failed source=%s", source)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 1)
        cache_after = active_cache.cache_info()
        cache_event = "none"
        if result_cache_hit:
            cache_event = "result-cache-hit"
        elif cache_after.hits > cache_before.hits:
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
        if str(job.get("status") or "").lower() == CALC_JOB_CANCELLED_STATUS or bool(job.get("cancel_requested")):
            _mark_job_cancelled_locked(job)
            _cache_calculation_job_snapshot(job)
            return
        job["status"] = "running"
        job["started_at"] = _iso_now()
        job["updated_at"] = job["started_at"]
        job["error"] = None
        _cache_calculation_job_snapshot(job)

    try:
        req = CalculateRequest(**req_payload)
        result = _run_calculate_request(req, source="job")
        with CALCULATOR_JOB_LOCK:
            job = CALCULATOR_JOBS.get(job_id)
            if job is None:
                return
            if str(job.get("status") or "").lower() == CALC_JOB_CANCELLED_STATUS or bool(job.get("cancel_requested")):
                _mark_job_cancelled_locked(job)
                _cache_calculation_job_snapshot(job)
                return
            now = _iso_now()
            job["status"] = "completed"
            job["result"] = result
            job["completed_at"] = now
            job["updated_at"] = now
            job["error"] = None
            _cache_calculation_job_snapshot(job)
    except HTTPException as exc:
        with CALCULATOR_JOB_LOCK:
            job = CALCULATOR_JOBS.get(job_id)
            if job is None:
                return
            if str(job.get("status") or "").lower() == CALC_JOB_CANCELLED_STATUS or bool(job.get("cancel_requested")):
                _mark_job_cancelled_locked(job)
                _cache_calculation_job_snapshot(job)
                return
            now = _iso_now()
            job["status"] = "failed"
            job["error"] = {"status_code": exc.status_code, "detail": exc.detail}
            job["completed_at"] = now
            job["updated_at"] = now
            job["result"] = None
            _cache_calculation_job_snapshot(job)
    except Exception as exc:
        CALC_LOGGER.exception("calculator job crashed job_id=%s", job_id)
        with CALCULATOR_JOB_LOCK:
            job = CALCULATOR_JOBS.get(job_id)
            if job is None:
                return
            if str(job.get("status") or "").lower() == CALC_JOB_CANCELLED_STATUS or bool(job.get("cancel_requested")):
                _mark_job_cancelled_locked(job)
                _cache_calculation_job_snapshot(job)
                return
            now = _iso_now()
            job["status"] = "failed"
            job["error"] = {"status_code": 500, "detail": str(exc)}
            job["completed_at"] = now
            job["updated_at"] = now
            job["result"] = None
            _cache_calculation_job_snapshot(job)
    finally:
        with CALCULATOR_JOB_LOCK:
            _cleanup_calculation_jobs()


@app.post("/api/calculate")
def calculate_dynasty_values(req: CalculateRequest, request: Request):
    """Run the dynasty value calculator and return results as JSON."""
    _enforce_rate_limit(request, action="calc-sync", limit_per_minute=CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE)
    return _run_calculate_request(req, source="sync")


@app.post("/api/calculate/export")
def export_calculate_dynasty_values(req: CalculateExportRequest, request: Request):
    _enforce_rate_limit(request, action="calc-sync", limit_per_minute=CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE)
    payload = req.model_dump()
    export_format = str(payload.pop("format", "csv")).strip().lower()
    include_explanations = bool(payload.pop("include_explanations", False))
    calc_req = CalculateRequest(**payload)
    result = _run_calculate_request(calc_req, source="sync-export")
    explain_rows = _flatten_explanations_for_export(result.get("explanations", {})) if include_explanations else None
    return _tabular_export_response(
        result.get("data", []),
        filename_base=f"dynasty-rankings-{calc_req.scoring_mode}",
        file_format="xlsx" if export_format == "xlsx" else "csv",
        explain_rows=explain_rows,
    )


@app.post("/api/calculate/jobs", status_code=202)
def create_calculate_dynasty_job(req: CalculateRequest, request: Request):
    _enforce_rate_limit(request, action="calc-job-create", limit_per_minute=CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE)
    client_ip = _client_ip(request)
    created_at = _iso_now()
    payload = req.model_dump()
    cache_key = _calc_result_cache_key(payload)
    cached_result = _result_cache_get(cache_key)
    job_id = uuid4().hex
    job = {
        "job_id": job_id,
        "status": "completed" if cached_result is not None else "queued",
        "created_at": created_at,
        "started_at": created_at if cached_result is not None else None,
        "completed_at": created_at if cached_result is not None else None,
        "updated_at": created_at,
        "created_ts": time.time(),
        "client_ip": client_ip,
        "settings": payload,
        "result": cached_result,
        "error": None,
        "cancel_requested": False,
        "future": None,
    }

    with CALCULATOR_JOB_LOCK:
        _cleanup_calculation_jobs(job["created_ts"])
        if cached_result is None:
            active_for_ip = _active_jobs_for_ip(client_ip)
            if active_for_ip >= CALCULATOR_MAX_ACTIVE_JOBS_PER_IP:
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "Too many active calculation jobs for this client IP. "
                        "Wait for an existing job to finish and retry."
                    ),
                )
        CALCULATOR_JOBS[job_id] = job
        if cached_result is not None:
            _cache_calculation_job_snapshot(job)
        response_payload = _calculation_job_public_payload(job)

    if cached_result is None:
        try:
            future = CALCULATOR_JOB_EXECUTOR.submit(_run_calculation_job, job_id, payload)
        except RuntimeError as exc:
            with CALCULATOR_JOB_LOCK:
                CALCULATOR_JOBS.pop(job_id, None)
            raise HTTPException(status_code=503, detail="Calculation worker is unavailable.") from exc
        with CALCULATOR_JOB_LOCK:
            live_job = CALCULATOR_JOBS.get(job_id)
            if live_job is not None:
                live_job["future"] = future
        CALC_LOGGER.info("calculator job queued job_id=%s settings=%s", job_id, json.dumps(payload, sort_keys=True))
    else:
        CALC_LOGGER.info("calculator job cache-hit job_id=%s settings=%s", job_id, json.dumps(payload, sort_keys=True))

    return response_payload


@app.get("/api/calculate/jobs/{job_id}")
def get_calculate_dynasty_job(job_id: str, request: Request):
    _enforce_rate_limit(request, action="calc-job-status", limit_per_minute=CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE)
    with CALCULATOR_JOB_LOCK:
        _cleanup_calculation_jobs()
        job = CALCULATOR_JOBS.get(job_id)
        if job is None:
            cached_job = _cached_calculation_job_snapshot(job_id)
            if cached_job is not None:
                return cached_job
            raise HTTPException(status_code=404, detail="Calculation job not found or expired.")
        return _calculation_job_public_payload(job)


@app.delete("/api/calculate/jobs/{job_id}")
def cancel_calculate_dynasty_job(job_id: str, request: Request):
    _enforce_rate_limit(request, action="calc-job-status", limit_per_minute=CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE)
    with CALCULATOR_JOB_LOCK:
        _cleanup_calculation_jobs()
        job = CALCULATOR_JOBS.get(job_id)
        if job is None:
            cached_job = _cached_calculation_job_snapshot(job_id)
            if cached_job is not None:
                return cached_job
            raise HTTPException(status_code=404, detail="Calculation job not found or expired.")

        status = str(job.get("status") or "").lower()
        if status not in {"queued", "running"}:
            return _calculation_job_public_payload(job)

        job["cancel_requested"] = True
        future = job.get("future")
        cancel_future = getattr(future, "cancel", None)
        if callable(cancel_future):
            try:
                cancel_future()
            except Exception:
                pass
        _mark_job_cancelled_locked(job)
        _cache_calculation_job_snapshot(job)
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
    ASSET_CACHE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}

    @app.get("/")
    def serve_index():
        try:
            html = INDEX_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail="Frontend dist/index.html is unavailable. Build the frontend with: npm run build (in frontend/).",
            ) from exc

        if INDEX_BUILD_TOKEN in html:
            html = html.replace(INDEX_BUILD_TOKEN, APP_BUILD_ID)

        return HTMLResponse(content=html, headers=INDEX_CACHE_HEADERS)

    @app.get("/assets/{asset_path:path}")
    def serve_frontend_asset(asset_path: str):
        normalized = asset_path.lstrip("/")
        candidate = (FRONTEND_DIST_ASSETS_DIR / normalized).resolve()
        assets_root = FRONTEND_DIST_ASSETS_DIR.resolve()
        try:
            candidate.relative_to(assets_root)
        except ValueError:
            raise HTTPException(status_code=404, detail="Asset not found")
        if not candidate.is_file():
            raise HTTPException(status_code=404, detail="Asset not found")
        return FileResponse(path=str(candidate), headers=ASSET_CACHE_HEADERS)
