"""
Preprocess the Excel projections file into JSON for fast API serving.

Run this whenever you update 'Dynasty Baseball Projections.xlsx':
    python preprocess.py
"""

import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
EXCEL_PATH = DATA_DIR / "Dynasty Baseball Projections.xlsx"


def main():
    print(f"Reading {EXCEL_PATH} ...")
    bat = pd.read_excel(EXCEL_PATH, sheet_name="Bat")
    pit = pd.read_excel(EXCEL_PATH, sheet_name="Pitch")

    # Convert datetime columns to strings for JSON serialization
    for df in [bat, pit]:
        for col in df.columns:
            if df[col].dtype == "datetime64[ns]" or "date" in col.lower():
                df[col] = df[col].astype(str)

    # Round floats for cleaner JSON
    for col in bat.select_dtypes(include="float").columns:
        bat[col] = bat[col].round(3 if col in ("AVG", "OPS") else 1)
    for col in pit.select_dtypes(include="float").columns:
        pit[col] = pit[col].round(3 if col in ("ERA", "WHIP") else 1)

    # Write data JSON files
    bat.to_json(DATA_DIR / "bat.json", orient="records")
    pit.to_json(DATA_DIR / "pitch.json", orient="records")

    # Write metadata for frontend filters
    meta = {
        "teams": sorted(bat["Team"].dropna().unique().tolist()),
        "years": sorted(int(y) for y in bat["Year"].unique()),
        "bat_positions": sorted(bat["Pos"].dropna().unique().tolist()),
        "pit_positions": sorted(pit["Pos"].dropna().unique().tolist()),
        "total_hitters": int(bat["Player"].nunique()),
        "total_pitchers": int(pit["Player"].nunique()),
    }
    with open(DATA_DIR / "meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    print(f"  Hitters:  {len(bat):,} rows, {meta['total_hitters']} unique players")
    print(f"  Pitchers: {len(pit):,} rows, {meta['total_pitchers']} unique players")
    print(f"  Years:    {meta['years'][0]}–{meta['years'][-1]}")
    print(f"  Output:   bat.json, pitch.json, meta.json")
    print("Done!")


if __name__ == "__main__":
    main()
