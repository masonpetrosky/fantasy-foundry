# Default Dynasty Divergence Memo

- Profile id: `standard_roto`
- Tracked benchmark players: 30
- Settings snapshot: `{"bench":6,"bench_negative_penalty":0.55,"discount":0.94,"enable_age_risk_adjustment":false,"enable_bench_stash_relief":false,"enable_ir_stash_relief":false,"enable_playing_time_reliability":false,"enable_prospect_risk_adjustment":true,"enable_replacement_blend":true,"hit_1b":1,"hit_2b":1,"hit_3b":1,"hit_c":1,"hit_ci":1,"hit_dh":0,"hit_mi":1,"hit_of":5,"hit_ss":1,"hit_ut":1,"horizon":20,"ip_max":null,"ip_min":0.0,"ir":0,"ir_negative_penalty":0.2,"minors":0,"pit_p":9,"pit_rp":0,"pit_sp":0,"replacement_blend_alpha":0.4,"replacement_depth_blend_alpha":0.33,"replacement_depth_mode":"blended_depth","roto_hit_2b":false,"roto_hit_avg":true,"roto_hit_bb":false,"roto_hit_h":false,"roto_hit_hr":true,"roto_hit_obp":false,"roto_hit_ops":false,"roto_hit_r":true,"roto_hit_rbi":true,"roto_hit_sb":true,"roto_hit_slg":false,"roto_hit_tb":false,"roto_pit_era":true,"roto_pit_k":true,"roto_pit_qa3":false,"roto_pit_qs":false,"roto_pit_sv":true,"roto_pit_svh":false,"roto_pit_w":true,"roto_pit_whip":true,"sgp_denominator_mode":"classic","sgp_epsilon_counting":0.15,"sgp_epsilon_ratio":0.0015,"sgp_winsor_high_pct":0.9,"sgp_winsor_low_pct":0.1,"sims":300,"start_year":2026,"teams":12,"two_way":"sum"}`
- Projection data version: `83d42c9d6e14`
- Methodology fingerprint: `b27c08d528ff`
- Previous projection snapshot: `bat_prev/pit_prev`
- Weighted mean absolute rank error: 11.3200
- Suspect model gaps: 8
- Aggregation gaps: 5
- Raw-value gaps: 3
- Mixed gaps: 0
- Attribution counts: projection `9`, roto conversion `4`, aggregation `4`, mixed `13`.

## Target Players

### Corbin Carroll

- Benchmark rank 6, model rank 17, delta 11, start-year rank 28, bucket `unbucketed`.
- Start-year best slot `OF`. Primary raw-value cause `slot_replacement_context`.
- Raw start-year rank 22, raw value 4.31, raw best slot `OF`. Attribution `projection_shape_gap`.
- Layer deltas: raw->replacement 6, replacement->dynasty -11.
- Projection delta +0.000 (`stable`), top changed stats: AVG (+0.000), HR (+0.000), OPS (+0.000).
- Start-year projection snapshot: AB=540.9, R=95.0, HR=25.2, RBI=79.7, SB=30.0, AVG=0.259, OPS=0.832.
- Refresh label: `n/a`.
- Start-year value 10.21, discounted 3-year total 30.28, discounted full-horizon total 51.03.
- Positive years 8, last positive year 2033, top discounted seasons: 2027 (10.55), 2026 (10.21), 2028 (9.51).
- Raw start-year positive categories: SB (+1.54), R (+1.52), RBI (+0.61). Raw start-year negative categories: none.
- Start-year positive categories: R (+3.58), SB (+2.29), RBI (+2.10). Start-year negative categories: none.
- Slot baseline reference: slot=OF, mode=flat, ab=510.4. Replacement reference: slot=OF, depth=23, mode=blended_depth, blend_alpha=0.33, slot_count=5, slot_capacity=60, ab=360.2.
- Start-year guard summary: none, share=1.057, scale=1.000.
- Start-year bounds summary: none.
- Players immediately above in model rank: Roman Anthony (14), Sal Stewart (15), Drake Baldwin (16).
- Explanation drivers: none.

### Yordan Alvarez

