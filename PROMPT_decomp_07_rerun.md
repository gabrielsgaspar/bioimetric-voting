# Prompt: Re-run Affected Decomposition Components with Corrected pct_bvr

```
CONTEXT:

Following the pct_bvr backfill (Prompt 06), the corrected source
data is now at:
  data/clean/decomposition/decomposition_data_v2.parquet

This data has the same schema as decomposition_data.parquet but
with pct_bvr (and num_voters_bvr) backfilled for years 2008, 2010,
and 2012 using 2014 values per (municipality, age_cohort, education)
cell. Two new flag columns mark imputed cells: pct_bvr_imputed and
pct_bvr_source.

The framework has five steps documented in PROMPT_decomp_01_prepare.md
through PROMPT_decomp_05_aggregate.md. Of these, only the following
depend on pct_bvr:

  Prompt 1 (data preparation): The panels include pct_bvr columns.
    Need to rebuild the panels using the corrected source.

  Prompt 4 (re-labeling): The b-bound on re-labeling uses pct_bvr
    directly. Needs to re-run.

  Prompt 5 (aggregation): Aggregates re-labeling, which has changed.
    Needs to re-run.

The following do NOT depend on pct_bvr:

  Prompt 2 (survival rates): Uses voter counts only.
  Prompt 3 (exit computation): Uses voter counts and survival rates.

Their outputs (decomposition_pretreatment_cycles.parquet,
decomposition_survival_*.parquet, decomposition_inflows.parquet,
decomposition_exit_cohort.parquet, decomposition_exit_municipality.parquet)
remain valid as-is.

This prompt re-runs Prompts 1, 4, and 5 against the corrected
source. The existing scripts in src/decomposition/ should be
reusable with minimal modification: they need to point at the new
source file and write to versioned output filenames.

Save the new outputs under data/clean/decomposition/ with the _v2
suffix:
  decomposition_panel_main_v2.parquet
  decomposition_panel_full_v2.parquet
  decomposition_residual_report_v2.parquet
  decomposition_progression_rates_v2.parquet
  decomposition_relabel_cohort_v2.parquet
  decomposition_relabel_municipality_v2.parquet
  decomposition_prediction_education_v2.parquet
  decomposition_final_municipality_v2.parquet
  decomposition_final_aggregate_v2.parquet
  decomposition_final_by_cohort_v2.parquet
  decomposition_consistency_check_v2.parquet
  decomposition_map_counts_v2.parquet
  decomposition_map_rates_v2.parquet

The original (non-v2) files are preserved as-is. This lets us
compare the before-and-after side by side.

Save code to:
  src/decomposition/07_rerun_with_v2.py (or .R)

This script can be a wrapper that calls the existing 01_prepare_data.py,
04_compute_relabel.py, and 05_aggregate_and_check.py scripts with
the v2 source file and v2 output filenames. Or it can be a
standalone script — whichever is simpler given the existing code
structure.

================================================================
GOAL
================================================================

Re-run the three affected pipeline components against the corrected
source data and produce updated decomposition estimates. The exit
estimates from Prompt 3 are reused as-is.

================================================================
PART 1: REBUILD THE PANELS (Prompt 1 RE-RUN)
================================================================

Load: data/clean/decomposition/decomposition_data_v2.parquet

Apply the same logic as PROMPT_decomp_01_prepare.md:
  - Construct the working panel (decomposition_panel_main_v2.parquet)
    excluding Inválido age cohort and zero-voter cells.
  - Construct the full panel (decomposition_panel_full_v2.parquet)
    retaining residual categories.
  - Construct the residual report (decomposition_residual_report_v2.parquet).

The two new flag columns (pct_bvr_imputed, pct_bvr_source) should
be carried through to the output panels.

Verify that the panels contain the corrected pct_bvr values. Spot
check: for the 2010 treatment cohort municipalities, pct_bvr at
year=2010 should now be substantially non-zero (around the 2014
mean for those municipalities).

================================================================
PART 2: RE-RUN RE-LABELING (Prompt 4 RE-RUN)
================================================================

Inputs (some unchanged, some new):
  data/clean/decomposition/decomposition_panel_main_v2.parquet (NEW)
  data/clean/decomposition/decomposition_panel_full_v2.parquet (NEW)
  data/clean/decomposition/decomposition_survival_municipality.parquet (UNCHANGED)
  data/clean/decomposition/decomposition_inflows.parquet (UNCHANGED)
  data/clean/decomposition/decomposition_exit_cohort.parquet (UNCHANGED)
  data/clean/decomposition/decomposition_exit_municipality.parquet (UNCHANGED)

Apply the same logic as PROMPT_decomp_04_relabel.md:
  - Estimate natural progression rates δ_{c,e} from pre-treatment
    cycles. (Same as before; depends only on voter counts.)
  - Compute predicted no-BVR education composition.
  - Allocate cohort exit under Scenarios B and C.
  - Compute re-labeling within each cohort.
  - Apply the b-bound: R_{m,t+2,c} ≤ b_{m,t+2,c} × N_{m,t+2,c},
    using the corrected pct_bvr from the v2 panels.
  - Flag cells where the bound binds.

Outputs:
  decomposition_progression_rates_v2.parquet
  decomposition_prediction_education_v2.parquet
  decomposition_relabel_cohort_v2.parquet
  decomposition_relabel_municipality_v2.parquet

The implementation should match the original Prompt 4 exactly, with
the only change being the source data file. Do NOT modify the
methodology.

Spot check: for the 2010 cohort municipalities, R_B_count should
now be non-zero (it was zero in v1 because pct_bvr was zero,
zeroing the b-bound). Print a summary of R_B_count by
year_first_any_bvr.

================================================================
PART 3: RE-RUN AGGREGATION (Prompt 5 RE-RUN)
================================================================

Inputs:
  data/clean/decomposition/decomposition_exit_municipality.parquet (UNCHANGED)
  data/clean/decomposition/decomposition_relabel_municipality_v2.parquet (NEW)
  data/clean/decomposition/decomposition_exit_cohort.parquet (UNCHANGED)
  data/clean/decomposition/decomposition_relabel_cohort_v2.parquet (NEW)
  data/clean/decomposition/decomposition_panel_main_v2.parquet (NEW; for baseline)

Apply the same logic as PROMPT_decomp_05_aggregate.md:
  - Compute final municipality-level exit and re-labeling rates
    (Scenarios B and C, b-bounded).
  - Aggregate to national totals by first_regime and overall.
  - Construct map-ready files.
  - Run the qualitative consistency check against the cross-section.

Outputs:
  decomposition_final_municipality_v2.parquet
  decomposition_final_aggregate_v2.parquet
  decomposition_final_by_cohort_v2.parquet
  decomposition_consistency_check_v2.parquet
  decomposition_map_counts_v2.parquet
  decomposition_map_rates_v2.parquet

================================================================
PART 4: COMPARE V1 VS V2 RESULTS
================================================================

Print a side-by-side comparison to screen, and save it to:
  data/clean/decomposition/decomposition_v1_vs_v2_comparison.parquet

The comparison should show:

Aggregate headline numbers:
                                     V1          V2          delta
National exit count                  ___         ___         ___
National exit rate (2008 baseline)   8.35%       ___%        ___pp
National R_B count                   3,657,637   ___         ___
National R_B rate (2008 baseline)    3.93%       ___%        ___pp
National R_C count                   4,939,153   ___         ___
National R_C rate (2008 baseline)    5.30%       ___%        ___pp

Re-labeling by treatment cohort year:
                              V1 R_B_count    V2 R_B_count    delta
2010 cohort                   0               ___             ___
2012 cohort                   0               ___             ___
2014 cohort                   1,065,543       ___             ___
2016 cohort                   1,383,790       ___             ___
2018 cohort                   1,208,304       ___             ___

State-level changes for AL and SE (where v1 R_B was zero):
                              V1 R_B_rate     V2 R_B_rate
AL                            0.00%           ___%
SE                            0.00%           ___%

Cross-section consistency check:
                              Cross-section   V1          V2
Exit (2008 / 2006-rescaled)   12.60%          8.35% / 8.65%   ___% / ___%
R_B lower bound               5.22%           3.93% / 4.07%   ___% / ___%
R_C scenario value            10.40%          5.30% / 5.50%   ___% / ___%

Direction agreement: should remain "same_sign" for all metrics.
Magnitude agreement: should remain or improve to "within_factor_2"
for all metrics. If V2 brings R_B closer to the 5.22% lower bound,
the consistency check tightens.

================================================================
PART 5: REPORT TO SCREEN
================================================================

Print a clean summary at the end:

================================================================
Decomposition Re-run with Corrected pct_bvr — Summary
================================================================

Source: data/clean/decomposition/decomposition_data_v2.parquet
  pct_bvr backfilled for 2008, 2010, 2012 from 2014 values

Re-run components: Prompts 1, 4, 5 (Prompts 2, 3 unchanged)

Headline changes:
  National exit:        8.35% → ___% (change: ___pp)
  National R_B:         3.93% → ___% (change: ___pp)
  National R_C:         5.30% → ___% (change: ___pp)

The 2010 and 2012 treatment cohorts now contribute non-zero
re-labeling, which they didn't in v1 because the b-bound was
binding at zero due to missing pre-2014 pct_bvr data.

Consistency check status:
  V1: All three metrics within_factor_2, same_sign
  V2: All three metrics within_factor_2, same_sign [or: tighter agreement]

Files produced: 13 v2 parquet files under data/clean/decomposition/
plus 1 comparison file.

================================================================
CRITICAL REMINDERS
================================================================

1. The exit computations from Prompt 3 are NOT re-run. The exit
   estimates depend only on voter counts and survival rates,
   neither of which changed. Reuse the original exit_*.parquet
   files.

2. The survival rate estimates from Prompt 2 are NOT re-run. They
   use only voter counts. Reuse the original survival_*.parquet
   files.

3. The methodology is unchanged. Only the input data has been
   corrected. If the v2 implementation differs from v1 in any
   substantive way (e.g., different progression rate estimation
   or different b-bound formula), that is a bug. Match v1 exactly
   except for the source file.

4. Use _v2 suffixes for all outputs to preserve the original v1
   files. This lets us compare before-and-after.

5. The flags pct_bvr_imputed and pct_bvr_source should propagate
   through the panels into the re-labeling output, so downstream
   diagnostics can identify which cells used imputed values.

6. If the v2 R_B aggregate moves closer to the cross-section lower
   bound (5.22%), this is favorable evidence for the framework's
   internal consistency. If it overshoots the upper bound (17.82%),
   that's a problem and would suggest the imputation is too
   aggressive.

7. Print the comparison table prominently so the user can assess
   the magnitude of the v1-to-v2 changes.

Good luck. The goal is updated decomposition estimates that use the
corrected pct_bvr data. The headline numbers should improve modestly,
particularly for re-labeling, and the consistency check with the
cross-section should tighten.
```
