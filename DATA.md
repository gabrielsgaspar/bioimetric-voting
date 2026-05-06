# DATA.md

## What this file is for

This file is a detailed map of the project's data: where each source comes from, what has been done to it, which clean files now exist, and which graphs and plots in the paper are built from which parts of the pipeline. It is written as a practical onboarding note for someone who wants to understand the repo without reverse-engineering every script from scratch.

## The basic data philosophy of the repository

The repo is organized around a standard research pipeline:

- `data/raw/` holds immutable source material
- `data/interim/` holds parsed files, audits, diagnostics, and harmonization reviews
- `data/clean/` holds analysis-ready datasets
- `resources/` holds generated tables, figures, and logs
- `paper/` reads from `resources/`, not from ad hoc working folders

The project is careful about keeping the administrative and survey pipelines separate until merges are explicit. That is a good design choice for this paper because the registry outcomes and the attitudinal outcomes come from fundamentally different data-generating processes.

## The raw data sources

## 1. TSE biometric-rollout sources

The BVR treatment timing is not downloaded from one single clean municipality-year panel. It is reconstructed from official legal and administrative material stored under:

- `data/raw/tse_bvr_legal/`

This folder includes:

- TSE resolutions
- TSE provimentos
- TSE news pages about biometric rollout
- ZIP attachments listing municipalities in some election cycles
- TSE electorate/open-data files used as verification sources for later years

Important raw files include:

- `www.tse.jus.br__legislacao__compilada__res__2008__resolucao-no-22-713-de-28-de-fevereiro-de-2008.html`
- `www.justicaeleitoral.jus.br__arquivos__tse-lista-de-cidades-onde-houve-votacao-em-urnas-com-leitor-biometrico-nas-eleicoes-2010.zip`
- `www.justicaeleitoral.jus.br__arquivos__tse-lista-de-localidades-onde-havera-recadastramento-biometrico-em-2012.zip`
- later TSE articles and electorate/open-data files used to calibrate 2014, 2016, and 2018 treatment status

## 2. TSE electorate files

The electorate panel comes from year-specific TSE electorate archives stored under:

- `data/raw/tse_eleitorado/2000/`
- `data/raw/tse_eleitorado/2002/`
- `data/raw/tse_eleitorado/2004/`
- `data/raw/tse_eleitorado/2006/`
- `data/raw/tse_eleitorado/2008/`
- `data/raw/tse_eleitorado/2010/`
- `data/raw/tse_eleitorado/2012/`
- `data/raw/tse_eleitorado/2014/`
- `data/raw/tse_eleitorado/2016/`
- `data/raw/tse_eleitorado/2018/`

Each folder contains a `perfil_eleitorado_<year>.zip` file. These are the raw administrative inputs for electorate size and composition.

## 3. IBGE files and municipality crosswalk inputs

IBGE-related source inputs live under:

- `data/raw/ibge/bd-tse_mun_ids.csv`
- `data/raw/ibge/ibge_municipios_api_v1_localidades_municipios.json`

These are used for:

- TSE-to-IBGE municipality matching
- municipality lookup tables
- validation of municipality identifiers and names

Additional municipal population and GDP covariates are fetched from IBGE SIDRA by the analysis scripts and saved directly as clean files.

## 4. LAPOP raw survey files

Raw LAPOP Brazil files currently in the repo are:

- `data/raw/lapop/2008/bra_2008_cy_por_p_v10.dta`
- `data/raw/lapop/2010/bra_2010_cy_por_p_v4.dta`
- `data/raw/lapop/2012/bra_2012_cy_por_p_v1.dta`
- `data/raw/lapop/2014/bra_2014_cy_spa-eng_p_v3-0.dta`
- `data/raw/lapop/2017/bra_2017_cy_spa-eng_p_v1-0.dta`
- `data/raw/lapop/2019/bra_2019_cy_spa-eng_p_v1-0.dta`
- `data/raw/lapop/2021/bra_2021_cy_spa-eng_p_v1-2.dta`

There is also:

- `data/raw/lapop/2023_package/bra23.rda`

But that 2023 raw package is not currently part of a fully integrated clean survey pipeline in the repo, and the recent backlash rewrite did not rely on it.

## What has been done to the raw data

## 1. Municipality-level BVR treatment timing has been reconstructed

This is one of the most important data-engineering tasks in the repo.

The script:

- `src/analysis/build_municipality_bvr_first_treat.py`

builds the clean treatment file:

