# Fantasy Foundry Valuation Engine -- Algorithm Documentation

## 1. Overview

The Fantasy Foundry valuation engine computes **dynasty player values** for fantasy baseball leagues. It answers the question: *"How much is this player worth across a multi-year dynasty horizon?"*

The engine supports two scoring modes:

- **Roto (rotisserie)** -- the default mode, where teams compete across statistical categories (e.g., HR, SB, ERA, WHIP) and standings are determined by rank in each category.
- **Points** -- an alternative mode where each stat event earns or costs a fixed number of points.

At a high level, the pipeline works like this:

1. **Assign players to roster slots** based on position eligibility and projected production.
2. **Estimate SGP denominators** (roto mode) or compute raw points totals (points mode) to establish a common value currency.
3. **Compute replacement-level baselines** from the unrostered player pool.
4. **Value each player** as their marginal contribution above replacement.
5. **Combine hitting and pitching** for two-way players.
6. **Discount and aggregate** across a multi-year dynasty horizon using a keep-or-drop dynamic program.
7. **Center** final values so the last rostered player is worth approximately zero.

---

## 2. SGP (Standings Gained Points)

### What SGP Is

In rotisserie fantasy baseball, teams are ranked 1st through Nth in each statistical category. The team with the most home runs gets N points in HR, the second-most gets N-1, and so on. Your total score is the sum across all categories.

**Standings Gained Points (SGP)** measures how much of a stat it takes to move up one place in the standings. For example, if the typical gap between adjacent teams in HR is 15 home runs, then 1 SGP in HR = 15 HR. This converts all categories (counting stats like HR, rate stats like ERA) into a single "standings points" currency so they can be compared directly.

### Why Monte Carlo Simulation

Rather than using a simple historical average or a formula, the engine estimates SGP denominators through **Monte Carlo simulation**:

1. For each simulation trial, randomly assign the pool of rostered players to teams (respecting roster slot structure).
2. Compute each simulated team's category totals.
3. Sort the teams and measure the **mean adjacent rank gap** -- the average difference between consecutive teams in the standings.
4. Repeat for many trials (default: 200) and average the results.

This approach captures the realistic distribution of talent and positional scarcity in the specific player pool being valued, rather than relying on generic league-average assumptions.

### Winsorization (Robust Mode)

In "robust" SGP mode, the adjacent rank gaps are **Winsorized** before averaging. This means extreme outlier gaps (caused by, say, one team having a historically great hitter) are clipped to the 10th and 90th percentile values. This prevents a single outlier team from inflating or deflating the SGP denominator.

- `sgp_winsor_low_pct` (default 0.10) -- the lower quantile for clipping
- `sgp_winsor_high_pct` (default 0.90) -- the upper quantile for clipping

### Epsilon Floors

When the SGP denominator is very close to zero (which can happen in thin categories or small leagues), dividing by it produces unstable values. In robust mode, a minimum floor is enforced:

- **Counting stats** (HR, SB, W, K, SV, etc.): floor of `sgp_epsilon_counting` (default 0.15)
- **Rate stats** (ERA, WHIP, AVG, OBP, etc.): floor of `sgp_epsilon_ratio` (default 0.0015)

### Reversed Categories

For ERA and WHIP, lower is better. The simulation accounts for this by sorting in ascending order when computing adjacent rank gaps, and by flipping the sign of deltas when computing player values (so a pitcher who lowers team ERA gets positive credit).

---

## 3. Replacement Level

### Concept

Replacement level answers: *"If I dropped this player, how good would the best freely available alternative be?"* A player's value is measured as their production **above** this replacement baseline, not above zero or above average.

### How Replacement Baselines Are Computed

1. **Determine who is rostered.** The engine runs a first pass to estimate dynasty values and identifies the top N players (based on league roster size) as "rostered."
2. **Identify the free agent pool.** Everyone not rostered with positive playing time (AB > 0 for hitters, IP > 0 for pitchers).
3. **Per-slot replacement.** For each roster slot (C, 1B, SS, OF, SP, RP, etc.), find the top free agents eligible for that slot, take the top N (default: number of teams), and average their component stats. This produces a **per-slot replacement baseline** -- the stats you would expect from the best available free agent at each position.