- Benchmark rank 26, model rank 87, delta 61, start-year rank 44, bucket `raw_value_gap`.
- Start-year best slot `OF`. Primary raw-value cause `slot_replacement_context`.
- Raw start-year rank 33, raw value 3.32, raw best slot `OF`. Attribution `roto_conversion_gap`.
- Layer deltas: raw->replacement 11, replacement->dynasty 43.
- Projection delta +0.000 (`stable`), top changed stats: AVG (+0.000), HR (+0.000), OPS (+0.000).
- Start-year projection snapshot: AB=470.0, R=81.0, HR=29.3, RBI=88.7, SB=1.7, AVG=0.295, OPS=0.937.
- Refresh label: `stable_model_gap`.
- Start-year value 9.20, discounted 3-year total 21.97, discounted full-horizon total 25.45.
- Positive years 5, last positive year 2030, top discounted seasons: 2026 (9.20), 2027 (7.37), 2028 (5.40).
- Raw start-year positive categories: AVG (+2.19), RBI (+1.23), HR (+1.08). Raw start-year negative categories: SB (-1.66).
- Start-year positive categories: AVG (+3.11), RBI (+2.73), R (+2.48). Start-year negative categories: SB (-0.90).
- Slot baseline reference: slot=OF, mode=flat, ab=510.4. Replacement reference: slot=OF, depth=23, mode=blended_depth, blend_alpha=0.33, slot_count=5, slot_capacity=60, ab=360.2.
- Start-year guard summary: none, share=0.921, scale=1.000.
- Start-year bounds summary: none.
- Players immediately above in model rank: Lawrence Butler (84), Charlie Condon (85), Gabriel Moreno (86).
- Explanation drivers: none.

### Kyle Tucker

- Benchmark rank 23, model rank 55, delta 32, start-year rank 22, bucket `aggregation_gap`.
- Start-year best slot `OF`. Primary raw-value cause `slot_replacement_context`.
- Raw start-year rank 13, raw value 5.14, raw best slot `OF`. Attribution `dynasty_aggregation_gap`.
- Layer deltas: raw->replacement 9, replacement->dynasty 33.
- Projection delta +0.000 (`stable`), top changed stats: AVG (+0.000), HR (+0.000), OPS (+0.000).
- Start-year projection snapshot: AB=528.7, R=95.0, HR=29.7, RBI=90.7, SB=19.3, AVG=0.270, OPS=0.878.
- Refresh label: `stable_model_gap`.
- Start-year value 11.08, discounted 3-year total 26.72, discounted full-horizon total 33.19.
- Positive years 6, last positive year 2031, top discounted seasons: 2026 (11.08), 2027 (8.91), 2028 (6.74).
- Raw start-year positive categories: R (+1.54), RBI (+1.36), HR (+1.13). Raw start-year negative categories: none.
- Start-year positive categories: R (+3.60), RBI (+2.87), HR (+1.81). Start-year negative categories: none.
- Slot baseline reference: slot=OF, mode=flat, ab=510.4. Replacement reference: slot=OF, depth=23, mode=blended_depth, blend_alpha=0.33, slot_count=5, slot_capacity=60, ab=360.2.
- Start-year guard summary: none, share=1.036, scale=1.000.
- Start-year bounds summary: none.
- Players immediately above in model rank: Michael Busch (52), Francisco Lindor (53), Jose Ramirez (54).
- Explanation drivers: none.

### Yoshinobu Yamamoto

- Benchmark rank 21, model rank 47, delta 26, start-year rank 56, bucket `raw_value_gap`.
- Start-year best slot `P`. Primary raw-value cause `slot_replacement_context`.
- Raw start-year rank 18, raw value 4.81, raw best slot `P`. Attribution `roto_conversion_gap`.
- Layer deltas: raw->replacement 38, replacement->dynasty -9.
- Projection delta +0.000 (`stable`), top changed stats: ERA (+0.000), K (+0.000), SV (+0.000).
- Start-year projection snapshot: IP=161.0, W=12.3, K=178.4, ERA=3.231, WHIP=1.100, QS=15.5, SV=0.0.
- Refresh label: `stable_model_gap`.
- Start-year value 8.56, discounted 3-year total 24.96, discounted full-horizon total 34.29.
- Positive years 6, last positive year 2031, top discounted seasons: 2027 (8.84), 2026 (8.56), 2028 (7.56).
- Raw start-year positive categories: ERA (+1.57), WHIP (+1.41), W (+1.39). Raw start-year negative categories: SV (-0.65).
- Start-year positive categories: ERA (+2.43), W (+2.28), WHIP (+2.15). Start-year negative categories: SV (-0.31).
- Slot baseline reference: slot=P, mode=flat, ip=126.5. Replacement reference: slot=P, depth=44, mode=blended_depth, blend_alpha=0.33, slot_count=9, slot_capacity=108, ip=100.1.
- Start-year guard summary: low_volume_split, share=1.264, scale=1.000.
- Start-year bounds summary: none.
- Players immediately above in model rank: Brice Turang (44), Nolan Schanuel (45), Bryan Woo (46).
- Explanation drivers: none.

