# Repository Structure

This file is the repository map. It explains what each major folder is for, which files are the important ones inside it, and where to look when you need to understand or extend a specific part of the project.

## How To Read This Repository

The repository is organized around a standard research pipeline:

1. raw source files are stored under `data/raw/`,
2. parsed and audited intermediate products live under `data/interim/`,
3. analysis-ready files live under `data/clean/`,
4. reusable code lives under `src/`,
5. generated tables, figures, and logs live under `resources/`,
6. the paper itself lives under `paper/`,
7. durable notes and replication decisions live under `docs/`,
8. repository-local Codex skills live under `.agents/skills/`.

If you are unsure where a file belongs, use that sequence.

## Top-Level Folders

### `.agents/`

Repository-local skills and reusable automation for Codex.

- `.agents/skills/did-estimators/`
  DiD estimation skill used for dynamic TWFE event studies and alternative staggered-adoption estimators in R.
- `.agents/skills/lapop-brazil-harmonizer/`
  LAPOP Brazil download, parsing, harmonization, and validation skill.
- `.agents/skills/regression-runner/`
  Reusable regression skill for fixed-effects and interaction regressions, including plotting-ready outputs.
- `.agents/skills/tse-bvr-treatment-dataset/`
  Skill for building the municipality BVR treatment file from legal and administrative sources.
- `.agents/skills/tse-eleitorado-education-gender/`
  Skill for constructing the electorate-by-education-and-gender panel.
- `.agents/skills/literature-review/`
  Literature-review skill scaffold for manuscript support.

### `data/`

The data pipeline is split into raw, interim, and clean products.

### `docs/`

Durable notes on data construction, PCA choices, treatment timing, trust regressions, and replication issues.

### `paper/`

The LaTeX manuscript, modular section files, references, and appendix.

### `resources/`

Generated figures, tables, logs, and other paper-ready outputs. The manuscript should read from here rather than from ad hoc folders.

### `scripts/`

Small command-line wrappers that launch reusable pipelines.

### `src/`

Reusable Python analysis, cleaning, and download code.

### `tests/`

Reserved for lightweight tests. It is currently empty.

## Data Folders

### `data/raw/`

Immutable source files. Nothing here should be overwritten manually.

#### `data/raw/ibge/`

- `bd-tse_mun_ids.csv`
  Main crosswalk between TSE municipality identifiers and IBGE municipality identifiers.
- `ibge_municipios_api_v1_localidades_municipios.json`
  Raw IBGE municipality reference file used for harmonization and validation.

#### `data/raw/lapop/`

Raw LAPOP source files and wave-specific downloads. This folder is the starting point for LAPOP harmonization work.

#### `data/raw/tse_bvr_legal/`

Official TSE legal and institutional documents used to reconstruct BVR rollout timing.

- TSE resolutions and provimentos.
- TSE news pages about biometric expansion.
- Zips and PDFs listing municipalities with biometric implementation or hybrid voting.

#### `data/raw/tse_eleitorado/`

Raw TSE electorate files used to build the municipality x education x gender panel.

### `data/interim/`

Intermediate products, parsed files, diagnostics, and audit tables.

#### `data/interim/lapop/`

- `source_inventory.csv`
  Inventory of LAPOP source files used in the repository.
- `variable_crosswalk.csv`
  Crosswalk between raw LAPOP variable names and harmonized variables.
- `wave_variable_availability.csv`
  Which variables exist in which LAPOP waves.

#### `data/interim/tse/`

- `tse_clean_panel_diagnostics.csv`
  Diagnostics for the municipality-year TSE clean panel.
- `tse_clean_panel_2000_2018_excl_hybrid_municipalities.csv`
  Interim restricted sample that excludes hybrid municipalities for robustness checks.

#### `data/interim/tse_bvr/`

Audit and parsing products for the BVR treatment file.

- duplicate and benchmark audits,
- parsed legal-source rows,
- hybrid-municipality reviews,
- name-matching reviews,
- source indexes.

#### `data/interim/tse_eleitorado/`

Parsed and harmonized year-by-year electorate files plus schema and source diagnostics.

