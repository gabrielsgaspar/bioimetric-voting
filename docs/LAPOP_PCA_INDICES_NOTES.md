# LAPOP PCA Indices Notes

## Input File Used

- Main input file: `data/clean/lapop/lapop_brazil_core_2008_2019.parquet`

## Actual Survey Years Included

- Clean file survey years: [2008, 2010, 2012, 2014, 2017, 2019]
- Requested main sample years from the draft/notebook instructions: [2006, 2008, 2010, 2012, 2014, 2016, 2018]
- Requested extended notebook-availability years from the draft/notebook instructions: [2006, 2008, 2010, 2012, 2014, 2016, 2018, 2021, 2023]

## Why The Main Sample Uses [2008, 2010, 2012, 2014, 2017, 2019]

- The requested main sample was 2006, 2008, 2010, 2012, 2014, 2016, 2018, but the best clean comparable LAPOP file in the repository contains actual survey years [2008, 2010, 2012, 2014, 2017, 2019]. The script therefore uses the full comparable clean file as the default main sample and does not relabel years.
- The repository does not contain a clean comparable 2006 wave.
- The clean comparable core uses actual LAPOP field years `2008, 2010, 2012, 2014, 2017, 2019`; it does not relabel 2017 as 2016 or 2019 as 2018.
- A partial 2021 selected-question file exists, but it does not contain the full 8-item trust block or the 3-item democracy block, so it is not used for the default PCA outputs.
- No clean comparable 2023 Brazil LAPOP file is present in the repository.

## Variables Used

### Trust PCA

- `trust_inst_respect`
- `trust_rights_protected`
- `trust_proud_system`
- `trust_support_system`
- `trust_parties`
- `trust_municipal_gov`
- `trust_president`
- `trust_elections`

### Democracy PCA

- `democracy_best_form`
- `democracy_satisfaction`
- `democracy_voice_matters`

`democracy_understands_politics` is retained in the clean core but excluded from the main democracy index by design.

## Preprocessing Steps

1. Restrict to the main comparable clean sample described above.
2. Check that trust inputs already use larger values for more trust.
3. Reverse `democracy_satisfaction` as `5 - democracy_satisfaction` after verifying that the harmonized variable is on the raw 1-4 LAPOP scale.
4. Impute missing PCA inputs using the sample median for each variable.
5. Standardize each PCA input variable.
6. Run PCA on the standardized matrix.
7. Use the first principal component as the default paper-consistent index.
8. Standardize the respondent-level PCA1 score to mean zero and unit variance over the main sample.

## Direction Handling

- Trust items: larger values already correspond to more trust.
- Democracy items:
  - `democracy_best_form`: larger values correspond to stronger agreement that democracy is best.
  - `democracy_voice_matters`: larger values correspond to stronger belief that government cares about citizens' views.
  - `democracy_satisfaction`: reversed before PCA so larger values correspond to more satisfaction with democracy.

## Notebook Versus Paper Discrepancy

- The paper-consistent default implemented here uses the first principal component for both the trust index and the democracy index.
- The notebook-style trust construction is consistent with that choice.
- The notebook's democracy section appears to use a legacy combination of PC1 and PC2 rather than pure PCA1.
- This script does **not** use that legacy combination as the main democracy index.
- Instead, it saves:
  - `democracy_index_pca1_raw`
  - `democracy_index_std`
  - `democracy_index_legacy_combo_raw`
  - `democracy_index_legacy_combo_std`
- The legacy comparison summary is saved to `resources/lapop/pca/democracy_pca_legacy_notebook_comparison.csv`.

## Sample Sizes By Year

| survey_year | n_respondents |
| --- | --- |
| 2008 | 1497 |
| 2010 | 2482 |
| 2012 | 1500 |
| 2014 | 1500 |
| 2017 | 1532 |
| 2019 | 1498 |

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

## Main PCA Results

- Trust PC1 explained variance: 0.4909
- Trust PC2 explained variance: 0.1087
- Democracy PC1 explained variance: 0.4104
- Democracy PC2 explained variance: 0.3051

## Legacy Democracy Comparison

| metric | value |
| --- | --- |
| n_obs | 10009.0 |
| pc1_explained_variance_ratio | 0.4103864547911322 |
| pc2_explained_variance_ratio | 0.3051343128401388 |
| correlation_main_vs_legacy_std | 0.8418386881566813 |
| mean_absolute_difference_std | 0.4529432159288228 |
| root_mean_squared_difference_std | 0.5624256605869249 |

## Outputs

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
- `resources/logs/lapop_pca_indices_log.md`
