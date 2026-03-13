"""Team-level stat calculations and category aggregation helpers."""

from __future__ import annotations

from typing import Dict, Optional

import pandas as pd

try:
    from backend.valuation.models import (
        PIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )
except ImportError:
    from valuation.models import (  # type: ignore[no-redef]
        PIT_COMPONENT_COLS,
        CommonDynastyRotoSettings,
    )


def _team_avg(h: float, ab: float) -> float:
    return float(h / ab) if ab > 0 else 0.0


def _team_obp(h: float, bb: float, hbp: float, ab: float, sf: float) -> float:
    den = ab + bb + hbp + sf
    return float((h + bb + hbp) / den) if den > 0 else 0.0


def _team_era(er: float, ip: float) -> float:
    return float(9.0 * er / ip) if ip > 0 else float("nan")


def _team_whip(h: float, bb: float, ip: float) -> float:
    return float((h + bb) / ip) if ip > 0 else float("nan")


def common_hit_category_totals(totals: Dict[str, float]) -> Dict[str, float]:
    h = float(totals.get("H", 0.0))
    ab = float(totals.get("AB", 0.0))
    b2 = float(totals.get("2B", 0.0))
    b3 = float(totals.get("3B", 0.0))
    hr = float(totals.get("HR", 0.0))
    bb = float(totals.get("BB", 0.0))
    hbp = float(totals.get("HBP", 0.0))
    sf = float(totals.get("SF", 0.0))

    tb = h + b2 + 2.0 * b3 + 3.0 * hr
    obp = _team_obp(h, bb, hbp, ab, sf)
    slg = float(tb / ab) if ab > 0 else 0.0

    return {
        "R": float(totals.get("R", 0.0)),
        "RBI": float(totals.get("RBI", 0.0)),
        "HR": hr,
        "SB": float(totals.get("SB", 0.0)),
        "AVG": _team_avg(h, ab),
        "OBP": obp,
        "SLG": slg,
        "OPS": obp + slg,
        "H": h,
        "BB": bb,
        "2B": b2,
        "TB": tb,
    }


def common_pitch_category_totals(totals: Dict[str, float]) -> Dict[str, float]:
    return {
        "W": float(totals.get("W", 0.0)),
        "K": float(totals.get("K", 0.0)),
        "SV": float(totals.get("SV", 0.0)),
        "ERA": float(totals.get("ERA", 0.0)),
        "WHIP": float(totals.get("WHIP", 0.0)),
        "QS": float(totals.get("QS", 0.0)),
        "QA3": float(totals.get("QA3", 0.0)),
        "SVH": float(totals.get("SVH", 0.0)),
    }


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
        return {k: 0.0 for k in ["W", "QS", "QA3", "K", "SV", "SVH", "ER", "H", "BB"]}

    return {
        "W": float(rep["W"].sum() / ip),
        "QS": float(rep["QS"].sum() / ip),
        "QA3": float(rep["QA3"].sum() / ip),
        "K": float(rep["K"].sum() / ip),
        "SV": float(rep["SV"].sum() / ip),
        "SVH": float(rep["SVH"].sum() / ip),
        "ER": float(rep["ER"].sum() / ip),
        "H": float(rep["H"].sum() / ip),
        "BB": float(rep["BB"].sum() / ip),
    }


def common_apply_pitching_bounds(
    totals: Dict[str, float],
    lg: CommonDynastyRotoSettings,
    rep_rates: Optional[Dict[str, float]],
    *,
    fill_to_ip_max: bool = True,
    enforce_ip_min: bool = True,
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
        if fill_to_ip_max and ip < ip_cap and rep_rates is not None:
            add = ip_cap - ip
            out["IP"] = ip_cap
            for col in ["W", "QS", "QA3", "K", "SV", "SVH", "ER", "H", "BB"]:
                out[col] = float(out[col]) + add * float(rep_rates.get(col, 0.0))
            ip = ip_cap

    out["ERA"] = _team_era(out["ER"], ip)
    out["WHIP"] = _team_whip(out["H"], out["BB"], ip)

    # Optional IP minimum qualification rule (default OFF)
    if enforce_ip_min and lg.ip_min and lg.ip_min > 0 and ip < lg.ip_min:
        out["ERA"] = 99.0
        out["WHIP"] = 5.0

    return out
