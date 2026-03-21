# Points Dynasty Audit Memo

- Focus profile id: `points_season_total`
- Projection data version: `83d42c9d6e14`

## season_total

- Profile `points_season_total` fingerprint `2649d4523193`.
- Settings snapshot: `{"1B":1,"2B":1,"3B":1,"C":1,"CI":0,"DH":0,"MI":0,"OF":3,"P":2,"RP":2,"SP":5,"SS":1,"UT":1,"allow_same_day_starts_overflow":false,"bench":6,"bench_negative_penalty":0.55,"discount":0.94,"enable_age_risk_adjustment":false,"enable_bench_stash_relief":false,"enable_ir_stash_relief":false,"enable_playing_time_reliability":false,"enable_prospect_risk_adjustment":true,"enable_replacement_blend":true,"hit_1b":1,"hit_2b":1,"hit_3b":1,"hit_c":1,"hit_ci":1,"hit_dh":0,"hit_mi":1,"hit_of":5,"hit_ss":1,"hit_ut":1,"horizon":20,"ip_max":null,"ip_min":0.0,"ir":0,"ir_negative_penalty":0.2,"keeper_limit":null,"minors":0,"pit_p":9,"pit_rp":0,"pit_sp":0,"points_valuation_mode":"season_total","pts_hit_1b":1.0,"pts_hit_2b":2.0,"pts_hit_3b":3.0,"pts_hit_bb":1.0,"pts_hit_hbp":0.0,"pts_hit_hr":4.0,"pts_hit_r":1.0,"pts_hit_rbi":1.0,"pts_hit_sb":1.0,"pts_hit_so":-1.0,"pts_pit_bb":-1.0,"pts_pit_er":-2.0,"pts_pit_h":-1.0,"pts_pit_hbp":0.0,"pts_pit_hld":0.0,"pts_pit_ip":3.0,"pts_pit_k":1.0,"pts_pit_l":-5.0,"pts_pit_sv":5.0,"pts_pit_w":5.0,"replacement_blend_alpha":0.4,"replacement_depth_blend_alpha":0.33,"replacement_depth_mode":"blended_depth","roto_hit_2b":false,"roto_hit_avg":true,"roto_hit_bb":false,"roto_hit_h":false,"roto_hit_hr":true,"roto_hit_obp":false,"roto_hit_ops":false,"roto_hit_r":true,"roto_hit_rbi":true,"roto_hit_sb":true,"roto_hit_slg":false,"roto_hit_tb":false,"roto_pit_era":true,"roto_pit_k":true,"roto_pit_qa3":false,"roto_pit_qs":false,"roto_pit_sv":true,"roto_pit_svh":false,"roto_pit_w":true,"roto_pit_whip":true,"scoring_mode":"points","sgp_denominator_mode":"classic","sgp_epsilon_counting":0.15,"sgp_epsilon_ratio":0.0015,"sgp_winsor_high_pct":0.9,"sgp_winsor_low_pct":0.1,"sims":300,"start_year":2026,"teams":12,"two_way":"sum","weekly_acquisition_cap":null,"weekly_starts_cap":null}`.
- Replacement rank `336`, in-season replacement rank `336`, keeper limit `None`.
- `season_total_bench_ir_stash_relief` bucket `stash_risk_adjustment_effect` -> status `expected_mechanism`.
- Audit reason: stash relief should raise selected points for reserve or injured hitters.
- Cohort `reserve / stash hitters` direct metrics: count=2, med_pts=+3.2500, mean_pts=+3.2500, med_dyn=+2.0000, mean_dyn=+2.0000, med_raw=+2.0000, mean_raw=+2.0000, med_rank=+0.0000, med_usage=+0.0000, mean_usage=+0.0000, med_starts=+0.0000, mean_starts=+0.0000, med_ip=+0.0000, mean_ip=+0.0000.
- Pool recenter metrics: replacement_rank_delta=+0, in_season_replacement_rank_delta=+0, unaffected_top_movers=2, examples=Replacement C (4 -> 4, +0), Starter A (1 -> 1, +0).
- `season_total_deep_replacement_depth` bucket `replacement_depth_keeper_limit_effect` -> status `expected_mechanism`.
- Audit reason: deeper season-total depth should push the replacement rank deeper.
- Cohort `replacement fringe hitters` direct metrics: count=3, med_pts=+2.0000, mean_pts=+3.3333, med_dyn=+2.0000, mean_dyn=+4.6667, med_raw=+0.0000, mean_raw=+2.6667, med_rank=+0.0000, med_usage=+0.0000, mean_usage=+0.0000, med_starts=+0.0000, mean_starts=+0.0000, med_ip=+0.0000, mean_ip=+0.0000.
- Pool recenter metrics: replacement_rank_delta=+26, in_season_replacement_rank_delta=+26, unaffected_top_movers=0.
- `season_total_ip_max_hard_cap` bucket `innings_cap_trimming` -> status `expected_with_pool_recenter`.
- Audit reason: ip_max should bind, trim assigned IP, and lower selected points for the pitcher cohort.
- Cohort `IP-capped pitchers` direct metrics: count=2, med_pts=-150.0000, mean_pts=-150.0000, med_dyn=-170.0000, mean_dyn=-170.0000, med_raw=-150.0000, mean_raw=-150.0000, med_rank=+0.0000, med_usage=-0.8125, mean_usage=-0.8125, med_starts=+0.0000, mean_starts=+0.0000, med_ip=-110.0000, mean_ip=-110.0000.
- Pool recenter metrics: replacement_rank_delta=+0, in_season_replacement_rank_delta=+0, unaffected_top_movers=2, examples=Ace A (1 -> 1, +0), Utility Bat (3 -> 3, +0).
- `season_total_keeper_limit_override` bucket `replacement_depth_keeper_limit_effect` -> status `expected_mechanism`.
- Audit reason: keeper-limit override should pull the replacement rank shallower and match the keeper limit.
- Cohort `replacement fringe hitters` direct metrics: count=3, med_pts=-2.0000, mean_pts=-3.3333, med_dyn=-2.0000, mean_dyn=-4.6667, med_raw=+0.0000, mean_raw=-2.6667, med_rank=+0.0000, med_usage=+0.0000, mean_usage=+0.0000, med_starts=+0.0000, mean_starts=+0.0000, med_ip=+0.0000, mean_ip=+0.0000.
- Pool recenter metrics: replacement_rank_delta=-26, in_season_replacement_rank_delta=+0, unaffected_top_movers=0.
- `season_total_prospect_risk_discount` bucket `stash_risk_adjustment_effect` -> status `expected_mechanism`.
- Audit reason: prospect risk should lower dynasty value for minor-eligible players even when start-year points stay flat.
- Cohort `minor-eligible hitters` direct metrics: count=2, med_pts=+0.0000, mean_pts=+0.0000, med_dyn=-0.3760, mean_dyn=-0.3760, med_raw=-0.3760, mean_raw=-0.3760, med_rank=+0.0000, med_usage=+0.0000, mean_usage=+0.0000, med_starts=+0.0000, mean_starts=+0.0000, med_ip=+0.0000, mean_ip=+0.0000.
- Pool recenter metrics: replacement_rank_delta=+0, in_season_replacement_rank_delta=+0, unaffected_top_movers=2, examples=Replacement C (4 -> 4, +0), Starter A (1 -> 1, +0).

