# Municipality-Level Decomposition Diagnostic Report (v2)

Generated from the existing v2 parquet outputs in `data/clean/decomposition/`. This report is diagnostic only: it reads saved outputs and does not rerun the decomposition framework or re-estimate any component.

## 0. What Changed

The v1 decomposition treated pre-2014 `pct_bvr` as zero because the cell-level biometric registration counts were not published by TSE for 2008, 2010, and 2012. That source-data coverage limitation caused the b-bound on re-labeling to bind at zero for the 2010 and 2012 treatment cohorts, mechanically eliminating their re-labeling estimates. The v2 correction backfills pre-2014 `pct_bvr` from 2014 values for the same municipality, age cohort, and education cell, and recomputes `num_voters_bvr` accordingly. The original v1 files remain preserved.

The correction leaves aggregate exit unchanged, as expected, because exit depends only on voter counts and survival rates. National exit remains 8.35% of the 2008 treated baseline. The main movement is in re-labeling: Scenario B rises from 3.93% to 4.47%, a change of +0.54pp, or 500,539 additional voters. Scenario C rises from 5.30% to 6.10%, a change of +0.79pp.

The consistency check improves but does not change classification. V1 already classified all three headline metrics as `within_factor_2` and `same_sign`; v2 retains that classification. The Scenario B re-labeling estimate moves closer to the cross-section lower-bound reference of 5.22%: the 2006-rescaled municipality estimate increases from 4.07% to 4.63%. Scenario C also moves closer to its 10.40% reference, increasing from 5.50% to 6.32%. Exit is unchanged at 8.65% after rescaling.

The main downstream implication is favorable for paper use: the corrected estimates no longer mechanically zero out early treated cohorts, and the aggregate re-labeling estimates move toward the cross-section benchmarks without overshooting the upper bound. Remaining concerns are mostly inherited from v1: older-cohort natural progression remains positive for some 50+ cohorts, the exit floor still binds in one working-age cohort, and unbounded Scenario C still exceeds observed cohort totals in some cells before the b-bound is applied. Prompt 06 also flagged that 6.32% of pre-2014 cells lacked a 2014 lookup, although the treated-cohort spot checks show high post-backfill pct-BVR at adoption.

| Metric | v1 | v2 | Δ | Cross-section reference |
| --- | --- | --- | --- | --- |
| National exit count | 7,772,023 | 7,772,023 | 0 | n/a |
| National exit rate (2008 baseline) | 8.35% | 8.35% | +0.00pp | n/a |
| National R_B count | 3,657,637 | 4,158,176 | 500,539 | n/a |
| National R_B rate (2008 baseline) | 3.93% | 4.47% | +0.54pp | 5.22% |
| National R_C count | 4,939,153 | 5,677,995 | 738,842 | n/a |
| National R_C rate (2008 baseline) | 5.30% | 6.10% | +0.79pp | 10.40% |
| 2010-cohort R_B count | 0 | 66,949 | 66,949 | n/a |
| 2012-cohort R_B count | 0 | 433,590 | 433,590 | n/a |
| 2014-cohort R_B count | 1,065,543 | 1,065,543 | 0 | n/a |
| Strict R_B rate (2008 baseline) | 6.83% | 7.93% | +1.10pp | n/a |
| Hybrid R_B rate (2008 baseline) | 1.16% | 1.16% | +0.00pp | n/a |
| Cross-section R_B agreement | within_factor_2 | within_factor_2 | n/a | n/a |
| AL state R_B rate | 0.00% | 6.59% | +6.59pp | n/a |
| SE state R_B rate | 0.00% | 8.99% | +8.99pp | n/a |

## 1. Executive Summary

The v2 municipality-level decomposition produced final adoption-cycle estimates for 4,321 treated municipalities: 2,475 strict-first and 1,846 hybrid-first. Aggregated over all treated municipalities, the Scenario B exit estimate remains 7,772,023 voters, or 8.35% of the treated municipalities' 2008 baseline electorate. The corrected b-bounded Scenario B re-labeling estimate is 4,158,176 voters, or 4.47%; Scenario C gives 5,677,995 voters, or 6.10%. The v2 run therefore changes re-labeling but not exit.

The qualitative consistency check passes in v2 and is tighter than v1 for the re-labeling channel. The cross-section decomposition reports registry contraction around 12.7% of the 2006 baseline, a Scenario B lower-bound re-labeling reference of 5.22%, and a Scenario C reference of 10.40%. The v2 municipality-level estimates are 8.65% for exit, 4.63% for Scenario B re-labeling, and 6.32% for Scenario C re-labeling after rescaling to the 2006 baseline. All three remain `within_factor_2` and `same_sign`; the re-labeling estimates are closer to the cross-section references than in v1.

The most important remaining issues are diagnostic rather than mechanical failures: natural education progression remains above 2% for some 50+ cohorts, including 55 a 59 anos, 60 a 64 anos, 65 a 69 anos; the exit non-negativity floor still binds in more than 30% of cells for 50 a 54 anos; unbounded Scenario C exceeds observed cohort totals in 1,074 cells before bounding; 6.32% of pre-2014 cells had no 2014 lookup for the pct-BVR backfill. The fix resolves the most visible v1 artifact, namely zero re-labeling for the 2010 and 2012 cohorts. It does not resolve concerns inherited from the cohort-aging framework itself, especially the interpretation of older-cohort progression rates and cell-level floor or bound behavior.

## 2. Data Preparation Diagnostics

Note: Unchanged from v1; the data-preparation diagnostics do not depend on pct_bvr corrections except that the v2 panel files carry corrected `pct_bvr`, `pct_bvr_imputed`, and `pct_bvr_source` columns. See Section 8 for the v2 file inventory.

The working data cover election years 2008, 2010, 2012, 2014, 2016, and 2018. The main panel excludes `Inválido` age and unknown education cells and retains only cells with positive voters. The full panel retains the residual age and education categories, also only for positive cells.

### Panel row counts
| panel | rows | municipalities | years |
| --- | --- | --- | --- |
| decomposition_panel_main_v2 | 4,458,083 | 5,570 | 2008, 2010, 2012, 2014, 2016, 2018 |
| decomposition_panel_full_v2 | 4,589,955 | 5,570 | 2008, 2010, 2012, 2014, 2016, 2018 |
| decomposition_residual_report_v2 | 321 | NA | 2008, 2010, 2012, 2014, 2016, 2018 |

