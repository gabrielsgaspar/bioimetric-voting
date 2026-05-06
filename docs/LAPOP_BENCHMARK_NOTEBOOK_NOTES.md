# LAPOP Benchmark Notebook Notes

## Benchmark Notebook Source

- Zip file inspected: `Biometric-Voting.zip`
- Notebook inspected: `Biometric-Voting/regressions.ipynb`
- Benchmark figure cells: 146 (`lapop_trust_by_cat.pgf`) and 147 (`lapop_dem_by_cat.pgf`)
- PCA cells: 144 (trust) and 145 (democracy)
- Raw LAPOP build cell: 143
- Municipality and treatment setup cells: 160 and 161

## What The Benchmark Notebook Does

- Reads the raw Brazil LAPOP DTA files for 2006, 2008, 2010, 2012, 2014, 2016, 2018, 2021, and 2023.
- Harmonizes municipality and state strings inside the notebook rather than starting from the newer clean comparable core.
- Remaps source years to benchmark years `{2006: 2006, 2008: 2008, 2010: 2010, 2012: 2012, 2014: 2014, 2016: 2016, 2018: 2018, 2021: 2020, 2023: 2022}` so that 2021 becomes 2020 and 2023 becomes 2022.
- Builds `z_score_pca1_trust` from the first principal component of the eight trust variables.
- The archived notebook contains a legacy weighted democracy combination, but the corrected repository pipeline defines `z_score_pca1_dem` as the standardized first principal component of the three democracy variables and retains the weighted combination only as a comparison artifact.
- Runs the interaction regressions on the sample `year <= 2018`.
- Uses municipality and year fixed effects plus CRV1 clustering on `municipality_id + year`.
- Plots the base treatment effect, the combined treatment effect, and the interaction difference using hatched Yes bars, black CIs, black outlines, and brackets.

## Main Upstream Differences Relative To The Current Repo

- The benchmark notebook includes the 2006 wave, while the newer clean comparable core begins in 2008.
- The trust and democracy indices are standardized on the full matched benchmark panel, not only on the later clean comparable core.
- The archived notebook contains a legacy weighted democracy combo, but the corrected repository pipeline now uses the paper-default PCA1 democracy score in the saved regressions and figures.
- The benchmark plot styling is more specific than the current repo's generic interaction plotter.

## Benchmark Panel Summary

- Source years present: [2006, 2008, 2010, 2012, 2014, 2016, 2018, 2021, 2023]
- Benchmark years present after remapping: [2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022]
- Matched respondents retained after municipality merge: 15,493
- Regression sample years: [2006, 2008, 2010, 2012, 2014, 2016, 2018]

## Municipality Matching Summary

source_year | benchmark_year | rows_total | rows_matched | rows_unmatched | match_rate
--- | --- | --- | --- | --- | ---
2006.0 | 2006.0 | 1214.0 | 1206.0 | 8.0 | 0.9934102141680395
2008.0 | 2008.0 | 1497.0 | 1489.0 | 8.0 | 0.9946559786239145
2010.0 | 2010.0 | 2482.0 | 2392.0 | 90.0 | 0.9637389202256245
2012.0 | 2012.0 | 1441.0 | 1429.0 | 12.0 | 0.9916724496877168
2014.0 | 2014.0 | 1500.0 | 1488.0 | 12.0 | 0.992
2016.0 | 2016.0 | 1532.0 | 1518.0 | 14.0 | 0.9908616187989556
2018.0 | 2018.0 | 1498.0 | 1486.0 | 12.0 | 0.9919893190921228
2021.0 | 2020.0 | 2989.0 | 2971.0 | 18.0 | 0.993977919036467
2023.0 | 2022.0 | 1526.0 | 1514.0 | 12.0 | 0.9921363040629095

## Outputs Updated

- `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready_corrected.parquet`
- `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready_corrected.csv`
- `resources/lapop/regressions/trust_interactions/`
- `resources/lapop/regressions/democracy_interactions/`
- `resources/lapop/figures/trust_interactions_barplot.pdf`
- `resources/lapop/figures/democracy_interactions_barplot.pdf`