### `data/clean/`

Analysis-ready files used directly by scripts and regressions.

#### `data/clean/ibge/`

- `municipality_gdp_population_survey_years.parquet`
- `municipality_gdp_population_survey_years.csv`

Municipal GDP and population covariates aligned to the survey years used in LAPOP analysis.

#### `data/clean/lapop/`

- `lapop_brazil_core_2008_2019.parquet`
  Harmonized LAPOP Brazil comparable core.
- `lapop_brazil_2021_selected_questions.parquet`
  Focused extract for later-wave selected items.
- `lapop_brazil_with_pca_indices.parquet`
  Core LAPOP file with trust and democracy PCA indices added.
- `lapop_brazil_with_pca_indices_regression_ready.parquet`
  Baseline regression-ready LAPOP file used by the reusable regression pipeline.
- `lapop_brazil_with_pca_indices_regression_ready_corrected.parquet`
  Corrected notebook-replication version used to audit and rerun trust/democracy interaction regressions.

CSV companions exist for all main clean LAPOP products.

#### `data/clean/tse/`

- `tse_clean_panel_2000_2018.parquet`
  Main municipality-year administrative panel used for electorate-size and composition results.

#### `data/clean/tse_bvr/`

- `municipality_bvr_first_treat.parquet`
  Main municipality first-treatment timing file.
- `municipality_bvr_first_treat_detailed.csv`
  Detailed treatment timing file with source-level information.
- `ibge_municipalities.csv`
  Clean municipality lookup used in treatment construction and merges.

#### `data/clean/tse_eleitorado/`

- `eleitorado_education_gender_2000_2018.parquet`
  Municipality x year electorate panel by education and gender.

## Code Folders

### `src/data/`

Download utilities for source material.

- `download_ibge_municipalities.py`
  Downloads or refreshes IBGE municipality reference data.
- `download_tse_bvr_legal_docs.py`
  Downloads TSE legal and institutional documents related to BVR rollout.
- `download_tse_eleitorado.py`
  Downloads TSE electorate files by year.

### `src/cleaning/`

Reusable parsing and harmonization code.

- `harmonize_tse_municipalities.py`
  Standardizes municipality identifiers and names across sources.
- `match_tse_to_ibge.py`
  Builds and audits the TSE-to-IBGE municipality crosswalk.
- `parse_tse_bvr_legal_docs.py`
  Parses TSE legal and institutional documents into structured rollout evidence.
- `parse_tse_eleitorado.py`
  Parses raw electorate files into standardized intermediate data.

### `src/analysis/`

Main reproducible analysis scripts. This is the most important code folder for day-to-day empirical work.

- `audit_tse_bvr_counts.py`
  Audits treatment counts against official benchmarks.
- `build_bvr_rollout_figure.py`
  Builds the rollout timeline figure and summary objects used in the paper.
- `build_did_estimator_comparison.py`
  Produces event-study comparison plots across estimators.
- `build_eleitorado_education_gender_panel.py`
  Constructs the municipality-level electorate-by-education-and-gender panel.
- `build_lapop_interaction_barplots.py`
  Builds LAPOP interaction plots from regression outputs.
- `build_lapop_pca_indices.py`
  Constructs trust and democracy PCA indices and explained-variance outputs.
- `build_municipality_bvr_first_treat.py`
  Builds the main municipality BVR first-treatment file.
- `build_tse_clean_panel.py`
  Constructs the main municipality-year administrative panel used in the paper.
- `build_twfe_dynamic_main_table.py`
  Builds the appendix TWFE coefficient table.
- `debug_lapop_trust_replication.py`
  Audits the notebook-paper mismatch in LAPOP trust/democracy interactions and builds the corrected replication-ready dataset.
- `plot_style.py`
  Shared plotting style helpers for LaTeX-consistent figure output.
- `run_lapop_trust_regressions.py`
  Baseline LAPOP trust/democracy interaction regression runner used by the reusable regression pipeline.
- `run_lapop_trust_regressions_replicated.py`
  Notebook-style rerun of the trust/democracy interaction regressions that now refreshes the main LAPOP regression outputs.
