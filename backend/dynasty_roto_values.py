"""
dynasty_roto_values.py

Unified script for dynasty roto player values.

Modes:
- common: 5x5 roto, typical lineup, no IP cap by default.
- league: custom league settings (SP/RP/P slots, IP min/max, OPS/SVH/QA3 cats).

"Most common" dynasty roto configuration:
- 12-team roto
- 5x5 categories:
    Hitters: R, HR, RBI, SB, AVG
    Pitchers: W, K, SV, ERA, WHIP
- No IP cap (by default)
- Typical roto lineup:
    Hitters: C(1), 1B, 2B, 3B, SS, CI, MI, OF(5), UT
    Pitchers: P(9)
- Roster (common defaults): 28 total = 22 starters + 6 bench; 0 minors; 0 IR.
- Dynasty value: discounted multi-year marginal roto points (SGP),
  then centered so that ~0 corresponds to the replacement-level roster
  cutoff (active + bench).

Input format (same as your file):
Excel workbook with sheets:
- "Bat" with columns at least:
  Player, Year, Team, Age, Pos, AB, H, R, HR, RBI, SB
- "Pitch" with columns at least:
  Player, Year, Team, Age, Pos, IP, W, K, SV, ER, H, BB
  (If SV missing but SVH present, we use SV = SVH)
Optional:
  - A minors eligibility column in either sheet named like MinorEligible, Minor, or minor_eligible.
If multiple projections exist for the same Player/Year, the script averages the
three most recent rows (by projection date column if present, otherwise file order)
over counting stats, then recomputes rate stats (AVG/ERA/WHIP/OPS).

Outputs:
- common_player_values.csv
- common_player_values.xlsx

Run (common mode):
  python dynasty_roto_values.py common --input "Dynasty Baseball Projections.xlsx" --start-year 2026

Optional (common):
  python dynasty_roto_values.py common --input "Dynasty Baseball Projections.xlsx" --teams 12 --sims 200 --horizon 10

Run (league mode):
  python dynasty_roto_values.py league --input "Dynasty Baseball Projections.xlsx" --start-year 2026

Dependencies:
  pip install pandas numpy openpyxl
Optional (faster/better slot assignment):
  pip install scipy
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from importlib.util import find_spec
from typing import Callable, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

# Excel formatting (output workbook)
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

# Projection de-duplication helpers
PROJECTION_DATE_COLS = ["ProjectionDate", "Date", "Updated", "LastUpdated", "Timestamp", "Created", "AsOf"]


def positive_int_arg(value: Union[str, int]) -> int:
    """argparse type: integer >= 1."""
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Expected an integer, got: {value!r}") from exc
    if ivalue < 1:
        raise argparse.ArgumentTypeError(f"Expected an integer >= 1, got: {ivalue}")
    return ivalue


def non_negative_int_arg(value: Union[str, int]) -> int:
    """argparse type: integer >= 0."""
    try:
        ivalue = int(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Expected an integer, got: {value!r}") from exc
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"Expected an integer >= 0, got: {ivalue}")
    return ivalue


def non_negative_float_arg(value: Union[str, float]) -> float:
    """argparse type: float >= 0."""
    try:
        fvalue = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Expected a float, got: {value!r}") from exc
    if fvalue < 0.0:
        raise argparse.ArgumentTypeError(f"Expected a float >= 0, got: {fvalue}")
    return fvalue


def discount_arg(value: Union[str, float]) -> float:
    """argparse type: annual discount factor in the interval (0, 1]."""
    try:
        fvalue = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Expected a float, got: {value!r}") from exc
    if not (0.0 < fvalue <= 1.0):
        raise argparse.ArgumentTypeError(f"Expected discount in (0, 1], got: {fvalue}")
    return fvalue


def optional_non_negative_float_arg(value: Union[str, float]) -> Optional[float]:
    """argparse type: float >= 0, or None for disabled limits."""
    if value is None:
        return None

    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"none", "null", "off", "no", "disabled"}:
            return None

    try:
        fvalue = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f"Expected a float or 'none', got: {value!r}") from exc

    if fvalue < 0.0:
        raise argparse.ArgumentTypeError(f"Expected a float >= 0 or 'none', got: {fvalue}")
    return fvalue


def validate_ip_bounds(ip_min: float, ip_max: Optional[float]) -> None:
    """Ensure optional IP bounds are internally consistent."""
    if ip_min < 0:
        raise ValueError(f"ip_min must be >= 0, got {ip_min}")
    if ip_max is not None and ip_max < ip_min:
        raise ValueError(f"ip_max ({ip_max}) must be >= ip_min ({ip_min})")


def _find_projection_date_col(df: pd.DataFrame) -> Optional[str]:
    for col in PROJECTION_DATE_COLS:
        if col in df.columns:
            return col
    return None


def average_recent_projections(
    df: pd.DataFrame,
    stat_cols: List[str],
    group_cols: Optional[List[str]] = None,
    max_entries: int = 3,
) -> pd.DataFrame:
    """
    If multiple projections exist for the same (Player, Year), average the most recent
    `max_entries` rows (by projection date column if present, otherwise file order).

    Adds two columns to the averaged output:
      - ProjectionsUsed: number of rows actually averaged (<= max_entries)
      - OldestProjectionDate: the oldest projection date among the rows averaged
        (i.e., the "third-oldest" among the selected rows when max_entries=3).
        If no projection date column exists, this will be NaT.
    """
    if max_entries < 1:
        raise ValueError("max_entries must be >= 1")

    df = df.copy()
    group_cols = group_cols or ["Player", "Year"]

    missing_group_cols = [c for c in group_cols if c not in df.columns]
    if missing_group_cols:
        raise ValueError(f"average_recent_projections missing required group columns: {missing_group_cols}")

    date_col = _find_projection_date_col(df)

    df["_projection_order"] = np.arange(len(df))

    # Always create _projection_date so downstream logic can rely on it.
    if date_col:
        df["_projection_date"] = pd.to_datetime(df[date_col], errors="coerce")
        df["_sort_key"] = df["_projection_date"].fillna(pd.Timestamp.min)
    else:
        df["_projection_date"] = pd.NaT
        df["_sort_key"] = df["_projection_order"]

    # Keep up to `max_entries` most-recent rows per (Player, Year)
    recent = (
        df.sort_values(["_sort_key", "_projection_order"], ascending=False)
        .groupby(group_cols, as_index=False, sort=False)
        .head(max_entries)
    )

    # Per-row markers so we can aggregate to group-level metadata
    recent["ProjectionsUsed"] = 1
    recent["OldestProjectionDate"] = recent["_projection_date"]

    stat_cols_present = [c for c in stat_cols if c in recent.columns]

    # Meta cols are carried forward from the most recent row (same behavior as before)
    meta_cols = [
        c for c in recent.columns
        if c not in stat_cols_present
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

    agg: Dict[str, str] = {c: "mean" for c in stat_cols_present}
    agg["ProjectionsUsed"] = "sum"
    agg["OldestProjectionDate"] = "min"
    for c in meta_cols:
        agg[c] = "first"

    out = (
        recent.sort_values(["_sort_key", "_projection_order"], ascending=False)
        .groupby(group_cols, as_index=False, sort=False)
        .agg(agg)
    )

    # Nice column order: group keys, then the new metadata columns, then everything else
    front = list(group_cols) + ["ProjectionsUsed", "OldestProjectionDate"]
    rest = [c for c in out.columns if c not in front]
    return out[front + rest]


def projection_meta_for_start_year(
    bat_df: pd.DataFrame,
    pit_df: pd.DataFrame,
    start_year: int,
) -> pd.DataFrame:
    """
    Produce one row per Player with:
      - ProjectionsUsed: max of Bat vs Pitch (handles hitter-only / pitcher-only / two-way)
      - OldestProjectionDate: min (oldest) of Bat vs Pitch dates

    Uses the already-averaged frames produced by average_recent_projections().
    """
    cols = ["Player", "ProjectionsUsed", "OldestProjectionDate"]

    def _subset_projection_meta(df: pd.DataFrame) -> pd.DataFrame:
        """Return a safe start-year projection metadata slice.

        Handles empty frames and cases where upstream processing provided no rows,
        ensuring we still return the expected metadata columns.
        """
        if df.empty:
            return pd.DataFrame(columns=cols)

        missing = [c for c in ["Year"] + cols if c not in df.columns]
        if missing:
            raise ValueError(f"projection metadata is missing required columns: {missing}")

        return df.loc[df["Year"] == start_year, cols].copy()

    b = _subset_projection_meta(bat_df)
    p = _subset_projection_meta(pit_df)

    m = b.merge(p, on="Player", how="outer", suffixes=("_bat", "_pit"))

    # How many projections were used (cap is enforced upstream by max_entries)
    m["ProjectionsUsed"] = m[["ProjectionsUsed_bat", "ProjectionsUsed_pit"]].max(axis=1, skipna=True)
    m["ProjectionsUsed"] = m["ProjectionsUsed"].round().astype("Int64")

    # Oldest date among whichever side exists (and the min if both exist)
    m["OldestProjectionDate"] = m[["OldestProjectionDate_bat", "OldestProjectionDate_pit"]].min(axis=1, skipna=True)

    # Store as date-only (no time) for cleaner Excel display
    m["OldestProjectionDate"] = pd.to_datetime(m["OldestProjectionDate"], errors="coerce").dt.date

    return m[["Player", "ProjectionsUsed", "OldestProjectionDate"]]

# ----------------------------
# Helpers: recent-projection averaging + detail sheet formatting
# ----------------------------

DERIVED_HIT_RATE_COLS: Set[str] = {"AVG", "OPS"}
DERIVED_PIT_RATE_COLS: Set[str] = {"ERA", "WHIP"}


def numeric_stat_cols_for_recent_avg(
    df: pd.DataFrame,
    group_cols: Optional[List[str]] = None,
    exclude_cols: Optional[Set[str]] = None,
) -> List[str]:
    """Return numeric columns that should be averaged when collapsing projections.

    This is used both for valuation (so that any categories you care about get averaged)
    and for building "detail" output tabs that closely match the input sheets.
    """
    group_cols = group_cols or ["Player", "Year"]
    exclude_cols = set(exclude_cols or set())

    cols: List[str] = []
    for c in df.columns:
        if c in group_cols or c in exclude_cols:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols


def reorder_detail_columns(
    df: pd.DataFrame,
    input_cols: List[str],
    add_after: Optional[str] = None,
    extra_cols: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Reorder a detail DataFrame to resemble the original input sheet.

    - Start with input_cols order (only those present).
    - Insert extra_cols immediately after `add_after` if provided and present.
    - Append any remaining columns at the end.
    """
    df = df.copy()

    base = [c for c in input_cols if c in df.columns]
    extras = [c for c in (extra_cols or []) if c in df.columns and c not in base]

    if add_after and add_after in base and extras:
        idx = base.index(add_after) + 1
        ordered = base[:idx] + extras + base[idx:]
    else:
        ordered = base + extras

    remaining = [c for c in df.columns if c not in ordered]
    return df[ordered + remaining]





