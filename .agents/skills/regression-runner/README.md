# Regression Runner

This skill provides a reusable, config-driven regression pipeline for fixed-effects regressions and interaction-series summaries.

It is especially useful when a project needs repeatable output files rather than ad hoc notebook cells.

## Run

```bash
python .agents/skills/regression-runner/scripts/run_regression.py path/to/config.yml
```

## Current Note

The preferred backend is `pyfixest`, but this repository currently uses a documented `statsmodels` fixed-effects fallback because `pyfixest` could not be installed cleanly in the local environment.
