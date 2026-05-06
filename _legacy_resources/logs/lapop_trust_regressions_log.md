# LAPOP Trust Regressions Log

- Timestamp: `2026-04-10T11:32:18+01:00`
- Regression-ready dataset: `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready.parquet`
- Trust config: `.agents/skills/regression-runner/examples/config_trust_interactions.yml`
- Democracy config: `.agents/skills/regression-runner/examples/config_democracy_interactions.yml`

## Sample Years

- Full years in regression-ready file: [2008, 2010, 2012, 2014, 2017, 2019]
- Main regression years used: [2008, 2010, 2012, 2014, 2017]

## Respondent Match Summary

- Total respondents: 10,009
- Municipality matched: 9,919
- Municipality unmatched: 90
- Manual override matches: 187
- Respondents with municipal covariates: 9,919

## Estimation Sample Sizes By Category

### Trust

Female           8135
Low Education    8135
Married          8135
White            8135

### Democracy

Female           8135
Low Education    8135
Married          8135
White            8135

## Output Files

- `resources/lapop/regressions/trust_interactions/config_used.yml`
- `resources/lapop/regressions/trust_interactions/tidy_results.csv`
- `resources/lapop/regressions/trust_interactions/interaction_effects.csv`
- `resources/lapop/regressions/trust_interactions/model_summaries.txt`
- `resources/lapop/regressions/trust_interactions/regression_table.csv`
- `resources/lapop/regressions/trust_interactions/regression_table.tex`
- `resources/lapop/regressions/democracy_interactions/config_used.yml`
- `resources/lapop/regressions/democracy_interactions/tidy_results.csv`
- `resources/lapop/regressions/democracy_interactions/interaction_effects.csv`
- `resources/lapop/regressions/democracy_interactions/model_summaries.txt`
- `resources/lapop/regressions/democracy_interactions/regression_table.csv`
- `resources/lapop/regressions/democracy_interactions/regression_table.tex`
- `resources/lapop/figures/trust_interactions_barplot.pdf`
- `resources/lapop/figures/democracy_interactions_barplot.pdf`
- `resources/tables/lapop_trust_interactions_main_table.tex`

## Unmatched Municipality-State Pairs

```text
 municipality_name state_name  n_respondents
               NaN       para             60
               NaN  sao paulo             30
```

## Warnings And Deviations

- No executable LAPOP notebook file was available in the repo, so notebook logic was reconstructed from existing notes and the requested design target.
- `pyfixest` installation failed because `llvmlite` could not build without a local LLVM configuration; the regression skill used the documented `statsmodels` fixed-effects fallback.
- The second clustering dimension has only a handful of survey-year groups in the main sample, so inference should be interpreted with that limitation in mind.
