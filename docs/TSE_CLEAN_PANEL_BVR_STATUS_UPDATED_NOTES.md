# TSE Clean Panel With Updated BVR Status

This file documents `data/clean/tse/tse_clean_panel_2000_2018_bvr_status_updated.csv`
and `.parquet`.

## Construction

- Base panel: `data/clean/tse/tse_clean_panel_2000_2018`.
- Status source for 2012, 2014, 2016, and 2018:
  `data/interim/tse_bvr/quantitativo_municipios_municipio_2012_2018_matched.csv`.
- The legacy `year_treated` and `dist_treatment` columns are preserved unchanged.
- The old `hybrid` indicator is preserved as `hybrid_legacy_2018_only`.
- The updated `hybrid` indicator is year-specific and equals one when the matched
  quantitative municipality status source classifies that municipality-year as
  `hybrid_bvr`.

## Added Variables

- `bvr_status`: one of `strict_bvr`, `hybrid_bvr`, or `no_bvr`.
- `strict_bvr`, `hybrid`, `any_bvr`, `no_bvr`: mutually exclusive status flags,
  except `any_bvr`, which is the union of strict and hybrid.
- `year_first_any_bvr`, `dist_any_bvr`: first observed strict-or-hybrid BVR year
  and event time.
- `year_first_strict_bvr`, `dist_strict_bvr`: first observed strict/full BVR year
  and event time.
- `year_first_hybrid_bvr`, `dist_hybrid_bvr`: first observed hybrid BVR year
  and event time.
- `pct_with_bvr`: share of the municipality electorate with biometric registration
  in the official TSE `perfil_eleitorado` file.
- `pct_low_ed_with_bvr`: share of low-education voters with biometric registration.
- `pct_high_ed_with_bvr`: share of high-education voters with biometric registration.

## Diagnostics

|   year |   rows |   municipalities |   strict_bvr |   hybrid |   any_bvr |   no_bvr |   legacy_hybrid_2018_only |   nonmissing_pct_with_bvr |   nonmissing_pct_low_ed_with_bvr |   nonmissing_pct_high_ed_with_bvr |
|-------:|-------:|-----------------:|-------------:|---------:|----------:|---------:|--------------------------:|--------------------------:|---------------------------------:|----------------------------------:|
|   2000 |   5561 |             5561 |            0 |        0 |         0 |     5561 |                         0 |                         0 |                                0 |                                 0 |
|   2002 |   5565 |             5565 |            0 |        0 |         0 |     5565 |                         0 |                         0 |                                0 |                                 0 |
|   2004 |   5564 |             5564 |            0 |        0 |         0 |     5564 |                         0 |                         0 |                                0 |                                 0 |
|   2006 |   5565 |             5565 |            0 |        0 |         0 |     5565 |                         0 |                         0 |                                0 |                                 0 |
|   2008 |   5563 |             5563 |            3 |        0 |         3 |     5560 |                         0 |                         0 |                                0 |                                 0 |
|   2010 |   5567 |             5567 |           60 |        0 |        60 |     5507 |                         0 |                         0 |                                0 |                                 0 |
|   2012 |   5568 |             5568 |          298 |        0 |       298 |     5270 |                         0 |                         0 |                                0 |                                 0 |
|   2014 |   5570 |             5570 |          762 |        2 |       764 |     4806 |                         0 |                      5570 |                             5570 |                              5570 |
|   2016 |   5568 |             5568 |         1541 |      840 |      2381 |     3187 |                         0 |                      5568 |                             5568 |                              5568 |
|   2018 |   5570 |             5570 |         2793 |     1533 |      4326 |     1244 |                      1533 |                      5570 |                             5570 |                              5570 |

## Caveat

For election years before 2012, there is no row in the matched quantitative
status files, so `bvr_status` is derived from the legacy first-treatment timing.
For 2012 onward, status comes from the matched quantitative files.

The biometric-share variables come from
`data/clean/tse_eleitorado/eleitorado_biometric_shares_2000_2018`. They are set
to missing for years where the raw TSE biometric count is zero nationally,
because this source does not capture the known early BVR rollout before 2014.
