# Strict-vs-Hybrid Analysis Panel

Input panel: `data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.parquet`

Output panel: `resources/regressions/reg_fe_compare/analysis_panel.parquet`
Placebo panel: `resources/regressions/reg_fe_compare/placebo/analysis_panel_placebo.parquet`

## Baseline Denominator

The normalized outcomes divide each municipality-year count by the municipality's total 2006 electorate.

- Input rows: 55,661
- Input municipalities: 5,571
- Municipalities with 2006 baseline: 5,565
- Municipalities excluded because 2006 baseline is missing: 6
- Duplicate 2006 baseline municipality IDs: 0

Excluded municipalities:

| municipality_id | municipality_name | state |
|---|---|---|
| 5006275 | paraiso das aguas | MS |
| 0000nan | boa esperanca do norte | MT |
| 1504752 | mojui dos campos | PA |
| 4314548 | pinto bandeira | RS |
| 4212650 | pescaria brava | SC |
| 4220000 | balneario rincao | SC |

## Treatment Regime Classification

First regime is assigned by comparing `year_first_hybrid_bvr` and `year_first_strict_bvr`. Strict wins finite ties, as specified in the prompt. `year_first_any_bvr` is retained as the canonical first-exposure year.

- Municipalities with non-constant treatment-year fields across rows: 0
- Municipalities where `year_first_any_bvr` differs from `min(strict, hybrid)`: 0
- Finite strict/hybrid treatment-year ties assigned to strict: 0

Municipality counts by first regime:

| first_regime | municipalities |
|---|---|
| hybrid | 1845 |
| never_treated | 1243 |
| strict | 2477 |

Cohort counts by first regime:

| first_regime | year_first_any_bvr | municipalities |
|---|---|---|
| hybrid | 2014 | 2 |
| hybrid | 2016 | 839 |
| hybrid | 2018 | 1004 |
| never_treated | 9999 | 1243 |
| strict | 2008 | 3 |
| strict | 2010 | 57 |
| strict | 2012 | 238 |
| strict | 2014 | 463 |
| strict | 2016 | 779 |
| strict | 2018 | 937 |

Inconsistent first-exposure records:

_None._

## Main Regression Panel

Treated municipalities are restricted to event time -2 and event time 0. Never-treated municipalities keep all years.

- Rows: 21,066
- Municipalities: 5,563
- Strict event-time-0 observations (`D_str_0 == 1`): 2475
- Hybrid event-time-0 observations (`D_hyb_0 == 1`): 1845
- Treated municipalities excluded because the event-time -2/0 pair is incomplete: 2

Observations by first regime:

| first_regime | observations |
|---|---|
| hybrid | 3690 |
| never_treated | 12426 |
| strict | 4950 |

Treated municipalities excluded for an incomplete event-time -2/0 pair:

| municipality_id | first_regime | year_first_any_bvr | main_obs_kept |
|---|---|---|---|
| 2605459 | strict | 2014 | 1 |
| 5300108 | strict | 2014 | 1 |

Treated municipalities without exactly two kept observations after this exclusion:

_None._

Outcome summary statistics in the main regression panel:

| variable | n | mean | sd | min | p25 | median | p75 | max |
|---|---|---|---|---|---|---|---|---|
| norm_2006_voters | 21066 | 1.0903 | 0.1562 | 0.2937 | 1.0000 | 1.0800 | 1.1711 | 2.7876 |
| norm_2006_voters_low_ed | 21066 | 0.7369 | 0.1482 | 0.2066 | 0.6356 | 0.7219 | 0.8292 | 1.6593 |
| norm_2006_voters_high_ed | 21066 | 0.3524 | 0.1562 | 0.0102 | 0.2437 | 0.3468 | 0.4520 | 1.4590 |

## Placebo Panel

For the event-time -4 placebo, treated municipalities are restricted to event time -6 and event time -4. Never-treated municipalities keep all years.

- Rows: 21,066
- Municipalities: 5,563
- Strict placebo observations (`D_str_minus4 == 1`): 2475
- Hybrid placebo observations (`D_hyb_minus4 == 1`): 1845
- Treated municipalities excluded because the event-time -6/-4 pair is incomplete: 2

Treated municipalities excluded for an incomplete event-time -6/-4 pair:

| municipality_id | first_regime | year_first_any_bvr | placebo_obs_kept |
|---|---|---|---|
| 2605459 | strict | 2014 | 1 |
| 5300108 | strict | 2014 | 1 |

Treated municipalities without exactly two kept observations in the placebo panel:

_None._