## weekly_h2h

- Profile `points_weekly_h2h` fingerprint `a6c92fde452f`.
- Settings snapshot: `{"1B":1,"2B":1,"3B":1,"C":1,"CI":0,"DH":0,"MI":0,"OF":3,"P":2,"RP":2,"SP":5,"SS":1,"UT":1,"allow_same_day_starts_overflow":false,"bench":6,"bench_negative_penalty":0.55,"discount":0.94,"enable_age_risk_adjustment":false,"enable_bench_stash_relief":false,"enable_ir_stash_relief":false,"enable_playing_time_reliability":false,"enable_prospect_risk_adjustment":true,"enable_replacement_blend":true,"hit_1b":1,"hit_2b":1,"hit_3b":1,"hit_c":1,"hit_ci":1,"hit_dh":0,"hit_mi":1,"hit_of":5,"hit_ss":1,"hit_ut":1,"horizon":20,"ip_max":null,"ip_min":0.0,"ir":0,"ir_negative_penalty":0.2,"keeper_limit":null,"minors":0,"pit_p":9,"pit_rp":0,"pit_sp":0,"points_valuation_mode":"weekly_h2h","pts_hit_1b":1.0,"pts_hit_2b":2.0,"pts_hit_3b":3.0,"pts_hit_bb":1.0,"pts_hit_hbp":0.0,"pts_hit_hr":4.0,"pts_hit_r":1.0,"pts_hit_rbi":1.0,"pts_hit_sb":1.0,"pts_hit_so":-1.0,"pts_pit_bb":-1.0,"pts_pit_er":-2.0,"pts_pit_h":-1.0,"pts_pit_hbp":0.0,"pts_pit_hld":0.0,"pts_pit_ip":3.0,"pts_pit_k":1.0,"pts_pit_l":-5.0,"pts_pit_sv":5.0,"pts_pit_w":5.0,"replacement_blend_alpha":0.4,"replacement_depth_blend_alpha":0.33,"replacement_depth_mode":"blended_depth","roto_hit_2b":false,"roto_hit_avg":true,"roto_hit_bb":false,"roto_hit_h":false,"roto_hit_hr":true,"roto_hit_obp":false,"roto_hit_ops":false,"roto_hit_r":true,"roto_hit_rbi":true,"roto_hit_sb":true,"roto_hit_slg":false,"roto_hit_tb":false,"roto_pit_era":true,"roto_pit_k":true,"roto_pit_qa3":false,"roto_pit_qs":false,"roto_pit_sv":true,"roto_pit_svh":false,"roto_pit_w":true,"roto_pit_whip":true,"scoring_mode":"points","sgp_denominator_mode":"classic","sgp_epsilon_counting":0.15,"sgp_epsilon_ratio":0.0015,"sgp_winsor_high_pct":0.9,"sgp_winsor_low_pct":0.1,"sims":300,"start_year":2026,"teams":12,"two_way":"sum","weekly_acquisition_cap":2,"weekly_starts_cap":7}`.
- Replacement rank `336`, in-season replacement rank `336`, keeper limit `None`.
- `weekly_reliever_fractional_start_handling` bucket `weekly_streaming_fungibility` -> status `expected_mechanism`.
- Audit reason: relievers with fractional GS should not pick up streaming starts.
- Cohort `fractional-start relievers` direct metrics: count=1, med_pts=+0.0000, mean_pts=+0.0000, med_dyn=+0.0000, mean_dyn=+0.0000, med_raw=+0.0000, mean_raw=+0.0000, med_rank=+0.0000, med_usage=+0.0000, mean_usage=+0.0000, med_starts=+0.0000, mean_starts=+0.0000, med_ip=+0.0000, mean_ip=+0.0000.
- Pool recenter metrics: replacement_rank_delta=+0, in_season_replacement_rank_delta=+0, unaffected_top_movers=2, examples=Ace A (1 -> 1, +0), Starter B (2 -> 2, +0).
- `weekly_same_day_starts_overflow` bucket `weekly_streaming_fungibility` -> status `expected_mechanism`.
- Audit reason: same-day starts overflow should increase the capped SP cohort's assigned starts and raise selected points or dynasty value.
- Cohort `streamable SP cohort` direct metrics: count=1, med_pts=+0.0000, mean_pts=+0.0000, med_dyn=+20.0000, mean_dyn=+20.0000, med_raw=+0.0000, mean_raw=+0.0000, med_rank=+0.0000, med_usage=+0.5000, mean_usage=+0.5000, med_starts=+13.0000, mean_starts=+13.0000, med_ip=+39.0000, mean_ip=+39.0000.
- Pool recenter metrics: replacement_rank_delta=+0, in_season_replacement_rank_delta=+0, unaffected_top_movers=3, examples=Ace A (1 -> 1, +0), Starter B (2 -> 2, +0), Utility Bat (3 -> 3, +0).
- `weekly_streaming_suppression` bucket `weekly_streaming_fungibility` -> status `expected_with_pool_recenter`.
- Audit reason: weekly starts/acquisition caps should reduce SP usage share and assigned starts, with lower selected points or dynasty value for the direct SP cohort.
- Cohort `streamable SP cohort` direct metrics: count=1, med_pts=+0.0000, mean_pts=+0.0000, med_dyn=-20.0000, mean_dyn=-20.0000, med_raw=+0.0000, mean_raw=+0.0000, med_rank=+0.0000, med_usage=-1.0000, mean_usage=-1.0000, med_starts=-26.0000, mean_starts=-26.0000, med_ip=-78.0000, mean_ip=-78.0000.
- Pool recenter metrics: replacement_rank_delta=+0, in_season_replacement_rank_delta=+0, unaffected_top_movers=3, examples=Ace A (1 -> 1, +0), Starter B (2 -> 2, +0), Utility Bat (3 -> 3, +0).