- `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`
- `data/clean/tse_bvr/municipality_bvr_first_treat.csv`
- `data/clean/tse_bvr/municipality_bvr_first_treat_detailed.csv`

Key choices documented in `docs/TSE_BVR_DATASET_NOTES.md`:

- 2008 uses the pilot resolution directly
- 2010 uses the official TSE ZIP attachment listing municipalities where biometric voting occurred
- 2012 uses the official revision attachment listing municipalities apt for biometric identification
- 2014 is recovered from the official 2014 electorate file calibrated to the official 764-municipality benchmark using a `0.45` biometric-elector share cutoff
- 2016 is recovered from the official 2016 electorate open-data file calibrated to the official 1,540 full-biometric municipality benchmark using a `0.95` biometric-elector share cutoff
- 2018 uses the official status labels `Biometrico`, `Hibrido`, and `Sem biometria`

This is a serious reconstruction exercise, not a trivial import.

Important interim and audit files include:

- `data/interim/tse_bvr/tse_legal_sources_index.csv`
- `data/interim/tse_bvr/name_matching_review.csv`
- `data/interim/tse_bvr/hybrid_2018_review.csv`
- `resources/logs/tse_bvr_build_log.md`
- `resources/logs/tse_bvr_treatment_audit.md`

## 2. The TSE electorate files have been parsed into an education x gender panel

The script:

- `src/analysis/build_eleitorado_education_gender_panel.py`

turns the raw TSE electorate files into:

- `data/clean/tse_eleitorado/eleitorado_education_gender_2000_2018.parquet`
- `data/clean/tse_eleitorado/eleitorado_education_gender_2000_2018.csv`

Upstream parsing and harmonization work sits in:

- `src/cleaning/parse_tse_eleitorado.py`
- `src/tse_eleitorado_common.py`

The project maps education into:

- low education: `illiterate`, `reads_and_writes`, `incomplete_primary`, `complete_primary`
- high education: `incomplete_secondary`, `complete_secondary`, `incomplete_higher`, `complete_higher`

And gender into:

- `male`
- `female`
- `unknown`

A key deliberate choice is that the denominator for the composition shares includes `unknown`. So:

- `pct_voters_low_ed + pct_voters_high_ed` can be less than `1`
- `pct_voters_men + pct_voters_women` can be less than `1`

That is not a bug. It is a conservative design choice to avoid redistributing unknown cases into substantive categories.

## 3. The final TSE clean panel has been built

The script:

- `src/analysis/build_tse_clean_panel.py`

combines the electorate panel and the treatment file into:

- `data/clean/tse/tse_clean_panel_2000_2018.parquet`
- `data/clean/tse/tse_clean_panel_2000_2018.csv`

Key facts from `docs/TSE_CLEAN_PANEL_NOTES.md`:

- 55,661 municipality-election rows
- 5,571 municipalities
- 2,794 ever treated
- 2,777 never treated
- 1,533 municipality-year rows flagged as hybrid in 2018

The retained election years are:

- 2000
- 2002
- 2004
- 2006
- 2008
- 2010
- 2012
- 2014
- 2016
- 2018

The final key is unique on `year_election + municipality_id`.

## 4. IBGE municipal covariates have been fetched and aligned

Two clean IBGE-based covariate files now exist:

- `data/clean/ibge/municipality_gdp_population_survey_years.parquet`
- `data/clean/ibge/municipality_population_2021.parquet`

The first is used in the trust regressions and contains municipal GDP and population aligned to the survey years. The second was created specifically for the 2021 backlash regressions.

These covariates are pulled from official IBGE SIDRA tables by the analysis scripts rather than being hand-entered.

## 5. LAPOP Brazil has been harmonized into a comparable core

The main harmonization note is:

- `docs/LAPOP_BRAZIL_HARMONIZATION_NOTES.md`

The key clean comparable file is:

- `data/clean/lapop/lapop_brazil_core_2008_2019.parquet`

This file contains `10,009` respondents.

Important harmonization choices:

- the public comparable core uses actual survey years `2008, 2010, 2012, 2014, 2017, 2019`
- 2021 is not folded into this comparable core
- municipality and state labels are decoded and normalized
- `b47` and `b47a` are harmonized into a common `trust_elections` item
- education is harmonized conservatively from survey coding into broad categories
- `white` is coded from the LAPOP ethnicity/race variable as white versus non-white

The harmonizer preserves location fields for later municipality linkage but does not itself assign official municipality IDs; that happens in the merge stages used by the regression pipelines.

