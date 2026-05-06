# Municipality-Level Decomposition Diagnostic Report

Generated from the existing parquet outputs in `data/clean/decomposition/`. This report is diagnostic only: it reads saved outputs and does not rerun the decomposition framework or re-estimate any component.

## 1. Executive Summary

The municipality-level decomposition produced final adoption-cycle estimates for 4,321 treated municipalities: 2,475 strict-first and 1,846 hybrid-first. Aggregated over all treated municipalities, the final Scenario B exit estimate is 7,772,023 voters, or 8.35% of the treated municipalities' 2008 baseline electorate. The final b-bounded Scenario B re-labeling estimate is 3,657,637 voters, or 3.93% of the same baseline; Scenario C raises the b-bounded re-labeling estimate to 5.30%. 2 treated municipalities in the working panel do not appear in the final estimates; the saved outputs imply that they lacked a usable adoption-cycle estimate. 4 processed municipalities lack an exact 2008 age-by-education baseline; Prompt 5 uses their earliest available age-by-education year (2010, 2012) and flags this in the final file.

The qualitative consistency check passes in the saved output. The cross-section decomposition reports a registry contraction of about 12.7% of the 2006 baseline, with re-labeling bounded between 5.22% and 17.82%. The municipality-level framework gives exit of 8.35% of the 2008 baseline, re-labeling of 3.93% under Scenario B, and re-labeling of 5.30% under Scenario C. Rescaling the municipality-level denominators to the 2006 baseline using the saved consistency check gives 8.65% for exit, 4.07% for Scenario B re-labeling, and 5.50% for Scenario C re-labeling. Direction agrees with the cross-section signs: net exit is positive as a loss from the registry, and re-labeling is positive. Magnitudes are lower than the cross-section point estimates but within a factor of two after acknowledging the 2006-versus-2008 baseline difference.

The framework is not mechanically broken, but several diagnostics matter for interpretation: natural education progression is meaningfully positive for some older cohorts, including 55 a 59 anos, 60 a 64 anos, 65 a 69 anos; the b-bound binds in 5.51% of strict-first cohort cells under Scenario B, slightly above the 5% diagnostic threshold; the exit non-negativity floor binds in more than 30% of cells for working-age cohorts 50 a 54 anos; unbounded Scenario C re-labeling exceeds observed cohort totals in 1,074 cohort cells before the b-bound is applied. These issues do not overturn the aggregate consistency check, but they suggest that the cleanest paper use is the aggregate and spatial descriptive application with explicit caveats, rather than strong cohort-level causal claims for every age bin. Hybrid-first municipalities show much smaller aggregate exit than strict-first municipalities (3.28% versus 13.64%), which is directionally consistent with the voluntary-uptake logic.

## 2. Data Preparation Diagnostics

The working data cover election years 2008, 2010, 2012, 2014, 2016, and 2018. The main panel excludes `Inválido` age and unknown education cells and retains only cells with positive voters. The full panel retains the residual age and education categories, also only for positive cells.

### Panel row counts
| panel | rows | municipalities | years |
| --- | --- | --- | --- |
| decomposition_panel_main | 4,458,083 | 5,570 | 2008, 2010, 2012, 2014, 2016, 2018 |
| decomposition_panel_full | 4,589,955 | 5,570 | 2008, 2010, 2012, 2014, 2016, 2018 |
| decomposition_residual_report | 321 | NA | 2008, 2010, 2012, 2014, 2016, 2018 |

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
The saved main and full panels do not retain zero-voter cells, so zero-cell sparsity is inferred as the difference between the complete municipality-year × age × education grid and the positive cells saved in `decomposition_panel_full.parquet`.
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

The final b-bounded Scenario B re-labeling estimate is 3,657,637 voters, or 3.93% of the treated municipalities' 2008 baseline. Scenario C gives 4,939,153 voters, or 5.30%. These are lower than the cross-section Scenario B and Scenario C point estimates, but not different in sign.

