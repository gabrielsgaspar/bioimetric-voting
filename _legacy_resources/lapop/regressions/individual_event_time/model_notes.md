# LAPOP Individual Event-Time Notes

- Generated: 2026-04-24 11:34 UTC
- Input file: `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready_corrected.parquet`
- Treatment timing file: `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`
- Output file: `data/clean/lapop/lapop_brazil_individual_event_time.parquet`

## Design choices

- Sample years use the benchmark `year` variable and are restricted to `2005 <= year <= 2020`.
- The sample is restricted to municipalities observed in every survey wave in that window.
- Respondents younger than 18 are excluded because the exposure proxy follows the requested age-18 adult eligibility rule.
- `first_eligible_year = year - floor(age) + 18`; the benchmark `year` is used as the interview year for consistency with the notebook-style LAPOP panel.
- `T_im = 1` marks respondents who first became adult-eligible after municipal BVR adoption, `T_im = -1` marks adult mixed-cohort respondents who experienced a transition, and `T_im = 0` covers pre-BVR, not-yet-treated, or never-treated exposure histories.
- Event-time dummies are binned to the paper window `[-8, 8]`, with endpoints absorbing earlier/later exposure and event time `-2` omitted.
- All regressions cluster standard errors by municipality-year cell.
- The no-hybrid event-study sample excludes rows with `is_hybrid = 1`; in the balanced-wave sample this exclusion removes no rows.

## Sample support

- All sample respondents: 2,425
- All sample municipalities: 8
- Survey waves: 8 (2006-2020)
- Always-BVR respondents: 28
- Mixed-cohort respondents: 247
- Low-education respondents in the always-BVR cohort: 2
- No-hybrid respondents: 2,425

## Headline coefficients

- Trust ITT (`registered_under_bvr`): 0.235 (0.184), p = 0.206
- Trust triple-difference (`registered_under_bvr x low_ed`): -0.310 (0.219), p = 0.162
- Democracy triple-difference (`registered_under_bvr x low_ed`): 0.358 (0.370), p = 0.337

## Event-study support

| outcome             | sample    |   n_obs |
|:--------------------|:----------|--------:|
| democracy_index_std | all       |    2425 |
| democracy_index_std | no_hybrid |    2425 |
| trust_index_std     | all       |    2425 |
| trust_index_std     | no_hybrid |    2425 |
