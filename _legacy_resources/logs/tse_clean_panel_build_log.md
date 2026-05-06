# TSE Clean Panel Build Log

## Summary

- Final municipality-year rows: 55661
- Unique municipalities: 5571
- Ever treated municipalities: 2794
- Never treated municipalities: 2777
- Hybrid municipality-year rows: 1533
- Unique hybrid municipalities: 1533
- Missing low-education shares: 0
- Missing high-education shares: 0
- Missing male shares: 0
- Missing female shares: 0
- Missing log low-education electorate: 0
- Missing log high-education electorate: 0

- Missing log male electorate: 0
- Missing log female electorate: 0

## Row Counts By Year

- 2000: 5561 rows
- 2002: 5565 rows
- 2004: 5564 rows
- 2006: 5565 rows
- 2008: 5563 rows
- 2010: 5567 rows
- 2012: 5568 rows
- 2014: 5570 rows
- 2016: 5568 rows
- 2018: 5570 rows

## Validation

- Final key `year_election + municipality_id` is unique.
- Year coverage matches the required ten election years only.
- All share variables are within `[0, 1]`.
- All `num_voters`, `num_voters_low_ed`, `num_voters_high_ed`, `num_voters_men`, and `num_voters_women` values are positive.
- All log electorate outcomes are present where their underlying counts are positive.
- `dist_treatment = -9999` iff `year_treated = 9999`.
- Otherwise `dist_treatment = year_election - year_treated`.