### Raw versus b-bounded re-labeling
| estimate | count | rate_2008 |
| --- | --- | --- |
| Scenario B re-labeling, unbounded | 4,169,556 | 4.48% |
| Scenario B re-labeling, b-bounded/final | 3,657,637 | 3.93% |
| Scenario C re-labeling, unbounded | 5,695,816 | 6.12% |
| Scenario C re-labeling, b-bounded/final | 4,939,153 | 5.30% |

### Distribution of municipality-level Scenario B re-labeling rates
| percentile | R_B_rate_2008 |
| --- | --- |
| p10 | 0.31% |
| p25 | 0.87% |
| p50 | 2.46% |
| p75 | 6.48% |
| p90 | 9.88% |
| p95 | 11.52% |

### Cohort-level re-labeling pattern
| age_cohort | R_B_bounded | R_C_bounded | R_B_rate_observed | R_C_rate_observed | share_of_total_R_B | B_bound_bind_share | C_bound_bind_share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16 anos | 785 | 5,704 | 0.16% | 1.18% | 0.02% | 0.35% | 0.93% |
| 17 anos | 2,521 | 10,978 | 0.25% | 1.08% | 0.07% | 0.51% | 0.93% |
| 18 anos | 21,461 | 55,040 | 1.20% | 3.07% | 0.59% | 2.68% | 3.17% |
| 19 anos | 26,023 | 69,696 | 1.26% | 3.37% | 0.71% | 4.67% | 5.65% |
| 20 anos | 60,315 | 82,686 | 2.77% | 3.80% | 1.65% | 7.64% | 10.65% |
| 21 a 24 anos | 183,045 | 351,143 | 2.07% | 3.98% | 5.00% | 7.66% | 8.93% |
| 25 a 29 anos | 346,508 | 548,830 | 3.17% | 5.02% | 9.47% | 7.15% | 8.45% |
| 30 a 34 anos | 588,667 | 795,983 | 5.26% | 7.12% | 16.09% | 7.89% | 9.00% |
| 35 a 39 anos | 855,959 | 991,191 | 7.94% | 9.20% | 23.40% | 9.44% | 10.30% |
| 40 a 44 anos | 687,229 | 828,972 | 7.27% | 8.77% | 18.79% | 8.40% | 9.42% |
| 45 a 49 anos | 397,569 | 518,041 | 4.54% | 5.92% | 10.87% | 6.57% | 7.41% |
| 50 a 54 anos | 214,543 | 262,456 | 2.60% | 3.19% | 5.87% | 5.05% | 6.11% |
| 55 a 59 anos | 123,228 | 164,092 | 1.74% | 2.32% | 3.37% | 4.12% | 5.02% |
| 60 a 64 anos | 76,470 | 100,607 | 1.32% | 1.73% | 2.09% | 2.89% | 3.91% |
| 65 a 69 anos | 44,717 | 58,585 | 1.01% | 1.32% | 1.22% | 3.01% | 3.68% |
| 70 a 74 anos | 17,612 | 50,366 | 0.59% | 1.68% | 0.48% | 3.54% | 5.46% |
| 75 a 79 anos | 6,422 | 23,225 | 0.32% | 1.16% | 0.18% | 4.07% | 6.57% |
| 80 a 84 anos | 2,440 | 10,738 | 0.20% | 0.88% | 0.07% | 4.51% | 6.73% |
| 85 a 89 anos | 1,565 | 7,110 | 0.22% | 1.00% | 0.04% | 5.79% | 8.15% |
| 90 a 94 anos | 443 | 2,858 | 0.10% | 0.66% | 0.01% | 4.58% | 6.85% |
| 95 a 99 anos | 95 | 745 | 0.07% | 0.52% | 0.00% | 2.01% | 8.84% |
| 100 anos ou mais | 22 | 109 | 0.10% | 0.52% | 0.00% | 1.94% | 21.45% |