- `run_twfe_nonhybrid_robustness.py`
  Re-runs dynamic TWFE after excluding hybrid municipalities.

### `src/`

Two shared helper modules also live directly under `src/`.

- `tse_bvr_common.py`
  Shared utilities for the BVR treatment dataset workflow.
- `tse_eleitorado_common.py`
  Shared utilities for the electorate-by-education-and-gender workflow.

## Skills

### `.agents/skills/did-estimators/`

R-based DiD skill for the administrative panel.

- `scripts/estimator_twfe_dynamic.R`
  Main dynamic TWFE estimator and plot generator.
- `scripts/estimator_bjs.R`
  Borusyak-Jaravel-Spiess implementation.
- `scripts/estimator_callaway_santanna.R`
  Callaway-Sant'Anna implementation.
- `scripts/estimator_dcdh.R`
  dCDH implementation.
- `scripts/estimator_sun_abraham.R`
  Sun-Abraham implementation retained for reference even if not used in the current paper.
- `scripts/helpers.R`, `scripts/save_outputs.R`, `scripts/validate_inputs.R`
  Shared helpers for formatting, saving, and validating estimator runs.
- `examples/`
  YAML configs for each outcome and estimator.

### `.agents/skills/lapop-brazil-harmonizer/`

Python skill for LAPOP download, harmonization, and validation.

- `scripts/discover_lapop_sources.py`
  Discovers available LAPOP Brazil sources.
- `scripts/download_lapop_brazil.py`
  Downloads official LAPOP source files when available.
- `scripts/parse_lapop_brazil.py`
  Parses raw LAPOP Brazil data.
- `scripts/harmonize_variables.py`
  Harmonizes variables across waves.
- `scripts/build_core_panel.py`
  Builds the comparable LAPOP Brazil core panel.
- `scripts/build_requested_extract.py`
  Builds smaller requested LAPOP extracts.
- `scripts/validate_panel.py`
  Validates the comparable panel.
- `scripts/run_lapop_harmonizer.py`
  Main entry point for the skill.

### `.agents/skills/regression-runner/`

Reusable regression skill for FE and interaction models.

- `scripts/run_regression.py`
  Main config-driven regression entry point.
- `scripts/build_formula.py`
  Builds formulas from YAML config inputs.
- `scripts/fit_model_pyfixest.py`
  Fits the configured regression, with fallback handling when needed.
- `scripts/extract_results.py`
  Extracts tidy coefficients and interaction effects.
- `scripts/compute_linear_combinations.py`
  Computes combined treatment effects and uncertainty.
- `scripts/build_regression_table.py`
  Builds CSV and LaTeX regression tables.
- `scripts/plot_interaction_bars.py`
  Builds paired interaction-effect barplots.
- `examples/`
  Example configs for trust, democracy, and generic FE regressions.

### `.agents/skills/tse-bvr-treatment-dataset/`

Skill focused on BVR rollout timing and treatment-file construction.

### `.agents/skills/tse-eleitorado-education-gender/`

Skill focused on the electorate-by-education-and-gender panel.

## Resources

### `resources/`

Paper assets rebuilt from the current resource baseline.

#### `resources/context/`

- `biometric_example.jpeg`
  Context image for the institutional background section.
- `voter_id.jpeg`
  Context image for the institutional background section.
- `bvr_rollout_timeline.tex`
  LaTeX-native rollout figure drawn from the treatment data.
- `bvr_rollout_summary.csv`
  Data summary used for the rollout figure.

#### `resources/images/regressions/`

Reserved for paper-facing regression figures that are not LAPOP- or DID-specific.

### `resources/did/`

Generated outputs for administrative-panel DiD work.

- `twfe_dynamic/`
  Main dynamic TWFE outputs by outcome.
- `twfe_dynamic_excl_hybrid/`
  Dynamic TWFE outputs excluding hybrid municipalities.
- `estimator_comparison/`
  Alternative-estimator comparison outputs and run logs.

### `resources/lapop/`

Generated outputs for survey-based analysis.

#### `resources/lapop/pca/`

