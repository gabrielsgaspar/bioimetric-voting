# TWFE Dynamic BVR Log

## Files Used

- Data: `data/clean/tse/tse_clean_panel_2000_2018.csv`
- Estimator runner: `.agents/skills/did-estimators/scripts/run_estimator.R`
- TWFE estimator script: `.agents/skills/did-estimators/scripts/estimator_twfe_dynamic.R`
- Configs:
  - `.agents/skills/did-estimators/examples/config_twfe_bvr_log_num_voters.yml`
  - `.agents/skills/did-estimators/examples/config_twfe_bvr_log_low_ed.yml`
  - `.agents/skills/did-estimators/examples/config_twfe_bvr_log_high_ed.yml`
  - `.agents/skills/did-estimators/examples/config_twfe_bvr_log_men.yml`
  - `.agents/skills/did-estimators/examples/config_twfe_bvr_log_women.yml`
  - `.agents/skills/did-estimators/examples/config_twfe_bvr_low_ed.yml`
  - `.agents/skills/did-estimators/examples/config_twfe_bvr_high_ed.yml`
  - `.agents/skills/did-estimators/examples/config_twfe_bvr_pct_men.yml`
  - `.agents/skills/did-estimators/examples/config_twfe_bvr_pct_women.yml`

## Specification

- Estimator: dynamic TWFE event study
- Fixed effects: municipality and election year
- Event-time variable: `dist_treatment`
- Treatment cohort variable: `year_treated`
- Reference period: `-2`
- Event window: `[-8, 8]`
- Clustered standard errors: `municipality_id` and `year_election`
- Plot titles: omitted

## Sample

- Input municipality-year observations: `55,661`
- Unique municipalities: `5,571`
- Ever treated municipalities: `2,794`
- Never treated municipalities: `2,777`

These counts are the validated input sample written to each outcome folder's `sample_diagnostics.csv`.

## Outputs Refreshed

- `resources/did/twfe_dynamic/log_num_voters/`
- `resources/did/twfe_dynamic/log_num_voters_low_ed/`
- `resources/did/twfe_dynamic/log_num_voters_high_ed/`
- `resources/did/twfe_dynamic/log_num_voters_men/`
- `resources/did/twfe_dynamic/log_num_voters_women/`
- `resources/did/twfe_dynamic/pct_voters_low_ed/`
- `resources/did/twfe_dynamic/pct_voters_high_ed/`
- `resources/did/twfe_dynamic/pct_voters_men/`
- `resources/did/twfe_dynamic/pct_voters_women/`

## Added Outcomes

- `log_num_voters_low_ed`: log number of registered voters in the low-education categories.
- `log_num_voters_high_ed`: log number of registered voters in the high-education categories.
- `log_num_voters_men`: log number of male registered voters.
- `log_num_voters_women`: log number of female registered voters.
- `pct_voters_men`: share of male registered voters in the municipality-year electorate.
- `pct_voters_women`: share of female registered voters in the municipality-year electorate.
- All of these outcomes are built in `src/analysis/build_tse_clean_panel.py` from the municipality-year electorate counts and are defined everywhere in the final clean panel.

## Estimation Notes

- `fixest` reported that one singleton fixed-effect observation was removed in each run.
- `fixest` also warned that the clustered VCOV matrix was not positive definite and was numerically fixed.
- These are warnings, not hard errors, but they should be kept in mind when interpreting the TWFE event-study uncertainty bands.

## Framing Warning

This is the simple TWFE baseline event study used for comparability with the notebook/paper section. Under staggered treatment timing with heterogeneous effects, TWFE event studies can be misleading relative to modern staggered-DiD estimators.