Under Scenario B, 66.39% of aggregate bounded re-labeling comes from cohorts 35+ and 33.61% comes from cohorts below 35. The older-cohort component is therefore quantitatively important and is the cleaner part of the identification, but younger and middle cohorts still contribute materially.

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

### b-bound binding by first regime
| first_regime | cells | B_bound_bind_share | C_bound_bind_share | mean_b_uptake |
| --- | --- | --- | --- | --- |
| hybrid | 40,612 | 3.73% | 5.49% | 24.00% |
| strict | 54,450 | 5.51% | 8.41% | 83.56% |

### b-bound binding by cohort and first regime
| age_cohort | hybrid_B | strict_B | hybrid_C | strict_C | hybrid_b | strict_b |
| --- | --- | --- | --- | --- | --- | --- |
| 16 anos | 0.05% | 0.57% | 0.81% | 1.01% | 96.99% | 87.75% |
| 17 anos | 0.05% | 0.85% | 0.65% | 1.13% | 88.46% | 88.00% |
| 18 anos | 0.11% | 4.61% | 0.38% | 5.25% | 56.41% | 88.00% |
| 19 anos | 0.16% | 8.04% | 0.92% | 9.17% | 40.67% | 87.94% |
| 20 anos | 5.47% | 9.25% | 9.75% | 11.31% | 23.67% | 87.78% |
| 21 a 24 anos | 3.58% | 10.71% | 5.15% | 11.76% | 16.85% | 87.97% |
| 25 a 29 anos | 1.79% | 11.15% | 4.01% | 11.76% | 15.45% | 87.98% |
| 30 a 34 anos | 3.52% | 11.15% | 5.47% | 11.64% | 16.00% | 87.96% |
| 35 a 39 anos | 7.42% | 10.95% | 8.78% | 11.43% | 17.02% | 87.97% |
| 40 a 44 anos | 4.82% | 11.07% | 6.66% | 11.47% | 17.83% | 87.98% |
| 45 a 49 anos | 1.35% | 10.46% | 2.22% | 11.27% | 18.42% | 87.98% |
| 50 a 54 anos | 0.22% | 8.65% | 0.38% | 10.38% | 19.28% | 87.99% |
| 55 a 59 anos | 0.54% | 6.79% | 0.87% | 8.12% | 20.71% | 87.98% |
| 60 a 64 anos | 1.19% | 4.16% | 1.57% | 5.66% | 21.21% | 87.98% |
| 65 a 69 anos | 2.33% | 3.52% | 2.55% | 4.53% | 20.05% | 87.93% |
| 70 a 74 anos | 4.71% | 2.67% | 5.58% | 5.37% | 14.81% | 87.88% |
| 75 a 79 anos | 5.96% | 2.67% | 6.55% | 6.59% | 10.20% | 87.69% |
| 80 a 84 anos | 8.18% | 1.78% | 9.15% | 4.93% | 6.51% | 87.30% |
| 85 a 89 anos | 11.92% | 1.21% | 14.52% | 3.39% | 3.79% | 86.70% |
| 90 a 94 anos | 10.02% | 0.53% | 11.32% | 3.52% | 1.89% | 80.55% |
| 95 a 99 anos | 4.39% | 0.24% | 5.90% | 11.03% | 1.08% | 58.61% |
| 100 anos ou mais | 4.23% | 0.24% | 17.55% | 24.36% | 0.65% | 30.34% |

### Municipalities with Scenario B re-labeling above 30% of baseline
Count: 0 municipalities.
None.

**flagged: Scenario B re-labeling (3.93% of 2008 baseline; 4.07% rescaled) is below the cross-section lower bound of 5.22%, though not by a wide factor.**
**flagged: national natural progression delta is above 2% for 50+ cohorts 55 a 59 anos, 60 a 64 anos, 65 a 69 anos.** This suggests pre-treatment record updating or composition shifts in older cohorts, which weakens the clean re-labeling assumption for those bins.
**flagged: b-bound binds in 5.51% of strict-first cells under Scenario B, above the 5% diagnostic threshold.**

