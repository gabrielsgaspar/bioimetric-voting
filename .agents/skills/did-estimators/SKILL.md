# DID Estimators Skill

## Purpose

This skill runs reusable difference-in-differences estimators from a YAML config file and writes standardized outputs for downstream empirical work.

The supported estimators are:

- `callaway_santanna`
- `sun_abraham`
- `bjs`
- `dcdh`
- `twfe_dynamic`

The implementation is R-first and uses maintained package interfaces:

- Callaway-Sant'Anna via `did::att_gt()` and `did::aggte()`
- Sun-Abraham via `fixest::sunab()` inside `fixest::feols()`
- Borusyak-Jaravel-Spiess via `didimputation::did_imputation()`
- de Chaisemartin-D'Haultfoeuille via `DIDmultiplegtDYN::did_multiplegt_dyn()` by default and `DIDmultiplegt::did_multiplegt_old()` optionally
- Dynamic TWFE via `fixest::feols()` with `fixest::i()`

## When To Use Each Estimator

- Use `callaway_santanna` when you want transparent ATT(g,t) estimation and explicit aggregation choices.
- Use `sun_abraham` when you want staggered-adoption event-study plots with the `fixest` workflow.
- Use `bjs` when you want imputation-based staggered DID and horizon-based dynamic effects.
- Use `dcdh` when treatment is more general than simple first-treatment timing or when the user explicitly wants the de Chaisemartin-D'Haultfoeuille estimator.
- Use `twfe_dynamic` only as a baseline or comparability check. It can be misleading under staggered timing with heterogeneous effects.

## Required Inputs

The main interface is a YAML config file with fields such as:

```yaml
estimator: "sun_abraham"
data_path: "data/clean/panel.parquet"
file_format: "parquet"
outcome: "turnout"
unit_id: "municipality_id"
time_id: "year"
group_id: "year_first_treat"
treatment_var: null
controls:
  - "log_pop"
  - "gdp_pc"
cluster_var: "state"
weights_var: null
event_time_var: null
lead: 5
lag: 5
anticipation: 0
control_group: "nevertreated"
balanced_panel_required: false
output_dir: "resources/did/sunab_turnout"
notes: "example run"
```

## Commands

Install any missing R packages:

```bash
Rscript .agents/skills/did-estimators/scripts/install_packages.R
```

Run an estimator:

```bash
Rscript .agents/skills/did-estimators/scripts/run_estimator.R path/to/config.yml
```

Optional shell wrapper:

```bash
bash scripts/run_did_estimator.sh path/to/config.yml
```

## Workflow

1. Confirm the intended estimator and required treatment representation.
2. Point the config at a CSV, Parquet, Feather, or RDS file.
3. Set `group_id` for first-treatment timing designs.
4. Set `treatment_var` when an estimator needs a direct treatment measure or when treatment is not just first-treatment timing.
5. Set optional controls, weights, clustering, and horizon settings.
6. Run `run_estimator.R`.
7. Inspect the output folder for estimates, diagnostics, metadata, and event-study artifacts.

## Output Files

Every run writes:

- `tidy_estimates.csv`
- `model_summary.txt`
- `sample_diagnostics.csv`
- `run_metadata.yml`
- `config_used.yml`

Dynamic estimators also write:

- `event_study_estimates.csv`
- `event_study_plot.png`
- `event_study_plot.pdf`

Event-study plots use the paper's canonical graph defaults: 8 x 5 inch exports, 320 DPI PNGs and matching PDFs, serif text, light gray major grid, full black panel border, solid zero line, dotted reference-period line, no title, no subtitle, and no y-axis label unless `plot_y_label` is explicitly set. For DID event studies, the estimate series defaults to dark blue with linerange confidence intervals. Treat this boxed 8 x 5 style as the default for paper-style generated graphs unless a figure has a specific documented reason to depart from it.

Estimator-specific extra tables are saved with intuitive names like:

- `aggregate_att.csv`
- `group_time_att.csv`
- `calendar_aggregation.csv`
- `placebo_effects.csv`

Table outputs are CSV-only by default. Only write duplicate Parquet versions if
`output.save_parquet: true` is explicitly set in the run config.

## Practical Guidance

- `group_id` should represent first treatment period for staggered-adoption estimators.
- The Callaway-Sant'Anna implementation internally standardizes never-treated units to `0`, following `did::att_gt()` expectations.
- The Sun-Abraham and dynamic TWFE scripts build unit and time fixed effects automatically.
- The BJS script defaults to a first stage with unit and time fixed effects.
- The dCDH script defaults to the modern dynamic implementation and only uses the old mode if explicitly requested.
- When `group_id` is supplied to the dCDH estimator without a `treatment_var`, the skill constructs an absorbing binary treatment that turns on when `time_id >= group_id`.
- For paper-style figures, keep `omit_plot_title: true` or leave it unset. Set `plot_y_label` only when a labeled y-axis is needed for a standalone diagnostic figure.
- For Callaway-Sant'Anna, BJS, and dCDH plots, the default visual reference line is at event time `-2`; override it with `plot_reference_event_time` if the design uses a different anchor. Sun-Abraham and dynamic TWFE use `reference_event_time` because it is part of the estimator specification.

## Important Warnings

- Dynamic TWFE is included for baseline comparison, not as a preferred staggered-DID estimator.
- Never-treated units can be encoded as `NA` or `0` in the input. The scripts standardize them internally and record this in metadata.
- If treatment timing is ambiguous, the validation step should fail rather than guess.
- Duplicate `unit_id` x `time_id` rows are treated as an error.
- Character time variables are only coerced to numeric when the coercion is exact and documented.

## Examples

Example configs live in:

- `.agents/skills/did-estimators/examples/config_callaway_santanna.yml`
- `.agents/skills/did-estimators/examples/config_sun_abraham.yml`
- `.agents/skills/did-estimators/examples/config_bjs.yml`
- `.agents/skills/did-estimators/examples/config_dcdh.yml`
- `.agents/skills/did-estimators/examples/config_twfe_dynamic.yml`

## Estimator Selection Guidance

- Start with `callaway_santanna` if the user wants ATT(g,t) plus simple, group, calendar, and dynamic aggregations.
- Use `sun_abraham` if the user specifically wants a `fixest` event-study workflow.
- Use `bjs` if the user wants imputation-based dynamic effects and explicit horizon settings.
- Use `dcdh` when treatment is more general or when the user explicitly requests de Chaisemartin-D'Haultfoeuille.
- Use `twfe_dynamic` only as a comparability check and label it accordingly in writeups.