PCA loadings, explained-variance summaries, LaTeX tables, and explained-variance figures for trust and democracy indices.

- These files feed both the main-text trust section and the appendix figures on explained variance.
- The main paper now uses standardized PCA1 indices for both trust in institutions and trust in democracy.

#### `resources/lapop/regressions/`

Regression outputs for trust and democracy interaction analyses.

- `trust_interactions/`
  Current benchmark-aligned trust interaction outputs.
- `democracy_interactions/`
  Current benchmark-aligned democracy interaction outputs, now aligned to the PCA1 democracy index used in the paper text.

#### `resources/lapop/figures/`

Separate barplots for trust and democracy interactions.

### `resources/tables/`

Paper-facing tables.

- `twfe_dynamic_main_table.tex`
  Main TWFE coefficient table now used in the appendix.
- `lapop_trust_interactions_main_table.tex`
  Summary table for LAPOP trust interactions.
- `lapop_pca_decomposition_main.tex`
  Main-text PCA decomposition table used in the political-trust section.

### `resources/logs/`

Machine-readable or human-readable logs documenting major builds and audits.

- LAPOP harmonization and PCA logs,
- trust-regression logs,
- notebook-replication debug logs,
- TSE BVR build and audit logs,
- clean-panel logs,
- TWFE run logs.

## Paper Folder

### `paper/main.tex`

Main manuscript entry point.

### `paper/inputs/`

LaTeX packages, settings, macros, and notation inputs.

### `paper/frontmatter/`

Title page and abstract.

### `paper/sections/`

Main paper text, split by section.

- `introduction.tex`
- `institutional_background.tex`
- `bvr_and_electorate_size.tex`
- `bvr_and_political_trust.tex`
- `backlash_and_electoral_integrity.tex`
- `conclusion.tex`
- `literature.tex`

The current manuscript entry point, `paper/main.tex`, uses exactly these live section files. In particular, `bvr_and_political_trust.tex` is organized around two subsections, `Building Trust and Democracy Indices` and `BVR Exposure and Political Attitudes`, with the PCA decomposition table in the main text and the explained-variance figures moved to the appendix.

### `paper/appendix/`

- `appendix_main.tex`
  Appendix figures, robustness exercises, and extra tables.

### `paper/references/`

- `references.bib`
  Main bibliography file used by the manuscript.

## Docs Folder

The `docs/` folder stores durable notes that explain how major datasets and empirical objects were built.

- `TSE_BVR_DATASET_NOTES.md`
  Notes on treatment timing and source construction.
- `TSE_CLEAN_PANEL_NOTES.md`
  Notes on the clean administrative panel.
- `TSE_ELEITORADO_EDU_GENDER_NOTES.md`
  Notes on the education-and-gender electorate panel.
- `LAPOP_BRAZIL_HARMONIZATION_NOTES.md`
  Notes on harmonizing LAPOP waves.
- `LAPOP_PCA_INDICES_NOTES.md`
  Notes on trust and democracy PCA indices.
- `LAPOP_TRUST_REGRESSIONS_NOTES.md`
  Notes on the baseline LAPOP trust/democracy regressions.
- `LAPOP_TRUST_REPLICATION_DEBUG_NOTES.md`
  Notes on the notebook-replication mismatch and fix.
- `DID_ESTIMATORS_NOTES.md`
  Notes on estimator choices and implementation details for staggered-adoption analysis.

## Scripts Folder

### `scripts/run_did_estimator.sh`

Shell wrapper for launching the DiD estimator skill from the command line.

## Most Useful Starting Points

If you are new to the repository, these are the best first files to open:

1. [README.md](README.md)
2. [PROJECT.md](PROJECT.md)
3. [AGENTS.md](AGENTS.md)
4. [paper/main.tex](paper/main.tex)
5. [build_tse_clean_panel.py](src/analysis/build_tse_clean_panel.py)
6. [build_lapop_pca_indices.py](src/analysis/build_lapop_pca_indices.py)
7. [run_lapop_trust_regressions_replicated.py](src/analysis/run_lapop_trust_regressions_replicated.py)
8. [appendix_main.tex](paper/appendix/appendix_main.tex)