## daily_h2h

- Profile `points_daily_h2h` fingerprint `a30fc137568b`.
- Settings snapshot: `{"1B":1,"2B":1,"3B":1,"C":1,"CI":0,"DH":0,"MI":0,"OF":3,"P":2,"RP":2,"SP":5,"SS":1,"UT":1,"allow_same_day_starts_overflow":false,"bench":6,"bench_negative_penalty":0.55,"discount":0.94,"enable_age_risk_adjustment":false,"enable_bench_stash_relief":false,"enable_ir_stash_relief":false,"enable_playing_time_reliability":false,"enable_prospect_risk_adjustment":true,"enable_replacement_blend":true,"hit_1b":1,"hit_2b":1,"hit_3b":1,"hit_c":1,"hit_ci":1,"hit_dh":0,"hit_mi":1,"hit_of":5,"hit_ss":1,"hit_ut":1,"horizon":20,"ip_max":null,"ip_min":0.0,"ir":0,"ir_negative_penalty":0.2,"keeper_limit":null,"minors":0,"pit_p":9,"pit_rp":0,"pit_sp":0,"points_valuation_mode":"daily_h2h","pts_hit_1b":1.0,"pts_hit_2b":2.0,"pts_hit_3b":3.0,"pts_hit_bb":1.0,"pts_hit_hbp":0.0,"pts_hit_hr":4.0,"pts_hit_r":1.0,"pts_hit_rbi":1.0,"pts_hit_sb":1.0,"pts_hit_so":-1.0,"pts_pit_bb":-1.0,"pts_pit_er":-2.0,"pts_pit_h":-1.0,"pts_pit_hbp":0.0,"pts_pit_hld":0.0,"pts_pit_ip":3.0,"pts_pit_k":1.0,"pts_pit_l":-5.0,"pts_pit_sv":5.0,"pts_pit_w":5.0,"replacement_blend_alpha":0.4,"replacement_depth_blend_alpha":0.33,"replacement_depth_mode":"blended_depth","roto_hit_2b":false,"roto_hit_avg":true,"roto_hit_bb":false,"roto_hit_h":false,"roto_hit_hr":true,"roto_hit_obp":false,"roto_hit_ops":false,"roto_hit_r":true,"roto_hit_rbi":true,"roto_hit_sb":true,"roto_hit_slg":false,"roto_hit_tb":false,"roto_pit_era":true,"roto_pit_k":true,"roto_pit_qa3":false,"roto_pit_qs":false,"roto_pit_sv":true,"roto_pit_svh":false,"roto_pit_w":true,"roto_pit_whip":true,"scoring_mode":"points","sgp_denominator_mode":"classic","sgp_epsilon_counting":0.15,"sgp_epsilon_ratio":0.0015,"sgp_winsor_high_pct":0.9,"sgp_winsor_low_pct":0.1,"sims":300,"start_year":2026,"teams":12,"two_way":"sum","weekly_acquisition_cap":2,"weekly_starts_cap":7}`.
- Replacement rank `336`, in-season replacement rank `336`, keeper limit `None`.
- `daily_starts_cap_behavior` bucket `daily_starts_cap_effect` -> status `expected_with_pool_recenter`.
- Audit reason: daily starts caps should reduce assigned starts and selected points for the capped SP cohort.
- Cohort `daily capped SP cohort` direct metrics: count=3, med_pts=+0.0000, mean_pts=-52.0000, med_dyn=+0.0000, mean_dyn=-52.0000, med_raw=+0.0000, mean_raw=-52.0000, med_rank=+0.0000, med_usage=-1.0000, mean_usage=-1.0000, med_starts=-52.0000, mean_starts=-52.0000, med_ip=-104.0000, mean_ip=-104.0000.
- Pool recenter metrics: replacement_rank_delta=+0, in_season_replacement_rank_delta=+0, unaffected_top_movers=2, examples=Utility Bat (3 -> 2, +1), Ace A (1 -> 1, +0).

## Recommendation

- `recommend_no_points_change_yet`
