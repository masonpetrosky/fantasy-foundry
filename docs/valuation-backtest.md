# Valuation Backtest Harness

Use `scripts/backtest_valuation.py` to compare predicted dynasty values against realized outcomes.

## Inputs

- `--predictions`: CSV/TSV/JSON with at least:
  - key column (default `PlayerEntityKey`)
  - prediction value column (default `DynastyValue`)
- `--realized`: CSV/TSV/JSON with at least:
  - key column (default `PlayerEntityKey`)
  - realized value column (default `RealizedValue`)

Optional:

- `--year`: filter both datasets to a single season (requires year columns)
- `--top-n`: comma-separated cutoffs for overlap precision (default `25,50,100`)
- `--out-json`: write metrics JSON to disk

## Example

```bash
python scripts/backtest_valuation.py \
  --predictions tmp/predictions_2026.csv \
  --realized tmp/realized_2026.csv \
  --pred-key-col PlayerEntityKey \
  --real-key-col PlayerEntityKey \
  --pred-value-col DynastyValue \
  --realized-value-col RealizedValue \
  --year 2026 \
  --out-json tmp/backtest_2026.json
```

## Output Metrics

- `spearman`: rank correlation between predicted and realized values
- `kendall`: Kendall rank correlation
- `top_n_precision`: overlap ratio between predicted top-N and realized top-N
- `overlap_rows`: joined rows used in metric computation
