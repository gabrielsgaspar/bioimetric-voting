# Strict-vs-Hybrid Identification Tests

All estimates are shares of the municipality's 2006 baseline electorate.

## Test 1: Hybrid Total Electorate Effect

Hybrid total effect: -0.63% with 95% CI [-0.88%, -0.38%].
The 95% CI does not contain zero, so this test does not support the no-exit-in-hybrid prediction.

## Test 2: Hybrid Education Effects Are Mirror-Image

I test this by estimating the low-plus-high normalized outcome directly, which supplies the correct covariance for `gamma_L_hyb + gamma_H_hyb`.

Hybrid low-plus-high effect: -0.61% with 95% CI [-0.86%, -0.36%].
The 95% CI does not contain zero, so this test does not support the pure re-labeling prediction.

## Test 3: Event-Time -4 Placebo

The placebo compares event time -4 against event time -6 for treated municipalities, retaining all never-treated years.

| outcome_label | term | estimate | se | ci | p |
|---|---|---|---|---|---|
| Total electorate | D_str_minus4 | 0.19% | 0.13% | [-0.06%, 0.43%] | 0.1435 |
| Total electorate | D_hyb_minus4 | -0.04% | 0.12% | [-0.28%, 0.20%] | 0.7531 |
| Low-education voters | D_str_minus4 | 0.40% | 0.09% | [0.22%, 0.57%] | 0.0000 |
| Low-education voters | D_hyb_minus4 | 0.33% | 0.08% | [0.17%, 0.49%] | 0.0001 |
| High-education voters | D_str_minus4 | -0.21% | 0.06% | [-0.33%, -0.10%] | 0.0002 |
| High-education voters | D_hyb_minus4 | -0.36% | 0.06% | [-0.47%, -0.25%] | 0.0000 |

At least one strict-first or hybrid-first placebo confidence interval excludes zero, so this test raises a pre-trend concern.
