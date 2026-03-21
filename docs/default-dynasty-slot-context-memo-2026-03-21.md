# Default Dynasty Slot-Context Memo

- Profile id: `standard_roto`
- Projection data version: `83d42c9d6e14`
- Methodology fingerprint: `b27c08d528ff`
- Control weighted MAE: `11.3200`
- Control slot alphas: `OF=0.33`, `P=0.33`

## Candidate Matrix

| Candidate | Group | OF Alpha | P Alpha | WMAE | WMAE vs Control | OF +8 | P +8 | Worst Hitter Control Reg | Worst Pitcher Control Reg | Guard Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A | of_only | 0.25 | 0.33 | 12.0267 | -6.24% | 0 | 0 | 5 | 0 | fail |
| B | of_only | 0.20 | 0.33 | 12.5067 | -10.48% | 0 | 0 | 7 | 0 | fail |
| C | p_only | 0.33 | 0.25 | 11.7333 | -3.65% | 0 | 0 | 0 | 1 | fail |
| D | p_only | 0.33 | 0.20 | 11.8267 | -4.48% | 0 | 0 | 0 | 1 | fail |
| E | combined | 0.25 | 0.25 | 12.4400 | -9.89% | 0 | 0 | 5 | 1 | fail |
| F | combined | 0.20 | 0.25 | 12.9200 | -14.13% | 0 | 0 | 7 | 1 | fail |

## Interpretation

- The current shipped control outperformed every softer slot-context candidate on weighted benchmark error.
- No OF-only candidate improved even 1 of the 5 tracked OF targets by the required 8 dynasty-rank slots; both candidates landed at `0/5`.
- No P-only candidate improved either Yamamoto or Woo by the required 8 dynasty-rank slots; both candidates landed at `0/2`.
- The combined candidates were strictly worse than control and worse than the single-family candidates.
- The remaining stable model gaps are therefore not explained by the current `OF`/`P` replacement-depth blend being too strong at `0.33`.

## Target Set

- OF targets reviewed: Yordan Alvarez, Kyle Tucker, Fernando Tatis Jr., Aaron Judge, Ronald Acuna Jr.
- P targets reviewed: Yoshinobu Yamamoto, Bryan Woo
- Negative-control holdout: Jose Ramirez
- Explained controls held constant in the guard lane: Corbin Carroll, Roman Anthony, Wyatt Langford, Pete Crow-Armstrong, Juan Soto, Julio Rodriguez, Paul Skenes, Tarik Skubal

## Recommendation

- `recommend_no_slot_context_change_yet`