### Roman Anthony

- Benchmark rank 8, model rank 14, delta 6, start-year rank 103, bucket `unbucketed`.
- Start-year best slot `OF`. Primary raw-value cause `slot_replacement_context`.
- Raw start-year rank 74, raw value 0.84, raw best slot `OF`. Attribution `projection_shape_gap`.
- Layer deltas: raw->replacement 29, replacement->dynasty -89.
- Projection delta +0.000 (`stable`), top changed stats: AVG (+0.000), HR (+0.000), OPS (+0.000).
- Start-year projection snapshot: AB=520.0, R=87.4, HR=19.0, RBI=73.3, SB=8.8, AVG=0.269, OPS=0.809.
- Refresh label: `n/a`.
- Start-year value 6.70, discounted 3-year total 22.31, discounted full-horizon total 55.62.
- Positive years 11, last positive year 2036, top discounted seasons: 2029 (8.24), 2028 (7.96), 2027 (7.66).
- Raw start-year positive categories: R (+0.96), AVG (+0.71), RBI (+0.19). Raw start-year negative categories: SB (-0.85), HR (-0.18).
- Start-year positive categories: R (+3.00), RBI (+1.68), AVG (+1.63). Start-year negative categories: SB (-0.09).
- Slot baseline reference: slot=OF, mode=flat, ab=510.4. Replacement reference: slot=OF, depth=23, mode=blended_depth, blend_alpha=0.33, slot_count=5, slot_capacity=60, ab=360.2.
- Start-year guard summary: none, share=1.019, scale=1.000.
- Start-year bounds summary: none.
- Players immediately above in model rank: Julio Rodriguez (11), James Wood (12), Shohei Ohtani (13).
- Explanation drivers: long_horizon_weight.

### Fernando Tatis Jr.

- Benchmark rank 19, model rank 34, delta 15, start-year rank 23, bucket `aggregation_gap`.
- Start-year best slot `OF`. Primary raw-value cause `slot_replacement_context`.
- Raw start-year rank 15, raw value 5.11, raw best slot `OF`. Attribution `mixed_gap`.
- Layer deltas: raw->replacement 8, replacement->dynasty 11.
- Projection delta +0.000 (`stable`), top changed stats: AVG (+0.000), HR (+0.000), OPS (+0.000).
- Start-year projection snapshot: AB=562.7, R=97.7, HR=28.7, RBI=83.7, SB=23.3, AVG=0.268, OPS=0.833.
- Refresh label: `stable_model_gap`.
- Start-year value 11.04, discounted 3-year total 28.43, discounted full-horizon total 39.74.
- Positive years 6, last positive year 2031, top discounted seasons: 2026 (11.04), 2027 (9.76), 2028 (7.63).
- Raw start-year positive categories: R (+1.74), HR (+1.00), RBI (+0.89). Raw start-year negative categories: none.
- Start-year positive categories: R (+3.81), RBI (+2.39), HR (+1.69). Start-year negative categories: none.
- Slot baseline reference: slot=OF, mode=flat, ab=510.4. Replacement reference: slot=OF, depth=23, mode=blended_depth, blend_alpha=0.33, slot_count=5, slot_capacity=60, ab=360.2.
- Start-year guard summary: none, share=1.102, scale=1.000.
- Start-year bounds summary: none.
- Players immediately above in model rank: Agustin Ramirez (31), Francisco Alvarez (32), Wyatt Langford (33).
- Explanation drivers: none.

### Wyatt Langford

- Benchmark rank 24, model rank 33, delta 9, start-year rank 70, bucket `unbucketed`.
- Start-year best slot `OF`. Primary raw-value cause `slot_replacement_context`.
- Raw start-year rank 48, raw value 2.07, raw best slot `OF`. Attribution `projection_shape_gap`.
- Layer deltas: raw->replacement 22, replacement->dynasty -37.
- Projection delta +0.000 (`stable`), top changed stats: AVG (+0.000), HR (+0.000), OPS (+0.000).
- Start-year projection snapshot: AB=540.3, R=84.6, HR=23.8, RBI=77.9, SB=20.3, AVG=0.257, OPS=0.798.
- Refresh label: `n/a`.
- Start-year value 7.93, discounted 3-year total 23.32, discounted full-horizon total 39.82.
- Positive years 7, last positive year 2032, top discounted seasons: 2027 (7.94), 2026 (7.93), 2028 (7.46).
- Raw start-year positive categories: R (+0.74), RBI (+0.50), SB (+0.45). Raw start-year negative categories: AVG (-0.05).
- Start-year positive categories: R (+2.77), RBI (+1.99), SB (+1.21). Start-year negative categories: none.
- Slot baseline reference: slot=OF, mode=flat, ab=510.4. Replacement reference: slot=OF, depth=23, mode=blended_depth, blend_alpha=0.33, slot_count=5, slot_capacity=60, ab=360.2.
- Start-year guard summary: none, share=1.059, scale=1.000.
- Start-year bounds summary: none.
- Players immediately above in model rank: Ben Rice (30), Agustin Ramirez (31), Francisco Alvarez (32).
- Explanation drivers: none.