### BVR status by year, counted by municipalities
| year | hybrid_bvr | no_bvr | strict_bvr |
| --- | --- | --- | --- |
| 2008 | 0 | 5,560 | 3 |
| 2010 | 0 | 5,507 | 60 |
| 2012 | 0 | 5,270 | 298 |
| 2014 | 2 | 4,806 | 762 |
| 2016 | 840 | 3,187 | 1,541 |
| 2018 | 1,533 | 1,244 | 2,793 |

### First-treatment cohort distribution
| year_first_any_bvr | municipalities |
| --- | --- |
| 2008 | 3 |
| 2010 | 57 |
| 2012 | 238 |
| 2014 | 466 |
| 2016 | 1,619 |
| 2018 | 1,943 |
| 9999 | 1,244 |

### First-regime split among treated municipalities
| first_regime | municipalities | share_of_treated |
| --- | --- | --- |
| hybrid | 1,846 | 42.70% |
| strict | 2,477 | 57.30% |

### `Inválido` voter share by year
| year | invalid_voters | total_voters_full | invalid_share |
| --- | --- | --- | --- |
| 2008 | 6,963 | 128,806,592 | 0.01% |
| 2010 | 6,619 | 135,604,041 | 0.00% |
| 2012 | 5,734 | 138,544,348 | 0.00% |
| 2014 | 4,828 | 142,467,862 | 0.00% |
| 2016 | 3,928 | 144,088,912 | 0.00% |
| 2018 | 2,907 | 146,805,548 | 0.00% |

### `NÃO INFORMADO` education share by year
| year | unknown_education_voters | total_voters_full | unknown_education_share |
| --- | --- | --- | --- |
| 2008 | 163,356 | 128,806,592 | 0.13% |
| 2010 | 152,863 | 135,604,041 | 0.11% |
| 2012 | 137,419 | 138,544,348 | 0.10% |
| 2014 | 115,471 | 142,467,862 | 0.08% |
| 2016 | 90,599 | 144,088,912 | 0.06% |
| 2018 | 56,358 | 146,805,548 | 0.04% |

### Inferred cell sparsity by year
The saved main and full panels do not retain zero-voter cells, so zero-cell sparsity is inferred as the difference between the complete municipality-year × age × education grid and the positive cells saved in `decomposition_panel_full_v2.parquet`.
| year | municipalities | age_categories | education_categories | possible_cells | positive_cells_saved | inferred_zero_cells | inferred_zero_share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2008 | 5,563 | 23 | 9 | 1,151,541 | 751,748 | 399,793 | 34.72% |
| 2010 | 5,567 | 23 | 9 | 1,152,369 | 756,140 | 396,229 | 34.38% |
| 2012 | 5,568 | 23 | 9 | 1,152,576 | 773,294 | 379,282 | 32.91% |
| 2014 | 5,570 | 23 | 9 | 1,152,990 | 765,957 | 387,033 | 33.57% |
| 2016 | 5,568 | 23 | 9 | 1,152,576 | 778,087 | 374,489 | 32.49% |
| 2018 | 5,570 | 23 | 9 | 1,152,990 | 764,729 | 388,261 | 33.67% |

No year has `Inválido` voter share above 1%.
No year has `NÃO INFORMADO` education share above 1%.
The first-regime split is not heavily imbalanced by the <10% rule: the smaller group is 42.70% of treated municipalities.

## 3. Survival Rate Diagnostics

Note: Unchanged from v1; survival-rate estimation depends only on voter counts, not `pct_bvr`.

The survival files contain national, state-level, and municipality-level cohort survival rates. Cohorts 16-19 are inflow-only in the survival table; cohorts 20 and older have estimated survival rates.

### National survival rates by age cohort
| age_cohort | rate_type | sigma_national | n_cycles | total_predicted | total_observed |
| --- | --- | --- | --- | --- | --- |
| 16 anos | inflow_only | NA | 0 | 0 | 0 |
| 17 anos | inflow_only | NA | 0 | 0 | 0 |
| 18 anos | inflow_only | NA | 0 | 0 | 0 |
| 19 anos | inflow_only | NA | 0 | 0 | 0 |
| 20 anos | survival | 1.180 | 20,007 | 9,411,731 | 11,107,301 |
| 21 a 24 anos | survival | 1.019 | 20,007 | 45,207,620 | 46,073,112 |
| 25 a 29 anos | survival | 0.998 | 20,007 | 58,796,301 | 58,664,166 |
| 30 a 34 anos | survival | 1.008 | 20,007 | 57,338,199 | 57,817,148 |
| 35 a 39 anos | survival | 0.996 | 20,007 | 52,428,892 | 52,200,782 |
| 40 a 44 anos | survival | 0.991 | 20,007 | 47,868,953 | 47,423,360 |
| 45 a 49 anos | survival | 1.001 | 20,007 | 44,441,449 | 44,491,365 |
| 50 a 54 anos | survival | 0.997 | 20,007 | 39,907,989 | 39,799,445 |
| 55 a 59 anos | survival | 0.988 | 20,007 | 33,879,392 | 33,472,984 |
| 60 a 64 anos | survival | 0.984 | 20,007 | 27,331,986 | 26,904,463 |
| 65 a 69 anos | survival | 0.955 | 20,007 | 20,896,916 | 19,964,471 |
| 70 a 74 anos | survival | 0.950 | 20,007 | 15,543,979 | 14,771,904 |
| 75 a 79 anos | survival | 0.928 | 20,007 | 11,261,709 | 10,449,265 |
| 80 a 84 anos | survival | 0.910 | 20,007 | 7,964,058 | 7,248,310 |
| 85 a 89 anos | survival | 0.910 | 20,006 | 5,138,859 | 4,675,703 |
| 90 a 94 anos | survival | 0.814 | 19,993 | 2,345,947 | 1,908,524 |
| 95 a 99 anos | survival | 0.616 | 19,625 | 615,754 | 379,300 |
| 100 anos ou mais | survival | 0.621 | 17,194 | 133,542 | 82,870 |

### State-level dispersion for working-age survival rates
| age_cohort | p10_sigma_state | p50_sigma_state | p90_sigma_state | p90_minus_p10 |
| --- | --- | --- | --- | --- |
| 25 a 29 anos | 0.985 | 0.998 | 1.017 | 0.032 |
| 30 a 34 anos | 0.992 | 1.005 | 1.018 | 0.026 |
| 35 a 39 anos | 0.983 | 0.993 | 1.004 | 0.021 |
| 40 a 44 anos | 0.985 | 0.991 | 1.007 | 0.022 |
| 45 a 49 anos | 0.993 | 1.002 | 1.013 | 0.020 |
| 50 a 54 anos | 0.987 | 0.997 | 1.004 | 0.018 |

