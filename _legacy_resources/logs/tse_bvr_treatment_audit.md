# TSE BVR Treatment Audit

## Existing Dataset Grain

- Raw rows: 5109
- Unique municipalities: 2798
- Unique municipality-zone pairs: 2814
- Municipalities with more than one treatment year in the file: 1552

## Municipality-Level Counts

```
 year  new_rows_input_grain  new_municipalities  cumulative_municipalities  official_new  official_cumulative  diff_new_vs_official  diff_cumulative_vs_official
 2008                     3                   3                          3           3.0                  3.0                   0.0                          0.0
 2010                    16                  16                         19          57.0                 60.0                 -41.0                        -41.0
 2012                   299                 280                        299           NaN                  NaN                   NaN                          NaN
 2014                   458                 458                        757           NaN                764.0                   NaN                         -7.0
 2016                  1540                 800                       1557           NaN                  NaN                   NaN                          NaN
 2018                  2793                1241                       2798           NaN                  NaN                   NaN                          NaN
```

## Diagnosis

- The existing file is not a pure municipality-level first-treatment file.
- Many municipalities reappear in later election-use years, so downstream code must collapse to the earliest municipality treatment year.
- Large benchmark gaps should therefore be interpreted after municipality-level collapse, not from raw row counts.
