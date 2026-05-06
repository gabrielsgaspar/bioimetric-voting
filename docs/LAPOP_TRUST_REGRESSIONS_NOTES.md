# LAPOP Trust Regressions Notes

## Input Dataset Used

- Base respondent-level file: `data/clean/lapop/lapop_brazil_with_pca_indices.parquet`
- Regression-ready file created in this step: `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready.parquet`

## Actual Sample Years Used

- Full regression-ready file years: [2008, 2010, 2012, 2014, 2017, 2019]
- Main regression sample years with `survey_year <= 2018`: [2008, 2010, 2012, 2014, 2017]

## Outcomes Used

- `trust_index_std`
- `democracy_index_std`

## Controls Used

- `low_ed`
- `female`
- `white`
- `married`
- `working`
- `age`
- `log_gdp_pc`
- `log_total_pop`

## Fixed Effects And Clustering

- Municipality fixed effects: `municipality_id`
- Survey-year fixed effects: `survey_year`
- Requested clustering: `municipality_id + survey_year`
- The regression runner uses a two-way clustered covariance matrix when it is numerically well behaved and falls back to one-way municipality clustering if the two-way covariance is not usable.

## Municipality And Covariate Linkage

- Respondents matched to municipalities: 9,919 of 10,009
- Respondents unmatched to municipalities: 90
- Respondents with manual municipality overrides: 187
- Respondents with municipal GDP and population covariates: 9,919

The municipality linkage uses LAPOP normalized municipality names and normalized state names, then merges them to the repo's clean IBGE municipality file. A small manual override list handles spelling or historical-name differences such as `Embu` versus `Embu das Artes` and `Santana do Livramento` versus `Sant'Ana do Livramento`.

## Treatment Coding

- `treatment_dummy` equals one when a respondent lives in a municipality whose first biometric election year is less than or equal to the respondent's survey year.
- Municipal treatment timing comes from `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`.

## Municipal Covariates

- `log_total_pop` is based on official IBGE resident-population estimates from SIDRA table `6579`, variable `9324`.
- `log_gdp_pc` is constructed from official IBGE municipal GDP at current prices from SIDRA table `5938`, variable `37`, divided by resident population in the same survey year.
- These covariates were fetched because the repository did not already contain a clean municipality-year GDP/population file.

## How Interaction Effects Were Computed

Each interaction model fits:

`outcome ~ treatment_dummy * interaction_var + controls + municipality FE + survey-year FE`

The saved interaction outputs then compute:

1. the base-group treatment effect as the coefficient on `treatment_dummy`,
2. the interacted-group treatment effect as `treatment_dummy + treatment_dummy:interaction_var`,
3. the interaction difference as the interaction coefficient itself,
4. the interacted-group standard error from the full fitted covariance matrix.

## How The Plots Were Built

- Single-outcome figures use two bars per category, labeled `No` and `Yes`.
- Whiskers show 95% confidence intervals.
- The interaction difference is printed above each pair with stars based on the interaction p-value.
- Trust plots use a dark-slate palette and democracy plots use a brown palette, following the existing project conventions.

## Deviations From The Notebook Request

- No executable LAPOP notebook file was present in the repository during this build, so the regression specification was reconstructed from the manuscript scaffold, the harmonization notes, the PCA notes, and the requested design target.
- The clean LAPOP file uses actual years `2008, 2010, 2012, 2014, 2017, 2019`, so the main sample restriction `survey_year <= 2018` corresponds to `2008, 2010, 2012, 2014, 2017`.
- `pyfixest` could not be installed cleanly in this environment because `llvmlite` required a local LLVM configuration. The reusable regression skill therefore runs a documented `statsmodels` fixed-effects fallback.

## Main Outputs

- `resources/lapop/regressions/trust_interactions/`
- `resources/lapop/regressions/democracy_interactions/`
- `resources/lapop/figures/trust_interactions_barplot.pdf`
- `resources/lapop/figures/democracy_interactions_barplot.pdf`
- `resources/tables/lapop_trust_interactions_main_table.tex`