### Survival fallback source by cohort
| age_cohort | total_cells | municipality_share | state_share | national_share |
| --- | --- | --- | --- | --- |
| 16 anos | 0 | NA | NA | NA |
| 17 anos | 0 | NA | NA | NA |
| 18 anos | 0 | NA | NA | NA |
| 19 anos | 0 | NA | NA | NA |
| 20 anos | 5,570 | 70.22% | 26.48% | 3.30% |
| 21 a 24 anos | 5,570 | 89.26% | 7.49% | 3.25% |
| 25 a 29 anos | 5,570 | 91.89% | 4.87% | 3.25% |
| 30 a 34 anos | 5,570 | 91.35% | 5.40% | 3.25% |
| 35 a 39 anos | 5,570 | 90.65% | 6.10% | 3.25% |
| 40 a 44 anos | 5,570 | 90.34% | 6.39% | 3.27% |
| 45 a 49 anos | 5,570 | 89.96% | 6.75% | 3.29% |
| 50 a 54 anos | 5,570 | 88.26% | 8.42% | 3.32% |
| 55 a 59 anos | 5,570 | 84.27% | 12.35% | 3.38% |
| 60 a 64 anos | 5,570 | 78.29% | 18.26% | 3.45% |
| 65 a 69 anos | 5,570 | 69.64% | 26.75% | 3.61% |
| 70 a 74 anos | 5,570 | 60.59% | 35.67% | 3.73% |
| 75 a 79 anos | 5,570 | 48.69% | 47.41% | 3.90% |
| 80 a 84 anos | 5,570 | 34.74% | 61.29% | 3.97% |
| 85 a 89 anos | 5,570 | 22.15% | 73.79% | 4.06% |
| 90 a 94 anos | 5,570 | 9.86% | 86.05% | 4.09% |
| 95 a 99 anos | 5,570 | 1.22% | 94.63% | 4.15% |
| 100 anos ou mais | 5,570 | 0.16% | 95.69% | 4.15% |

### Inflow rates for cohorts 16-19
| age_cohort | municipalities | national_rate | mean_used | sd_used | p10_used | p50_used | p90_used |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16 anos | 5,570 | 0.59% | 1.06% | 0.53% | 0.42% | 0.99% | 1.81% |
| 17 anos | 5,570 | 1.02% | 1.48% | 0.54% | 0.83% | 1.42% | 2.23% |
| 18 anos | 5,570 | 1.88% | 2.15% | 0.45% | 1.63% | 2.08% | 2.76% |
| 19 anos | 5,570 | 2.15% | 2.28% | 0.41% | 1.80% | 2.22% | 2.83% |

### Pre-treatment cycle counts by first-treatment cohort
| year_first_any_bvr | total_municipalities | municipalities_with_cycles | municipality_cycles | avg_cycles_per_municipality |
| --- | --- | --- | --- | --- |
| 2008 | 3 | 0 | 0 | 0.00 |
| 2010 | 57 | 0 | 0 | 0.00 |
| 2012 | 238 | 238 | 238 | 1.00 |
| 2014 | 466 | 463 | 926 | 1.99 |
| 2016 | 1,619 | 1,619 | 4,856 | 3.00 |
| 2018 | 1,943 | 1,943 | 7,768 | 4.00 |
| 9999 | 1,244 | 1,244 | 6,219 | 5.00 |

No working-age national survival rate is below 0.90. Several working-age rates are near or slightly above 1.0, which suggests that the estimated survival object also absorbs net migration or registration growth, not mortality alone.
No working-age cohort has a state-level 90th-minus-10th percentile sigma gap above 0.15.
No working-age cohort relies on the national fallback for more than 50% of municipality-cohort cells.

## 4. Exit Estimation Diagnostics

Note: Unchanged from v1; exit estimation uses voter counts and survival rates, not `pct_bvr`.

The final aggregate exit estimate is 7,772,023 voters, equal to 8.35% of the treated municipalities' 2008 baseline electorate. This is below the cross-section's 12.7% registry contraction but in the same order of magnitude.

### Treated municipalities in the working panel but absent from final estimates
| ibge_municipality_id | state | year_first_any_bvr | first_regime |
| --- | --- | --- | --- |
| 5300108 | DF | 2014 | strict |
| 2605459 | PE | 2014 | strict |

### Exit by first regime
| first_regime | municipalities | N_2008_total | exit_count | exit_rate_2008 |
| --- | --- | --- | --- | --- |
| hybrid | 1,846 | 47,602,319 | 1,561,570 | 3.28% |
| strict | 2,475 | 45,514,603 | 6,210,453 | 13.64% |

### Exit by first-treatment cohort year
| year_first_any_bvr | municipalities | N_2008_total | exit_count | exit_rate_2008 |
| --- | --- | --- | --- | --- |
| 2010 | 57 | 1,235,328 | 187,720 | 15.20% |
| 2012 | 238 | 6,717,705 | 856,813 | 12.75% |
| 2014 | 464 | 11,669,276 | 1,486,624 | 12.74% |
| 2016 | 1,619 | 37,458,633 | 2,524,410 | 6.74% |
| 2018 | 1,943 | 36,035,980 | 2,716,455 | 7.54% |

### Distribution of municipality-level exit rates
| percentile | exit_rate_2008 |
| --- | --- |
| p10 | 2.42% |
| p25 | 4.23% |
| p50 | 9.26% |
| p75 | 16.10% |
| p90 | 21.65% |
| p95 | 24.97% |