## 6. Aggregation and Consistency Check

The final aggregation files report b-bounded re-labeling estimates. The cross-section comparison in `decomposition_consistency_check.parquet` classifies all three headline metrics as within a factor of two and directionally consistent.

### Final aggregate headline numbers
| aggregation_level | n_municipalities | national_2008_baseline | national_t_post_observed | national_exit_count | national_R_B_count | national_R_C_count | national_exit_rate_2008 | national_R_B_rate_2008 | national_R_C_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| strict | 2,475 | 45,514,603 | 46,781,648 | 6,210,453 | 3,107,256 | 4,219,678 | 13.64% | 6.83% | 9.27% |
| hybrid | 1,846 | 47,602,319 | 53,766,096 | 1,561,570 | 550,381 | 719,475 | 3.28% | 1.16% | 1.51% |
| all_treated | 4,321 | 93,116,922 | 100,547,744 | 7,772,023 | 3,657,637 | 4,939,153 | 8.35% | 3.93% | 5.30% |

### Scenario exit allocation implied by the saved outputs
| scenario | low_ed_exit_count | high_ed_exit_count | low_ed_exit_rate_2008 | high_ed_exit_rate_2008 | total_exit_rate_2008 |
| --- | --- | --- | --- | --- | --- |
| B: no high-ed exit | 7,772,023 | 0 | 8.35% | 0.00% | 8.35% |
| C: proportional exit | 4,826,564 | 2,945,459 | 5.18% | 3.16% | 8.35% |

### Cross-section comparison
| metric | cross_section_value | muni_level_value_t_post_baseline | muni_level_value_2008_baseline | muni_level_value_rescaled_to_2006 | agreement_qualitative | agreement_directional |
| --- | --- | --- | --- | --- | --- | --- |
| exit_scenario_B | 12.60% | 7.73% | 8.35% | 8.65% | within_factor_2 | same_sign |
| R_B_lower_bound | 5.22% | 3.64% | 3.93% | 4.07% | within_factor_2 | same_sign |
| R_C_scenario_C | 10.40% | 4.91% | 5.30% | 5.50% | within_factor_2 | same_sign |

Direction agreement is positive for all three metrics in the consistency file. Magnitude agreement is classified as a pass in the saved final output: the municipality-level exit and re-labeling estimates are lower than the cross-section values but remain within a factor of two after the 2008-to-2006 rescaling embedded in the saved consistency output.

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

The cross-section decomposition is education-by-education and cannot produce this age-by-age allocation. The municipality-level framework attributes the largest exit shares to middle and older working-age cohorts in absolute terms, with high exit rates relative to cohort baseline among the oldest cohorts where small denominators and mortality dynamics matter most. The consistency check passes qualitatively, but the age decomposition should be treated as model-implied and more sensitive to survival-rate assumptions than the aggregate count.

## 7. Heterogeneity Across Municipalities

Municipality-level effects vary substantially across geography, rollout cohort, and municipality size. The weighted state aggregates show the highest exit rates in AL, MA, ES and the lowest in MG, RJ, BA. By region, the highest weighted exit rate is in the Center-West, while the highest Scenario B re-labeling rate is in the North. These are descriptive patterns from the saved final table, not separate causal estimates.

### Top 5 states by exit rate
| state | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| AL | 102 | 1,974,873 | 317,688 | 0 | 16.09% | 0.00% |
| MA | 145 | 3,415,585 | 546,493 | 241,988 | 16.00% | 7.08% |
| ES | 38 | 983,732 | 147,326 | 31,248 | 14.98% | 3.18% |
| PE | 129 | 4,681,148 | 681,651 | 397,259 | 14.56% | 8.49% |
| PI | 224 | 2,183,294 | 305,152 | 216,596 | 13.98% | 9.92% |