## 6. PCA indices have been built for trust and democracy

The script:

- `src/analysis/build_lapop_pca_indices.py`

creates:

- `data/clean/lapop/lapop_brazil_with_pca_indices.parquet`
- `data/clean/lapop/lapop_brazil_with_pca_indices.csv`

It also produces a whole set of PCA outputs under `resources/lapop/pca/`.

Important choices from `docs/LAPOP_PCA_INDICES_NOTES.md`:

- missing PCA inputs are median-imputed
- variables are standardized before PCA
- the main paper indices use the first principal component
- `democracy_satisfaction` is reversed before PCA so larger values mean more democratic satisfaction

The trust block uses eight items:

- respect for political institutions
- protection of rights
- pride in the system
- support for the system
- confidence in parties
- confidence in municipal government
- confidence in the president
- confidence in elections

The democracy block uses three items:

- democracy is the best form of government
- satisfaction with democracy
- whether those who govern care about people like the respondent

The PCA outputs include:

- loadings CSVs
- summary CSVs
- TeX tables
- explained-variance plots
- a note comparing the main democracy index to the older notebook's legacy combination

## 7. LAPOP trust regression files have been built twice: once as a clean default and once as a notebook-style correction

The default trust-regression script is:

- `src/analysis/run_lapop_trust_regressions.py`

This produces:

- `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready.parquet`

But the repo also discovered that the older benchmark notebook underlying the draft paper did not line up with this cleaned default. That led to the replication-debug workflow:

- `src/analysis/debug_lapop_trust_replication.py`
- `src/analysis/run_lapop_trust_regressions_replicated.py`

Those produce:

- `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready_corrected.parquet`
- updated trust and democracy regression outputs
- updated main trust figures and tables

This correction is a major piece of work. It means the repository no longer silently mixes a newer cleaned LAPOP core with a paper section that was implicitly written from an older notebook universe.

Key benchmark facts from the corrected trust workflow:

- linked benchmark sample: `11,008` respondents
- municipalities in the linked benchmark sample: `235`
- main regression sample after controls and non-missing outcomes: `10,632`

## 8. A separate 2021 backlash file has now been built

The recently added script:

- `src/analysis/run_lapop_backlash_regressions.py`

creates:

- `data/clean/lapop/lapop_brazil_backlash_2021_regression_ready.parquet`
- `data/clean/ibge/municipality_population_2021.parquet`
- `resources/tables/lapop_backlash_2021_main_table.tex`

This was added because the public 2021 LAPOP wave contained the electoral-integrity questions, while the more ambitious 2023 design could not be cleanly reproduced from public access in this environment.

Useful matching facts from the 2021 backlash build:

- 2,989 rows had municipality/state labels
- 2,971 matched to IBGE municipality IDs
- 18 remained unmatched
- 988 unique municipalities appear in the matched sample

## The main clean datasets you can work from

If you want the shortest list of "real" working datasets, start with these:

- `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`
- `data/clean/tse_eleitorado/eleitorado_education_gender_2000_2018.parquet`
- `data/clean/tse/tse_clean_panel_2000_2018.parquet`
- `data/clean/ibge/municipality_gdp_population_survey_years.parquet`
- `data/clean/ibge/municipality_population_2021.parquet`
- `data/clean/lapop/lapop_brazil_core_2008_2019.parquet`
- `data/clean/lapop/lapop_brazil_with_pca_indices.parquet`
- `data/clean/lapop/lapop_brazil_with_pca_indices_regression_ready_corrected.parquet`
- `data/clean/lapop/lapop_brazil_backlash_2021_regression_ready.parquet`

## Matching and validation work already done

Several validation layers already exist in the repo.

### TSE / municipality validation

- municipality names are standardized to lowercase ASCII
- matching is constrained within state
- fuzzy matching is only used to generate candidates, not to silently force final matches
- manual overrides are documented
- clean panel keys are validated to be unique

### LAPOP / municipality validation

For the default LAPOP trust workflow:

- 9,919 of 10,009 respondents match to municipalities
- 90 respondents are unmatched
- 187 respondents use manual municipality overrides

For the 2021 backlash workflow:

- 2,989 rows have municipality/state labels
- 2,971 rows match to IBGE municipality IDs
- 18 rows remain unmatched
- 988 unique municipalities appear in the matched sample

This is useful context because the paper's survey sections depend on municipal linkage being good enough to assign BVR exposure credibly.

## Graphs and plots shown in the paper

