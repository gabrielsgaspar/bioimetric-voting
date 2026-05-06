# 2006-Normalized Panel Preparation

Input panel: `data/clean/tse/tse_clean_panel_2000_2018.parquet`

Output panel: `resources/decomposition/panel_normalized_2006.parquet`

## Coverage

- Input rows: 55,661
- Input municipalities: 5,571
- Municipalities with a 2006 baseline: 5,565
- Municipalities excluded for missing 2006 baseline: 6
- Excluded municipality IDs: 0000nan, 1504752, 4212650, 4220000, 4314548, 5006275
- Excluded municipality states: MS: 1, MT: 1, PA: 1, RS: 1, SC: 2
- Normalized rows retained: 55,636
- Normalized municipalities retained: 5,565

## Additivity

The unknown-education count is computed as `num_voters - num_voters_low_ed - num_voters_high_ed`.
It is nonnegative in all retained observations.

- Unknown-education minimum count: 0
- Unknown-education maximum count: 18,776
- Unknown-education total over retained municipality-years: 1,576,141
- Maximum additivity residual in random 1,000-observation check: 2.220e-16
- Maximum additivity residual in the full normalized panel: 4.441e-16