### Cohort-level exit pattern
| age_cohort | baseline_population | exit_count | exit_share_of_baseline | share_of_total_exit | floor_bind_share |
| --- | --- | --- | --- | --- | --- |
| 16 anos | 587,971 | 286,099 | 48.66% | 3.68% | 23.91% |
| 17 anos | 1,042,046 | 256,685 | 24.63% | 3.30% | 30.22% |
| 18 anos | 1,860,861 | 296,497 | 15.93% | 3.81% | 15.92% |
| 19 anos | 2,156,455 | 258,006 | 11.96% | 3.32% | 13.96% |
| 20 anos | 2,295,685 | 77,575 | 3.38% | 1.00% | 35.96% |
| 21 a 24 anos | 9,325,851 | 536,035 | 5.75% | 6.90% | 23.00% |
| 25 a 29 anos | 11,916,182 | 920,537 | 7.73% | 11.84% | 10.67% |
| 30 a 34 anos | 11,892,195 | 880,790 | 7.41% | 11.33% | 13.33% |
| 35 a 39 anos | 10,787,825 | 517,238 | 4.79% | 6.66% | 29.67% |
| 40 a 44 anos | 9,559,730 | 549,993 | 5.75% | 7.08% | 18.42% |
| 45 a 49 anos | 8,941,228 | 507,544 | 5.68% | 6.53% | 14.46% |
| 50 a 54 anos | 8,159,614 | 274,291 | 3.36% | 3.53% | 31.87% |
| 55 a 59 anos | 6,832,621 | 246,398 | 3.61% | 3.17% | 27.38% |
| 60 a 64 anos | 5,549,544 | 198,898 | 3.58% | 2.56% | 25.78% |
| 65 a 69 anos | 4,187,579 | 149,870 | 3.58% | 1.93% | 38.02% |
| 70 a 74 anos | 3,055,656 | 371,220 | 12.15% | 4.78% | 19.53% |
| 75 a 79 anos | 2,200,386 | 386,030 | 17.54% | 4.97% | 29.58% |
| 80 a 84 anos | 1,484,253 | 405,023 | 27.29% | 5.21% | 21.57% |
| 85 a 89 anos | 998,822 | 395,401 | 39.59% | 5.09% | 13.96% |
| 90 a 94 anos | 523,150 | 187,763 | 35.89% | 2.42% | 28.77% |
| 95 a 99 anos | 94,054 | 51,744 | 55.02% | 0.67% | 35.94% |
| 100 anos ou mais | 21,671 | 18,384 | 84.83% | 0.24% | 19.14% |

### Hybrid municipality exit-rate distribution
| percentile | hybrid_exit_rate_2008 |
| --- | --- |
| p10 | 1.67% |
| p25 | 2.57% |
| p50 | 3.93% |
| p75 | 6.21% |
| p90 | 8.64% |
| p95 | 10.58% |

National aggregate exit does not exceed the 20% over-attribution threshold.
Hybrid aggregate exit is 3.28%, below the 5% diagnostic threshold and much smaller than strict-first exit.
**flagged: floor-binding exceeds 30% in working-age cohorts 50 a 54 anos.** This means observed counts exceeded predicted counts frequently enough that the exit floor is doing material work in these cohorts.

## 5. Re-labeling Diagnostics

The v2 b-bounded Scenario B re-labeling estimate is 4,158,176 voters, or 4.47% of the treated municipalities' 2008 baseline. Scenario C gives 5,677,995 voters, or 6.10%. Relative to v1, Scenario B increases by 500,539 voters and +0.54pp; Scenario C increases by 738,842 voters and +0.79pp.

### Raw versus b-bounded re-labeling
| estimate | count | rate_2008 |
| --- | --- | --- |
| Scenario B re-labeling, unbounded | 4,169,556 | 4.48% |
| Scenario B re-labeling, b-bounded/final | 4,158,176 | 4.47% |
| Scenario C re-labeling, unbounded | 5,695,816 | 6.12% |
| Scenario C re-labeling, b-bounded/final | 5,677,995 | 6.10% |

### Distribution of municipality-level Scenario B re-labeling rates
| percentile | R_B_rate_2008 |
| --- | --- |
| p10 | 0.60% |
| p25 | 1.13% |
| p50 | 3.26% |
| p75 | 6.96% |
| p90 | 10.13% |
| p95 | 11.75% |

### Cohort-level re-labeling pattern
| age_cohort | R_B_bounded | R_C_bounded | R_B_rate_observed | R_C_rate_observed | share_of_total_R_B | B_bound_bind_share | C_bound_bind_share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16 anos | 898 | 5,915 | 0.19% | 1.22% | 0.02% | 0.02% | 0.35% |
| 17 anos | 2,880 | 11,478 | 0.28% | 1.13% | 0.07% | 0.02% | 0.28% |
| 18 anos | 24,094 | 58,287 | 1.34% | 3.25% | 0.58% | 0.05% | 0.16% |
| 19 anos | 33,790 | 78,687 | 1.64% | 3.81% | 0.81% | 0.07% | 0.39% |
| 20 anos | 71,679 | 99,773 | 3.30% | 4.59% | 1.72% | 2.34% | 4.17% |
| 21 a 24 anos | 248,503 | 448,762 | 2.82% | 5.09% | 5.98% | 1.53% | 2.20% |
| 25 a 29 anos | 441,290 | 687,070 | 4.03% | 6.28% | 10.61% | 0.76% | 1.71% |
| 30 a 34 anos | 694,836 | 937,685 | 6.21% | 8.38% | 16.71% | 1.50% | 2.34% |
| 35 a 39 anos | 934,235 | 1,101,119 | 8.67% | 10.22% | 22.47% | 3.17% | 3.75% |
| 40 a 44 anos | 745,420 | 911,353 | 7.88% | 9.64% | 17.93% | 2.06% | 2.85% |
| 45 a 49 anos | 430,715 | 569,926 | 4.92% | 6.51% | 10.36% | 0.58% | 0.95% |
| 50 a 54 anos | 231,963 | 294,815 | 2.82% | 3.58% | 5.58% | 0.09% | 0.16% |
| 55 a 59 anos | 134,740 | 184,927 | 1.91% | 2.62% | 3.24% | 0.23% | 0.37% |
| 60 a 64 anos | 84,163 | 114,109 | 1.45% | 1.96% | 2.02% | 0.51% | 0.67% |
| 65 a 69 anos | 49,305 | 67,040 | 1.11% | 1.51% | 1.19% | 1.00% | 1.09% |
| 70 a 74 anos | 18,491 | 56,199 | 0.62% | 1.88% | 0.44% | 2.01% | 2.38% |
| 75 a 79 anos | 6,507 | 26,574 | 0.33% | 1.33% | 0.16% | 2.55% | 2.80% |
| 80 a 84 anos | 2,487 | 12,479 | 0.20% | 1.02% | 0.06% | 3.49% | 3.91% |
| 85 a 89 anos | 1,595 | 7,832 | 0.22% | 1.10% | 0.04% | 5.09% | 6.20% |
| 90 a 94 anos | 457 | 3,061 | 0.11% | 0.70% | 0.01% | 4.28% | 5.46% |
| 95 a 99 anos | 100 | 783 | 0.07% | 0.54% | 0.00% | 1.90% | 8.24% |
| 100 anos ou mais | 27 | 122 | 0.13% | 0.58% | 0.00% | 1.81% | 21.18% |

Under Scenario B, 63.49% of aggregate bounded re-labeling comes from cohorts 35+ and 36.51% comes from cohorts below 35. The cleanest part of the identification therefore remains quantitatively important, although younger and middle cohorts still contribute a large share of the total.

