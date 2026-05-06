# PCA Diagnostics

The PCA uses standardized PT second-round vote shares from 2006, 2010, and 2014. The sign of PC1 is oriented so that higher scores indicate higher PT support.

## Coverage

- Municipalities in the wide 2006-2014 panel: 5,570.
- Municipalities with complete runoff coverage: 5,565.
- Municipalities missing at least one runoff share: 5.

## Loadings

|   year | variable             |   pc1_loading |   standardized_mean |   standardized_sd |
|-------:|:---------------------|--------------:|--------------------:|------------------:|
|   2006 | pt_share_2006_runoff |      0.574014 |            0.618997 |          0.169669 |
|   2010 | pt_share_2010_runoff |      0.582277 |            0.594923 |          0.153884 |
|   2014 | pt_share_2014_runoff |      0.575727 |            0.577453 |          0.18072  |

## Variance Explained

| component   |   eigenvalue |   variance_explained |
|:------------|-------------:|---------------------:|
| PC1         |    2.75539   |            0.918298  |
| PC2         |    0.145748  |            0.0485739 |
| PC3         |    0.0994032 |            0.0331285 |

## Interpretation Checks

All PC1 loadings have the same sign: True.
Sign correction applied: 1 (`-1` means the raw SVD score was flipped).
PC1 variance explained: 0.9183.
Correlation between vote-share-scaled PC1 and simple runoff mean: 0.9999.
Correlations with yearly runoff shares: 2006 = 0.9527, 2010 = 0.9665, 2014 = 0.9556.

For regression comparability with the single-year benchmark, `pc1_score` is the signed PC1 score rescaled to the mean and standard deviation of the simple three-year PT runoff average. The files also retain `pc1_score_raw` and `pc1_score_z` for audit.