### Frozen vs. Rolling Baselines

By default, replacement baselines are **frozen from the start year** and reused for all future projection years. This prevents late-horizon value inflation caused by an increasingly thin projected replacement pool in years far from the present.

An optional **blend mode** can be enabled to mix the frozen baseline with the current year's computed baseline:

    blended = alpha * frozen + (1 - alpha) * current_year

where `alpha` defaults to 0.70, weighting the frozen baseline more heavily.

### Per-Year Value Above Replacement

For each player in each year, the engine:

1. Takes the average team's stat totals.
2. Swaps out the average player at the best-fit slot and swaps in the player being valued.
3. Swaps out the average player and swaps in the replacement-level player.
4. Computes the category-level difference between these two substitutions.
5. Divides each category delta by its SGP denominator and sums across categories.

The result is the player's **YearValue** -- their marginal SGP contribution above replacement for that year.

---

## 4. Two-Way Player Handling

Players like Shohei Ohtani who contribute as both hitters and pitchers need special treatment. The engine computes separate hitting and pitching values for every player, then merges them.

Two modes are available (controlled by the `two_way` setting):

- **"max" (default):** For each year, take the higher of the player's hitting value or pitching value. This reflects how most leagues work -- you roster the player for their best side, and the other side is a bonus that does not stack for valuation purposes.
- **"sum":** Add the hitting and pitching values together. This is appropriate for leagues where a two-way player genuinely occupies both a hitter slot and a pitcher slot simultaneously, contributing to both.

For players who only appear on one side (hitter-only or pitcher-only), they simply get their single-side value regardless of the mode.

---

## 5. Credit Guards

Credit guards prevent the engine from giving outsized positive credit to players with very low projected playing time. A relief pitcher projected for 20 innings might have a stellar ERA, but his small sample means that ERA contribution is unreliable and should not be valued the same as a starter with 180 innings.

### How the Scale Works

The guard computes a **workload share**:

    share = player_volume / slot_volume_reference

where `player_volume` is the player's projected IP (or AB for hitters) and `slot_volume_reference` is the average IP (or AB) for starters at that slot.

The scale is then:

- If `share >= 1.0` (full workload): scale = 1.0 (no penalty)
- If `share <= 0.35` (less than 35% of a typical starter): scale = 0.0 (no positive credit)
- Between 0.35 and 1.0: linear interpolation from 0 to 1

### What Gets Scaled

Only **positive** category credit is scaled down. Negative credit (a pitcher hurting your team) is never reduced -- you always pay the full penalty for bad production. This asymmetry is intentional: the risk of a low-volume player being bad is real, while the upside from a tiny sample is speculative.

There are two guard variants:

- **Non-ratio guard:** Scales positive credit in counting categories (W, K, SV, etc.) for low-IP pitchers.
- **Ratio guard:** Scales positive credit in rate categories (ERA, WHIP) for low-IP pitchers.

When the unified `enable_playing_time_reliability` flag is on, a single guard handles all categories together (both ratio and counting) for both hitters and pitchers.

---

## 6. Player-to-Slot Assignment

### The Problem

A player eligible at multiple positions (e.g., a 2B/SS player who can fill 2B, SS, MI, or UT slots) must be assigned to exactly one slot. The engine needs to assign *all* players across the entire league to maximize total production.

### Hungarian Algorithm (Optimal)

When the SciPy library is available, the engine uses the **Hungarian algorithm** (also called the Kuhn-Munkres algorithm) to find the globally optimal assignment. This solves a cost matrix where:

- Rows = roster slots across all teams (e.g., 12 teams x 13 hitter slots = 156 slot instances)
- Columns = all eligible players
- Cost = negative weight (so minimizing cost maximizes total weight)
- Ineligible player-slot pairs get a prohibitively high cost (1,000,000)

### Greedy Fallback

Without SciPy, a greedy heuristic is used:

1. Sort slots by scarcity (fewest eligible players first).
2. For each slot, assign the highest-weighted eligible player who has not already been assigned.

This is not globally optimal but produces reasonable results.

### Vacancy Filling

When there are not enough eligible players to fill all slots (common in thin projection pools for future years), the engine automatically creates zero-stat "vacancy" placeholder players. This prevents the assignment from crashing and treats unfilled slots as producing nothing.