### Bottom 5 states by exit rate
| state | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| MG | 731 | 12,824,255 | 479,047 | 177,862 | 3.74% | 1.39% |
| RJ | 92 | 11,228,591 | 436,976 | 94,227 | 3.89% | 0.84% |
| BA | 417 | 9,135,992 | 472,144 | 126,837 | 5.17% | 1.39% |
| SC | 294 | 4,354,622 | 231,451 | 139,854 | 5.32% | 3.21% |
| AC | 18 | 419,964 | 22,725 | 40,265 | 5.41% | 9.59% |

### Top 5 states by Scenario B re-labeling rate
| state | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| AM | 10 | 1,260,683 | 116,505 | 232,615 | 9.24% | 18.45% |
| AP | 16 | 384,703 | 31,819 | 54,389 | 8.27% | 14.14% |
| RR | 15 | 247,757 | 18,708 | 31,615 | 7.55% | 12.76% |
| PA | 54 | 2,430,017 | 261,259 | 282,081 | 10.75% | 11.61% |
| PI | 224 | 2,183,294 | 305,152 | 216,596 | 13.98% | 9.92% |

### Bottom 5 states by Scenario B re-labeling rate
| state | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| AL | 102 | 1,974,873 | 317,688 | 0 | 16.09% | 0.00% |
| SE | 75 | 1,369,303 | 129,249 | 0 | 9.44% | 0.00% |
| RJ | 92 | 11,228,591 | 436,976 | 94,227 | 3.89% | 0.84% |
| MG | 731 | 12,824,255 | 479,047 | 177,862 | 3.74% | 1.39% |
| BA | 417 | 9,135,992 | 472,144 | 126,837 | 5.17% | 1.39% |

### Heterogeneity by first-treatment cohort year
| year_first_any_bvr | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| 2010 | 57 | 1,235,328 | 187,720 | 0 | 15.20% | 0.00% |
| 2012 | 238 | 6,717,705 | 856,813 | 0 | 12.75% | 0.00% |
| 2014 | 464 | 11,669,276 | 1,486,624 | 1,065,543 | 12.74% | 9.13% |
| 2016 | 1,619 | 37,458,633 | 2,524,410 | 1,383,790 | 6.74% | 3.69% |
| 2018 | 1,943 | 36,035,980 | 2,716,455 | 1,208,304 | 7.54% | 3.35% |

### Heterogeneity by first regime
| first_regime | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| hybrid | 1,846 | 47,602,319 | 1,561,570 | 550,381 | 3.28% | 1.16% |
| strict | 2,475 | 45,514,603 | 6,210,453 | 3,107,256 | 13.64% | 6.83% |

### Heterogeneity by population-size decile
D1 is the smallest decile by 2008 baseline electorate; D10 is the largest.
| size_decile | municipalities | min_N_2008 | max_N_2008 | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| D1 | 433 | 943 | 2,595 | 886,144 | 124,630 | 36,654 | 14.06% | 4.14% |
| D2 | 432 | 2,596 | 3,491 | 1,317,189 | 180,326 | 55,257 | 13.69% | 4.20% |
| D3 | 433 | 3,495 | 4,491 | 1,712,426 | 209,479 | 73,873 | 12.23% | 4.31% |
| D4 | 431 | 4,492 | 5,775 | 2,180,941 | 252,032 | 91,623 | 11.56% | 4.20% |
| D5 | 432 | 5,776 | 7,395 | 2,824,170 | 294,996 | 102,451 | 10.45% | 3.63% |
| D6 | 432 | 7,398 | 9,841 | 3,704,424 | 380,798 | 135,653 | 10.28% | 3.66% |
| D7 | 432 | 9,846 | 13,251 | 4,899,939 | 465,045 | 186,260 | 9.49% | 3.80% |
| D8 | 432 | 13,261 | 18,925 | 6,756,199 | 678,034 | 248,102 | 10.04% | 3.67% |
| D9 | 432 | 18,937 | 34,175 | 10,653,011 | 1,006,407 | 430,836 | 9.45% | 4.04% |
| D10 | 432 | 34,225 | 4,566,338 | 58,182,479 | 4,180,276 | 2,296,928 | 7.18% | 3.95% |