### Natural progression rates
| age_cohort | delta_national | median_delta_used | p10_delta_used | p90_delta_used |
| --- | --- | --- | --- | --- |
| 16 anos | 5.68% | 5.21% | 1.15% | 8.71% |
| 17 anos | 4.84% | 4.84% | 1.74% | 9.25% |
| 18 anos | 3.21% | 3.34% | 1.22% | 7.51% |
| 19 anos | 3.01% | 3.42% | 1.31% | 7.29% |
| 20 anos | 3.82% | 4.16% | 1.49% | 9.04% |
| 21 a 24 anos | 3.80% | 4.77% | 1.88% | 8.30% |
| 25 a 29 anos | 5.26% | 5.84% | 3.86% | 8.29% |
| 30 a 34 anos | 6.01% | 5.84% | 2.46% | 8.67% |
| 35 a 39 anos | 4.43% | 3.42% | 0.98% | 6.47% |
| 40 a 44 anos | 2.14% | 1.41% | -0.11% | 3.62% |
| 45 a 49 anos | 1.27% | 0.95% | -0.31% | 2.47% |
| 50 a 54 anos | 1.88% | 1.41% | 0.35% | 2.72% |
| 55 a 59 anos | 2.30% | 1.65% | 0.57% | 2.90% |
| 60 a 64 anos | 2.36% | 1.60% | 0.44% | 2.86% |
| 65 a 69 anos | 2.17% | 1.29% | 0.24% | 2.47% |
| 70 a 74 anos | 1.50% | 0.87% | 0.03% | 1.92% |
| 75 a 79 anos | 0.96% | 0.73% | -0.01% | 1.29% |
| 80 a 84 anos | 0.70% | 0.52% | -0.04% | 0.97% |
| 85 a 89 anos | 0.29% | 0.24% | -0.02% | 0.61% |
| 90 a 94 anos | -0.91% | -0.91% | -1.55% | -0.20% |
| 95 a 99 anos | -3.57% | -3.57% | -3.57% | -3.57% |
| 100 anos ou mais | -1.36% | -1.36% | -1.36% | -1.36% |

Natural progression rates are unchanged from v1 up to numerical precision, as expected, because progression estimation uses voter counts rather than `pct_bvr`.

### b-bound binding by first regime
| first_regime | cells | B_bound_bind_share | C_bound_bind_share | mean_b_uptake |
| --- | --- | --- | --- | --- |
| hybrid | 40,612 | 3.73% | 5.49% | 24.00% |
| strict | 54,450 | 0.00% | 1.59% | 94.60% |

### b-bound binding by cohort and first regime
| age_cohort | hybrid_B | strict_B | hybrid_C | strict_C | hybrid_b | strict_b |
| --- | --- | --- | --- | --- | --- | --- |
| 16 anos | 0.05% | 0.00% | 0.81% | 0.00% | 96.99% | 99.23% |
| 17 anos | 0.05% | 0.00% | 0.65% | 0.00% | 88.46% | 99.58% |
| 18 anos | 0.11% | 0.00% | 0.38% | 0.00% | 56.41% | 99.72% |
| 19 anos | 0.16% | 0.00% | 0.92% | 0.00% | 40.67% | 99.63% |
| 20 anos | 5.47% | 0.00% | 9.75% | 0.00% | 23.67% | 99.54% |
| 21 a 24 anos | 3.58% | 0.00% | 5.15% | 0.00% | 16.85% | 99.83% |
| 25 a 29 anos | 1.79% | 0.00% | 4.01% | 0.00% | 15.45% | 99.86% |
| 30 a 34 anos | 3.52% | 0.00% | 5.47% | 0.00% | 16.00% | 99.84% |
| 35 a 39 anos | 7.42% | 0.00% | 8.78% | 0.00% | 17.02% | 99.85% |
| 40 a 44 anos | 4.82% | 0.00% | 6.66% | 0.00% | 17.83% | 99.87% |
| 45 a 49 anos | 1.35% | 0.00% | 2.22% | 0.00% | 18.42% | 99.86% |
| 50 a 54 anos | 0.22% | 0.00% | 0.38% | 0.00% | 19.28% | 99.87% |
| 55 a 59 anos | 0.54% | 0.00% | 0.87% | 0.00% | 20.71% | 99.87% |
| 60 a 64 anos | 1.19% | 0.00% | 1.57% | 0.00% | 21.21% | 99.86% |
| 65 a 69 anos | 2.33% | 0.00% | 2.55% | 0.00% | 20.05% | 99.80% |
| 70 a 74 anos | 4.71% | 0.00% | 5.58% | 0.00% | 14.81% | 99.75% |
| 75 a 79 anos | 5.96% | 0.00% | 6.55% | 0.00% | 10.20% | 99.50% |
| 80 a 84 anos | 8.18% | 0.00% | 9.15% | 0.00% | 6.51% | 99.06% |
| 85 a 89 anos | 11.92% | 0.00% | 14.52% | 0.00% | 3.79% | 98.09% |
| 90 a 94 anos | 10.02% | 0.00% | 11.32% | 1.09% | 1.89% | 90.40% |
| 95 a 99 anos | 4.39% | 0.04% | 5.90% | 9.98% | 1.08% | 64.50% |
| 100 anos ou mais | 4.23% | 0.00% | 17.55% | 23.88% | 0.65% | 33.61% |

### Municipalities with Scenario B re-labeling above 30% of baseline
Count: 0 municipalities.
None.

**flagged: Scenario B re-labeling (4.47% of 2008 baseline; 4.63% rescaled) remains below the cross-section lower bound of 5.22%, though it is closer than v1.**
**flagged: national natural progression delta is above 2% for 50+ cohorts 55 a 59 anos, 60 a 64 anos, 65 a 69 anos.** This is unchanged from v1 and suggests pre-treatment record updating or composition shifts in older cohorts.
Compared with v1, the fix resolves the pct-BVR artifact for early cohorts: 2010-cohort re-labeling is no longer mechanically zero, 2012-cohort re-labeling is no longer mechanically zero. It also resolves the strict-first Scenario B b-bound flag: strict-first B binding falls from 5.51% in v1 to 0.00% in v2. The older-cohort progression flag remains.

## 6. Aggregation and Consistency Check

The v2 aggregation files report b-bounded re-labeling estimates using corrected `pct_bvr`. Exit remains unchanged because the v2 rerun reused the v1 survival and exit outputs by design.