def recompute_common_rates_hit(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute rate stats after averaging counting components.

    Common mode uses AVG/ERA/WHIP, but many projection files also include OPS.
    If the necessary component columns are present, we recompute OPS as well so
    the aggregated rows stay internally consistent.
    """
    df = df.copy()

    # AVG = H / AB
    if "H" in df.columns and "AB" in df.columns:
        h = df["H"].to_numpy(dtype=float)
        ab = df["AB"].to_numpy(dtype=float)
        df["AVG"] = np.divide(h, ab, out=np.zeros_like(h), where=ab > 0)

    # OPS = OBP + SLG
    needed = {"H", "2B", "3B", "HR", "BB", "HBP", "AB", "SF"}
    if needed.issubset(df.columns):
        h = df["H"].to_numpy(dtype=float)
        b2 = df["2B"].to_numpy(dtype=float)
        b3 = df["3B"].to_numpy(dtype=float)
        hr = df["HR"].to_numpy(dtype=float)
        bb = df["BB"].to_numpy(dtype=float)
        hbp = df["HBP"].to_numpy(dtype=float)
        ab = df["AB"].to_numpy(dtype=float)
        sf = df["SF"].to_numpy(dtype=float)

        # TB = 1B + 2*2B + 3*3B + 4*HR, and 1B = H - 2B - 3B - HR
        # => TB = H + 2B + 2*3B + 3*HR
        tb = h + b2 + 2.0 * b3 + 3.0 * hr

        obp_den = ab + bb + hbp + sf
        obp = np.divide(h + bb + hbp, obp_den, out=np.zeros_like(obp_den), where=obp_den > 0)
        slg = np.divide(tb, ab, out=np.zeros_like(ab), where=ab > 0)

        df["OPS"] = obp + slg

    return df

def recompute_common_rates_pit(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "ER" in df.columns and "IP" in df.columns:
        er = df["ER"].to_numpy(dtype=float)
        ip = df["IP"].to_numpy(dtype=float)
        df["ERA"] = np.divide(9.0 * er, ip, out=np.full_like(ip, np.nan), where=ip > 0)
    if "H" in df.columns and "BB" in df.columns and "IP" in df.columns:
        h = df["H"].to_numpy(dtype=float)
        bb = df["BB"].to_numpy(dtype=float)
        ip = df["IP"].to_numpy(dtype=float)
        df["WHIP"] = np.divide(h + bb, ip, out=np.full_like(ip, np.nan), where=ip > 0)
    return df


def recompute_league_rates_hit(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if {"H", "2B", "3B", "HR"}.issubset(df.columns):
        df["TB"] = df["H"] + df["2B"] + 2 * df["3B"] + 3 * df["HR"]
    if {"H", "BB", "HBP", "AB", "SF"}.issubset(df.columns):
        df["OBP_num"] = df["H"] + df["BB"] + df["HBP"]
        df["OBP_den"] = df["AB"] + df["BB"] + df["HBP"] + df["SF"]
    if "H" in df.columns and "AB" in df.columns:
        h = df["H"].to_numpy(dtype=float)
        ab = df["AB"].to_numpy(dtype=float)
        df["AVG"] = np.divide(h, ab, out=np.zeros_like(h), where=ab > 0)
    if {"OBP_num", "OBP_den", "TB", "AB"}.issubset(df.columns):
        obp_den = df["OBP_den"].to_numpy(dtype=float)
        ab = df["AB"].to_numpy(dtype=float)
        obp = np.divide(df["OBP_num"].to_numpy(dtype=float), obp_den, out=np.zeros_like(obp_den), where=obp_den > 0)
        slg = np.divide(df["TB"].to_numpy(dtype=float), ab, out=np.zeros_like(ab), where=ab > 0)
        df["OPS"] = obp + slg
    return df


def recompute_league_rates_pit(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "ER" in df.columns and "IP" in df.columns:
        er = df["ER"].to_numpy(dtype=float)
        ip = df["IP"].to_numpy(dtype=float)
        df["ERA"] = np.divide(9.0 * er, ip, out=np.full_like(ip, np.nan), where=ip > 0)
    if "H" in df.columns and "BB" in df.columns and "IP" in df.columns:
        h = df["H"].to_numpy(dtype=float)
        bb = df["BB"].to_numpy(dtype=float)
        ip = df["IP"].to_numpy(dtype=float)
        df["WHIP"] = np.divide(h + bb, ip, out=np.full_like(ip, np.nan), where=ip > 0)
    return df

# Optional: gives globally optimal assignment for positional scarcity baseline
# NOTE: probing a submodule via find_spec("scipy.optimize") raises when scipy
# itself is not installed, so we guard on the package first.
if find_spec("scipy") is not None and find_spec("scipy.optimize") is not None:
    from scipy.optimize import linear_sum_assignment  # type: ignore
    HAVE_SCIPY = True
else:
    HAVE_SCIPY = False
    linear_sum_assignment = None


# ----------------------------
# Defaults: "common" dynasty roto
# ----------------------------

@dataclass
class CommonDynastyRotoSettings:
    n_teams: int = 12

    # Typical roto hitter lineup (NFBC-ish)
    hitter_slots: Dict[str, int] = field(default_factory=lambda: {
        "C": 1,
        "1B": 1,
        "2B": 1,
        "3B": 1,
        "SS": 1,
        "CI": 1,
        "MI": 1,
        "OF": 5,
        "UT": 1,
    })

    # Typical roto pitchers: just "P" slots (no SP/RP split)
    pitcher_slots: Dict[str, int] = field(default_factory=lambda: {
        "P": 9,
    })

    # Typical dynasty roster extras (you can tune these)
    bench_slots: int = 6
    minor_slots: int = 0
    ir_slots: int = 0

    # Many “standard” roto leagues do NOT enforce an IP cap.
    # Some do enforce an IP minimum for ERA/WHIP qualification; default off.
    ip_min: float = 0.0  # set e.g. 900 or 1000 if your league has it
    ip_max: Optional[float] = None  # no cap

    # Monte Carlo settings for SGP denominators
    sims_for_sgp: int = 200
    replacement_pitchers_n: int = 100

    # Dynasty parameters
    discount: float = 0.85
    horizon_years: int = 10

    # Two-way players: "max" = choose best of hitter/pitcher per year
    # (Most leagues effectively work like this for valuation purposes)
    two_way: str = "max"

    # Minor eligibility (best-effort inference, since projections file usually lacks career AB/IP):
    minor_ab_max: int = 130
    minor_ip_max: int = 50
    minor_age_max_hit: int = 25
    minor_age_max_pit: int = 26


# ----------------------------
# Column requirements (5x5)
# ----------------------------

HIT_COMPONENT_COLS = ["AB", "H", "R", "HR", "RBI", "SB"]
PIT_COMPONENT_COLS = ["IP", "W", "K", "SV", "ER", "H", "BB"]

HIT_CATS = ["R", "HR", "RBI", "SB", "AVG"]
PIT_CATS = ["W", "K", "SV", "ERA", "WHIP"]

COMMON_COLUMN_ALIASES = {
    "mlbteam": "Team",
    "team": "Team",
    "player_name": "Player",
    "name": "Player",
}

LEAGUE_COLUMN_ALIASES = {
    "team": "MLBTeam",
    "mlb_team": "MLBTeam",
    "player_name": "Player",
    "name": "Player",
}


def require_cols(df: pd.DataFrame, cols: List[str], sheet_name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Sheet '{sheet_name}' is missing required columns: {missing}")


def normalize_input_schema(df: pd.DataFrame, aliases: Dict[str, str]) -> pd.DataFrame:
    """Normalize incoming sheet columns (trim + alias mapping) while preserving existing names."""
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    lower_to_actual = {c.lower(): c for c in out.columns}
    rename_map: Dict[str, str] = {}
    for alias, canonical in aliases.items():
        actual = lower_to_actual.get(alias.lower())
        if actual and canonical not in out.columns:
            rename_map[actual] = canonical

    if rename_map:
        out = out.rename(columns=rename_map)
    return out


# ----------------------------
# Position parsing / eligibility
# ----------------------------

POSITION_SPLIT_RE = re.compile(r"[\s\/,;|+\-]+")


def _normalize_position_tokens(pos_str: str) -> Set[str]:
    """Split a raw position field into normalized uppercase tokens.

    Projection sources commonly mix delimiters ("/", ",", ";", "|") and
    inconsistent whitespace/casing. Normalizing once keeps the slot-eligibility
    logic resilient without changing downstream assumptions.
    """
    if pd.isna(pos_str):
        return set()

    normalized = POSITION_SPLIT_RE.sub("/", str(pos_str).upper())
    return {p.strip() for p in normalized.split("/") if p.strip()}


def parse_hit_positions(pos_str: str) -> Set[str]:
    tokens = _normalize_position_tokens(pos_str)
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
    return {aliases.get(token, token) for token in tokens}

def eligible_hit_slots(pos_set: Set[str]) -> Set[str]:
    """
    Common roto eligibility mapping:
      - UT for any hitter
      - CI if 1B or 3B
      - MI if 2B or SS
    """
    if not pos_set:
        return set()

    slots: Set[str] = {"UT"}
    if "C" in pos_set:
        slots.add("C")
    if "1B" in pos_set:
        slots.update({"1B", "CI"})
    if "3B" in pos_set:
        slots.update({"3B", "CI"})
    if "2B" in pos_set:
        slots.update({"2B", "MI"})
    if "SS" in pos_set:
        slots.update({"SS", "MI"})
    if "OF" in pos_set:
        slots.add("OF")
    if "CI" in pos_set:
        slots.add("CI")
    if "MI" in pos_set:
        slots.add("MI")
    return slots

def parse_pit_positions(pos_str: str) -> Set[str]:
    tokens = _normalize_position_tokens(pos_str)
    if not tokens:
        return set()

    aliases = {
        "RHP": "SP",
        "LHP": "SP",
    }
    return {aliases.get(token, token) for token in tokens}

def eligible_pit_slots(pos_set: Set[str]) -> Set[str]:
    """
    Default common setup uses P-only slots, so everyone eligible for "P".
    Still supports SP/RP if you customize pitcher_slots.
    """
    if not pos_set:
        return set()
    slots: Set[str] = {"P"}
    if "SP" in pos_set:
        slots.add("SP")
    if "RP" in pos_set:
        slots.add("RP")
    return slots


# ----------------------------
# Utility: z-scores for initial starter-pool weights
# (only used to construct baseline + starter pool; not the final valuation)
# ----------------------------

def zscore(s: pd.Series) -> pd.Series:
    x = s.astype(float)
    mu = float(x.mean())
    sd = float(x.std(ddof=0))
    if sd == 0.0 or np.isnan(sd):
        return x * 0.0
    return (x - mu) / sd

def initial_hitter_weight(df: pd.DataFrame) -> pd.Series:
    """
    Rough first-pass weight to select/assign starters with positional scarcity.
    Uses counting stats + "hits above average given AB" for AVG impact.
    """
    df = df.copy()
    ab_sum = float(df["AB"].sum())
    mean_avg = float(df["H"].sum() / ab_sum) if ab_sum > 0 else 0.0
    df["AVG_surplus_H"] = df["H"] - mean_avg * df["AB"]

    w = (
        zscore(df["R"]) +
        zscore(df["HR"]) +
        zscore(df["RBI"]) +
        zscore(df["SB"]) +
        zscore(df["AVG_surplus_H"])
    )
    return w

def initial_pitcher_weight(df: pd.DataFrame) -> pd.Series:
    """
    Rough first-pass weight for pitchers:
    counting stats + "runs prevented" (ERA) + "baserunners prevented" (WHIP),
    both scaled by IP to reflect volume.
    """
    df = df.copy()
    ip_sum = float(df["IP"].sum())
    mean_era = float(9.0 * df["ER"].sum() / ip_sum) if ip_sum > 0 else float(df["ERA"].mean())
    mean_whip = float((df["H"].sum() + df["BB"].sum()) / ip_sum) if ip_sum > 0 else float(df["WHIP"].mean())

    df["ERA_surplus_ER"] = (mean_era - df["ERA"]) * df["IP"] / 9.0
    df["WHIP_surplus"] = (mean_whip - df["WHIP"]) * df["IP"]

    w = (
        zscore(df["W"]) +
        zscore(df["K"]) +
        zscore(df["SV"]) +
        zscore(df["ERA_surplus_ER"]) +
        zscore(df["WHIP_surplus"])
    )
    return w


# ----------------------------
# Slot assignment for league-wide baseline (positional scarcity)
# ----------------------------

def expand_slot_counts(per_team: Dict[str, int], n_teams: int) -> Dict[str, int]:
    return {slot: cnt * n_teams for slot, cnt in per_team.items()}

def build_slot_list(slot_counts: Dict[str, int]) -> List[str]:
    slots: List[str] = []
    for s, c in slot_counts.items():
        slots.extend([s] * c)
    return slots

def build_team_slot_template(per_team: Dict[str, int]) -> List[str]:
    slots: List[str] = []
    for s, c in per_team.items():
        slots.extend([s] * c)
    return slots


def validate_assigned_slots(
    assigned: pd.DataFrame,
    slot_counts: Dict[str, int],
    elig_sets: List[Set[str]],
    mode_label: str,
) -> None:
    """Ensure slot assignment is complete and eligibility-valid with clear diagnostics."""
    if assigned.empty and sum(slot_counts.values()) == 0:
        return

    idx_col = "_assign_idx"
    if idx_col not in assigned.columns:
        raise ValueError(f"{mode_label} assignment missing internal index column '{idx_col}'.")

    bad_rows: List[Tuple[str, str]] = []
    for player_idx, slot, player in zip(
        assigned[idx_col].to_numpy(dtype=int),
        assigned["AssignedSlot"].astype(str).to_numpy(),
        assigned.get("Player", pd.Series(["<unknown>"] * len(assigned))).astype(str).to_numpy(),
    ):
        if player_idx < 0 or player_idx >= len(elig_sets) or slot not in elig_sets[player_idx]:
            bad_rows.append((player, slot))

    if bad_rows:
        preview = ", ".join([f"{p}->{s}" for p, s in bad_rows[:5]])
        raise ValueError(
            f"{mode_label} assignment produced ineligible player-slot mappings. "
            f"Examples: {preview}. Check position eligibility and slot settings."
        )

    actual_counts = assigned["AssignedSlot"].value_counts().to_dict()
    missing = {slot: need - int(actual_counts.get(slot, 0)) for slot, need in slot_counts.items() if int(actual_counts.get(slot, 0)) < need}
    if missing:
        details = ", ".join([f"{slot}: short {short}" for slot, short in sorted(missing.items())])
        raise ValueError(f"{mode_label} assignment cannot fill required slots ({details}).")

def assign_players_to_slots(
    df: pd.DataFrame,
    slot_counts: Dict[str, int],
    eligible_func: Callable[[Set[str]], Set[str]],
    weight_col: str = "weight",
) -> pd.DataFrame:
    """
    Choose exactly (sum slot_counts) distinct players and assign each to a slot
    to maximize total weight.
    - Uses Hungarian algorithm if scipy is available.
    - Falls back to a reasonable greedy method if not.
    """
    df = df.copy().reset_index(drop=True)
    df["_assign_idx"] = np.arange(len(df))

    slots = build_slot_list(slot_counts)
    n_slots = len(slots)
    if n_slots == 0:
        return df.iloc[0:0].copy()

    weights = df[weight_col].to_numpy(dtype=float)
    n_players = len(df)

    if n_players < n_slots:
        raise ValueError(f"Not enough players ({n_players}) to fill required slots ({n_slots}).")

    elig_sets: List[Set[str]] = []
    parse_func = parse_hit_positions if eligible_func == eligible_hit_slots else parse_pit_positions
    for pos_str in df["Pos"]:
        elig_sets.append(eligible_func(parse_func(pos_str)))

    for slot, req in slot_counts.items():
        elig_count = sum(1 for e in elig_sets if slot in e)
        if elig_count < req:
            raise ValueError(
                f"Cannot fill slot '{slot}': need {req} eligible players but only found {elig_count}."
            )

    if HAVE_SCIPY:
        BIG = 1e6
        cost = np.full((n_slots, n_players), BIG, dtype=float)
        for i, slot in enumerate(slots):
            for j in range(n_players):
                if slot in elig_sets[j]:
                    cost[i, j] = -weights[j]  # maximize weight
        row_ind, col_ind = linear_sum_assignment(cost)  # type: ignore

        chosen_cost = cost[row_ind, col_ind]
        infeasible_rows = row_ind[chosen_cost >= (BIG / 2.0)]
        if len(infeasible_rows) > 0:
            missing: Dict[str, int] = {}
            for row_idx in infeasible_rows:
                slot = slots[int(row_idx)]
                missing[slot] = missing.get(slot, 0) + 1
            details = ", ".join([f"{slot}: short {short}" for slot, short in sorted(missing.items())])
            raise ValueError(f"Common mode assignment cannot fill required slots ({details}).")

        assigned = df.loc[col_ind].copy()
        assigned["AssignedSlot"] = [slots[i] for i in row_ind]
        validate_assigned_slots(assigned, slot_counts, elig_sets, mode_label="Common mode")
        return assigned.drop(columns=["_assign_idx"])

    # Greedy fallback (works, but not globally optimal)
    remaining = set(range(n_players))

    # Fill scarcer slots first (fewer eligible players)
    slot_order = sorted(
        range(n_slots),
        key=lambda i: sum(1 for j in remaining if slots[i] in elig_sets[j])
    )

    chosen: List[Tuple[int, str]] = []
    for i in slot_order:
        slot = slots[i]
        candidates = [j for j in remaining if slot in elig_sets[j]]
        if not candidates:
            continue
        best = max(candidates, key=lambda j: weights[j])
        remaining.remove(best)
        chosen.append((best, slot))

    assigned = df.loc[[j for j, _ in chosen]].copy()
    assigned["AssignedSlot"] = [slot for _, slot in chosen]
    validate_assigned_slots(assigned, slot_counts, elig_sets, mode_label="Common mode")
    return assigned.drop(columns=["_assign_idx"])


SLOT_SHORTAGE_RE = re.compile(r"Cannot fill slot '([^']+)': need (\d+) eligible players but only found (\d+)\.")
ASSIGN_SHORT_RE = re.compile(r"([A-Za-z0-9]+): short (\d+)")
NOT_ENOUGH_PLAYERS_RE = re.compile(r"Not enough players \((\d+)\) to fill required slots \((\d+)\)\.")
VACANCY_WEIGHT = -1e5


def _infer_slot_shortages_from_assignment_error(message: str, slot_counts: Dict[str, int]) -> Dict[str, int]:
    shortages: Dict[str, int] = {}

    slot_match = SLOT_SHORTAGE_RE.search(message)
    if slot_match:
        slot = slot_match.group(1)
        need = int(slot_match.group(2))
        found = int(slot_match.group(3))
        if slot in slot_counts and need > found:
            shortages[slot] = need - found
        return shortages

    if "cannot fill required slots" in message.lower():
        for slot, short_text in ASSIGN_SHORT_RE.findall(message):
            short = int(short_text)
            if slot in slot_counts and short > 0:
                shortages[slot] = shortages.get(slot, 0) + short
        if shortages:
            return shortages

    count_match = NOT_ENOUGH_PLAYERS_RE.search(message)
    if count_match:
        available = int(count_match.group(1))
        required = int(count_match.group(2))
        short = max(required - available, 0)
        if short > 0:
            if slot_counts.get("UT", 0) > 0:
                shortages["UT"] = short
            elif slot_counts.get("P", 0) > 0:
                shortages["P"] = short
            else:
                fallback_slot = max(slot_counts.items(), key=lambda item: int(item[1]))[0]
                shortages[fallback_slot] = short

    return shortages


def _build_vacancy_rows(
    *,
    year: int,
    side_label: str,
    shortages: Dict[str, int],
    stat_cols: List[str],
    weight_col: str,
    existing_cols: List[str],
    existing_count: int,
    attempt: int,
) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for slot, short in shortages.items():
        for i in range(int(short)):
            idx = existing_count + len(rows) + 1
            row: Dict[str, object] = {
                "Player": f"__VACANT_{side_label.upper()}_{year}_{slot}_{attempt}_{idx}",
                "Year": year,
                "Team": "VAC",
                "Age": 0,
                "Pos": slot,
                weight_col: VACANCY_WEIGHT,
            }
            for stat_col in stat_cols:
                row[stat_col] = 0.0
            rows.append(row)

    if not rows:
        return pd.DataFrame(columns=existing_cols)

    out = pd.DataFrame(rows)
    for col in existing_cols:
        if col not in out.columns:
            out[col] = np.nan
    return out[existing_cols]


def assign_players_to_slots_with_vacancy_fill(
    df: pd.DataFrame,
    slot_counts: Dict[str, int],
    eligible_func: Callable[[Set[str]], Set[str]],
    *,
    stat_cols: List[str],
    year: int,
    side_label: str,
    weight_col: str = "weight",
    max_attempts: int = 8,
) -> pd.DataFrame:
    """Assign players, auto-filling unfillable slots with zero-value vacancy rows.

    This keeps common-mode calculations runnable in deep settings where late-horizon
    years do not have enough eligible players at one or more specific positions.
    """
    working = df.copy()
    if weight_col not in working.columns:
        working[weight_col] = 0.0

    for attempt in range(1, max_attempts + 1):
        try:
            return assign_players_to_slots(
                working,
                slot_counts,
                eligible_func,
                weight_col=weight_col,
            )
        except ValueError as exc:
            shortages = _infer_slot_shortages_from_assignment_error(str(exc), slot_counts)
            if not shortages:
                raise
            vacancy_rows = _build_vacancy_rows(
                year=year,
                side_label=side_label,
                shortages=shortages,
                stat_cols=stat_cols,
                weight_col=weight_col,
                existing_cols=list(working.columns),
                existing_count=len(working),
                attempt=attempt,
            )
            if vacancy_rows.empty:
                raise
            vacancy_rows = vacancy_rows.dropna(axis=1, how="all")
            working = pd.concat([working, vacancy_rows], ignore_index=True, sort=False)

    return assign_players_to_slots(
        working,
        slot_counts,
        eligible_func,
        weight_col=weight_col,
    )


# ----------------------------
# Team stat calculations (5x5)
# ----------------------------

def team_avg(H: float, AB: float) -> float:
    return float(H / AB) if AB > 0 else 0.0

def team_era(ER: float, IP: float) -> float:
    return float(9.0 * ER / IP) if IP > 0 else float("nan")

def team_whip(H: float, BB: float, IP: float) -> float:
    return float((H + BB) / IP) if IP > 0 else float("nan")


def common_replacement_pitcher_rates(
    all_pit_df: pd.DataFrame,
    assigned_pit_df: pd.DataFrame,
    n_rep: int,
) -> Dict[str, float]:
    """Per-inning replacement rates from the best available non-starter pitchers."""
    assigned_players = set(assigned_pit_df["Player"])
    rep = all_pit_df[~all_pit_df["Player"].isin(assigned_players)].copy()
    rep = rep.sort_values("weight", ascending=False).head(max(int(n_rep), 1))

    ip = float(rep["IP"].sum()) if not rep.empty else 0.0
    if ip <= 0:
        return {k: 0.0 for k in ["W", "K", "SV", "ER", "H", "BB"]}

    return {
        "W": float(rep["W"].sum() / ip),
        "K": float(rep["K"].sum() / ip),
        "SV": float(rep["SV"].sum() / ip),
        "ER": float(rep["ER"].sum() / ip),
        "H": float(rep["H"].sum() / ip),
        "BB": float(rep["BB"].sum() / ip),
    }


def common_apply_pitching_bounds(
    totals: Dict[str, float],
    lg: CommonDynastyRotoSettings,
    rep_rates: Optional[Dict[str, float]],
) -> Dict[str, float]:
    """Apply optional IP cap/fill and IP-min qualification to common-mode pitching totals."""
    out = {k: float(totals.get(k, 0.0)) for k in PIT_COMPONENT_COLS}
    ip = float(out["IP"])

    if lg.ip_max is not None:
        ip_cap = float(lg.ip_max)

        # If over cap, scale all counting components down to cap.
        if ip > ip_cap and ip > 0:
            factor = ip_cap / ip
            for col in PIT_COMPONENT_COLS:
                out[col] = float(out[col]) * factor
            ip = ip_cap

        # If under cap, assume streamable replacement innings.
        if ip < ip_cap and rep_rates is not None:
            add = ip_cap - ip
            out["IP"] = ip_cap
            for col in ["W", "K", "SV", "ER", "H", "BB"]:
                out[col] = float(out[col]) + add * float(rep_rates.get(col, 0.0))
            ip = ip_cap

    out["ERA"] = team_era(out["ER"], ip)
    out["WHIP"] = team_whip(out["H"], out["BB"], ip)

    # Optional IP minimum qualification rule (default OFF)
    if lg.ip_min and lg.ip_min > 0 and ip < lg.ip_min:
        out["ERA"] = 99.0
        out["WHIP"] = 5.0

    return out


# ----------------------------
# Monte Carlo SGP denominators
# ----------------------------

def simulate_sgp_hit(assigned_hit: pd.DataFrame, lg: CommonDynastyRotoSettings, rng: np.random.Generator) -> Dict[str, float]:
    """
    Estimates how many of each stat ~= 1 roto point (SGP denominator),
    by simulating random allocations of the "starter pool" to 12 teams.
    """
    per_team = lg.hitter_slots
    diffs = {c: [] for c in HIT_CATS}

    groups = {slot: assigned_hit[assigned_hit["AssignedSlot"] == slot] for slot in per_team.keys()}

    for _ in range(lg.sims_for_sgp):
        AB = np.zeros(lg.n_teams)
        H = np.zeros(lg.n_teams)
        R = np.zeros(lg.n_teams)
        HR = np.zeros(lg.n_teams)
        RBI = np.zeros(lg.n_teams)
        SB = np.zeros(lg.n_teams)

        for slot, cnt in per_team.items():
            df_slot = groups[slot]
            idx = rng.permutation(len(df_slot))
            arr = df_slot.iloc[idx][HIT_COMPONENT_COLS].to_numpy(dtype=float)
            arr = arr.reshape(lg.n_teams, cnt, len(HIT_COMPONENT_COLS))
            sums = arr.sum(axis=1)

            AB += sums[:, 0]
            H += sums[:, 1]
            R += sums[:, 2]
            HR += sums[:, 3]
            RBI += sums[:, 4]
            SB += sums[:, 5]

        AVG = np.divide(H, AB, out=np.zeros_like(H), where=AB > 0)

        vals = {"R": R, "HR": HR, "RBI": RBI, "SB": SB, "AVG": AVG}
        for c in HIT_CATS:
            x = vals[c].astype(float)
            x_sorted = np.sort(x)[::-1]  # higher is better
            diffs[c].append(float(np.mean(np.abs(np.diff(x_sorted)))))

    return {c: float(np.mean(diffs[c])) for c in HIT_CATS}

def simulate_sgp_pit(
    assigned_pit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng: np.random.Generator,
    rep_rates: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    diffs = {c: [] for c in PIT_CATS}
    per_team = lg.pitcher_slots
    groups = {slot: assigned_pit[assigned_pit["AssignedSlot"] == slot] for slot in per_team.keys()}

    for _ in range(lg.sims_for_sgp):
        IP = np.zeros(lg.n_teams)
        W = np.zeros(lg.n_teams)
        K = np.zeros(lg.n_teams)
        SV = np.zeros(lg.n_teams)
        ER = np.zeros(lg.n_teams)
        H = np.zeros(lg.n_teams)
        BB = np.zeros(lg.n_teams)

        for slot, cnt in per_team.items():
            df_slot = groups[slot]
            idx = rng.permutation(len(df_slot))
            arr = df_slot.iloc[idx][PIT_COMPONENT_COLS].to_numpy(dtype=float)
            arr = arr.reshape(lg.n_teams, cnt, len(PIT_COMPONENT_COLS))
            sums = arr.sum(axis=1)

            IP += sums[:, 0]
            W += sums[:, 1]
            K += sums[:, 2]
            SV += sums[:, 3]
            ER += sums[:, 4]
            H += sums[:, 5]
            BB += sums[:, 6]

        vals = {c: [] for c in PIT_CATS}
        for t in range(lg.n_teams):
            bounded = common_apply_pitching_bounds(
                {
                    "IP": float(IP[t]),
                    "W": float(W[t]),
                    "K": float(K[t]),
                    "SV": float(SV[t]),
                    "ER": float(ER[t]),
                    "H": float(H[t]),
                    "BB": float(BB[t]),
                },
                lg,
                rep_rates,
            )
            vals["W"].append(float(bounded["W"]))
            vals["K"].append(float(bounded["K"]))
            vals["SV"].append(float(bounded["SV"]))
            vals["ERA"].append(float(bounded["ERA"]))
            vals["WHIP"].append(float(bounded["WHIP"]))

        for c in PIT_CATS:
            x = np.array(vals[c], dtype=float)
            x_sorted = np.sort(x) if c in {"ERA", "WHIP"} else np.sort(x)[::-1]
            diffs[c].append(float(np.mean(np.abs(np.diff(x_sorted)))))

    return {c: float(np.mean(diffs[c])) for c in PIT_CATS}


# ----------------------------
# Year context + player year values
# ----------------------------

def compute_year_context(year: int, bat: pd.DataFrame, pit: pd.DataFrame, lg: CommonDynastyRotoSettings, rng_seed: Optional[int] = None) -> dict:
    bat_y = bat[bat["Year"] == year].copy()
    pit_y = pit[pit["Year"] == year].copy()

    # Clean numeric NaNs
    for c in HIT_COMPONENT_COLS:
        bat_y[c] = bat_y[c].fillna(0.0)
    for c in PIT_COMPONENT_COLS:
        pit_y[c] = pit_y[c].fillna(0.0)

    # Starter-pool candidates (must have playing time)
    bat_play = bat_y[bat_y["AB"] > 0].copy()
    pit_play = pit_y[pit_y["IP"] > 0].copy()

    if bat_play.empty:
        raise ValueError(
            f"Year {year}: no hitters with AB > 0 after filtering. Check Year values and AB projections."
        )
    if pit_play.empty:
        raise ValueError(
            f"Year {year}: no pitchers with IP > 0 after filtering. Check Year values and IP projections."
        )

    # Initial weights to define the league baseline pool/positional scarcity
    bat_play["weight"] = initial_hitter_weight(bat_play)
    pit_play["weight"] = initial_pitcher_weight(pit_play)

    league_hit_slots = expand_slot_counts(lg.hitter_slots, lg.n_teams)
    league_pit_slots = expand_slot_counts(lg.pitcher_slots, lg.n_teams)

    assigned_hit = assign_players_to_slots_with_vacancy_fill(
        bat_play,
        league_hit_slots,
        eligible_hit_slots,
        stat_cols=HIT_COMPONENT_COLS,
        year=year,
        side_label="hitter",
        weight_col="weight",
    )
    assigned_pit = assign_players_to_slots_with_vacancy_fill(
        pit_play,
        league_pit_slots,
        eligible_pit_slots,
        stat_cols=PIT_COMPONENT_COLS,
        year=year,
        side_label="pitcher",
        weight_col="weight",
    )

    baseline_hit = assigned_hit.groupby("AssignedSlot")[HIT_COMPONENT_COLS].mean()
    baseline_pit = assigned_pit.groupby("AssignedSlot")[PIT_COMPONENT_COLS].mean()

    # Baseline "average team" totals
    team_hit_slots = build_team_slot_template(lg.hitter_slots)
    team_pit_slots = build_team_slot_template(lg.pitcher_slots)

    base_hit_tot = baseline_hit.loc[team_hit_slots].sum()
    base_avg = team_avg(float(base_hit_tot["H"]), float(base_hit_tot["AB"]))

    base_pit_tot = baseline_pit.loc[team_pit_slots].sum()
    rep_rates = common_replacement_pitcher_rates(
        pit_play,
        assigned_pit,
        n_rep=lg.replacement_pitchers_n,
    )
    base_pit_bounded = common_apply_pitching_bounds(
        {col: float(base_pit_tot[col]) for col in PIT_COMPONENT_COLS},
        lg,
        rep_rates,
    )

    # SGP denominators by simulation
    seed = year if rng_seed is None else int(rng_seed)
    rng_hit = np.random.default_rng(seed)
    rng_pit = np.random.default_rng(seed + 1)
    sgp_hit = simulate_sgp_hit(assigned_hit, lg, rng_hit)
    sgp_pit = simulate_sgp_pit(assigned_pit, lg, rng_pit, rep_rates=rep_rates)

    return {
        "year": year,
        "bat_y": bat_y,
        "pit_y": pit_y,
        "baseline_hit": baseline_hit,
        "baseline_pit": baseline_pit,
        "base_hit_tot": base_hit_tot,
        "base_avg": base_avg,
        "base_pit_tot": base_pit_tot,
        "base_pit_bounded": base_pit_bounded,
        "rep_rates": rep_rates,
        "sgp_hit": sgp_hit,
        "sgp_pit": sgp_pit,
    }

def compute_year_player_values(ctx: dict, lg: CommonDynastyRotoSettings) -> Tuple[pd.DataFrame, pd.DataFrame]:
    year = int(ctx["year"])
    bat_y = ctx["bat_y"]
    pit_y = ctx["pit_y"]

    baseline_hit = ctx["baseline_hit"]
    baseline_pit = ctx["baseline_pit"]
    base_hit_tot = ctx["base_hit_tot"]
    base_avg = float(ctx["base_avg"])

    base_pit_tot = ctx["base_pit_tot"]
    base_pit_bounded = dict(ctx["base_pit_bounded"])
    rep_rates = ctx.get("rep_rates")

    sgp_hit = ctx["sgp_hit"]
    sgp_pit = ctx["sgp_pit"]

    # --- Hitters: best eligible slot vs average starter at that slot ---
    hit_rows = []
    for row in bat_y.itertuples(index=False):
        pos_set = parse_hit_positions(getattr(row, "Pos", ""))
        slots = eligible_hit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_hit.index:
                continue
            b = baseline_hit.loc[slot]

            new_tot = base_hit_tot.copy()
            for col in HIT_COMPONENT_COLS:
                new_tot[col] = new_tot[col] - b[col] + getattr(row, col)

            new_avg = team_avg(float(new_tot["H"]), float(new_tot["AB"]))

            delta = {
                "R": float(new_tot["R"] - base_hit_tot["R"]),
                "HR": float(new_tot["HR"] - base_hit_tot["HR"]),
                "RBI": float(new_tot["RBI"] - base_hit_tot["RBI"]),
                "SB": float(new_tot["SB"] - base_hit_tot["SB"]),
                "AVG": float(new_avg - base_avg),
            }

            val = 0.0
            for c in HIT_CATS:
                denom = float(sgp_hit[c])
                val += (delta[c] / denom) if denom else 0.0

            if val > best_val:
                best_val = val
                best_slot = slot

        hit_rows.append({
            "Player": getattr(row, "Player"),
            "Year": year,
            "Type": "H",
            "Team": getattr(row, "Team", np.nan),
            "Age": getattr(row, "Age", np.nan),
            "Pos": getattr(row, "Pos", np.nan),
            "BestSlot": best_slot,
            "YearValue": float(best_val),
        })

    hit_vals = pd.DataFrame(hit_rows)

    # --- Pitchers: best eligible slot (usually just P) vs average starter at that slot ---
    pit_rows = []
    for row in pit_y.itertuples(index=False):
        pos_set = parse_pit_positions(getattr(row, "Pos", ""))
        slots = eligible_pit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_pit.index:
                continue
            b = baseline_pit.loc[slot]

            new_tot = base_pit_tot.copy()
            for col in PIT_COMPONENT_COLS:
                new_tot[col] = new_tot[col] - b[col] + getattr(row, col)

            new_tot_bounded = common_apply_pitching_bounds(
                {col: float(new_tot[col]) for col in PIT_COMPONENT_COLS},
                lg,
                rep_rates,
            )

            delta = {
                "W": float(new_tot_bounded["W"] - base_pit_bounded["W"]),
                "K": float(new_tot_bounded["K"] - base_pit_bounded["K"]),
                "SV": float(new_tot_bounded["SV"] - base_pit_bounded["SV"]),
                "ERA": float(base_pit_bounded["ERA"] - new_tot_bounded["ERA"]),       # lower is better
                "WHIP": float(base_pit_bounded["WHIP"] - new_tot_bounded["WHIP"]),    # lower is better
            }

            val = 0.0
            for c in PIT_CATS:
                denom = float(sgp_pit[c])
                val += (delta[c] / denom) if denom else 0.0

            if val > best_val:
                best_val = val
                best_slot = slot

        pit_rows.append({
            "Player": getattr(row, "Player"),
            "Year": year,
            "Type": "P",
            "Team": getattr(row, "Team", np.nan),
            "Age": getattr(row, "Age", np.nan),
            "Pos": getattr(row, "Pos", np.nan),
            "BestSlot": best_slot,
            "YearValue": float(best_val),
        })

    pit_vals = pd.DataFrame(pit_rows)
    return hit_vals, pit_vals


def compute_replacement_baselines(
    ctx: dict,
    lg: CommonDynastyRotoSettings,
    rostered_players: Set[str],
    n_repl: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Build per-slot replacement baselines from the unrostered pool."""
    n_repl = int(n_repl or lg.n_teams)

    bat_y = ctx["bat_y"].copy()
    pit_y = ctx["pit_y"].copy()

    for c in HIT_COMPONENT_COLS:
        bat_y[c] = bat_y[c].fillna(0.0)
    for c in PIT_COMPONENT_COLS:
        pit_y[c] = pit_y[c].fillna(0.0)

    bat_y["weight"] = initial_hitter_weight(bat_y)
    pit_y["weight"] = initial_pitcher_weight(pit_y)

    fa_hit = bat_y[(~bat_y["Player"].isin(rostered_players)) & (bat_y["AB"] > 0)].copy()
    fa_pit = pit_y[(~pit_y["Player"].isin(rostered_players)) & (pit_y["IP"] > 0)].copy()

    fa_hit["elig"] = fa_hit["Pos"].apply(lambda p: eligible_hit_slots(parse_hit_positions(p)))
    fa_pit["elig"] = fa_pit["Pos"].apply(lambda p: eligible_pit_slots(parse_pit_positions(p)))

    baseline_hit_avg = ctx["baseline_hit"]
    baseline_pit_avg = ctx["baseline_pit"]

    repl_hit_rows: List[dict] = []
    for slot in baseline_hit_avg.index:
        cand = (
            fa_hit[fa_hit["elig"].apply(lambda s: slot in s)]
            .sort_values("weight", ascending=False)
            .head(n_repl)
        )
        repl = baseline_hit_avg.loc[slot] if len(cand) == 0 else cand[HIT_COMPONENT_COLS].mean()
        row = {c: float(repl.get(c, 0.0)) for c in HIT_COMPONENT_COLS}
        row["AssignedSlot"] = slot
        repl_hit_rows.append(row)

    repl_hit = pd.DataFrame(repl_hit_rows).set_index("AssignedSlot")

    repl_pit_rows: List[dict] = []
    for slot in baseline_pit_avg.index:
        cand = (
            fa_pit[fa_pit["elig"].apply(lambda s: slot in s)]
            .sort_values("weight", ascending=False)
            .head(n_repl)
        )
        repl = baseline_pit_avg.loc[slot] if len(cand) == 0 else cand[PIT_COMPONENT_COLS].mean()
        row = {c: float(repl.get(c, 0.0)) for c in PIT_COMPONENT_COLS}
        row["AssignedSlot"] = slot
        repl_pit_rows.append(row)

    repl_pit = pd.DataFrame(repl_pit_rows).set_index("AssignedSlot")
    return repl_hit, repl_pit


def compute_year_player_values_vs_replacement(
    ctx: dict,
    lg: CommonDynastyRotoSettings,
    repl_hit: pd.DataFrame,
    repl_pit: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Compute per-year values as marginal roto points above replacement."""
    year = int(ctx["year"])
    bat_y = ctx["bat_y"]
    pit_y = ctx["pit_y"]

    baseline_hit_avg = ctx["baseline_hit"]
    baseline_pit_avg = ctx["baseline_pit"]
    base_hit_tot_avg = ctx["base_hit_tot"]
    base_pit_tot_avg = ctx["base_pit_tot"]
    rep_rates = ctx.get("rep_rates")

    sgp_hit = ctx["sgp_hit"]
    sgp_pit = ctx["sgp_pit"]

    hit_rows = []
    for row in bat_y.itertuples(index=False):
        pos_set = parse_hit_positions(getattr(row, "Pos", ""))
        slots = eligible_hit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_hit_avg.index or slot not in repl_hit.index:
                continue

            b_avg = baseline_hit_avg.loc[slot]
            b_rep = repl_hit.loc[slot]

            base_tot = base_hit_tot_avg.copy()
            new_tot = base_hit_tot_avg.copy()
            for col in HIT_COMPONENT_COLS:
                base_tot[col] = base_tot[col] - b_avg[col] + b_rep[col]
                new_tot[col] = new_tot[col] - b_avg[col] + getattr(row, col, 0.0)

            base_avg = team_avg(float(base_tot["H"]), float(base_tot["AB"]))
            new_avg = team_avg(float(new_tot["H"]), float(new_tot["AB"]))

            delta = {
                "R": float(new_tot["R"] - base_tot["R"]),
                "HR": float(new_tot["HR"] - base_tot["HR"]),
                "RBI": float(new_tot["RBI"] - base_tot["RBI"]),
                "SB": float(new_tot["SB"] - base_tot["SB"]),
                "AVG": float(new_avg - base_avg),
            }

            val = 0.0
            for c in HIT_CATS:
                denom = float(sgp_hit[c])
                val += (delta[c] / denom) if denom else 0.0

            if val > best_val:
                best_val = val
                best_slot = slot

        hit_rows.append({
            "Player": getattr(row, "Player"),
            "Year": year,
            "Type": "H",
            "Team": getattr(row, "Team", np.nan),
            "Age": getattr(row, "Age", np.nan),
            "Pos": getattr(row, "Pos", np.nan),
            "BestSlot": best_slot,
            "YearValue": float(best_val),
        })

    hit_vals = pd.DataFrame(hit_rows)

    pit_rows = []
    for row in pit_y.itertuples(index=False):
        pos_set = parse_pit_positions(getattr(row, "Pos", ""))
        slots = eligible_pit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_pit_avg.index or slot not in repl_pit.index:
                continue

            b_avg = baseline_pit_avg.loc[slot]
            b_rep = repl_pit.loc[slot]

            base_raw = {c: float(base_pit_tot_avg[c]) for c in PIT_COMPONENT_COLS}
            new_raw = {c: float(base_pit_tot_avg[c]) for c in PIT_COMPONENT_COLS}
            for col in PIT_COMPONENT_COLS:
                base_raw[col] = base_raw[col] - float(b_avg[col]) + float(b_rep[col])
                new_raw[col] = new_raw[col] - float(b_avg[col]) + float(getattr(row, col, 0.0))

            base_bounded = common_apply_pitching_bounds(base_raw, lg, rep_rates)
            new_bounded = common_apply_pitching_bounds(new_raw, lg, rep_rates)

            delta = {
                "W": float(new_bounded["W"] - base_bounded["W"]),
                "K": float(new_bounded["K"] - base_bounded["K"]),
                "SV": float(new_bounded["SV"] - base_bounded["SV"]),
                "ERA": float(base_bounded["ERA"] - new_bounded["ERA"]),
                "WHIP": float(base_bounded["WHIP"] - new_bounded["WHIP"]),
            }

            val = 0.0
            for c in PIT_CATS:
                denom = float(sgp_pit[c])
                val += (delta[c] / denom) if denom else 0.0

            if val > best_val:
                best_val = val
                best_slot = slot

        pit_rows.append({
            "Player": getattr(row, "Player"),
            "Year": year,
            "Type": "P",
            "Team": getattr(row, "Team", np.nan),
            "Age": getattr(row, "Age", np.nan),
            "Pos": getattr(row, "Pos", np.nan),
            "BestSlot": best_slot,
            "YearValue": float(best_val),
        })

    pit_vals = pd.DataFrame(pit_rows)
    return hit_vals, pit_vals


def combine_two_way(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame:
    merged = pd.merge(
        hit_vals[["Player", "Year", "YearValue", "BestSlot", "Team", "Age", "Pos"]],
        pit_vals[["Player", "Year", "YearValue", "BestSlot", "Team", "Age", "Pos"]],
        on=["Player", "Year"],
        how="outer",
        suffixes=("_hit", "_pit"),
    )

    out_vals = []
    out_slots = []

    for _, r in merged.iterrows():
        hv = r.get("YearValue_hit")
        pv = r.get("YearValue_pit")

        if pd.isna(hv) and pd.isna(pv):
            out_vals.append(np.nan)
            out_slots.append(None)
            continue
        if pd.isna(hv):
            out_vals.append(float(pv))
            out_slots.append(r.get("BestSlot_pit"))
            continue
        if pd.isna(pv):
            out_vals.append(float(hv))
            out_slots.append(r.get("BestSlot_hit"))
            continue

        hv = float(hv)
        pv = float(pv)

        if two_way == "sum":
            out_vals.append(hv + pv)
            out_slots.append(f"{r.get('BestSlot_hit')}+{r.get('BestSlot_pit')}")
        else:  # "max"
            if hv >= pv:
                out_vals.append(hv)
                out_slots.append(r.get("BestSlot_hit"))
            else:
                out_vals.append(pv)
                out_slots.append(r.get("BestSlot_pit"))

    merged["YearValue"] = out_vals
    merged["BestSlot"] = out_slots
    merged["Team"] = merged["Team_hit"].combine_first(merged["Team_pit"])
    merged["Pos"] = merged["Pos_hit"].combine_first(merged["Pos_pit"])
    merged["Age"] = merged["Age_hit"].combine_first(merged["Age_pit"])

    return merged[["Player", "Year", "YearValue", "BestSlot", "Team", "Pos", "Age"]]


# ----------------------------
# Dynasty aggregation + centering
# ----------------------------


# ----------------------------
# Dynasty aggregation utilities
# ----------------------------

def dynasty_keep_or_drop_value(values: List[float], years: List[int], discount: float) -> float:
    """Compute the optimal discounted value of owning a player with a drop option.

    At the start of each season you either:
      - **Keep** the player for that season (receiving that season's `values[i]`, which may be negative), or
      - **Drop** the player permanently and receive 0 from that season onward.

    Discounting is applied between seasons using `discount ** year_gap`, where
    `year_gap = years[i+1] - years[i]`.

    This implements the one-dimensional dynamic program:

        F[i] = max(0, values[i] + discount**(gap) * F[i+1])

    Returns the optimal value in "start-year" units (i.e., relative to `years[0]`).
    """
    if not years or not values:
        return 0.0
    if len(values) != len(years):
        raise ValueError("values and years must have the same length")
    if len(years) == 1:
        return float(max(values[0], 0.0))

    f_next = 0.0
    for i in range(len(years) - 1, -1, -1):
        v = float(values[i])
        if i == len(years) - 1:
            hold = v
        else:
            gap = int(years[i + 1]) - int(years[i])
            if gap < 0:
                raise ValueError("years must be increasing")
            hold = v + (discount ** gap) * f_next
        f_next = max(0.0, hold)

    return float(f_next)

def infer_minor_eligible(bat: pd.DataFrame, pit: pd.DataFrame, lg: CommonDynastyRotoSettings, start_year: int) -> pd.DataFrame:
    """
    Best-effort inference from projections only (since career AB/IP often not present):
      - hitter: projected AB <= 130 and Age <= 25
      - pitcher: projected IP <= 50 and Age <= 26
    """
    bat_y = bat[bat["Year"] == start_year][["Player", "AB", "Age"]].copy()
    pit_y = pit[pit["Year"] == start_year][["Player", "IP", "Age"]].copy()

    bat_y = bat_y.groupby("Player", as_index=False).agg({"AB": "max", "Age": "min"})
    pit_y = pit_y.groupby("Player", as_index=False).agg({"IP": "max", "Age": "min"})

    m = pd.merge(bat_y, pit_y, on="Player", how="outer", suffixes=("_hit", "_pit"))
    m["Age"] = m["Age_hit"].combine_first(m["Age_pit"])
    m["AB"] = m["AB"].fillna(0.0)
    m["IP"] = m["IP"].fillna(0.0)

    m["minor_eligible"] = (
        ((m["AB"] > 0) & (m["AB"] <= lg.minor_ab_max) & (m["Age"] <= lg.minor_age_max_hit))
        | ((m["IP"] > 0) & (m["IP"] <= lg.minor_ip_max) & (m["Age"] <= lg.minor_age_max_pit))
    )

    return m[["Player", "minor_eligible"]]



def _fillna_bool(series: pd.Series, default: bool = False) -> pd.Series:
    """
    Coerce a Series to boolean and fill missing values without relying on pandas'
    deprecated silent downcasting behavior (avoids FutureWarning on .fillna/.ffill/.bfill).
    """
    # Use pandas' nullable BooleanDtype to handle NA safely, then convert to plain bool.
    return series.astype("boolean").fillna(default).astype(bool)

def _normalize_minor_eligibility(series: pd.Series) -> pd.Series:
    def _coerce(value: object) -> Optional[bool]:
        if pd.isna(value):
            return None
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if isinstance(value, (int, float, np.integer, np.floating)):
            return bool(value)
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"y", "yes", "true", "t", "1"}:
                return True
            if cleaned in {"n", "no", "false", "f", "0", ""}:
                return False
            coerced = pd.to_numeric(cleaned, errors="coerce")
            if not pd.isna(coerced):
                return bool(coerced)
        return None

    return series.apply(_coerce)


def minor_eligibility_from_input(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
    start_year: int,
) -> Optional[pd.DataFrame]:
    candidates = {"minor", "minor_eligible", "minors_eligible", "minor_eligibility", "minors_eligibility", "minoreligible"}

    def _extract(df: pd.DataFrame) -> Optional[pd.DataFrame]:
        if df.empty:
            return None
        col_map = {c: c.strip().lower().replace(" ", "_") for c in df.columns}
        matched = [c for c, norm in col_map.items() if norm in candidates or ("minor" in norm and "elig" in norm)]
        if not matched:
            return None
        col = matched[0]
        use_df = df
        if "Year" in df.columns:
            use_df = df[df["Year"] == start_year]
        subset = use_df[["Player", col]].copy()
        subset["minor_eligible"] = _normalize_minor_eligibility(subset[col])
        subset = subset.drop(columns=[col])
        subset = subset.dropna(subset=["Player"]).groupby("Player", as_index=False)["minor_eligible"].max()
        return subset

    bat_minor = _extract(bat)
    pit_minor = _extract(pit)

    if bat_minor is None and pit_minor is None:
        return None
    if bat_minor is None:
        return pit_minor
    if pit_minor is None:
        return bat_minor

    merged = bat_minor.merge(pit_minor, on="Player", how="outer", suffixes=("_bat", "_pit"))
    merged["minor_eligible"] = merged["minor_eligible_bat"].combine_first(merged["minor_eligible_pit"])
    return merged[["Player", "minor_eligible"]]

def calculate_common_dynasty_values(
    excel_path: str,
    lg: CommonDynastyRotoSettings,
    start_year: Optional[int] = None,
    years: Optional[List[int]] = None,
    verbose: bool = True,
    return_details: bool = False,
    seed: int = 0,
    recent_projections: int = 3,
):
    """Compute common-mode dynasty values.

    If return_details=True, also returns (bat_detail, pit_detail) tables that:
      - collapse duplicate (Player, Year) rows by averaging the most-recent N projections
      - keep the original input columns in roughly the same order
      - attach YearValue/BestSlot (per side) and DynastyValue to each Player/Year row
    """
    bat_raw = normalize_input_schema(pd.read_excel(excel_path, sheet_name="Bat"), COMMON_COLUMN_ALIASES)
    pit_raw = normalize_input_schema(pd.read_excel(excel_path, sheet_name="Pitch"), COMMON_COLUMN_ALIASES)

    bat_input_cols = list(bat_raw.columns)
    pit_input_cols = list(pit_raw.columns)
    bat_date_col = _find_projection_date_col(bat_raw)
    pit_date_col = _find_projection_date_col(pit_raw)

    # Average *all numeric stat columns* (except derived rates and Age) so the
    # aggregated detail tabs reflect the true averaged projections.
    bat_stat_cols = numeric_stat_cols_for_recent_avg(
        bat_raw,
        group_cols=["Player", "Year"],
        exclude_cols={"Age"} | DERIVED_HIT_RATE_COLS,
    )
    pit_stat_cols = numeric_stat_cols_for_recent_avg(
        pit_raw,
        group_cols=["Player", "Year"],
        exclude_cols={"Age"} | DERIVED_PIT_RATE_COLS,
    )

    bat = average_recent_projections(bat_raw, bat_stat_cols, max_entries=recent_projections)
    pit = average_recent_projections(pit_raw, pit_stat_cols, max_entries=recent_projections)

    # Recompute rates after averaging components
    bat = recompute_common_rates_hit(bat)
    pit = recompute_common_rates_pit(pit)

    # Required fields
    require_cols(bat, ["Player", "Year", "Team", "Age", "Pos"] + HIT_COMPONENT_COLS, "Bat")
    require_cols(pit, ["Player", "Year", "Team", "Age", "Pos"], "Pitch")
    require_cols(pit, ["IP", "W", "K", "ER", "H", "BB"], "Pitch")

    # Ensure SV exists
    if "SV" not in pit.columns:
        if "SVH" in pit.columns:
            pit["SV"] = pit["SVH"]
        else:
            pit["SV"] = 0.0
    pit["SV"] = pit["SV"].fillna(0.0)

    if start_year is None:
        start_year = int(min(bat["Year"].min(), pit["Year"].min()))

    if years is None:
        max_year = int(max(bat["Year"].max(), pit["Year"].max()))
        years = [y for y in range(start_year, start_year + lg.horizon_years) if y <= max_year]

    if not years:
        raise ValueError("No valuation years available after applying start year / horizon to projection file years.")

    # Projection metadata: how many projections were averaged (<= recent_projections) and the oldest date used
    proj_meta = projection_meta_for_start_year(bat, pit, start_year)

    # Minor eligibility source precedence:
    # 1) explicit eligibility column in projections (authoritative when present)
    # 2) inference fallback only when explicit data is unavailable
    if lg.minor_slots and lg.minor_slots > 0:
        input_elig = minor_eligibility_from_input(bat, pit, start_year)
        if input_elig is not None:
            elig_df = input_elig.copy()
        else:
            elig_df = infer_minor_eligible(bat, pit, lg, start_year)
        elig_df["minor_eligible"] = _fillna_bool(elig_df["minor_eligible"])
    else:
        elig_df = pd.DataFrame(columns=["Player", "minor_eligible"])

    active_per_team = sum(lg.hitter_slots.values()) + sum(lg.pitcher_slots.values())
    total_minor_slots = lg.n_teams * lg.minor_slots
    total_mlb_slots = lg.n_teams * (active_per_team + lg.bench_slots + lg.ir_slots)

    # PASS 1: average-starter values to estimate who is rostered in a deep league.
    year_contexts: Dict[int, dict] = {}
    year_tables_avg: List[pd.DataFrame] = []

    for y in years:
        if verbose:
            print(f"Year {y}: baseline + SGP + player values (avg-starter pass) ...")
        ctx = compute_year_context(y, bat, pit, lg, rng_seed=seed + y)
        year_contexts[y] = ctx
        hit_vals, pit_vals = compute_year_player_values(ctx, lg)
        combined = combine_two_way(hit_vals, pit_vals, two_way=lg.two_way)
        year_tables_avg.append(combined)

    all_year_avg = pd.concat(year_tables_avg, ignore_index=True)
    wide_avg = all_year_avg.pivot_table(index="Player", columns="Year", values="YearValue", aggfunc="max").reset_index()
    for y in years:
        if y not in wide_avg.columns:
            wide_avg[y] = 0.0

    elig_map = dict(zip(elig_df["Player"], elig_df["minor_eligible"].astype(bool))) if not elig_df.empty else {}

    def _stash_row(row: pd.Series) -> float:
        player = row["Player"]
        can_stash = bool(lg.minor_slots and lg.minor_slots > 0 and bool(elig_map.get(player, False)))
        vals: List[float] = []
        for y in years:
            v = row.get(y)
            if pd.isna(v):
                v = 0.0
            v = float(v)
            if can_stash and v < 0.0:
                v = 0.0
            vals.append(v)
        return dynasty_keep_or_drop_value(vals, years, lg.discount)

    wide_avg["StashScore"] = wide_avg.apply(_stash_row, axis=1)
    stash = wide_avg[["Player", "StashScore"]].copy()
    stash = stash.merge(elig_df, on="Player", how="left")
    stash["minor_eligible"] = _fillna_bool(stash["minor_eligible"])

    stash_sorted = stash.sort_values("StashScore", ascending=False).reset_index(drop=True)
    minors_pool = stash_sorted[stash_sorted["minor_eligible"]]
    minors_sel = minors_pool.head(total_minor_slots)
    minor_names = set(minors_sel["Player"])

    remaining = stash_sorted[~stash_sorted["Player"].isin(minor_names)]
    extra_minor_needed = max(total_minor_slots - len(minors_sel), 0)
    extra_minors = remaining.head(extra_minor_needed)
    extra_minor_names = set(extra_minors["Player"])

    remaining = remaining[~remaining["Player"].isin(extra_minor_names)]
    mlb_sel = remaining.head(total_mlb_slots)
    rostered_names: Set[str] = set(mlb_sel["Player"]) | minor_names | extra_minor_names

    # PASS 2: replacement-level per-year values from the unrostered pool.
    year_tables: List[pd.DataFrame] = []
    hit_year_tables: List[pd.DataFrame] = []
    pit_year_tables: List[pd.DataFrame] = []

    for y in years:
        if verbose:
            print(f"Year {y}: replacement baselines + player values (replacement pass) ...")
        ctx = year_contexts[y]
        repl_hit, repl_pit = compute_replacement_baselines(ctx, lg, rostered_names, n_repl=lg.n_teams)
        hit_vals, pit_vals = compute_year_player_values_vs_replacement(ctx, lg, repl_hit, repl_pit)

        if not hit_vals.empty:
            hit_year_tables.append(hit_vals[["Player", "Year", "BestSlot", "YearValue"]].copy())
        if not pit_vals.empty:
            pit_year_tables.append(pit_vals[["Player", "Year", "BestSlot", "YearValue"]].copy())

        combined = combine_two_way(hit_vals, pit_vals, two_way=lg.two_way)
        year_tables.append(combined)

    all_year = pd.concat(year_tables, ignore_index=True) if year_tables else pd.DataFrame()

    # Wide format: one row per player with Value_YEAR columns
    wide = all_year.pivot_table(index="Player", columns="Year", values="YearValue", aggfunc="max").reset_index()
    wide.columns = ["Player"] + [f"Value_{int(c)}" for c in wide.columns[1:]]

    # Metadata from start year
    meta = (
        all_year[all_year["Year"] == start_year][["Player", "Team", "Pos", "Age"]]
        .drop_duplicates("Player")
    )
    out = meta.merge(wide, on="Player", how="right")

    # Attach projection metadata (based on the start-year averaged projections)
    out = out.merge(proj_meta, on="Player", how="left")
    out = out.merge(elig_df, on="Player", how="left")
    out["minor_eligible"] = _fillna_bool(out["minor_eligible"])

    # Raw dynasty value: optimal keep/drop value.
    #
    # Old behavior: sum of positive years only (i.e., negatives were always free to ignore).
    # New behavior:
    #   - If the player can be stashed in a minors slot (league has minors slots AND player is minors-eligible),
    #     we still treat negative years as 0 (you keep them in minors, so no "holding" penalty).
    #   - Otherwise, negative years *do* count as a cost if you keep the player, but you can always drop
    #     the player permanently for 0 (so truly droppable players won't go negative overall).
    raw_vals: List[float] = []
    for _, r in out.iterrows():
        can_stash = bool(lg.minor_slots and lg.minor_slots > 0 and bool(r.get("minor_eligible", False)))

        vals: List[float] = []
        for y in years:
            v = r.get(f"Value_{y}")
            if pd.isna(v):
                v = 0.0
            v = float(v)
            if can_stash and v < 0.0:
                v = 0.0
            vals.append(v)

        raw_vals.append(dynasty_keep_or_drop_value(vals, years, lg.discount))

    out["RawDynastyValue"] = raw_vals

    # Centering: replacement-level roster cutoff with minors reserved first.
    out_sorted = out.sort_values("RawDynastyValue", ascending=False).reset_index(drop=True)
    minors_pool = out_sorted[out_sorted["minor_eligible"]]
    minors_sel = minors_pool.head(total_minor_slots)
    minor_names = set(minors_sel["Player"])

    remaining = out_sorted[~out_sorted["Player"].isin(minor_names)]
    extra_minor_needed = max(total_minor_slots - len(minors_sel), 0)
    extra_minors = remaining.head(extra_minor_needed)
    extra_minor_names = set(extra_minors["Player"])

    remaining = remaining[~remaining["Player"].isin(extra_minor_names)]
    mlb_sel = remaining.head(total_mlb_slots)

    rostered = pd.concat([minors_sel, extra_minors, mlb_sel], ignore_index=True)
    baseline_value = float(rostered["RawDynastyValue"].iloc[-1]) if len(rostered) else 0.0

    out["DynastyValue"] = out["RawDynastyValue"] - baseline_value
    out["CenteringBaselineValue"] = baseline_value
    out["CenteringBaselineMean"] = baseline_value

    out = out.sort_values("DynastyValue", ascending=False).reset_index(drop=True)

    if not return_details:
        return out

    # ----------------------------
    # Detail tabs (aggregated projections + value columns)
    # ----------------------------
    hit_year = pd.concat(hit_year_tables, ignore_index=True) if hit_year_tables else pd.DataFrame(columns=["Player", "Year", "BestSlot", "YearValue"])
    pit_year = pd.concat(pit_year_tables, ignore_index=True) if pit_year_tables else pd.DataFrame(columns=["Player", "Year", "BestSlot", "YearValue"])

    player_vals = out[["Player", "DynastyValue", "RawDynastyValue", "minor_eligible"]].copy()

    bat_detail = bat.merge(hit_year, on=["Player", "Year"], how="left")
    bat_detail = bat_detail.merge(player_vals, on="Player", how="left")

    pit_detail = pit.merge(pit_year, on=["Player", "Year"], how="left")
    pit_detail = pit_detail.merge(player_vals, on="Player", how="left")

    extra = ["ProjectionsUsed", "OldestProjectionDate", "BestSlot", "YearValue", "DynastyValue", "RawDynastyValue", "minor_eligible"]
    bat_detail = reorder_detail_columns(bat_detail, bat_input_cols, add_after=bat_date_col, extra_cols=extra)
    pit_detail = reorder_detail_columns(pit_detail, pit_input_cols, add_after=pit_date_col, extra_cols=extra)

    return out, bat_detail, pit_detail

# ----------------------------
# Custom league version (renamed to avoid collisions)
# ----------------------------

"""
Dynasty roto player values for your league settings.

What this script does (high level):
1) Reads your Excel file (sheets: "Bat" and "Pitch")
2) Builds an "average team" baseline using a league-wide optimal slot assignment
   (positional scarcity baked in).
3) Estimates SGP denominators (how much of each stat ~= 1 roto point) by Monte Carlo
   simulation of 12-team leagues built from that starter pool.
