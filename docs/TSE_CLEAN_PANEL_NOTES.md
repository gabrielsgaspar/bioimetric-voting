# TSE Clean Panel Notes

## Input Files Used

- Electorate input: `data/clean/tse_eleitorado/eleitorado_education_gender_2000_2018.parquet`
- BVR treatment input: `data/clean/tse_bvr/municipality_bvr_first_treat.parquet`
- Optional municipality crosswalk reference available in repo: `data/raw/ibge/bd-tse_mun_ids.csv`

## Election Years Retained

The final panel is restricted to the ten election years:

- 2000
- 2002
- 2004
- 2006
- 2008
- 2010
- 2012
- 2014
- 2016
- 2018

Row counts by year:

2000    5561
2002    5565
2004    5564
2006    5565
2008    5563
2010    5567
2012    5568
2014    5570
2016    5568
2018    5570

## Education Mapping Used

Low education is defined as less than high school and includes:

- `illiterate`
- `reads_and_writes`
- `incomplete_primary`
- `complete_primary`

High education is defined as high school or more and includes:

- `incomplete_secondary`
- `complete_secondary`
- `incomplete_higher`
- `complete_higher`

The upstream electorate file also includes `unknown`. The final panel uses:

- denominator = total municipality-year electorate, including `unknown`
- numerator for low/high shares = only the mapped categories above

As a result, `pct_voters_low_ed + pct_voters_high_ed` can be less than 1 when `unknown` education is present.

## Gender Mapping Used

The upstream electorate file uses:

- `male`
- `female`
- `unknown`

The final panel uses:

- `num_voters_men` = male voters
- `num_voters_women` = female voters
- `log_num_voters_men` = log male voters
- `log_num_voters_women` = log female voters
- `pct_voters_men` = male voters / total municipality-year electorate
- `pct_voters_women` = female voters / total municipality-year electorate

As with education, the denominator includes `unknown`, so `pct_voters_men + pct_voters_women` can be less than 1.

## Treatment Timing Merge

The BVR treatment file is municipality-zone level in some years. For the municipality-level panel, treatment is first collapsed to municipality level by:

- grouping on `municipality_id`
- taking the minimum `year_first_treat` within municipality

The collapsed field is renamed `year_treated` in the final panel.
Municipalities never treated by 2018 are assigned `year_treated = 9999`.

Municipalities with multiple treatment rows in the source BVR file: 0
Municipalities with multiple distinct treatment years in the source BVR file: 0

## Hybrid Status Variable

The final panel now includes a binary `hybrid` indicator:

- `hybrid = 1` if the municipality is explicitly marked as `Híbrido` in the official TSE 2018 electorate file
- `hybrid = 0` otherwise

The current repo has an official municipality-level hybrid source for 2018 only. Because municipality-level hybrid coding for 2016 remains unresolved, this panel does not impute hybrid status for earlier years.

- Hybrid municipality-year rows in the final panel: 1533
- Unique municipalities flagged as hybrid: 1533

## Distance-to-Treatment Formula

The final panel defines:

- `year_treated = 9999` if the municipality is never treated
- `dist_treatment = -9999` if `year_treated = 9999`
- otherwise `dist_treatment = year_election - year_treated`

This keeps the measure in calendar-year differences rather than election-count units.

## Municipality Name and State Handling

- `municipality_id` is treated as the primary key.
- `state` is taken from the cleaned electorate input and validated against the 27 official UFs.
- `municipality_name` is rebuilt from the most common cleaned electorate name observed for each `municipality_id` across the panel, then normalized to lower-case ASCII with stripped punctuation and collapsed spaces.

## Validation Results

- Municipality-year rows: 55661
- Unique municipalities: 5571
- Ever treated municipalities: 2794
- Never treated municipalities: 2777
- Hybrid municipality-year rows: 1533
- Unique hybrid municipalities: 1533
- Missing `pct_voters_low_ed`: 0
- Missing `pct_voters_high_ed`: 0
- Missing `pct_voters_men`: 0
- Missing `pct_voters_women`: 0
- Missing `log_num_voters_low_ed`: 0
- Missing `log_num_voters_high_ed`: 0
- Missing `log_num_voters_men`: 0
- Missing `log_num_voters_women`: 0
- All final keys are unique on `year_election + municipality_id`.
- All pct variables are within `[0, 1]`.
- All `num_voters`, `num_voters_low_ed`, `num_voters_high_ed`, `num_voters_men`, and `num_voters_women` values are positive, so all log electorate outcomes are defined everywhere in the final panel.

Average residual education share `1 - low - high` by year:

2000    0.002521
2002    0.002258
2004    0.001879
2006    0.001705
2008    0.001464
2010    0.001334
2012    0.001160
2014    0.001013
2016    0.000789
2018    0.000470

Average residual gender share `1 - men - women` by year:

2000    0.001574
2002    0.001417
2004    0.001151
2006    0.001038
2008    0.000884
2010    0.000801
2012    0.000691
2014    0.000619
2016    0.000491
2018    0.000294

## Caveats and Unresolved Issues

- Because education and gender unknown categories are kept in the denominator, the reported composition shares are intentionally conservative and may sum to less than 1.
- Municipality-level treatment timing collapses any zone-level variation to the earliest treated election year within municipality.
- The `hybrid` indicator is only sourced from the official 2018 TSE municipality status file. It should be interpreted as a year-specific status measure, not as a full history of hybrid implementation before 2018.
- The panel inherits any residual upstream limitations from the clean electorate file and the clean BVR timing file, but it does not introduce additional fuzzy municipality matching.
