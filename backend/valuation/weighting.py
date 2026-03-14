"""Initial weighting helpers for baseline starter-pool construction."""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from backend.valuation.models import HIT_CATS, PIT_CATS
except ImportError:
    from valuation.models import HIT_CATS, PIT_CATS  # type: ignore[no-redef]


def _zscore(s: pd.Series) -> pd.Series:
    x = s.astype(float)
    mu = float(x.mean())
    sd = float(x.std(ddof=0))
    if sd == 0.0 or np.isnan(sd):
        return x * 0.0
    return (x - mu) / sd


def _initial_hitter_weight(df: pd.DataFrame, categories: Optional[List[str]] = None) -> pd.Series:
    """Rough first-pass weight for baseline starter-pool construction."""
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
            components.append(_zscore(series))

    if "AVG" in selected:
        mean_avg = float(np.nanmean(avg)) if len(avg) else 0.0
        components.append(_zscore(pd.Series((avg - mean_avg) * ab, index=df.index)))
    if "OBP" in selected:
        mean_obp = float(np.nanmean(obp)) if len(obp) else 0.0
        components.append(_zscore(pd.Series((obp - mean_obp) * obp_den, index=df.index)))
    if "SLG" in selected:
        mean_slg = float(np.nanmean(slg)) if len(slg) else 0.0
        components.append(_zscore(pd.Series((slg - mean_slg) * ab, index=df.index)))
    if "OPS" in selected:
        mean_ops = float(np.nanmean(ops)) if len(ops) else 0.0
        components.append(_zscore(pd.Series((ops - mean_ops) * ab, index=df.index)))

    if not components:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)

    w = components[0].copy()
    for component in components[1:]:
        w = w + component
    return w


def _initial_pitcher_weight(df: pd.DataFrame, categories: Optional[List[str]] = None) -> pd.Series:
    """Rough first-pass weight for baseline starter-pool construction."""
    df = df.copy()
    selected = {str(cat).strip().upper() for cat in (categories or list(PIT_CATS))}
    components: List[pd.Series] = []

    for cat in ("W", "K", "SV", "QS", "QA3", "SVH"):
        if cat in selected:
            components.append(_zscore(df[cat]))

    if "ERA" in selected or "WHIP" in selected:
        ip_sum = float(df["IP"].sum())
        mean_era = float(9.0 * df["ER"].sum() / ip_sum) if ip_sum > 0 else float(df["ERA"].mean())
        mean_whip = float((df["H"].sum() + df["BB"].sum()) / ip_sum) if ip_sum > 0 else float(df["WHIP"].mean())
        if "ERA" in selected:
            df["ERA_surplus_ER"] = (mean_era - df["ERA"]) * df["IP"] / 9.0
            components.append(_zscore(df["ERA_surplus_ER"]))
        if "WHIP" in selected:
            df["WHIP_surplus"] = (mean_whip - df["WHIP"]) * df["IP"]
            components.append(_zscore(df["WHIP_surplus"]))

    if not components:
        return pd.Series(np.zeros(len(df), dtype=float), index=df.index)

    w = components[0].copy()
    for component in components[1:]:
        w = w + component
    return w