4) Computes each player's per-year marginal roto points vs the average starter in their
   best eligible slot, with the pitching IP cap/min/max accounted for:
   - Pitching totals are capped at 1500 IP (stats scale down if over).
   - If under 1500 IP, the script fills the gap with "replacement innings" from the
     best available non-starters (so high-IP SP only help insofar as they replace
     worse innings; "too many SP" gets diminishing returns under the cap).
5) Produces a single DynastyValue per player by discounting future years and then
   centering so that ~0 is the replacement-level rostered cutoff in this league format.

Dependencies:
  pip install pandas numpy openpyxl scipy
"""


# ----------------------------
# League settings / parameters
# ----------------------------

@dataclass
class LeagueSettings:
    n_teams: int = 12

    # Active roster slots per team
    hitter_slots: Dict[str, int] = field(default_factory=lambda: {
        "C": 2,
        "1B": 1,
        "2B": 1,
        "3B": 1,
        "SS": 1,
        "CI": 1,
        "MI": 1,
        "OF": 5,
        "UT": 1,
    })
    pitcher_slots: Dict[str, int] = field(default_factory=lambda: {
        "SP": 3,
        "RP": 3,
        "P": 3,   # any pitcher
    })

    # Pitching innings rules
    ip_min: float = 1000.0
    ip_max: float = 1500.0

    # Bench / minors / IR (used for dynasty centering baseline)
    bench_slots: int = 15
    minor_slots: int = 20
    ir_slots: int = 8

    # Minor eligibility thresholds (career), used as a *best-effort* inference
    minor_hitters_career_ab_max: int = 130
    minor_pitchers_career_ip_max: int = 50

    # Monte Carlo settings
    sims_for_sgp: int = 200           # increase for more stable SGP; decrease for speed
    replacement_pitchers_n: int = 100 # how many non-starter pitchers define "replacement innings"

    # Dynasty parameters
    discount: float = 0.85            # 0.85 = ~15% annual discount
    horizon_years: int = 10           # number of seasons included in dynasty value

    # To reduce false positives when inferring minor eligibility from projections
    infer_minor_age_max_hit: int = 25
    infer_minor_age_max_pit: int = 26

    # Two-way handling if player appears in both Bat and Pitch:
    #   "max" = treat as choose hitter OR pitcher each season
    #   "sum" = count both (only use if your league counts both simultaneously)
    two_way: str = "max"


# ----------------------------
# Helpers: positions / eligibility
# ----------------------------

def league_parse_hit_positions(pos_str: str) -> Set[str]:
    if pd.isna(pos_str):
        return set()
    return {p.strip() for p in str(pos_str).split("/") if p.strip()}

def league_eligible_hit_slots(pos_set: Set[str]) -> Set[str]:
    slots: Set[str] = set()
    if not pos_set:
        return slots

    # UT always if any hitter projection row exists
    slots.add("UT")

    if "C" in pos_set:
        slots.add("C")
    if "1B" in pos_set:
        slots.update({"1B", "CI"})
    if "3B" in pos_set:
        slots.update({"3B", "CI"})
    if "2B" in pos_set:
        slots.update({"2B", "MI"})
    if "SS" in pos_set:
        slots.update({"SS", "MI"})
    if "OF" in pos_set:
        slots.add("OF")

    # "DH" -> only UT (already included)
    return slots

def league_parse_pit_positions(pos_str: str) -> Set[str]:
    if pd.isna(pos_str):
        return set()
    parts = [p.strip() for p in str(pos_str).split("/") if p.strip()]
    out: Set[str] = set()
    for p in parts:
        if p == "UT":
            continue
        if p in {"UT/SP", "UT-SP"}:
            out.add("SP")
        else:
            out.add(p)
    return out

def league_eligible_pit_slots(pos_set: Set[str]) -> Set[str]:
    slots: Set[str] = set()
    if "SP" in pos_set:
        slots.update({"SP", "P"})
    if "RP" in pos_set:
        slots.update({"RP", "P"})
    if not slots and pos_set:
        slots.add("P")
    return slots


# ----------------------------
# Helpers: stat components
# ----------------------------

LEAGUE_HIT_STAT_COLS = [
    "AB", "H", "R", "HR", "RBI", "SB", "BB", "HBP", "SF", "2B", "3B",
    "TB", "OBP_num", "OBP_den",
]

def league_hitter_components(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Total Bases: TB = H + 2B + 2*3B + 3*HR
    df["TB"] = df["H"] + df["2B"] + 2 * df["3B"] + 3 * df["HR"]

    # OBP numerator/denominator (standard OBP)
    df["OBP_num"] = df["H"] + df["BB"] + df["HBP"]
    df["OBP_den"] = df["AB"] + df["BB"] + df["HBP"] + df["SF"]

    return df

def league_ensure_pitch_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Allow alternative source columns if needed
    if "SVH" not in df.columns:
        if "SV" in df.columns and "HLD" in df.columns:
            df["SVH"] = df["SV"].fillna(0) + df["HLD"].fillna(0)
        else:
            df["SVH"] = 0.0

    return df


# ----------------------------
# Core math: baseline, assignment, SGP
# ----------------------------

def league_zscore(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    mu = s.mean()
    sd = s.std(ddof=0)
    if sd == 0 or np.isnan(sd):
        return (s - mu) * 0.0
    return (s - mu) / sd

def league_initial_hitter_weight(df: pd.DataFrame) -> pd.Series:
    """
    Rough first-pass weight used only to determine the starter pool and average slot baselines.
    """
    df = df.copy()
    mean_hit_rate = df["H"].sum() / df["AB"].sum() if df["AB"].sum() > 0 else 0.0
    mean_ops = df["OPS"].mean() if "OPS" in df.columns else 0.0

    df["H_surplus"] = df["H"] - mean_hit_rate * df["AB"]
    df["OPS_surplus"] = (df.get("OPS", 0.0) - mean_ops) * df["AB"]

    cols = ["R", "HR", "RBI", "SB", "H_surplus", "OPS_surplus"]
    zsum = 0.0
    for c in cols:
        zsum += league_zscore(df[c])
    return zsum

def league_initial_pitcher_weight(df: pd.DataFrame) -> pd.Series:
    """
    Rough first-pass weight used only to determine the starter pool and average slot baselines.
    """
    df = df.copy()
    ip_sum = df["IP"].sum()
    mean_era = (df["ER"].sum() * 9 / ip_sum) if ip_sum > 0 else df["ERA"].mean()
    mean_whip = ((df["H"].sum() + df["BB"].sum()) / ip_sum) if ip_sum > 0 else df["WHIP"].mean()

    # Convert ratios into "runs prevented" / "baserunners prevented" relative to mean
    df["ERA_surplus_ER"] = (mean_era - df["ERA"]) * df["IP"] / 9
    df["WHIP_surplus"] = (mean_whip - df["WHIP"]) * df["IP"]

    cols = ["W", "K", "SVH", "QA3", "ERA_surplus_ER", "WHIP_surplus"]
    zsum = 0.0
    for c in cols:
        zsum += league_zscore(df[c])
    return zsum

def league_expand_slot_counts(slot_counts_per_team: Dict[str, int], n_teams: int) -> Dict[str, int]:
    return {slot: cnt * n_teams for slot, cnt in slot_counts_per_team.items()}

def league_build_slot_list(slot_counts: Dict[str, int]) -> List[str]:
    slots: List[str] = []
    for slot, count in slot_counts.items():
        slots.extend([slot] * count)
    return slots

def league_build_team_slot_template(slot_counts_per_team: Dict[str, int]) -> List[str]:
    slots: List[str] = []
    for slot, count in slot_counts_per_team.items():
        slots.extend([slot] * count)
    return slots

def league_assign_players_to_slots(
    df: pd.DataFrame,
    slot_counts: Dict[str, int],
    eligible_func: Callable[[Set[str]], Set[str]],
    weight_col: str = "weight",
) -> pd.DataFrame:
    """
    Maximum-weight assignment (Hungarian algorithm) to fill all league slots with distinct players.
    """
    df = df.copy().reset_index(drop=True)
    df["_assign_idx"] = np.arange(len(df))

    slots = league_build_slot_list(slot_counts)
    n_slots = len(slots)
    n_players = len(df)

    if n_players < n_slots:
        raise ValueError(f"Not enough players ({n_players}) to fill required slots ({n_slots}).")

    elig_sets: List[Set[str]] = []
    parse_func = league_parse_hit_positions if eligible_func == league_eligible_hit_slots else league_parse_pit_positions
    for pos_str in df["Pos"]:
        pos_set = parse_func(pos_str)
        elig_sets.append(eligible_func(pos_set))

    for slot, req in slot_counts.items():
        elig_count = sum(1 for e in elig_sets if slot in e)
        if elig_count < req:
            raise ValueError(
                f"Cannot fill slot '{slot}': need {req} eligible players but only found {elig_count}."
            )

    weights = df[weight_col].to_numpy(dtype=float)
    BIG = 1e6

    cost = np.full((n_slots, n_players), BIG, dtype=float)
    for i, slot in enumerate(slots):
        for j in range(n_players):
            if slot in elig_sets[j]:
                cost[i, j] = -weights[j]  # maximize weight => minimize negative weight

    row_ind, col_ind = linear_sum_assignment(cost)
    assigned = df.loc[col_ind].copy()
    assigned["AssignedSlot"] = [slots[i] for i in row_ind]
    validate_assigned_slots(assigned, slot_counts, elig_sets, mode_label="League mode")
    return assigned.drop(columns=["_assign_idx"])

def league_team_avg_ops(hit_tot: pd.Series) -> Tuple[float, float]:
    ab = float(hit_tot["AB"])
    avg = float(hit_tot["H"] / ab) if ab > 0 else 0.0
    obp_den = float(hit_tot["OBP_den"])
    obp = float(hit_tot["OBP_num"] / obp_den) if obp_den > 0 else 0.0
    slg = float(hit_tot["TB"] / ab) if ab > 0 else 0.0
    ops = obp + slg
    return avg, ops

def league_replacement_pitcher_rates(all_pit_df: pd.DataFrame, assigned_pit_df: pd.DataFrame, n_rep: int = 100) -> Dict[str, float]:
    """
    Compute per-inning replacement rates from the best available non-starter pitchers.
    """
    assigned_players = set(assigned_pit_df["Player"])
    rep = all_pit_df[~all_pit_df["Player"].isin(assigned_players)].copy()
    rep = rep.sort_values("weight", ascending=False).head(n_rep)

    ip = rep["IP"].sum()
    if ip <= 0:
        return {k: 0.0 for k in ["W", "K", "SVH", "QA3", "ER", "H", "BB"]}

    return {
        "W": rep["W"].sum() / ip,
        "K": rep["K"].sum() / ip,
        "SVH": rep["SVH"].sum() / ip,
        "QA3": rep["QA3"].sum() / ip,
        "ER": rep["ER"].sum() / ip,
        "H": rep["H"].sum() / ip,
        "BB": rep["BB"].sum() / ip,
    }

def league_apply_ip_cap(t: Dict[str, float], ip_cap: float, rep_rates: Optional[Dict[str, float]]) -> Dict[str, float]:
    """
    Enforce the 1500 IP cap and fill missing innings with replacement to reach the cap.
    """
    out = dict(t)
    ip = float(out.get("IP", 0.0))

    # If over cap: scale everything down proportionally (exactly matches "stats stop accruing at 1500")
    if ip > ip_cap and ip > 0:
        f = ip_cap / ip
        for k in ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]:
            out[k] = float(out.get(k, 0.0)) * f
        ip = ip_cap

    # If under cap: fill with replacement innings
    if ip < ip_cap and rep_rates is not None:
        add = ip_cap - ip
        out["IP"] = ip_cap
        for k in ["W", "K", "SVH", "QA3", "ER", "H", "BB"]:
            out[k] = float(out.get(k, 0.0)) + add * float(rep_rates.get(k, 0.0))
        ip = ip_cap

    # Ratios on capped totals
    out["ERA"] = 9.0 * out["ER"] / ip if ip > 0 else np.nan
    out["WHIP"] = (out["H"] + out["BB"]) / ip if ip > 0 else np.nan
    return out

def league_simulate_sgp_hit(assigned_hit_df: pd.DataFrame, lg: LeagueSettings, rng: np.random.Generator) -> Dict[str, float]:
    """
    Monte Carlo estimate of the average adjacent gap between roto ranks ("stat per roto point").
    """
    # Group players by the slot they were assigned to in the league-wide optimal assignment
    groups = {slot: assigned_hit_df[assigned_hit_df["AssignedSlot"] == slot] for slot in assigned_hit_df["AssignedSlot"].unique()}
    per_team = lg.hitter_slots

    cats = ["R", "HR", "RBI", "SB", "AVG", "OPS"]
    diffs = {c: [] for c in cats}

    for _ in range(lg.sims_for_sgp):
        # Team totals for each simulation
        team_tot = [{col: 0.0 for col in LEAGUE_HIT_STAT_COLS} for _ in range(lg.n_teams)]

        for slot, df_slot in groups.items():
            cnt = per_team[slot]
            idx = rng.permutation(len(df_slot))
            arr = df_slot.iloc[idx][LEAGUE_HIT_STAT_COLS].to_numpy()
            arr = arr.reshape(lg.n_teams, cnt, len(LEAGUE_HIT_STAT_COLS))

            # Vector sums per team, then add
            for t in range(lg.n_teams):
                sums = arr[t].sum(axis=0)
                for k, col in enumerate(LEAGUE_HIT_STAT_COLS):
                    team_tot[t][col] += float(sums[k])

        # Compute category totals
        vals = {c: [] for c in cats}
        for t in range(lg.n_teams):
            tot = team_tot[t]
            avg, ops = league_team_avg_ops(pd.Series(tot))
            vals["R"].append(tot["R"])
            vals["HR"].append(tot["HR"])
            vals["RBI"].append(tot["RBI"])
            vals["SB"].append(tot["SB"])
            vals["AVG"].append(avg)
            vals["OPS"].append(ops)

        for c in cats:
            arr = np.array(vals[c], dtype=float)
            arr_sorted = np.sort(arr)[::-1]  # higher is better for all hitter cats here
            diffs[c].append(float(np.mean(np.abs(np.diff(arr_sorted)))))

    return {c: float(np.mean(diffs[c])) for c in cats}

def league_simulate_sgp_pit(assigned_pit_df: pd.DataFrame, lg: LeagueSettings, rep_rates: Dict[str, float], rng: np.random.Generator) -> Dict[str, float]:
    """
    Monte Carlo estimate of the average adjacent gap between roto ranks ("stat per roto point") for pitching.
    """
    groups = {slot: assigned_pit_df[assigned_pit_df["AssignedSlot"] == slot] for slot in assigned_pit_df["AssignedSlot"].unique()}
    per_team = lg.pitcher_slots

    cats = ["W", "K", "SVH", "QA3", "ERA", "WHIP"]
    diffs = {c: [] for c in cats}

    base_cols = ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]

    for _ in range(lg.sims_for_sgp):
        team_raw = [{col: 0.0 for col in base_cols} for _ in range(lg.n_teams)]

        for slot, df_slot in groups.items():
            cnt = per_team[slot]
            idx = rng.permutation(len(df_slot))
            arr = df_slot.iloc[idx][base_cols].to_numpy()
            arr = arr.reshape(lg.n_teams, cnt, len(base_cols))

            for t in range(lg.n_teams):
                sums = arr[t].sum(axis=0)
                for k, col in enumerate(base_cols):
                    team_raw[t][col] += float(sums[k])

        vals = {c: [] for c in cats}
        for t in range(lg.n_teams):
            capped = league_apply_ip_cap(team_raw[t], ip_cap=lg.ip_max, rep_rates=rep_rates)
            vals["W"].append(capped["W"])
            vals["K"].append(capped["K"])
            vals["SVH"].append(capped["SVH"])
            vals["QA3"].append(capped["QA3"])
            vals["ERA"].append(capped["ERA"])
            vals["WHIP"].append(capped["WHIP"])

        for c in cats:
            arr = np.array(vals[c], dtype=float)
            # For ERA/WHIP lower is better => sort ascending for rank gaps
            arr_sorted = np.sort(arr) if c in {"ERA", "WHIP"} else np.sort(arr)[::-1]
            diffs[c].append(float(np.mean(np.abs(np.diff(arr_sorted)))))

    return {c: float(np.mean(diffs[c])) for c in cats}


# ----------------------------
# Year context + player year-values
# ----------------------------

def league_sum_slots(baseline_df: pd.DataFrame, slot_list: List[str]) -> pd.Series:
    return baseline_df.loc[slot_list].sum()

def league_compute_year_context(year: int, bat_df: pd.DataFrame, pit_df: pd.DataFrame, lg: LeagueSettings, rng_seed: int) -> dict:
    bat_y = league_hitter_components(bat_df[bat_df["Year"] == year].copy())
    pit_y = league_ensure_pitch_cols(pit_df[pit_df["Year"] == year].copy())

    # Use only playing-time > 0 rows to build the "starter pool" baselines
    bat_play = bat_y[bat_y["AB"] > 0].copy()
    pit_play = pit_y[pit_y["IP"] > 0].copy()

    if bat_play.empty:
        raise ValueError(
            f"Year {year}: no hitters with AB > 0 after filtering. Check Year values and AB projections."
        )
    if pit_play.empty:
        raise ValueError(
            f"Year {year}: no pitchers with IP > 0 after filtering. Check Year values and IP projections."
        )

    bat_play["weight"] = league_initial_hitter_weight(bat_play)
    pit_play["weight"] = league_initial_pitcher_weight(pit_play)

    league_hit_slots = league_expand_slot_counts(lg.hitter_slots, lg.n_teams)
    league_pit_slots = league_expand_slot_counts(lg.pitcher_slots, lg.n_teams)

    assigned_hit = league_assign_players_to_slots(bat_play, league_hit_slots, league_eligible_hit_slots, weight_col="weight")
    assigned_pit = league_assign_players_to_slots(pit_play, league_pit_slots, league_eligible_pit_slots, weight_col="weight")

    baseline_hit = assigned_hit.groupby("AssignedSlot")[LEAGUE_HIT_STAT_COLS].mean()
    baseline_pit = assigned_pit.groupby("AssignedSlot")[["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]].mean()

    team_hit_slots = league_build_team_slot_template(lg.hitter_slots)
    team_pit_slots = league_build_team_slot_template(lg.pitcher_slots)

    base_hit_tot = league_sum_slots(baseline_hit, team_hit_slots)
    base_avg, base_ops = league_team_avg_ops(base_hit_tot)

    base_pit_raw = league_sum_slots(baseline_pit, team_pit_slots)
    base_pit_raw_dict = {k: float(base_pit_raw[k]) for k in ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]}

    rep_rates = league_replacement_pitcher_rates(pit_play.assign(weight=league_initial_pitcher_weight(pit_play)), assigned_pit, n_rep=lg.replacement_pitchers_n)

    rng_hit = np.random.default_rng(rng_seed)
    rng_pit = np.random.default_rng(rng_seed + 1)
    sgp_hit = league_simulate_sgp_hit(assigned_hit, lg, rng_hit)
    sgp_pit = league_simulate_sgp_pit(assigned_pit, lg, rep_rates, rng_pit)

    return {
        "year": year,
        "bat_y": bat_y,
        "pit_y": pit_y,
        "baseline_hit": baseline_hit,
        "baseline_pit": baseline_pit,
        "base_hit_tot": base_hit_tot,
        "base_avg": base_avg,
        "base_ops": base_ops,
        "base_pit_raw": base_pit_raw_dict,
        "rep_rates": rep_rates,
        "sgp_hit": sgp_hit,
        "sgp_pit": sgp_pit,
    }

def league_compute_year_player_values(ctx: dict, lg: LeagueSettings) -> Tuple[pd.DataFrame, pd.DataFrame]:
    year = int(ctx["year"])
    bat_y = ctx["bat_y"]
    pit_y = ctx["pit_y"]

    baseline_hit = ctx["baseline_hit"]
    baseline_pit = ctx["baseline_pit"]
    base_hit_tot = ctx["base_hit_tot"]
    base_avg = float(ctx["base_avg"])
    base_ops = float(ctx["base_ops"])

    base_pit_raw = dict(ctx["base_pit_raw"])
    rep_rates = ctx["rep_rates"]

    sgp_hit = ctx["sgp_hit"]
    sgp_pit = ctx["sgp_pit"]

    base_pit_capped = league_apply_ip_cap(base_pit_raw, ip_cap=lg.ip_max, rep_rates=rep_rates)

    # --- Hitters: best-slot marginal SGP vs average starter in that slot ---
    hit_rows = []
    for row in bat_y.itertuples(index=False):
        pos_set = league_parse_hit_positions(getattr(row, "Pos", ""))
        slots = league_eligible_hit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_hit.index:
                continue

            b = baseline_hit.loc[slot]
            new_tot = base_hit_tot.copy()
            for col in LEAGUE_HIT_STAT_COLS:
                new_tot[col] = new_tot[col] - b[col] + getattr(row, col)

            new_avg, new_ops = league_team_avg_ops(new_tot)

            delta_R = float(new_tot["R"] - base_hit_tot["R"])
            delta_HR = float(new_tot["HR"] - base_hit_tot["HR"])
            delta_RBI = float(new_tot["RBI"] - base_hit_tot["RBI"])
            delta_SB = float(new_tot["SB"] - base_hit_tot["SB"])
            delta_AVG = float(new_avg - base_avg)
            delta_OPS = float(new_ops - base_ops)

            val = (
                (delta_R / sgp_hit["R"] if sgp_hit["R"] else 0.0)
                + (delta_HR / sgp_hit["HR"] if sgp_hit["HR"] else 0.0)
                + (delta_RBI / sgp_hit["RBI"] if sgp_hit["RBI"] else 0.0)
                + (delta_SB / sgp_hit["SB"] if sgp_hit["SB"] else 0.0)
                + (delta_AVG / sgp_hit["AVG"] if sgp_hit["AVG"] else 0.0)
                + (delta_OPS / sgp_hit["OPS"] if sgp_hit["OPS"] else 0.0)
            )

            if val > best_val:
                best_val = val
                best_slot = slot

        hit_rows.append({
            "Player": getattr(row, "Player"),
            "Year": year,
            "Type": "H",
            "MLBTeam": getattr(row, "MLBTeam", np.nan),
            "Age": getattr(row, "Age", np.nan),
            "Pos": getattr(row, "Pos", np.nan),
            "BestSlot": best_slot,
            "YearValue": float(best_val),
        })

    hit_vals = pd.DataFrame(hit_rows)

    # --- Pitchers: best-slot marginal SGP vs average starter in that slot, with IP cap ---
    pit_rows = []
    for row in pit_y.itertuples(index=False):
        pos_set = league_parse_pit_positions(getattr(row, "Pos", ""))
        slots = league_eligible_pit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_pit.index:
                continue

            b = baseline_pit.loc[slot]
            new_raw = dict(base_pit_raw)
            for col in ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]:
                new_raw[col] = float(new_raw[col]) - float(b[col]) + float(getattr(row, col, 0.0))

            new_capped = league_apply_ip_cap(new_raw, ip_cap=lg.ip_max, rep_rates=rep_rates)

            delta_W = float(new_capped["W"] - base_pit_capped["W"])
            delta_K = float(new_capped["K"] - base_pit_capped["K"])
            delta_SVH = float(new_capped["SVH"] - base_pit_capped["SVH"])
            delta_QA3 = float(new_capped["QA3"] - base_pit_capped["QA3"])

            # Lower is better for ERA/WHIP => improvement = base - new
            delta_ERA = float(base_pit_capped["ERA"] - new_capped["ERA"])
            delta_WHIP = float(base_pit_capped["WHIP"] - new_capped["WHIP"])

            val = (
                (delta_W / sgp_pit["W"] if sgp_pit["W"] else 0.0)
                + (delta_K / sgp_pit["K"] if sgp_pit["K"] else 0.0)
                + (delta_SVH / sgp_pit["SVH"] if sgp_pit["SVH"] else 0.0)
                + (delta_QA3 / sgp_pit["QA3"] if sgp_pit["QA3"] else 0.0)
                + (delta_ERA / sgp_pit["ERA"] if sgp_pit["ERA"] else 0.0)
                + (delta_WHIP / sgp_pit["WHIP"] if sgp_pit["WHIP"] else 0.0)
            )

            if val > best_val:
                best_val = val
                best_slot = slot

        pit_rows.append({
            "Player": getattr(row, "Player"),
            "Year": year,
            "Type": "P",
            "MLBTeam": getattr(row, "MLBTeam", np.nan),
            "Age": getattr(row, "Age", np.nan),
            "Pos": getattr(row, "Pos", np.nan),
            "BestSlot": best_slot,
            "YearValue": float(best_val),
        })

    pit_vals = pd.DataFrame(pit_rows)
    return hit_vals, pit_vals

def league_compute_replacement_baselines(
    ctx: dict,
    lg: LeagueSettings,
    rostered_players: Set[str],
    n_repl: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build per-slot replacement-level baselines from the *unrostered* player pool.

    We approximate "replacement at slot" as the mean stat line of the top `n_repl`
    free agents eligible at that slot (default: n_teams).
    """
    n_repl = int(n_repl or lg.n_teams)

    bat_y = ctx["bat_y"].copy()
    pit_y = ctx["pit_y"].copy()

    # Clean numeric NaNs
    for c in LEAGUE_HIT_STAT_COLS:
        if c in bat_y.columns:
            bat_y[c] = bat_y[c].fillna(0.0)
    for c in ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]:
        if c in pit_y.columns:
            pit_y[c] = pit_y[c].fillna(0.0)

    if "ERA" in pit_y.columns:
        pit_y["ERA"] = pit_y["ERA"].fillna(pit_y["ERA"].mean())
    if "WHIP" in pit_y.columns:
        pit_y["WHIP"] = pit_y["WHIP"].fillna(pit_y["WHIP"].mean())

    # Weights for ordering free agents (same rough weights used for starter-pool selection)
    bat_y["weight"] = league_initial_hitter_weight(bat_y)
    pit_y["weight"] = league_initial_pitcher_weight(pit_y)

    # Candidate free-agent pools (must have playing time to be meaningful replacements)
    fa_hit = bat_y[(~bat_y["Player"].isin(rostered_players)) & (bat_y["AB"] > 0)].copy()
    fa_pit = pit_y[(~pit_y["Player"].isin(rostered_players)) & (pit_y["IP"] > 0)].copy()

    fa_hit["elig"] = fa_hit["Pos"].apply(lambda p: league_eligible_hit_slots(league_parse_hit_positions(p)))
    fa_pit["elig"] = fa_pit["Pos"].apply(lambda p: league_eligible_pit_slots(league_parse_pit_positions(p)))

    # Hit replacement baselines per slot
    repl_hit_rows: List[dict] = []
    baseline_hit_avg = ctx["baseline_hit"]
    for slot in baseline_hit_avg.index:
        cand = (
            fa_hit[fa_hit["elig"].apply(lambda s: slot in s)]
            .sort_values("weight", ascending=False)
            .head(n_repl)
        )
        if len(cand) == 0:
            repl = baseline_hit_avg.loc[slot]
        else:
            repl = cand[LEAGUE_HIT_STAT_COLS].mean()

        row = {c: float(repl.get(c, 0.0)) for c in LEAGUE_HIT_STAT_COLS}
        row["AssignedSlot"] = slot
        repl_hit_rows.append(row)

    repl_hit = pd.DataFrame(repl_hit_rows).set_index("AssignedSlot")

    # Pitch replacement baselines per slot
    repl_pit_rows: List[dict] = []
    baseline_pit_avg = ctx["baseline_pit"]
    pit_cols = ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]
    for slot in baseline_pit_avg.index:
        cand = (
            fa_pit[fa_pit["elig"].apply(lambda s: slot in s)]
            .sort_values("weight", ascending=False)
            .head(n_repl)
        )
        if len(cand) == 0:
            repl = baseline_pit_avg.loc[slot]
        else:
            repl = cand[pit_cols].mean()

        row = {c: float(repl.get(c, 0.0)) for c in pit_cols}
        row["AssignedSlot"] = slot
        repl_pit_rows.append(row)

    repl_pit = pd.DataFrame(repl_pit_rows).set_index("AssignedSlot")

    return repl_hit, repl_pit


