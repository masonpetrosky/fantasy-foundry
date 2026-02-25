# GPT Single-Player Projection Prompt Template

Use this template exactly for one-player projection generation.  
Model setting: `GPT 5.2 Pro` with `Extended Thinking`.

Replace only these 3 values before submitting:
- Player Name: `[Player]`
- Position: `[Position]`
- Team: `[Team]`

```text
You are an expert MLB analytics + dynasty fantasy baseball projection engine. Your job is to produce expected value (EV) season-stat projections (NOT "assuming full health") for ONE specified player for each season year 2026-2045, using the exact OUTPUT stat columns below, and deliver the results as an Excel file (.xlsx).

IMPORTANT: Project MLB regular season only (exclude postseason + spring training).
IMPORTANT: EV only (already incorporates injury/availability and all other risks). Do NOT output "if healthy" as the main line.

----------------------------------------------------------------------
INPUT (single player)
- Player Name: [Player]
- Position: [Position]
- Team: [Team]

Role inference rules:
- If Position is P/SP/RP -> treat player as a Pitcher.
- If Position is C/1B/2B/3B/SS/OF/DH -> treat player as a Hitter.
- If Position indicates TWO-WAY (or P/DH) -> treat player as Two-Way (project BOTH hitting + pitching).
- If Position conflicts with publicly verifiable information, choose the most likely true MLB role using whatever evidence you deem best, then proceed.

If the name is ambiguous, pick the most likely match using the provided position and team plus any reliable identifiers you can verify (e.g., age, handedness, org history). If you truly cannot identify the player, make a best-effort assumption and proceed.

----------------------------------------------------------------------
PLAYER AGE COLUMN REQUIREMENT
Include a player age column for each season.

Definition:
- Age = "season age" in whole years, defined as the player's age as of June 30 of that MLB season year.
  - Example: For Year=2029, Age is the player's age on 2029-06-30.
  - Use publicly verifiable birthdate if available; if not available, make a best-effort estimate and proceed.

Age is deterministic per year (not an EV stat).

----------------------------------------------------------------------
PLAYER TEAM COLUMN REQUIREMENT
Include a Team column for each season.
- Team must be copied directly from the INPUT Team value exactly as given (text), and repeated on every row.
- Do NOT infer team changes/trades; do NOT abbreviate; do NOT "correct" the input team string.

Team is deterministic per year (not an EV stat).

----------------------------------------------------------------------
PLAYER POSITION (Pos) COLUMN REQUIREMENT
Include a Pos column for each season (and on every sheet that is output).
- Pos must be copied directly from the INPUT Position value exactly as given (text), and repeated on every row.
- Do NOT infer position changes; do NOT abbreviate; do NOT "correct" the input Position string.
- Note: Even though Pos is required, it must be placed at the END of each row (see column-order requirements below).

Pos is deterministic per year (not an EV stat).

----------------------------------------------------------------------
OUTPUT STAT COLUMNS TO PROJECT (use exactly these)
Project MLB regular season only (exclude postseason + spring training).
All counting stats may be non-integers because these are EV projections.

If the player is a Hitter (including DH), output ONLY these columns (in addition to Player/Team/Age/Year):
Counting stats:
- G
- AB
- R
- RBI
- H
- 2B
- 3B
- HR
- BB
- IBB
- HBP
- SO
- SB
- CS
- SF
- SH
- GDP

Derived output columns (MUST be written as values, NOT Excel formulas):
- AVG
- OPS
- Pos

If the player is a Pitcher (SP and/or RP), output ONLY these columns (in addition to Player/Team/Age/Year):
Counting stats:
- G
- GS
- IP
- BF
- W
- L
- SV
- HLD
- BS
- QS
- QA3
- K
- BB
- IBB
- HBP
- H
- HR
- R
- ER

Derived output columns (MUST be written as values, NOT Excel formulas):
- SVH
- ERA
- WHIP
- Pos

If the player is Two-Way:
- Output BOTH sets (one hitting sheet + one pitching sheet), each with its corresponding derived output columns appended at the end.

Category definitions (for clarity):
- QS (Quality Start) = 1 credited for a start where IP >= 6.0 AND ER <= 3
- QA3 (Quality Appearance 3) = 1 credited for a pitcher appearance where IP >= 5.0 AND game ERA <= 4.50 (i.e., ER * 9 / IP <= 4.50). Season QA3 is the expected total count of qualifying appearances.

----------------------------------------------------------------------
DERIVED COLUMN DEFINITIONS (write VALUES, not Excel formulas)

HITTER DERIVED COLUMNS
- AVG (Batting Average) = H / AB
  - If AB = 0, set AVG = 0.000
- OPS = OBP + SLG
  - OBP = (H + BB + HBP) / (AB + BB + HBP + SF)
    - Use total BB (BB already includes IBB).
    - If (AB + BB + HBP + SF) = 0, set OBP = 0.000
  - SLG = TB / AB
    - 1B = H - 2B - 3B - HR
    - TB = 1B + 2*2B + 3*3B + 4*HR
      - Equivalent: TB = H + 2B + 2*3B + 3*HR
    - If AB = 0, set SLG = 0.000
  - If AB = 0 and the OBP denominator is also 0, OPS must still be a numeric value; set OPS = 0.000

PITCHER DERIVED COLUMNS
- SVH = SV + HLD
- ERA = (ER * 9) / IP
  - If IP = 0, set ERA = 0.00
- WHIP = (BB + H) / IP
  - Standard WHIP excludes HBP.
  - If IP = 0, set WHIP = 0.00

IMPORTANT: These derived columns MUST be output as plain numeric/text values in the Excel cells (like the other columns), not as Excel formulas.

----------------------------------------------------------------------
INNINGS FORMATTING RULE (Pitchers)
In the Excel output, IP must be shown using decimal thirds:
- .00 for whole innings
- .33 for 1/3 inning
- .67 for 2/3 inning
Examples: 132.00, 132.33, 132.67
You may calculate internally however you want, but the final Excel cells must use .00/.33/.67 formatting (only these endings).

IMPORTANT: When computing ERA and WHIP, use true innings pitched internally (outs/3), not the rounded "decimal thirds" display representation.

----------------------------------------------------------------------
TIME + SCHEDULE HANDLING
- Establish "today" as the runtime date you are using (Eastern Time), but DO NOT output it anywhere in the workbook.
- 2026 requirement = REST-OF-SEASON (ROS) totals through end of 2026 MLB regular season, relative to "today".
  - If today is before the 2026 regular season starts: treat 2026 ROS as the full 2026 regular season.
  - If today is after the 2026 regular season ends: 2026 ROS = 0 playing time (all output counting stats should be 0.0).
  - If today is during the 2026 regular season: include remaining regular-season games appropriately using whatever schedule/transaction information you deem most reliable.
- 2027-2045 requirement = full regular-season totals (assume 162 games unless you have strong reason to adjust).

----------------------------------------------------------------------
EXPECTED VALUE REQUIREMENT (NO "assuming healthy")
Your yearly totals MUST be true EV outcomes that already include:
- Injury/availability risk (expected missed time / reduced workload)
- Minor-league/option risk (if relevant)
- Suspension probability if relevant
- Role volatility (platoon risk for hitters; SP/RP role risk for pitchers; leverage/closing share for relievers)
- Late-career "out of MLB/retirement/overseas" risk (increasing with age and distance into the future)

Do NOT present "if healthy" lines as the main answer. EV only.

----------------------------------------------------------------------
RESEARCH / DATA (use judgment)
Use whatever research, sources, calculations, and methods you judge will produce the most accurate and useful projections.
If external research is not available, proceed with best-effort estimates.

----------------------------------------------------------------------
DELIVERABLE: EXCEL WORKBOOK (.xlsx)
Create and return an Excel workbook that contains the projections for 2026-2045.

Player string fidelity requirement:
- In the Excel output, the Player column must copy the INPUT Player Name EXACTLY as given, character-for-character.
- Do NOT add/remove accents/diacritics, punctuation, suffixes, spacing, or capitalization.
- Do NOT "fix" typos or normalize the name in any way.

Tidy-data requirement (no timestamp column):
- Each projection row (each year) must repeat the Player, Team, Age, and Pos values.
- In the Excel output, the column order must be Player, Team, Age (then Year, then stats as specified below).

Sheets:
1) If the player is a Hitter:
   - One sheet named "Projections" with one row per year 2026-2045 and these columns IN THIS EXACT ORDER:
     - Player
     - Team
     - Age
     - Year
     - G
     - AB
     - R
     - RBI
     - H
     - 2B
     - 3B
     - HR
     - BB
     - IBB
     - HBP
     - SO
     - SB
     - CS
     - SF
     - SH
     - GDP
     - AVG
     - OPS
     - Pos

2) If the player is a Pitcher:
   - One sheet named "Projections" with one row per year 2026-2045 and these columns IN THIS EXACT ORDER:
     - Player
     - Team
     - Age
     - Year
     - G
     - GS
     - IP
     - BF
     - W
     - L
     - SV
     - HLD
     - BS
     - QS
     - QA3
     - K
     - BB
     - IBB
     - HBP
     - H
     - HR
     - R
     - ER
     - SVH
     - ERA
     - WHIP
     - Pos

3) If the player is Two-Way:
   - Two sheets:
     - "Hitting Projections" with the hitter columns above (including AVG, OPS, Pos at the end)
     - "Pitching Projections" with the pitcher columns above (including SVH, ERA, WHIP, Pos at the end)

Precision / formatting (in the Excel cells):
- Age: 0 decimals (whole years)
- Year: integer (no decimals)
- 1 decimal place: all output counting stats (including SVH)
- IP: show with 2 decimals and only .00/.33/.67 endings
- AVG: 3 decimals
- OPS: 3 decimals
- ERA: 2 decimals
- WHIP: 2 decimals
- Pos: text (copied from INPUT Position exactly)

Output:
- Return the .xlsx file as the primary output.
```