---

## 7. Dynasty Weighting

### Multi-Year Aggregation

Dynasty values aggregate a player's contributions across a configurable horizon (default: 10 years). Each year's value is discounted to present value using an annual discount rate (default: 0.94, meaning each year into the future is worth 94% of the previous year).

### The Keep-or-Drop Dynamic Program

The dynasty value is not simply the sum of discounted year values. Instead, it models the **option to drop the player**. At the start of each season, you choose:

- **Keep:** Receive that year's value (even if negative) and retain the option for future years.
- **Drop:** Receive zero from that point forward.

This is solved by backward induction:

    F[last_year] = max(0, value[last_year])
    F[i] = max(0, value[i] + discount^gap * F[i+1])

The result is always non-negative (you can always drop for zero) and correctly handles players with a bad near-term projection but strong long-term upside (you hold through the bad years to capture future value).

### Age-Risk Adjustment (Optional)

When enabled, an additional multiplier is applied to future year values based on the player's projected age. This captures the increased uncertainty and decline risk for older players:

- **Hitters:** Peak through age 29, gradual decline to 0.88 at 35, then to 0.75 at 39.
- **Pitchers:** Peak through age 28, decline to 0.84 at 34, then to 0.70 at 38.
- **Catchers:** Peak through age 27, steeper decline to 0.82 at 33, then to 0.65 at 37.

For players 31+ with projections beyond the start year, an additional 2%-per-year compounding uncertainty penalty is applied.

### Minor League Stashing

Players eligible for minor league slots can be "stashed" without penalty. Negative year values for minor-eligible players are treated as zero (they sit in minors at no cost), making it free to hold onto young prospects during their development years.

### Centering

After computing raw dynasty values, the engine determines the **last rostered player** (the player at the roster cutoff based on total league size including MLB, bench, minors, and IL slots). That player's raw value becomes the baseline, and all values are shifted so the replacement-level player is worth approximately zero:

    DynastyValue = RawDynastyValue - baseline_value

---

## 8. Points Mode

### How It Differs from Roto

In points-based leagues, there are no category standings. Instead, each stat event has a fixed point value (e.g., HR = +5 points, SO = -1 point). A player's value is their total projected points minus a replacement-level baseline.

### Key Differences in the Algorithm

- **No SGP denominators.** Points are the native currency -- no conversion is needed.
- **Direct point computation.** Each player's projected stats are multiplied by the scoring weights to produce a total points projection. For hitters: singles, doubles, triples, HR, R, RBI, SB, BB, SO. For pitchers: IP, W, L, K, SV, SVH, H, ER, BB.
- **Replacement level.** Computed per slot as the average points total of the top unrostered players eligible at each position.
- **Optimal assignment via min-cost flow.** Instead of the Hungarian algorithm on raw weights, points mode uses a min-cost max-flow network to optimally assign players to slots, maximizing total surplus (points above replacement). This handles the constraint that each player can fill only one slot and each slot has a league-wide capacity.
- **Same dynasty framework.** The keep-or-drop dynamic program, discounting, and centering work identically to roto mode.

### Per-Stat Attribution (Roto Only)

In roto mode, the engine breaks down a player's dynasty value into per-category contributions (e.g., "3.2 of this player's 8.5 dynasty value comes from HR"). This is computed by tracking per-category SGP contributions across years, discounting them, and distributing the total dynasty value proportionally.

---

## Summary of Key Parameters

| Parameter | Default | Purpose |
|---|---|---|
| `n_teams` | 12 | Number of teams in the league |
| `horizon_years` | 10 | How many years to project forward |
| `discount` | 0.94 | Annual discount rate for future value |
| `sims_for_sgp` | 200 | Monte Carlo trials for SGP estimation |
| `two_way` | "max" | How to combine two-way player values |
| `freeze_replacement_baselines` | true | Reuse start-year replacement level for all years |
| `sgp_denominator_mode` | "classic" | "classic" or "robust" (with Winsorization) |
| `enable_playing_time_reliability` | false | Unified playing-time guard for all categories |
| `enable_age_risk_adjustment` | false | Apply age-based decline curves to future values |