def league_compute_year_player_values_vs_replacement(
    ctx: dict,
    lg: LeagueSettings,
    repl_hit: pd.DataFrame,
    repl_pit: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Compute per-year player values as marginal roto points above *replacement level*
    (instead of above the average starter).

    Implementation detail:
    - We keep the *team context* as an average-starter roster for the other slots.
    - For each candidate slot, we compare "player in that slot" vs
      "replacement player in that slot".
    """
    year = int(ctx["year"])
    bat_y = ctx["bat_y"]
    pit_y = ctx["pit_y"]

    baseline_hit_avg = ctx["baseline_hit"]
    baseline_pit_avg = ctx["baseline_pit"]

    base_hit_tot_avg = ctx["base_hit_tot"]

    base_pit_raw_avg = dict(ctx["base_pit_raw"])
    rep_rates = ctx["rep_rates"]

    sgp_hit = ctx["sgp_hit"]
    sgp_pit = ctx["sgp_pit"]

    # --- Hitters ---
    hit_rows = []
    for row in bat_y.itertuples(index=False):
        pos_set = league_parse_hit_positions(getattr(row, "Pos", ""))
        slots = league_eligible_hit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_hit_avg.index or slot not in repl_hit.index:
                continue

            b_avg = baseline_hit_avg.loc[slot]
            b_rep = repl_hit.loc[slot]

            # Base team but with replacement in this slot
            base_tot = base_hit_tot_avg.copy()
            for col in LEAGUE_HIT_STAT_COLS:
                base_tot[col] = base_tot[col] - b_avg[col] + b_rep[col]

            # New team with this player in this slot
            new_tot = base_hit_tot_avg.copy()
            for col in LEAGUE_HIT_STAT_COLS:
                new_tot[col] = new_tot[col] - b_avg[col] + getattr(row, col, 0.0)

            base_avg, base_ops = league_team_avg_ops(base_tot)
            new_avg, new_ops = league_team_avg_ops(new_tot)

            delta_R = float(new_tot["R"] - base_tot["R"])
            delta_HR = float(new_tot["HR"] - base_tot["HR"])
            delta_RBI = float(new_tot["RBI"] - base_tot["RBI"])
            delta_SB = float(new_tot["SB"] - base_tot["SB"])
            delta_AVG = float(new_avg - base_avg)
            delta_OPS = float(new_ops - base_ops)

            val = (
                (delta_R / sgp_hit["R"] if sgp_hit["R"] else 0.0)
                + (delta_HR / sgp_hit["HR"] if sgp_hit["HR"] else 0.0)
                + (delta_RBI / sgp_hit["RBI"] if sgp_hit["RBI"] else 0.0)
                + (delta_SB / sgp_hit["SB"] if sgp_hit["SB"] else 0.0)
                + (delta_AVG / sgp_hit["AVG"] if sgp_hit["AVG"] else 0.0)
                + (delta_OPS / sgp_hit["OPS"] if sgp_hit["OPS"] else 0.0)
            )

            if val > best_val:
                best_val = val
                best_slot = slot

        hit_rows.append({
            "Player": getattr(row, "Player"),
            "Year": year,
            "Type": "H",
            "MLBTeam": getattr(row, "MLBTeam", np.nan),
            "Age": getattr(row, "Age", np.nan),
            "Pos": getattr(row, "Pos", np.nan),
            "BestSlot": best_slot,
            "YearValue": float(best_val),
        })

    hit_vals = pd.DataFrame(hit_rows)

    # --- Pitchers ---
    pit_rows = []
    pit_cols = ["IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"]

    for row in pit_y.itertuples(index=False):
        pos_set = league_parse_pit_positions(getattr(row, "Pos", ""))
        slots = league_eligible_pit_slots(pos_set)
        if not slots:
            continue

        best_val = -1e18
        best_slot = None

        for slot in slots:
            if slot not in baseline_pit_avg.index or slot not in repl_pit.index:
                continue

            b_avg = baseline_pit_avg.loc[slot]
            b_rep = repl_pit.loc[slot]

            # Base team but with replacement in this slot
            base_raw = dict(base_pit_raw_avg)
            for col in pit_cols:
                base_raw[col] = float(base_raw.get(col, 0.0)) - float(b_avg.get(col, 0.0)) + float(b_rep.get(col, 0.0))

            # New team with this player in this slot
            new_raw = dict(base_pit_raw_avg)
            for col in pit_cols:
                new_raw[col] = float(new_raw.get(col, 0.0)) - float(b_avg.get(col, 0.0)) + float(getattr(row, col, 0.0))

            base_capped = league_apply_ip_cap(base_raw, ip_cap=lg.ip_max, rep_rates=rep_rates)
            new_capped = league_apply_ip_cap(new_raw, ip_cap=lg.ip_max, rep_rates=rep_rates)

            delta_W = float(new_capped["W"] - base_capped["W"])
            delta_K = float(new_capped["K"] - base_capped["K"])
            delta_SVH = float(new_capped["SVH"] - base_capped["SVH"])
            delta_QA3 = float(new_capped["QA3"] - base_capped["QA3"])

            # Lower is better for ERA/WHIP
            delta_ERA = float(base_capped["ERA"] - new_capped["ERA"])
            delta_WHIP = float(base_capped["WHIP"] - new_capped["WHIP"])

            val = (
                (delta_W / sgp_pit["W"] if sgp_pit["W"] else 0.0)
                + (delta_K / sgp_pit["K"] if sgp_pit["K"] else 0.0)
                + (delta_SVH / sgp_pit["SVH"] if sgp_pit["SVH"] else 0.0)
                + (delta_QA3 / sgp_pit["QA3"] if sgp_pit["QA3"] else 0.0)
                + (delta_ERA / sgp_pit["ERA"] if sgp_pit["ERA"] else 0.0)
                + (delta_WHIP / sgp_pit["WHIP"] if sgp_pit["WHIP"] else 0.0)
            )

            if val > best_val:
                best_val = val
                best_slot = slot

        pit_rows.append({
            "Player": getattr(row, "Player"),
            "Year": year,
            "Type": "P",
            "MLBTeam": getattr(row, "MLBTeam", np.nan),
            "Age": getattr(row, "Age", np.nan),
            "Pos": getattr(row, "Pos", np.nan),
            "BestSlot": best_slot,
            "YearValue": float(best_val),
        })

    pit_vals = pd.DataFrame(pit_rows)
    return hit_vals, pit_vals

def league_combine_hitter_pitcher_year(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame:
    merged = pd.merge(
        hit_vals[["Player", "Year", "YearValue", "BestSlot", "Pos", "MLBTeam", "Age"]],
        pit_vals[["Player", "Year", "YearValue", "BestSlot", "Pos", "MLBTeam", "Age"]],
        on=["Player", "Year"],
        how="outer",
        suffixes=("_hit", "_pit"),
    )

    combined_val = []
    combined_slot = []

    for _, r in merged.iterrows():
        hv = r.get("YearValue_hit")
        pv = r.get("YearValue_pit")

        if pd.isna(hv) and pd.isna(pv):
            combined_val.append(np.nan)
            combined_slot.append(None)
            continue

        if pd.isna(hv):
            combined_val.append(float(pv))
            combined_slot.append(r.get("BestSlot_pit"))
            continue

        if pd.isna(pv):
            combined_val.append(float(hv))
            combined_slot.append(r.get("BestSlot_hit"))
            continue

        hv = float(hv)
        pv = float(pv)

        if two_way == "sum":
            combined_val.append(hv + pv)
            combined_slot.append(f"{r.get('BestSlot_hit')}+{r.get('BestSlot_pit')}")
        else:
            if hv >= pv:
                combined_val.append(hv)
                combined_slot.append(r.get("BestSlot_hit"))
            else:
                combined_val.append(pv)
                combined_slot.append(r.get("BestSlot_pit"))

    merged["YearValue"] = combined_val
    merged["BestSlot"] = combined_slot

    merged["Pos"] = merged["Pos_hit"].combine_first(merged["Pos_pit"])
    merged["MLBTeam"] = merged["MLBTeam_hit"].combine_first(merged["MLBTeam_pit"])
    merged["Age"] = merged["Age_hit"].combine_first(merged["Age_pit"])

    return merged[["Player", "Year", "YearValue", "BestSlot", "Pos", "MLBTeam", "Age"]]


# ----------------------------
# XLSX output formatting
# ----------------------------

def _xlsx_apply_header_style(ws) -> None:
    """Apply a consistent header style to row 1."""
    max_col = ws.max_column
    if max_col < 1:
        return

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")  # dark blue
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="D9D9D9")
    header_border = Border(bottom=thin)

    ws.row_dimensions[1].height = 22
    for c in range(1, max_col + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = header_border


def _xlsx_set_freeze_filters_and_view(ws, freeze_panes: str, add_autofilter: bool = False) -> None:
    """Freeze panes, optionally add a worksheet AutoFilter, and hide gridlines.

    IMPORTANT:
      Excel Tables include their own AutoFilter. If the worksheet also has a
      worksheet-level AutoFilter over the same range, Excel will often open the
      file in "repair" mode and remove the Table/filters.

    By default we therefore *clear* any worksheet-level filter and rely on the
    Table's built-in filter dropdowns. Pass add_autofilter=True only for sheets
    where you are NOT creating a Table.
    """
    ws.freeze_panes = freeze_panes
    ws.sheet_view.showGridLines = False

    if add_autofilter:
        max_row = ws.max_row
        max_col = ws.max_column
        if max_row >= 1 and max_col >= 1:
            ref = f"A1:{get_column_letter(max_col)}{max_row}"
            ws.auto_filter.ref = ref
    else:
        # Clear worksheet-level AutoFilter to avoid conflicts with Excel Tables.
        ws.auto_filter.ref = None


def _xlsx_add_table(ws, table_name: str, style_name: str = "TableStyleMedium9") -> None:
    """Wrap the used range in an Excel Table for striping + filter dropdowns.

    Excel Tables carry their own AutoFilter. If a worksheet-level AutoFilter is
    also present (ws.auto_filter.ref), Excel may "repair" the workbook on open
    and remove the table. To prevent that, we clear any sheet-level AutoFilter
    before adding the Table.
    """
    max_row = ws.max_row
    max_col = ws.max_column
    if max_row < 2 or max_col < 1:
        return

    # Prevent Excel repair: don't mix worksheet AutoFilter + Table AutoFilter.
    ws.auto_filter.ref = None

    ref = f"A1:{get_column_letter(max_col)}{max_row}"
    tab = Table(displayName=table_name, ref=ref)
    tab.tableStyleInfo = TableStyleInfo(
        name=style_name,
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    ws.add_table(tab)


def _xlsx_set_column_widths(
    ws,
    df: pd.DataFrame,
    overrides: Optional[Dict[str, float]] = None,
    sample_rows: int = 1000,
    min_width: float = 8.0,
    max_width: float = 45.0,
) -> None:
    """Best-effort "auto-fit" widths with sensible caps (fast + readable)."""
    if df is None or df.empty:
        return

    overrides = dict(overrides or {})

    # Common dynamic overrides
    for col in df.columns:
        if isinstance(col, str) and col.startswith("Value_"):
            overrides.setdefault(col, 10.0)

    for i, col_name in enumerate(df.columns, start=1):
        letter = get_column_letter(i)

        # Explicit override wins
        if col_name in overrides:
            ws.column_dimensions[letter].width = float(overrides[col_name])
            continue

        s = df[col_name]

        # Dates (including Python date objects often come through as object dtype)
        if str(col_name).lower().endswith("date"):
            ws.column_dimensions[letter].width = 14.0
            continue

        # Numeric: keep compact
        if pd.api.types.is_numeric_dtype(s):
            base = max(len(str(col_name)) + 2, 10)
            ws.column_dimensions[letter].width = float(min(max(base, min_width), 16.0))
            continue

        # Boolean: compact
        if pd.api.types.is_bool_dtype(s):
            ws.column_dimensions[letter].width = float(max(12.0, len(str(col_name)) + 2))
            continue

        # Text/object: use a sample to estimate
        sample = s.dropna().astype(str).head(sample_rows)
        max_len = int(sample.str.len().max()) if not sample.empty else 0
        width = min(max(max_len, len(str(col_name))) + 2, int(max_width))
        width = max(float(width), float(min_width))
        ws.column_dimensions[letter].width = float(width)


def _xlsx_apply_number_formats(ws, df: pd.DataFrame, formats_by_col: Dict[str, str]) -> None:
    """Apply number formats to entire columns (data rows only)."""
    if df is None or df.empty:
        return

    max_row = ws.max_row
    if max_row < 2:
        return

    cols = list(df.columns)
    for col_name, fmt in formats_by_col.items():
        if col_name not in cols:
            continue
        col_idx = cols.index(col_name) + 1
        for r in range(2, max_row + 1):
            ws.cell(row=r, column=col_idx).number_format = fmt


def _xlsx_add_value_color_scale(ws, df: pd.DataFrame, col_name: str) -> None:
    """Add a red-yellow-green color scale on a value column for readability."""
    if df is None or df.empty:
        return
    if col_name not in df.columns:
        return
    max_row = ws.max_row
    if max_row < 3:
        return

    col_idx = list(df.columns).index(col_name) + 1
    col_letter = get_column_letter(col_idx)
    cell_range = f"{col_letter}2:{col_letter}{max_row}"

    rule = ColorScaleRule(
        start_type="min",
        start_color="F8696B",  # red
        mid_type="percentile",
        mid_value=50,
        mid_color="FFEB84",    # yellow
        end_type="max",
        end_color="63BE7B",    # green
    )
    ws.conditional_formatting.add(cell_range, rule)


def _xlsx_format_player_values(ws, df: pd.DataFrame, table_name: str = "PlayerValuesTbl") -> None:
    """Formatting for the summary tab."""
    _xlsx_apply_header_style(ws)
    _xlsx_set_freeze_filters_and_view(ws, freeze_panes="B2")
    _xlsx_add_table(ws, table_name=table_name)

    overrides = {
        "Player": 24.0,
        "Team": 8.0,
        "MLBTeam": 8.0,
        "Pos": 10.0,
        "OldestProjectionDate": 14.0,
        "DynastyValue": 12.0,
        "RawDynastyValue": 14.0,
        "CenteringBaselineMean": 16.0,
    }
    _xlsx_set_column_widths(ws, df, overrides=overrides)

    formats = {
        "ProjectionsUsed": "0",
        "Age": "0",
        "OldestProjectionDate": "yyyy-mm-dd",
        "DynastyValue": "0.00",
        "RawDynastyValue": "0.00",
        "CenteringBaselineMean": "0.00",
    }
    for c in df.columns:
        if isinstance(c, str) and c.startswith("Value_"):
            formats[c] = "0.00"
    _xlsx_apply_number_formats(ws, df, formats)

    # Helpful visual cue: color-scale DynastyValue
    _xlsx_add_value_color_scale(ws, df, "DynastyValue")


def _xlsx_format_detail_sheet(
    ws,
    df: pd.DataFrame,
    *,
    table_name: str,
    is_pitch: bool,
) -> None:
    """Formatting for Bat_Aggregated / Pitch_Aggregated."""
    _xlsx_apply_header_style(ws)
    # Freeze Player + Year (first two columns) + header row
    _xlsx_set_freeze_filters_and_view(ws, freeze_panes="C2")
    _xlsx_add_table(ws, table_name=table_name)

    overrides = {
        "Player": 24.0,
        "Team": 8.0,
        "MLBTeam": 8.0,
        "Pos": 10.0,
        "BestSlot": 10.0,
        "OldestProjectionDate": 14.0,
        "DynastyValue": 12.0,
        "RawDynastyValue": 14.0,
        "YearValue": 10.0,
    }
    _xlsx_set_column_widths(ws, df, overrides=overrides)

    # Core formats
    formats: Dict[str, str] = {
        "Year": "0",
        "Age": "0",
        "ProjectionsUsed": "0",
        "OldestProjectionDate": "yyyy-mm-dd",
        "YearValue": "0.00",
        "DynastyValue": "0.00",
        "RawDynastyValue": "0.00",
        "AVG": "0.000",
        "OBP": "0.000",
        "SLG": "0.000",
        "OPS": "0.000",
        "ERA": "0.00",
        "WHIP": "0.00",
        "IP": "0.0",
    }

    # Apply only formats for columns that exist in this sheet.
    _xlsx_apply_number_formats(ws, df, formats)

    # Color-scale the most important value columns.
    _xlsx_add_value_color_scale(ws, df, "YearValue")
    _xlsx_add_value_color_scale(ws, df, "DynastyValue")


# ----------------------------
# Dynasty aggregation + centering
# ----------------------------

def league_infer_minor_eligible_start(bat_df: pd.DataFrame, pit_df: pd.DataFrame, lg: LeagueSettings, start_year: int) -> pd.DataFrame:
    """
    Best-effort minor eligibility inference if career AB/IP not provided:
      - hitter: projected AB <= 130 AND Age <= infer_minor_age_max_hit
      - pitcher: projected IP <= 50 AND Age <= infer_minor_age_max_pit
    """
    bat_y = bat_df[bat_df["Year"] == start_year][["Player", "AB", "Age"]].copy()
    pit_y = pit_df[pit_df["Year"] == start_year][["Player", "IP", "Age"]].copy()

    bat_y = bat_y.groupby("Player", as_index=False).agg({"AB": "max", "Age": "min"})
    pit_y = pit_y.groupby("Player", as_index=False).agg({"IP": "max", "Age": "min"})

    m = pd.merge(bat_y, pit_y, on="Player", how="outer", suffixes=("_hit", "_pit"))
    m["Age"] = m["Age_hit"].combine_first(m["Age_pit"])
    m["AB"] = m["AB"].fillna(0.0)
    m["IP"] = m["IP"].fillna(0.0)

    m["minor_eligible"] = (
        ((m["AB"] > 0) & (m["AB"] <= lg.minor_hitters_career_ab_max) & (m["Age"] <= lg.infer_minor_age_max_hit))
        | ((m["IP"] > 0) & (m["IP"] <= lg.minor_pitchers_career_ip_max) & (m["Age"] <= lg.infer_minor_age_max_pit))
    )

    return m[["Player", "minor_eligible"]]

def calculate_league_dynasty_values(
    excel_path: str,
    lg: LeagueSettings,
    start_year: Optional[int] = None,
    years: Optional[List[int]] = None,
    verbose: bool = True,
    return_details: bool = False,
    seed: int = 0,
    recent_projections: int = 3,
):
    """League-mode dynasty values (your custom categories/rules).

    If return_details=True, also returns (bat_detail, pit_detail) tables that:
      - collapse duplicate (Player, Year) rows by averaging the most-recent 3 projections
      - keep the original input columns in roughly the same order
      - attach YearValue/BestSlot (per side) and DynastyValue to each Player/Year row
    """
    if linear_sum_assignment is None:
        raise ImportError("scipy is required for league mode (linear_sum_assignment not available).")

    bat_raw = normalize_input_schema(pd.read_excel(excel_path, sheet_name="Bat"), LEAGUE_COLUMN_ALIASES)
    pit_raw = normalize_input_schema(pd.read_excel(excel_path, sheet_name="Pitch"), LEAGUE_COLUMN_ALIASES)

    bat_input_cols = list(bat_raw.columns)
    pit_input_cols = list(pit_raw.columns)
    bat_date_col = _find_projection_date_col(bat_raw)
    pit_date_col = _find_projection_date_col(pit_raw)

    # Average *all numeric stat columns* (except derived rates and Age) so the
    # aggregated detail tabs (and category stats like SVH/QA3) reflect the true averaged projections.
    bat_stat_cols = numeric_stat_cols_for_recent_avg(
        bat_raw,
        group_cols=["Player", "Year"],
        exclude_cols={"Age"} | DERIVED_HIT_RATE_COLS,
    )
    pit_stat_cols = numeric_stat_cols_for_recent_avg(
        pit_raw,
        group_cols=["Player", "Year"],
        exclude_cols={"Age"} | DERIVED_PIT_RATE_COLS,
    )

    bat_df = average_recent_projections(bat_raw, bat_stat_cols, max_entries=recent_projections)
    pit_df = average_recent_projections(pit_raw, pit_stat_cols, max_entries=recent_projections)

    bat_df = recompute_league_rates_hit(bat_df)
    pit_df = recompute_league_rates_pit(pit_df)
    pit_df = league_ensure_pitch_cols(pit_df)

    require_cols(
        bat_df,
        ["Player", "Year", "MLBTeam", "Age", "Pos", "AB", "H", "R", "HR", "RBI", "SB", "BB", "HBP", "SF", "2B", "3B"],
        "Bat",
    )
    require_cols(
        pit_df,
        ["Player", "Year", "MLBTeam", "Age", "Pos", "IP", "W", "K", "SVH", "QA3", "ER", "H", "BB"],
        "Pitch",
    )

    if years is None:
        if start_year is None:
            start_year = int(min(bat_df["Year"].min(), pit_df["Year"].min()))
        max_year = int(max(bat_df["Year"].max(), pit_df["Year"].max()))
        years = [y for y in range(start_year, start_year + lg.horizon_years) if y <= max_year]
    else:
        if start_year is None:
            start_year = int(min(years))
        max_year = int(max(bat_df["Year"].max(), pit_df["Year"].max()))
        years = [y for y in years if y <= max_year]

    if not years:
        raise ValueError("No valuation years available after applying start year / horizon to projection file years.")

    # Projection metadata: how many projections were averaged (<=3) and the oldest date used
    proj_meta = projection_meta_for_start_year(bat_df, pit_df, start_year)

    # --- Minor eligibility (for roster selection + output/centering) ---
    # Explicit eligibility from input is authoritative when present; only infer as fallback.
    input_elig = minor_eligibility_from_input(bat_df, pit_df, start_year)
    if input_elig is not None:
        elig_df = input_elig.copy()
    else:
        elig_df = league_infer_minor_eligible_start(bat_df, pit_df, lg, start_year)
    elig_df["minor_eligible"] = _fillna_bool(elig_df["minor_eligible"])

    # Roster depth (league-wide)
    active_per_team = sum(lg.hitter_slots.values()) + sum(lg.pitcher_slots.values())  # should be 23
    total_minor_slots = lg.n_teams * lg.minor_slots
    total_mlb_slots = lg.n_teams * (active_per_team + lg.bench_slots + lg.ir_slots)

    # ------------------------------------------------------------------
    # PASS 1: compute average-starter year values (for a "stash score" that
    #         approximates who is rostered in a deep dynasty league).
    # ------------------------------------------------------------------
    year_contexts: Dict[int, dict] = {}
    year_tables_avg: List[pd.DataFrame] = []

    for y in years:
        if verbose:
            print(f"Year {y}: building baseline + SGP + player values (avg-starter pass) ...")
        ctx = league_compute_year_context(y, bat_df, pit_df, lg, rng_seed=seed + y)
        year_contexts[y] = ctx

        hit_vals, pit_vals = league_compute_year_player_values(ctx, lg)  # vs average starter
        combined = league_combine_hitter_pitcher_year(hit_vals, pit_vals, two_way=lg.two_way)
        year_tables_avg.append(combined)

    all_year_avg = pd.concat(year_tables_avg, ignore_index=True)

    # Stash score: optimal keep/drop value on the avg-starter YearValue stream.
    # Minor-eligible players can be stashed in minors (negative years treated as 0)
    # when the league has minors slots.
    elig_map = dict(zip(elig_df["Player"], elig_df["minor_eligible"].astype(bool)))

    wide_avg = all_year_avg.pivot_table(index="Player", columns="Year", values="YearValue", aggfunc="max").reset_index()

    # Ensure every horizon year exists as a column (missing years => 0 value)
    for y in years:
        if y not in wide_avg.columns:
            wide_avg[y] = 0.0

    def _stash_row(row: pd.Series) -> float:
        player = row["Player"]
        can_stash = bool(lg.minor_slots and lg.minor_slots > 0 and bool(elig_map.get(player, False)))

        vals: List[float] = []
        for y in years:
            v = row.get(y)
            if pd.isna(v):
                v = 0.0
            v = float(v)
            if can_stash and v < 0.0:
                v = 0.0
            vals.append(v)

        return dynasty_keep_or_drop_value(vals, years, lg.discount)

    wide_avg["StashScore"] = wide_avg.apply(_stash_row, axis=1)
    stash = wide_avg[["Player", "StashScore"]].copy()

    stash = stash.merge(elig_df, on="Player", how="left")
    stash["minor_eligible"] = _fillna_bool(stash["minor_eligible"])

    # Determine rostered set (minors reserved first, then the rest)
    stash_sorted = stash.sort_values("StashScore", ascending=False).reset_index(drop=True)

    minors_pool = stash_sorted[stash_sorted["minor_eligible"]]
    minors_sel = minors_pool.head(total_minor_slots)
    minor_names = set(minors_sel["Player"])

    remaining = stash_sorted[~stash_sorted["Player"].isin(minor_names)]
    extra_minor_needed = max(total_minor_slots - len(minors_sel), 0)
    extra_minors = remaining.head(extra_minor_needed)
    extra_minor_names = set(extra_minors["Player"])

    remaining = remaining[~remaining["Player"].isin(extra_minor_names)]
    mlb_sel = remaining.head(total_mlb_slots)

    rostered_names: Set[str] = set(mlb_sel["Player"]) | minor_names | extra_minor_names

    # ------------------------------------------------------------------
    # PASS 2: compute per-year values vs *replacement* (from unrostered pool)
    # ------------------------------------------------------------------
    year_tables: List[pd.DataFrame] = []
    hit_year_tables: List[pd.DataFrame] = []
    pit_year_tables: List[pd.DataFrame] = []

    for y in years:
        if verbose:
            print(f"Year {y}: computing replacement baselines + player values (replacement pass) ...")
        ctx = year_contexts[y]

        repl_hit, repl_pit = league_compute_replacement_baselines(ctx, lg, rostered_names, n_repl=lg.n_teams)
        hit_vals, pit_vals = league_compute_year_player_values_vs_replacement(ctx, lg, repl_hit, repl_pit)

        # Store side-specific year values for the detail tabs
        if not hit_vals.empty:
            hit_year_tables.append(hit_vals[["Player", "Year", "BestSlot", "YearValue"]].copy())
        if not pit_vals.empty:
            pit_year_tables.append(pit_vals[["Player", "Year", "BestSlot", "YearValue"]].copy())

        combined = league_combine_hitter_pitcher_year(hit_vals, pit_vals, two_way=lg.two_way)
        year_tables.append(combined)

    all_year_vals = pd.concat(year_tables, ignore_index=True)

    # Wide table (one row per player) with Value_YEAR columns
    wide = all_year_vals.pivot_table(index="Player", columns="Year", values="YearValue", aggfunc="max").reset_index()
    wide.columns = ["Player"] + [f"Value_{int(c)}" for c in wide.columns[1:]]

    # Metadata from start year
    meta = (
        all_year_vals[all_year_vals["Year"] == start_year][["Player", "MLBTeam", "Pos", "Age"]]
        .drop_duplicates("Player")
    )

    out = meta.merge(wide, on="Player", how="right")

    # Attach projection metadata (based on the start-year averaged projections)
    out = out.merge(proj_meta, on="Player", how="left")

    # Raw dynasty value: optimal keep/drop value.
    #
    # - If the player can be stashed in a minors slot (league has minors slots AND player is minors-eligible),
    #   negative years are treated as 0 (no holding penalty while stashed).
    # - Otherwise, negative years *do* count as a cost if you keep the player, but you can drop the player
    #   permanently for 0 at any year boundary.
    raw_vals: List[float] = []
    for _, r in out.iterrows():
        player = r.get("Player")
        can_stash = bool(lg.minor_slots and lg.minor_slots > 0 and bool(elig_map.get(player, False)))

        vals: List[float] = []
        for y in years:
            col = f"Value_{y}"
            v = r.get(col)
            if pd.isna(v):
                v = 0.0
            v = float(v)
            if can_stash and v < 0.0:
                v = 0.0
            vals.append(v)

        raw_vals.append(dynasty_keep_or_drop_value(vals, years, lg.discount))

    out["RawDynastyValue"] = raw_vals

    # Attach minor eligibility (for centering + output)
    out = out.merge(elig_df, on="Player", how="left")
    out["minor_eligible"] = _fillna_bool(out["minor_eligible"])

    # Center so replacement-level rostered cutoff ~= 0 (active + bench + minors + IR)
    out_sorted = out.sort_values("RawDynastyValue", ascending=False).reset_index(drop=True)

    minors_pool = out_sorted[out_sorted["minor_eligible"]]
    minors_sel = minors_pool.head(total_minor_slots)
    minor_names = set(minors_sel["Player"])

    remaining = out_sorted[~out_sorted["Player"].isin(minor_names)]
    extra_minor_needed = max(total_minor_slots - len(minors_sel), 0)
    extra_minors = remaining.head(extra_minor_needed)
    extra_minor_names = set(extra_minors["Player"])

    remaining = remaining[~remaining["Player"].isin(extra_minor_names)]
    mlb_sel = remaining.head(total_mlb_slots)

    rostered = pd.concat([minors_sel, extra_minors, mlb_sel], ignore_index=True)
    baseline_value = float(rostered["RawDynastyValue"].iloc[-1]) if len(rostered) else 0.0

    out["DynastyValue"] = out["RawDynastyValue"] - baseline_value
    out["CenteringBaselineValue"] = baseline_value
    out["CenteringBaselineMean"] = baseline_value

    out = out.sort_values("DynastyValue", ascending=False).reset_index(drop=True)

    if not return_details:
        return out

    # ----------------------------
    # Detail tabs (aggregated projections + value columns)
    # ----------------------------
    hit_year = pd.concat(hit_year_tables, ignore_index=True) if hit_year_tables else pd.DataFrame(columns=["Player", "Year", "BestSlot", "YearValue"])
    pit_year = pd.concat(pit_year_tables, ignore_index=True) if pit_year_tables else pd.DataFrame(columns=["Player", "Year", "BestSlot", "YearValue"])

    player_vals = out[["Player", "DynastyValue", "RawDynastyValue", "minor_eligible"]].copy()

    bat_detail = bat_df.merge(hit_year, on=["Player", "Year"], how="left")
    bat_detail = bat_detail.merge(player_vals, on="Player", how="left")

    pit_detail = pit_df.merge(pit_year, on=["Player", "Year"], how="left")
    pit_detail = pit_detail.merge(player_vals, on="Player", how="left")

    extra = ["ProjectionsUsed", "OldestProjectionDate", "BestSlot", "YearValue", "DynastyValue", "RawDynastyValue", "minor_eligible"]
    bat_detail = reorder_detail_columns(bat_detail, bat_input_cols, add_after=bat_date_col, extra_cols=extra)
    pit_detail = reorder_detail_columns(pit_detail, pit_input_cols, add_after=pit_date_col, extra_cols=extra)

    return out, bat_detail, pit_detail

# ----------------------------
# CLI (subcommands)
# ----------------------------

def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="mode", required=True)

    common = sub.add_parser("common", help="Run the common 5x5 dynasty roto valuation.")
    common.add_argument(
        "--input",
        default="Dynasty Baseball Projections.xlsx",
        help="Excel file with Bat and Pitch sheets (default: Dynasty Baseball Projections.xlsx).",
    )
    common.add_argument("--start-year", type=int, default=None, help="First valuation year (default: min Year in file).")
    common.add_argument("--teams", type=positive_int_arg, default=12)
    common.add_argument("--sims", type=positive_int_arg, default=200, help="Monte Carlo sims for SGP denominators.")
    common.add_argument("--horizon", type=positive_int_arg, default=10, help="Dynasty horizon years.")
    common.add_argument("--discount", type=discount_arg, default=0.85, help="Annual discount factor in (0, 1].")
    common.add_argument("--seed", type=int, default=0, help="Global random seed offset for deterministic simulations.")
    common.add_argument("--bench", type=non_negative_int_arg, default=6)
    common.add_argument("--minors", type=non_negative_int_arg, default=0)
    common.add_argument("--ir", type=non_negative_int_arg, default=0)
    common.add_argument("--ip-min", type=non_negative_float_arg, default=0.0, help="Optional IP minimum to qualify for ERA/WHIP (default 0).")
    common.add_argument(
        "--ip-max",
        type=optional_non_negative_float_arg,
        default=None,
        help="Optional IP maximum/cap (default none). Accepts numeric values or 'none'.",
    )
    common.add_argument("--out-prefix", default="common_player_values", help="Output prefix for CSV/XLSX.")
    common.add_argument("--recent-projections", type=positive_int_arg, default=3, help="Number of most recent projections to average per player/year.")

    league = sub.add_parser("league", help="Run the custom league valuation from the original my-league script.")
    league.add_argument(
        "--input",
        default="Dynasty Baseball Projections.xlsx",
        help="Excel file with Bat and Pitch sheets (default: Dynasty Baseball Projections.xlsx).",
    )
    league.add_argument("--start-year", type=int, default=None, help="First valuation year (default: min Year in file).")
    league.add_argument("--sims", type=positive_int_arg, default=200, help="Monte Carlo sims for SGP denominators.")
    league.add_argument("--horizon", type=positive_int_arg, default=10, help="Dynasty horizon years.")
    league.add_argument("--discount", type=discount_arg, default=0.85, help="Annual discount factor in (0, 1].")
    league.add_argument("--seed", type=int, default=0, help="Global random seed offset for deterministic simulations.")
    league.add_argument("--out-prefix", default="player_values", help="Output prefix for CSV/XLSX.")
    league.add_argument("--recent-projections", type=positive_int_arg, default=3, help="Number of most recent projections to average per player/year.")

    args = p.parse_args()

    bat_detail = None
    pit_detail = None

    if args.mode == "common":
        validate_ip_bounds(args.ip_min, args.ip_max)
        lg = CommonDynastyRotoSettings(
            n_teams=args.teams,
            sims_for_sgp=args.sims,
            horizon_years=args.horizon,
            discount=args.discount,
            bench_slots=args.bench,
            minor_slots=args.minors,
            ir_slots=args.ir,
            ip_min=args.ip_min,
            ip_max=args.ip_max,
        )

        out, bat_detail, pit_detail = calculate_common_dynasty_values(
            args.input,
            lg,
            start_year=args.start_year,
            verbose=True,
            return_details=True,
            seed=args.seed,
            recent_projections=args.recent_projections,
        )

        year_cols = [c for c in out.columns if c.startswith("Value_")]
        df = out[
            [
                "Player",
                "ProjectionsUsed",
                "OldestProjectionDate",
                "Team",
                "Pos",
                "Age",
                "DynastyValue",
                "RawDynastyValue",
                "minor_eligible",
            ]
            + year_cols
            + ["CenteringBaselineMean"]
        ]

    else:
        lg = LeagueSettings(
            sims_for_sgp=args.sims,
            horizon_years=args.horizon,
            discount=args.discount,
            two_way="max",
        )
        validate_ip_bounds(lg.ip_min, lg.ip_max)

        out, bat_detail, pit_detail = calculate_league_dynasty_values(
            args.input,
            lg,
            start_year=args.start_year,
            verbose=True,
            return_details=True,
            seed=args.seed,
            recent_projections=args.recent_projections,
        )

        year_cols = [c for c in out.columns if c.startswith("Value_")]
        df = out[
            [
                "Player",
                "ProjectionsUsed",
                "OldestProjectionDate",
                "MLBTeam",
                "Pos",
                "Age",
                "DynastyValue",
                "RawDynastyValue",
                "minor_eligible",
            ]
            + year_cols
        ]

    csv_path = f"{args.out_prefix}.csv"
    xlsx_path = f"{args.out_prefix}.xlsx"

    # CSV stays as the compact per-player summary (same as before)
    df.to_csv(csv_path, index=False)

    # XLSX now includes extra detail tabs:
    #   - PlayerValues (summary)
    #   - Bat_Aggregated (aggregated Bat sheet + YearValue + DynastyValue)
    #   - Pitch_Aggregated (aggregated Pitch sheet + YearValue + DynastyValue)
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="PlayerValues", index=False)
        if bat_detail is not None:
            bat_detail.to_excel(writer, sheet_name="Bat_Aggregated", index=False)
        if pit_detail is not None:
            pit_detail.to_excel(writer, sheet_name="Pitch_Aggregated", index=False)

        # ----------------------------
        # Formatting pass (openpyxl)
        # ----------------------------
        try:
            if "PlayerValues" in writer.sheets:
                _xlsx_format_player_values(writer.sheets["PlayerValues"], df, table_name="PlayerValuesTbl")

            if bat_detail is not None and "Bat_Aggregated" in writer.sheets:
                _xlsx_format_detail_sheet(
                    writer.sheets["Bat_Aggregated"],
                    bat_detail,
                    table_name="BatAggregatedTbl",
                    is_pitch=False,
                )

            if pit_detail is not None and "Pitch_Aggregated" in writer.sheets:
                _xlsx_format_detail_sheet(
                    writer.sheets["Pitch_Aggregated"],
                    pit_detail,
                    table_name="PitchAggregatedTbl",
                    is_pitch=True,
                )
        except Exception as e:
            # Formatting should never prevent producing the workbook.
            print(f"WARNING: Failed to apply Excel formatting: {e}")

    print("\nTop 25 by DynastyValue:")
    print(df.head(25).to_string(index=False))
    print(f"\nWrote: {csv_path}")
    print(f"Wrote: {xlsx_path}")

if __name__ == "__main__":
    main()