### Regional aggregates
| region | municipalities | N_2008_total | exit_count | R_B_count | exit_rate_2008 | R_B_rate_2008 |
| --- | --- | --- | --- | --- | --- | --- |
| Center-West | 298 | 5,737,073 | 650,395 | 281,786 | 11.34% | 4.91% |
| Northeast | 1,657 | 33,036,912 | 3,529,136 | 1,662,617 | 10.68% | 5.03% |
| North | 287 | 6,479,228 | 611,900 | 762,169 | 9.44% | 11.76% |
| South | 1,097 | 18,767,274 | 1,498,433 | 531,301 | 7.98% | 2.83% |
| Southeast | 982 | 29,096,435 | 1,482,158 | 419,765 | 5.09% | 1.44% |

The municipality-level Pearson correlation between exit rate and Scenario B re-labeling rate is 0.255; the Spearman rank correlation is 0.355. This is consistent with a positive but imperfect relationship between BVR-induced disruption and re-labeling. By regime, the correlations are:
| first_regime | pearson | spearman |
| --- | --- | --- |
| hybrid | 0.028 | 0.009 |
| strict | -0.188 | -0.156 |

For the spatial visualization, the map-ready files should be useful because the final table contains strong cross-state and cross-region variation. The regional table suggests higher weighted exit in the North and Northeast than in the Southeast and South, while re-labeling is also highest in the North. This pattern should be visualized rather than over-interpreted from the table alone.

## 8. Files Inventory

