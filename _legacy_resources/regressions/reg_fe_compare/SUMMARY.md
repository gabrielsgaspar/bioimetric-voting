# Strict-vs-Hybrid Regression Summary

All coefficients are shares of the municipality's 2006 baseline electorate. Percentages below multiply those shares by 100.

## Sample Summary

- Main analysis panel: 21,066 observations across 5,563 municipalities.
- Municipalities excluded for missing 2006 baseline: 6.
- Additional treated municipalities excluded for incomplete event-window pairs: 2.

Municipalities by first regime in the regression sample:

| first_regime | municipalities |
|---|---|
| hybrid | 1845 |
| never_treated | 1243 |
| strict | 2475 |

Municipalities by cohort and first regime in the regression sample:

| first_regime | year_first_any_bvr | municipalities |
|---|---|---|
| hybrid | 2014 | 2 |
| hybrid | 2016 | 839 |
| hybrid | 2018 | 1004 |
| never_treated | 9999 | 1243 |
| strict | 2008 | 3 |
| strict | 2010 | 57 |
| strict | 2012 | 238 |
| strict | 2014 | 461 |
| strict | 2016 | 779 |
| strict | 2018 | 937 |

## Main Results

| outcome | beta_str | beta_hyb | strict_minus_hybrid |
|---|---|---|---|
| Total electorate | -13.15% [-13.52%, -12.78%] | -0.63% [-0.88%, -0.38%] | -12.51% [-12.88%, -12.14%] |
| Low-education voters | -18.35% [-18.65%, -18.05%] | -0.29% [-0.47%, -0.11%] | -18.06% [-18.37%, -17.75%] |
| High-education voters | 5.29% [5.02%, 5.56%] | -0.32% [-0.53%, -0.12%] | 5.61% [5.33%, 5.89%] |

## Strict-Minus-Hybrid Differences

These differences use the clustered variance-covariance matrix from the same `fixest` model, not the separate JSON standard errors.

| outcome | diff | se | ci | p |
|---|---|---|---|---|
| Total electorate | -12.51% | 0.19% | [-12.88%, -12.14%] | 0.0000 |
| Low-education voters | -18.06% | 0.16% | [-18.37%, -17.75%] | 0.0000 |
| High-education voters | 5.61% | 0.14% | [5.33%, 5.89%] | 0.0000 |

## Identification Tests

| test | estimate | ci | pass |
|---|---|---|---|
| Hybrid total electorate effect is zero | -0.63% | [-0.88%, -0.38%] | no |
| Hybrid low-plus-high education effects sum to zero | -0.61% | [-0.86%, -0.36%] | no |
| Placebo event-time -4 coefficients are zero |  |  | no |

Placebo details are in `identification_tests.md` and `placebo/placebo_results.csv`.

## Implied Decomposition

| quantity | value_ci |
|---|---|
| gamma_N_hyb | -0.63% [-0.88%, -0.38%] |
| gamma_L_hyb | -0.29% [-0.47%, -0.11%] |
| gamma_H_hyb | -0.32% [-0.53%, -0.12%] |
| gamma_N_str | -13.15% [-13.52%, -12.78%] |
| gamma_L_str | -18.35% [-18.65%, -18.05%] |
| gamma_H_str | 5.29% [5.02%, 5.56%] |
| R_hat | -0.32% [-0.53%, -0.12%] |
| E_L_hat | 18.06% [17.75%, 18.37%] |
| E_H_hat | -5.61% [-5.89%, -5.33%] |
| E_total_hat | 12.51% [12.14%, 12.88%] |
| sanity_E_total_minus_E_L_plus_E_H | 0.07% |

Bounded decomposition comparison: `R_hat = -0.32%`; adoption bounds are [5.22%, 17.82%]. In bounds: no.
Sanity check: `E_total_hat - (E_L_hat + E_H_hat) = 0.07%`.

## Interpretation

The strict-vs-hybrid comparison does not deliver the hoped-for re-labeling point estimate. The hybrid-first coefficients are small but negative for total, low-education, and high-education counts, so the maintained interpretation of hybrid BVR as a re-labeling-only counterfactual is not supported in this specification.

The comparison narrows the decomposition only by imposing an assumption that the data do not support here. It produces a negative `R_hat`, outside the bounded interval from the static accounting framework, and the implied `E_H_hat` is negative. Those signs are a warning that hybrid-first municipalities are not behaving like a clean re-labeling-only counterfactual in this two-period specification.

## Caveats

- The interpretation requires re-labeling rates to be comparable in hybrid-first and strict-first municipalities.
- Hybrid-first cohorts are concentrated in 2016 and 2018, with only two hybrid-first municipalities in 2014.
- The hybrid no-exit prediction fails in this sample because the hybrid total-electorate coefficient is small but statistically negative.
- The mirror-image education prediction fails because the hybrid low-plus-high coefficient is negative.
- Any placebo coefficient excluding zero should be treated as a parallel-trends concern before using the strict-minus-hybrid differences as a structural decomposition.
