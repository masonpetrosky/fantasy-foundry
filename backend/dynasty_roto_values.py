"""Legacy compatibility surface for dynasty valuation helpers and CLI."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd

try:
    from backend.valuation.assignment import (
        HAVE_SCIPY,
        assign_players_to_slots,
        assign_players_to_slots_with_vacancy_fill,
        build_slot_list,
        build_team_slot_template,
        expand_slot_counts,
        league_assign_players_to_slots,
        league_build_slot_list,
        league_build_team_slot_template,
        league_expand_slot_counts,
        validate_assigned_slots,
    )
    from backend.valuation.models import (
        CommonDynastyRotoSettings,
        HIT_CATS,
        HIT_COMPONENT_COLS,
        LEAGUE_HIT_STAT_COLS,
        LeagueSettings,
        PIT_CATS,
        PIT_COMPONENT_COLS,
    )
    from backend.valuation.positions import (
        eligible_hit_slots,
        eligible_pit_slots,
        league_eligible_hit_slots,
        league_eligible_pit_slots,
        league_parse_hit_positions,
        league_parse_pit_positions,
        parse_hit_positions,
        parse_pit_positions,
    )
    from backend.valuation import common_math as _common_math
    from backend.valuation import league_math as _league_math
    from backend.valuation import minor_eligibility as _minor_elig
    from backend.valuation import xlsx_formatting as _xlsx_fmt
except ImportError:
    # Support direct execution/import when /backend is added to sys.path.
    from valuation.assignment import (
        HAVE_SCIPY,
        assign_players_to_slots,
        assign_players_to_slots_with_vacancy_fill,
        build_slot_list,
        build_team_slot_template,
        expand_slot_counts,
        league_assign_players_to_slots,
        league_build_slot_list,
        league_build_team_slot_template,
        league_expand_slot_counts,
        validate_assigned_slots,
    )
    from valuation.models import (
        CommonDynastyRotoSettings,
        HIT_CATS,
        HIT_COMPONENT_COLS,
        LEAGUE_HIT_STAT_COLS,
        LeagueSettings,
        PIT_CATS,
        PIT_COMPONENT_COLS,
    )
    from valuation.positions import (
        eligible_hit_slots,
        eligible_pit_slots,
        league_eligible_hit_slots,
        league_eligible_pit_slots,
        league_parse_hit_positions,
        league_parse_pit_positions,
        parse_hit_positions,
        parse_pit_positions,
    )
    from valuation import common_math as _common_math
    from valuation import league_math as _league_math
    from valuation import minor_eligibility as _minor_elig
    from valuation import xlsx_formatting as _xlsx_fmt

# Projection de-duplication helpers
PROJECTION_DATE_COLS = ["ProjectionDate", "Date", "Updated", "LastUpdated", "Timestamp", "Created", "AsOf"]
PLAYER_KEY_COL = "PlayerKey"
PLAYER_ENTITY_KEY_COL = "PlayerEntityKey"
PLAYER_KEY_PATTERN = re.compile(r"[^a-z0-9]+")

# Bench-stash penalty curve defaults:
# - first stash round per team should still carry a small cost
# - later rounds are progressively more punitive
BENCH_STASH_MIN_PENALTY = 0.10
BENCH_STASH_MAX_PENALTY = 0.85
BENCH_STASH_PENALTY_GAMMA = 1.35


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
        numeric = float(value)
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
    effective_group_cols = list(group_cols)

    missing_group_cols = [c for c in group_cols if c not in df.columns]
    if missing_group_cols:
        raise ValueError(f"average_recent_projections missing required group columns: {missing_group_cols}")

    team_col = _team_column_for_dataframe(df)
    if (
        team_col
        and "Player" in group_cols
        and "Year" in group_cols
        and "_entity_team" not in effective_group_cols
    ):
        team_values = df[team_col].astype("string").fillna("").str.strip()
        team_nonempty = team_values.where(team_values != "", pd.NA)
        team_counts = team_nonempty.groupby([df[c] for c in group_cols], dropna=False).transform("nunique")
        if team_counts.gt(1).any():
            # Split only ambiguous same-name/same-year groups where teams differ.
            df["_entity_team"] = team_values.where(team_counts > 1, "")
            effective_group_cols.append("_entity_team")

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
        .groupby(effective_group_cols, as_index=False, sort=False)
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
        and c not in effective_group_cols
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
        .groupby(effective_group_cols, as_index=False, sort=False)
        .agg(agg)
    )
    out = out.drop(columns=["_entity_team"], errors="ignore")

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

DERIVED_HIT_RATE_COLS: Set[str] = {"AVG", "OBP", "SLG", "OPS"}
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

    Recompute AVG/OBP/SLG/OPS (plus TB) from counting components when possible so
    aggregated rows stay internally consistent.
    """
    df = df.copy()

    # AVG = H / AB
    if "H" in df.columns and "AB" in df.columns:
        h = df["H"].to_numpy(dtype=float)
        ab = df["AB"].to_numpy(dtype=float)
        df["AVG"] = np.divide(h, ab, out=np.zeros_like(h), where=ab > 0)

    # OBP + OPS (OPS = OBP + SLG)
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

        df["TB"] = tb
        df["OBP"] = obp
        df["SLG"] = slg
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