### Decomposition parquet outputs
| file | rows | columns | description |
| --- | --- | --- | --- |
| data/clean/decomposition/decomposition_consistency_check.parquet | 3 | metric, cross_section_value, muni_level_value_t_post_baseline, muni_level_value_2008_baseline, muni_level_value_rescaled_to_2006, agreement_qualitative, agreement_directional | Cross-section versus municipality-level consistency metrics. |
| data/clean/decomposition/decomposition_exit_cohort.parquet | 95,062 | ibge_municipality_id, state, t, t_post, age_cohort, N_observed_t, N_aged_forward, N_predicted_no_bvr, N_observed_t_post, exit_count, exit_rate, year_first_any_bvr, first_regime, sigma_used, inflow_used | Cohort-level no-BVR predictions and BVR-induced exit estimates for adoption cycles. |
| data/clean/decomposition/decomposition_exit_municipality.parquet | 4,321 | ibge_municipality_id, state, t, t_post, year_first_any_bvr, first_regime, total_predicted, total_observed, exit_count_total, exit_rate_total, exit_count_by_cohort, n_cohorts_with_exit | Municipality-level exit totals aggregated across cohorts. |
| data/clean/decomposition/decomposition_final_aggregate.parquet | 3 | aggregation_level, n_municipalities, national_2008_baseline, national_t_post_observed, national_exit_count, national_R_B_count, national_R_C_count, national_exit_rate_2008, national_R_B_rate_2008, national_R_C_rate_2008, national_exit_rate_t_post, national_R_B_rate_t_post, national_R_C_rate_t_post | Aggregate national rates by first regime and all treated municipalities. |
| data/clean/decomposition/decomposition_final_by_cohort.parquet | 8 | year_first_any_bvr, first_regime, n_municipalities, exit_count, R_B_count, R_C_count, exit_rate_2008, R_B_rate_2008, R_C_rate_2008, average_b_uptake | Aggregate decomposition by adoption cohort year and first regime. |
| data/clean/decomposition/decomposition_final_municipality.parquet | 4,321 | ibge_municipality_id, state, t_post, year_first_any_bvr, first_regime, N_2008_total, baseline_year_used, baseline_is_exact_2008, total_predicted, total_observed, exit_count, R_B_count, R_C_count, exit_rate_t_post, R_B_rate_t_post, R_C_rate_t_post, exit_rate_2008, R_B_rate_2008, R_C_rate_2008, n_cohorts_with_exit, n_cohorts_bound_binds_B, n_cohorts_bound_binds_C | Final municipality-level exit and re-labeling table with 2008 baseline rates. |
| data/clean/decomposition/decomposition_inflows.parquet | 22,280 | ibge_municipality_id, state, age_cohort, n_cycles_used, total_inflow, total_denominator, inflow_rate, inflow_rate_state, inflow_rate_state_used, state_threshold_met, inflow_rate_national, municipality_threshold_met, inflow_rate_used, rate_source | Operative inflow rates for cohorts 16-19 with fallback source. |
| data/clean/decomposition/decomposition_map_counts.parquet | 4,321 | ibge_municipality_id, state, first_regime, year_first_any_bvr, exit_count, R_B_count, R_C_count, total_decomposition_count_B, total_decomposition_count_C | Map-ready municipality count variables for spatial visualization. |
| data/clean/decomposition/decomposition_map_rates.parquet | 4,321 | ibge_municipality_id, state, first_regime, year_first_any_bvr, exit_rate_2008, R_B_rate_2008, R_C_rate_2008, total_decomposition_rate_B, total_decomposition_rate_C | Map-ready municipality rate variables for spatial visualization. |
| data/clean/decomposition/decomposition_panel_full.parquet | 4,589,955 | ibge_municipality_id, state, year, age_cohort, education, low_ed, high_ed, num_voters, num_voters_bvr, pct_bvr, bvr_status, year_first_any_bvr, year_first_strict_bvr, year_first_hybrid_bvr, first_regime, event_time | Full positive-cell age-by-education panel retaining residual age and education categories. |
| data/clean/decomposition/decomposition_panel_main.parquet | 4,458,083 | ibge_municipality_id, state, year, age_cohort, education, low_ed, high_ed, num_voters, num_voters_bvr, pct_bvr, bvr_status, year_first_any_bvr, year_first_strict_bvr, year_first_hybrid_bvr, first_regime, event_time | Main working age-by-education panel; positive voter cells only; excludes Inválido age and unknown education. |
| data/clean/decomposition/decomposition_prediction_education.parquet | 95,062 | ibge_municipality_id, state, t, t_post, age_cohort, N_low_observed_t, N_high_observed_t, N_low_predicted_t_post, N_high_predicted_t_post, N_low_observed_t_post, N_high_observed_t_post, N_predicted_total, exit_count, pi_low_t, pi_low_predicted_t_post, pi_low_observed_t_post, delta_used, N_observed_total, b_uptake, pi_low_t_source, rate_source | Predicted no-BVR low/high education counts by cohort at adoption. |
| data/clean/decomposition/decomposition_pretreatment_cycles.parquet | 440,154 | ibge_municipality_id, state, t, t_plus_2, age_cohort, N_t, N_t_plus_2, aged_forward_count, total_voters_t, year_first_any_bvr, first_regime | Pre-treatment municipality-cycle age counts and aging-operator predictions used for survival estimation. |
| data/clean/decomposition/decomposition_progression_rates.parquet | 122,540 | ibge_municipality_id, state, age_cohort, delta_municipality, delta_state, delta_national, delta_used, n_cycles_used, n_cycles_state, n_cycles_national, municipality_threshold_met, state_threshold_met, rate_source | Natural low-education share progression rates by municipality and cohort. |
| data/clean/decomposition/decomposition_relabel_cohort.parquet | 95,062 | ibge_municipality_id, state, t, t_post, age_cohort, year_first_any_bvr, first_regime, R_B_raw, R_B_bounded, R_C_raw, R_C_bounded, R_max_b, b_uptake, bound_binds_B, bound_binds_C, exit_count, N_predicted_total, N_observed_total, R_B_unfloored, R_C_unfloored | Cohort-level Scenario B/C re-labeling estimates, b-bounds, and binding flags. |
| data/clean/decomposition/decomposition_relabel_municipality.parquet | 4,321 | ibge_municipality_id, state, t_post, year_first_any_bvr, first_regime, R_B_total, R_C_total, R_rate_B_total, R_rate_C_total, R_B_younger, R_B_older, R_C_younger, R_C_older, N_observed_total, n_cohorts_with_relabel, n_cohorts_bound_binds_B, n_cohorts_bound_binds_C | Municipality-level bounded Scenario B/C re-labeling totals. |
| data/clean/decomposition/decomposition_residual_report.parquet | 321 | year, state, first_regime, total_voters_full, total_voters_excluded, excluded_share | Excluded residual voter shares by year, state, and first regime. |
| data/clean/decomposition/decomposition_survival_municipality.parquet | 122,540 | ibge_municipality_id, state, age_cohort, n_cycles_used, total_predicted_used, total_observed_used, sigma_municipality, sigma_state, sigma_state_fallback, state_fallback_source, state_threshold_met, sigma_national, municipality_threshold_met, sigma_used, rate_source | Operative municipality-cohort survival rates with municipality/state/national fallback source. |
| data/clean/decomposition/decomposition_survival_national.parquet | 22 | age_cohort, n_cycles, total_predicted, total_observed, sigma_national, rate_type | National cohort survival rates and inflow-only markers. |
| data/clean/decomposition/decomposition_survival_state.parquet | 572 | state, age_cohort, n_cycles, total_predicted, total_observed, sigma_state, sigma_national, state_threshold_met, sigma_used, fallback_source | State-level cohort survival rates with national fallbacks. |

