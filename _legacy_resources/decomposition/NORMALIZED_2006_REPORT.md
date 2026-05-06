# 2006-Normalized Decomposition Event Studies

## What Was Computed

This module constructs four count outcomes normalized by each municipality's
registered electorate in 2006:

- `y_N = num_voters / N_m_2006`
- `y_L = num_voters_low_ed / N_m_2006`
- `y_H = num_voters_high_ed / N_m_2006`
- `y_U = num_voters_unknown_ed / N_m_2006`

It then runs dynamic TWFE event studies for all four outcomes using the shared
`did-estimators` wrapper and the same specification in every run:
municipality fixed effects, election-year fixed effects, event-time bins from
`-8` to `+8`, reference period `-2`, and two-way clustered standard errors by
municipality and election year.

The normalized panel retains 5,565
municipalities and 55,636 municipality-year
observations. Six municipalities are excluded because they have no 2006
baseline observation.

## Accounting Identity

The coefficient identity `gamma_N = gamma_L + gamma_H + gamma_U` holds.

Maximum absolute residual across event times: `1.152e-15`.

The corresponding observation-level identity also holds in the normalized
panel, with a full-panel maximum residual of
`4.441e-16`.

## Event-Time 0 Coefficients

| Outcome | Description | Coefficient and 95% CI |
|---|---|---:|
| `y_N` | Registered voters | -0.1262 [-0.1380, -0.1143] |
| `y_L` | Low-education voters | -0.1798 [-0.1916, -0.1680] |
| `y_H` | High-education voters | 0.0544 [0.0427, 0.0661] |
| `y_U` | Unknown-education voters | -0.0008 [-0.0009, -0.0007] |

## Event-Time 0 Decomposition Inputs

- Re-labeling lower bound: `R_min = max(0, gamma_H^0) = 0.0544`
- Re-labeling upper bound: `R_max = -gamma_L^0 = 0.1798`
- Scenario B re-labeling: `R = gamma_H^0 = 0.0544`
- Scenario B high-education exit: `E_H = 0.0000`
- Scenario B low-education exit from the low-count accounting equation,
  `E_L = -gamma_L^0 - gamma_H^0 = 0.1254`
- Equivalently using the additive identity and treating unknown education as a
  separate residual category, `E_L = -gamma_N^0 + gamma_U^0 = 0.1254`

Note: the formula above follows directly from `gamma_L = -E_L - R` and
`R = gamma_H` under the no-high-education-exit scenario. A formula that instead
adds `gamma_H` to `-gamma_N` would not satisfy the low-count accounting equation
when `R = gamma_H`.

## Comparison With Current Section 5 Bounds

Current Section 5 reports `R_min = 6.9%` and `R_max = 13.5%` from transformed
log-count event studies. The 2006-normalized level estimates imply
`R_min = 5.4%` and `R_max = 18.0%`.

At least one new bound differs from the current Section 5 bounds by more than two percentage points; this should be investigated before rewriting Section 5.

At event time 0, the log-based implied share effects and new level coefficients are:

| Outcome | Log-implied share effect | 2006-normalized level coefficient | Difference |
|---|---:|---:|---:|
| `N` | -0.1089 | -0.1262 | -0.0172 |
| `L` | -0.1349 | -0.1798 | -0.0449 |
| `H` | 0.0686 | 0.0544 | -0.0142 |

## Outputs

- Normalized panel: `resources/decomposition/panel_normalized_2006.parquet`
- Event-study outputs:
  - `resources/decomposition/event_study_y_N/`
  - `resources/decomposition/event_study_y_L/`
  - `resources/decomposition/event_study_y_H/`
  - `resources/decomposition/event_study_y_U/`
- Identity check: `resources/decomposition/identity_check.csv`
- Identity note: `resources/decomposition/identity_check_notes.md`
- Individual plots:
  - `resources/decomposition/event_study_plot_y_N.pdf`
  - `resources/decomposition/event_study_plot_y_L.pdf`
  - `resources/decomposition/event_study_plot_y_H.pdf`
  - `resources/decomposition/event_study_plot_y_U.pdf`
- Combined plot: `resources/decomposition/event_study_plot_combined.pdf`
- Log-vs-level comparison table: `resources/decomposition/comparison_logs_vs_levels.csv`
- Log-vs-level comparison plot: `resources/decomposition/comparison_logs_vs_levels.pdf`

## Anomalies and Warnings

- The clean panel contains 5,571 municipalities, but only 5,565 have a 2006
  observation. The normalized analysis excludes the six municipalities without
  a common baseline denominator, as required.
- The event-time-zero estimates should be compared with the rough log-based
  sanity values in the prompt. Differences are expected where the log-based
  transformed semi-elasticities were previously generating the accounting
  residual.
- A same-sample check of the original log-count event studies on the retained
  2006-baseline sample gives event-time-zero coefficients of `-0.1154` for
  total voters, `-0.2591` for low-education voters, and `0.1554` for
  high-education voters. These are essentially unchanged from the existing log
  outputs, so the level/log divergence is not caused by excluding the six
  municipalities without 2006 baselines.
- `fixest` repaired non-positive-definite two-way clustered VCOV matrices for
  the `y_N`, `y_L`, and `y_H` runs. The point estimates are unaffected, but the
  confidence intervals use the repaired VCOV.
- Dynamic TWFE remains a staggered-adoption baseline estimator, so these
  estimates are intended for internal accounting consistency and comparability
  with the existing Section 4 event studies.
