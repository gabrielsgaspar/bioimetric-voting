# TSE Age-Education DID Notes

## Scope

This note documents the construction of age-band electorate-count outcomes and Callaway-Sant'Anna DID runs for those outcomes.

## Inputs

- Raw official TSE `perfil_eleitorado` zip files under `data/raw/tse_eleitorado/`.
- TSE-to-IBGE municipality crosswalk: `data/raw/ibge/bd-tse_mun_ids.csv`.
- Treatment and status panel: `data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.parquet`.

## Age Data Coverage

The raw TSE age field is usable for 2008, 2010, 2012, 2014, 2016, and 2018. In the 2000-2006 files, the age field is only `#NE`, so those years are not used for the age-band outcomes.

The TSE files report pre-binned age ranges, not exact ages. The requested bands overlap at their boundaries and cannot be recovered exactly from the source bins. This build assigns each whole raw age bin by midpoint, producing non-overlapping analysis bands.

## Age-Bin Mapping

|   raw_age_code | raw_age_label    | assigned_age_band   | assignment_rule                            |
|---------------:|:-----------------|:--------------------|:-------------------------------------------|
|           1600 | 16 anos          | age_16_30           | whole raw TSE age bin assigned by midpoint |
|           1700 | 17 anos          | age_16_30           | whole raw TSE age bin assigned by midpoint |
|           1800 | 18 anos          | age_16_30           | whole raw TSE age bin assigned by midpoint |
|           1900 | 19 anos          | age_16_30           | whole raw TSE age bin assigned by midpoint |
|           2000 | 20 anos          | age_16_30           | whole raw TSE age bin assigned by midpoint |
|           2124 | 21 a 24 anos     | age_16_30           | whole raw TSE age bin assigned by midpoint |
|           2529 | 25 a 29 anos     | age_16_30           | whole raw TSE age bin assigned by midpoint |
|           3034 | 30 a 34 anos     | age_31_45           | whole raw TSE age bin assigned by midpoint |
|           3539 | 35 a 39 anos     | age_31_45           | whole raw TSE age bin assigned by midpoint |
|           4044 | 40 a 44 anos     | age_31_45           | whole raw TSE age bin assigned by midpoint |
|           4549 | 45 a 49 anos     | age_46_60           | whole raw TSE age bin assigned by midpoint |
|           5054 | 50 a 54 anos     | age_46_60           | whole raw TSE age bin assigned by midpoint |
|           5559 | 55 a 59 anos     | age_46_60           | whole raw TSE age bin assigned by midpoint |
|           6064 | 60 a 64 anos     | age_60_plus         | whole raw TSE age bin assigned by midpoint |
|           6569 | 65 a 69 anos     | age_60_plus         | whole raw TSE age bin assigned by midpoint |
|           7074 | 70 a 74 anos     | age_60_plus         | whole raw TSE age bin assigned by midpoint |
|           7579 | 75 a 79 anos     | age_60_plus         | whole raw TSE age bin assigned by midpoint |
|           8084 | 80 a 84 anos     | age_60_plus         | whole raw TSE age bin assigned by midpoint |
|           8589 | 85 a 89 anos     | age_60_plus         | whole raw TSE age bin assigned by midpoint |
|           9094 | 90 a 94 anos     | age_60_plus         | whole raw TSE age bin assigned by midpoint |
|           9599 | 95 a 99 anos     | age_60_plus         | whole raw TSE age bin assigned by midpoint |
|           9999 | 100 anos ou mais | age_60_plus         | whole raw TSE age bin assigned by midpoint |

## Education Groups

- `low_ed`: illiterate, reads and writes, incomplete primary, complete primary.
- `high_ed`: incomplete secondary, complete secondary, incomplete higher, complete higher.
- Unknown education is included in total age-band counts but excluded from the low- and high-education subgroup counts.

## Outputs

- Long age-by-education panel: `data/clean/tse_eleitorado/eleitorado_age_education_bands_2008_2018.csv` and `data/clean/tse_eleitorado/eleitorado_age_education_bands_2008_2018.parquet`.
- Wide DID sample: `data/interim/tse/tse_age_education_bands_did_cs_sample.csv` and `data/interim/tse/tse_age_education_bands_did_cs_sample.parquet`.
- Estimator configs: `resources/regressions/did_cs_age_education/configs/`.
- Estimator outputs: `resources/regressions/did_cs_log_num_voters_<category>/`.
- Combined event-study output: `resources/regressions/did_cs_age_education/event_study_estimates_all.csv`.
- Combined simple ATT output: `resources/regressions/did_cs_age_education/aggregate_simple_all.csv`.

## Municipality Matching

- Direct code-year-state matches: 32369.
- Exact state-name fallback matches: 1015.
- Unmatched raw municipality rows: 516. Unmatched rows are overseas `ZZ` units or otherwise outside the Brazilian municipality panel and are excluded.

## Sample Diagnostics

