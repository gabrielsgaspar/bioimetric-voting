# LAPOP Trust Replication Debug Notes

## What Differed Between The Benchmark Notebook And The Current Repo

The benchmark notebook did not start from the newer clean comparable LAPOP core. It rebuilt the Brazil panel directly from the older raw DTA waves, including the 2006 survey, and then created the trust and democracy indices on that full matched benchmark panel before filtering to `year <= 2018` for the interaction regressions. The current repo's earlier pipeline started from the newer cleaned 2008-2019 core, which meant it dropped the 2006 benchmark wave and standardized the outcomes on a different universe.

## Municipality Matching

Municipality matching was not the main reason the coefficients differed. The notebook's manual municipality corrections are now reproduced in the benchmark builder, but the quantitative impact of those matching fixes is limited relative to the bigger upstream differences in the data source and index construction. The important matching change was rebuilding from the raw notebook waves rather than reusing the later clean comparable file.

## Treatment Assignment

Treatment assignment was not the main source of the divergence. The current cleaned municipality first-treatment file follows the same treated-by-year logic used in the notebook once the benchmark year mapping is restored.

## PCA And Outcome Construction

This was a major source of divergence. The trust benchmark uses `z_score_pca1_trust`, built from the first principal component of the eight trust items on the full matched notebook panel. The corrected democracy benchmark likewise uses `z_score_pca1_dem`, the standardized first principal component of the three-item democracy block. The archived notebook also contains a legacy weighted PC1/PC2 democracy combination, but that object is now retained only as a comparison variable rather than the main regression outcome.

## Fixed Effects And Vcov

Fixed effects and clustered standard errors also mattered. The benchmark notebook uses municipality and benchmark-year fixed effects with CRV1 clustering on `municipality_id + year`. The current repo's earlier fallback path was closer after the first audit, but the benchmark runner now uses `fixest` directly through `Rscript`, which aligns the FE and clustered vcov path much more closely with the notebook benchmark.

## Plotting Logic

The earlier current-repo figures were not plotting with the same visual grammar as the benchmark notebook. The updated plotting path now matches the notebook structure much more closely: base treatment and combined-effect bars, hatched Yes bars, black outlines, black markers, black CI lines, brackets, textbox annotations, notebook-like spacing, and `.pgf` exports to the benchmark figure paths.

## Final Benchmark Build

- Source years used to build the benchmark panel: [2006, 2008, 2010, 2012, 2014, 2016, 2018, 2021, 2023]
- Benchmark years after notebook remapping: [2006, 2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022]
- Benchmark regression sample: `year <= 2018`
- Controls: low_ed, female, white, married, working, age, log_gdp_pc, log_total_pop

## Trust Replication Check

category | expected_coef | expected_se | replicated_coef | replicated_se | abs_coef_diff | abs_se_diff | match_status
--- | --- | --- | --- | --- | --- | --- | ---
Female | 0.085 | 0.054 | 0.0822245439976678 | 0.0562763283736822 | 0.0027754560023321995 | 0.0022763283736821974 | exact_or_close
White | -0.042 | 0.053 | -0.0392022142943454 | 0.0535480509671675 | 0.0027977857056546013 | 0.0005480509671675002 | exact_or_close
Married | -0.049 | 0.058 | -0.0465866471027476 | 0.058429156027512 | 0.002413352897252405 | 0.0004291560275119996 | exact_or_close
Low Education | 0.124 | 0.029 | 0.122792205242151 | 0.0305937732905781 | 0.001207794757849004 | 0.0015937732905780995 | exact_or_close

## Summary

The main remaining difference after the first replication audit was not municipality matching. It was the benchmark notebook's distinct upstream survey build: missing 2006 in the current cleaned core, benchmark-wide standardization for the trust index, and the earlier benchmark-linked democracy outcome overwrite. Those issues are now corrected directly in the repository.

Trust benchmark check: Female: 0.082 (0.056) [exact_or_close], White: -0.039 (0.054) [exact_or_close], Married: -0.047 (0.058) [exact_or_close], Low Education: 0.123 (0.031) [exact_or_close]
