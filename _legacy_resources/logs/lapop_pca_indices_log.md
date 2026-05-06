# LAPOP PCA Indices Log

- Timestamp: `2026-04-10T16:01:01+01:00`
- Input file: `data/clean/lapop/lapop_brazil_core_2008_2019.parquet`
- Actual survey years used: `[2008, 2010, 2012, 2014, 2017, 2019]`
- Requested main sample years: `[2006, 2008, 2010, 2012, 2014, 2016, 2018]`
- Requested extended notebook years: `[2006, 2008, 2010, 2012, 2014, 2016, 2018, 2021, 2023]`

## Sample Sizes

| survey_year | n_respondents |
| --- | --- |
| 2008 | 1497 |
| 2010 | 2482 |
| 2012 | 1500 |
| 2014 | 1500 |
| 2017 | 1532 |
| 2019 | 1498 |

## Main-Sample Note

- The requested main sample was 2006, 2008, 2010, 2012, 2014, 2016, 2018, but the best clean comparable LAPOP file in the repository contains actual survey years [2008, 2010, 2012, 2014, 2017, 2019]. The script therefore uses the full comparable clean file as the default main sample and does not relabel years.

## Imputation Counts

### Trust

| variable | imputed_n | median_imputation_value |
| --- | --- | --- |
| trust_inst_respect | 230 | 4.0 |
| trust_rights_protected | 239 | 3.0 |
| trust_proud_system | 212 | 3.0 |
| trust_support_system | 286 | 3.0 |
| trust_parties | 179 | 2.0 |
| trust_municipal_gov | 129 | 4.0 |
| trust_president | 108 | 4.0 |
| trust_elections | 150 | 4.0 |

### Democracy

| variable | imputed_n | median_imputation_value |
| --- | --- | --- |
| democracy_best_form | 492 | 5.0 |
| democracy_satisfaction | 1117 | 2.0 |
| democracy_voice_matters | 317 | 3.0 |

## Explained Variance

- Trust PC1: 0.490907
- Trust PC2: 0.108671
- Democracy PC1: 0.410386
- Democracy PC2: 0.305134

## Validation

- Trust PCA uses 8 variables.
- Democracy PCA uses 3 variables.
- Trust standardized index mean: 0.00000000
- Trust standardized index sd: 1.00000000
- Democracy standardized index mean: 0.00000000
- Democracy standardized index sd: 1.00000000

## Notebook Legacy Democracy Comparison

| metric | value |
| --- | --- |
| n_obs | 10009.0 |
| pc1_explained_variance_ratio | 0.4103864547911322 |
| pc2_explained_variance_ratio | 0.3051343128401388 |
| correlation_main_vs_legacy_std | 0.8418386881566813 |
| mean_absolute_difference_std | 0.4529432159288228 |
| root_mean_squared_difference_std | 0.5624256605869249 |

## Output Files

- `data/clean/lapop/lapop_brazil_with_pca_indices.parquet`
- `data/clean/lapop/lapop_brazil_with_pca_indices.csv`
- `resources/lapop/pca/trust_pca_loadings_main.csv`
- `resources/lapop/pca/trust_pca_summary_main.csv`
- `resources/lapop/pca/democracy_pca_loadings_main.csv`
- `resources/lapop/pca/democracy_pca_summary_main.csv`
- `resources/lapop/pca/democracy_pca_legacy_notebook_comparison.csv`
- `resources/lapop/pca/trust_pca_table_main.tex`
- `resources/lapop/pca/democracy_pca_table_main.tex`
- `resources/lapop/pca/trust_explained_variance_main.pdf`
- `resources/lapop/pca/trust_explained_variance_main.png`
- `resources/lapop/pca/democracy_explained_variance_main.pdf`
- `resources/lapop/pca/democracy_explained_variance_main.png`

## Warnings And Deviations

- The repository's clean comparable LAPOP input does not include 2006, 2016, 2018, or 2023 as actual survey years.
- The default main PCA outputs therefore use the actual clean comparable years in the core file: 2008, 2010, 2012, 2014, 2017, 2019.
- The 2021 selected-question clean file is incomplete for the full trust and democracy blocks, so it is not used for the default PCA outputs.
- The democracy legacy combo is provided only as a notebook-comparison artifact; the main democracy index remains PCA1 only.
