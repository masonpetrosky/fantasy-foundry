"""Shared runtime constants/config helpers for backend.runtime."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

INDEX_BUILD_TOKEN = "__APP_BUILD_ID__"
API_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

YEAR_RANGE_TOKEN_RE = re.compile(r"^(\d{4})\s*-\s*(\d{4})$")
PROJECTION_QUERY_CACHE_MAXSIZE = 256
ALL_TAB_HITTER_STAT_COLS = ("G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "BB", "SO", "AVG", "OBP", "OPS")
ALL_TAB_PITCH_STAT_COLS = ("GS", "IP", "W", "QS", "QA3", "L", "K", "SV", "SVH", "ERA", "WHIP", "ER")
PROJECTION_TEXT_SORT_COLS = {"Player", "Team", "Pos", "Type", "Years"}

REDIS_RESULT_PREFIX = "ff:calc:result:"
REDIS_JOB_PREFIX = "ff:calc:job:"
REDIS_JOB_CANCEL_PREFIX = "ff:calc:job-cancel:"
REDIS_ACTIVE_JOBS_PREFIX = "ff:calc:active-jobs:"
REDIS_JOB_CLIENT_PREFIX = "ff:calc:job-client:"
REDIS_RATE_LIMIT_PREFIX = "ff:rate:"

CALC_JOB_CANCELLED_STATUS = "cancelled"
CALC_JOB_CANCELLED_ERROR = {"status_code": 499, "detail": "Calculation job cancelled by client."}


def build_app_build_metadata(*, index_path: Path, deploy_commit_sha: str) -> tuple[str, str | None]:
    deploy_sha = str(deploy_commit_sha or "").strip()
    if deploy_sha:
        app_build_id = deploy_sha[:12]
    else:
        try:
            app_build_id = str(index_path.stat().st_mtime_ns)
        except OSError:
            app_build_id = "unknown"

    try:
        timestamp = index_path.stat().st_mtime
    except OSError:
        app_build_at = None
    else:
        app_build_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    return app_build_id, app_build_at