Below is a map of the figures and plots that the manuscript currently shows, along with where they live and how they are generated.

## Main-text figures

### 1. Electoral Identification Materials

Files:

- `resources/context/voter_id.jpeg`
- `resources/context/biometric_example.jpeg`

Used in:

- `paper/sections/background.tex`

What they are:

- contextual images, not statistical plots
- they illustrate the voter ID card and biometric verification process

### 2. Municipal Rollout of Biometric Registration

File used by the paper:

- `resources/context/bvr_rollout_timeline.tex`

Supporting summary:

- `resources/context/bvr_rollout_summary.csv`

Generated by:

- `src/analysis/build_bvr_rollout_figure.py`

Used in:

- `paper/sections/institutional_background.tex`

What it shows:

- counts of municipalities entering BVR in each election cycle

### 3. Biometric Registration and Electorate Size

File:

- `resources/images/regressions/twfe_dynamic/log_num_voters/event_study_plot.pdf`

Used in:

- `paper/sections/bvr_and_electorate_size.tex`

What it shows:

- dynamic TWFE event-study coefficients for `log_num_voters`

Where the underlying estimates live:

- `resources/did/twfe_dynamic/log_num_voters/`

How it is generated:

- via the DiD estimator workflow under `.agents/skills/did-estimators/`
- the reusable shell wrapper is `scripts/run_did_estimator.sh`

### 4. Biometric Registration and Education Composition

Files:

- `resources/images/regressions/twfe_dynamic/pct_voters_low_ed/event_study_plot.pdf`
- `resources/images/regressions/twfe_dynamic/pct_voters_high_ed/event_study_plot.pdf`

Used in:

- `paper/sections/bvr_and_electorate_size.tex`

What they show:

- dynamic TWFE event-study coefficients for the low-education and high-education electorate shares

Underlying estimate folders:

- `resources/did/twfe_dynamic/pct_voters_low_ed/`
- `resources/did/twfe_dynamic/pct_voters_high_ed/`

### 5. Biometric Registration and Political Trust by Respondent Characteristics

Files:

- `resources/lapop/figures/trust_interactions_barplot.pdf`
- `resources/lapop/figures/democracy_interactions_barplot.pdf`

Used in:

- `paper/sections/bvr_and_political_trust.tex`

What they show:

- barplots of the base treatment effect and the interacted-group treatment effect for each respondent characteristic
- one figure for institutional trust
- one figure for democratic attitudes

Generated by:

- `src/analysis/run_lapop_trust_regressions_replicated.py`

There is also a dedicated figure builder:

- `src/analysis/build_lapop_interaction_barplots.py`

## Appendix figures

### 6. Excluding Hybrid Municipalities: Electorate Size

File:

- `resources/images/regressions/twfe_dynamic_excl_hybrid/log_num_voters/event_study_plot.pdf`

Used in:

- `paper/appendix/appendix_main.tex`

Generated by:

- `src/analysis/run_twfe_nonhybrid_robustness.py`

### 7. Excluding Hybrid Municipalities: Education Composition

Files:

- `resources/images/regressions/twfe_dynamic_excl_hybrid/pct_voters_low_ed/event_study_plot.pdf`
- `resources/images/regressions/twfe_dynamic_excl_hybrid/pct_voters_high_ed/event_study_plot.pdf`

Used in:

- `paper/appendix/appendix_main.tex`

### 8. Alternative Estimator Comparison Plots

Files:

- `resources/images/regressions/estimator_comparison/log_num_voters/estimator_comparison.pdf`
- `resources/images/regressions/estimator_comparison/pct_voters_low_ed/estimator_comparison.pdf`
- `resources/images/regressions/estimator_comparison/pct_voters_high_ed/estimator_comparison.pdf`

Used in:

- `paper/appendix/appendix_main.tex`

Generated by:

- `src/analysis/build_did_estimator_comparison.py`

Underlying estimates are stored under:

- `resources/did/estimator_comparison/`

### 9. PCA Explained-Variance Plots

Files:

- `resources/lapop/pca/trust_explained_variance_main.pdf`
- `resources/lapop/pca/democracy_explained_variance_main.pdf`

Used in:

- `paper/appendix/appendix_main.tex`

Generated by:

- `src/analysis/build_lapop_pca_indices.py`

## Tables that anchor the paper's results

These are not graphs, but they are central paper outputs and worth listing here because they are generated artifacts tied directly to the data pipeline.

### Main-text tables

