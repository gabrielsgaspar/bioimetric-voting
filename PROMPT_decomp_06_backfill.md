# Prompt: Fix pct_bvr Backfill for Pre-2014 Years

```
CONTEXT:

A diagnostic review of the municipality-level decomposition output
(documented in PROMPT_REPORT.md) revealed that pct_bvr is uniformly
zero in years 2008, 2010, and 2012, even for municipalities that
were demonstrably treated in those years. This is a TSE source-data
coverage limitation: biometric registration counts (qt_eleitores_
biometria) were only published from 2014 onward at the cell level.
The implementation treated missing pre-2014 pct_bvr as zero, which
caused the b-bound on re-labeling (equation eq:relabel_pctbvr_bound
in decomposition_mun.tex) to bind at zero for 2010 and 2012
treatment cohorts, mechanically zeroing out their re-labeling
estimates.

The fix is to backfill pre-2014 pct_bvr values from the 2014 value
for the same (municipality, age_cohort, education) cell. This
treats the 2014 observed pct_bvr as a backward-projection for
2008, 2010, and 2012, which is defensible because:

1. The pre-2014 cells for 2010 and 2012 treatment cohorts are
   already in their post-treatment phase (BVR has been applied),
   and their true biometric uptake at adoption was non-zero by
   construction.

2. For cells where the municipality was not yet treated in the
   pre-2014 year, the original zero pct_bvr is conceptually
   correct (no BVR applied), but applying the 2014 value as a
   backfill is still benign because these cells are not used in
   downstream re-labeling computation (they are pre-treatment for
   the framework). The b-bound only enters at adoption-cycle
   t+2, which by definition is post-treatment.

3. Cells with no 2014 observation (e.g., municipality dissolved
   before 2014, cohort emptied) cannot be backfilled and retain
   their original value (zero), with a flag indicating no
   backfill source was available.

This prompt does NOT re-run any framework component. It produces a
corrected source file that downstream prompts can consume.

Save the corrected file to:
  data/clean/decomposition/decomposition_data_v2.parquet

Save a backfill audit file to:
  data/clean/decomposition/decomposition_pct_bvr_backfill_audit.parquet

Save code to:
  src/decomposition/06_backfill_pct_bvr.py (or .R)

================================================================
GOAL
================================================================

Produce a corrected source data file in which pct_bvr for years
2008, 2010, and 2012 is filled with the 2014 value of pct_bvr for
the same (municipality, age_cohort, education) cell. Cells where
no 2014 observation exists retain their original pct_bvr value
(zero) and are flagged in the audit.

Also recompute num_voters_bvr to be consistent with the corrected
pct_bvr, since num_voters_bvr = pct_bvr × num_voters by definition.
Imputed num_voters_bvr should be rounded to the nearest integer.

================================================================
PART 1: LOAD THE SOURCE DATA
================================================================

Load the original source file:
  data/clean/decomposition/decomposition_data.parquet

Confirm the schema matches expectations: (year, ibge_municipality_id,
state, bvr_status, year_first_any_bvr, year_first_strict_bvr,
year_first_hybrid_bvr, age_cohort, education, low_ed, high_ed,
num_voters, num_voters_bvr, pct_bvr).

Print the pre-fix descriptives to the screen:

For each year in {2008, 2010, 2012, 2014, 2016, 2018}:
  - Total cells (rows where num_voters > 0)
  - Cells with pct_bvr > 0
  - Share of cells with pct_bvr > 0

Expected pattern: 0% of cells have pct_bvr > 0 in 2008, 2010, 2012;
substantial shares in 2014, 2016, 2018.

================================================================
PART 2: BUILD THE 2014 LOOKUP TABLE
================================================================

For each (ibge_municipality_id, age_cohort, education) cell present
in 2014, extract its pct_bvr and num_voters_bvr values. This is the
backfill source.

Save the lookup table internally for the imputation step. It
should have:
  ibge_municipality_id, age_cohort, education, pct_bvr_2014_source,
  num_voters_bvr_2014_source.

Report the size of this lookup table: number of cells with 2014
observations.

================================================================
PART 3: APPLY THE BACKFILL
================================================================

For each row in the source data with year ∈ {2008, 2010, 2012}:

If a matching cell exists in the 2014 lookup table:
  - Replace pct_bvr with the 2014 value
  - Replace num_voters_bvr with round(pct_bvr_2014 * num_voters)
  - Add a flag: pct_bvr_imputed = TRUE
  - Add a flag: pct_bvr_source = "2014_backfill"

If no matching cell exists in 2014 lookup table:
  - Keep original pct_bvr (zero)
  - Keep original num_voters_bvr
  - Add flags: pct_bvr_imputed = FALSE, pct_bvr_source = "no_match_kept_zero"

For each row with year ∈ {2014, 2016, 2018}:
  - Keep original values
  - Add flags: pct_bvr_imputed = FALSE, pct_bvr_source = "observed"

The output file should have the original 14 columns plus the two
new flag columns: pct_bvr_imputed (bool) and pct_bvr_source (string).

================================================================
PART 4: SANITY CHECK THE CORRECTED DATA
================================================================

After applying the backfill, compute and print to screen:

For each year in {2008, 2010, 2012}:
  - Number of cells imputed
  - Number of cells where no 2014 source was available (kept zero)
  - Mean pct_bvr after backfill (should be in 0.4-0.7 range, since
    most cells get backfilled with 2014 values which themselves
    average ~0.5)

For each year in {2014, 2016, 2018}:
  - Number of cells observed (no change)
  - Mean pct_bvr (should be unchanged from original)

Specific spot checks:
  - The 3 municipalities with year_first_any_bvr == 2008: their
    pct_bvr at year=2008 should now be non-zero for most cells.
    Print their cell-level pct_bvr distribution at year=2008.
  - The 57 municipalities with year_first_any_bvr == 2010: their
    pct_bvr at year=2010 should now be non-zero. Print summary.
  - The 238 municipalities with year_first_any_bvr == 2012: their
    pct_bvr at year=2012 should now be non-zero. Print summary.

If any of these spot checks fail (e.g., the 2010 cohort still shows
mostly zero pct_bvr after backfill), report the failure and
investigate. Possible causes: cell turnover between 2010 and 2014
(unlikely to be widespread), municipalities dissolved before 2014
(rare), or implementation bug.

================================================================
PART 5: SAVE THE OUTPUTS
================================================================

Save the corrected data:
  data/clean/decomposition/decomposition_data_v2.parquet

Columns: original 14 + pct_bvr_imputed + pct_bvr_source = 16 total.

Save the backfill audit:
  data/clean/decomposition/decomposition_pct_bvr_backfill_audit.parquet

Columns: year, n_cells_total, n_cells_observed, n_cells_imputed_from_2014,
n_cells_no_match_kept_zero, mean_pct_bvr_before, mean_pct_bvr_after.

This serves as transparent documentation of what the backfill did.

================================================================
PART 6: REPORT TO SCREEN
================================================================

Print a clean summary:

================================================================
pct_bvr Backfill — Summary
================================================================

Source file: data/clean/decomposition/decomposition_data.parquet
Output file: data/clean/decomposition/decomposition_data_v2.parquet

Pre-backfill state:
  Year 2008: ___ cells, ___% with pct_bvr > 0
  Year 2010: ___ cells, ___% with pct_bvr > 0
  Year 2012: ___ cells, ___% with pct_bvr > 0
  Year 2014: ___ cells, ___% with pct_bvr > 0
  Year 2016: ___ cells, ___% with pct_bvr > 0
  Year 2018: ___ cells, ___% with pct_bvr > 0

Post-backfill state:
  Year 2008: ___ cells imputed (___%), ___ no-match (___%)
  Year 2010: ___ cells imputed (___%), ___ no-match (___%)
  Year 2012: ___ cells imputed (___%), ___ no-match (___%)
  Year 2014: ___ cells observed (no change)
  Year 2016: ___ cells observed (no change)
  Year 2018: ___ cells observed (no change)

Spot checks for treated cohorts:
  2008 cohort (3 municipalities): mean pct_bvr at year=2008 was 0.0%,
    now ___%.
  2010 cohort (57 municipalities): mean pct_bvr at year=2010 was 0.0%,
    now ___%.
  2012 cohort (238 municipalities): mean pct_bvr at year=2012 was 0.0%,
    now ___%.

================================================================
CRITICAL REMINDERS
================================================================

1. This prompt does NOT re-run the framework. It only corrects the
   source data.

2. The original file decomposition_data.parquet is preserved. The
   corrected file is decomposition_data_v2.parquet.

3. The flag pct_bvr_imputed transparently marks which cells were
   modified. Downstream analyses can use this flag to apply lower
   confidence to imputed cells if desired, but the framework's
   default is to treat them as observed.

4. The backfill assumes 2014 pct_bvr is informative about pre-2014
   pct_bvr for the same cell. This is approximately true for cells
   where biometric uptake was driven primarily by enforcement
   (strict cohorts) and stable across years post-adoption. It is
   less defensible for cells with substantial post-adoption uptake
   trajectories. The implementation does not attempt to model
   trajectories; the backfill is a single-value imputation.

5. If the 2014 lookup table is missing more than 5% of expected
   pre-2014 cells, flag this prominently in the report. This
   indicates substantial cell-level turnover between pre-2014 and
   2014 elections, which complicates the imputation.

6. Save all outputs under data/clean/decomposition/ and code under
   src/decomposition/ as per project conventions.

Good luck. The goal is a corrected source file that downstream
prompts can consume to produce updated decomposition estimates.
```