### Final aggregate headline numbers
| aggregation_level | n_municipalities | national_2008_baseline | national_t_post_observed | national_exit_count | national_R_B_count | national_R_C_count | national_exit_rate_2008 | national_R_B_rate_2008 | national_R_C_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strict | 2,475 | 45,514,603 | 46,781,648 | 6,210,453 | 3,607,795 | 4,958,520 | 13.64% | 7.93% | 10.89% |
| hybrid | 1,846 | 47,602,319 | 53,766,096 | 1,561,570 | 550,381 | 719,475 | 3.28% | 1.16% | 1.51% |
| all_treated | 4,321 | 93,116,922 | 100,547,744 | 7,772,023 | 4,158,176 | 5,677,995 | 8.35% | 4.47% | 6.10% |

### Scenario exit allocation implied by the saved outputs
| scenario | low_ed_exit_count | high_ed_exit_count | low_ed_exit_rate_2008 | high_ed_exit_rate_2008 | total_exit_rate_2008 |
| --- | --- | --- | --- | --- | --- |
| B: no high-ed exit | 7,772,023 | 0 | 8.35% | 0.00% | 8.35% |
| C: proportional exit | 4,826,564 | 2,945,459 | 5.18% | 3.16% | 8.35% |

### Cross-section comparison
| metric | cross_section_value | muni_level_value_t_post_baseline | muni_level_value_2008_baseline | muni_level_value_rescaled_to_2006 | agreement_qualitative | agreement_directional |
| --- | --- | --- | --- | --- | --- | --- |
| exit_scenario_B | 12.60% | 7.73% | 8.35% | 8.65% | within_factor_2 | same_sign |
| R_B_lower_bound | 5.22% | 4.14% | 4.47% | 4.63% | within_factor_2 | same_sign |
| R_C_scenario_C | 10.40% | 5.65% | 6.10% | 6.32% | within_factor_2 | same_sign |

Direction agreement is positive for all three metrics in the v2 consistency file. Magnitude agreement remains `within_factor_2` for all three metrics. The classification does not change from v1, but the re-labeling estimates move closer to their cross-section references.

### Cohort-by-cohort share of total exit
| age_cohort | exit_count | share_of_total_exit | exit_share_of_baseline |
| --- | --- | --- | --- |
| 16 anos | 286,099 | 3.68% | 48.66% |
| 17 anos | 256,685 | 3.30% | 24.63% |
| 18 anos | 296,497 | 3.81% | 15.93% |
| 19 anos | 258,006 | 3.32% | 11.96% |
| 20 anos | 77,575 | 1.00% | 3.38% |
| 21 a 24 anos | 536,035 | 6.90% | 5.75% |
| 25 a 29 anos | 920,537 | 11.84% | 7.73% |
| 30 a 34 anos | 880,790 | 11.33% | 7.41% |
| 35 a 39 anos | 517,238 | 6.66% | 4.79% |
| 40 a 44 anos | 549,993 | 7.08% | 5.75% |
| 45 a 49 anos | 507,544 | 6.53% | 5.68% |
| 50 a 54 anos | 274,291 | 3.53% | 3.36% |
| 55 a 59 anos | 246,398 | 3.17% | 3.61% |
| 60 a 64 anos | 198,898 | 2.56% | 3.58% |
| 65 a 69 anos | 149,870 | 1.93% | 3.58% |
| 70 a 74 anos | 371,220 | 4.78% | 12.15% |
| 75 a 79 anos | 386,030 | 4.97% | 17.54% |
| 80 a 84 anos | 405,023 | 5.21% | 27.29% |
| 85 a 89 anos | 395,401 | 5.09% | 39.59% |
| 90 a 94 anos | 187,763 | 2.42% | 35.89% |
| 95 a 99 anos | 51,744 | 0.67% | 55.02% |
| 100 anos ou mais | 18,384 | 0.24% | 84.83% |

The cohort-by-cohort exit allocation is unchanged from v1 because Prompt 07 did not rerun exit. The age decomposition remains model-implied and should be interpreted with the same survival-rate caveats documented in v1.

### Quantitative change in consistency gaps
| metric | v1_rescaled | v2_rescaled | cross_section | v1_factor_gap | v2_factor_gap | gap_change |
| --- | --- | --- | --- | --- | --- | --- |
| exit_scenario_B | 8.65% | 8.65% | 12.60% | 1.46 | 1.46 | 0.00 |
| R_B_lower_bound | 4.07% | 4.63% | 5.22% | 1.28 | 1.13 | -0.15 |
| R_C_scenario_C | 5.50% | 6.32% | 10.40% | 1.89 | 1.65 | -0.25 |

The exit gap is unchanged. Scenario B re-labeling tightens materially: the factor gap to the 5.22% cross-section reference improves from 1.28 to 1.13. Scenario C also tightens, improving from 1.89 to 1.65. The v2 consistency check is therefore not a new categorical pass, but it is a cleaner pass for the re-labeling channel.

## 7. Heterogeneity Across Municipalities

Exit-related heterogeneity is unchanged from v1; re-labeling-related heterogeneity is updated with v2 values. Tables below report exit and Scenario B re-labeling side by side where useful, with exit identical to v1 and R_B from the corrected v2 outputs.

### Top 5 states by exit rate
| state | municipalities | N_2008_total | exit_count | exit_rate_2008 |
| --- | --- | --- | --- | --- |
| AL | 102 | 1,974,873 | 317,688 | 16.09% |
| MA | 145 | 3,415,585 | 546,493 | 16.00% |
| ES | 38 | 983,732 | 147,326 | 14.98% |
| PE | 129 | 4,681,148 | 681,651 | 14.56% |
| PI | 224 | 2,183,294 | 305,152 | 13.98% |

### Bottom 5 states by exit rate
| state | municipalities | N_2008_total | exit_count | exit_rate_2008 |
| --- | --- | --- | --- | --- |
| MG | 731 | 12,824,255 | 479,047 | 3.74% |
| RJ | 92 | 11,228,591 | 436,976 | 3.89% |
| BA | 417 | 9,135,992 | 472,144 | 5.17% |
| SC | 294 | 4,354,622 | 231,451 | 5.32% |
| AC | 18 | 419,964 | 22,725 | 5.41% |

### Top 5 states by Scenario B re-labeling rate (v2)
| state | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| AM | 10 | 1,260,683 | 116,505 | 232,615 | 9.24% | 18.45% |
| AP | 16 | 384,703 | 31,819 | 54,444 | 8.27% | 14.15% |
| RR | 15 | 247,757 | 18,708 | 31,615 | 7.55% | 12.76% |
| PA | 54 | 2,430,017 | 261,259 | 286,913 | 10.75% | 11.81% |
| PI | 224 | 2,183,294 | 305,152 | 229,132 | 13.98% | 10.49% |