- `resources/tables/lapop_pca_decomposition_main.tex`
- `resources/tables/lapop_backlash_2021_main_table.tex`

### Appendix / supporting tables

- `resources/tables/twfe_dynamic_main_table.tex`
- `resources/tables/lapop_trust_interactions_main_table.tex`

The trust-interaction table is especially important because it captures the benchmark-replicated survey results that now underpin the paper's trust section.

## Logs and notes that document the data work

The repo already includes a lot of durable documentation. The most useful files are:

- `docs/TSE_BVR_DATASET_NOTES.md`
- `docs/TSE_CLEAN_PANEL_NOTES.md`
- `docs/LAPOP_BRAZIL_HARMONIZATION_NOTES.md`
- `docs/LAPOP_PCA_INDICES_NOTES.md`
- `docs/LAPOP_TRUST_REGRESSIONS_NOTES.md`
- `docs/LAPOP_TRUST_REPLICATION_DEBUG_NOTES.md`
- `docs/LAPOP_BACKLASH_REGRESSIONS_NOTES.md`
- `docs/DID_ESTIMATORS_NOTES.md`

And the key logs are:

- `resources/logs/tse_bvr_build_log.md`
- `resources/logs/tse_clean_panel_build_log.md`
- `resources/logs/tse_eleitorado_build_log.md`
- `resources/logs/lapop_brazil_build_log.md`
- `resources/logs/lapop_pca_indices_log.md`
- `resources/logs/lapop_trust_regressions_log.md`
- `resources/logs/lapop_trust_replication_debug_log.md`
- `resources/logs/lapop_backlash_regressions_log.md`

## The biggest data challenges in the repo

These are the issues a future user should understand before trusting every result mechanically.

## 1. BVR timing is partly reconstructed, not directly downloaded

The treatment file is carefully built, but later years rely on calibration and administrative status recovery, not on one perfect municipality annex covering the whole period.

## 2. Hybrid treatment is only partially observed

The repo has explicit 2018 hybrid coding, but not a perfect municipality-level hybrid history for all earlier years.

## 3. LAPOP location linkage is good but not automatic

Survey municipality labels have to be decoded, normalized, and matched. Manual overrides are part of the pipeline.

## 4. The trust section had a notebook-versus-clean-core mismatch

This has been substantially repaired, but it means there is more than one plausible LAPOP "main file" in the repo and users need to know which one underlies which result.

## 5. The later-wave backlash design is constrained by public-data access

The current reproducible section uses 2021, not the more ambitious 2023/2022 design envisioned in the draft.

## The most recent data work that has been done

The most recent additions reflected in the current paper state are:

- a rewritten and reproducible backlash pipeline using the public Brazil 2021 LAPOP wave
- a new clean file `lapop_brazil_backlash_2021_regression_ready.parquet`
- a new clean IBGE file `municipality_population_2021.parquet`
- a new generated table `resources/tables/lapop_backlash_2021_main_table.tex`
- updated manuscript text in the backlash section to match what the public data can actually support

Before that, one of the biggest repo improvements was the trust-replication repair:

- rebuilding the benchmark-style LAPOP regression-ready file
- aligning the trust section with the older notebook workflow
- refreshing the trust and democracy interaction figures and main table

## If you want to regenerate the data products

The main scripts to know are:

- `src/analysis/build_municipality_bvr_first_treat.py`
- `src/analysis/build_eleitorado_education_gender_panel.py`
- `src/analysis/build_tse_clean_panel.py`
- `src/analysis/build_bvr_rollout_figure.py`
- `src/analysis/build_lapop_pca_indices.py`
- `src/analysis/debug_lapop_trust_replication.py`
- `src/analysis/run_lapop_trust_regressions_replicated.py`
- `src/analysis/run_lapop_backlash_regressions.py`
- `src/analysis/build_did_estimator_comparison.py`
- `src/analysis/run_twfe_nonhybrid_robustness.py`
- `src/analysis/build_twfe_dynamic_main_table.py`

The DiD event-study plots themselves are tied to the reusable estimator workflow under:

- `.agents/skills/did-estimators/`
- `scripts/run_did_estimator.sh`

## Bottom line

The repository already contains a serious amount of data work. The treatment timing, electorate panel, LAPOP harmonization, PCA construction, regression-ready survey files, and paper-ready outputs are all in place. The main data story is that the administrative side is the clean backbone of the project, while the LAPOP side is richer but more fragile because of matching, sample comparability, and public-access constraints. Anyone extending the paper should keep that asymmetry in mind.