### Bryan Woo

- Benchmark rank 25, model rank 46, delta 21, start-year rank 55, bucket `raw_value_gap`.
- Start-year best slot `P`. Primary raw-value cause `slot_replacement_context`.
- Raw start-year rank 17, raw value 4.86, raw best slot `P`. Attribution `roto_conversion_gap`.
- Layer deltas: raw->replacement 38, replacement->dynasty -9.
- Projection delta +0.000 (`stable`), top changed stats: ERA (+0.000), K (+0.000), SV (+0.000).
- Start-year projection snapshot: IP=181.8, W=12.2, K=184.2, ERA=3.497, WHIP=1.071, QS=17.8, SV=0.0.
- Refresh label: `stable_model_gap`.
- Start-year value 8.58, discounted 3-year total 24.45, discounted full-horizon total 34.30.
- Positive years 7, last positive year 2032, top discounted seasons: 2026 (8.58), 2027 (8.49), 2028 (7.38).
- Raw start-year positive categories: WHIP (+2.14), W (+1.41), K (+1.27). Raw start-year negative categories: SV (-0.65).
- Start-year positive categories: WHIP (+2.88), W (+2.30), K (+2.19). Start-year negative categories: SV (-0.31).
- Slot baseline reference: slot=P, mode=flat, ip=126.5. Replacement reference: slot=P, depth=44, mode=blended_depth, blend_alpha=0.33, slot_count=9, slot_capacity=108, ip=100.1.
- Start-year guard summary: low_volume_split, share=1.438, scale=1.000.
- Start-year bounds summary: none.
- Players immediately above in model rank: Kevin McGonigle (43), Brice Turang (44), Nolan Schanuel (45).
- Explanation drivers: none.

### Pete Crow-Armstrong

- Benchmark rank 29, model rank 28, delta -1, start-year rank 37, bucket `unbucketed`.
- Start-year best slot `OF`. Primary raw-value cause `slot_replacement_context`.
- Raw start-year rank 27, raw value 3.81, raw best slot `OF`. Attribution `mixed_gap`.
- Layer deltas: raw->replacement 10, replacement->dynasty -9.
- Projection delta +0.000 (`stable`), top changed stats: AVG (+0.000), HR (+0.000), OPS (+0.000).
- Start-year projection snapshot: AB=568.7, R=87.0, HR=24.7, RBI=85.0, SB=32.2, AVG=0.252, OPS=0.752.
- Refresh label: `n/a`.
- Start-year value 9.69, discounted 3-year total 27.29, discounted full-horizon total 42.64.
- Positive years 7, last positive year 2032, top discounted seasons: 2026 (9.69), 2027 (9.34), 2028 (8.26).
- Raw start-year positive categories: SB (+1.80), RBI (+0.98), R (+0.93). Raw start-year negative categories: AVG (-0.41).
- Start-year positive categories: R (+2.96), SB (+2.54), RBI (+2.48). Start-year negative categories: none.
- Slot baseline reference: slot=OF, mode=flat, ab=510.4. Replacement reference: slot=OF, depth=23, mode=blended_depth, blend_alpha=0.33, slot_count=5, slot_capacity=60, ab=360.2.
- Start-year guard summary: none, share=1.114, scale=1.000.
- Start-year bounds summary: none.
- Players immediately above in model rank: Shea Langeliers (25), William Contreras (26), Zach Neto (27).
- Explanation drivers: none.

## Bucket Summaries

- `aggregation_gap`: 5 tracked players still rank inside the top-25 in start-year roto value (median start-year rank 12.0) but fall to a median dynasty rank of 39.0 against median benchmark rank 19.0. This points to a dynasty aggregation problem rather than a one-year valuation miss.
- `raw_value_gap`: 3 tracked players are already outside the top-25 in start-year roto value (median start-year rank 55.0), so their gap starts before dynasty aggregation. This points to one-year roto or replacement-context assumptions rather than horizon discounting.
- `mixed_gap`: No tracked mixed-gap players in the current review.

