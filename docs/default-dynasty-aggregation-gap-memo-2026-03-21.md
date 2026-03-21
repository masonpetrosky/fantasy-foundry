# Default Dynasty Aggregation-Gap Memo

- Tracked benchmark players: 30
- Projection data version: `83d42c9d6e14`
- Methodology fingerprint: `b27c08d528ff`
- Weighted mean absolute rank error: 11.3200
- Aggregation gaps: 5
- Recommendation: `recommend_no_methodology_change_yet`

## Target Players

### Aaron Judge

- Benchmark rank 14, model rank 39, start-year rank 6, diagnosis `mixed`.
- Projection delta +0.000 (`stable`), top changed stats: AVG (+0.000), HR (+0.000), OPS (+0.000).
- Discounted 3-year total 33.49, discounted full-horizon total 37.36.
- Positive years 4, last positive year 2029, first near-zero year 2035.
- First non-positive adjusted year 2030, positive-year span 4, tail after year 3 3.87 (share 0.1036).
- Tail preview: 2026 adj=14.54 disc=14.54 ab=521.3 ip=0.0; 2027 adj=12.07 disc=11.35 ab=499.3 ip=0.0; 2028 adj=8.61 disc=7.61 ab=471.3 ip=0.0; 2029 adj=4.66 disc=3.87 ab=435.0 ip=0.0; 2030 adj=-2.31 disc=0.00 ab=379.7 ip=0.0; 2031 adj=-16.07 disc=0.00 ab=307.3 ip=0.0.
- Players immediately above in model rank: Luke Keaschall (rank 36, start 95, positive_years 9, first_near_zero 2042, tail_share 0.4815); Yainer Diaz (rank 37, start 60, positive_years 6, first_near_zero 2039, tail_share 0.3512); Chase Burns (rank 38, start 210, positive_years 10, first_near_zero 2042, tail_share 0.6483).
- Median comp positive-year count: 9.0.

### Ronald Acuna Jr.

- Benchmark rank 10, model rank 29, start-year rank 12, diagnosis `mixed`.
- Projection delta +0.000 (`stable`), top changed stats: AVG (+0.000), HR (+0.000), OPS (+0.000).
- Discounted 3-year total 31.23, discounted full-horizon total 40.72.
- Positive years 6, last positive year 2031, first near-zero year 2039.
- First non-positive adjusted year 2032, positive-year span 6, tail after year 3 9.49 (share 0.2332).
- Tail preview: 2026 adj=12.74 disc=12.74 ab=551.3 ip=0.0; 2027 adj=11.20 disc=10.53 ab=540.7 ip=0.0; 2028 adj=9.01 disc=7.96 ab=527.3 ip=0.0; 2029 adj=6.69 disc=5.56 ab=509.0 ip=0.0; 2030 adj=3.81 disc=2.97 ab=484.3 ip=0.0; 2031 adj=1.31 disc=0.96 ab=457.7 ip=0.0.
- Players immediately above in model rank: William Contreras (rank 26, start 25, positive_years 5, first_near_zero 2038, tail_share 0.2898); Zach Neto (rank 27, start 19, positive_years 7, first_near_zero 2041, tail_share 0.2816); Pete Crow-Armstrong (rank 28, start 37, positive_years 7, first_near_zero 2041, tail_share 0.3600).
- Median comp positive-year count: 7.0.

### Jose Ramirez

- Benchmark rank 22, model rank 54, start-year rank 8, diagnosis `comp_horizon_gap`.
- Projection delta +0.000 (`stable`), top changed stats: AVG (+0.000), HR (+0.000), OPS (+0.000).
- Discounted 3-year total 30.38, discounted full-horizon total 33.22.
- Positive years 4, last positive year 2029, first near-zero year 2035.
- First non-positive adjusted year 2030, positive-year span 4, tail after year 3 2.84 (share 0.0854).
- Tail preview: 2026 adj=13.84 disc=13.84 ab=571.0 ip=0.0; 2027 adj=11.19 disc=10.52 ab=544.7 ip=0.0; 2028 adj=6.82 disc=6.03 ab=517.3 ip=0.0; 2029 adj=3.42 disc=2.84 ab=480.7 ip=0.0; 2030 adj=-2.72 disc=0.00 ab=435.7 ip=0.0; 2031 adj=-14.50 disc=0.00 ab=379.0 ip=0.0.
- Players immediately above in model rank: JJ Wetherholt (rank 51, start 149, positive_years 10, first_near_zero 2041, tail_share 0.4640); Michael Busch (rank 52, start 39, positive_years 6, first_near_zero 2038, tail_share 0.2318); Francisco Lindor (rank 53, start 14, positive_years 4, first_near_zero 2034, tail_share 0.0898).
- Median comp positive-year count: 6.0.

## Root Cause Summary

- Target classification mix: 1 `comp_horizon_gap`, 2 `mixed`.
- The target set does not reduce to one clean shared aggregation mechanism yet, so no methodology change is recommended from this diagnostic pass.

## Recommendation

- `recommend_no_methodology_change_yet`
