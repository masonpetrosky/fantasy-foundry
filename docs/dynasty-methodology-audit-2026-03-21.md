# Dynasty Value Methodology Audit

Date: 2026-03-21

## Summary

This audit reviewed the shipped dynasty valuation methodology across:

- Default roto runtime behavior
- Shared dynasty logic used by both roto and points
- Points season-total, weekly H2H, and daily H2H branches
- Public methodology/docs copy
- External market and rankings comps

Primary conclusion:

- No immediate engine-breaking defect surfaced in the targeted validation slice.
- The largest risks are source-of-truth drift and calibration drift, not missing code paths.
- The shipped default roto baseline is materially more prospect-aggressive than comparable public market, expert, and trade-value sources.

Follow-up status:

- Source-of-truth default drift was remediated in the same branch by aligning the legacy model defaults, CLI defaults, and public docs to shipped runtime behavior.
- Points-mode docs drift was remediated in the same branch by clarifying that `ip_max` still applies in points mode.
- Calibration review infrastructure was added in follow-up changes on 2026-03-21 via richer explanation payloads, a frozen benchmark fixture, and a repeatable divergence report script.
- The standard default roto baseline was updated in follow-up changes on 2026-03-21 to enable replacement blending by default with `replacement_blend_alpha=0.40`.
- That change reduced weighted benchmark rank error from `23.6000` to `16.7333` and shrank the tracked aggregation-gap queue from `7` players to `3`.
- A post-refresh rebaseline later on 2026-03-21 captured the current control at projection data version `83d42c9d6e14` and methodology fingerprint `b1bc74b4fb76`.
- Under that refreshed projection set, the shipped default still clears its replacement-blend guard and now grades at weighted MAE `17.4933` with `12` suspect gaps (`9` raw-value, `3` aggregation).
- The current open work is no longer a refresh-specific audit question; the new projection-refresh memo classifies the tracked disagreement set as stable model gaps and recommends resuming direct model-gap work.

## Key Findings

### 1. High: Default methodology has multiple conflicting sources of truth

Status: remediated in follow-up changes on 2026-03-21.

At audit time, the shipped app defaults were not aligned with the legacy model defaults, the long-form algorithm doc, or the CLI defaults.

Current shipped defaults are:

- API request model: `horizon=20`, `two_way="sum"`, `enable_prospect_risk_adjustment=True` in `backend/services/calculator/service.py`.
- Frontend calculator defaults: same values in `frontend/src/dynasty_calculator_config.ts`.
- Runtime default lookup/prewarm params: same values in `backend/core/calculator_helpers.py`.

Conflicting defaults at audit time:

- `CommonDynastyRotoSettings` still defaults to `horizon_years=10`, `two_way="max"`, `enable_prospect_risk_adjustment=False` in `backend/valuation/models.py`.
- `backend/valuation/ALGORITHM.md` still documents `two_way="max"` and `horizon_years=10`.
- `backend/valuation/cli.py` still defaults `--horizon` to `10` and `--sims` to `200`.

Impact:

- The runtime site baseline, CLI runs, and developer mental model can diverge.
- The algorithm doc is not reliable as a current source of truth.
- Any offline workflow that relies on legacy defaults can produce a materially different ranking set from the site-default lookup.

Recommendation:

- Make one layer canonical for defaults. The practical choice is the runtime/API layer plus `default_calculation_cache_params`.
- Update or remove conflicting defaults in the dataclass, CLI, and `ALGORITHM.md`.
- Add one test that asserts docs-facing defaults match runtime defaults.

### 2. High: The shipped default roto baseline is materially out of band with public dynasty markets

The shipped default runtime lookup is a 20-year, `two_way=sum`, prospect-risk-on roto baseline. Its top ranks are:

1. Bobby Witt Jr.
2. Nick Kurtz
3. Junior Caminero
4. Vladimir Guerrero Jr.
5. Elly De La Cruz
6. Gunnar Henderson
7. Konnor Griffin
8. Paul Skenes
9. Jackson Chourio
10. Tyler Soderstrom

Notable shipped default ranks from the live lookup:

- Shohei Ohtani: 11
- Juan Soto: 12
- Corbin Carroll: 32
- Tarik Skubal: 39
- Ronald Acuna Jr.: 59
- Roman Anthony: 22

External comparisons do not support this as a neutral baseline:

- Harry Knows Ball trade/rankings market snapshot has Bobby Witt 1, Ohtani 2, Paul Skenes 3, Juan Soto 4, Nick Kurtz 5, Corbin Carroll 6, Junior Caminero 7, Gunnar Henderson 8, Tarik Skubal 9, Elly De La Cruz 10, Julio Rodriguez 11, Roman Anthony 12, Vladimir Guerrero Jr. 14, Ronald Acuna Jr. 15.
- DynastySignal's March 2026 model and ADP comparison has Corbin Carroll at ADP 14 / model 1, Tarik Skubal at ADP 7 / model 24, Ronald Acuna Jr. at ADP 8 / model 3, and Tyler Soderstrom at ADP 87 / model 35.
- Imaginary Brick Wall's 2026 expert rankings still led with Shohei Ohtani 1 and Juan Soto 2.

Sensitivity runs suggest this is not just a two-way setting artifact:

- `two_way=max` only moved Shohei from 11 to 10.
- Enabling age-risk made the veteran suppression stronger, not weaker: Shohei fell to 17 and Tarik Skubal to 47.
- Reducing the horizon from 20 to 10 still left Corbin Carroll at 26, Tarik Skubal at 36, and Ronald Acuna Jr. at 58.
- Turning prospect risk off made the prospect skew even stronger: Konnor Griffin moved to 1 and Sal Stewart to 8.

Assessment:

- The current default stack behaves like an aggressively long-horizon, youth-upside-first model.
- That may be intentional for a "pure model" view, but it is not behaving like a market-adjacent baseline.
- If the site-default list is presented as the main baseline dynasty ranking, this is a product-calibration risk.

Follow-up:

- The shipped default was partially rebalanced on 2026-03-21 by enabling replacement blending at `alpha=0.40`.
- That change materially improved the star-vs-prospect aggregation problem without introducing a large anchor regression.
- A later post-refresh rebaseline under projection data version `83d42c9d6e14` confirmed that the shipped replacement-blend default still passes its benchmark guard.
- The remaining disagreement set is still concentrated in players who are already low before dynasty aggregation, so the next methodology pass should focus on one-year roto/replacement-context assumptions instead of further broad horizon changes.

Recommendation:

- Decide whether the site-default ranking should be:
  - a model-first ranking with explicit "not consensus" framing, or
  - a balanced baseline that is closer to public dynasty market behavior.
- If the latter, recalibration should start with the default horizon, age treatment, and how future upside is centered against replacement.

### 3. Medium: Points-mode public docs are incorrect and H2H explanations are too thin

Status: docs mismatch remediated in follow-up changes on 2026-03-21. H2H explanation depth remains open.

At audit time, the README glossary said points mode had "no Monte Carlo or IP min/max constraints." That was not true for shipped behavior.

Actual shipped behavior:

- The frontend explicitly says `IP Max` applies in roto and points, while `IP Min` is roto-only.
- The points test suite verifies that `ip_max` acts as a hard pitcher-value cap in points mode.

The methodology page is directionally right, but still under-explains the H2H branches relative to the implementation:

- It mentions `keeper_limit`, weekly H2H calibration, and final-day overflow.
- The actual implementation also includes synthetic season-day capacity, effective weekly starts caps, streaming-add assumptions, daily-period caps, and IP-budget diagnostics.

Impact:

- Users can misunderstand why points outputs move when they change `ip_max`, `keeper_limit`, or H2H starts settings.
- Public copy currently understates the amount of modeling embedded in the H2H branches.

Recommendation:

- Fix the README glossary immediately.
- Expand the methodology page with one short subsection per points mode:
  - `season_total`
  - `weekly_h2h`
  - `daily_h2h`
- Include one concrete explanation of starts-cap handling and one note that `ip_max` still binds in points mode.

### 4. Medium: The repo has no reproducible external calibration lane

The repo includes an internal backtest harness in `scripts/backtest_valuation.py`, which is useful for realized-outcome testing. It does not include:

- frozen external dynasty benchmark snapshots
- a repeatable external-comparison script
- a docs/default parity check

Impact:

- The strongest calibration drift in this audit was detectable only through manual comparison.
- Future ranking drift will be hard to classify as intentional or accidental.

Recommendation:

- Add a frozen benchmark dataset for a small comparison set of public sources.
- Add a lightweight comparison script that emits rank deltas for a tracked player list.
- Add a docs/default parity test for key shipped defaults.

## Validation Performed

Local validation that passed:

