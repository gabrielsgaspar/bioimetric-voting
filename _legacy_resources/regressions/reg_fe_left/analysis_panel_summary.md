# Analysis Panel Summary

The analysis panel has 5,565 complete municipalities after merging the presidential vote panel, treatment timing, 2010 controls, region, and the 2006-2010 PC1.

## Merge Diagnostics

- Treatment nonmatches: 0.
- Control nonmatches: 5.
- PC1 nonmatches: 5.
- First-regime counts: `{'strict': 2477, 'hybrid': 1845, 'never_treated': 1243}`.
- First-treatment-year counts: `{2008: 3, 2010: 57, 2012: 238, 2014: 465, 2016: 1618, 2018: 1941, 9999: 1243}`.

## Regression Samples

| sample   |   rows |   states |   never_treated |   strict_first |   hybrid_first |   bvr_by_2014 |   bvr_by_2018 |
|:---------|-------:|---------:|----------------:|---------------:|---------------:|--------------:|--------------:|
| test1    |   2006 |       27 |            1243 |            761 |              2 |           763 |           763 |
| test2    |   5565 |       27 |            1243 |           2477 |           1845 |           763 |          4322 |
| placebo2 |   4802 |       23 |            1243 |           1716 |           1843 |             0 |          3559 |

## Cohorts In Full Test Sample

|   year_first_any_bvr | first_regime   |   n_municipalities |
|---------------------:|:---------------|-------------------:|
|                 2008 | strict         |                  3 |
|                 2010 | strict         |                 57 |
|                 2012 | strict         |                238 |
|                 2014 | hybrid         |                  2 |
|                 2014 | strict         |                463 |
|                 2016 | hybrid         |                839 |
|                 2016 | strict         |                779 |
|                 2018 | hybrid         |               1004 |
|                 2018 | strict         |                937 |
|                 9999 | never_treated  |               1243 |

The Test 1 sample keeps never-treated municipalities and municipalities first treated by 2014, excluding municipalities first treated in 2016 or 2018. The Test 2 sample includes all complete municipalities because every treated municipality in this panel is treated by 2018 or never treated. The placebo-2 sample keeps never-treated municipalities and municipalities first treated in 2016 or 2018.