# ----------------------------
# Column aliases and requirements
# ----------------------------

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

def _active_common_hit_categories(lg: CommonDynastyRotoSettings) -> List[str]:
    configured = getattr(lg, "hitter_categories", None)
    if not configured:
        return list(HIT_CATS)
    wanted = {str(cat).strip().upper() for cat in configured if str(cat).strip()}
    selected = [cat for cat in HIT_CATS if cat.upper() in wanted]
    return selected or list(HIT_CATS)


def _active_common_pitch_categories(lg: CommonDynastyRotoSettings) -> List[str]:
    configured = getattr(lg, "pitcher_categories", None)
    if not configured:
        return list(PIT_CATS)
    wanted = {str(cat).strip().upper() for cat in configured if str(cat).strip()}
    selected = [cat for cat in PIT_CATS if cat.upper() in wanted]
    return selected or list(PIT_CATS)


def initial_hitter_weight(df: pd.DataFrame, categories: Optional[List[str]] = None) -> pd.Series:
    """
    Rough first-pass weight to select/assign starters with positional scarcity.
    Uses selected categories with rate stats translated into counting impact.
    """
    df = df.copy()
    selected = {str(cat).strip().upper() for cat in (categories or list(HIT_CATS))}
    components: List[pd.Series] = []

    h = df["H"].astype(float)
    ab = df["AB"].astype(float)
    b2 = df["2B"].astype(float)
    b3 = df["3B"].astype(float)
    hr = df["HR"].astype(float)
    bb = df["BB"].astype(float)
    hbp = df["HBP"].astype(float)
    sf = df["SF"].astype(float)

    tb = h + b2 + 2.0 * b3 + 3.0 * hr
    obp_den = ab + bb + hbp + sf
    avg = np.divide(h, ab, out=np.zeros_like(ab, dtype=float), where=ab > 0)
    obp = np.divide(h + bb + hbp, obp_den, out=np.zeros_like(obp_den, dtype=float), where=obp_den > 0)
    slg = np.divide(tb, ab, out=np.zeros_like(ab, dtype=float), where=ab > 0)
    ops = obp + slg

    counting_sources: Dict[str, pd.Series] = {
        "R": df["R"].astype(float),
        "RBI": df["RBI"].astype(float),
        "HR": hr,
        "SB": df["SB"].astype(float),
        "H": h,
        "BB": bb,
        "2B": b2,
        "TB": pd.Series(tb, index=df.index),
    }
    for cat, series in counting_sources.items():
        if cat in selected:
            components.append(zscore(series))

    if "AVG" in selected:
        mean_avg = float(np.nanmean(avg)) if len(avg) else 0.0
        components.append(zscore(pd.Series((avg - mean_avg) * ab, index=df.index)))
    if "OBP" in selected:
        mean_obp = float(np.nanmean(obp)) if len(obp) else 0.0
        components.append(zscore(pd.Series((obp - mean_obp) * obp_den, index=df.index)))
    if "SLG" in selected:
        mean_slg = float(np.nanmean(slg)) if len(slg) else 0.0
        components.append(zscore(pd.Series((slg - mean_slg) * ab, index=df.index)))
    if "OPS" in selected:
        mean_ops = float(np.nanmean(ops)) if len(ops) else 0.0
        components.append(zscore(pd.Series((ops - mean_ops) * ab, index=df.index)))

    if not components:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)

    w = components[0].copy()
    for component in components[1:]:
        w = w + component
    return w


