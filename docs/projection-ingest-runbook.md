# Manual Projection Ingest Runbook (GPT Single-Player)

## Purpose
Document the manual workflow for generating one-player MLB EV projections (2026-2045) with GPT and ingesting them into this repo's projection workbook.

This process is intentionally manual for player-level updates:
- Generate one-player projections in GPT.
- Append the rows into the master workbook.
- Manually set league/roster metadata fields.
- Regenerate JSON artifacts used by the app.

## Files and Targets
- Master workbook: `data/Dynasty Baseball Projections.xlsx`
- Target sheets in master workbook: `Bat`, `Pitch`
- Prompt template: [`docs/templates/gpt-single-player-projection-prompt.md`](templates/gpt-single-player-projection-prompt.md)

## Prerequisites
- GPT model/mode: `GPT 5.2 Pro` with `Extended Thinking`
- Spreadsheet editor that can copy/paste rows between `.xlsx` files
- Local Python environment for `python preprocess.py`

## Workflow

1. Prepare and run the prompt in GPT
- Open [`docs/templates/gpt-single-player-projection-prompt.md`](templates/gpt-single-player-projection-prompt.md).
- Replace only the 3 placeholders near the top:
  - `[Player]`
  - `[Position]`
  - `[Team]`
- Submit the prompt to GPT.
- Download the returned `.xlsx` file.

2. Identify which downloaded sheet(s) to ingest
- If GPT output is hitter-only or pitcher-only:
  - Expect one sheet named `Projections`.
- If GPT output is two-way:
  - Expect two sheets: `Hitting Projections` and `Pitching Projections`.

3. Append rows into the master workbook
- Open `data/Dynasty Baseball Projections.xlsx`.
- Append, do not overwrite, the new 20 yearly rows (`2026` through `2045`) at the bottom of target sheet(s).
- Use this mapping:
  - Hitter output -> append to `Bat`
  - Pitcher output -> append to `Pitch`
  - Two-way output -> append `Hitting Projections` to `Bat` and `Pitching Projections` to `Pitch`

4. Preserve projection columns exactly
- Copy projection columns as produced (all numeric values, not formulas).
- Keep `Player`, `Team`, and `Pos` text exactly as in GPT output.
- Keep year range as exactly `2026`-`2045`.

Expected projection columns copied into `Bat`:
- `Player, Team, Age, Year, G, AB, R, RBI, H, 2B, 3B, HR, BB, IBB, HBP, SO, SB, CS, SF, SH, GDP, AVG, OPS, Pos`

Expected projection columns copied into `Pitch`:
- `Player, Team, Age, Year, G, GS, IP, BF, W, L, SV, HLD, BS, QS, QA3, K, BB, IBB, HBP, H, HR, R, ER, SVH, ERA, WHIP, Pos`

5. Manually fill workbook-specific metadata columns
- For newly appended `Bat` rows, manually set:
  - `Minor` (`Yes` or `No`)
  - `Fantrax Roster`
  - `Date` (today's date, ET)
- For newly appended `Pitch` rows, manually set:
  - `Minor` (`Yes` or `No`)
  - `Roster`
  - `Date` (today's date, ET)

Note:
- These metadata columns are part of the master workbook schema and are maintained manually after projection row append.

6. Rebuild JSON artifacts used by the app
```bash
python preprocess.py
```

Optional faster run (skips dynasty lookup cache generation):
```bash
python preprocess.py --skip-dynasty-cache
```

## Quality Checklist
- Exactly 20 rows appended per side (`2026`-`2045`).
- Correct target sheet(s) used (`Bat`, `Pitch`).
- `Player`, `Team`, and `Pos` strings preserved as-is.
- Hitter derived columns (`AVG`, `OPS`) are values, not formulas.
- Pitcher derived columns (`SVH`, `ERA`, `WHIP`) are values, not formulas.
- Pitcher `IP` values use `.00`, `.33`, or `.67` endings.
- Manual metadata fields (`Minor`, roster, `Date`) filled for appended rows.
- `python preprocess.py` completes successfully.

## Troubleshooting
- Downloaded workbook has unexpected sheet names:
  - Confirm role type from the prompt input (`Position`) and re-run GPT if needed.
- Columns do not align when pasting:
  - Align by header name, not visual position, and ensure all required projection columns are present.
- `preprocess.py` fails with missing required columns:
  - Verify `Bat` and `Pitch` sheet headers were not altered.
  - Verify projection rows include full required stat columns before metadata columns.

## Notes on Multi-Projection History
- App valuation pipelines support multiple projections per player-year and use projection-date-aware averaging logic.
- Appending a new dated projection set for the same player-year is expected behavior, not a conflict.
