# Multi-Race PCA Diagnostics

The PCA uses standardized 2006, 2010, and 2014 values for PT presidential runoff share, federal deputy left-coalition candidate share, and state deputy left-coalition candidate share. The sign is oriented so that higher PC1 means greater left support.

## Coverage

- Municipalities in the integrated panel: 5,570.
- Municipalities with complete 9-variable coverage: 5,564.
- Municipalities missing at least one PCA variable: 6.

## Loadings

| variable                | race      |   year |   pc1_loading |   standardized_mean |   standardized_sd |
|:------------------------|:----------|-------:|--------------:|--------------------:|------------------:|
| pt_share_2006_runoff    | president |   2006 |      0.357942 |            0.619006 |          0.169683 |
| pt_share_2010_runoff    | president |   2010 |      0.38532  |            0.594935 |          0.153895 |
| pt_share_2014_runoff    | president |   2014 |      0.36562  |            0.577488 |          0.180717 |
| left_share_dep_fed_2006 | dep_fed   |   2006 |      0.307174 |            0.245819 |          0.166692 |
| left_share_dep_fed_2010 | dep_fed   |   2010 |      0.326272 |            0.294579 |          0.180607 |
| left_share_dep_fed_2014 | dep_fed   |   2014 |      0.327178 |            0.273869 |          0.176705 |
| left_share_dep_est_2006 | dep_est   |   2006 |      0.278395 |            0.251853 |          0.174564 |
| left_share_dep_est_2010 | dep_est   |   2010 |      0.339454 |            0.308748 |          0.18911  |
| left_share_dep_est_2014 | dep_est   |   2014 |      0.298566 |            0.275401 |          0.181087 |

## Loadings By Race

| race      |     mean |      min |      max |   mean_abs |
|:----------|---------:|---------:|---------:|-----------:|
| dep_est   | 0.305471 | 0.278395 | 0.339454 |   0.305471 |
| dep_fed   | 0.320208 | 0.307174 | 0.327178 |   0.320208 |
| president | 0.369627 | 0.357942 | 0.38532  |   0.369627 |

## Variance Explained

| component   |   eigenvalue |   variance_explained |   cumulative_variance_explained |
|:------------|-------------:|---------------------:|--------------------------------:|
| PC1         |    3.23145   |            0.358985  |                        0.358985 |
| PC2         |    2.43436   |            0.270435  |                        0.62942  |
| PC3         |    0.841819  |            0.0935187 |                        0.722939 |
| PC4         |    0.80879   |            0.0898494 |                        0.812789 |
| PC5         |    0.546469  |            0.0607078 |                        0.873496 |
| PC6         |    0.51169   |            0.0568443 |                        0.930341 |
| PC7         |    0.387705  |            0.0430706 |                        0.973411 |
| PC8         |    0.141744  |            0.0157466 |                        0.989158 |
| PC9         |    0.0975969 |            0.0108422 |                        1        |

## Interpretation Checks

All PC1 loadings have the same sign: True.
Sign correction applied: 1 (`-1` means the raw SVD score was flipped).
PC1 variance explained: 0.3590.
Correlation between simple-mean-scaled PC1 and standardized simple mean: 0.9973.
Mean absolute loading by race: president = 0.3696, federal deputy = 0.3202, state deputy = 0.3055.

The deputy shares are candidate-vote shares from `resultados_candidato_municipio`; party-list votes are not included because the prompt requested this candidate-result table.