```bash
pytest --no-cov -q tests/test_api_validation_calculator.py -k default_horizon_is_twenty
pytest --no-cov -q tests/test_common_dynasty_value_regressions.py -k "prospect_risk_adjustment_discounts_minor_eligible_future_value or age_risk_adjustment_penalizes_older_comparable_bat"
pytest --no-cov -q tests/test_api_validation_value_penalties.py -k points_ip_max_hard_cap_trims_excess_pitcher_value
```

Notes:

- Plain `pytest -q` on these narrow selections tripped the repo coverage fail-under gate, so `--no-cov` was used for surgical behavior verification.
- The default lookup and sensitivity evidence came from the live runtime module and the shipped `data/dynasty_lookup.json` payload.

## External Sources Used

- Harry Knows Ball rankings/trade market snapshot: https://harryknowsball.com/rankings?level=Prospects&search=Robles
- DynastySignal ADP vs model: https://dynastysignal.com/articles/adp-vs-model-2026-03-02
- DynastySignal Top 100 ADP gaps: https://dynastysignal.com/articles/adp-top100-2026-02-16
- DynastySignal Top 100 ADP gaps: https://dynastysignal.com/articles/adp-top100-2026-03-09
- Imaginary Brick Wall 2026 rankings page snippet: https://www.imaginarybrickwall.com/page/2/

## Recommended Next Actions

1. Align the default source of truth across runtime, docs, dataclass, and CLI.
2. Make a product call on whether the site-default ranking is meant to be market-adjacent or intentionally model-first.
3. Fix the points-mode docs mismatch and expand H2H methodology notes.
4. Add a reproducible external calibration lane so future audits are not manual.

## Follow-Up Status

- The default source-of-truth mismatch has been remediated across runtime, docs, dataclass, and CLI.
- The external calibration lane now exists through the frozen benchmark fixture, divergence review helpers, and the checked-in default divergence memo.
- The first aggregation fix shipped: replacement blending is now the live default at `alpha=0.40`.
- A follow-up OF/P replacement-depth re-evaluation shipped on the refreshed projection set: the live default now uses internal `replacement_depth_mode="blended_depth"` with `replacement_depth_blend_alpha=0.33` for broad shared `OF` and `P` slots.
- The current projection-refresh rebaseline is captured in `docs/default-dynasty-projection-refresh-memo-2026-03-21.md`.
- Under the current shipped methodology fingerprint `b27c08d528ff`, the refreshed default-roto control is weighted MAE `11.3200` with `22` explained players, `8` suspect gaps, `5` aggregation gaps, and `3` raw-value gaps.
- The latest recommendation is to resume direct model-gap work rather than run another refresh-specific audit, because the tracked disagreement set remained stable through the workbook update.
- A dedicated standard-roto slot-context audit lane now exists for internal OF/P alpha counterfactuals, with the current memo captured in `docs/default-dynasty-slot-context-memo-2026-03-21.md`.
- That slot-context pass currently recommends `recommend_no_slot_context_change_yet`; every softer `OF`/`P` blend candidate regressed weighted benchmark error versus the shipped `0.33 / 0.33` control and none of the tracked OF/P targets cleared the required improvement guards.
- A dedicated standard-roto attribution lane now exists for raw one-year vs replacement vs dynasty-layer classification, with the current memo captured in `docs/default-dynasty-attribution-memo-2026-03-21.md`.
- That attribution pass currently recommends `recommend_aggregation_followup`; among the 8 tracked stable gaps, 4 now classify as clean dynasty-aggregation gaps (`Kyle Tucker`, `Aaron Judge`, `Ronald Acuna Jr.`, `Jose Ramirez`), 3 classify as roto-conversion gaps (`Yordan Alvarez`, `Yoshinobu Yamamoto`, `Bryan Woo`), and `Fernando Tatis Jr.` remains mixed.
- A dedicated deep-roto audit lane now exists in `scripts/report_default_dynasty_divergence.py --profile deep_roto`, with the current memo captured in `docs/deep-dynasty-roto-audit-memo-2026-03-21.md`.
- That deep-roto pass currently recommends `recommend_no_deep_specific_change_yet`; the biggest movement is concentrated in stash economics and forced-roster centering rather than one clean deep-only bug.
- A dedicated points audit lane now exists in `scripts/report_default_dynasty_divergence.py --profile points_season_total` (and the weekly/daily variants), with the current memo captured in `docs/points-dynasty-audit-memo-2026-03-21.md`.
- The hardened, synthetic-scenario-backed points pass now recommends `recommend_no_points_change_yet`; the current season-total, weekly, and daily audit scenarios all classify as expected mechanism behavior or expected behavior with pool recentering.