def initial_pitcher_weight(df: pd.DataFrame, categories: Optional[List[str]] = None) -> pd.Series:
    """
    Rough first-pass weight for pitchers:
    counting stats + "runs prevented" (ERA) + "baserunners prevented" (WHIP),
    both scaled by IP to reflect volume.
    """
    df = df.copy()
    selected = {str(cat).strip().upper() for cat in (categories or list(PIT_CATS))}
    components: List[pd.Series] = []

    for cat in ("W", "K", "SV", "QS", "QA3", "SVH"):
        if cat in selected:
            components.append(zscore(df[cat]))

    if "ERA" in selected or "WHIP" in selected:
        ip_sum = float(df["IP"].sum())
        mean_era = float(9.0 * df["ER"].sum() / ip_sum) if ip_sum > 0 else float(df["ERA"].mean())
        mean_whip = float((df["H"].sum() + df["BB"].sum()) / ip_sum) if ip_sum > 0 else float(df["WHIP"].mean())
        if "ERA" in selected:
            df["ERA_surplus_ER"] = (mean_era - df["ERA"]) * df["IP"] / 9.0
            components.append(zscore(df["ERA_surplus_ER"]))
        if "WHIP" in selected:
            df["WHIP_surplus"] = (mean_whip - df["WHIP"]) * df["IP"]
            components.append(zscore(df["WHIP_surplus"]))

    if not components:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)

    w = components[0].copy()
    for component in components[1:]:
        w = w + component
    return w


# ----------------------------
# Team stat calculations (default 5x5)
# ----------------------------

def team_avg(H: float, AB: float) -> float:
    return float(H / AB) if AB > 0 else 0.0

def team_obp(H: float, BB: float, HBP: float, AB: float, SF: float) -> float:
    den = AB + BB + HBP + SF
    return float((H + BB + HBP) / den) if den > 0 else 0.0

def team_ops(H: float, BB: float, HBP: float, AB: float, SF: float, b2: float, b3: float, HR: float) -> float:
    obp = team_obp(H, BB, HBP, AB, SF)
    slg = float((H + b2 + 2.0 * b3 + 3.0 * HR) / AB) if AB > 0 else 0.0
    return float(obp + slg)

def team_era(ER: float, IP: float) -> float:
    return float(9.0 * ER / IP) if IP > 0 else float("nan")

def team_whip(H: float, BB: float, IP: float) -> float:
    return float((H + BB) / IP) if IP > 0 else float("nan")


COMMON_REVERSED_PITCH_CATS: Set[str] = {"ERA", "WHIP"}


def common_hit_category_totals(totals: Dict[str, float]) -> Dict[str, float]:
    return _common_math.common_hit_category_totals(totals)


def common_pitch_category_totals(totals: Dict[str, float]) -> Dict[str, float]:
    return _common_math.common_pitch_category_totals(totals)


def common_replacement_pitcher_rates(
    all_pit_df: pd.DataFrame,
    assigned_pit_df: pd.DataFrame,
    n_rep: int,
) -> Dict[str, float]:
    return _common_math.common_replacement_pitcher_rates(all_pit_df, assigned_pit_df, n_rep)