### Bottom 5 states by Scenario B re-labeling rate (v2)
| state | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| RJ | 92 | 11,228,591 | 436,976 | 95,981 | 3.89% | 0.85% |
| BA | 417 | 9,135,992 | 472,144 | 130,482 | 5.17% | 1.43% |
| MG | 731 | 12,824,255 | 479,047 | 193,592 | 3.74% | 1.51% |
| RS | 497 | 7,921,995 | 506,010 | 127,622 | 6.39% | 1.61% |
| MT | 43 | 1,273,755 | 93,867 | 36,153 | 7.37% | 2.84% |

### Heterogeneity by first-treatment cohort year
| year_first_any_bvr | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| 2010 | 57 | 1,235,328 | 187,720 | 66,949 | 15.20% | 5.42% |
| 2012 | 238 | 6,717,705 | 856,813 | 433,590 | 12.75% | 6.45% |
| 2014 | 464 | 11,669,276 | 1,486,624 | 1,065,543 | 12.74% | 9.13% |
| 2016 | 1,619 | 37,458,633 | 2,524,410 | 1,383,790 | 6.74% | 3.69% |
| 2018 | 1,943 | 36,035,980 | 2,716,455 | 1,208,304 | 7.54% | 3.35% |

### Heterogeneity by first regime
| first_regime | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid | 1,846 | 47,602,319 | 1,561,570 | 550,381 | 3.28% | 1.16% |
| strict | 2,475 | 45,514,603 | 6,210,453 | 3,607,795 | 13.64% | 7.93% |

### Heterogeneity by population-size decile
D1 is the smallest decile by 2008 baseline electorate; D10 is the largest.
| size_decile | municipalities | min_N_2008 | max_N_2008 | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | 433 | 943 | 2,595 | 886,144 | 124,630 | 39,911 | 14.06% | 4.50% |
| D2 | 432 | 2,596 | 3,491 | 1,317,189 | 180,326 | 58,966 | 13.69% | 4.48% |
| D3 | 433 | 3,495 | 4,491 | 1,712,426 | 209,479 | 78,143 | 12.23% | 4.56% |
| D4 | 431 | 4,492 | 5,775 | 2,180,941 | 252,032 | 101,334 | 11.56% | 4.65% |
| D5 | 432 | 5,776 | 7,395 | 2,824,170 | 294,996 | 114,399 | 10.45% | 4.05% |
| D6 | 432 | 7,398 | 9,841 | 3,704,424 | 380,798 | 150,530 | 10.28% | 4.06% |
| D7 | 432 | 9,846 | 13,251 | 4,899,939 | 465,045 | 212,130 | 9.49% | 4.33% |
| D8 | 432 | 13,261 | 18,925 | 6,756,199 | 678,034 | 286,468 | 10.04% | 4.24% |
| D9 | 432 | 18,937 | 34,175 | 10,653,011 | 1,006,407 | 493,554 | 9.45% | 4.63% |
| D10 | 432 | 34,225 | 4,566,338 | 58,182,479 | 4,180,276 | 2,622,741 | 7.18% | 4.51% |

### Regional aggregates
| region | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| Center-West | 298 | 5,737,073 | 650,395 | 324,956 | 11.34% | 5.66% |
| Northeast | 1,657 | 33,036,912 | 3,529,136 | 1,976,959 | 10.68% | 5.98% |
| North | 287 | 6,479,228 | 611,900 | 815,830 | 9.44% | 12.59% |
| South | 1,097 | 18,767,274 | 1,498,433 | 583,223 | 7.98% | 3.11% |
| Southeast | 982 | 29,096,435 | 1,482,158 | 457,208 | 5.09% | 1.57% |

The municipality-level Pearson correlation between exit rate and Scenario B re-labeling rate is 0.273; the Spearman rank correlation is 0.441. This is recomputed using v2 R_B values. By regime, the correlations are:
| first_regime | pearson | spearman |
| --- | --- | --- |
| hybrid | 0.028 | 0.009 |
| strict | -0.306 | -0.280 |

The v2 correction mainly changes early strict-treated places and states whose v1 re-labeling was mechanically zero. AL and SE move from 0.00% R_B rates in v1 to positive rates in v2, which is visible in the state-level heterogeneity table and the v1-to-v2 comparison. Spatially, the map-ready v2 files should better represent early BVR states because the backfilled b-bound no longer suppresses their re-labeling estimates.

## 8. Files Inventory

The v1 files listed in `PROMPT_REPORT.md` are preserved alongside the v2 outputs. This section lists the new v2 outputs and the two scripts added for the backfill and rerun.