| metric                                        | outcome                            | value                         |
|:----------------------------------------------|:-----------------------------------|:------------------------------|
| rows                                          | nan                                | 33406                         |
| municipalities                                | nan                                | 5570                          |
| years                                         | nan                                | 2008,2010,2012,2014,2016,2018 |
| rows_with_any_age_data                        | nan                                | 33384                         |
| treated_municipalities_strict_bvr             | nan                                | 2793                          |
| never_treated_municipalities_strict_bvr       | nan                                | 2777                          |
| nonmissing_log_rows                           | log_num_voters_age_16_30           | 33384                         |
| zero_count_rows                               | log_num_voters_age_16_30           | 0                             |
| positive_count_rows                           | log_num_voters_age_16_30           | 33384                         |
| nonmissing_log_rows                           | log_num_voters_age_31_45           | 33384                         |
| zero_count_rows                               | log_num_voters_age_31_45           | 0                             |
| positive_count_rows                           | log_num_voters_age_31_45           | 33384                         |
| nonmissing_log_rows                           | log_num_voters_age_46_60           | 33384                         |
| zero_count_rows                               | log_num_voters_age_46_60           | 0                             |
| positive_count_rows                           | log_num_voters_age_46_60           | 33384                         |
| nonmissing_log_rows                           | log_num_voters_age_60_plus         | 33384                         |
| zero_count_rows                               | log_num_voters_age_60_plus         | 0                             |
| positive_count_rows                           | log_num_voters_age_60_plus         | 33384                         |
| nonmissing_log_rows                           | log_num_voters_high_ed_age_16_30   | 33384                         |
| zero_count_rows                               | log_num_voters_high_ed_age_16_30   | 0                             |
| positive_count_rows                           | log_num_voters_high_ed_age_16_30   | 33384                         |
| nonmissing_log_rows                           | log_num_voters_high_ed_age_31_45   | 33384                         |
| zero_count_rows                               | log_num_voters_high_ed_age_31_45   | 0                             |
| positive_count_rows                           | log_num_voters_high_ed_age_31_45   | 33384                         |
| nonmissing_log_rows                           | log_num_voters_high_ed_age_46_60   | 33384                         |
| zero_count_rows                               | log_num_voters_high_ed_age_46_60   | 0                             |
| positive_count_rows                           | log_num_voters_high_ed_age_46_60   | 33384                         |
| nonmissing_log_rows                           | log_num_voters_high_ed_age_60_plus | 33364                         |
| zero_count_rows                               | log_num_voters_high_ed_age_60_plus | 20                            |
| positive_count_rows                           | log_num_voters_high_ed_age_60_plus | 33364                         |
| nonmissing_log_rows                           | log_num_voters_low_ed_age_16_30    | 33384                         |
| zero_count_rows                               | log_num_voters_low_ed_age_16_30    | 0                             |
| positive_count_rows                           | log_num_voters_low_ed_age_16_30    | 33384                         |
| nonmissing_log_rows                           | log_num_voters_low_ed_age_31_45    | 33384                         |
| zero_count_rows                               | log_num_voters_low_ed_age_31_45    | 0                             |
| positive_count_rows                           | log_num_voters_low_ed_age_31_45    | 33384                         |
| nonmissing_log_rows                           | log_num_voters_low_ed_age_46_60    | 33384                         |
| zero_count_rows                               | log_num_voters_low_ed_age_46_60    | 0                             |
| positive_count_rows                           | log_num_voters_low_ed_age_46_60    | 33384                         |
| nonmissing_log_rows                           | log_num_voters_low_ed_age_60_plus  | 33384                         |
| zero_count_rows                               | log_num_voters_low_ed_age_60_plus  | 0                             |
| positive_count_rows                           | log_num_voters_low_ed_age_60_plus  | 33384                         |
| max_abs_age_total_minus_panel_total           | nan                                | 207.0                         |
| rows_where_age_total_differs_from_panel_total | nan                                | 12324                         |

## DID Specification

Each outcome uses the same Callaway-Sant'Anna specification as `resources/regressions/did_cs_log_num_voters`: strict-BVR first-treatment year (`year_first_strict_bvr`) as the cohort variable, never-treated controls, no covariates, municipality-clustered standard errors, event window from -8 to +8, and reference event time -2 in plots.

## Run Status

Successful estimator runs: 12. Failed estimator runs: 0.

| outcome                            | success   | output_dir                                                      |
|:-----------------------------------|:----------|:----------------------------------------------------------------|
| log_num_voters_age_16_30           | True      | resources/regressions/did_cs_log_num_voters_age_16_30           |
| log_num_voters_age_31_45           | True      | resources/regressions/did_cs_log_num_voters_age_31_45           |
| log_num_voters_age_46_60           | True      | resources/regressions/did_cs_log_num_voters_age_46_60           |
| log_num_voters_age_60_plus         | True      | resources/regressions/did_cs_log_num_voters_age_60_plus         |
| log_num_voters_high_ed_age_16_30   | True      | resources/regressions/did_cs_log_num_voters_high_ed_age_16_30   |
| log_num_voters_high_ed_age_31_45   | True      | resources/regressions/did_cs_log_num_voters_high_ed_age_31_45   |
| log_num_voters_high_ed_age_46_60   | True      | resources/regressions/did_cs_log_num_voters_high_ed_age_46_60   |
| log_num_voters_high_ed_age_60_plus | True      | resources/regressions/did_cs_log_num_voters_high_ed_age_60_plus |
| log_num_voters_low_ed_age_16_30    | True      | resources/regressions/did_cs_log_num_voters_low_ed_age_16_30    |
| log_num_voters_low_ed_age_31_45    | True      | resources/regressions/did_cs_log_num_voters_low_ed_age_31_45    |
| log_num_voters_low_ed_age_46_60    | True      | resources/regressions/did_cs_log_num_voters_low_ed_age_46_60    |
| log_num_voters_low_ed_age_60_plus  | True      | resources/regressions/did_cs_log_num_voters_low_ed_age_60_plus  |
