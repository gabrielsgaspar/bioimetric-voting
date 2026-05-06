# DID Estimators Notes

## Scope

This note documents the reusable difference-in-differences skill under `.agents/skills/did-estimators/`. The goal is to provide a consistent YAML-driven interface for multiple staggered-adoption estimators while keeping outputs tidy and reproducible.

## Estimator Mapping

- Callaway-Sant'Anna uses `did::att_gt()` and `did::aggte()`.
- Sun-Abraham uses `fixest::feols()` with `fixest::sunab()`.
- Borusyak-Jaravel-Spiess uses `didimputation::did_imputation()`.
- de Chaisemartin-D'Haultfoeuille defaults to `DIDmultiplegtDYN::did_multiplegt_dyn()` and optionally supports `DIDmultiplegt::did_multiplegt_old()`.
- Dynamic TWFE uses `fixest::feols()` with `fixest::i()` and should be treated as a baseline estimator only.

## Required Data Structure

- Long panel data with one row per unit-period.
- A unique `unit_id` x `time_id` combination.
- An outcome variable.
- A first-treatment timing variable `group_id` for staggered-adoption estimators.
- Optionally, a direct treatment variable `treatment_var` for more general treatment paths.

## Validation Rules

- Duplicate `unit_id` x `time_id` rows are treated as an error.
- Time must be numeric or safely coercible to numeric.
- `group_id` is interpreted as first-treatment timing and never-treated values can be `NA` or `0`.
- Controls, weights, and clustering variables must exist if specified.
- Dynamic estimators require either `group_id` or a usable `event_time_var`.

## Common Pitfalls

- Mis-specifying `group_id` as treatment status instead of first treatment period.
- Passing repeated cross sections to scripts that assume a panel.
- Interpreting dynamic TWFE coefficients causally under heterogeneous treatment effects.
- Forgetting that dCDH can handle more general treatment paths than the simpler first-treatment estimators.
- Supplying event-study windows that are unsupported by the data.

## Interpretation Notes

- Callaway-Sant'Anna is useful for explicit ATT(g,t) estimation and transparent aggregation choices.
- Sun-Abraham is convenient for event-study visualization in the `fixest` ecosystem.
- BJS estimates imputation-based treatment effects and supports horizons and pretrend diagnostics.
- dCDH is flexible for settings with switching or more general treatment variation.
- Dynamic TWFE can be useful for replication or comparability, but it should not be treated as the preferred design under staggered timing.

## Output Conventions

Each run writes tidy estimates, a model summary, sample diagnostics, metadata, and the used config. Dynamic estimators also write event-study tables and plots. Estimator-specific extra tables are saved with intuitive names.

## Package-Documentation Mapping

- `did::att_gt()` and `did::aggte()` follow the `did` package documentation for group-time ATT and aggregations.
- `fixest::sunab()` and `aggregate.fixest()` follow the `fixest` documentation for Sun-Abraham aggregation.
- `didimputation::did_imputation()` follows the package interface for static and horizon-specific estimates.
- `DIDmultiplegtDYN::did_multiplegt_dyn()` follows the modern dynamic dCDH interface.
- `DIDmultiplegt::did_multiplegt_old()` is exposed only when explicitly requested.

## Recommended Use

- Start with Callaway-Sant'Anna or Sun-Abraham for standard staggered-adoption work.
- Add BJS as an imputation-based robustness check.
- Use dCDH when treatment is not well summarized by first-treatment timing alone.
- Keep dynamic TWFE in the appendix or as a baseline comparison unless there is a strong design reason to foreground it.
