# LAPOP Backlash Regressions Notes

## Why This Uses The 2021 Public File

- The draft section in `backlash.tex` was written as a `2023` LAPOP exercise tied to the `2022` presidential election.
- On April 23, 2026, the official Vanderbilt Brazil country page listed a `2023` Brazil study and linked its technical report, but the public dataset app route `https://lapop.app.vanderbilt.edu/datasets/download/bra_2023` returned an HTTP 500 error in this environment.
- The official public microdata file available locally and reproducibly in the repository is therefore `data/raw/lapop/2021/bra_2021_cy_spa-eng_p_v1-2.dta`.
- The public `2021` file contains the electoral-integrity battery (`countfair1` and `countfair3`) but does not expose an individual presidential vote-choice variable.
- The public `2019` file contains presidential vote choice (`vb3n`) but does not contain the `countfair` battery.
- The implemented section therefore keeps the same interaction design as the draft but uses `m1` (approval of the executive) as a respondent-level proxy for Bolsonaro alignment in the `2021` public wave.

## Inputs

- LAPOP public wave: `data/raw/lapop/2021/bra_2021_cy_spa-eng_p_v1-2.dta`
- Municipal BVR treatment timing: `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`
- Municipal population control fetched from official IBGE SIDRA table `6579`, variable `9324`, year `2021`

## Variable Construction

- `count_fair_always` = 1 when `countfair1 == 1` (`Siempre`), 0 when `countfair1` is `Algunas veces` or `Nunca`
- `ballot_secret_never` = 1 when `countfair3 == 3` (`Nunca`), 0 when `countfair3` is `Siempre` or `Algunas veces`
- `bolsonaro_approve` = 1 when `m1` is `Muy bueno` or `Bueno`, 0 when `m1` is `Ni bueno, ni malo`, `Malo`, or `Muy malo`
- `treatment_dummy` = 1 when the respondent lives in a municipality with `year_first_treat <= 2021`
- Controls retained in the integrity module sample: `low_ed`, `female`, `white`, `age`, `urban`, `log_total_pop`

## Matching Summary

- LAPOP rows with municipality/state labels: 2989
- Rows matched to IBGE municipality IDs: 2971
- Rows unmatched to IBGE municipality IDs: 18
- Unique matched municipalities: 988
- Treated share in the matched 2021 sample: 0.477
- Bolsonaro-approval share in the matched 2021 sample: 0.303

## Main Results

- Count-fair interaction estimate: 0.198 (s.e. 0.107, p = 0.063)
- Ballot-secrecy interaction estimate: -0.112 (s.e. 0.105, p = 0.283)

## Interpretation Boundary

- These are weighted cross-sectional linear-probability models with municipality-clustered standard errors.
- Because the public `2021` file does not include individual presidential vote recall, the section should refer to `Bolsonaro approval` or `Bolsonaro-aligned respondents`, not to `voting for Bolsonaro in 2022`.
- The estimates should be read as suggestive associations rather than causal effects.
