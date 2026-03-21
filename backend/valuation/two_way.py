"""Two-way player value combination logic."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _prepare_side_frame(df: pd.DataFrame, *, side: str) -> tuple[pd.DataFrame, list[str]]:
    sgp_cols = [col for col in df.columns if col.startswith("SGP_")]
    keep_cols = ["Player", "Year", "YearValue", "BestSlot", "Team", "Age", "Pos", "ReplacementDiagnostics", *sgp_cols]
    existing_cols = [col for col in keep_cols if col in df.columns]
    frame = df[existing_cols].copy() if existing_cols else pd.DataFrame()

    if "Player" not in frame.columns:
        frame["Player"] = pd.Series(dtype=object)
    if "Year" not in frame.columns:
        frame["Year"] = pd.Series(dtype=object)

    rename_map = {
        "YearValue": f"YearValue_{side}",
        "BestSlot": f"BestSlot_{side}",
        "Team": f"Team_{side}",
        "Age": f"Age_{side}",
        "Pos": f"Pos_{side}",
        "ReplacementDiagnostics": f"ReplacementDiagnostics_{side}",
    }
    sgp_categories: list[str] = []
    for col in sgp_cols:
        category = col[4:]
        sgp_categories.append(category)
        rename_map[col] = f"SGP_{side}_{category}"

    return frame.rename(columns=rename_map), sgp_categories


def _column_or_default(
    frame: pd.DataFrame,
    column: str,
    *,
    dtype: str,
    fill_value: float | None = None,
) -> pd.Series:
    if column in frame.columns:
        return frame[column]
    if fill_value is None:
        return pd.Series(index=frame.index, dtype=dtype)
    return pd.Series(fill_value, index=frame.index, dtype=dtype)


def combine_two_way(hit_vals: pd.DataFrame, pit_vals: pd.DataFrame, two_way: str) -> pd.DataFrame:
    hit_frame, hit_sgp_cats = _prepare_side_frame(hit_vals, side="hit")
    pit_frame, pit_sgp_cats = _prepare_side_frame(pit_vals, side="pit")
    merged = pd.merge(hit_frame, pit_frame, on=["Player", "Year"], how="outer")

    all_sgp_cats = sorted(set(hit_sgp_cats) | set(pit_sgp_cats))

    hit_values = pd.to_numeric(
        _column_or_default(merged, "YearValue_hit", dtype="float64"),
        errors="coerce",
    )
    pit_values = pd.to_numeric(
        _column_or_default(merged, "YearValue_pit", dtype="float64"),
        errors="coerce",
    )
    hit_missing = hit_values.isna()
    pit_missing = pit_values.isna()
    both_missing = hit_missing & pit_missing

    hit_slots = _column_or_default(merged, "BestSlot_hit", dtype="object")
    pit_slots = _column_or_default(merged, "BestSlot_pit", dtype="object")
    hit_slot_values = hit_slots.to_numpy(dtype=object)
    pit_slot_values = pit_slots.to_numpy(dtype=object)
    hit_diags = _column_or_default(merged, "ReplacementDiagnostics_hit", dtype="object")
    pit_diags = _column_or_default(merged, "ReplacementDiagnostics_pit", dtype="object")

    if two_way == "sum":
        year_values = hit_values.fillna(0.0) + pit_values.fillna(0.0)
        year_values = year_values.where(~both_missing, np.nan)
        combined_slots = hit_slots.astype("string").fillna("") + "+" + pit_slots.astype("string").fillna("")
        best_slots = pd.Series(
            np.where(
                hit_missing.to_numpy(),
                pit_slot_values,
                np.where(
                    pit_missing.to_numpy(),
                    hit_slot_values,
                    combined_slots.to_numpy(dtype=object),
                ),
            ),
            index=merged.index,
            dtype=object,
        )
    else:
        choose_hit = pit_missing | ((~hit_missing) & (~pit_missing) & (hit_values >= pit_values))
        year_values = pd.Series(
            np.where(
                hit_missing.to_numpy(),
                pit_values.to_numpy(),
                np.where(
                    pit_missing.to_numpy(),
                    hit_values.to_numpy(),
                    np.where(choose_hit.to_numpy(), hit_values.to_numpy(), pit_values.to_numpy()),
                ),
            ),
            index=merged.index,
            dtype=float,
        ).where(~both_missing, np.nan)
        best_slots = pd.Series(
            np.where(
                hit_missing.to_numpy(),
                pit_slot_values,
                np.where(
                    pit_missing.to_numpy(),
                    hit_slot_values,
                    np.where(choose_hit.to_numpy(), hit_slot_values, pit_slot_values),
                ),
            ),
            index=merged.index,
            dtype=object,
        )

    merged["YearValue"] = year_values
    merged["BestSlot"] = best_slots
    merged["Team"] = _column_or_default(merged, "Team_hit", dtype="object").combine_first(
        _column_or_default(merged, "Team_pit", dtype="object")
    )
    merged["Pos"] = _column_or_default(merged, "Pos_hit", dtype="object").combine_first(
        _column_or_default(merged, "Pos_pit", dtype="object")
    )
    merged["Age"] = _column_or_default(merged, "Age_hit", dtype="float64").combine_first(
        _column_or_default(merged, "Age_pit", dtype="float64")
    )

    for category in all_sgp_cats:
        hit_sgp = pd.to_numeric(
            _column_or_default(merged, f"SGP_hit_{category}", dtype="float64", fill_value=0.0),
            errors="coerce",
        ).fillna(0.0)
        pit_sgp = pd.to_numeric(
            _column_or_default(merged, f"SGP_pit_{category}", dtype="float64", fill_value=0.0),
            errors="coerce",
        ).fillna(0.0)
        if two_way == "sum":
            merged[f"SGP_{category}"] = hit_sgp + pit_sgp
        else:
            merged[f"SGP_{category}"] = np.where(choose_hit.to_numpy(), hit_sgp.to_numpy(), pit_sgp.to_numpy())

    replacement_diags: list[dict | None] = []
    for idx in merged.index:
        hit_diag = hit_diags.iloc[idx] if isinstance(hit_diags.iloc[idx], dict) else None
        pit_diag = pit_diags.iloc[idx] if isinstance(pit_diags.iloc[idx], dict) else None
        if two_way == "sum":
            if hit_diag and pit_diag:
                category_sgp: dict[str, float] = {}
                for source in (hit_diag, pit_diag):
                    for category, value in dict(source.get("category_sgp") or {}).items():
                        try:
                            category_sgp[str(category)] = float(category_sgp.get(str(category), 0.0)) + float(value)
                        except (TypeError, ValueError):
                            continue
                replacement_diags.append(
                    {
                        "side": "two_way",
                        "two_way_mode": "sum",
                        "best_slot": best_slots.iloc[idx],
                        "category_sgp": category_sgp,
                        "components": {"hit": hit_diag, "pit": pit_diag},
                    }
                )
            else:
                replacement_diags.append(hit_diag or pit_diag)
        else:
            use_hit = bool(choose_hit.iloc[idx]) if idx in choose_hit.index else False
            selected = hit_diag if use_hit or pd.isna(pit_values.iloc[idx]) else pit_diag
            if isinstance(selected, dict):
                selected = dict(selected)
                selected["two_way_mode"] = "max"
                selected["selected_side"] = "hit" if use_hit or pd.isna(pit_values.iloc[idx]) else "pit"
            replacement_diags.append(selected)

    merged["ReplacementDiagnostics"] = replacement_diags

    base_cols = ["Player", "Year", "YearValue", "BestSlot", "Team", "Pos", "Age"]
    return merged[base_cols + ["ReplacementDiagnostics"] + [f"SGP_{category}" for category in all_sgp_cats]]