### v2 decomposition parquet outputs
| file | rows | columns | description |
| --- | --- | --- | --- |
| data/clean/decomposition/decomposition_data_v2.parquet | 4,589,955 | year, ibge_municipality_id, state, bvr_status, year_first_any_bvr, year_first_strict_bvr, year_first_hybrid_bvr, age_cohort, education, low_ed, high_ed, num_voters, num_voters_bvr, pct_bvr, pct_bvr_imputed, pct_bvr_source | Corrected source data with pre-2014 pct_bvr and num_voters_bvr backfilled from 2014 cell values, plus imputation flags. |
| data/clean/decomposition/decomposition_pct_bvr_backfill_audit.parquet | 6 | year, n_cells_total, n_cells_observed, n_cells_imputed_from_2014, n_cells_no_match_kept_zero, mean_pct_bvr_before, mean_pct_bvr_after | Audit of pct_bvr backfill counts and before/after means by year. |
| data/clean/decomposition/decomposition_panel_main_v2.parquet | 4,458,083 | ibge_municipality_id, state, year, age_cohort, education, low_ed, high_ed, num_voters, num_voters_bvr, pct_bvr, pct_bvr_imputed, pct_bvr_source, bvr_status, year_first_any_bvr, year_first_strict_bvr, year_first_hybrid_bvr, first_regime, event_time | Main v2 working panel; positive voter cells only; excludes Inválido age and unknown education; carries pct_bvr imputation flags. |
| data/clean/decomposition/decomposition_panel_full_v2.parquet | 4,589,955 | ibge_municipality_id, state, year, age_cohort, education, low_ed, high_ed, num_voters, num_voters_bvr, pct_bvr, pct_bvr_imputed, pct_bvr_source, bvr_status, year_first_any_bvr, year_first_strict_bvr, year_first_hybrid_bvr, first_regime, event_time | Full v2 positive-cell age-by-education panel retaining residual categories and pct_bvr imputation flags. |
| data/clean/decomposition/decomposition_residual_report_v2.parquet | 321 | year, state, first_regime, total_voters_full, total_voters_excluded, excluded_share | v2 excluded residual voter shares by year, state, and first regime. |
| data/clean/decomposition/decomposition_progression_rates_v2.parquet | 122,540 | ibge_municipality_id, state, age_cohort, delta_municipality, delta_state, delta_national, delta_used, n_cycles_used, n_cycles_state, n_cycles_national, municipality_threshold_met, state_threshold_met, rate_source | v2 natural low-education share progression rates by municipality and cohort. |
| data/clean/decomposition/decomposition_prediction_education_v2.parquet | 95,062 | ibge_municipality_id, state, t, t_post, age_cohort, N_low_observed_t, N_high_observed_t, N_low_predicted_t_post, N_high_predicted_t_post, N_low_observed_t_post, N_high_observed_t_post, N_predicted_total, exit_count, pi_low_t, pi_low_predicted_t_post, pi_low_observed_t_post, delta_used, N_observed_total, b_uptake, pi_low_t_source, rate_source, pct_bvr_imputed_any, pct_bvr_imputed_voter_share, pct_bvr_source | v2 predicted no-BVR low/high education counts by cohort at adoption with pct_bvr imputation flags. |
| data/clean/decomposition/decomposition_relabel_cohort_v2.parquet | 95,062 | ibge_municipality_id, state, t, t_post, age_cohort, year_first_any_bvr, first_regime, R_B_raw, R_B_bounded, R_C_raw, R_C_bounded, R_max_b, b_uptake, bound_binds_B, bound_binds_C, exit_count, N_predicted_total, N_observed_total, R_B_unfloored, R_C_unfloored, pct_bvr_imputed_any, pct_bvr_imputed_voter_share, pct_bvr_source | v2 cohort-level Scenario B/C re-labeling estimates, b-bounds, binding flags, and pct_bvr imputation flags. |
| data/clean/decomposition/decomposition_relabel_municipality_v2.parquet | 4,321 | ibge_municipality_id, state, t_post, year_first_any_bvr, first_regime, R_B_total, R_C_total, R_rate_B_total, R_rate_C_total, R_B_younger, R_B_older, R_C_younger, R_C_older, N_observed_total, n_cohorts_with_relabel, n_cohorts_bound_binds_B, n_cohorts_bound_binds_C, n_cohorts_pct_bvr_imputed, pct_bvr_imputed_voter_share | v2 municipality-level bounded Scenario B/C re-labeling totals. |
| data/clean/decomposition/decomposition_final_municipality_v2.parquet | 4,321 | ibge_municipality_id, state, t_post, year_first_any_bvr, first_regime, N_2008_total, baseline_year_used, baseline_is_exact_2008, total_predicted, total_observed, exit_count, R_B_count, R_C_count, exit_rate_t_post, R_B_rate_t_post, R_C_rate_t_post, exit_rate_2008, R_B_rate_2008, R_C_rate_2008, n_cohorts_with_exit, n_cohorts_bound_binds_B, n_cohorts_bound_binds_C | v2 final municipality-level exit and re-labeling table with 2008 baseline rates. |
| data/clean/decomposition/decomposition_final_aggregate_v2.parquet | 3 | aggregation_level, n_municipalities, national_2008_baseline, national_t_post_observed, national_exit_count, national_R_B_count, national_R_C_count, national_exit_rate_2008, national_R_B_rate_2008, national_R_C_rate_2008, national_exit_rate_t_post, national_R_B_rate_t_post, national_R_C_rate_t_post | v2 aggregate national rates by first regime and all treated municipalities. |
| data/clean/decomposition/decomposition_final_by_cohort_v2.parquet | 8 | year_first_any_bvr, first_regime, n_municipalities, exit_count, R_B_count, R_C_count, exit_rate_2008, R_B_rate_2008, R_C_rate_2008, average_b_uptake | v2 aggregate decomposition by adoption cohort year and first regime. |
| data/clean/decomposition/decomposition_consistency_check_v2.parquet | 3 | metric, cross_section_value, muni_level_value_t_post_baseline, muni_level_value_2008_baseline, muni_level_value_rescaled_to_2006, agreement_qualitative, agreement_directional | v2 cross-section versus municipality-level consistency metrics. |
| data/clean/decomposition/decomposition_map_counts_v2.parquet | 4,321 | ibge_municipality_id, state, first_regime, year_first_any_bvr, exit_count, R_B_count, R_C_count, total_decomposition_count_B, total_decomposition_count_C | v2 map-ready municipality count variables for spatial visualization. |
| data/clean/decomposition/decomposition_map_rates_v2.parquet | 4,321 | ibge_municipality_id, state, first_regime, year_first_any_bvr, exit_rate_2008, R_B_rate_2008, R_C_rate_2008, total_decomposition_rate_B, total_decomposition_rate_C | v2 map-ready municipality rate variables for spatial visualization. |
| data/clean/decomposition/decomposition_v1_vs_v2_comparison.parquet | 24 | section, group, metric, v1, v2, delta, cross_section | Side-by-side v1 versus v2 comparison of headline, cohort, state, and consistency metrics. |

### New v2 scripts
| file | description |
| --- | --- |
| src/decomposition/06_backfill_pct_bvr.py | Creates corrected source `decomposition_data_v2.parquet` by backfilling pre-2014 pct_bvr and num_voters_bvr from 2014 cell values. |
| src/decomposition/07_rerun_with_v2.py | Rebuilds affected Prompt 1, 4, and 5 outputs with `_v2` suffixes while reusing v1 survival and exit outputs. |

### Consolidated v2 flags
- **flagged:** Scenario B re-labeling is 4.47% of the 2008 baseline, below the cross-section lower bound of 5.22%, though closer than v1.
- **flagged:** National natural progression delta is above 2% for 50+ cohorts: 55 a 59 anos, 60 a 64 anos, 65 a 69 anos.
- **flagged:** Floor-binding exceeds 30% in working-age cohorts: 50 a 54 anos.
- **flagged:** 2014 lookup was missing for 6.32% of pre-2014 cells in Prompt 06; treated-cohort spot checks still show high positive pct_bvr after backfill.
- **flagged:** Unbounded Scenario C re-labeling exceeds observed cohort totals in 1,074 cohort cells before the b-bound is applied.
