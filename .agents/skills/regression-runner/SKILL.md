# Regression Runner Skill

## Purpose

This skill runs reusable fixed-effects regressions from a YAML config file and writes standardized outputs for downstream empirical work.

It is designed for respondent-level or panel regressions that need:

- a configurable data path,
- outcome, treatment, and interaction terms,
- optional controls,
- optional fixed effects,
- one-way or two-way clustering,
- sample filters,
- paper-ready summary tables,
- and plotting-ready interaction-effect outputs.

## Main Use Cases

- Run a single fixed-effects regression from a config file.
- Run a series of interaction regressions that vary one interaction variable at a time.
- Save consistent regression tables, tidy coefficient files, model summaries, and plots.

## Supported Run Types

- `single_model`
- `interaction_series`

For `interaction_series`, the skill fits one model per interaction variable and computes:

- the treatment effect for the reference group,
- the treatment effect for the interacted group,
- the interaction difference,
- standard errors,
- 95% confidence intervals,
- p-values and stars,
- and a plotting-ready dataset with two bars per category.

## Backend

The intended backend is `pyfixest`, but this environment may not always support it. The current implementation attempts a Python fixed-effects workflow and falls back to a documented `statsmodels` fixed-effects implementation when `pyfixest` is unavailable. In this repository, the fallback is currently the active path because `pyfixest` could not be installed without a local LLVM toolchain.

## Required Config Fields

```yaml
run_type: "interaction_series"
data_path: "data/clean/example.parquet"
file_format: "parquet"
outcome: "y"
main_var: "treatment"
interaction_vars: ["female", "low_ed"]
controls: ["female", "low_ed", "age"]
fixed_effects: ["municipality_id", "survey_year"]
cluster: ["municipality_id", "survey_year"]
sample_filter: "survey_year <= 2018"
output_dir: "resources/example"
```

## Optional Config Fields

- `weight_var`
- `outcome_label`
- `category_labels`
- `figure_output_base`
- `plot_colors`
- `notes`

## Commands

Run the regression skill:

```bash
python .agents/skills/regression-runner/scripts/run_regression.py path/to/config.yml
```

## Workflow

1. Load and validate the YAML config.
2. Read the configured CSV or Parquet input.
3. Apply the sample filter if one is provided.
4. Build the regression formula from the requested outcome, controls, and fixed effects.
5. Fit the regression model for each requested interaction.
6. Compute the base-group effect, interacted-group effect, and interaction difference using the fitted covariance matrix.
7. Save tidy coefficients, interaction-effect tables, summaries, and plots.

## Outputs

For `interaction_series`, the skill writes:

- `config_used.yml`
- `tidy_results.csv`
- `interaction_effects.csv`
- `model_summaries.txt`
- `regression_table.csv`
- `regression_table.tex`

If `figure_output_base` is provided, it also writes:

- `*.png`
- `*.pdf`

## Examples

Example configs live in:

- `.agents/skills/regression-runner/examples/config_trust_interactions.yml`
- `.agents/skills/regression-runner/examples/config_democracy_interactions.yml`
- `.agents/skills/regression-runner/examples/config_generic_ols_fe.yml`
