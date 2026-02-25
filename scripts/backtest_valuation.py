#!/usr/bin/env python3
"""Backtest dynasty valuation predictions against realized outcomes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _load_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv"}:
        sep = "\t" if suffix == ".tsv" else ","
        return pd.read_csv(path, sep=sep)
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return pd.DataFrame(data)
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return pd.DataFrame(data["data"])
        raise ValueError(f"Unsupported JSON shape in {path}. Expected list or {{\"data\": [...]}}.")
    raise ValueError(f"Unsupported file type: {path}")


def _require_columns(df: pd.DataFrame, *, columns: list[str], label: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"{label} missing required columns: {', '.join(missing)}")


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _top_n_precision(df: pd.DataFrame, *, pred_col: str, real_col: str, n: int) -> float | None:
    if n <= 0:
        return None
    if df.empty:
        return None
    key_col = "__join_key__"
    pred_top = df.nlargest(n, pred_col)[key_col].tolist()
    real_top = df.nlargest(n, real_col)[key_col].tolist()
    if not pred_top or not real_top:
        return None
    pred_set = set(pred_top)
    real_set = set(real_top)
    return float(len(pred_set & real_set) / float(min(len(pred_set), len(real_set))))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest dynasty valuation against realized outcomes.")
    parser.add_argument("--predictions", required=True, help="Path to predicted valuations (.csv/.tsv/.json).")
    parser.add_argument("--realized", required=True, help="Path to realized outcomes (.csv/.tsv/.json).")
    parser.add_argument("--pred-key-col", default="PlayerEntityKey")
    parser.add_argument("--real-key-col", default="PlayerEntityKey")
    parser.add_argument("--pred-value-col", default="DynastyValue")
    parser.add_argument("--realized-value-col", default="RealizedValue")
    parser.add_argument("--pred-year-col", default="Year")
    parser.add_argument("--real-year-col", default="Year")
    parser.add_argument("--year", type=int, default=None, help="Optional single year filter.")
    parser.add_argument(
        "--top-n",
        default="25,50,100",
        help="Comma-separated cutoffs for top-N overlap precision (default: 25,50,100).",
    )
    parser.add_argument("--out-json", default="", help="Optional output path for JSON metrics.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pred_path = Path(args.predictions).expanduser().resolve()
    real_path = Path(args.realized).expanduser().resolve()

    pred_df = _load_table(pred_path)
    real_df = _load_table(real_path)

    required_pred_cols = [args.pred_key_col, args.pred_value_col]
    required_real_cols = [args.real_key_col, args.realized_value_col]
    if args.year is not None:
        required_pred_cols.append(args.pred_year_col)
        required_real_cols.append(args.real_year_col)

    _require_columns(pred_df, columns=required_pred_cols, label="predictions")
    _require_columns(real_df, columns=required_real_cols, label="realized")

    if args.year is not None:
        pred_df = pred_df[pd.to_numeric(pred_df[args.pred_year_col], errors="coerce") == float(args.year)].copy()
        real_df = real_df[pd.to_numeric(real_df[args.real_year_col], errors="coerce") == float(args.year)].copy()

    pred_df = pred_df.rename(
        columns={
            args.pred_key_col: "__join_key__",
            args.pred_value_col: "__pred_value__",
        }
    )
    real_df = real_df.rename(
        columns={
            args.real_key_col: "__join_key__",
            args.realized_value_col: "__real_value__",
        }
    )

    pred_df["__join_key__"] = pred_df["__join_key__"].astype("string").fillna("").str.strip()
    real_df["__join_key__"] = real_df["__join_key__"].astype("string").fillna("").str.strip()
    pred_df = pred_df[pred_df["__join_key__"] != ""].copy()
    real_df = real_df[real_df["__join_key__"] != ""].copy()

    merged = pred_df[["__join_key__", "__pred_value__"]].merge(
        real_df[["__join_key__", "__real_value__"]],
        on="__join_key__",
        how="inner",
    )
    merged["__pred_value__"] = _coerce_numeric(merged["__pred_value__"])
    merged["__real_value__"] = _coerce_numeric(merged["__real_value__"])
    merged = merged.dropna(subset=["__pred_value__", "__real_value__"]).copy()

    if merged.empty:
        raise ValueError("No overlapping rows after key join/year filter/value coercion.")

    spearman = float(merged["__pred_value__"].corr(merged["__real_value__"], method="spearman"))
    kendall = float(merged["__pred_value__"].corr(merged["__real_value__"], method="kendall"))

    top_n_tokens = [token.strip() for token in str(args.top_n or "").split(",") if token.strip()]
    top_n_values: list[int] = []
    for token in top_n_tokens:
        try:
            value = int(token)
        except ValueError:
            continue
        if value > 0:
            top_n_values.append(value)

    top_n_precision = {
        str(n): _top_n_precision(merged, pred_col="__pred_value__", real_col="__real_value__", n=n)
        for n in sorted(set(top_n_values))
    }

    metrics: dict[str, Any] = {
        "predictions_path": str(pred_path),
        "realized_path": str(real_path),
        "year": args.year,
        "overlap_rows": int(len(merged)),
        "spearman": spearman,
        "kendall": kendall,
        "top_n_precision": top_n_precision,
    }

    print(json.dumps(metrics, indent=2, sort_keys=True))

    out_json = str(args.out_json or "").strip()
    if out_json:
        out_path = Path(out_json).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
