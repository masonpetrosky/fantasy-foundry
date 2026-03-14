"""Two-way player value combination logic."""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd


def combine_two_way(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame:
    hit_sgp_cols = [c for c in hit_vals.columns if c.startswith("SGP_")]
    pit_sgp_cols = [c for c in pit_vals.columns if c.startswith("SGP_")]
    hit_merge_cols = ["Player", "Year", "YearValue", "BestSlot", "Team", "Age", "Pos"] + hit_sgp_cols
    pit_merge_cols = ["Player", "Year", "YearValue", "BestSlot", "Team", "Age", "Pos"] + pit_sgp_cols
    merged = pd.merge(
        hit_vals[[c for c in hit_merge_cols if c in hit_vals.columns]],
        pit_vals[[c for c in pit_merge_cols if c in pit_vals.columns]],
        on=["Player", "Year"],
        how="outer",
        suffixes=("_hit", "_pit"),
    )

    hit_sgp_cat_set = {c[4:] for c in hit_sgp_cols}
    pit_sgp_cat_set = {c[4:] for c in pit_sgp_cols}
    all_sgp_cats = sorted(hit_sgp_cat_set | pit_sgp_cat_set)

    def _get_sgp(r: pd.Series, cat: str, side: str) -> float:
        """Get SGP value for a category from the merged row, handling suffix logic."""
        # If the cat exists on both sides, pandas adds _hit/_pit suffixes
        suffixed = f"SGP_{cat}_{side}"
        if suffixed in r.index:
            v = r[suffixed]
            return float(v) if v is not None and not pd.isna(v) else 0.0
        # If the cat exists only on one side, pandas keeps it unsuffixed
        unsuffixed = f"SGP_{cat}"
        if unsuffixed in r.index:
            # Only return the value if this cat belongs to the requested side
            if (side == "hit" and cat in hit_sgp_cat_set) or (side == "pit" and cat in pit_sgp_cat_set):
                v = r[unsuffixed]
                return float(v) if v is not None and not pd.isna(v) else 0.0
        return 0.0

    out_vals: List[float] = []
    out_slots: List[object] = []
    out_sgps: Dict[str, List[float]] = {cat: [] for cat in all_sgp_cats}

    for _, r in merged.iterrows():
        hv = r.get("YearValue_hit")
        pv = r.get("YearValue_pit")

        if pd.isna(hv) and pd.isna(pv):
            out_vals.append(np.nan)
            out_slots.append(None)
            for cat in all_sgp_cats:
                out_sgps[cat].append(0.0)
            continue
        if pd.isna(hv):
            out_vals.append(float(pv))
            out_slots.append(r.get("BestSlot_pit"))
            for cat in all_sgp_cats:
                out_sgps[cat].append(_get_sgp(r, cat, "pit"))
            continue
        if pd.isna(pv):
            out_vals.append(float(hv))
            out_slots.append(r.get("BestSlot_hit"))
            for cat in all_sgp_cats:
                out_sgps[cat].append(_get_sgp(r, cat, "hit"))
            continue

        hv = float(hv)
        pv = float(pv)

        if two_way == "sum":
            out_vals.append(hv + pv)
            out_slots.append(f"{r.get('BestSlot_hit')}+{r.get('BestSlot_pit')}")
            for cat in all_sgp_cats:
                out_sgps[cat].append(_get_sgp(r, cat, "hit") + _get_sgp(r, cat, "pit"))
        else:  # "max"
            if hv >= pv:
                out_vals.append(hv)
                out_slots.append(r.get("BestSlot_hit"))
                for cat in all_sgp_cats:
                    out_sgps[cat].append(_get_sgp(r, cat, "hit"))
            else:
                out_vals.append(pv)
                out_slots.append(r.get("BestSlot_pit"))
                for cat in all_sgp_cats:
                    out_sgps[cat].append(_get_sgp(r, cat, "pit"))

    merged["YearValue"] = out_vals
    merged["BestSlot"] = out_slots
    merged["Team"] = merged["Team_hit"].combine_first(merged["Team_pit"])
    merged["Pos"] = merged["Pos_hit"].combine_first(merged["Pos_pit"])
    merged["Age"] = merged["Age_hit"].combine_first(merged["Age_pit"])
    for cat in all_sgp_cats:
        merged[f"SGP_{cat}"] = out_sgps[cat]

    base_cols = ["Player", "Year", "YearValue", "BestSlot", "Team", "Pos", "Age"]
    return merged[base_cols + [f"SGP_{cat}" for cat in all_sgp_cats]]