### Decomposition scripts
| file | description |
| --- | --- |
| src/decomposition/01_prepare_data.py | Builds and validates the main/full decomposition panels and residual report. |
| src/decomposition/02_estimate_survival.py | Builds pre-treatment cycles and estimates national, state, and municipality survival/inflow rates. |
| src/decomposition/03_compute_exit.py | Applies survival/inflow parameters to adoption cycles and estimates cohort and municipality exit. |
| src/decomposition/04_compute_relabel.py | Estimates education progression rates and Scenario B/C b-bounded re-labeling. |
| src/decomposition/05_aggregate_and_check.py | Aggregates municipality results, constructs map files, and runs consistency checks. |
| src/decomposition/aging_operator.py | Defines the 22-cohort mechanical aging operator used by survival and exit steps. |

### Markdown notes and prompt files
| file | description |
| --- | --- |
| PROMPT_decomp_01_prepare.md | Saved decomposition prompt/instructions. |
| PROMPT_decomp_02_survival.md | Saved decomposition prompt/instructions. |
| PROMPT_decomp_03_exit.md | Saved decomposition prompt/instructions. |
| PROMPT_decomp_04_relabel.md | Saved decomposition prompt/instructions. |
| PROMPT_decomp_05_aggregate.md | Saved decomposition prompt/instructions. |
| AGE_EDUCATION.md | Age and education raw-data note. |
| PROMPT_REPORT.md | This diagnostic report. |

### Consolidated flags
- **flagged:** Floor-binding exceeds 30% in working-age cohorts: 50 a 54 anos.
- **flagged:** National delta is above 2% per cycle for 50+ cohorts: 55 a 59 anos, 60 a 64 anos, 65 a 69 anos.
- **flagged:** b-bound binds in more than 5% of strict-first cells under Scenario B.