def common_apply_pitching_bounds(
    totals: Dict[str, float],
    lg: CommonDynastyRotoSettings,
    rep_rates: Optional[Dict[str, float]],
    *,
    fill_to_ip_max: bool = True,
    enforce_ip_min: bool = True,
) -> Dict[str, float]:
    return _common_math.common_apply_pitching_bounds(
        totals,
        lg,
        rep_rates,
        fill_to_ip_max=fill_to_ip_max,
        enforce_ip_min=enforce_ip_min,
    )


def _coerce_non_negative_float(value: object) -> float:
    return _common_math._coerce_non_negative_float(value)


def _low_volume_positive_credit_scale(
    *,
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> float:
    return _common_math._low_volume_positive_credit_scale(
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )


def _apply_low_volume_non_ratio_positive_guard(
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> None:
    return _common_math._apply_low_volume_non_ratio_positive_guard(
        delta,
        pit_categories=pit_categories,
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )


def _apply_low_volume_ratio_guard(
    delta: Dict[str, float],
    *,
    pit_categories: List[str],
    pitcher_ip: float,
    slot_ip_reference: float,
    min_share_for_positive_ratio_credit: float = 0.35,
    full_share_for_positive_ratio_credit: float = 1.00,
) -> None:
    return _common_math._apply_low_volume_ratio_guard(
        delta,
        pit_categories=pit_categories,
        pitcher_ip=pitcher_ip,
        slot_ip_reference=slot_ip_reference,
        min_share_for_positive_ratio_credit=min_share_for_positive_ratio_credit,
        full_share_for_positive_ratio_credit=full_share_for_positive_ratio_credit,
    )


# ----------------------------
# Monte Carlo SGP denominators
# ----------------------------

def _mean_adjacent_rank_gap(values: np.ndarray, *, ascending: bool) -> float:
    return _common_math._mean_adjacent_rank_gap(values, ascending=ascending)


def simulate_sgp_hit(
    assigned_hit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng: np.random.Generator,
    categories: Optional[List[str]] = None,
) -> Dict[str, float]:
    return _common_math.simulate_sgp_hit(assigned_hit, lg, rng, categories=categories)

def simulate_sgp_pit(
    assigned_pit: pd.DataFrame,
    lg: CommonDynastyRotoSettings,
    rng: np.random.Generator,
    rep_rates: Optional[Dict[str, float]] = None,
    categories: Optional[List[str]] = None,
) -> Dict[str, float]:
    return _common_math.simulate_sgp_pit(
        assigned_pit,
        lg,
        rng,
        rep_rates=rep_rates,
        categories=categories,
    )


# ----------------------------
# Year context + player year values
# ----------------------------

def compute_year_context(year: int, bat: pd.DataFrame, pit: pd.DataFrame, lg: CommonDynastyRotoSettings, rng_seed: Optional[int] = None) -> dict:
    return _common_math.compute_year_context(year, bat, pit, lg, rng_seed=rng_seed)

def compute_year_player_values(ctx: dict, lg: CommonDynastyRotoSettings) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return _common_math.compute_year_player_values(ctx, lg)


def compute_replacement_baselines(
    ctx: dict,
    lg: CommonDynastyRotoSettings,
    rostered_players: Set[str],
    n_repl: Optional[int] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return _common_math.compute_replacement_baselines(
        ctx,
        lg,
        rostered_players=rostered_players,
        n_repl=n_repl,
    )


def compute_year_player_values_vs_replacement(
    ctx: dict,
    lg: CommonDynastyRotoSettings,
    repl_hit: pd.DataFrame,
    repl_pit: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    return _common_math.compute_year_player_values_vs_replacement(
        ctx,
        lg,
        repl_hit=repl_hit,
        repl_pit=repl_pit,
    )


def combine_two_way(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame:
    return _common_math.combine_two_way(hit_vals, pit_vals, two_way)


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

def _infer_minor_eligibility_by_year(
    bat_df: pd.DataFrame,
    pit_df: pd.DataFrame,
    *,
    years: Optional[List[int]],
    hitter_usage_max: int,
    pitcher_usage_max: int,
    hitter_age_max: int,
    pitcher_age_max: int,
) -> pd.DataFrame:
    return _minor_elig._infer_minor_eligibility_by_year(
        bat_df,
        pit_df,
        years=years,
        hitter_usage_max=hitter_usage_max,
        pitcher_usage_max=pitcher_usage_max,
        hitter_age_max=hitter_age_max,
        pitcher_age_max=pitcher_age_max,
    )


def infer_minor_eligible(bat: pd.DataFrame, pit: pd.DataFrame, lg: CommonDynastyRotoSettings, start_year: int) -> pd.DataFrame:
    return _minor_elig.infer_minor_eligible(bat, pit, lg, start_year)


def _non_vacant_player_names(df: Optional[pd.DataFrame]) -> Set[str]:
    return _minor_elig._non_vacant_player_names(df)


def _players_with_playing_time(bat_df: pd.DataFrame, pit_df: pd.DataFrame, years: List[int]) -> Set[str]:
    return _minor_elig._players_with_playing_time(bat_df, pit_df, years)


def _select_mlb_roster_with_active_floor(
    stash_sorted: pd.DataFrame,
    *,
    excluded_players: Set[str],
    total_mlb_slots: int,
    active_floor_names: Set[str],
) -> pd.DataFrame:
    return _minor_elig._select_mlb_roster_with_active_floor(
        stash_sorted,
        excluded_players=excluded_players,
        total_mlb_slots=total_mlb_slots,
        active_floor_names=active_floor_names,
    )


def _estimate_bench_negative_penalty(start_ctx: dict, lg: object) -> float:
    return _minor_elig._estimate_bench_negative_penalty(start_ctx, lg)


def _bench_stash_round_penalty(
    round_number: int,
    *,
    bench_slots: int,
    min_penalty: float = BENCH_STASH_MIN_PENALTY,
    max_penalty: float = BENCH_STASH_MAX_PENALTY,
    gamma: float = BENCH_STASH_PENALTY_GAMMA,
) -> float:
    return _minor_elig._bench_stash_round_penalty(
        round_number,
        bench_slots=bench_slots,
        min_penalty=min_penalty,
        max_penalty=max_penalty,
        gamma=gamma,
    )


def _build_bench_stash_penalty_map(
    stash_sorted: pd.DataFrame,
    *,
    bench_stash_players: Set[str],
    n_teams: int,
    bench_slots: int,
) -> Dict[str, float]:
    return _minor_elig._build_bench_stash_penalty_map(
        stash_sorted,
        bench_stash_players=bench_stash_players,
        n_teams=n_teams,
        bench_slots=bench_slots,
    )


def _apply_negative_value_stash_rules(
    value: float,
    *,
    can_minor_stash: bool,
    can_bench_stash: bool,
    bench_negative_penalty: float,
) -> float:
    return _minor_elig._apply_negative_value_stash_rules(
        value,
        can_minor_stash=can_minor_stash,
        can_bench_stash=can_bench_stash,
        bench_negative_penalty=bench_negative_penalty,
    )
def _fillna_bool(series: pd.Series, default: bool = False) -> pd.Series:
    return _minor_elig._fillna_bool(series, default=default)

def _normalize_minor_eligibility(series: pd.Series) -> pd.Series:
    return _minor_elig._normalize_minor_eligibility(series)


def minor_eligibility_by_year_from_input(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
) -> Optional[pd.DataFrame]:
    return _minor_elig.minor_eligibility_by_year_from_input(bat, pit)


def minor_eligibility_from_input(
    bat: pd.DataFrame,
    pit: pd.DataFrame,
    start_year: int,
) -> Optional[pd.DataFrame]:
    return _minor_elig.minor_eligibility_from_input(bat, pit, start_year)


def _resolve_minor_eligibility_by_year(
    bat_df: pd.DataFrame,
    pit_df: pd.DataFrame,
    *,
    years: List[int],
    hitter_usage_max: int,
    pitcher_usage_max: int,
    hitter_age_max: int,
    pitcher_age_max: int,
) -> pd.DataFrame:
    return _minor_elig._resolve_minor_eligibility_by_year(
        bat_df,
        pit_df,
        years=years,
        hitter_usage_max=hitter_usage_max,
        pitcher_usage_max=pitcher_usage_max,
        hitter_age_max=hitter_age_max,
        pitcher_age_max=pitcher_age_max,
    )

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
    """Compatibility wrapper delegating to extracted common orchestration."""
    try:  # pragma: no branch
        from backend.valuation import common_orchestration as _orchestration
    except ImportError:  # pragma: no cover - direct script execution fallback
        from valuation import common_orchestration as _orchestration
    return _orchestration.calculate_common_dynasty_values(
        excel_path,
        lg,
        start_year=start_year,
        years=years,
        verbose=verbose,
        return_details=return_details,
        seed=seed,
        recent_projections=recent_projections,
    )
def league_hitter_components(df: pd.DataFrame) -> pd.DataFrame: return _league_math.league_hitter_components(df)
def league_ensure_pitch_cols(df: pd.DataFrame) -> pd.DataFrame: return _league_math.league_ensure_pitch_cols(df)
def league_zscore(s: pd.Series) -> pd.Series: return _league_math.league_zscore(s)
def league_initial_hitter_weight(df: pd.DataFrame) -> pd.Series: return _league_math.league_initial_hitter_weight(df)
def league_initial_pitcher_weight(df: pd.DataFrame) -> pd.Series: return _league_math.league_initial_pitcher_weight(df)
def league_team_avg_ops(hit_tot: pd.Series) -> Tuple[float, float]: return _league_math.league_team_avg_ops(hit_tot)
def league_replacement_pitcher_rates(all_pit_df: pd.DataFrame, assigned_pit_df: pd.DataFrame, n_rep: int = 100) -> Dict[str, float]: return _league_math.league_replacement_pitcher_rates(all_pit_df, assigned_pit_df, n_rep=n_rep)
def league_apply_ip_cap(t: Dict[str, float], ip_cap: float, rep_rates: Optional[Dict[str, float]]) -> Dict[str, float]: return _league_math.league_apply_ip_cap(t, ip_cap=ip_cap, rep_rates=rep_rates)
def league_simulate_sgp_hit(assigned_hit_df: pd.DataFrame, lg: LeagueSettings, rng: np.random.Generator) -> Dict[str, float]: return _league_math.league_simulate_sgp_hit(assigned_hit_df, lg, rng)
def league_simulate_sgp_pit(assigned_pit_df: pd.DataFrame, lg: LeagueSettings, rep_rates: Dict[str, float], rng: np.random.Generator) -> Dict[str, float]: return _league_math.league_simulate_sgp_pit(assigned_pit_df, lg, rep_rates, rng)
def league_sum_slots(baseline_df: pd.DataFrame, slot_list: List[str]) -> pd.Series: return _league_math.league_sum_slots(baseline_df, slot_list)
def league_compute_year_context(year: int, bat_df: pd.DataFrame, pit_df: pd.DataFrame, lg: LeagueSettings, rng_seed: int) -> dict: return _league_math.league_compute_year_context(year, bat_df, pit_df, lg, rng_seed)
def league_compute_year_player_values(ctx: dict, lg: LeagueSettings) -> Tuple[pd.DataFrame, pd.DataFrame]: return _league_math.league_compute_year_player_values(ctx, lg)
def league_compute_replacement_baselines(ctx: dict, lg: LeagueSettings, rostered_players: Set[str], n_repl: Optional[int] = None) -> Tuple[pd.DataFrame, pd.DataFrame]: return _league_math.league_compute_replacement_baselines(ctx, lg, rostered_players=rostered_players, n_repl=n_repl)
def league_compute_year_player_values_vs_replacement(ctx: dict, lg: LeagueSettings, repl_hit: pd.DataFrame, repl_pit: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]: return _league_math.league_compute_year_player_values_vs_replacement(ctx, lg, repl_hit=repl_hit, repl_pit=repl_pit)
def league_combine_hitter_pitcher_year(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame: return _league_math.league_combine_hitter_pitcher_year(hit_vals, pit_vals, two_way)
def _xlsx_apply_header_style(ws) -> None: return _xlsx_fmt._xlsx_apply_header_style(ws)
def _xlsx_set_freeze_filters_and_view(ws, freeze_panes: str, add_autofilter: bool = False) -> None: return _xlsx_fmt._xlsx_set_freeze_filters_and_view(ws, freeze_panes=freeze_panes, add_autofilter=add_autofilter)
def _xlsx_add_table(ws, table_name: str, style_name: str = "TableStyleMedium9") -> None: return _xlsx_fmt._xlsx_add_table(ws, table_name=table_name, style_name=style_name)
def _xlsx_set_column_widths(ws, df: pd.DataFrame, overrides: Optional[Dict[str, float]] = None, sample_rows: int = 1000, min_width: float = 8.0, max_width: float = 45.0) -> None: return _xlsx_fmt._xlsx_set_column_widths(ws, df, overrides=overrides, sample_rows=sample_rows, min_width=min_width, max_width=max_width)
def _xlsx_apply_number_formats(ws, df: pd.DataFrame, formats_by_col: Dict[str, str]) -> None: return _xlsx_fmt._xlsx_apply_number_formats(ws, df, formats_by_col)
def _xlsx_add_value_color_scale(ws, df: pd.DataFrame, col_name: str) -> None: return _xlsx_fmt._xlsx_add_value_color_scale(ws, df, col_name)
def _xlsx_format_player_values(ws, df: pd.DataFrame, table_name: str = "PlayerValuesTbl") -> None: return _xlsx_fmt._xlsx_format_player_values(ws, df, table_name=table_name)
def _xlsx_format_detail_sheet(ws, df: pd.DataFrame, *, table_name: str, is_pitch: bool) -> None: return _xlsx_fmt._xlsx_format_detail_sheet(ws, df, table_name=table_name, is_pitch=is_pitch)

def league_infer_minor_eligible_start(bat_df: pd.DataFrame, pit_df: pd.DataFrame, lg: LeagueSettings, start_year: int) -> pd.DataFrame:
    inferred = _infer_minor_eligibility_by_year(
        bat_df,
        pit_df,
        years=[start_year],
        hitter_usage_max=lg.minor_hitters_career_ab_max,
        pitcher_usage_max=lg.minor_pitchers_career_ip_max,
        hitter_age_max=lg.infer_minor_age_max_hit,
        pitcher_age_max=lg.infer_minor_age_max_pit,
    )
    out = inferred[inferred["Year"] == int(start_year)][["Player", "minor_eligible"]].copy()
    if out.empty:
        return pd.DataFrame(columns=["Player", "minor_eligible"])
    return out.groupby("Player", as_index=False)["minor_eligible"].max()
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
    """Compatibility wrapper delegating to extracted league orchestration."""
    try:  # pragma: no branch
        from backend.valuation import league_orchestration as _orchestration
    except ImportError:  # pragma: no cover - direct script execution fallback
        from valuation import league_orchestration as _orchestration
    return _orchestration.calculate_league_dynasty_values(
        excel_path,
        lg,
        start_year=start_year,
        years=years,
        verbose=verbose,
        return_details=return_details,
        seed=seed,
        recent_projections=recent_projections,
    )
def main() -> None:
    try:  # pragma: no branch
        from backend.valuation import cli as _cli
    except ImportError:  # pragma: no cover - direct script execution fallback
        from valuation import cli as _cli
    _cli.main()
if __name__ == "__main__":
    main()
